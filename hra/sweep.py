"""
보상 가중치 스윕.

가중치 조합마다 서로 다른 시드로 반복 학습해서, 성능 차이가 시드 노이즈인지
가중치 때문인지 구분한다. 단일 실행 결과만 보면 순위가 실행마다 뒤집힌다.

실행:
    python -m hra.sweep                    # 4개 가중치 x 5시드
    python -m hra.sweep --seeds 3 --episodes 800
결과는 results/weight_sweep.csv 로 저장.
"""
import argparse
import collections
import csv
import os

import numpy as np
import torch

from hra.env import EconEnv, ACTIONS
from hra.train import train

SWEEP = [
    {'board': 1.0, 'econ': 0.0},
    {'board': 1.0, 'econ': 0.3},
    {'board': 1.0, 'econ': 0.6},
    {'board': 1.0, 'econ': 1.0},
]


def rollout_stats(net, weights, n=300):
    """평균 board_value와 행동 분포를 함께 잰다."""
    env = EconEnv()
    scores = []
    actions = collections.Counter()
    for _ in range(n):
        state = env.reset()
        done = False
        while not done:
            with torch.no_grad():
                q = net(torch.tensor(state, dtype=torch.float32))
            action = int(net.combined(q, weights).argmax())
            actions[ACTIONS[action]] += 1
            state, _, done = env.step(action)
        scores.append(env.board_value())
    total = sum(actions.values())
    roll_pct = 100 * (actions['ROLL50'] + actions['ROLLHARD']) / total
    return float(np.mean(scores)), roll_pct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=5)
    ap.add_argument('--episodes', type=int, default=1200)
    args = ap.parse_args()

    rows = []
    for weights in SWEEP:
        label = f"{weights['board']}:{weights['econ']}"
        scores, rolls = [], []
        for seed in range(args.seeds):
            net, _ = train(weights, episodes=args.episodes, seed=seed, verbose=False)
            score, roll = rollout_stats(net, weights)
            scores.append(score)
            rolls.append(roll)
            print(f'  {label}  seed {seed}: board_value {score:.1f}, ROLL {roll:.0f}%', flush=True)
        rows.append({
            'weights': label,
            'mean': round(float(np.mean(scores)), 2),
            'std': round(float(np.std(scores)), 2),
            'roll_pct': round(float(np.mean(rolls)), 1),
        })
        print(f'  -> {label}: {np.mean(scores):.1f} +- {np.std(scores):.1f}\n', flush=True)

    print(f"{'가중치(board:econ)':>20}{'board_value':>16}{'ROLL%':>8}")
    for r in rows:
        print(f"{r['weights']:>20}{r['mean']:>10.1f} +- {r['std']:<4.1f}{r['roll_pct']:>7.0f}%")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'weight_sweep.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['weights', 'mean', 'std', 'roll_pct'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'\n저장: {path}')


if __name__ == '__main__':
    main()
