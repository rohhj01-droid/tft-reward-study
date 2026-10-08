"""
meta.real_boards 검사.

실행: python -m meta.test_real_boards
"""
from multiprocessing import Pool

from Simulator import stats
from analysis.battle import build_player, to_units
from Simulator.pool import pool
from meta.real_boards import load_trends, prehotfix, ranks, spec


def boards_count_traits_like_lolchess_test():
    """선택받은 자와 상징 아이템을 넣은 보드를 시뮬레이터가 세면 롤체지지 조합 이름의 특성 수와 같아야 한다."""
    boards = load_trends()
    assert len(boards) == 27
    for b in boards:
        p = build_player(pool(), 0, to_units(spec(b, 2)), 'range')
        p.update_team_tiers()
        counted = {t: p.team_composition[t] for t in b['traits']}
        assert counted == b['traits'], (b['key'], counted)
        # 아지르의 모래 병사는 빼고 센다
        assert sum(1 for row in p.board for u in row if u and u.name != 'sandguard') == len(b['units']), b['key']


def ranks_average_ties_test():
    assert ranks([3, 1, 3, 2]) == [2.5, 0, 2.5, 1]


def _zed_attack_speed():
    return stats.AS['zed']


def prehotfix_reaches_workers_test():
    """윈도우 일꾼은 모듈을 새로 불러서 부모에서 바꾼 값을 못 본다. initializer로 넘겨야 한다."""
    with Pool(1, initializer=prehotfix) as workers:
        assert workers.apply(_zed_attack_speed) == 0.8
    with Pool(1) as workers:
        assert workers.apply(_zed_attack_speed) == 0.75


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
