"""
meta.lobby의 아이템 나눠 주기(hand_out_items) 검사.

실행: python -m meta.test_lobby
"""
from types import SimpleNamespace as Unit

from Simulator.champion import champion
from Simulator.item_stats import basic_items, item_builds
from Simulator.player import Player
from Simulator.pool import pool
from meta.lobby import DeckPolicy, hand_out_items

DECK = {'jhin': ['guardian_angel', 'infinity_edge', 'last_whisper'],
        'riven': ['ionic_spark', 'quicksilver', 'sunfire_cape']}


def player(board_units, bench_items):
    board = [[None] * 4 for _ in range(7)]
    for x, u in enumerate(board_units):
        board[x][0] = u
    return Unit(board=board, bench=[None] * 9, item_bench=list(bench_items) + [None] * (10 - len(bench_items)))


def worth(p):
    """조각 1, 완성 아이템 2로 센 합. 나눠 주기 전후로 같아야 한다."""
    held = [i for row in p.board for u in row if u for i in u.items] + [i for i in p.item_bench if i]
    return sum(1 if i in basic_items else 2 if i in item_builds else 0 for i in held)


def gives_recommended_items_in_order_test():
    """가진 몫(조각 2 + 완성 1 + 조각 1 = 5)의 절반인 2개를 추천 순서대로 캐리에게 주고, 홀수로 남는 조각 하나는 남긴다."""
    jhin = Unit(name='jhin', stars=2, items=['bf_sword', 'recurve_bow'])
    riven = Unit(name='riven', stars=1, items=['infinity_edge'])
    p = player([jhin, riven], ['chain_vest'])
    hand_out_items(p, DECK)
    assert jhin.items == ['guardian_angel', 'infinity_edge'] and riven.items == [], (jhin.items, riven.items)
    assert worth(p) == 5 and sum(1 for i in p.item_bench if i) == 1, p.item_bench
    hand_out_items(p, DECK)  # 라운드마다 다시 해도 같다
    assert jhin.items == ['guardian_angel', 'infinity_edge'] and worth(p) == 5


def missing_carrier_keeps_components_test():
    """캐리(진)가 없으면 그 몫은 조각 두 개씩으로 아이템 칸에 남아, 다음 라운드에 다시 센다."""
    riven = Unit(name='riven', stars=2, items=['infinity_edge', 'last_whisper'])
    p = player([riven], [])
    hand_out_items(p, DECK)
    assert riven.items == [] and worth(p) == 4, (riven.items, p.item_bench)
    assert sorted(i for i in p.item_bench if i) == sorted(item_builds['guardian_angel'] + item_builds['infinity_edge'])


def special_items_untouched_test():
    """도적의 장갑·소모품·주걱은 건드리지 않고, 도적의 장갑을 든 유닛에게는 주지 않는다."""
    jhin = Unit(name='jhin', stars=1, items=['thieves_gloves'])
    p = player([jhin], ['champion_duplicator', 'spatula', 'bf_sword', 'bf_sword'])
    hand_out_items(p, DECK)
    assert jhin.items == ['thieves_gloves'], jhin.items
    assert {'champion_duplicator', 'spatula'} <= set(p.item_bench), p.item_bench
    assert sorted(i for i in p.item_bench if i in item_builds or i in basic_items and i != 'spatula') == \
        sorted(item_builds['guardian_angel']), p.item_bench


def keeps_extra_share_beyond_recommended_test():
    """추천 6개를 다 줘도 남는 몫은 조각으로 남긴다(합이 줄지 않는다)."""
    jhin = Unit(name='jhin', stars=2, items=[])
    riven = Unit(name='riven', stars=2, items=[])
    p = player([jhin, riven], ['infinity_edge'] * 7)
    hand_out_items(p, DECK)
    assert jhin.items == DECK['jhin'] and riven.items == DECK['riven'], (jhin.items, riven.items)
    assert worth(p) == 14, p.item_bench


SHARPSHOOTERS = {'name': 'Chosen Sharpshooters', 'slow': False, 'items': DECK,
                 'units': ['nidalee', 'vayne', 'jarvaniv', 'teemo', 'kennen', 'jinx', 'jhin', 'riven', 'azir']}
OPEN = [[1]] * 60  # 상점 다섯 칸이 모두 살 수 있는 마스크(정책은 mask[47 + i][0]만 본다)


def deck_player(board_units, bench_units=(), gold=100):
    """보드가 꽉 찬(max_units = 보드 유닛 수) 플레이어."""
    p = Player(pool(), 0)
    p.gold, p.max_units = 1000, len(board_units)
    for x, name in enumerate(board_units):
        p.buy_champion(champion(name))
        p.move_bench_to_board(0, x, 0)
    for name in bench_units:
        p.buy_champion(champion(name))
    p.gold = gold
    return p


def deck_policy_buys_only_deck_units_test():
    """덱 유닛은 사고 덱 밖 유닛은 사지 않는다."""
    p = deck_player(['jhin'])
    policy = DeckPolicy(p.default_agent, SHARPSHOOTERS)
    assert policy(p, ['garen', 'vayne', 'garen', 'garen', 'garen'], 12, OPEN) == '3_1'
    assert not policy(p, ['garen'] * 5, 12, OPEN).startswith('3_')


def deck_policy_buys_chosen_of_deck_trait_test():
    """덱 특성의 선택받은 자는 1성 값의 세 배로 산다. 다른 특성 선택받은 자는 사지 않는다."""
    p = deck_player(['vayne'], gold=12)
    policy = DeckPolicy(p.default_agent, SHARPSHOOTERS)
    assert policy(p, ['jhin_cultist_c', 'jhin_sharpshooter_c', 'garen', 'garen', 'garen'], 12, OPEN) == '3_1'
    p.gold = 11
    assert not policy(p, ['jhin_sharpshooter_c', 'garen', 'garen', 'garen', 'garen'], 12, OPEN).startswith('3_')


def deck_policy_swaps_bench_deck_unit_onto_board_test():
    """벤치의 덱 유닛과 보드의 덱 밖 유닛을 바꾼다. 보드에 이미 있는 덱 유닛의 사본은 올리지 않는다."""
    p = deck_player(['garen'], ['jhin'], gold=0)
    policy = DeckPolicy(p.default_agent, SHARPSHOOTERS)
    assert policy(p, ['garen'] * 5, 12, OPEN) == '5_0_28'
    p = deck_player(['jhin'], ['jhin'], gold=0)
    policy = DeckPolicy(p.default_agent, SHARPSHOOTERS)
    assert not policy(p, ['garen'] * 5, 12, OPEN).startswith('5_')


def deck_policy_sells_non_deck_units_first_test():
    """벤치가 차면 덱 밖 유닛부터 판다."""
    p = deck_player(['jhin'], ['vayne', 'teemo', 'jinx', 'kennen', 'nidalee', 'garen', 'jarvaniv', 'azir', 'riven'],
                    gold=0)
    policy = DeckPolicy(p.default_agent, SHARPSHOOTERS)
    assert policy(p, ['garen'] * 5, 12, OPEN) == f'4_{28 + 5}'


def deck_policy_levels_and_rolls_by_style_test():
    """보통 덱: 4단계에 레벨 7, 4단계 후반(18번째 칸부터) 8, 그 뒤 20골드를 남기고 리롤.
    느린 리롤 덱: 레벨 6에서 50골드 넘는 몫으로 리롤, 5단계(21번째 칸부터) 레벨 8."""
    slow = dict(SHARPSHOOTERS, slow=True)
    cases = [(SHARPSHOOTERS, 16, 6, 50, '1'), (SHARPSHOOTERS, 16, 7, 60, '0'), (SHARPSHOOTERS, 18, 7, 60, '1'),
             (SHARPSHOOTERS, 18, 8, 22, '2'), (SHARPSHOOTERS, 18, 8, 21, '0'),
             (slow, 12, 5, 30, '1'), (slow, 12, 6, 52, '2'), (slow, 12, 6, 51, '0'), (slow, 21, 6, 30, '1')]
    for board, game_round, level, gold, expected in cases:
        p = deck_player(['jhin'], gold=gold)
        p.level = level
        action = DeckPolicy(p.default_agent, board)(p, ['garen'] * 5, game_round, OPEN)
        assert action == expected, (board['slow'], game_round, level, gold, action)


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
