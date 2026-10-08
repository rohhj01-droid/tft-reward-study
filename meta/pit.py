"""
10.24 메타 보드끼리 시뮬레이터에서 붙인다.

tftactics 10.24 표의 보드 27개를 서로 모두 붙여(라운드로빈) 보드마다 나머지 26개 상대 평균 승률을 낸다.
조건은 두 가지다.
  사람 근사: 5코스트는 1성, 느린 리롤 덱에서 아이템 3개를 든 1~2코스트는 3성, 나머지 2성.
            선택받은 자 1명(chosen_of), 근접은 앞줄·원거리는 뒷줄(analysis/battle.range_positions).
  기존 하네스: 모두 2성, 선택받은 자 없음, 무작위 배치. analysis/comp_tiers.py와 같은 조건이다.

실행: python -m meta.pit --n 60 --jobs 7 --out results/pit_1024.json
"""
import argparse
import json
import os
import re
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import CHAMPION_TRAITS, TRAIT_BREAKS, cost_of
from Simulator.item_stats import item_builds
from analysis.battle import win_rate
from meta.decks_1024 import DECKS, classify, trait_counts

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tftactics_10.24_2020-11-28.txt')

# bunnymuffins 10.24b(핫픽스 뒤) 티어를 같은 덱으로 보이는 tftactics 보드에 옮긴 것. 나머지 13개는 그 표에 없다.
BUNNY_1024B = {
    'Chosen Dusks': 'S', 'Chosen Divines': 'S',
    'Ninja Shades': 'A', 'Moonlight Assassins': 'A', 'Chosen Warlords': 'A',
    'Chosen Duelists': 'B', 'Chosen Sharpshooters': 'B', 'Chosen Hunters': 'B',
    'Vanguard Mystics': 'B', 'Chosen Brawlers': 'B', 'Chosen Elderwood': 'B',
    'Enlightened Adepts': 'C', 'Enlightened Mages': 'C', 'Chosen Cultists': 'C',
}

# 이름 첫 단어와 bunnymuffins 10.24b가 권한 선택받은 자가 다른 덱. 닌자는 4명일 때만 켜져서 5명이 되면 안 된다.
CHOSEN_OVERRIDE = {'Ninja Shades': 'shade'}


def load_boards(path=SRC):
    """원자료 txt의 보드들. 유닛은 밑줄을 빼고, 아이템은 소문자·밑줄로 바꿔 시뮬레이터 이름에 맞춘다."""
    boards = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        tier, name, style, _, body = [c.strip() for c in line.split('|')]
        units, items = [], {}
        for unit, held in re.findall(r'(\w+)(?:\[([^\]]*)\])?', body):
            unit = unit.replace('_', '')
            units.append(unit)
            if held:
                items[unit] = [i.lower().replace("'", '').replace(' ', '_') for i in held.split('+')]
                # 이름을 잘못 옮기면 전투에서 아이템이 조용히 빠질 수 있어서 여기서 막는다
                assert all(i in item_builds for i in items[unit]), (name, unit, items[unit])
        boards.append({'name': name, 'tier': tier, 'slow': style == 'Slow Roll',
                       'units': units, 'items': items})
    return boards


def chosen_of(board):
    """선택받은 자 (유닛, 특성). 특성은 이름이 "Chosen X"면 X, 아니면 이름의 첫 단어다.
    유닛은 그 특성을 가진 1~4코스트 중 아이템이 가장 많은 쪽, 같으면 비싼 쪽, 그래도 같으면 먼저 적힌 쪽."""
    words = board['name'].split()
    trait = CHOSEN_OVERRIDE.get(board['name'],
                                (words[1] if words[0] == 'Chosen' else words[0]).lower().rstrip('s'))
    assert trait in TRAIT_BREAKS, (board['name'], trait)
    order = {u: i for i, u in enumerate(board['units'])}
    pool = [u for u in board['units'] if trait in CHAMPION_TRAITS[u] and cost_of(u) < 5]
    pool.sort(key=lambda u: (-len(board['items'].get(u, [])), -cost_of(u), order[u]))
    return (pool[0], trait) if pool else None


def spec(board, human):
    """전투 하네스 형식의 보드. human=False면 기존 하네스 조건(모두 2성, 선택받은 자 없음)."""
    pick = chosen_of(board) if human else None
    out = []
    for name in board['units']:
        items = board['items'].get(name, [])
        stars = 2
        if human and cost_of(name) == 5:
            stars = 1
        elif human and board['slow'] and cost_of(name) <= 2 and len(items) == 3:
            stars = 3
        unit = {'name': name, 'stars': stars, 'items': items}
        if pick and pick[0] == name:
            unit['chosen'] = pick[1]
        out.append(unit)
    return out


def _pair(job):
    return win_rate(*job)


def round_robin(specs, n, place, jobs, init=None, only=None):
    """init은 일꾼 프로세스마다 먼저 부르는 함수다(수치 바꾸기 등). 윈도우에서는 일꾼이 모듈을 새로 불러서
    부모에서 바꾼 값이 넘어가지 않는다. only를 주면 그 이름이 낀 매치업만 붙인다."""
    names = list(specs)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if only is None or a in only or b in only]
    with Pool(jobs, initializer=init) as workers:
        rates = workers.map(_pair, [(specs[a], specs[b], n, place) for a, b in pairs], chunksize=1)
    matrix = {a: {} for a in names}
    for (a, b), rate in zip(pairs, rates):
        matrix[a][b] = round(rate, 3)
        matrix[b][a] = round(1 - rate, 3)
    return matrix


def average(matrix):
    return {a: sum(row.values()) / len(row) for a, row in matrix.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=60, help='매치업당 판 수')
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=None, help='승률 매트릭스 JSON 저장 경로')
    args = ap.parse_args()

    boards = {b['name']: b for b in load_boards()}
    deck_board = {key: next(b['name'] for b in boards.values() if set(b['units']) == set(d['units']))
                  for key, d in DECKS.items()}
    deck_of = {}
    for name, b in boards.items():
        pick = chosen_of(b)
        deck_of[name] = ','.join(classify(b['units'], trait_counts(b['units'], b['items'],
                                                                   pick[1] if pick else None))) or '-'

    matrices = {}
    for setting, human, place in [('human', True, 'range'), ('harness', False, 'random')]:
        matrices[setting] = round_robin({n: spec(b, human) for n, b in boards.items()},
                                        args.n, place, args.jobs)
        print(f'{setting} 완료', flush=True)
    avg = {s: average(m) for s, m in matrices.items()}

    # 상대 26개 x N판이라 평균 승률의 표준오차는 N=60에서 1.3%p 안팎이다.
    print(f'\n보드별 평균 승률 (상대 {len(boards) - 1}개, 매치업당 N={args.n}), 사람 근사 순')
    print(f'{"보드":22} {"tftactics":>9} {"10.24b":>7} {"우리 덱":>16} {"사람 근사":>9} {"기존 하네스":>10}')
    for name in sorted(boards, key=lambda x: -avg['human'][x]):
        print(f'{name:22} {boards[name]["tier"]:>9} {BUNNY_1024B.get(name, "-"):>7} {deck_of[name]:>16} '
              f'{avg["human"][name] * 100:8.1f}% {avg["harness"][name] * 100:9.1f}%')

    print('\n티어별 평균 승률')
    for label, tier_of in [('tftactics 10.24(핫픽스 전)', {n: b['tier'] for n, b in boards.items()}),
                           ('bunnymuffins 10.24b(핫픽스 뒤)', BUNNY_1024B)]:
        for tier in 'SABC':
            members = [n for n, t in tier_of.items() if t == tier]
            if members:
                h = sum(avg['human'][n] for n in members) / len(members)
                r = sum(avg['harness'][n] for n in members) / len(members)
                print(f'  {label} {tier} ({len(members)}개)  사람 근사 {h * 100:5.1f}%  기존 하네스 {r * 100:5.1f}%')

    keys = list(DECKS)
    for setting in matrices:
        print(f'\n우리 덱끼리 ({setting}, 행이 열을 이긴 비율, 매치업당 N={args.n})')
        print(' ' * 16 + ''.join(f'{k[:10]:>11}' for k in keys))
        for a in keys:
            row = matrices[setting][deck_board[a]]
            print(f'{a:16}' + ''.join(f'{"":>11}' if a == b else f'{row[deck_board[b]] * 100:10.0f}%'
                                      for b in keys))

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'n': args.n, 'deck_board': deck_board, **matrices}, f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
