"""노선 강제 대조 다시 셈(2026-10-31, 판을 돌리지 않고 diag_line 기록만 읽음).

1. 노선마다 1등·4등 안·8등 비율(강제 자리 대 규칙 자리)과 판마다 짝지은 차 ± 표준오차. 빠른 8의 8등은 4-1 시작 체력 띠로 나눈다.
2. 띠(4-1 시작 체력 세 띠, 덱 세 갈래)마다 세 노선과 규칙 중 평균 등수가 가장 나은 것을 고른 이득을 띠 몫(규칙 자리 기준)으로 더한
   값과, 노선 효과가 없을 때 같은 셈이 얼마나 나오는지(판 안에서 강제 4자리를 무작위로 다시 뽑아 3천 번, 같은 판 번호면 세 변형에
   같은 자리).

실행(저장소 맨 위에서): python meta/inversion/line_risk.py   (기록 폴더를 따로 주려면 첫 인자로)
"""
import json
import os
import statistics
import sys
from collections import Counter

import numpy as np

INV = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
FILES = {'stab7': ['diag_line_rows_stab7.json'], 'fast8': ['diag_line_rows_fast8.json', 'diag_line_rows_fast8_more.json'],
         'stay7': ['diag_line_rows_stay7.json']}
LATE = {'Chosen Dusks', 'Vanguard Mystics', 'Dusk Cultists', 'Chosen Divines', 'Adept Mystics'}  # 설계 10절의 후반 덱 다섯
SLOW = set()
for ln in open(os.path.join(INV, '..', 'tftactics_10.24_2020-11-28.txt'), encoding='utf-8'):
    if ln.strip() and not ln.startswith('#'):
        _, name, style, *_ = [c.strip() for c in ln.split('|')]
        if style == 'Slow Roll':
            SLOW.add(name)


def load(var):
    """-> 정수 배열 [판, 자리, 체력 띠(0: 60 이상, 1: 40~59, 2: 40 미만, -1: 4-1 전 탈락), 덱 갈래(0 후반, 1 느린 리롤, 2 보통), 등수, 강제]."""
    rows = [r for f in FILES[var] for r in json.load(open(os.path.join(INV, f), encoding='utf-8'))['rows']]
    seat, out = Counter(), []
    for r in rows:  # 한 판의 8자리는 자리 순서대로 적혀 있다(diag_line.run)
        c = next((c for c in r['curve'] if c[0] == 15), None)
        out.append((r['game'], seat[r['game']], -1 if c is None else 0 if c[3] >= 60 else 1 if c[3] >= 40 else 2,
                    0 if r['deck'] in LATE else 1 if r['deck'] in SLOW else 2, r['place'], r['forced']))
        seat[r['game']] += 1
    assert set(seat.values()) == {8}
    return np.array(out, dtype=np.int64)


RUNS = {v: load(v) for v in FILES}

print('## 1. 노선마다 1등·4등 안·8등 (강제 대 규칙, 판마다 짝지은 차 ± 표준오차)')
for var, a in RUNS.items():
    f = a[:, 5] == 1
    for name, hit in [('1등', a[:, 4] == 1), ('4등 안', a[:, 4] <= 4), ('8등', a[:, 4] == 8)]:
        d = [hit[(a[:, 0] == g) & f].mean() - hit[(a[:, 0] == g) & ~f].mean() for g in np.unique(a[:, 0])]
        m, s = statistics.mean(d), statistics.stdev(d) / len(d) ** 0.5
        print(f'{var} {name}: {hit[f].mean():.1%} 대 {hit[~f].mean():.1%}, 차 {m * 100:+.2f} ± {s * 100:.2f}%p ({abs(m) / s:.1f}배)')
a = RUNS['fast8']
for b, name in enumerate(['체력 60 이상', '체력 40~59', '체력 40 미만']):
    f, r = (a[:, 2] == b) & (a[:, 5] == 1), (a[:, 2] == b) & (a[:, 5] == 0)
    print(f'fast8 {name}: 8등 {(a[f, 4] == 8).sum()}/{f.sum()} 대 {(a[r, 4] == 8).sum()}/{r.sum()}')


def gain(forced, part):
    """forced: 변형 -> 강제 여부. 띠마다 min(0, 변형별 강제 − 규칙 평균 등수 차)를 띠 몫으로 더해 부호를 바꾼다."""
    best, cnt, n = np.zeros(3), np.zeros(3), 0
    for var, a in RUNS.items():
        band = a[:, 2] if part == 'hp' else np.where(a[:, 2] >= 0, a[:, 3], -1)
        ok, f = band >= 0, forced[var]
        mf = np.bincount(band[ok & f], a[ok & f, 4], 3) / np.bincount(band[ok & f], minlength=3)
        mr = np.bincount(band[ok & ~f], a[ok & ~f, 4], 3) / np.bincount(band[ok & ~f], minlength=3)
        best = np.minimum(best, mf - mr)
        cnt += np.bincount(band[ok & (a[:, 5] == 0)], minlength=3)
        n += int((a[:, 5] == 0).sum())
    return float((cnt / n * -best).sum())


print('\n## 2. 띠마다 가장 나은 노선을 고른 이득(띠 몫으로 더함)과 노선 효과가 없을 때')
rng = np.random.default_rng(0)
G = 1 + max(int(a[:, 0].max()) for a in RUNS.values())
for part, label in [('hp', '체력 세 띠'), ('deck', '덱 세 갈래')]:
    obs = gain({v: a[:, 5] == 1 for v, a in RUNS.items()}, part)
    null = []
    for _ in range(3000):
        m = np.zeros((G, 8), bool)
        np.put_along_axis(m, np.argsort(rng.random((G, 8)), axis=1)[:, :4], True, axis=1)
        null.append(gain({v: m[a[:, 0], a[:, 1]] for v, a in RUNS.items()}, part))
    null = np.array(null)
    print(f'{label}: 이득 {obs:.3f}등, 효과 없을 때 평균 {null.mean():.3f} (95% 위 {np.quantile(null, 0.95):.3f}), 그 이상이 나온 비율 {(null >= obs).mean():.2f}')
