"""
풀게임 A/B.

한 게임(8명) 안에서 절반은 새 정책, 절반은 시뮬레이터 기본 봇으로 돌린다.
같은 게임 안에서 붙이므로 패치/RNG 조건이 공유되고, 등수는 합이 고정된
zero-sum 이라 두 집단 차이만 보면 된다.

어느 슬롯을 새 정책에 줄지는 매 게임 무작위로 바꾼다(자리 편향 제거).

실행: python -m fullgame.ab_test 40
"""
import contextlib
import os
import random
import sys

import numpy as np

import config
from Simulator.tft_simulator import parallel_env, TFTConfig
from Simulator.observation.token.basic_observation import ObservationToken

try:
    import utils
except ImportError:
    from Simulator import utils

from analysis.comps import COMPS
from fullgame.policy import attach

N_PLAYERS = config.NUM_PLAYERS
# analysis/comps.py 의 low_coherent. 1~3코 중심이라 슬로우롤로 별을 올릴 여지가 있는 쪽이다.
# high 조합으로 바꾸면 리롤로는 별이 안 올라서 A/B 자체가 성립하지 않는다.
COMP = [name for name, _ in COMPS['low_coherent']]


@contextlib.contextmanager
def quiet():
    """시뮬레이터가 라운드마다 찍는 로그를 잠시 막는다."""
    saved = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stdout = saved


def star_counts(player):
    # board_stars.py 에 같은 함수가 있다. 옮겨 붙였다.
    counts = {1: 0, 2: 0, 3: 0}
    for row in player.board:
        for unit in row:
            if unit:
                star = getattr(unit, 'stars', 1)
                counts[star] = counts.get(star, 0) + 1
    return counts


def run_game(treated):
    """treated 에 든 인덱스의 플레이어만 새 정책. 반환: 등수, 최종 보드 상태."""
    cfg = TFTConfig(observation_class=ObservationToken,
                    max_actions_per_round=config.ACTIONS_PER_TURN)
    env = parallel_env(cfg)
    obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
    ids = list(info.keys())

    for i, agent_id in enumerate(ids):
        if i in treated:
            attach(info[agent_id]['player'], COMP)

    placement, final, rank = {}, {}, N_PLAYERS
    # 종료 신호를 놓치면 루프가 안 끝난다. 상한에 걸린 판은 아래에서 등수를 메운다.
    guard = 0
    while obs and guard < 5000:
        guard += 1
        alive = list(obs.keys())
        actions = [info[a]['player'].default_policy(info[a]['game_round'],
                                                    info[a]['shop'],
                                                    obs[a]['action_mask'])
                   for a in alive]
        decoded = utils.decode_action(actions)
        obs, _, terminated, _, info = env.step(
            {a: decoded[i] for i, a in enumerate(alive)})

        for agent_id, done in terminated.items():
            if done and agent_id not in placement:
                placement[agent_id] = rank
                rank -= 1
                player = info[agent_id]['player']
                counts = star_counts(player)
                final[agent_id] = (getattr(player, 'level', 0),
                                   counts[1], counts[2], counts[3])

    # 끝까지 살아남아 terminated 가 안 온 플레이어. 등수 합이 어긋나면
    # zero-sum 가정이 깨져서 두 집단 평균 차이를 못 믿는다.
    for agent_id in ids:
        if agent_id not in placement:
            placement[agent_id] = rank
            rank -= 1
            final.setdefault(agent_id, (0, 0, 0, 0))
    return ids, placement, final


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    treated_stats = {'place': [], 'level': [], 's1': [], 's2': [], 's3': []}
    control_stats = {'place': [], 'level': [], 's1': [], 's2': [], 's3': []}
    diffs = []

    for g in range(n_games):
        treated = set(random.sample(range(N_PLAYERS), N_PLAYERS // 2))
        with quiet():
            ids, placement, final = run_game(treated)

        t_place = np.mean([placement[ids[i]] for i in treated])
        c_place = np.mean([placement[ids[i]] for i in range(N_PLAYERS) if i not in treated])
        diffs.append(c_place - t_place)

        for i in range(N_PLAYERS):
            bucket = treated_stats if i in treated else control_stats
            level, s1, s2, s3 = final[ids[i]]
            bucket['place'].append(placement[ids[i]])
            bucket['level'].append(level)
            bucket['s1'].append(s1)
            bucket['s2'].append(s2)
            bucket['s3'].append(s3)
        print(f'  {g + 1}/{n_games}: 새 정책 {t_place:.2f} | 기본 봇 {c_place:.2f}', flush=True)

    sem = np.std(diffs) / np.sqrt(len(diffs))
    print(f'\n{n_games}게임')
    print(f"{'':14}{'새 정책':>10}{'기본 봇':>10}")
    for key, label in [('place', '평균 등수'), ('level', '평균 레벨'),
                       ('s1', '1성 유닛'), ('s2', '2성 유닛'), ('s3', '3성 유닛')]:
        print(f'  {label:<12}{np.mean(treated_stats[key]):>10.2f}'
              f'{np.mean(control_stats[key]):>10.2f}')
    print(f'\n등수 차이(기본 봇 - 새 정책): {np.mean(diffs):+.3f} +- {sem:.3f} (SEM)')
    print('양수면 새 정책이 더 좋은 등수. SEM의 2배를 넘지 않으면 차이가 있다고 보기 어렵다.')


if __name__ == '__main__':
    main()
