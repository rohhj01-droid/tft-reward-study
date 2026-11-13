"""고친 시뮬레이터의 영향 재기 판정(results/README 「엔진 버그를 고친 시뮬레이터의 영향: 미리 정한 판정」, 2026-11-13).
판은 안 돌리고 탐침 기록만 읽는다.

B(시너지·유닛 수 0.3)와 2차의 시드 2~5 신경망(3천 판, 고치기 전 시뮬레이터로 배움)을 같은 판(시드 700000~700399, 같은 자리 뽑기)에서
고치기 전 시뮬레이터(june 65a6fc9)와 고친 시뮬레이터(june fbc238d)로 본래·틀 탐침을 돌린 기록을 판마다 짝짓는다. 판마다 「규칙 평균
등수 − AI 평균 등수」(A/B)를 내고, 학습 몫 L = 본래 − 틀이다(계획 틀 몫 판정과 같은 셈). 네 탐침(고치기 전 본래·틀, 고친 본래·틀)에 다
있는 판만 짝짓는다. 바뀐 양 = 고친 쪽 − 고치기 전 쪽이다.
판정(문턱 ±0.18): 1. 본래 A/B 바뀜(여덟 실행 평균) 2. 학습 몫 바뀜(여덟 실행 평균) 3. 학습 몫의 B − 2차 차 바뀜.
실행(저장소 맨 위에서): python meta/inversion/fix_shift.py results/plan_fix_shift.json
셈 확인: 둘째 인자로 check를 주면 고친 쪽 자리에 고치기 전 기록을 넣는다. 바뀐 양이 모두 0이고, 고치기 전 학습 몫이 계획 틀 몫
판정(results/plan_frame_share.json)과 같아야 한다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
STEM = {'B': 'plan_dense_both', '2차': 'plan_margin_deck'}
SEEDS = (2, 3, 4, 5)
T, Z90 = 0.18, 1.645
NEW = '' if CHECK else 'deadfix_'
record = {'check': CHECK, 'inputs': {}, 'runs': {}}


def probe(path, tag):
    """-> ({판 시드: 규칙 − AI}, {(판, 자리): 2-1 덱}, AI 자리 5-1 시작 레벨 평균, 오류 난 판)"""
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
            {(r['seed'], r['seat']): r['curve'][0][4] for r in ai}, lv51, sorted(e[0] for e in d['errors']))


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def run(cond, s):
    tag = f'{STEM[cond]}_s{s}'
    (b0, d_b0, l_b0, e_b0), (f0, d_f0, l_f0, e_f0) = (probe(f'probe_rows_{p}{tag}_latest.json', tag) for p in ('', 'frame_'))
    (b1, d_b1, l_b1, e_b1), (f1, d_f1, l_f1, e_f1) = (probe(f'probe_rows_{p}{NEW}{tag}_latest.json', tag) for p in ('', 'frame_'))
    g = sorted(set(b0) & set(f0) & set(b1) & set(f1))
    assert all(d_b0[k] == d_f0[k] for k in d_b0 if k[0] in g) and all(d_b1[k] == d_f1[k] for k in d_b1 if k[0] in g), f'{tag}: 2-1 덱이 어긋난다'
    same21 = statistics.mean(d_b0[k] == d_b1[k] for k in d_b0 if k[0] in g)
    return {'dAB': mse([b1[x] - b0[x] for x in g]), 'dL': mse([(b1[x] - f1[x]) - (b0[x] - f0[x]) for x in g]),
            'dF': mse([f1[x] - f0[x] for x in g]), 'AB': (mse([b0[x] for x in g]), mse([b1[x] for x in g])),
            'L': (mse([b0[x] - f0[x] for x in g]), mse([b1[x] - f1[x] for x in g])), 'games': len(g),
            'errors': {'old_base': e_b0, 'old_frame': e_f0, 'new_base': e_b1, 'new_frame': e_f1},
            'level_5_1': {'old': (l_b0, l_f0), 'new': (l_b1, l_f1)}, 'same_2_1_deck': same21}


def pooled(vals, ses):
    """평균과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ √실행 수보다 작으면 그 값을 쓴다(앞 판정들과 같은 식)."""
    n = len(vals)
    return statistics.mean(vals), max((statistics.variance(vals) / n) ** 0.5, statistics.mean(ses) / n ** 0.5)


def cell(subject, m, se):
    lo, hi = m - Z90 * se, m + Z90 * se
    c = (f'고치면 {subject} 거의 안 바뀐다' if abs(m) <= T else f'고치면 {subject} 바뀐다') + (' (경계 걸침)' if lo < -T < hi or lo < T < hi else '')
    return {'mean': m, 'se': se, 'ci90': (lo, hi), 'cell': c}


R = {(c, s): run(c, s) for c in STEM for s in SEEDS}
print(f'## 실행마다 (판별 짝, ± 판 표준오차){" — 셈 확인" if CHECK else ""}')
for (c, s), r in R.items():
    record['runs'][f'{c} s{s}'] = r
    print(f'{c} 시드 {s}: A/B 바뀜 {r["dAB"][0]:+.4f} ± {r["dAB"][1]:.4f}, 학습 몫 바뀜 {r["dL"][0]:+.4f} ± {r["dL"][1]:.4f}, '
          f'틀 A/B 바뀜 {r["dF"][0]:+.4f}, A/B {r["AB"][0][0]:+.4f} → {r["AB"][1][0]:+.4f}, 학습 몫 {r["L"][0][0]:+.4f} → {r["L"][1][0]:+.4f}, '
          f'판 {r["games"]}, 2-1 덱 같음 {r["same_2_1_deck"]:.0%}, 오류 {r["errors"]}')

P = {}
for k in ('dAB', 'dL', 'dF'):
    for c in STEM:
        P[c, k] = pooled([R[c, s][k][0] for s in SEEDS], [R[c, s][k][1] for s in SEEDS])
    P['all', k] = pooled([R[c, s][k][0] for c in STEM for s in SEEDS], [R[c, s][k][1] for c in STEM for s in SEEDS])
for c in STEM:
    P[c, 'L_old'] = pooled([R[c, s]['L'][0][0] for s in SEEDS], [R[c, s]['L'][0][1] for s in SEEDS])
    P[c, 'L_new'] = pooled([R[c, s]['L'][1][0] for s in SEEDS], [R[c, s]['L'][1][1] for s in SEEDS])
record['means'] = {f'{c} {k}': v for (c, k), v in P.items()}
print('\n## 평균 (± 표준오차)')
for c in ('B', '2차', 'all'):
    print(f'{c}: A/B 바뀜 {P[c, "dAB"][0]:+.4f} ± {P[c, "dAB"][1]:.4f}, 학습 몫 바뀜 {P[c, "dL"][0]:+.4f} ± {P[c, "dL"][1]:.4f}, '
          f'틀 A/B 바뀜 {P[c, "dF"][0]:+.4f} ± {P[c, "dF"][1]:.4f}' +
          (f', 학습 몫 {P[c, "L_old"][0]:+.4f} → {P[c, "L_new"][0]:+.4f}' if c != 'all' else ''))

dd = P['B', 'dL'][0] - P['2차', 'dL'][0]
record['verdict'] = [cell('본래 A/B가', *P['all', 'dAB']), cell('학습 몫이', *P['all', 'dL']),
                     cell('학습 몫의 B − 2차 차가', dd, (P['B', 'dL'][1] ** 2 + P['2차', 'dL'][1] ** 2) ** 0.5)]
print('\n## 판정')
for i, (v, what) in enumerate(zip(record['verdict'], ('본래 A/B 바뀜(여덟 실행)', '학습 몫 바뀜(여덟 실행)', '학습 몫 B − 2차 차 바뀜')), 1):
    print(f'{i}. {what} {v["mean"]:+.4f} ± {v["se"]:.4f} (90% {v["ci90"][0]:+.3f}~{v["ci90"][1]:+.3f}) → 「{v["cell"]}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
