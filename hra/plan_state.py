"""
계획 AI의 계획 번호와 상태(hra/plan_ai_design.md 2·3절).

계획은 세 갈래다: 목표 덱(0 = 그대로, 1~27 = meta/lobby.BOARDS[번호 - 1]), 목표 레벨(지금 레벨에 0~2를 더한다),
리롤할 때 남길 골드(FLOORS[번호], None은 리롤 안 함). 가림 37칸은 덱 28 + 레벨 3 + 남길 골드 6이다.
"""
import numpy as np

from meta.lobby import BOARDS

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
