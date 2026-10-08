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


def _kayn_form_on_board():
    p = build_player(pool(), 0, to_units([{'name': 'kayn', 'stars': 2}]), 'range')
    return next(u.kayn_form for row in p.board for u in row if u)


def _warlord_wins_after_battle():
    import Simulator.config as config
    from analysis.battle import battle
    battle(to_units([{'name': 'garen', 'stars': 2}]), to_units([{'name': 'vi', 'stars': 2}]), 'range')
    return dict(config.WARLORD_WINS)


def _veigar_lockout_after_cast():
    """베이가(게임 파일 시전 시간 0.5초, 시뮬레이터 스킬에는 시전 뒤 쉬는 시간이 없다)가 스킬을 쓴 직후 행동할 수
    있는지와 행동 금지가 풀리는 때(지금부터 ms)."""
    import Simulator.champion as cm
    from Simulator import field
    field.coordinates = [[None] * 7 for _ in range(8)]
    veigar = cm.champion('veigar', 'blue', 3, 3, stars=2)
    foe = cm.champion('garen', 'red', 4, 3, stars=2)
    cm.blue[:], cm.red[:] = [veigar], [foe]
    cm.que.clear()
    veigar.target = foe
    veigar.cast()
    return veigar.idle, [q[2] - cm.MILLIS() for q in cm.que if q[1] is veigar and q[0] == 'clear_idle']


def _spots():
    """원거리 둘(아이템 1개, 3개)과 근접 하나를 놓았을 때 각 유닛의 (열, 줄). 줄 3이 앞, 0이 뒤다."""
    p = build_player(pool(), 0, to_units([{'name': 'ashe', 'stars': 2, 'items': ['guardian_angel']},
                                          {'name': 'jinx', 'stars': 2,
                                           'items': ['infinity_edge', 'giant_slayer', 'guardian_angel']},
                                          {'name': 'garen', 'stars': 2}]), 'range')
    return {u.name: (x, y) for x, row in enumerate(p.board) for y, u in enumerate(row) if u}


def reroll_spec_triples_only_rerolled_carries_test():
    """리롤 3성 조건은 1~2코스트에 추천 아이템 3개를 든 캐리만 3성으로 만든다: 닌자 보드 12개의 제드, 결투가 보드 6개의 야스오."""
    from meta.isolate import _reroll_spec
    tripled = [(b['key'], u['name']) for b in load_trends() for u in _reroll_spec(b) if u['stars'] == 3]
    assert sorted({name for _, name in tripled}) == ['yasuo', 'zed'], tripled
    assert sum(name == 'zed' for _, name in tripled) == 12 and sum(name == 'yasuo' for _, name in tripled) == 6


def isolate_variants_reach_battles_test():
    """떼어 재기 조건(meta.isolate)이 일꾼의 전투까지 들어가야 한다. 대전은 판마다 승리 수를 0으로 지운다."""
    from functools import partial
    from meta.isolate import setup
    with Pool(1, initializer=partial(setup, 'kayn_rhaast')) as workers:
        assert workers.apply(_kayn_form_on_board) == 'kayn_rhast'
    with Pool(1, initializer=partial(setup, 'warlord5')) as workers:
        assert workers.apply(_warlord_wins_after_battle) == {'blue': 5, 'red': 5}
    with Pool(1, initializer=partial(setup, 'cast_time')) as workers:
        assert workers.apply(_veigar_lockout_after_cast) == (False, [500])
    with Pool(1, initializer=partial(setup, 'corner')) as workers:
        assert workers.apply(_spots) == {'jinx': (0, 0), 'ashe': (6, 0), 'garen': (3, 3)}
    with Pool(1, initializer=prehotfix) as workers:
        assert workers.apply(_kayn_form_on_board) is None
        assert workers.apply(_warlord_wins_after_battle) == {'blue': 0, 'red': 0}
        assert workers.apply(_veigar_lockout_after_cast) == (True, [])
        assert workers.apply(_spots) == {'ashe': (3, 0), 'jinx': (2, 0), 'garen': (3, 3)}


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
