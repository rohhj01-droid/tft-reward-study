"""
따라 하기 자료 모으기(hra/plan_ai_design.md 5절): 규칙 사람 봇 8명이 모두 기록하는 판을 돌려 경험을 npz로 저장한다.
시뮬레이터가 판 중간에 멈춘 판은 건너뛰고 수를 적는다. 판 번호 열(game)은 데우기에서 판 단위로 떼어 내는 데 쓴다.

실행: python -m hra.collect --games 2000 --jobs 7 --out checkpoints/plan_demos.npz
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_bot import safe_play
from hra.plan_learn import KEYS
from meta.lobby import N_PLAYERS

SEED_BASE = 900000  # 자기 대전·평가와 겹치지 않는 시드 구간


def one_game(seed):
    """한 판의 경험 목록과 오류(없으면 None)."""
    out, err = safe_play(seed, ['record'] * N_PLAYERS)
    if out is None:
        return [], err
    return [t for seat in out['seats'] for t in seat['transitions']], None


def stack(transitions, games=None):
    """경험 목록 -> KEYS별 배열. games(경험마다 판 번호)를 주면 'game' 열을 붙인다."""
    data = {key: np.stack(col) for key, col in zip(KEYS, zip(*transitions))}
    if games is not None:
        data['game'] = np.array(games)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=2000)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=os.path.join('checkpoints', 'plan_demos.npz'))
    args = ap.parse_args()
    transitions, games, errors = [], [], []
    with Pool(args.jobs) as workers:
        seeds = range(SEED_BASE, SEED_BASE + args.games)
        for k, (ts, err) in enumerate(workers.imap(one_game, seeds)):
            transitions += ts
            games += [k] * len(ts)
            if err:
                errors.append(err)
            if (k + 1) % 100 == 0:
                print(f'{k + 1}판, 경험 {len(transitions)}개, 멈춘 판 {len(errors)}', flush=True)
    data = stack(transitions, games)
    data['n_games'] = np.array(args.games - len(errors))
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    np.savez_compressed(args.out, **data)
    print(f'저장: {args.out} (경험 {len(transitions)}개, 멈춘 판 {len(errors)}개)')
    for e in errors[:5]:
        print('  ', e)


if __name__ == '__main__':
    main()
