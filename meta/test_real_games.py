"""
실제 Set 4 판 기록 집계 검사(meta/real_games.py).

실행: python -m meta.test_real_games
"""
import csv
import json
import os
import tempfile

HEADER = ['patch_version', 'match_id', 'puuid', 'placement', 'level', 'gold_left', 'last_round', 'time_in_game',
          'total_dmg_to_players', 'players_eliminated', 'chosen_unit', 'chosen_trait', 'units', 'traits']


def _units(*pairs):
    return str({name: {'items': [], 'stars': stars} for name, stars in pairs})


def _match(patch, mid, seats):
    """seats: 등수 1~8 차례로 (레벨, 남은 골드, 마지막 라운드, 유닛 문자열, 특성 문자열)."""
    return [[patch, mid, f'{mid}-player{p}', p, lv, gold, last, 1800.0, 0, 0, '', '', units, traits]
            for p, (lv, gold, last, units, traits) in enumerate(seats, 1)]


def _csv():
    """판 셋: 10.24 한 판, 10.19 한 판, 1등이 1-3에 끝난 다시 하기 판 하나."""
    dusk = "{'Dusk': 4}"
    a = _match('10.24', 'MATCHSECRET-A', [
        (9, 3, 40, _units(('Yone', 2), ('Kayn', 1), ('Riven', 2), ('Shen', 1)), dusk),
        (8, 0, 40, _units(('Yone', 1)), "{'Warlord': 6}")] +
        [(8, 0, 33 - k, _units(('Jinx', 2)), '{}') for k in range(6)])
    b = _match('10.19', 'MATCHSECRET-B', [
        (8, 10, 37, _units(('Zilean', 2)), dusk),
        (8, 0, 37, _units(('Jinx', 2)), '{}')] +
        [(7, 0, 26, _units(('Jinx', 1)), '{}') for _ in range(6)])
    c = _match('10.24', 'MATCHSECRET-C', [(1, 0, 3, '{}', '{}') for _ in range(8)])
    path = os.path.join(tempfile.mkdtemp(), 'games.csv')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(a + b + c)
    return path


def round_numbers_follow_the_game_test():
    """라운드 번호: 1단계는 넷, 2단계부터 일곱 칸(회전초밥 x-4와 크립 x-7 포함)이다. 봇의 칸 번호는 회전초밥을 뺀 번호다."""
    from meta.real_games import round_name, slot_round
    assert [round_name(r) for r in (4, 5, 11, 26, 33, 40)] == ['1-4', '2-1', '2-7', '5-1', '6-1', '7-1']
    assert [slot_round(s) for s in (3, 15, 18, 21, 27)] == [5, 19, 23, 26, 33]  # 2-1, 4-1, 4-5, 5-1, 6-1


def parsers_read_units_and_traits_test():
    from meta.real_games import parse_traits, parse_units
    assert parse_units("{'Yone': {'items': [99, 5], 'stars': 2}, 'Jhin': {'items': [], 'stars': 1}}") == [('Yone', 2), ('Jhin', 1)]
    assert parse_traits("{'Dusk': 4, 'Mystic': 2}") == {'dusk': 4, 'mystic': 2}


def tally_counts_places_rounds_and_boards_test():
    """1등 레벨 9는 두 판 중 하나, 다시 하기 판은 빠진다. 5코스트 2성 몫과 살아 있는 자리, 계열도 센다."""
    from meta.real_games import tally_csv
    out = tally_csv(_csv())
    assert out['dropped_games'] == 1
    every, one = out['groups']['all'], out['groups']['10.24']
    assert every['games'] == 2 and one['games'] == 1
    first = every['by_place']['1']
    assert first['level']['9'] == 0.5 and first['level']['8'] == 0.5
    assert first['last_round']['median'] == '6-5'  # 37과 40 가운데 낮은 쪽
    assert one['by_place']['1']['five_two_star_share'] == 0.5 and one['by_place']['1']['four_two_star_share'] == 0.5
    assert one['by_place']['1']['five_two_star_per_board'] == 1
    assert one['alive']['7-1'] == 2 and every['alive']['5-1'] == 8
    assert one['families']['dusk']['all']['mean_place'] == 1 and one['families']['warlord']['8']['mean_place'] == 2
    assert 'MATCHSECRET' not in json.dumps(out) and 'player' not in json.dumps(out)  # 식별 칸은 결과에 남기지 않는다


def bot_record_uses_the_last_round_it_started_test():
    """봇 기록: 마지막 칸의 레벨과 라운드로 같은 표를 낸다. 판 기록에만 있는 보드 값은 없다."""
    from meta.real_games import bot_summary
    seat = lambda place, slot, level: {'place': place, 'curve': [[3, 4, 10, 100], [slot, level, 5, 10]]}
    out = bot_summary({'rows': [[seat(1, 33, 9), seat(2, 33, 8)] + [seat(p, 21, 7) for p in range(3, 9)]]})
    assert out['games'] == 1 and out['by_place']['1']['level']['9'] == 1
    assert out['alive']['7-1'] == 2 and out['alive']['5-1'] == 8
    assert out['by_place']['1']['last_round']['median'] == '7-1'
    assert 'five_two_star_share' not in out['by_place']['1']


def tables_match_the_repo_test():
    """이 집계는 격리 실행(-I)을 위해 표를 따로 들고 있다. 저장소의 비용 표와 계열 규칙과 같아야 한다."""
    from meta.play_stats import FAMILIES as REPO
    from meta.real_games import FAMILIES, FOUR, FIVE
    from Simulator.stats import COST
    low = {k.lower() for k in FIVE | FOUR}
    assert {k for k, v in COST.items() if v == 5} == {k for k in low if COST.get(k) == 5} and all(COST[k.lower()] == 5 for k in FIVE)
    assert {k for k, v in COST.items() if v == 4} == {k for k in low if COST.get(k) == 4} and all(COST[k.lower()] == 4 for k in FOUR)
    assert FAMILIES == [(name, n) for name, n, _ in REPO]


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
