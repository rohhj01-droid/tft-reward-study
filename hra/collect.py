"""
따라 하기 자료 모으기(hra/plan_ai_design.md 5절): 규칙 사람 봇 8명이 모두 기록하는 판을 돌려 경험을 npz로 저장한다.
시뮬레이터가 판 중간에 멈춘 판은 건너뛰고 수를 적는다. 판 번호 열(game)은 데우기에서 판 단위로 떼어 내는 데 쓴다.
100판마다 저장하고, 같은 명령을 다시 돌리면 저장된 판 다음부터 이어 간다.

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


def collect(games, jobs, out, save_every=100):
    """games판까지 모아 out에 쌓는다. save_every판마다 지금까지를 저장하고, out이 이미 있으면 저장된 판 다음부터 이어 간다
    (모으다 꺼져도 같은 명령을 다시 돌리면 된다). 저장 파일에는 KEYS·game 열과 seeds_done(돌린 판), errors(멈춘 판),
    n_games(경험을 낸 판)가 있다."""
    data = dict(np.load(out)) if os.path.exists(out) else {}
    done, errors = int(data.get('seeds_done', 0)), int(data.get('errors', 0))
    transitions, owners = [], []
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with Pool(jobs) as workers:
        for k, (ts, err) in enumerate(workers.imap(one_game, range(SEED_BASE + done, SEED_BASE + games)), done):
            transitions += ts
            owners += [k] * len(ts)
            if err:
                errors += 1
                print(f'멈춘 판 {k}: {err}', flush=True)
            if (k + 1) % save_every == 0 or k + 1 == games:
                if transitions:
                    new = stack(transitions, owners)
                    data.update({key: np.concatenate([data[key], new[key]]) if key in data else new[key] for key in new})
                    transitions, owners = [], []
                data.update(seeds_done=np.array(k + 1), errors=np.array(errors), n_games=np.array(k + 1 - errors))
                tmp = out + '.tmp.npz'
                np.savez_compressed(tmp, **data)
                os.replace(tmp, out)
                print(f'{k + 1}판, 경험 {len(data.get("s", []))}개, 멈춘 판 {errors}', flush=True)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=2000)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=os.path.join('checkpoints', 'plan_demos.npz'))
    ap.add_argument('--save-every', type=int, default=100)
    args = ap.parse_args()
    data = collect(args.games, args.jobs, args.out, args.save_every)
    print(f'저장: {args.out} (경험 {len(data.get("s", []))}개, 멈춘 판 {int(data.get("errors", 0))}개)')


if __name__ == '__main__':
    main()
