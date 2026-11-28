"""
전투 하네스의 배치(analysis/battle.py effect_positions) 검사.

실행: python -m analysis.test_battle  (PYTHONPATH에 시뮬레이터 저장소와 이 저장소 맨 위)
"""
from types import SimpleNamespace

import Simulator.field as field
from analysis.battle import corner_positions, effect_positions


def unit(name, *items, chosen=False):
    return SimpleNamespace(name=name, items=list(items), chosen=chosen)


def near(a, b):  # 두 칸 (x, y)가 옆 칸인가
    return field.distance({'y': a[1], 'x': a[0]}, {'y': b[1], 'x': b[0]}, False) == 1


def board_without_placement_effects_keeps_corner_placement_test():
    """추방자도, 켜진 수호자도, 같은 줄 아이템도 없으면 구석 배치 그대로다. 수호자 하나는 특성이 안 켜져서 옮기지 않는다."""
    units = [unit('garen'), unit('vayne', 'a', 'b', 'c'), unit('wukong', 'a'), unit('jhin', 'a'), unit('riven')]
    assert effect_positions(units) == corner_positions(units)


def exiles_stand_with_no_ally_beside_them_test():
    """추방자(야스오, 요네)는 앞줄 양 끝에 서고 옆 칸에 같은 편이 없다. 아이템이 가장 많아도 그렇다."""
    units = [unit('yasuo', 'a', 'b', 'c'), unit('garen'), unit('yone'), unit('wukong'), unit('sett'), unit('nidalee'),
             unit('vayne', 'a'), unit('jhin'), unit('jax')]
    spots = effect_positions(units)
    assert spots[0] == (6, 3) and spots[2] == (0, 3)
    for e in (0, 2):
        assert not any(near(spots[e], s) for i, s in enumerate(spots) if i != e)


def keepers_stand_next_to_the_carry_test():
    """수호자가 켜지면(둘 이상) 수호자들이 아이템이 가장 많은 유닛 옆 칸으로 모인다. 구석 칸의 옆 칸은 셋이라 넷째는 한 칸 더
    떨어져 선다. 원거리 수호자는 같은 줄 옆, 근접 수호자는 앞쪽 칸이다."""
    units = [unit('riven'), unit('vayne', 'a', 'b', 'c'), unit('jarvaniv'), unit('garen'), unit('azir', 'a'), unit('kennen'), unit('jhin')]
    spots = effect_positions(units)
    assert spots[1] == (0, 0)
    assert sum(near(spots[k], spots[1]) for k in (0, 2, 4, 5)) == 3
    assert spots[4] == (1, 0) and {spots[0], spots[2]} == {(0, 1), (1, 1)}  # 아이템이 있는 아지르가 같은 줄 옆, 근접 둘이 앞
    assert all(field.distance({'y': spots[k][1], 'x': spots[k][0]}, {'y': 0, 'x': 0}, False) <= 2 for k in (0, 2, 4, 5))
    assert spots[3] == (3, 3) and spots[6] == (6, 0)  # 나머지는 구석 배치 순서대로


def chosen_keeper_alone_counts_as_two_test():
    """수호자로 선택받은 유닛은 혼자서도 특성을 켠다. 그러면 캐리 옆으로 간다."""
    units = [unit('vayne', 'a', 'b'), unit('riven', chosen='keeper'), unit('garen')]
    spots = effect_positions(units)
    assert near(spots[1], spots[0]) and spots[2] == (3, 3)


def row_item_holder_stands_beside_the_top_unit_of_its_row_test():
    """지크의 전령·힘의 성배·솔라리의 펜던트를 든 유닛은 제 줄(근접은 앞줄, 원거리는 뒷줄)에서 아이템이 가장 많은 유닛
    바로 옆에 서고, 그 줄의 나머지는 가까운 칸부터 붙어 선다."""
    units = [unit('vayne', 'a', 'b', 'c'), unit('jhin', 'zekes_herald'), unit('ashe', 'a'), unit('garen', 'locket_of_the_iron_solari'),
             unit('wukong', 'a', 'b'), unit('sett')]
    spots = effect_positions(units)
    assert spots[:3] == [(0, 0), (1, 0), (2, 0)]  # 베인, 지크 든 진, 그 옆에 애쉬
    assert spots[4] == (3, 3) and spots[3] == (2, 3) and spots[5] == (4, 3)  # 오공, 솔라리 든 가렌, 반대쪽 옆에 세트


def holders_do_not_stand_beside_each_other_when_there_is_room_test():
    """같은 줄 아이템을 든 유닛이 둘이면 서로 붙지 않게 한 칸 띄워 세워서, 사이에 선 유닛이 둘 다 받게 한다. 든 유닛이
    그 줄에서 아이템이 가장 많으면 그 유닛이 기준 자리에 선다."""
    units = [unit('vayne', 'a', 'b', 'c'), unit('jhin', 'zekes_herald'), unit('ashe', 'chalice_of_power'), unit('ahri', 'a', 'b')]
    assert effect_positions(units) == [(0, 0), (1, 0), (3, 0), (2, 0)]
    units = [unit('vayne', 'zekes_herald', 'b', 'c'), unit('jhin'), unit('ashe', 'a')]
    assert effect_positions(units) == [(0, 0), (2, 0), (1, 0)]


def every_unit_gets_its_own_spot_on_the_board_test():
    units = [unit('yasuo', 'a'), unit('yone', 'zekes_herald'), unit('riven', 'locket_of_the_iron_solari'), unit('jarvaniv'),
             unit('azir', 'a', 'b', 'c'), unit('kennen', 'chalice_of_power'), unit('elise'), unit('vayne', 'a', 'b'), unit('jhin'),
             unit('garen')]
    spots = effect_positions(units)
    assert len(set(spots)) == len(units) and all(0 <= x <= 6 and 0 <= y <= 3 for x, y in spots)
    for e in (0, 1):  # 추방자는 아이템이 있어도 혼자 선다
        assert not any(near(spots[e], s) for i, s in enumerate(spots) if i != e)


def sand_guards_do_not_break_exile_test():
    """아지르를 보드에 놓으면 시뮬레이터가 옆 빈칸(없으면 앞줄 오른쪽 끝 둘레)에 모래 병사 둘을 세운다. 효과 배치로 보드를
    만들 때는 추방자 옆에 선 병사를 비켜 세워서 추방자가 혼자 서게 한다. 병사 둘은 그대로 남는다."""
    from Simulator.pool import pool
    from analysis.battle import build_player, to_units
    spec = [{'name': 'yone', 'stars': 1}, {'name': 'azir', 'stars': 2, 'items': ['deathblade', 'infinity_edge', 'giant_slayer']},
            {'name': 'riven', 'stars': 2}, {'name': 'kennen', 'stars': 2}, {'name': 'garen', 'stars': 2}]
    p = build_player(pool(), 0, to_units(spec), 'effect')
    on = {(x, y): p.board[x][y].name for x in range(7) for y in range(4) if p.board[x][y]}
    assert on[(6, 3)] == 'yone' and on[(0, 0)] == 'azir' and list(on.values()).count('sandguard') == 2
    assert not any(near((6, 3), c) for c in on if c != (6, 3)), on


def zephyr_holder_stands_on_the_cell_of_the_enemy_carry_test():
    """서풍 든 유닛은 상대 보드에서 아이템이 가장 많은 유닛(수은 든 유닛은 빼고)이 자기 보드에서 선 칸과 같은 내 칸에 선다.
    그 칸에 내 유닛이 있으면 자리를 맞바꾸고, 나머지는 효과 배치 그대로다. 서풍이 없으면 효과 배치 그대로다."""
    from analysis.battle import aim_positions
    own = [unit('garen'), unit('vayne', 'a', 'b', 'c'), unit('shen', 'zephyr'), unit('jhin', 'a')]
    enemy = [unit('riven'), unit('jinx', 'a', 'b', 'c'), unit('kennen', 'a')]
    base, where = effect_positions(own), effect_positions(enemy)
    spots = aim_positions(own, enemy)
    assert spots[2] == where[1] != base[2]
    swapped = [i for i in range(4) if i != 2 and spots[i] != base[i]]
    assert swapped == [] or (len(swapped) == 1 and base[swapped[0]] == where[1] and spots[swapped[0]] == base[2])
    assert aim_positions(own, [unit('riven'), unit('jinx', 'quicksilver', 'b', 'c'), unit('kennen', 'a')])[2] == where[2]
    no_zephyr = [unit('garen'), unit('vayne', 'a', 'b', 'c')]
    assert aim_positions(no_zephyr, enemy) == effect_positions(no_zephyr)


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
