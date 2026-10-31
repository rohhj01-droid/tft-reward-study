"""사후 재조합 탐침 기록(probe_heads.py가 쓴 JSON)을 같은 덱끼리 AI 자리와 규칙 자리로 나눠 본다(2026-10-31, 판은 안 돌린다).
덱마다 자리 수·평균 등수, 4-1·4-5·5-1·5-5 시작 때 레벨 / 골드(살아 있던 자리 수), 4단계(15~20번째 칸)·5단계(21~26번째 칸) 계획 판단의
레벨 +1 비율과 남길 골드 50 / 10 / 0 비율, 그리고 노선마다 가장 많은 끝 덱 셋을 낸다. 덱은 끝 덱으로 가르고, --first면 2-1에 고른 덱으로
가른다. 같은 덱으로 끝난 자리라도 AI와 규칙은 그 덱에 간 까닭이 달라서(선택 효과) 이 표로 등수 차를 덱 몫과 레벨·골드 몫으로 나눌
수는 없다.
실행(probe_heads.py와 같은 PYTHONPATH): python meta/inversion/probe_perdeck.py meta/inversion/probe_rows_best_base.json [--first]
"""
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_heads import BOARDS, at, line

DECKS = ('Chosen Divines', 'Chosen Warlords', 'Chosen Duelists', 'Chosen Cultists', 'Chosen Dusks')


def main(path, first):
    rows = json.load(open(path, encoding='utf-8'))['rows']
    deck = (lambda r: BOARDS[r['curve'][0][4] - 1]['name']) if first else (lambda r: r['deck'])  # 첫 칸은 늘 2-1의 덱 고르기
    print(f'| 덱({"2-1" if first else "끝"}) | 쪽 | 자리 | 등수 | 4-1 | 4-5 | 5-1 | 5-5 | 4단계 레벨 +1 · 남길 골드 50/10/0 | 5단계 같은 것 |')
    for d in DECKS:
        for kind in ('ai', 'rule'):
            rs = [r for r in rows if r['kind'] == kind and deck(r) == d]
            if not rs:
                continue
            cells = []
            for slot in (15, 18, 21, 24):
                pts = [p for p in (at(r['curve'], slot) for r in rs) if p]
                cells.append(f'{statistics.mean(p[1] for p in pts):.2f} / {statistics.mean(p[2] for p in pts):.0f} ({len(pts)})' if pts else '-')
            for lo, hi in ((15, 20), (21, 26)):
                pts = [c for r in rs for c in r['curve'] if lo <= c[0] <= hi]
                lv, fl, n = Counter(c[5] for c in pts), Counter(c[6] for c in pts), len(pts) or 1
                cells.append(f'{lv[1] / n:.0%} · {fl[1] / n:.0%}/{fl[4] / n:.0%}/{fl[5] / n:.0%} ({len(pts)})')
            print(f'| {d} | {kind} | {len(rs)} | {statistics.mean(r["place"] for r in rs):.2f} | ' + ' | '.join(cells) + ' |')
    print('\n| 노선 | 쪽 | 자리 | 많은 끝 덱 셋 |')
    for name in ('7 안정', '빠른 8 리롤', '빠른 8 안 씀', '기다림'):
        for kind in ('ai', 'rule'):
            ds = Counter(r['deck'] for r in rows if r['kind'] == kind and line(r['curve']) == name)
            print(f'| {name} | {kind} | {sum(ds.values())} | ' + ', '.join(f'{k} {v}' for k, v in ds.most_common(3)) + ' |')


if __name__ == '__main__':
    main(sys.argv[1], '--first' in sys.argv[2:])
