"""
라벨링용 게임 상태 샘플링.

게임 단계별 프로필(라운드/레벨/골드/체력/등장 코스트)에 맞춰 그럴듯한 보드를 합성하고,
LLM에 넣을 텍스트와 분류기에 넣을 수치 피처를 함께 저장한다.

프로필을 한쪽으로 치우치게 잡으면 라벨도 한쪽으로 쏠린다. 라벨 분포를 볼 때는
프로필 구성부터 확인해야 한다(labeling/README.md).

실행: python -m labeling.sample_states 300 --out states.json
시뮬레이터 저장소가 필요하다.
"""
import argparse
import json
import random

from Simulator.pool import pool
from Simulator.player import Player
from Simulator.champion import champion
from Simulator.utils import coord_to_x_y
from Simulator.observation.token.action import ActionToken
from Simulator.default_agent_stats import (ONE_COST_UNITS, TWO_COST_UNITS, THREE_COST_UNITS,
                                           FOUR_COST_UNITS, FIVE_COST_UNITS)
from Evaluator.state_to_text import state_to_text

SPECIAL = {'azir', 'kayn'}  # 변신/소환 특수 유닛은 제외
COST_UNITS = {
    1: [u for u in ONE_COST_UNITS if u not in SPECIAL],
    2: [u for u in TWO_COST_UNITS if u not in SPECIAL],
    3: [u for u in THREE_COST_UNITS if u not in SPECIAL],
    4: [u for u in FOUR_COST_UNITS if u not in SPECIAL],
    5: [u for u in FIVE_COST_UNITS if u not in SPECIAL],
}
ITEMS = ['infinity_edge', 'guinsoos_rageblade', 'giant_slayer',
         'statikk_shiv', 'hand_of_justice', 'spear_of_shojin']

# (라운드, 레벨, 골드 범위, 체력 범위, 등장 코스트, 저코스트 별업 확률)
PROFILES = [
    ('2-1', 4, (8, 25), (80, 100), [1, 2], 0.2),
    ('2-5', 5, (10, 35), (60, 95), [1, 2, 3], 0.4),
    ('3-2', 6, (15, 45), (45, 90), [1, 2, 3, 4], 0.6),
    ('4-1', 7, (20, 55), (30, 80), [1, 2, 3, 4], 0.7),
    ('4-6', 8, (25, 60), (20, 70), [1, 2, 3, 4, 5], 0.6),
    ('5-3', 8, (30, 70), (15, 60), [2, 3, 4, 5], 0.5),
]

COST_OF = {u: c for c, units in COST_UNITS.items() for u in units}


def star_for(cost, low_star_prob):
    if cost <= 2:
        r = random.random()
        if r < low_star_prob * 0.4:
            return 3
        if r < low_star_prob:
            return 2
        return 1
    if cost == 3:
        return 2 if random.random() < 0.4 else 1
    return 1


def make_board(profile):
    _, level, _, _, costs, low_star_prob = profile
    n = max(3, min(level, random.randint(level - 1, level)))
    units, used = [], set()
    for _ in range(n):
        cost = random.choice(costs)
        candidates = [u for u in COST_UNITS[cost] if u not in used]
        if not candidates:
            continue
        name = random.choice(candidates)
        used.add(name)
        items = random.sample(ITEMS, 3) if (cost >= 3 and random.random() < 0.5) else []
        units.append(champion(name, stars=star_for(cost, low_star_prob), itemlist=items))
    return units


def build_player(base_pool, profile, units):
    player = Player(base_pool, 0)
    rnd, level, gold_range, hp_range, _, _ = profile
    player.level = level
    player.max_units = level
    player.gold = random.randint(*gold_range)
    player.health = random.randint(*hp_range)
    player.exp = random.randint(0, 20)
    streak = random.choice([0, 0, 1, 2, 3])
    if random.random() < 0.5:
        player.win_streak = streak
    else:
        player.loss_streak = streak

    for unit in units:
        player.add_to_bench(unit)
        token = ActionToken(player)
        _, bench_mask = token.create_move_and_sell_action_mask(player)
        valid = [c for c in range(28) if bench_mask[0][c]]
        if not valid:
            continue
        x, y = coord_to_x_y(random.choice(valid))
        player.move_bench_to_board(0, x, y)
    return player, rnd


def extract_features(player, stage):
    """분류기 학습용 수치 피처."""
    board = [u for row in player.board for u in row if u]
    board_value = sum(u.cost * (3 ** (getattr(u, 'stars', 1) - 1)) for u in board)
    tiers = {k: v for k, v in getattr(player, 'team_tiers', {}).items() if v > 0}
    return {
        'stage': stage,
        'level': player.level,
        'gold': player.gold,
        'interest': min(player.gold // 10, 5),
        'health': player.health,
        'win_streak': getattr(player, 'win_streak', 0),
        'loss_streak': getattr(player, 'loss_streak', 0),
        'num_units': len(board),
        'board_value': board_value,
        'num_high_cost': sum(1 for u in board if u.cost >= 4),
        'num_3star': sum(1 for u in board if getattr(u, 'stars', 1) == 3),
        'num_synergies': len(tiers),
        'max_synergy': max(tiers.values()) if tiers else 0,
        'num_items': sum(len(getattr(u, 'items', []) or []) for u in board),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int, nargs='?', default=100)
    ap.add_argument('--out', default='states.json')
    args = ap.parse_args()

    out = []
    for i in range(args.n):
        try:
            profile = random.choice(PROFILES)
            base_pool = pool()
            player, rnd = build_player(base_pool, profile, make_board(profile))
            stage = int(str(rnd).split('-')[0])
            out.append({'id': i,
                        'features': extract_features(player, stage),
                        'state_text': state_to_text(player, round_label=rnd)})
        except Exception as e:
            print(f'[skip {i}] {e}')

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'{len(out)}개 상태 저장 -> {args.out}')


if __name__ == '__main__':
    main()
