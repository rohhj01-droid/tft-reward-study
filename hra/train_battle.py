"""
전투 승패까지 보상 요인으로 넣고 학습한다.

hra/train.py는 board / econ 두 요인만 쓴다. board_value는 대리 지표라서 이 값이
높아도 실제로는 지는 보드가 나온다. 여기서는 win 요인을 하나 더 달아 전투 결과를
직접 최적화하게 한다. 에피소드마다 전투를 한 판 돌리므로 train.py보다 많이 느리다.

    python -m hra.train_battle --episodes 2000

시뮬레이터 저장소가 필요하다.
"""
import argparse
import collections
import random

import torch
import torch.nn as nn

from hra.env import ACTIONS
from hra.env_battle import BattleEconEnv, TIERS
from hra.model import HRANet

# 아래 학습 루프는 hra/train.py와 거의 같다. 헤드 수와 평가 방식이 달라서
# 하나로 합치려다 말았다.
HEADS = ['board', 'econ', 'win']
STATE_DIM = 6
GAMMA = 0.97
BATCH = 128
LR = 5e-4
REWARD_SCALE = 0.1


def eval_by_tier(net, weights, n=80):
    """난이도별 승률. 상대를 고정해야 티어끼리 비교가 된다."""
    out = {}
    for tier in TIERS:
        env = BattleEconEnv(fixed_tier=tier)
        wins = 0
        for _ in range(n):
            state = env.reset()
            done, win = False, 0
            # win 보상은 마지막 라운드에만 0이 아니다. 계속 덮어쓰다 마지막 값을 쓴다.
            while not done:
                with torch.no_grad():
                    q = net(torch.tensor(state, dtype=torch.float32))
                state, reward, done = env.step(int(net.combined(q, weights).argmax()))
                win = reward['win']
            wins += (win > 0)
        out[tier] = 100 * wins / n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', type=float, default=1.0)
    ap.add_argument('--econ', type=float, default=0.3)
    # win은 판당 한 번, 0 아니면 10이다. board와 econ은 매 라운드 들어온다.
    # 셋을 같은 가중치로 두면 win 신호가 묻혀서 기본값을 크게 잡았다.
    ap.add_argument('--win', type=float, default=2.0)
    ap.add_argument('--episodes', type=int, default=2000)
    args = ap.parse_args()

    weights = {'board': args.board, 'econ': args.econ, 'win': args.win}
    print(f'가중치 {weights}')

    env = BattleEconEnv()
    net = HRANet(STATE_DIM, len(ACTIONS), HEADS)
    target = HRANet(STATE_DIM, len(ACTIONS), HEADS)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    buf = collections.deque(maxlen=20000)
    eps = 1.0

    for ep in range(args.episodes):
        state = env.reset()
        done = False
        while not done:
            if random.random() < eps:
                action = random.randint(0, len(ACTIONS) - 1)
            else:
                with torch.no_grad():
                    q = net(torch.tensor(state, dtype=torch.float32))
                action = int(net.combined(q, weights).argmax())

            nxt, reward, done = env.step(action)
            buf.append((state, action, [reward[h] * REWARD_SCALE for h in HEADS], nxt, done))
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
        if ep % 300 == 0:
            rates = eval_by_tier(net, weights)
            summary = ' / '.join(f'{k} {v:.0f}%' for k, v in rates.items())
            print(f'ep {ep:5d}  eps {eps:.2f}  승률  {summary}', flush=True)


if __name__ == '__main__':
    main()
