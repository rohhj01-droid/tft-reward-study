"""
사람 봇(meta/human_bot.py) 검사.

실행: python -m meta.test_human_bot
"""
import random
from types import SimpleNamespace as Unit

from Simulator.item_stats import item_builds
from meta.test_lobby import OPEN, SHARPSHOOTERS, deck_player

FULL = [[1] * 37 for _ in range(60)]  # 상점·아이템을 모두 허락하는 마스크(mask[47 + i][0], mask[37 + 칸][유닛 칸])


def attach_human_takes_over_from_round_one_test():
    """사람 봇은 1라운드부터 정책을 맡는다(덱 봇은 11라운드까지 기본 봇이었다)."""
    from meta.human_bot import attach_human
    p = deck_player(['jhin'])
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(1, ['garen', 'vayne', 'garen', 'garen', 'garen'], OPEN) == '3_1'
    assert policy.choose_decks is False and policy.switches == 0


def human_bot_puts_ranged_carry_in_back_corner_test():
    """자리 맞추기는 구석 배치다(analysis.battle.corner_positions): 원거리는 뒷줄 구석부터 아이템 많은 순, 근접은 앞줄
    가운데부터. 자리가 맞으면 아무것도 하지 않는다."""
    from Simulator.utils import x_y_to_1d_coord
    from meta.human_bot import attach_human
    p = deck_player(['garen', 'jinx'])  # 가렌 (0, 0), 징크스 (1, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) == f'5_{x_y_to_1d_coord(0, 0)}_{x_y_to_1d_coord(3, 3)}'  # 근접은 앞줄 가운데로
    p = deck_player(['jinx'])  # 원거리 하나가 이미 뒷줄 구석 (0, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) is None


def item_player(board_units, item_bench, bench_units=()):
    """보드 x칸 0줄에 유닛을 놓은 가짜 플레이어. x번째 유닛의 칸 번호는 4x다."""
    board = [[None] * 4 for _ in range(7)]
    for x, u in enumerate(board_units):
        board[x][0] = u
    return Unit(board=board, bench=list(bench_units) + [None] * (9 - len(bench_units)),
                item_bench=list(item_bench) + [None] * (10 - len(item_bench)))


GA = item_builds['guardian_angel']
NO_TANK_DECK = {'name': 'x', 'tier': 'B', 'slow': False, 'units': ['jhin', 'vayne'], 'items': {'jhin': ['infinity_edge']}}


def builds_carry_item_on_carrier_test():
    """목표 덱 추천 아이템의 두 조각이 다 있으면 캐리에게 첫 조각을 올린다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[]), Unit(name='garen', stars=1, items=[])], [GA[1], GA[0]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_0_1'


def finishes_started_item_test():
    """조각 하나를 든 유닛이 있고 합칠 조각이 아이템 칸에 있으면 마저 올린다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[GA[0]])], [GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_0_0'


def carry_item_goes_to_holder_when_carrier_absent_test():
    """캐리가 없으면 보드의 덱 밖 유닛 중 별이 가장 높은 유닛(맡아 둘 유닛)에게 만든다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='vayne', stars=1, items=[]), Unit(name='garen', stars=2, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def holds_components_without_holder_test():
    """캐리도 맡아 둘 유닛(덱 밖 유닛)도 없고 조각이 4개 이하면 들고 있는다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='vayne', stars=1, items=[]), Unit(name='teemo', stars=1, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'lose', 12, FULL) is None


def gives_completed_item_to_carrier_test():
    """아이템 칸의 완성 아이템(맡긴 유닛을 팔아 돌아온 것)은 캐리에게 준다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='jhin', stars=2, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def win_mode_slams_defensive_item_on_one_cost_frontliner_test():
    """연승형은 2~3단계에 앞줄 유닛이면 1코스트 2성에게도 방어 아이템을 만든다(유저 제안)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[])], list(item_builds['sunfire_cape']))
    assert item_action(p, NO_TANK_DECK, 'win', 5, FULL) == '6_0_0'


def lose_mode_holds_defensive_components_test():
    """연패형은 방어 아이템을 미리 만들지 않는다(조각 4개 이하)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[])], list(item_builds['sunfire_cape']))
    assert item_action(p, NO_TANK_DECK, 'lose', 5, FULL) is None


def builds_something_with_more_than_four_components_test():
    """조각이 5개 이상이면 연패형이어도 하나를 만든다. 덱 아이템(무한의 대검)도 방어 아이템도 안 되는 조각들이라
    4번 규칙(아무 완성 아이템)을 탄다."""
    from meta.human_items import item_action
    comps = ['bf_sword', 'recurve_bow', 'needlessly_large_rod', 'tear_of_the_goddess', 'giants_belt']
    p = item_player([Unit(name='garen', stars=2, items=[])], comps)
    assert item_action(p, NO_TANK_DECK, 'lose', 12, FULL).startswith('6_0_')


def slams_leftover_components_from_stage_four_test():
    """4단계(4-1)부터는 남는 조각을 들고 있지 않고 짝이 맞으면 바로 완성 아이템으로 만든다(1단계 측정 뒤 유저 결정,
    2026-10-09). 3단계까지는 4개까지 들고 있는다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[])], ['bf_sword', 'needlessly_large_rod'])
    assert item_action(p, NO_TANK_DECK, 'lose', 15, FULL).startswith('6_0_')
    assert item_action(p, NO_TANK_DECK, 'lose', 12, FULL) is None


def leftover_items_go_to_carrier_test():
    """남는 조각으로 만든 아이템(덱 아이템도 방어 아이템도 아닌 것)은 캐리에게 준다(설계 5절 3번 「캐리나 맡아 둘 유닛에게」).
    별이 더 높은 덱 밖 유닛이 있어도 보드의 캐리가 먼저다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='jhin', stars=1, items=[])],
                    ['bf_sword', 'needlessly_large_rod'])
    assert item_action(p, SHARPSHOOTERS, 'lose', 15, FULL).startswith('6_4_')


def does_not_start_item_on_unit_holding_component_test():
    """조각을 든 유닛에는 새로 만들지 않는다. 캐리가 주걱 하나를 들고 있으면 맡아 둘 유닛에게 만든다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=['spatula']), Unit(name='garen', stars=1, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def ignores_consumables_test():
    """아이템 칸이 소모품으로만 차 있으면 아무것도 하지 않는다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[])], ['champion_duplicator'] * 10)
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) is None


def gives_item_to_higher_star_copy_test():
    """캐리가 두 장(1성, 2성) 있으면 별이 높은 쪽에 준다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=1, items=[]), Unit(name='jhin', stars=2, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def never_gives_items_to_summons_test():
    """모래 병사 같은 소환물에는 아이템을 주지 않는다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='sandguard', stars=1, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) is None


def human_policy_places_items_before_leveling_test():
    """살 것도 바꿀 것도 없으면 레벨·리롤보다 아이템을 먼저 한다."""
    import Simulator.champion as cm
    from meta.human_bot import attach_human
    p = deck_player(['jhin'], gold=50)
    p.item_bench[0], p.item_bench[1] = GA[0], GA[1]
    attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(12, ['garen'] * 5, FULL) == f'6_{0}_0'


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
