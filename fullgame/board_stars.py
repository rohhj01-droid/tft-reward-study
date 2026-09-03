"""
기본 봇이 게임을 끝낼 때 어떤 보드를 들고 있는가.

"레벨은 올리는데 유닛 성장이 안 된다"는 관찰을 수치로 확인하기 위한 스크립트.
8명 전원 기본 봇으로 게임을 돌리고, 탈락 시점의 레벨과 별 등급 분포를 센다.

탈락 시점 기준이라 일찍 죽은 플레이어가 평균 레벨을 끌어내린다.
절대값보다 별 등급 비율을 봐야 한다.

실행: python -m fullgame.board_stars 8
"""
import contextlib
import os
import statistics
import sys

import config
from Simulator.tft_simulator import parallel_env, TFTConfig
from Simulator.observation.token.basic_observation import ObservationToken

try:
    import utils
except ImportError:
    from Simulator import utils

N_PLAYERS = config.NUM_PLAYERS


@contextlib.contextmanager
def quiet():
    saved = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stdout = saved


def star_counts(player):
    counts = {1: 0, 2: 0, 3: 0}
    for row in player.board:
        for unit in row:
            if unit:
                star = getattr(unit, 'stars', 1)
                counts[star] = counts.get(star, 0) + 1
    return counts


def run_game():
    cfg = TFTConfig(observation_class=ObservationToken,
                    max_actions_per_round=config.ACTIONS_PER_TURN)
    env = parallel_env(cfg)
    obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
    final = {}
    while obs:
        alive = list(obs.keys())
        actions = [info[a]['player'].default_policy(info[a]['game_round'],
                                                    info[a]['shop'],
                                                    obs[a]['action_mask'])
                   for a in alive]
        decoded = utils.decode_action(actions)
        obs, _, terminated, _, info = env.step(
            {a: decoded[i] for i, a in enumerate(alive)})
        for agent_id, done in terminated.items():
            if done and agent_id not in final:
                player = info[agent_id]['player']
                final[agent_id] = (getattr(player, 'level', 0), star_counts(player))
    return final


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    levels, ones, twos, threes = [], [], [], []
    for g in range(n_games):
        with quiet():
            final = run_game()
        for level, counts in final.values():
            levels.append(level)
            ones.append(counts[1])
            twos.append(counts[2])
            threes.append(counts[3])
        print(f'  {g + 1}/{n_games}', flush=True)

    total = statistics.mean(ones) + statistics.mean(twos) + statistics.mean(threes)
    total = total or 1  # 보드가 전부 빈 판만 나오면 아래 비율 계산이 터진다
    print(f'\n기본 봇 최종 보드 ({len(levels)}명)')
    print(f'  평균 레벨 {statistics.mean(levels):.2f}')
    print(f'  1성 {statistics.mean(ones):.2f}  '
          f'2성 {statistics.mean(twos):.2f}  '
          f'3성 {statistics.mean(threes):.2f}')
    print(f'  비율  1성 {statistics.mean(ones) / total * 100:.0f}%  '
          f'2성 {statistics.mean(twos) / total * 100:.0f}%  '
          f'3성 {statistics.mean(threes) / total * 100:.0f}%')


if __name__ == '__main__':
    main()
