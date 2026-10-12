"""
계획 AI의 계획 번호와 상태(hra/plan_ai_design.md 2·3절).

계획은 세 갈래다: 목표 덱(0 = 그대로, 1~27 = meta/lobby.BOARDS[번호 - 1]), 목표 레벨(지금 레벨에 0~2를 더한다),
리롤할 때 남길 골드(FLOORS[번호], None은 리롤 안 함). 가림 37칸은 덱 28 + 레벨 3 + 남길 골드 6이다.
"""
import numpy as np

from set4 import COST_STAR_VALUE
from Simulator.stats import BASE_CHAMPION_LIST, COST
from hra.score_rank import tiers_of
from meta.human_deck import buildable, copies, held_items, key_units, scout, units_of
from meta.human_five import trait_table
from meta.lobby import BOARDS
from meta.pit import chosen_of

HEADS = ('place', 'hp', 'econ', 'synergy', 'units')  # 보상 갈래(설계 4절)
FLOORS = (None, 50, 30, 20, 10, 0)
PLAN_SIZES = (len(BOARDS) + 1, 3, len(FLOORS))  # (28, 3, 6)
MASK_SIZE = sum(PLAN_SIZES)                      # 37
SLICES = ((0, PLAN_SIZES[0]), (PLAN_SIZES[0], PLAN_SIZES[0] + PLAN_SIZES[1]),
          (PLAN_SIZES[0] + PLAN_SIZES[1], MASK_SIZE))


def masks(level, deck):
    """못 하는 선택을 가린 37칸. 덱이 없으면(2-1) 「그대로」를, 덱이 있으면 지금 덱을 다시 고르는 칸을 가린다
    (「그대로」와 같다). 레벨은 9를 넘는 목표를 가린다."""
    m = np.ones(MASK_SIZE, dtype=bool)
    if deck is None:
        m[0] = False
    else:
        m[BOARDS.index(deck) + 1] = False
    m[PLAN_SIZES[0] + 1] = level <= 8
    m[PLAN_SIZES[0] + 2] = level <= 7
    return m


def decode(plan, level, deck):
    """계획 번호 (덱, 레벨, 남길 골드) -> (목표 덱, 목표 레벨, 남길 골드)."""
    d, lv, fl = plan
    return (deck if d == 0 else BOARDS[d - 1]), level + lv, FLOORS[fl]


def floor_index(floor):
    """남길 골드 -> 가장 가까운 칸 번호. None(리롤 안 함)은 0번."""
    if floor is None:
        return 0
    return min(range(1, len(FLOORS)), key=lambda i: abs(FLOORS[i] - floor))


def rule_label(old_deck, new_deck, level_start, best_target, min_floor):
    """규칙 봇이 한 라운드에 한 일 -> 계획 번호(따라 하기 정답). best_target은 그 라운드에 규칙이 낸 가장 높은 목표
    레벨, min_floor는 가장 낮은 남길 골드(리롤 판단이 없었으면 None)."""
    d = 0 if new_deck is old_deck else BOARDS.index(new_deck) + 1
    lv = min(max(best_target - level_start, 0), 2, 9 - level_start)
    return d, lv, floor_index(min_floor)


STATE_SIZE = 8 + 7 + 5 * len(BOARDS) + 2 + 1  # 153


def board_units(player):
    """보드에 선 챔피언(아지르 모래 병사 같은 소환물 빼고)."""
    return [u for row in player.board for u in row if u and u.name in BASE_CHAMPION_LIST]


def active_tiers(units):
    """유닛들의 발동한 특성 단계 수. 선택받은 자 +1과 상징 아이템을 시뮬레이터처럼 센다(meta/human_five.trait_table)."""
    return tiers_of(trait_table(units))


def state(player, others, deck, deck_age, game_round):
    """153칸(설계 3절). deck은 지금 목표 덱(BOARDS의 원소 또는 None), deck_age는 그 덱을 고른 뒤 지난 라운드 수.
    실제 사람이 볼 수 있는 것만 넣고, 공략 사이트 티어 점수는 넣지 않는다. 덱마다의 앞 네 값은 규칙 봇 덱 점수
    (meta/human_deck.score)의 항과 같은 셈이다."""
    alive = [o for o in others if o.health > 0]
    units = board_units(player)
    stars = [u.stars for u in units]
    need = player.level_costs[player.level] if player.level < player.max_level else 0
    completed, components = held_items(player)
    mine, theirs = copies(units_of(player)), scout(others)
    x = [game_round / 40, player.health / 100, player.gold / 60, player.level / 9,
         player.exp / need if need else 1.0, player.win_streak / 5, player.loss_streak / 5, len(alive) / 7,
         sum(COST_STAR_VALUE[COST[u.name] - 1][u.stars - 1] for u in units) / 120,
         stars.count(2) / 9, stars.count(3) / 9, active_tiers(units) / 11, len(units) / 9,
         len(completed) / 10, len(components) / 10]
    for b in BOARDS:
        trait = (chosen_of(b) or (None, None))[1]
        x += [sum(COST[u] * min(mine.get(u, 0), 9) for u in set(b['units'])) / 40,
              sum(theirs.get(u, 0) for u in key_units(b)) / 10,
              float(bool(player.chosen) and player.chosen == trait),
              buildable(b, completed, components) / 8,
              float(b is deck)]
    x += [sum(o.health > player.health for o in alive) / 7,
          sum(o.level for o in alive) / len(alive) / 9 if alive else 0.0,
          deck_age / 20]
    return np.clip(np.array(x, dtype=np.float32), 0.0, 2.0)
