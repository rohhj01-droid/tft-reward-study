"""시너지 갈래와 유닛 수 갈래 떼어 배우기 판정(results/README 「시너지 갈래와 유닛 수 갈래 떼어 배우기: 미리 정한 판정」,
2026-11-10). 판은 안 돌리고 탐침 기록만 읽는다.

네 조건(2차 = 보조 갈래 없음, B = 시너지·유닛 수 0.3, 시너지만, 유닛 수만)의 새 시드 2~5마다 세 탐침(본래, 하이브리드, 틀)에서
판(시드)별 「규칙 평균 등수 − AI 평균 등수」를 내고, 세 탐침에 다 있는 판만 짝짓는다(시뮬레이터가 멈춘 판은 빠진다). 학습 몫
L = 본래 − 틀, 틀 몫 F = 틀 − 하이브리드, 레벨·골드 몫 LG = 본래 − 하이브리드다(계획 틀 몫 판정과 같은 셈).
판정은 학습 몫으로 한다: 갈래 비율 = (그 조건 L − 2차 L) ÷ (B L − 2차 L).
실행(저장소 맨 위에서): python meta/inversion/head_split.py results/plan_head_split.json
셈 확인: 둘째 인자로 check를 주면 시너지만 자리에 B를, 유닛 수만 자리에 2차를 넣는다. 비율이 1과 0이어야 하고, B·2차 값은 계획 틀 몫
판정(results/plan_frame_share.json)과 같아야 한다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
STEM = {'2차': 'plan_margin_deck', 'B': 'plan_dense_both',
        '시너지만': 'plan_dense_both' if CHECK else 'plan_dense_synergy',
        '유닛 수만': 'plan_margin_deck' if CHECK else 'plan_dense_units'}
HEAD = {'시너지만': '시너지 갈래', '유닛 수만': '유닛 수 갈래'}
SEEDS = (2, 3, 4, 5)
CUTS, Z90 = (1 / 3, 2 / 3), 1.645
record = {'check': CHECK, 'stems': STEM, 'inputs': {}, 'runs': {}}


def probe(path, tag):
    """-> ({판 시드: 규칙 − AI}, {(판, 자리): 2-1 덱}, AI 자리 5-1 시작 레벨 평균)"""
    raw = open(INV + path, 'rb').read()
    record['inputs'][path] = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    assert d['games'] == 400 and d['weights'] == d['saved_weights'] and d['net'] == f'{tag}_latest.pt', path
    by = {}
    for r in d['rows']:
        by.setdefault(r['seed'], {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert set(by) | {e[0] for e in d['errors']} == set(range(700000, 700400)), f'{path}: 시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values()), path
    ai = [r for r in d['rows'] if r['kind'] == 'ai']
    lv51 = statistics.mean(c[1] for r in ai for c in r['curve'] if c[0] == 21)
    return ({s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()},
            {(r['seed'], r['seat']): r['curve'][0][4] for r in ai}, lv51)


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def run(cond, s):
    tag = f'{STEM[cond]}_s{s}'
    (b, db, lb), (h, dh, lh), (f, df, lf) = (probe(f'{p}{tag}_latest.json', tag)
                                             for p in ('probe_rows_', 'probe_rows_hybrid_', 'probe_rows_frame_'))
    games = sorted(set(b) & set(h) & set(f))
    assert all(db[k] == dh[k] == df[k] for k in db if k[0] in games), f'{tag}: 2-1 덱이 어긋난다'
    return {'F': mse([f[x] - h[x] for x in games]), 'L': mse([b[x] - f[x] for x in games]), 'LG': mse([b[x] - h[x] for x in games]),
            'AB': mse([b[x] for x in games]), 'games': len(games), 'dropped': sorted(set(range(700000, 700400)) - set(games)),
            'level_5_1': (lb, lh, lf)}


def pooled(cond, key):
    """조건 평균(새 시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다."""
    vals = [R[cond, s][key][0] for s in SEEDS]
    se = max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(R[cond, s][key][1] for s in SEEDS) / len(vals) ** 0.5)
    return statistics.mean(vals), se


R = {(c, s): run(c, s) for c in STEM for s in SEEDS}
print(f'## 실행마다 (판별 짝, ± 판 표준오차){" — 셈 확인" if CHECK else ""}')
for (c, s), r in R.items():
    record['runs'][f'{c} s{s}'] = r
    print(f'{c} 시드 {s}: 학습 몫 {r["L"][0]:+.4f} ± {r["L"][1]:.4f}, 틀 몫 {r["F"][0]:+.4f}, 레벨·골드 몫 {r["LG"][0]:+.4f}, '
          f'본래 A/B {r["AB"][0]:+.4f}, 판 {r["games"]}' + (f' (뺀 판 {r["dropped"]})' if r['dropped'] else '') +
          ', AI 5-1 시작 레벨 본래 / 하이브리드 / 틀 ' + ' / '.join(f'{x:.2f}' for x in r['level_5_1']))

M = {(c, k): pooled(c, k) for c in STEM for k in ('L', 'F', 'LG', 'AB')}
record['means'] = {f'{c} {k}': v for (c, k), v in M.items()}
print('\n## 조건 평균 (새 시드 넷, ± 표준오차)')
for c in STEM:
    print(f'{c}: 학습 몫 {M[c, "L"][0]:+.4f} ± {M[c, "L"][1]:.4f}, 틀 몫 {M[c, "F"][0]:+.4f}, 레벨·골드 몫 {M[c, "LG"][0]:+.4f}, '
          f'본래 A/B {M[c, "AB"][0]:+.4f}')

print('\n## 판정')
l2, se2 = M['2차', 'L']
den = M['B', 'L'][0] - l2
record['verdict'] = {'den': den}
for i, c in enumerate(HEAD, 1):
    num = M[c, 'L'][0] - l2
    se = (M[c, 'L'][1] ** 2 + se2 ** 2) ** 0.5
    ratio = num / den
    lo, hi = sorted(((num - Z90 * se) / den, (num + Z90 * se) / den))
    h = HEAD[c]
    cell = (f'{h} 혼자로 B만큼 줄인다' if ratio >= CUTS[1] else f'{h} 혼자로는 거의 못 줄인다' if ratio <= CUTS[0] else
            f'{h} 혼자로 일부 줄인다') + (' (경계 걸침)' if any(lo < x < hi for x in CUTS) else '')
    record['verdict'][c] = {'num': num, 'se': se, 'ratio': ratio, 'ratio_90': (lo, hi), 'cell': cell}
    print(f'{i}. {h} 비율 = ({c} − 2차 {num:+.4f} ± {se:.4f}) ÷ (B − 2차 {den:+.4f}) = {ratio:.3f} (90% {lo:.3f}~{hi:.3f}) → 「{cell}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
