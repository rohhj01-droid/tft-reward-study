"""밸류덱(후반 덱)과 돈·체력 관찰(코드 안 바꿈, 새 판 안 돌림, 2026-11-13): 이미 있는 규칙 사람 봇 8명 기록
(diag_flex.py의 자리별 곡선 [칸, 레벨, 골드, 체력, ...])에서 4-1 시작 때 골드·체력과 덱 묶음별 등수, 레벨 8에 올라선 때의 골드를 센다.
덱을 무작위로 나눈 것이 아니라서 관찰이다. 덱 묶음은 끝 덱으로 나눈다.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/diag_spend.py meta/inversion/diag_flex_rows_syn.json
"""
import json
import statistics
import sys

from meta.human_bot import KNOBS, late_deck
from meta.lobby import BOARDS

LATE = {b['name'] for b in BOARDS if late_deck(b, KNOBS)}
SLOW = {b['name'] for b in BOARDS if b['slow']}
NAMES = {'late': '밸류덱(후반 덱 5개)', 'normal': '보통 덱', 'slow': '느린 리롤 덱'}


def group(deck):
    return 'late' if deck in LATE else 'slow' if deck in SLOW else 'normal'


def cell(places):
    if not places:
        return '-'
    return (f'{len(places)}, {statistics.mean(places):.2f}등, 1등 {sum(p == 1 for p in places) / len(places):.0%}, '
            f'4등 안 {sum(p <= 4 for p in places) / len(places):.0%}')


if __name__ == '__main__':
    rows = json.load(open(sys.argv[1], encoding='utf-8'))
    seats = []  # (묶음, 4-1 골드, 4-1 체력, 등수)
    for r in rows:
        c = next((x for x in r['curve'] if x[0] == 15), None)
        if c:
            seats.append((group(r['deck']), c[2], c[3], r['place']))
    gold, hp = sorted(s[1] for s in seats), sorted(s[2] for s in seats)
    q = lambda a, p: a[int(len(a) * p)]
    print(f'4-1을 시작한 자리 {len(seats)}개. 골드 10%·50%·90% 자리: {q(gold, .1)}, {q(gold, .5)}, {q(gold, .9)} / 체력: {q(hp, .1)}, {q(hp, .5)}, {q(hp, .9)}')
    print('\n| 4-1 체력 | ' + ' | '.join(NAMES.values()) + ' |\n|---|---|---|---|')
    for lo, hi in ((80, 101), (60, 80), (40, 60), (0, 40)):
        print(f'| {lo}~{hi - 1} | ' + ' | '.join(cell([s[3] for s in seats if s[0] == g and lo <= s[2] < hi]) for g in NAMES) + ' |')
    print('| 골드 60 이상이고 체력 70 이상 | ' + ' | '.join(cell([s[3] for s in seats if s[0] == g and s[1] >= 60 and s[2] >= 70]) for g in NAMES) + ' |')
    late = [r for r in rows if r['deck'] in LATE]
    first8 = [next((c for c in r['curve'] if c[1] >= 8), None) for r in late]
    g8 = [c[2] for c in first8 if c]
    print(f'\n밸류덱 자리 {len(late)}개가 처음 레벨 8로 라운드를 시작할 때 골드: 가운데 {statistics.median(g8)}, 30 이상 {sum(g >= 30 for g in g8) / len(g8):.0%}')
    print('\n| 밸류덱 자리가 레벨 8로 처음 시작한 칸 | 자리, 등수 | 4코스트 2성이 하나 이상 |\n|---|---|---|')
    for name, cond in (('4-6(19번째 칸)까지', lambda c: c and c[0] <= 19), ('그 뒤', lambda c: c and c[0] > 19), ('끝까지 못 찍음', lambda c: c is None)):
        rs = [r for r, c in zip(late, first8) if cond(c)]
        if rs:
            print(f'| {name} | {len(rs)}, {statistics.mean(r["place"] for r in rs):.2f}등 | {sum(r["four2"] >= 1 for r in rs) / len(rs):.0%} |')
