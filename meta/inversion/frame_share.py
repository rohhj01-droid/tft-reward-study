"""계획 틀 몫 판정(results/README 「계획 틀 몫: 미리 정한 판정」, 2026-11-10). 판은 안 돌리고 탐침 기록만 읽는다.

B와 2차의 새 시드 2~5마다 세 탐침(본래, 하이브리드, 틀 = probe_frame.py)에서 판(시드)별 「규칙 평균 등수 − AI 평균 등수」를 내고,
세 탐침에 다 있는 판만 짝짓는다(시뮬레이터가 멈춘 판은 빠진다). 틀 몫 F = 틀 − 하이브리드, 학습 몫 L = 본래 − 틀이고, 둘의 합이
레벨·골드 몫(본래 − 하이브리드)이다.
실행(저장소 맨 위에서): python meta/inversion/frame_share.py results/plan_frame_share.json
셈 확인: 둘째 인자로 probe_rows_hybrid_ 를 주면(틀 탐침 자리에 하이브리드) F = 0이고 L이 시드 반복 2단계 판정의 레벨·골드 몫과 같다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
FRAME = sys.argv[2] if len(sys.argv) > 2 else 'probe_rows_frame_'
INV = 'meta/inversion/'
STEM = {'B': 'plan_dense_both', '2차': 'plan_margin_deck'}
SEEDS = (2, 3, 4, 5)
PHI_CUTS, DF_CUT, Z90 = (1 / 3, 2 / 3), 0.18, 1.645
record = {'frame_prefix': FRAME, 'inputs': {}, 'runs': {}}


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
    (b, db, lb), (h, dh, lh), (f, df, lf) = (probe(f'{p}{tag}_latest.json', tag) for p in ('probe_rows_', 'probe_rows_hybrid_', FRAME))
    games = sorted(set(b) & set(h) & set(f))
    assert all(db[k] == dh[k] == df[k] for k in db if k[0] in games), f'{tag}: 2-1 덱이 어긋난다'
    return {'F': mse([f[x] - h[x] for x in games]), 'L': mse([b[x] - f[x] for x in games]), 'LG': mse([b[x] - h[x] for x in games]),
            'games': len(games), 'dropped': sorted(set(range(700000, 700400)) - set(games)), 'level_5_1': (lb, lh, lf)}


def pooled(cond, key):
    """조건 평균(새 시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다."""
    vals = [R[cond, s][key][0] for s in SEEDS]
    se = max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(R[cond, s][key][1] for s in SEEDS) / len(vals) ** 0.5)
    return statistics.mean(vals), se


R = {(c, s): run(c, s) for c in STEM for s in SEEDS}
print(f'## 실행마다 (틀 탐침 앞머리 {FRAME}, 판별 짝, ± 판 표준오차)')
for (c, s), r in R.items():
    record['runs'][f'{c} s{s}'] = r
    print(f'{c} 시드 {s}: 틀 몫 {r["F"][0]:+.4f} ± {r["F"][1]:.4f}, 학습 몫 {r["L"][0]:+.4f} ± {r["L"][1]:.4f}, 레벨·골드 몫 {r["LG"][0]:+.4f}, '
          f'판 {r["games"]}' + (f' (뺀 판 {r["dropped"]})' if r['dropped'] else '') +
          ', AI 5-1 시작 레벨 본래 / 하이브리드 / 틀 ' + ' / '.join(f'{x:.2f}' for x in r['level_5_1']))

M = {(c, k): pooled(c, k) for c in STEM for k in ('F', 'L', 'LG')}
record['means'] = {f'{c} {k}': v for (c, k), v in M.items()}
print('\n## 조건 평균 (새 시드 넷, ± 표준오차)')
for c in STEM:
    print(f'{c}: 틀 몫 {M[c, "F"][0]:+.4f} ± {M[c, "F"][1]:.4f}, 학습 몫 {M[c, "L"][0]:+.4f} ± {M[c, "L"][1]:.4f}, 레벨·골드 몫 {M[c, "LG"][0]:+.4f}')

print('\n## 판정')
fb, se_b = M['B', 'F']
lg_b = M['B', 'LG'][0]
phi = fb / lg_b
lo, hi = sorted(((fb - Z90 * se_b) / lg_b, (fb + Z90 * se_b) / lg_b))
c1 = ('B의 남은 손해는 대부분 계획 틀 몫이다' if phi >= PHI_CUTS[1] else
      'B의 남은 손해는 대부분 학습 몫이다' if phi <= PHI_CUTS[0] else 'B의 남은 손해는 틀 몫과 학습 몫이 둘 다 크다')
c1 += ' (경계 걸침)' if any(lo < x < hi for x in PHI_CUTS) else ''
dF = fb - M['2차', 'F'][0]
se_d = (se_b ** 2 + M['2차', 'F'][1] ** 2) ** 0.5
d = lg_b - M['2차', 'LG'][0]
c2 = ('B가 2차보다 덜 잃은 몫은 학습 몫에 있다(틀 몫은 비슷하다)' if abs(dF) <= DF_CUT else
      'B가 덜 잃은 몫 가운데 틀 몫 차이가 있다(B가 고른 덱에서 틀이 덜 손해다)' if dF > 0 else
      'B의 학습 몫 이점은 레벨·골드 몫 차보다 크다(B가 고른 덱에서 틀이 더 손해다)')
c2 += ' (경계 걸침)' if any(dF - Z90 * se_d < x < dF + Z90 * se_d for x in (-DF_CUT, DF_CUT)) else ''
record['verdict'] = {'phi': phi, 'phi_90': (lo, hi), 'cell_1': c1, 'dF': dF, 'dF_se': se_d, 'dL': d - dF, 'd': d, 'cell_2': c2}
print(f'1. 틀 몫 비율 = {fb:+.4f} ÷ {lg_b:+.4f} = {phi:.3f} (90% {lo:.3f}~{hi:.3f}) → 「{c1}」')
print(f'2. 틀 몫 차 B − 2차 {dF:+.4f} ± {se_d:.4f} (레벨·골드 몫 차 {d:+.4f}, 학습 몫 차 {d - dF:+.4f}) → 「{c2}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
