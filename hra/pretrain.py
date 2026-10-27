"""
데우기(hra/plan_ai_design.md 5절): 따라 하기 자료로 신경망을 데운다. 규칙의 선택에 가장 높은 값을 주게 하면서(여백 손실)
그 판의 실제 보상으로 값도 배운다(시연에서 배우는 Q학습, DQfD). 판 단위로 10%를 떼어 일치율(성공 기준 3의 첫 숫자)을 잰다.

실행: python -m hra.pretrain --config both --aux-w 0.1 --steps 20000 --out checkpoints/plan_warm_both.pt
"""
import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_learn import KEYS, Replay, learn_step
from hra.plan_net import PlanNet, combined, masked_argmax, save, weights

BATCH, LR, SYNC = 256, 2.5e-4, 1000


def split_by_game(data, held=0.1, seed=0):
    """판 단위로 떼어 낸다(같은 판의 경험이 학습과 점검으로 갈라지지 않게). (학습, 점검)."""
    games = np.unique(data['game'])
    test = np.random.default_rng(seed).choice(games, max(1, int(len(games) * held)), replace=False)
    sel = np.isin(data['game'], test)
    return {k: data[k][~sel] for k in KEYS}, {k: data[k][sel] for k in KEYS}


def agreement(net, data, w):
    """갈래별로 신경망의 가중합 선택이 정답과 같은 비율, 그리고 셋 다 같은 비율."""
    with torch.no_grad():
        q = net(torch.as_tensor(data['s'], dtype=torch.float32))
    plan = masked_argmax(combined(q, w), torch.as_tensor(data['m'], dtype=torch.bool)).numpy()
    same = plan == np.asarray(data['a'])
    return {'deck': float(same[:, 0].mean()), 'level': float(same[:, 1].mean()),
            'floor': float(same[:, 2].mean()), 'all': float(same.all(1).mean())}


def pretrain(train, w, steps, seed=0, log_every=2000, test=None):
    """train(KEYS별 배열)으로 데운 (신경망, 목표 신경망, 옵티마이저)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    demos = Replay.from_arrays(train)
    net, target = PlanNet(), PlanNet()
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    for step in range(1, steps + 1):
        learn_step(net, target, opt, w, demo=demos.sample(BATCH, rng))
        if step % SYNC == 0:
            target.load_state_dict(net.state_dict())
        if test is not None and step % log_every == 0:
            print(f'{step}걸음 떼어 둔 판 일치율 {agreement(net, test, w)}', flush=True)
    return net, target, opt


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demos', default=os.path.join('checkpoints', 'plan_demos.npz'))
    ap.add_argument('--config', default='both')
    ap.add_argument('--aux-w', type=float, default=0.3, help='보조 갈래 가중치. 사전 시험에서 0.3을 골랐다(설계 4절)')
    ap.add_argument('--steps', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=None)
    return ap


def main():
    ap = parser()
    args = ap.parse_args()
    data = dict(np.load(args.demos))
    train, test = split_by_game(data, seed=args.seed)
    w = weights(args.config, args.aux_w)
    net, _, _ = pretrain(train, w, args.steps, args.seed, test=test)
    result = agreement(net, test, w)
    print(f'떼어 둔 판 일치율: {result}')
    out = args.out or os.path.join('checkpoints', f'plan_warm_{args.config}.pt')
    save(net, out, w, config=args.config, aux_w=args.aux_w, seed=args.seed, games=0, steps=args.steps,
         agree_deck=result['deck'], agree_level=result['level'], agree_floor=result['floor'], agree_all=result['all'])
    print(f'저장: {out}')


if __name__ == '__main__':
    main()
