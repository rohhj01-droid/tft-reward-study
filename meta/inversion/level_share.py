"""학습 몫 가르기 판정(results/README 「학습 몫 가르기: 미리 정한 판정」, 2026-11-10). 판은 안 돌리고 탐침 기록만 읽는다.

B와 2차의 새 시드 2~5마다 세 탐침(본래, 레벨만 = probe_level.py, 틀 = probe_frame.py)에서 판(시드)별 「규칙 평균 등수 − AI 평균
등수」를 내고, 세 탐침에 다 있는 판만 짝짓는다(시뮬레이터가 멈춘 판은 빠진다). 레벨 몫 = 본래 − 레벨만, 남길 골드 몫 = 레벨만 − 틀
이고, 둘의 합이 학습 몫(본래 − 틀)이다.
실행(저장소 맨 위에서): python meta/inversion/level_share.py results/plan_level_share.json
셈 확인: 둘째 인자로 probe_rows_frame_ 를 주면 레벨 몫 = 학습 몫·남길 골드 몫 = 0이고, probe_rows_ 를 주면 레벨 몫 = 0이다. 학습
몫은 어느 때나 틀 몫 판정(results/plan_frame_share.json)의 학습 몫과 같다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
LEVEL = sys.argv[2] if len(sys.argv) > 2 else 'probe_rows_level_'
INV = 'meta/inversion/'
STEM = {'B': 'plan_dense_both', '2차': 'plan_margin_deck'}
SEEDS = (2, 3, 4, 5)
CUTS, Z90 = (1 / 3, 2 / 3), 1.645
record = {'level_prefix': LEVEL, 'inputs': {}, 'runs': {}}


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
    (b, db, lb), (v, dv, lv), (f, df, lf) = (probe(f'{p}{tag}_latest.json', tag) for p in ('probe_rows_', LEVEL, 'probe_rows_frame_'))
    games = sorted(set(b) & set(v) & set(f))
    assert all(db[k] == dv[k] == df[k] for k in db if k[0] in games), f'{tag}: 2-1 덱이 어긋난다'
    return {'Llv': mse([b[x] - v[x] for x in games]), 'Lfl': mse([v[x] - f[x] for x in games]), 'L': mse([b[x] - f[x] for x in games]),
            'games': len(games), 'dropped': sorted(set(range(700000, 700400)) - set(games)), 'level_5_1': (lb, lv, lf)}


def pooled(cond, key):
    """조건 평균(새 시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다."""
    vals = [R[cond, s][key][0] for s in SEEDS]
    se = max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(R[cond, s][key][1] for s in SEEDS) / len(vals) ** 0.5)
    return statistics.mean(vals), se


def judge(num, se, den, labels):
    """비율 num ÷ den과 90% 구간((num ± 1.645 × se) ÷ den). labels = (2/3 이상, 1/3 이하, 그 사이)의 문장."""
    ratio = num / den
    lo, hi = sorted(((num - Z90 * se) / den, (num + Z90 * se) / den))
    cell = labels[0] if ratio >= CUTS[1] else labels[1] if ratio <= CUTS[0] else labels[2]
    return ratio, (lo, hi), cell + (' (경계 걸침)' if any(lo < x < hi for x in CUTS) else '')


R = {(c, s): run(c, s) for c in STEM for s in SEEDS}
print(f'## 실행마다 (레벨만 탐침 앞머리 {LEVEL}, 판별 짝, ± 판 표준오차)')
for (c, s), r in R.items():
    record['runs'][f'{c} s{s}'] = r
    print(f'{c} 시드 {s}: 레벨 몫 {r["Llv"][0]:+.4f} ± {r["Llv"][1]:.4f}, 남길 골드 몫 {r["Lfl"][0]:+.4f} ± {r["Lfl"][1]:.4f}, '
          f'학습 몫 {r["L"][0]:+.4f}, 판 {r["games"]}' + (f' (뺀 판 {r["dropped"]})' if r['dropped'] else '') +
          ', AI 5-1 시작 레벨 본래 / 레벨만 / 틀 ' + ' / '.join(f'{x:.2f}' for x in r['level_5_1']))

M = {(c, k): pooled(c, k) for c in STEM for k in ('Llv', 'Lfl', 'L')}
record['means'] = {f'{c} {k}': v for (c, k), v in M.items()}
print('\n## 조건 평균 (새 시드 넷, ± 표준오차)')
for c in STEM:
    print(f'{c}: 레벨 몫 {M[c, "Llv"][0]:+.4f} ± {M[c, "Llv"][1]:.4f}, 남길 골드 몫 {M[c, "Lfl"][0]:+.4f} ± {M[c, "Lfl"][1]:.4f}, '
          f'학습 몫 {M[c, "L"][0]:+.4f}')

print('\n## 판정')
lv_b, se_b = M['B', 'Llv']
l_b = M['B', 'L'][0]
psi, psi90, c1 = judge(lv_b, se_b, l_b, ('B의 학습 몫은 대부분 레벨 고르기 몫이다', 'B의 학습 몫은 대부분 남길 골드 고르기 몫이다',
                                         'B의 학습 몫은 레벨 고르기 몫과 남길 골드 고르기 몫이 둘 다 크다'))
d_lv = lv_b - M['2차', 'Llv'][0]
se_d = (se_b ** 2 + M['2차', 'Llv'][1] ** 2) ** 0.5
d_l = l_b - M['2차', 'L'][0]
chi, chi90, c2 = judge(d_lv, se_d, d_l, ('B가 2차보다 덜 잃은 학습 몫은 대부분 레벨 고르기에서 왔다',
                                         'B가 2차보다 덜 잃은 학습 몫은 대부분 남길 골드 고르기에서 왔다',
                                         'B가 2차보다 덜 잃은 학습 몫은 레벨 고르기와 남길 골드 고르기 둘 다에서 왔다'))
record['verdict'] = {'psi': psi, 'psi_90': psi90, 'cell_1': c1, 'd_level': d_lv, 'd_level_se': se_d, 'd_learning': d_l,
                     'chi': chi, 'chi_90': chi90, 'cell_2': c2}
print(f'1. 레벨 몫 비율 = {lv_b:+.4f} ÷ {l_b:+.4f} = {psi:.3f} (90% {psi90[0]:.3f}~{psi90[1]:.3f}) → 「{c1}」')
print(f'2. 레벨 몫 차 B − 2차 {d_lv:+.4f} ± {se_d:.4f} ÷ 학습 몫 차 {d_l:+.4f} = {chi:.3f} (90% {chi90[0]:.3f}~{chi90[1]:.3f}) → 「{c2}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
