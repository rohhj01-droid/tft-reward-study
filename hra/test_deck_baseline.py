"""
덱 고르기 기준선 검사(hra/deck_baseline.py). 끝의 두 검사는 판을 실제로 돌려서 느리다(판 하나에 20초쯤).

실행: python -m hra.test_deck_baseline
"""


def _games():
    """판 둘. 자리마다 2-1 덱, 끝 덱, 등수."""
    g1 = [{'first': 'A', 'final': 'A', 'place': 1}, {'first': 'A', 'final': 'B', 'place': 5},
          {'first': 'B', 'final': 'B', 'place': 2}, {'first': 'C', 'final': 'C', 'place': 8}]
    g2 = [{'first': 'A', 'final': 'A', 'place': 3}, {'first': 'B', 'final': 'B', 'place': 1},
          {'first': 'B', 'final': 'B', 'place': 6}, {'first': 'C', 'final': 'C', 'place': 4}]
    return [g1, g2]


def deck_table_counts_seats_mean_first_and_top4_test():
    """2-1 덱으로 세면 A는 자리 3개(1, 5, 3등): 평균 3, 1등 1/3, 4등 안 2/3. 끝 덱으로 세면 A는 자리 2개(1, 3등)다."""
    from hra.deck_baseline import deck_table
    t = deck_table(_games(), 'first')
    assert t['A']['seats'] == 3 and abs(t['A']['mean_place'] - 3) < 1e-9
    assert abs(t['A']['first'] - 1 / 3) < 1e-9 and abs(t['A']['top4'] - 2 / 3) < 1e-9
    assert t['C']['seats'] == 2 and t['C']['first'] == 0 and abs(t['C']['top4'] - 0.5) < 1e-9
    assert deck_table(_games(), 'final')['A']['seats'] == 2


def pair_check_needs_both_differences_beyond_two_se_test():
    """X는 1등 아니면 7등, Y는 2등 아니면 4등이면 X가 1등이 많고 Y가 4등 안이 많아 맞바꿈이 버틴다. 둘이 똑같이
    1~8등을 돌면 차가 없어 안 버틴다."""
    from hra.deck_baseline import pair_check
    games = [[{'first': 'X', 'final': 'X', 'place': 1 if k % 2 else 7},
              {'first': 'Y', 'final': 'Y', 'place': 2 if k % 3 else 4}] for k in range(400)]
    r = pair_check(games, 'X', 'Y', 'first')
    assert r['holds'] and r['first_diff'] > 2 * r['first_se'] and r['top4_diff'] > 2 * r['top4_se']
    same = [[{'first': 'X', 'final': 'X', 'place': 1 + k % 8}, {'first': 'Y', 'final': 'Y', 'place': 1 + (k + 1) % 8}]
            for k in range(400)]
    assert not pair_check(same, 'X', 'Y', 'first')['holds']


def top_decks_takes_best_mean_among_decks_with_enough_seats_test():
    """자리가 모자란 덱은 평균이 1등이어도 빼고, 남은 덱을 평균 등수가 좋은 순서로 k개 고른다."""
    from hra.deck_baseline import top_decks
    table = {'A': {'seats': 150, 'mean_place': 3.9}, 'B': {'seats': 120, 'mean_place': 3.2},
             'C': {'seats': 99, 'mean_place': 1.0}, 'D': {'seats': 300, 'mean_place': 4.5},
             'E': {'seats': 101, 'mean_place': 5.0}}
    assert top_decks(table, k=3, min_seats=100) == ['B', 'A', 'D']


def risk_game_reads_first_deck_of_every_seat_test():
    """규칙 기록기 8명 한 판: 자리마다 2-1 덱과 끝 덱이 사람 봇 덱 이름이고, 등수는 1~8이 하나씩 나간다."""
    from hra.deck_baseline import risk_game
    from meta.lobby import BOARDS
    seed, rows, err = risk_game(11)
    names = {b['name'] for b in BOARDS}
    assert err is None and len(rows) == 8, err
    assert sorted(r['place'] for r in rows) == list(range(1, 9))
    assert all(r['first'] in names and r['final'] in names for r in rows), rows


def top_deck_seats_only_go_to_allowed_decks_test():
    """기준선 자리 4개(덱 후보 셋)와 규칙 자리 4개 한 판: 기준선 자리는 끝까지 후보 셋 안의 덱에 있고, 등수는 1~8이 하나씩."""
    from hra.deck_baseline import topdecks
    from hra.plan_bot import play
    allowed = ('Chosen Warlords', 'Chosen Divines', 'Chosen Cultists')
    out = play(13, [topdecks(allowed)] * 4 + ['rule'] * 4)
    assert sorted(s['place'] for s in out['seats']) == list(range(1, 9))
    assert all(s['deck'] in allowed for s in out['seats'][:4]), [s['deck'] for s in out['seats'][:4]]


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
