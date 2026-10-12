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


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
