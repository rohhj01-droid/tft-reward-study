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


def reposition_does_not_swap_equal_units_test():
    """이름·별·아이템 수가 같은 유닛끼리는 자리를 맞바꾸지 않고, 이름·별이 같으면 아이템이 많은 쪽이 앞 순서다. 예전에는
    둘의 순서가 보드 칸 순서로 정해져서, 맞바꾸면 순서가 뒤집혀 같은 맞바꾸기를 라운드마다 8번까지 되풀이했다(최종 검토:
    3판 628 플레이어-라운드에 211번). 근접 첫 자리는 (3, 3), 둘째는 (2, 3)이고 칸은 (2, 3)부터 센다."""
    from meta.human_bot import HumanPolicy
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    p = item_player([], [])
    p.board[3][3], p.board[2][3] = plain(['garen', 'garen'])
    assert policy.reposition(p, 12) is None
    p.board[3][3].items = ['bf_sword']  # 아이템이 많은 가렌이 첫 자리에 있다
    assert policy.reposition(p, 13) is None


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
    """사람 봇은 아이템 단계 전에 캐리 아이템을 맡은 덱 밖 유닛을 판다. 상점은 덱에도 보드에도 없는 유닛(바이)이라
    사기·짝 사기가 끼지 않는다."""
    from meta.human_bot import attach_human
    p = deck_player(['garen', 'jhin'], gold=50)
    p.board[0][0].items = ['guardian_angel']
    attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(12, ['vi'] * 5, FULL) == '4_0'


def macro_buys_exp_toward_nine_without_stability_test():
    """5단계 레벨 8이면 안정이 아니어도 50 넘는 몫으로 경험치를 사서 9로 간다(유저 결정 2026-10-09)."""
    from meta.human_bot import HumanPolicy
    p = item_player([Unit(name='garen', stars=2, items=[])], [])
    p.level, p.gold, p.health = 8, 60, 50
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    policy.mode = 'win'
    assert policy.macro(p, 21) == '1'


def macro_knobs_for_gold_after_stage_five_test():
    """떼어 재기 손잡이. xp_to_9=0이면 5단계 레벨 8에서 경험치 대신 50 넘는 몫으로 리롤한다(기본 봇처럼). floor_9를 주면
    레벨 9에서 그만큼만 남기고 리롤한다. 둘 다 안 주면 지금 규칙 그대로다(경험치로 9, 9에서는 50을 지킨다)."""
    from meta.human_bot import HumanPolicy

    def act(level, gold, **knobs):
        p = item_player([Unit(name='garen', stars=2, items=[])], [])
        p.level, p.gold, p.health = level, gold, 50
        policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0), knobs)
        policy.mode = 'win'
        return policy.macro(p, 21)

    assert [act(8, 60), act(8, 60, xp_to_9=0)] == ['1', '2']
    assert [act(9, 30), act(9, 30, floor_9=20)] == ['0', '2']


def plain(names):
    """1성, 아이템 없음, 선택받은 자 아닌 유닛 목록."""
    return [Unit(name=n, stars=1, items=[], chosen=False) for n in names]


SHOOTERS4 = ['nidalee', 'vayne', 'teemo', 'jinx']  # SHARPSHOOTERS 덱의 계열(명사수 4)을 채운다


def buys_five_cost_from_level_eight_after_deck_units_test():
    """계열을 채운 보드면 레벨 8부터 상점의 5코스트를 산다. 덱 유닛이 먼저고, 레벨 7이나 골드 5 미만이면 안 산다(설계 9절)."""
    from meta.human_bot import HumanPolicy
    p = item_player(plain(SHOOTERS4), [])
    p.chosen, p.gold, p.level = False, 30, 8
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    # 채움 칸은 바이(덱 밖, 보드에도 없음)라 짝 사기 규칙에 안 걸린다
    assert policy.buy(p, ['yone', 'jhin', 'vi', 'vi', 'vi'], OPEN) == '3_1'  # 덱 유닛(진)이 먼저
    assert policy.buy(p, ['vi', 'yone', 'vi', 'vi', 'vi'], OPEN) == '3_1'
    p.level = 7
    assert policy.buy(p, ['vi', 'yone', 'vi', 'vi', 'vi'], OPEN) is None
    p.level, p.gold = 8, 4
    assert policy.buy(p, ['vi', 'yone', 'vi', 'vi', 'vi'], OPEN) is None


def five_cost_prefers_active_trait_and_stops_at_two_star_test():
    """5코스트가 여럿이면 보드에 켜진 특성에 보태는 쪽을 먼저 사고, 같은 이름은 1성으로 쳐서 3장(2성)까지만 산다.
    선택받은 자 칸은 덱 규칙에 맡긴다(설계 9절)."""
    from meta.human_bot import HumanPolicy
    dusk = plain(['riven'] + SHOOTERS4)  # 황혼 2명(리븐·베인) → 황혼이 켜진다. 명사수 4명으로 계열을 채웠다
    p = item_player(dusk, [])
    p.chosen, p.gold, p.level = False, 30, 8
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    assert policy.buy(p, ['sett', 'lillia', 'vi', 'vi', 'vi'], OPEN) == '3_1'  # 릴리아(황혼)
    assert policy.buy(p, ['sett', 'kayn', 'vi', 'vi', 'vi'], OPEN) == '3_0'  # 둘 다 안 보태면 앞 칸
    p = item_player(dusk, [], [Unit(name='yone', stars=2, items=[], chosen=False)])  # 요네 2성 = 3장
    p.chosen, p.gold, p.level = False, 30, 8
    assert policy.buy(p, ['yone', 'vi', 'vi', 'vi', 'vi'], OPEN) is None
    assert policy.buy(p, ['yone_adept_c', 'vi', 'vi', 'vi', 'vi'], OPEN) is None


FIVE_BOARD = ['nidalee', 'vayne', 'jarvaniv', 'teemo', 'kennen', 'jinx', 'jhin', 'riven']  # 명사수 5(큰 특성), 수호자 3, 황혼 2


def full_board(names, bench_names=('yone',), chosen=()):
    """보드가 꽉 찬 레벨 8 플레이어. 앞 7명은 0줄 x칸(칸 번호 4x)이고 8번째부터는 1줄에 놓는다. 벤치 칸은 28부터.
    chosen에 든 유닛은 자기 첫 특성의 선택받은 자다."""
    from meta.decks_1024 import CHAMPION_TRAITS
    units = [Unit(name=n, stars=1, items=[], chosen=(n in chosen and CHAMPION_TRAITS[n][0])) for n in names]
    p = item_player(units[:7], [], [Unit(name=n, stars=1, items=[], chosen=False) for n in bench_names])
    for x, u in enumerate(units[7:]):
        p.board[x][1] = u
    p.chosen, p.gold, p.level = False, 30, 8
    p.num_units_in_play, p.max_units = len(names), len(names)
    return p


def swaps_cheap_side_unit_for_bench_five_cost_test():
    """빈자리가 없으면 벤치의 5코스트를 보드의 덱 유닛과 바꾼다. 캐리(진·리븐)와 선택받은 자는 두고, 큰 특성(명사수 5)에
    안 드는 곁가지 유닛 중 가장 싼 자르반(2코스트)을 내린다. 내린 유닛은 그 덱에서 덱 밖으로 친다(설계 9절)."""
    from meta.human_bot import HumanPolicy
    p = full_board(FIVE_BOARD)
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    assert policy.swap(p) == f'5_{4 * 2}_28'
    assert policy.dropped == {'jarvaniv'} and 'jarvaniv' not in policy.units
    p = full_board(FIVE_BOARD, chosen=('jarvaniv',))  # 자르반이 선택받은 자면 다음 곁가지(케넨, 3코스트)
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))  # 자르반을 이미 덱 밖으로 친 정책은 쓰지 않는다
    assert policy.swap(p) == f'5_{4 * 4}_28'
    p.level = 7
    assert policy.swap(p) is None


def keeps_big_trait_at_four_and_carriers_test():
    """큰 특성(4명 이상)이 4명 아래로 떨어지는 바꾸기는 하지 않는다. 캐리만 남으면 바꾸지 않는다(설계 9절)."""
    from meta.human_bot import HumanPolicy
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    assert policy.swap(full_board(['nidalee', 'vayne', 'teemo', 'jinx'])) is None  # 명사수 딱 4명
    assert policy.swap(full_board(['nidalee', 'vayne', 'teemo', 'jinx', 'jhin'])) == f'5_{4 * 0}_28'  # 5명이면 1코스트 니달리
    assert policy.swap(full_board(['jhin', 'riven'])) is None


def keeps_family_trait_at_family_threshold_test():
    """계열 특성은 계열 기준 인원까지 지킨다(유저 결정 2026-10-09: 3b단계 첫 측정에서 1등 보드 52%가 계열을 잃었다).
    총사령관은 6명부터 계열이라(meta/play_stats.py의 FAMILIES) 6명이면 하나도 못 내리고, 7명이면 하나는 내린다."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    warlords = next(b for b in BOARDS if b['name'] == 'Chosen Warlords')  # 캐리는 카타리나
    six = ['garen', 'nidalee', 'jarvaniv', 'vi', 'katarina', 'xinzhao']
    assert HumanPolicy(None, warlords, [], random.Random(0)).swap(full_board(six)) is None
    assert HumanPolicy(None, warlords, [], random.Random(0)).swap(full_board(six + ['azir'])) == f'5_{4 * 0}_28'


def does_not_swap_deck_units_before_deck_family_is_complete_test():
    """목표 덱의 계열이 기준 인원에 못 미치면 덱 유닛을 5코스트로 바꾸지 않는다(유저 결정 2026-10-09: 계열을 못 갖춘 채
    5코스트가 자리를 차지해 마지막 계열 유닛이 못 들어왔다). 계열을 채우면 곁가지 유닛부터 바꾼다."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    warlords = next(b for b in BOARDS if b['name'] == 'Chosen Warlords')
    five = ['garen', 'nidalee', 'jarvaniv', 'vi', 'katarina', 'pyke']  # 총사령관 5명 + 파이크(곁가지)
    assert HumanPolicy(None, warlords, [], random.Random(0)).swap(full_board(five)) is None
    six = ['garen', 'nidalee', 'jarvaniv', 'vi', 'katarina', 'xinzhao', 'pyke']  # 총사령관 6명이면 파이크부터
    assert HumanPolicy(None, warlords, [], random.Random(0)).swap(full_board(six)) == f'5_{4 * 6}_28'


def swap_counts_emblems_and_chosen_and_skips_summons_test():
    """특성 수에 상징 아이템과 선택받은 자 특성을 넣고, 소환물은 후보에서 뺀다(Review Focus). 황혼 덱의 계열(황혼 4)은
    베인·쓰레쉬(유닛 2) + 진의 황혼 망토(1) + 보드에 있는 선택받은 자 쓰레쉬의 특성(1)으로만 채워진다. 둘 중 하나라도 안
    세면 계열을 못 채운 것으로 보고 아무것도 안 바꾼다. 채웠으면 황혼 유닛과 망토를 든 진은 두고 곁가지 아트록스를 내린다."""
    from Simulator.item_stats import trait_items
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')  # 캐리는 리븐
    p = full_board(['vayne', 'thresh', 'aatrox', 'jhin'])
    p.board[3][0].items = [trait_items['dusk']]
    p.chosen = p.board[1][0].chosen = 'dusk'  # 쓰레쉬가 선택받은 자(황혼)
    assert HumanPolicy(None, dusks, [], random.Random(0)).swap(p) == f'5_{4 * 2}_28'
    p = full_board(['nidalee', 'vayne', 'teemo', 'jinx', 'jhin'])
    p.board[5][0] = Unit(name='sandguard', stars=1, items=[], chosen=False)  # 소환물
    p.num_units_in_play = p.max_units = 6
    assert HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0)).swap(p) == f'5_{4 * 0}_28'  # 모래 병사는 후보도 특성 수도 아니다


def sells_dropped_unit_right_away_and_forgets_on_switch_test():
    """5코스트와 바꿔 내린 유닛은 벤치가 안 찼어도 바로 팔고, 덱을 갈아타면 목록을 비운다(설계 9절, Review Focus)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    p = item_player([], [], [Unit(name='garen', stars=1, items=[], chosen=False),
                             Unit(name='jarvaniv', stars=2, items=[], chosen=False)])
    p.chosen, p.gold, p.level = False, 30, 8
    policy = HumanPolicy(None, None, [], random.Random(0))
    policy.set_board(SHARPSHOOTERS)
    policy.dropped.add('jarvaniv')
    policy.units.discard('jarvaniv')
    assert policy.sell(p) == '4_29'
    policy.set_board(next(b for b in BOARDS if b['name'] == 'Chosen Dusks'))
    assert policy.dropped == set()


def five_cost_replaces_off_deck_unit_and_is_kept_on_full_bench_test():
    """계열을 채운 보드면 레벨 8부터 벤치의 5코스트는 보드의 덱 밖 유닛 자리에 올라가고, 벤치가 꽉 차도 팔지 않는다.
    레벨 7은 둘 다 아니다(설계 9절, Review Focus). 덱 봇은 그대로 5코스트를 덱 밖으로 본다."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import DeckPolicy
    p = full_board(['garen'] + SHOOTERS4)
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    assert policy.swap(p) == f'5_{4 * 0}_28'
    assert DeckPolicy(None, SHARPSHOOTERS).swap(p) is None
    bench = [Unit(name=n, stars=1, items=[], chosen=False) for n in ['yone'] + ['garen'] * 8]
    p = item_player(plain(SHOOTERS4), [], bench)
    p.chosen, p.gold, p.level = False, 30, 8
    p.bench_full = lambda: True
    assert policy.sell(p) == '4_29'
    p.level = 7
    assert policy.sell(p) == '4_28'


WARLORDS5 = ['garen', 'nidalee', 'jarvaniv', 'vi', 'katarina']  # Chosen Warlords의 계열(총사령관 6)에 하나 모자람


def buys_missing_family_unit_first_test():
    """목표 덱의 계열이 기준 인원에 모자라면 아직 없는 계열 유닛을 다른 덱 유닛보다 먼저 산다. 채웠으면 상점 순서대로다
    (유저 결정 2026-10-09: 계열 없는 1등 보드 절반이 결투가·총사령관 5명에서 멈췄다)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    warlords = next(b for b in BOARDS if b['name'] == 'Chosen Warlords')
    p = item_player(plain(WARLORDS5), [])
    p.chosen, p.gold, p.level = False, 30, 7
    policy = HumanPolicy(None, warlords, [], random.Random(0))
    shop = ['pyke', 'vi', 'xinzhao', 'lulu', 'lulu']
    assert policy.buy(p, shop, OPEN) == '3_2'  # 파이크(덱 유닛, 계열 아님)·바이(이미 있음)보다 신짜오
    p.board[5][0] = plain(['xinzhao'])[0]  # 총사령관 6명
    assert policy.buy(p, shop, OPEN) == '3_0'


def no_off_deck_five_cost_before_family_is_complete_test():
    """계열을 채우기 전에는 덱 밖 5코스트를 사지 않고 원하는 유닛으로도 치지 않는다: 벤치가 차면 먼저 팔고, 보드에 있으면
    덱 유닛과 바꾼다. 채우면 레벨 8 규칙 그대로다(유저 결정 2026-10-09)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    warlords = next(b for b in BOARDS if b['name'] == 'Chosen Warlords')
    policy = HumanPolicy(None, warlords, [], random.Random(0))
    p = item_player(plain(WARLORDS5), [], plain(['yone'] + ['lulu'] * 8))
    p.chosen, p.gold, p.level = False, 30, 8
    p.bench_full = lambda: True
    shop = ['yone', 'lulu', 'lulu', 'lulu', 'lulu']
    assert policy.buy(p, shop, OPEN) is None
    assert policy.sell(p) == '4_28'  # 요네부터 판다
    p.board[5][0] = plain(['xinzhao'])[0]  # 총사령관 6명
    assert policy.buy(p, shop, OPEN) == '3_0'
    assert policy.sell(p) == '4_29'
    p = full_board(WARLORDS5 + ['yone'], bench_names=('pyke',))
    assert policy.swap(p) == f'5_{4 * 5}_28'  # 보드의 요네를 덱 유닛 파이크와 바꾼다


def puts_family_unit_on_board_before_other_units_test():
    """계열이 모자라면 벤치의 계열 유닛(목표 덱 유닛)을 보드의 계열 아닌 유닛과 바꾼다. 덱 밖 유닛 먼저, 그다음 싼 것이고,
    같은 이름 사본도 후보다. 캐리와 선택받은 자는 두고, 계열을 채웠으면 하지 않는다(유저 결정 2026-10-09)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    deck = {b['name']: b for b in BOARDS}

    def swap(name, names, bench, level=8, chosen=()):
        p = full_board(names, bench_names=(bench,), chosen=chosen)
        p.level = level
        return HumanPolicy(None, deck[name], [], random.Random(0)).swap(p)

    duel = ['fiora', 'yasuo', 'jax', 'kalista', 'janna', 'shen']  # 결투가 4명(계열 6명), 캐리는 야스오
    assert swap('Chosen Duelists', duel + ['yone'], 'leesin', level=7) == f'5_{4 * 4}_28'  # 잔나(2코스트)
    assert swap('Chosen Duelists', duel + ['sett'], 'leesin', level=7) == f'5_{4 * 6}_28'  # 덱 밖 세트 먼저
    nidalee2 = ['garen', 'nidalee', 'nidalee', 'jarvaniv', 'vi', 'katarina', 'pyke']  # 총사령관 5명
    assert swap('Chosen Warlords', nidalee2, 'xinzhao', level=7) == f'5_{4 * 1}_28'  # 니달리 사본(1코스트)
    cult = ['elise', 'pyke', 'kalista', 'aatrox', 'jhin']  # 사교도 5명(계열 6명), 캐리는 리븐
    assert swap('Dusk Cultists', cult + ['riven'], 'zilean') is None  # 남은 후보가 캐리뿐
    assert swap('Dusk Cultists', cult + ['cassiopeia'], 'zilean', chosen=('cassiopeia',)) is None  # 선택받은 자
    assert swap('Chosen Warlords', WARLORDS5 + ['xinzhao', 'pyke'], 'azir', level=7) is None  # 총사령관 6명이면 안 한다


def bench_chosen_does_not_count_for_family_test():
    """선택받은 자 특성 +1은 보드에 있을 때만 센다(june fe92c2b, 시뮬레이터와 같게). 벤치의 선택받은 자 리븐(황혼)은 황혼
    계열을 못 채우므로 5코스트를 넣지 않고, 계열 유닛인 리븐을 먼저 올린다(곁가지 아트록스 자리)."""
    from Simulator.item_stats import trait_items
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')
    p = full_board(['vayne', 'thresh', 'aatrox', 'jhin'], bench_names=('yone', 'riven'))
    p.board[3][0].items = [trait_items['dusk']]
    p.chosen = p.bench[1].chosen = 'dusk'
    assert HumanPolicy(None, dusks, [], random.Random(0)).swap(p) == f'5_{4 * 2}_29'


def swapping_one_of_two_copies_keeps_the_unit_in_deck_test():
    """5코스트와 바꿔 내린 유닛의 사본이 보드에 남으면 그 이름을 덱 밖으로 치지 않는다. 치면 남은 사본이 지키는 인원 검사
    없이 일반 교체로 내려가 계열이 깨졌다(3b단계 진단 2026-10-09: 총사령관·명사수·사교도 1등 보드가 바꾸기 뒤 계열을 잃음)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    warlords = next(b for b in BOARDS if b['name'] == 'Chosen Warlords')
    p = full_board(['garen', 'garen', 'nidalee', 'jarvaniv', 'vi', 'katarina', 'xinzhao', 'azir'])  # 총사령관 7명
    policy = HumanPolicy(None, warlords, [], random.Random(0))
    assert policy.swap(p) == f'5_{4 * 0}_28'
    assert policy.dropped == set() and 'garen' in policy.units


def sells_other_units_before_wanted_five_cost_test():
    """벤치가 원하는 유닛으로 꽉 차서 기본 봇 규칙이 5코스트를 고르면 5코스트가 아닌 유닛을 대신 판다(1성 먼저, 없으면 가장
    싼 것). 벤치가 5코스트뿐이면 기본 봇 규칙 그대로다(유저 결정 2026-10-10: 1등 봇이 판마다 산 5코스트 6장 중 1.8장을
    기본 봇 규칙이 팔았다)."""
    from meta.human_bot import HumanPolicy
    agent = Unit(sell_bench_full=lambda p: '4_28')  # 기본 봇은 벤치 앞의 짝 없는 1성(요네)을 고른다
    policy = HumanPolicy(agent, SHARPSHOOTERS, [], random.Random(0))

    def sell(names, two_star=()):
        bench = plain(names)
        for u in bench:
            u.stars = 2 if u.name in two_star else 1
        p = item_player(plain(SHOOTERS4), [], bench)  # 명사수 4명으로 계열을 채웠다
        p.chosen, p.gold, p.level = False, 30, 8
        p.bench_full = lambda: True
        return policy.sell(p)

    deck = ['jhin', 'vayne', 'teemo', 'jinx', 'nidalee', 'kennen', 'riven']  # 모두 덱 유닛
    assert sell(['yone'] + deck + ['azir'], two_star=('jhin',)) == '4_30'  # 첫 1성 베인
    assert sell(['yone', 'jhin', 'kennen', 'nidalee', 'riven', 'jinx', 'azir', 'sett', 'lillia'],
                two_star=('jhin', 'kennen', 'nidalee', 'riven', 'jinx')) == '4_31'  # 다 2성이면 가장 싼 니달리
    assert sell(['yone', 'azir', 'sett', 'lillia', 'kayn', 'ezreal', 'zilean', 'leesin', 'sett']) == '4_28'


def placement_table_counts_ranks_by_family_test():
    """계열별 1~8등 비율(설계 7절 4단계). 실제 쪽은 메타 트렌드 조합의 비율을 고른 비율로 가중 평균한다. 롤체지지 비율은
    소수 셋째 자리로 반올림돼 합이 1에서 0.005 안쪽으로 어긋난다."""
    from meta.play_stats import placement_table, real_placements
    players = [{'place': 1, 'board': {'traits': {'dusk': 4}}}, {'place': 8, 'board': {'traits': {'dusk': 6}}},
               {'place': 3, 'board': {'traits': {}}}]
    table = placement_table(players)
    assert table['dusk'] == [0.5, 0, 0, 0, 0, 0, 0, 0.5] and table['other'][2] == 1.0
    real = real_placements()
    assert abs(sum(real['ninja']) - 1) < 0.005 and real['ninja'][0] > real['ninja'][7]


def board_summary_counts_five_costs_per_board_test():
    """1등 보드 표의 「보드당 5코스트 장수」(설계 7절 3b단계)."""
    from meta.play_stats import board_summary
    boards = [{'units': [['yone', 5, 2, 0], ['sett', 5, 1, 0], ['garen', 1, 2, 0]], 'traits': {}, 'chosen': None},
              {'units': [['garen', 1, 2, 0]], 'traits': {}, 'chosen': None}]
    assert board_summary(boards)['five_per_board'] == 1.0


D = dict(K, chosen_bonus=10, item_point=3, tier_weight=3, contest=1, temperature=3,
         switch={2: 0.1, 3: 0.3, 4: 0.6}, early_spread=6)


def score_follows_owned_units_and_chosen_test():
    """황혼 선택받은 자와 황혼 유닛을 들면 Chosen Dusks 점수가 Chosen Hunters보다 높다."""
    from collections import Counter
    from meta.human_deck import score
    from meta.lobby import BOARDS
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')
    hunters = next(b for b in BOARDS if b['name'] == 'Chosen Hunters')
    mine = Counter({'riven': 3, 'cassiopeia': 1, 'thresh': 3})
    assert score(dusks, mine, 'dusk', [], [], Counter(), D) > score(hunters, mine, 'dusk', [], [], Counter(), D)


def buildable_counts_completed_and_components_test():
    """들고 있는 완성 아이템과 조각으로 추천 아이템을 몇 개 만들 수 있는지 센다."""
    from meta.human_deck import buildable
    assert buildable(SHARPSHOOTERS, ['infinity_edge'], list(GA)) == 2
    assert buildable(SHARPSHOOTERS, [], [GA[0]]) == 0


def contest_lowers_score_test():
    """다른 플레이어가 핵심 유닛(캐리와 4·5코스트)을 들고 있으면 그 장수만큼 점수가 내려간다."""
    from collections import Counter
    from meta.human_deck import score
    from meta.lobby import BOARDS
    sharp = next(b for b in BOARDS if b['name'] == 'Chosen Sharpshooters')
    base = score(sharp, Counter(), None, [], [], Counter(), D)
    assert score(sharp, Counter(), None, [], [], Counter({'jhin': 9}), D) == base - 9


def choose_is_seeded_and_sticky_test():
    """처음엔 시드를 고정한 제비뽑기, 그다음엔 문턱을 넘어야 갈아탄다(2단계 10%, 4단계부터 60%)."""
    from meta.human_deck import choose
    scores = [1.0, 5.0, 3.0]
    assert choose(scores, None, 2, random.Random(7), D) == choose(scores, None, 2, random.Random(7), D)
    assert choose(scores, None, 2, random.Random(7), dict(D, temperature=0.01)) == 1
    assert choose([10.0, 15.0], 0, 4, random.Random(0), D) == 0
    assert choose([10.0, 17.0], 0, 4, random.Random(0), D) == 1
    assert choose([10.0, 12.0], 0, 2, random.Random(0), D) == 1


def choose_handles_non_positive_scores_and_late_stages_test():
    """점수가 모두 0 이하여도, 6단계여도 하나를 고른다(Review Focus)."""
    from meta.human_deck import choose
    assert choose([-5.0, -1.0, 0.0], None, 2, random.Random(0), D) in (0, 1, 2)
    assert choose([-5.0, 3.0], 0, 6, random.Random(0), D) == 1


def scout_ignores_eliminated_players_test():
    """탈락한 플레이어의 유닛은 정찰에서 세지 않는다(Review Focus)."""
    from meta.human_deck import scout
    alive = item_player([Unit(name='jhin', stars=2, items=[])], [])
    alive.health = 30
    dead = item_player([Unit(name='riven', stars=2, items=[])], [])
    dead.health = 0
    assert scout([alive, dead]) == {'jhin': 3}


def sells_chosen_of_other_trait_after_switch_test():
    """덱을 갈아타서 들고 있는 선택받은 자 특성이 목표 덱과 다르면 그 선택받은 자를 판다(벤치 칸은 28부터)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    hunters = next(b for b in BOARDS if b['name'] == 'Chosen Hunters')
    bench = [Unit(name='vayne', stars=1, items=[], chosen=False), Unit(name='garen', stars=1, items=[], chosen=False),
             Unit(name='riven', stars=2, items=[], chosen='dusk')]
    p = item_player([], [], bench)
    p.chosen = 'dusk'
    policy = HumanPolicy(None, None, [], random.Random(0))
    policy.set_board(hunters)
    assert policy.sell_chosen(p) == '4_30'


def buys_chosen_of_deck_unit_with_other_trait_test():
    """목표 덱에 들어가는 유닛이면 특성이 덱 특성과 달라도 선택받은 자를 산다(실제 1등의 52%가 그랬다, 유저 결정
    2026-10-09). 덱 봇은 그대로 덱 특성의 선택받은 자만 산다."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS, DeckPolicy
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')
    p = item_player([], [])
    p.gold, p.chosen = 30, False
    shop = ['vi', 'riven_keeper_c', 'vi', 'vi', 'vi']
    assert HumanPolicy(None, dusks, [], random.Random(0)).buy(p, shop, OPEN) == '3_1'
    assert DeckPolicy(None, dusks).buy(p, shop, OPEN) is None


def keeps_chosen_unit_of_new_deck_test():
    """덱을 바꿔도 들고 있는 선택받은 자 유닛이 새 덱에 있으면 특성이 달라도 팔지 않는다(유저 결정 2026-10-09)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')
    p = item_player([], [], [Unit(name='riven', stars=2, items=[], chosen='keeper')])
    p.chosen = 'keeper'
    policy = HumanPolicy(None, None, [], random.Random(0))
    policy.set_board(dusks)
    assert policy.sell_chosen(p) is None


def buys_pairs_and_widely_used_units_before_choosing_test():
    """목표 덱을 정하기 전에는 짝과 여러 후보 덱에 두루 들어가는 유닛을 산다."""
    from meta.human_bot import HumanPolicy
    from meta.human_deck import SPREAD
    p = item_player([Unit(name='jhin', stars=1, items=[], chosen=False)], [])
    p.gold, p.chosen = 10, False
    policy = HumanPolicy(None, None, [], random.Random(0))
    rare = min(SPREAD, key=SPREAD.get)
    assert policy.buy(p, [rare, 'jhin', rare, rare, rare], OPEN) == '3_1'
    assert SPREAD['shen'] >= 6 and policy.buy(p, [rare, 'shen', rare, rare, rare], OPEN) == '3_1'


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
