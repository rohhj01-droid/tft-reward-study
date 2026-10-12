"""
계획 AI 빠른 검사(판을 돌리지 않는다).

실행: python -m hra.test_plan
"""
import numpy as np


def board_scores_count_value_traits_units_test():
    """사람 봇 덱 Chosen Duelists(완성, 모두 2성): 보드 값 3+3+5+8+5+11+14+14 = 63(1학기 값표), 발동한 특성 단계 10, 유닛 8."""
    from hra.score_rank import board_scores
    from meta.lobby import BOARDS
    from meta.pit import chosen_of
    b = next(b for b in BOARDS if b['name'] == 'Chosen Duelists')
    assert board_scores(b['units'], b['items'], chosen_of(b)[1]) == (63, 10, 8)


def rho_skips_constant_lists_test():
    """8명 보드끼리는 유닛 수 점수가 모두 같아 순위 상관을 낼 수 없다. 그때는 None이다."""
    from hra.score_rank import rho
    assert rho([8, 8, 8], [0.1, 0.5, 0.3]) is None
    assert rho([1, 2, 3], [10, 20, 30]) == 1.0


def plan_sizes_and_slices_test():
    from hra.plan_state import HEADS, MASK_SIZE, PLAN_SIZES, SLICES
    assert HEADS == ('place', 'hp', 'econ', 'synergy', 'units')
    assert PLAN_SIZES == (28, 3, 6) and MASK_SIZE == 37
    assert SLICES == ((0, 28), (28, 31), (31, 37))


def masks_hide_impossible_plans_test():
    """덱이 없으면(2-1) 「그대로」를 가리고, 덱이 있으면 지금 덱을 다시 고르는 칸을 가린다. 레벨은 9를 넘는 목표를 가린다."""
    from hra.plan_state import masks
    from meta.lobby import BOARDS
    m = masks(3, None)
    assert not m[0] and m[1:28].all() and m[28:31].all() and m[31:].all()
    m = masks(8, BOARDS[4])
    assert m[0] and not m[5] and m[28] and m[29] and not m[30]
    assert list(masks(9, BOARDS[0])[28:31]) == [True, False, False]


def decode_turns_numbers_into_a_plan_test():
    from hra.plan_state import decode
    from meta.lobby import BOARDS
    assert decode((0, 1, 3), 5, BOARDS[2]) == (BOARDS[2], 6, 20)
    assert decode((5, 0, 0), 4, None) == (BOARDS[4], 4, None)


def floor_index_picks_nearest_floor_test():
    from hra.plan_state import floor_index
    assert [floor_index(f) for f in (None, 50, 20, 10, 0, 35, 45, 60)] == [0, 1, 3, 4, 5, 2, 1, 1]


def rule_label_maps_one_round_of_rule_play_test():
    """규칙의 한 라운드 -> 계획 번호. 레벨은 올릴 단계 수(0~2, 9를 넘지 않게), 남길 골드는 가장 가까운 칸."""
    from hra.plan_state import rule_label
    from meta.lobby import BOARDS
    assert rule_label(None, BOARDS[3], 3, 4, None) == (4, 1, 0)      # 2-1 첫 덱, 레벨 4 목표, 리롤 없음
    assert rule_label(BOARDS[3], BOARDS[3], 6, 7, 20) == (0, 1, 3)   # 4-1: 그대로, 7로, 20 남기고
    assert rule_label(BOARDS[3], BOARDS[7], 5, 9, 0) == (8, 2, 5)    # 갈아타기, 두 단계로 자름, 다 쓰기
    assert rule_label(BOARDS[3], BOARDS[3], 8, 9, 50) == (0, 1, 1)   # 레벨 8은 한 단계까지만


def _player(units, bench=(), index=0, **attrs):
    """시뮬레이터 플레이어. units는 보드(구석 배치), bench는 벤치, attrs는 골드·체력·레벨 같은 값."""
    from analysis.battle import build_player, to_units
    from Simulator.pool import pool
    p = build_player(pool(), index, to_units(list(units)), 'corner')
    for u in to_units(list(bench)):
        p.add_to_bench(u)
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


def state_counts_what_a_player_can_see_test():
    """2성 야스오(선택받은 결투가, 무한의 대검)·1성 피오라·3성 잭스가 보드에, 1성 칼리스타가 벤치에 있다. 살아 있는 상대
    다섯(체력 80·70·50·90·64, 레벨 6·6·5·7·6, 첫째가 2성 야스오를 든다), 죽은 상대 둘(2성 리 신을 든 쪽은 정찰에서 빠진다).
    목표 덱은 Chosen Duelists(4번), 고른 뒤 2라운드, 3-1(칸 9)."""
    from hra.plan_state import STATE_SIZE, state
    from meta.lobby import BOARDS
    me = _player([{'name': 'yasuo', 'stars': 2, 'items': ['infinity_edge'], 'chosen': 'duelist'},
                  {'name': 'fiora', 'stars': 1, 'items': []}, {'name': 'jax', 'stars': 3, 'items': []}],
                 bench=[{'name': 'kalista', 'stars': 1, 'items': []}],
                 gold=35, health=64, level=5, exp=10, win_streak=0, loss_streak=3)
    others = [_player([{'name': 'yasuo', 'stars': 2, 'items': []}], index=1, health=80, level=6)]
    others += [_player([{'name': 'garen', 'stars': 1, 'items': []}], index=i, health=h, level=lv)
               for i, h, lv in ((2, 70, 6), (3, 50, 5), (4, 90, 7), (5, 64, 6))]
    others += [_player([{'name': 'leesin', 'stars': 2, 'items': []}], index=6, health=0, level=9),
               _player([{'name': 'garen', 'stars': 1, 'items': []}], index=7, health=0, level=9)]
    x = state(me, others, BOARDS[4], 2, 9)
    assert x.shape == (STATE_SIZE,) == (153,) and x.dtype == np.float32
    # 내 상태: 칸/40, 체력/100, 골드/60, 레벨/9, 경험치 10/20, 연승/5, 연패/5, 살아 있는 상대/7
    # 내 보드: 보드 값 3+1+17=21 /120, 2성 1/9, 3성 1/9, 특성 단계(결투가 4 → 2, 추방자 1 → 1) 3/11, 유닛 3/9, 완성 1/10, 조각 0
    assert np.allclose(x[:15], [9 / 40, 0.64, 35 / 60, 5 / 9, 0.5, 0.0, 0.6, 5 / 7,
                                21 / 120, 1 / 9, 1 / 9, 3 / 11, 3 / 9, 0.1, 0.0]), x[:15]
    assert np.allclose(x[15:20], [0.0, 0.0, 0.0, 0.125, 0.0]), x[15:20]       # 0번 Chosen Dusks: 무한의 대검 하나 만들 수 있음
    assert np.allclose(x[35:40], [25 / 40, 0.3, 1.0, 0.0, 1.0]), x[35:40]     # 4번 Chosen Duelists: 몫 25, 남의 야스오 3장
    assert np.allclose(x[150:], [3 / 7, 6 / 9, 0.1]), x[150:]                 # 나보다 체력 많은 3명, 평균 레벨 6, 이력 2


def finish_without_a_decision_does_nothing_test():
    """판단 없이 끝난 자리(2-1 전 탈락)는 경험이 없고, finish를 두 번 불러도 한 번만 닫는다."""
    from hra.plan_bot import Recorder
    r = Recorder()
    r.start_recording()
    r.current_plan = lambda player: None
    me = _player([{'name': 'garen', 'stars': 1, 'items': []}])
    r.finish(me, 8)
    r.finish(me, 8)
    assert r.transitions == [] and r.finished


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
