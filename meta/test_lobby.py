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


def deck_policy_variants_change_normal_deck_levels_test():
    """떼어 재기 조건(--variant). fast8: 보통 덱이 4-3(17번째 칸)에 레벨 8로 가서 30골드를 남기고 리롤한다(ML).
    level9: 보통 덱이 5단계(21번째 칸)부터 레벨 9를 노린다(B24). 조건이 없으면 지금 규칙 그대로다."""
    from meta.lobby import apply_variant
    def act(game_round, level, gold):
        p = deck_player(['jhin'], gold=gold)
        p.level = level
        return DeckPolicy(p.default_agent, SHARPSHOOTERS)(p, ['garen'] * 5, game_round, OPEN)
    try:
        apply_variant('fast8')
        assert [act(17, 7, 60), act(17, 8, 31), act(17, 8, 32)] == ['1', '0', '2']
        apply_variant('level9')
        assert [act(21, 8, 60), act(18, 8, 60), act(21, 9, 22)] == ['1', '2', '2']
    finally:
        apply_variant(None)
    assert [act(17, 7, 60), act(17, 8, 31), act(21, 8, 60)] == ['0', '2', '2']


def _deck_rules():
    from meta.lobby import DeckPolicy
    return DeckPolicy.level8_round, DeckPolicy.level8_floor, DeckPolicy.level9_stage


def variant_reaches_workers_test():
    """--variant 조건이 일꾼 프로세스까지 들어가야 한다(Windows 일꾼은 새 프로세스라 부모가 바꾼 클래스 값을 물려받지 않는다)."""
    from multiprocessing import Pool
    from meta.lobby import apply_variant
    with Pool(1, initializer=apply_variant, initargs=('fast8',)) as workers:
        assert workers.apply(_deck_rules) == (17, 30, None)
    with Pool(1, initializer=apply_variant, initargs=('level9',)) as workers:
        assert workers.apply(_deck_rules) == (18, 20, 5)


def carriers_are_units_with_most_recommended_items_test():
    """덱의 캐리는 추천 아이템을 가장 많이 드는 유닛들이다(설계 4절)."""
    from meta.lobby import carriers
    assert carriers({'items': {'jhin': ['a', 'b', 'c'], 'riven': ['d', 'e', 'f'], 'aatrox': ['g']}}) == ['jhin', 'riven']
    assert carriers({'items': {'riven': ['a', 'b', 'c'], 'jhin': ['d', 'e']}}) == ['riven']


def finish_order_puts_survivor_on_top_and_ranks_by_health_before_round_test():
    """같은 걸음에 끝난 플레이어의 등수(낮은 등수부터): 같은 라운드 탈락자는 라운드 전 체력이 적은 쪽이 아래(공식 10.14),
    우승자(체력이 남은 사람)는 맨 위다. 라운드 전 체력이 같으면 이름순이 아니라 무작위다. 예전에는 이름순이라 마지막 두 명
    중 번호가 큰 쪽이 1등이 됐다(21판 중 10판에서 1등이 끝날 때 체력 0 이하)."""
    import random
    from meta.lobby import finish_order
    players = {'a': Unit(health=-5), 'b': Unit(health=-20), 'c': Unit(health=12), 'd': Unit(health=-1)}
    start = {'a': 30, 'b': 10, 'c': 5, 'd': 30}
    for seed in range(5):
        order = finish_order(['a', 'b', 'c', 'd'], players, start, random.Random(seed))
        assert order[0] == 'b' and order[-1] == 'c' and set(order[1:3]) == {'a', 'd'}, order
    firsts = {finish_order(['a', 'd'], players, start, random.Random(seed))[0] for seed in range(20)}
    assert firsts == {'a', 'd'}, firsts


def first_place_is_the_survivor_test():
    """한 판을 끝까지 돌려서 1등이 끝날 때 체력이 남은 플레이어인지 본다(덱 봇, 시드 2000)."""
    import random
    from meta import lobby
    health = {}
    record = lobby.board_record
    lobby.board_record = lambda p: health.__setitem__(p.player_num, p.health) or record(p)
    try:
        res = lobby.play((2000, random.Random(2000).sample(range(len(lobby.BOARDS)), 8)), bot='deck')
    finally:
        lobby.board_record = record
    first = next(i for i, p in enumerate(res['players']) if p['place'] == 1)
    assert health[first] > 0, (health, [p['place'] for p in res['players']])


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
