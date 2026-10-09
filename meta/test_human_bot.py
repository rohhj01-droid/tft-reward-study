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


K = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20}


def plan_follows_design_curves_test():
    """설계 3·4절의 레벨 곡선과 남길 골드. 칸: 2-1 = 3, 2-5 = 6, 3-1 = 9, 3-2 = 10, 4-1 = 15, 4-5 = 18, 5-1 = 21."""
    from meta.human_macro import plan
    cases = [
        ((3, 3, 90, 'win', False, None, False, False), (4, 50)),     # 연승형 2-1에 4, 넘는 몫은 리롤
        ((6, 4, 90, 'win', False, None, False, False), (5, 50)),     # 연승형 2-5에 5
        ((9, 5, 90, 'win', False, None, False, False), (6, 50)),     # 연승형 3-1에 6
        ((6, 4, 90, 'lose', False, None, False, False), (4, None)),  # 연패형은 모으기만
        ((12, 6, 60, 'lose', True, None, False, False), (6, 50)),    # 보드를 세운 다음 라운드부터는 다시 모은다
        ((15, 7, 60, 'win', False, None, False, False), (7, 20)),    # 4-1에 7, 안정이 아니면 그 라운드에 20까지
        ((16, 7, 60, 'win', False, None, False, False), (7, 50)),    # 4-1 다음 라운드는 안정이 아니어도 50을 지킨다
        ((15, 7, 60, 'win', False, None, False, True), (7, 50)),     # 안정이면 50을 지킨다
        ((18, 8, 60, 'win', False, None, False, False), (8, 10)),    # 4-5에 8, 안정이 아니면 그 라운드에 10까지
        ((19, 8, 60, 'win', False, None, False, False), (8, 50)),    # 4-5 다음 라운드도 50을 지킨다
        ((9, 5, 90, 'win', False, 5, False, False), (5, 50)),        # 느린 리롤(1코스트 캐리)은 5에 머문다
        ((15, 6, 60, 'win', False, 7, False, False), (7, None)),     # 3코스트 캐리는 7까지 올리고 그다음 리롤
        ((12, 6, 60, 'win', False, 6, True, False), (8, 50)),        # 캐리가 3성이면 8로
        ((16, 7, 35, 'win', False, None, False, True), (7, 10)),     # 4단계 체력 40 아래면 10까지
        ((16, 7, 15, 'win', False, None, False, True), (7, 0)),      # 20 아래면 다 쓴다
    ]
    for args, expected in cases:
        assert plan(*args, K) == expected, (args, plan(*args, K), expected)
    # 연패형이 보드를 세우는 라운드(3-2 또는 체력 50 아래가 된 라운드)에만 20까지 리롤한다
    assert plan(10, 4, 60, 'lose', True, None, False, False, K, rebuild_now=True) == (6, 20)


def action_spends_in_order_test():
    """목표 레벨까지 경험치 → 5단계 레벨 8에서 안정이면 50 넘는 몫을 경험치(9로) → 남길 골드까지 리롤."""
    from meta.human_macro import action
    assert action(30, 6, 7, 20, False) == '1'
    assert action(60, 8, 8, 50, True) == '1'
    assert action(53, 8, 8, 50, True) == '2'
    assert action(21, 7, 7, 20, False) == '0'
    assert action(80, 9, 8, 50, True) == '2'


def early_mode_and_board_state_test():
    """초반 전략은 2-3에 첫 대전 성적으로 고른다(2연승 이상이면 연승형, 유저 결정 2026-10-09). 안정과 캐리 3성도 본다."""
    from meta.human_macro import carry3, early_mode, stable
    winning, mixed = item_player([], []), item_player([], [])
    winning.win_streak, mixed.win_streak = 2, 1
    assert early_mode(winning, K) == 'win' and early_mode(mixed, K) == 'lose'
    half = item_player([Unit(name='jhin', stars=1, items=[]), Unit(name='riven', stars=2, items=[])], [])
    both = item_player([Unit(name='jhin', stars=2, items=[]), Unit(name='riven', stars=2, items=[])], [])
    assert not stable(half, SHARPSHOOTERS) and stable(both, SHARPSHOOTERS)
    brawlers = {'name': 'b', 'tier': 'A', 'slow': False, 'units': ['ashe', 'sett'],
                'items': {'ashe': ['a', 'b', 'c'], 'sett': ['d', 'e', 'f']}}
    assert stable(item_player([Unit(name='ashe', stars=2, items=[]), Unit(name='sett', stars=1, items=[])], []), brawlers)
    ninja = {'name': 'n', 'tier': 'S', 'slow': True, 'units': ['zed', 'akali'],
             'items': {'zed': ['a', 'b', 'c'], 'akali': ['d', 'e', 'f']}}
    assert carry3(item_player([Unit(name='zed', stars=3, items=[])], []), ninja)
    assert not carry3(item_player([Unit(name='akali', stars=3, items=[])], []), ninja)


def update_mode_switches_and_rebuilds_test():
    """2-3에 전략을 정하고(그 전에는 정하지 않는다), 연승형이 2~3단계에 두 번 연달아 지면 연패형으로, 연패형은 3-2나
    체력 50 아래에서 보드를 세운다. 보드를 세운 라운드를 기억한다(그 라운드에만 리롤)."""
    from meta.human_bot import HumanPolicy
    p = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='vayne', stars=2, items=[])], [])
    p.loss_streak, p.win_streak, p.health = 0, 2, 90
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    policy.update_mode(p, 4)
    assert policy.mode is None
    policy.update_mode(p, 5)
    assert policy.mode == 'win'
    p.loss_streak, p.win_streak = 2, 0
    policy.update_mode(p, 8)
    assert policy.mode == 'lose' and not policy.rebuilt
    policy.update_mode(p, 10)
    assert policy.rebuilt and policy.rebuilt_at == 10


def curve_table_splits_by_deck_style_test():
    """레벨 곡선은 덱 스타일별로도 낸다. 가이드 레벨은 보통 덱으로만 판정한다(유저 결정 2026-10-09).
    연패형 골드는 보드를 세우기 전인 3-2 시작 때도 본다."""
    from meta.play_stats import curve_table
    curve = [(16, 7, 30, 50, 'win', False), (16, 5, 60, 50, 'win', True)]
    assert [r['level'] for r in curve_table([curve], style=False)] == [7]
    assert [r['level'] for r in curve_table([curve], style=True)] == [5]
    assert [r['level'] for r in curve_table([curve])] == [6]
    assert curve_table([[(10, 4, 52, 60, 'lose', False)]], 'lose')[0]['when'] == '3-2 시작'


def transfer_sells_holder_of_carry_item_test():
    """캐리가 보드에 있고 자리가 있는데 덱 밖 유닛(보드나 벤치)이 그 캐리의 추천 아이템을 들고 있으면 그 유닛을 판다(유저
    결정 2026-10-09). 팔면 아이템이 아이템 칸으로 돌아오고 1번 규칙이 캐리에게 준다. 캐리 아이템이 아니거나 아이템 칸에
    자리가 모자라면 팔지 않는다(시뮬레이터는 자리가 모자라면 팔지 못한다)."""
    from meta.human_items import transfer_action
    holder = Unit(name='garen', stars=2, items=['guardian_angel'])
    p = item_player([Unit(name='jhin', stars=2, items=[]), holder], [])
    assert transfer_action(p, SHARPSHOOTERS) == '4_4'
    holder.items = ['warmogs_armor']
    assert transfer_action(p, SHARPSHOOTERS) is None
    holder.items = ['guardian_angel']
    p.item_bench = ['bf_sword'] * 10
    assert transfer_action(p, SHARPSHOOTERS) is None
    bench = item_player([Unit(name='jhin', stars=2, items=[])], [],
                        bench_units=[Unit(name='garen', stars=1, items=['infinity_edge'])])
    assert transfer_action(bench, SHARPSHOOTERS) == '4_28'


def human_policy_moves_carry_item_to_arrived_carrier_test():
    """사람 봇은 아이템 단계 전에 캐리 아이템을 맡은 덱 밖 유닛을 판다."""
    from meta.human_bot import attach_human
    p = deck_player(['garen', 'jhin'], gold=50)
    p.board[0][0].items = ['guardian_angel']
    attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(12, ['garen'] * 5, FULL) == '4_0'


def macro_buys_exp_toward_nine_without_stability_test():
    """5단계 레벨 8이면 안정이 아니어도 50 넘는 몫으로 경험치를 사서 9로 간다(유저 결정 2026-10-09)."""
    from meta.human_bot import HumanPolicy
    p = item_player([Unit(name='garen', stars=2, items=[])], [])
    p.level, p.gold, p.health = 8, 60, 50
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    policy.mode = 'win'
    assert policy.macro(p, 21) == '1'


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
