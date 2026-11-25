"""실제 10.24 판의 마지막 대전(1등과 2등의 끝 보드)을 뽑는다(2026-11-25, results/README 「실제 판의 마지막 대전을 시뮬레이터에서 붙이기」).

판 기록은 meta/real_games.py와 같은 Kaggle 판 기록이다. 판 번호와 플레이어 식별 칸은 한 판의 여덟 자리를 묶는 데만 쓰고 결과에 남기지 않는다.
결과는 판마다 두 보드(유닛 이름·별·아이템 번호, 선택받은 자, 레벨, 기록에 적힌 특성 수)이고 순서를 섞어 적는다. 저장소에는 넣지 않는다.

- 1등과 2등은 같은 라운드에 끝난다. 그 라운드에 둘이 붙었고 2등이 져서 죽었다.
- 뺀다: 3등이 2등과 같은 라운드에 끝난 판(셋이 남아 있었으니 2등이 1등과 붙었는지 모른다), 어느 보드든 유닛 수가 레벨보다 둘 이상 적은 판
  (보드를 판 것으로 본다), 선택받은 자 유닛은 적혀 있는데 특성이 빈 판, 1등이 4-1 전에 끝난 판(다시 하기).
- 한계: 유닛 칸이 이름을 열쇠로 한 사전이라 같은 유닛 두 장은 한 장으로 남는다. 배치는 기록에 없다.

내려받은 파일을 읽으므로 표준 라이브러리만 쓰고 격리 실행한다:
    python -I meta/inversion/final_pairs.py <csv> <적을 파일>
    python -I meta/inversion/final_pairs.py selfcheck
"""
import ast
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict

PATCH = '10.24'
FIRST_ROUND = 19  # meta/real_games.py와 같다
SHUFFLE_SEED = 0
NAME = re.compile(r'[A-Za-z]+\Z')


def board(row):
    """기록 한 줄 -> 보드. 이름은 글자만, 별은 1~3, 아이템은 번호여야 한다."""
    units = ast.literal_eval(row['units'])
    traits = ast.literal_eval(row['traits'])
    out = []
    for name, u in units.items():
        assert NAME.match(name) and u['stars'] in (1, 2, 3) and all(type(i) is int for i in u['items']), '유닛 칸의 모양이 다르다'
        out.append([name, u['stars'], list(u['items'])])
    assert all(NAME.match(t) and type(n) is int for t, n in traits.items()), '특성 칸의 모양이 다르다'
    cu, ct = row['chosen_unit'], row['chosen_trait']
    assert (not cu or NAME.match(cu)) and (not ct or NAME.match(ct)), '선택받은 자 칸의 모양이 다르다'
    return {'level': int(float(row['level'])), 'units': out, 'traits': traits, 'chosen': [cu, ct] if cu else None}


def pair(seats):
    """한 판의 여덟 자리(등수 -> 줄) -> (두 보드와 끝난 라운드, None) 또는 (None, 뺀 까닭)."""
    last = {p: int(float(r['last_round'])) for p, r in seats.items()}
    if last[1] < FIRST_ROUND:
        return None, 'replay'
    if last[3] >= last[2]:
        return None, 'third_same_round'
    boards = [board(seats[1]), board(seats[2])]
    if any(len(b['units']) < b['level'] - 1 for b in boards):
        return None, 'sold_board'
    if any(b['chosen'] and (not b['chosen'][1] or b['chosen'][0] not in {u[0] for u in b['units']}) for b in boards):
        return None, 'chosen_unclear'
    assert last[1] == last[2], '1등과 2등이 다른 라운드에 끝났다'
    return {'round': last[1], 'boards': boards}, None


def pairs_of(rows):
    games = defaultdict(dict)
    for row in rows:
        if row['patch_version'] == PATCH:
            games[row['match_id']][int(float(row['placement']))] = row
    assert all(sorted(g) == list(range(1, 9)) for g in games.values()), '여덟 자리가 아닌 판이 있다'
    out, dropped = [], Counter()
    for g in games.values():
        p, why = pair(g)
        if p is None:
            dropped[why] += 1
        else:
            out.append(p)
    random.Random(SHUFFLE_SEED).shuffle(out)  # 기록의 순서를 남기지 않는다. 앞에서부터 쓰면 무작위로 고른 것과 같다
    return len(games), out, dropped


def selfcheck():
    def row(m, place, last, units, level=2, cu='', ct=''):
        return {'patch_version': PATCH, 'match_id': m, 'placement': str(place), 'last_round': str(last), 'level': str(level),
                'units': repr(units), 'traits': "{'Dusk': 2}", 'chosen_unit': cu, 'chosen_trait': ct}
    two = {'Riven': {'items': [15, 7], 'stars': 2}, 'Vayne': {'items': [], 'stars': 1}}

    def game(m, last, **first):
        return [row(m, p, last[p - 1] if p <= 3 else 10, two, **(first if p == 1 else {})) for p in range(1, 9)]
    rows = (game('a', [37, 37, 30], cu='Riven', ct='Dusk') + game('b', [37, 37, 37]) + game('c', [18, 18, 17])
            + game('d', [37, 37, 30], level=4) + game('e', [37, 37, 30], cu='Riven') + game('f', [37, 37, 30], cu='Yone', ct='Exile')
            + [dict(r, patch_version='10.23') for r in game('g', [37, 37, 30])])
    n, out, dropped = pairs_of(rows)
    assert n == 6 and dropped == {'third_same_round': 1, 'replay': 1, 'sold_board': 1, 'chosen_unclear': 2}, (n, dropped)
    assert out == [{'round': 37, 'boards': [{'level': 2, 'units': [['Riven', 2, [15, 7]], ['Vayne', 1, []]], 'traits': {'Dusk': 2},
                                             'chosen': ['Riven', 'Dusk']},
                                            {'level': 2, 'units': [['Riven', 2, [15, 7]], ['Vayne', 1, []]], 'traits': {'Dusk': 2}, 'chosen': None}]}]
    assert 'match' not in json.dumps(out) and 'puuid' not in json.dumps(out)
    print('selfcheck 통과')


if __name__ == '__main__':
    if sys.argv[1] == 'selfcheck':
        selfcheck()
        sys.exit()
    csv.field_size_limit(10 ** 7)
    with open(sys.argv[1], 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(sys.argv[1], encoding='utf-8', newline='') as f:
        n, out, dropped = pairs_of(csv.DictReader(f))
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump({'source': {'name': 'TEAMFIGHT TACTICS: FATES Challenger EUW Rank Games', 'csv_sha256': digest}, 'patch': PATCH,
                   'games': n, 'dropped': dict(dropped), 'shuffle_seed': SHUFFLE_SEED, 'pairs': out}, f)
    print(f'판 {n} 뽑은 대전 {len(out)} 뺀 판 {dict(dropped)}')
