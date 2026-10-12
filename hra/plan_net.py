"""
계획 AI 신경망(hra/plan_ai_design.md 5절).

상태 153칸 -> 공유 두 층(256) -> 보상 갈래 5 x 행동 칸 37(덱 28 + 레벨 3 + 남길 골드 6). 행동 갈래마다 다섯 갈래 값을
가중합하고, 가린 칸을 빼고 가장 큰 쪽을 고른다(1학기 hra/model.py를 행동 갈래로 넓힌 것). 갈래마다 따로 값을 배우니
판단마다 어느 보상 갈래가 밀었는지 꺼내 볼 수 있다.
"""
import os
import random

import torch
import torch.nn as nn

from hra.plan_state import HEADS, MASK_SIZE, SLICES, STATE_SIZE

CONFIGS = ('none', 'synergy', 'units', 'both')


def weights(config, aux_w):
    """설정 이름 -> 보상 가중치(설계 4절). 등수 1, 체력 1, 이자 0.3, 시너지·유닛 수는 켜면 aux_w."""
    assert config in CONFIGS, config
    return {'place': 1.0, 'hp': 1.0, 'econ': 0.3,
            'synergy': aux_w if config in ('synergy', 'both') else 0.0,
            'units': aux_w if config in ('units', 'both') else 0.0}


class PlanNet(nn.Module):
    def __init__(self, hidden=256):
        super().__init__()
        self.args = {'hidden': hidden}  # 불러올 때 같은 모양으로 다시 짓는다
        self.trunk = nn.Sequential(nn.Linear(STATE_SIZE, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.out = nn.Linear(hidden, len(HEADS) * MASK_SIZE)

    def forward(self, x):
        """(배치, 153) -> (배치, 5, 37)."""
        return self.out(self.trunk(x)).view(-1, len(HEADS), MASK_SIZE)


def combined(q, w):
    """(배치, 5, 37) -> 보상 가중합 (배치, 37)."""
    return sum(w[h] * q[:, i] for i, h in enumerate(HEADS))


def masked_argmax(values, mask):
    """(배치, 37) 값과 가림 -> 행동 갈래마다 가리지 않은 칸 중 가장 큰 번호 (배치, 3)."""
    v = values.masked_fill(~mask, float('-inf'))
    return torch.stack([v[:, lo:hi].argmax(1) for lo, hi in SLICES], 1)


def choose(net, state, mask, w, eps=(0.0, 0.0, 0.0), rng=random):
    """상태 하나 -> 계획 (덱, 레벨, 남길 골드). eps는 행동 갈래마다 무작위로 고를 몫이다. 무작위로 골라도 가린 칸은 안 고른다."""
    with torch.no_grad():
        q = net(torch.as_tensor(state, dtype=torch.float32).unsqueeze(0))
    plan = masked_argmax(combined(q, w), torch.as_tensor(mask, dtype=torch.bool).unsqueeze(0))[0].tolist()
    for i, (lo, hi) in enumerate(SLICES):
        if rng.random() < eps[i]:
            plan[i] = rng.choice([j for j in range(hi - lo) if mask[lo + j]])
    return tuple(plan)


def flip_rate(net, states, masks_, w):
    """보조 갈래(시너지·유닛 수)를 뺐을 때 계획이 바뀌는 판단의 몫(설계 4절 사전 시험, 5절 중간 점검)."""
    if not len(states):
        return 0.0
    with torch.no_grad():
        q = net(torch.as_tensor(states, dtype=torch.float32))
    m = torch.as_tensor(masks_, dtype=torch.bool)
    a = masked_argmax(combined(q, w), m)
    b = masked_argmax(combined(q, dict(w, synergy=0.0, units=0.0)), m)
    return float((a != b).any(1).float().mean())


def save(net, path, w, **meta):
    """신경망·보상 가중치·설명(meta, 기본형만)을 함께 저장한다. 다른 프로세스가 읽는 중에 덮지 않게 임시 파일에 쓰고 바꾼다."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    torch.save({'args': net.args, 'state_dict': net.state_dict(), 'weights': dict(w), 'meta': meta}, tmp)
    os.replace(tmp, path)


def load(path):
    ck = torch.load(path, map_location='cpu', weights_only=True)
    net = PlanNet(**ck['args'])
    net.load_state_dict(ck['state_dict'])
    net.eval()
    return net, ck['weights'], ck['meta']
