"""덱·묶음별 평균 등수, 1등 비율, 4등 안 비율을 지난 기록으로 다시 센다(2026-10-31, 「노선 강제 대조」 읽은 것 5와 「2학기 정리」
5번). 판은 안 돌린다. 비율과 판 단위 부트스트랩 표준오차는 hra.deck_baseline의 deck_table·pair_check를 그대로 쓴다.

diag_flex 기록(자리 목록, 판마다 8자리 차례대로)은 모든 자리를, diag_line 기록({'variant', 'rows'})은 규칙 자리 중 4-1(15번째 칸)에
살아 있던 자리를 센다(「노선 강제 대조」 띠 표와 같은 셈). 묶음은 후반 덱(설계 10절), 느린 리롤 덱, 보통 덱(둘 다 아님)이다.
diag_line 기록이면 강제 자리 − 규칙 자리의 1등·4등 안·8등 비율 차도 판마다 짝지어 센다(모든 자리).

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/deck_rates.py meta/inversion/diag_flex_rows_syn.json
    python meta/inversion/deck_rates.py meta/inversion/diag_line_rows_fast8.json meta/inversion/diag_line_rows_fast8_more.json
"""
import json
import statistics
import sys

from hra.deck_baseline import deck_table, pair_check
from meta.human_bot import KNOBS, late_deck
from meta.lobby import BOARDS

LATE = {b['name'] for b in BOARDS if late_deck(b, KNOBS)}
SLOW = {b['name'] for b in BOARDS if b['slow']}


def load(paths):
    """판마다 자리 dict(기록의 항목 + group·forced·alive)."""
    games = []
    for path in paths:
        d = json.load(open(path, encoding='utf-8'))
        if isinstance(d, list):  # diag_flex: 8자리씩 차례대로, 강제 자리 없음
            part = [[dict(r, forced=False, alive=True) for r in d[i:i + 8]] for i in range(0, len(d), 8)]
            assert all(len(g) == 8 and sum(r['place'] == 1 for r in g) == 1 for g in part), '판 나누기가 어긋남'
        else:  # diag_line
            by = {}
            for r in d['rows']:
                by.setdefault(r['game'], []).append(dict(r, alive=any(c[0] == 15 for c in r['curve'])))
            part = list(by.values())
        games += [[dict(r, group='후반' if r['deck'] in LATE else '느린 리롤' if r['deck'] in SLOW else '보통') for r in g]
                  for g in part]
    return games


if __name__ == '__main__':
    games = load(sys.argv[1:])
    counted = [[r for r in g if not r['forced'] and r['alive']] for g in games]
    print(f'판 {len(counted)}개, 센 자리 {sum(map(len, counted))}개. 후반 덱: {sorted(LATE)}')
    for key in ('group', 'deck'):
        table = deck_table(counted, key, boot=True)
        for name, t in sorted(table.items(), key=lambda kv: -kv[1]['seats']):
            if t['seats'] >= 10:
                print(f"- {name}: {t['seats']}자리, 평균 등수 {t['mean_place']:.2f}, 1등 {t['first']:.1%} ± {t['first_se']:.1%}, "
                      f"4등 안 {t['top4']:.1%} ± {t['top4_se']:.1%}")
    for g in ('보통', '후반'):  # k등 안 비율(k = 1~7). 보통이 모든 k에서 낮지 않으면 등수에 단조인 어떤 보상으로도 못하지 않다
        places = [r['place'] for rows in counted for r in rows if r['group'] == g]
        print(f'{g} k등 안(1~7):', ' '.join(f'{sum(p <= k for p in places) / len(places):.3f}' for k in range(1, 8)))
    for a, b, key in (('보통', '후반', 'group'), ('Chosen Divines', 'Chosen Warlords', 'deck')):
        p = pair_check(counted, a, b, key)
        print(f"- 1등 {a} − {b}: {p['first_diff']:+.1%}p ± {p['first_se']:.1%}p, "
              f"4등 안 {b} − {a}: {p['top4_diff']:+.1%}p ± {p['top4_se']:.1%}p")
    paired = [g for g in games if any(r['forced'] for r in g) and not all(r['forced'] for r in g)]
    for what, ev in (('1등', lambda p: p == 1), ('4등 안', lambda p: p <= 4), ('8등', lambda p: p == 8)) if paired else ():
        x = [statistics.mean(ev(r['place']) for r in g if r['forced']) - statistics.mean(ev(r['place']) for r in g if not r['forced'])
             for g in paired]
        print(f'- 강제 − 규칙(판마다 짝, 모든 자리) {what}: {statistics.mean(x):+.1%}p ± {statistics.stdev(x) / len(x) ** 0.5:.1%}p ({len(x)}판)')
