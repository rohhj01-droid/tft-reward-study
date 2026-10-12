"""
계획 AI 학습의 바탕(hra/plan_ai_design.md 5절): 경험 더미, 갈래별 Q 손실, 따라 하기 여백 손실, 한 걸음 학습.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from hra.plan_net import combined, masked_argmax
from hra.plan_state import HEADS, MASK_SIZE, SLICES, STATE_SIZE

GAMMA = 0.98
MARGIN = 0.8
KEYS = ('s', 'm', 'a', 'r', 's2', 'd', 'm2')  # hra/plan_bot.Recorder 경험의 순서


class Replay:
    """경험 더미(고리). 꽉 차면 가장 오래된 것부터 덮는다."""

    def __init__(self, capacity):
        self.cap, self.n, self.i = capacity, 0, 0
        self.s = np.zeros((capacity, STATE_SIZE), np.float32)
        self.m = np.zeros((capacity, MASK_SIZE), bool)
        self.a = np.zeros((capacity, 3), np.int64)
        self.r = np.zeros((capacity, len(HEADS)), np.float32)
        self.s2 = np.zeros((capacity, STATE_SIZE), np.float32)
        self.d = np.zeros(capacity, np.float32)
        self.m2 = np.zeros((capacity, MASK_SIZE), bool)

    def __len__(self):
        return self.n

    def add(self, t):
        """t = (상태, 가림, 계획, 보상, 다음 상태, 끝, 다음 가림)."""
        for key, value in zip(KEYS, t):
            getattr(self, key)[self.i] = value
        self.i = (self.i + 1) % self.cap
        self.n = min(self.n + 1, self.cap)

    def sample(self, k, rng):
        idx = rng.integers(0, self.n, k)
        return {key: torch.as_tensor(getattr(self, key)[idx]) for key in KEYS}

    def arrays(self):
        return {key: getattr(self, key)[:self.n] for key in KEYS}

    @classmethod
    def from_arrays(cls, arrays):
        n = len(arrays['s'])
        replay = cls(max(n, 1))
        for key in KEYS:
            getattr(replay, key)[:n] = arrays[key]
        replay.n, replay.i = n, n % replay.cap
        return replay


def _pick(q, a):
    """(배치, 5, 칸) 값에서 배치마다 고른 칸 -> (배치, 5)."""
    return q.gather(2, a.view(-1, 1, 1).expand(-1, q.shape[1], 1)).squeeze(2)


def td_loss(net, target, batch, w):
    """갈래별 Q 손실. 다음 행동은 지금 신경망의 가중합으로 고르고(가린 칸 빼고), 값은 갈래마다 목표 신경망의 자기 값으로
    부트스트랩한다(1학기 hra/train.py와 같은 방식을 행동 갈래 셋으로)."""
    q = net(batch['s'])
    with torch.no_grad():
        a2 = masked_argmax(combined(net(batch['s2']), w), batch['m2'])
        q2 = target(batch['s2'])
    keep = (1 - batch['d']).unsqueeze(1)
    loss = 0.0
    for i, (lo, hi) in enumerate(SLICES):
        y = batch['r'] + GAMMA * keep * _pick(q2[:, :, lo:hi], a2[:, i])
        loss = loss + F.smooth_l1_loss(_pick(q[:, :, lo:hi], batch['a'][:, i]), y)
    return loss / len(SLICES)


def margin_loss(net, batch, w):
    """따라 하기 여백 손실(DQfD): 행동 갈래마다 정답 칸의 가중합 값이 가리지 않은 다른 칸보다 MARGIN 이상 높아야 한다."""
    c = combined(net(batch['s']), w).masked_fill(~batch['m'], float('-inf'))
    loss = 0.0
    for i, (lo, hi) in enumerate(SLICES):
        v, a = c[:, lo:hi], batch['a'][:, i:i + 1]
        bonus = torch.full_like(v, MARGIN).scatter(1, a, 0.0)
        loss = loss + ((v + bonus).max(1).values - v.gather(1, a).squeeze(1)).mean()
    return loss / len(SLICES)


def learn_step(net, target, opt, w, batch=None, demo=None, lam=1.0):
    """한 걸음. batch는 자기 대전 경험(값 손실), demo는 따라 하기 경험(값 손실 + 여백 손실). 둘 중 하나는 있어야 한다."""
    loss = 0.0
    if batch is not None:
        loss = loss + td_loss(net, target, batch, w)
    if demo is not None:
        loss = loss + td_loss(net, target, demo, w) + lam * margin_loss(net, demo, w)
    opt.zero_grad()
    loss.backward()
    nn.utils.clip_grad_norm_(net.parameters(), 10.0)
    opt.step()
    return loss.item()
