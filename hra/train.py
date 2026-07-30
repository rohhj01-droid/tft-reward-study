"""
다중 보상 학습기 학습 루프.

실행:
    python -m hra.train                 # 기본 가중치 board:econ = 1:0.3
    python -m hra.train --board 1 --econ 0

학습이 끝나면 레벨/골드 격자에 대해 어떤 행동을 고르는지 출력한다.
"""
import argparse
import collections
import random

import numpy as np
import torch
import torch.nn as nn

from hra.env import EconEnv, ACTIONS, HAND_POLICIES
from hra.model import HRANet

HEADS = ['board', 'econ']
STATE_DIM = 6
GAMMA = 0.97
BATCH = 128
LR = 5e-4
BUFFER = 20000
# 보상 스케일. board_value 증가분은 한 번에 10 이상 뛰기도 해서 그대로 쓰면 Q가 발산한다.
REWARD_SCALE = 0.1


def evaluate(net, weights, n=200):
    """탐험 없이(greedy) n판 돌려 평균 board_value를 잰다."""
    env = EconEnv()
    out = []
    for _ in range(n):
        state = env.reset()
        done = False
        while not done:
            with torch.no_grad():
                q = net(torch.tensor(state, dtype=torch.float32))
            action = int(net.combined(q, weights).argmax())
            state, _, done = env.step(action)
        out.append(env.board_value())
    return float(np.mean(out))


def train(weights, episodes=3000, seed=None, log_every=300, verbose=True):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    env = EconEnv()
    net = HRANet(STATE_DIM, len(ACTIONS), HEADS)
    target = HRANet(STATE_DIM, len(ACTIONS), HEADS)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    buf = collections.deque(maxlen=BUFFER)
    eps = 1.0
    curve = []

    def act(state):
        if random.random() < eps:
            return random.randint(0, len(ACTIONS) - 1)
        with torch.no_grad():
            q = net(torch.tensor(state, dtype=torch.float32))
        return int(net.combined(q, weights).argmax())

    for ep in range(episodes):
        state = env.reset()
        done = False
        while not done:
            action = act(state)
            nxt, reward, done = env.step(action)
            buf.append((state, action,
                        [reward[h] * REWARD_SCALE for h in HEADS], nxt, done))
            state = nxt

            if len(buf) < BATCH:
                continue
            batch = random.sample(buf, BATCH)
            s = torch.tensor([b[0] for b in batch], dtype=torch.float32)
            a = torch.tensor([b[1] for b in batch])
            r = torch.tensor([b[2] for b in batch], dtype=torch.float32)
            s2 = torch.tensor([b[3] for b in batch], dtype=torch.float32)
            d = torch.tensor([b[4] for b in batch], dtype=torch.float32)

            with torch.no_grad():
                q_next = target(s2)
                # 다음 행동은 "가중합 기준"으로 고르되, 각 헤드는 자기 값으로 부트스트랩한다.
                a_star = net.combined(q_next, weights).argmax(1)

            q = net(s)
            loss = 0
            for i, h in enumerate(HEADS):
                q_sa = q[h].gather(1, a.unsqueeze(1)).squeeze(1)
                q_next_sa = q_next[h].gather(1, a_star.unsqueeze(1)).squeeze(1)
                loss = loss + nn.functional.mse_loss(q_sa, r[:, i] + GAMMA * q_next_sa * (1 - d))
            opt.zero_grad()
            loss.backward()
            opt.step()

        eps = max(0.05, eps * 0.999)
        if ep % 50 == 0:
            target.load_state_dict(net.state_dict())
        if ep % log_every == 0:
            score = evaluate(net, weights)
            curve.append((ep, score))
            if verbose:
                print(f'ep {ep:5d}  eps {eps:.2f}  board_value {score:6.1f}')

    return net, curve


def show_policy(net, weights):
    """레벨 x 골드 격자에 대해 학습된 행동을 출력."""
    env = EconEnv()
    print('\n학습된 정책 (라운드 10 기준)')
    print(f"{'':8}" + ''.join(f'{"골드 " + str(g):>12}' for g in (20, 40, 60)))
    for level in (4, 5, 6, 7, 8):
        row = []
        for gold in (20, 40, 60):
            env.reset()
            env.level, env.gold, env.rnd = level, gold, 10
            with torch.no_grad():
                q = net(torch.tensor(env.state(), dtype=torch.float32))
            row.append(ACTIONS[int(net.combined(q, weights).argmax())])
        print(f'  레벨 {level}  ' + ''.join(f'{c:>12}' for c in row))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', type=float, default=1.0)
    ap.add_argument('--econ', type=float, default=0.3)
    ap.add_argument('--episodes', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=None)
    args = ap.parse_args()

    weights = {'board': args.board, 'econ': args.econ}
    print(f'가중치 board:econ = {args.board}:{args.econ}')

    net, curve = train(weights, episodes=args.episodes, seed=args.seed)
    show_policy(net, weights)

    print('\n수동 정책 기준선 (n=500)')
    for name, policy in HAND_POLICIES.items():
        env = EconEnv()
        scores = []
        for _ in range(500):
            env.reset()
            done = False
            while not done:
                _, _, done = env.step(policy(env))
            scores.append(env.board_value())
        print(f'  {name:12} {np.mean(scores):6.1f}')


if __name__ == '__main__':
    main()
