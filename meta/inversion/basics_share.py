"""2·3단계 기초 가르치기 판정(results/README 「2·3단계 기초를 끝까지 가르치기: 미리 정한 판정」, 2026-11-14). 판은 안 돌리고 탐침 기록만 읽는다.

두 조건(B = plan_dense_both, 기초 = plan_dense_basics: B에 --margin-keep-before 15만 더함)의 시드 2~5마다 본래·틀 탐침에서 판(시드)별
「규칙 평균 등수 − AI 평균 등수」를 내고, 두 탐침에 다 있는 판만 짝짓는다(시뮬레이터가 멈춘 판은 빠진다).
본래 A/B = 본래 탐침 값의 평균, 학습 몫 L = 본래 − 틀(계획 틀 몫 판정과 같은 셈).
판정 1: 본래 A/B 바뀜 = 기초 − B (문턱 ±0.18). 판정 2: 되찾은 비율 = (기초 L − B L) ÷ (0 − B L) (칸 1/3·2/3).
실행(저장소 맨 위에서): python meta/inversion/basics_share.py results/plan_basics_share.json
셈 확인: 둘째 인자로 check를 주면 기초 자리에 B를 넣는다. 바뀜과 비율이 0이고, B 값이 results/plan_head_split.json의 B와 같아야 한다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
STEM = {'B': 'plan_dense_both', '기초': 'plan_dense_both' if CHECK else 'plan_dense_basics'}
SEEDS = (2, 3, 4, 5)
SLOTS = {9: '3-1', 13: '3-6', 15: '4-1', 21: '5-1'}  # 라운드 시작(level_curve.py와 같다)
THRESHOLD, CUTS, Z90 = 0.18, (1 / 3, 2 / 3), 1.645
record = {'check': CHECK, 'stems': STEM, 'inputs': {}, 'runs': {}}


def probe(path, tag):
    """-> ({판 시드: 규칙 − AI}, {(판, 자리): 2-1 덱}, {라운드: (AI 자리 평균 레벨, 평균 골드)})"""
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
    curve = {k: tuple(statistics.mean(c[i] for r in ai for c in r['curve'] if c[0] == k) for i in (1, 2)) for k in SLOTS}
    return ({s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()},
            {(r['seed'], r['seat']): r['curve'][0][4] for r in ai}, curve)


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def run(cond, s):
    tag = f'{STEM[cond]}_s{s}'
    (b, db, cb), (f, df, cf) = (probe(f'{p}{tag}_latest.json', tag) for p in ('probe_rows_', 'probe_rows_frame_'))
    games = sorted(set(b) & set(f))
    assert all(db[k] == df[k] for k in db if k[0] in games), f'{tag}: 2-1 덱이 어긋난다'
    return {'AB': mse([b[x] for x in games]), 'L': mse([b[x] - f[x] for x in games]), 'games': len(games),
            'dropped': sorted(set(range(700000, 700400)) - set(games)), 'curve': {'본래': cb, '틀': cf}}


def pooled(cond, key):
    """조건 평균(시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다(앞 판정들과 같은 식)."""
    vals = [R[cond][s][key][0] for s in SEEDS]
    se = max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(R[cond][s][key][1] for s in SEEDS) / len(vals) ** 0.5)
    return statistics.mean(vals), se


R = {c: {s: run(c, s) for s in SEEDS} for c in STEM}
M = {c: {k: pooled(c, k) for k in ('AB', 'L')} for c in STEM}
record['runs'] = {f'{c} s{s}': r for c in R for s, r in R[c].items()}
record['means'] = M
print('## 실행마다 (판별 짝, ± 판 표준오차)')
for c in R:
    for s, r in R[c].items():
        print(f'{c} 시드 {s}: 본래 A/B {r["AB"][0]:+.4f} ± {r["AB"][1]:.4f}, 학습 몫 {r["L"][0]:+.4f} ± {r["L"][1]:.4f}, 판 {r["games"]}'
              + (f' (뺀 판 {r["dropped"]})' if r['dropped'] else ''))
        for k, cv in r['curve'].items():
            print(f'    {k}: ' + ', '.join(f'{SLOTS[t]} 레벨 {lv:.2f} 골드 {gd:.1f}' for t, (lv, gd) in cv.items()))
print('\n## 조건 평균 (시드 넷, ± 표준오차)')
for c in M:
    print(f'{c}: 본래 A/B {M[c]["AB"][0]:+.4f} ± {M[c]["AB"][1]:.4f}, 학습 몫 {M[c]["L"][0]:+.4f} ± {M[c]["L"][1]:.4f}')

d_ab = M['기초']['AB'][0] - M['B']['AB'][0]
se_ab = (M['기초']['AB'][1] ** 2 + M['B']['AB'][1] ** 2) ** 0.5
lo, hi = d_ab - Z90 * se_ab, d_ab + Z90 * se_ab
cell = ('2·3단계 기초를 끝까지 가르치면 B보다 낫다' if d_ab >= THRESHOLD else '2·3단계 기초를 끝까지 가르치면 B보다 못하다'
        if d_ab <= -THRESHOLD else '2·3단계 기초를 끝까지 가르쳐도 B와 비슷하다')
v1 = {'num': d_ab, 'se': se_ab, 'ci90': (lo, hi),
      'cell': cell + (' (경계 걸침)' if any(lo < x < hi for x in (-THRESHOLD, THRESHOLD)) else '')}
den = -M['B']['L'][0]
num = M['기초']['L'][0] - M['B']['L'][0]
se_l = (M['기초']['L'][1] ** 2 + M['B']['L'][1] ** 2) ** 0.5
ratio = num / den
rlo, rhi = sorted(((num - Z90 * se_l) / den, (num + Z90 * se_l) / den))
cell = ('2·3단계 기초를 끝까지 가르치면 B의 학습 몫을 대부분 되찾는다' if ratio >= CUTS[1] else
        '2·3단계 기초를 끝까지 가르쳐도 B의 학습 몫을 거의 못 되찾는다' if ratio <= CUTS[0] else
        '2·3단계 기초를 끝까지 가르치면 B의 학습 몫을 일부 되찾는다')
v2 = {'num': num, 'se': se_l, 'den': den, 'ratio': ratio, 'ratio_90': (rlo, rhi),
      'cell': cell + (' (경계 걸침)' if any(rlo < x < rhi for x in CUTS) else '')}
record['verdict'] = [v1, v2]
print('\n## 판정')
print(f'1. 본래 A/B 바뀜(기초 − B) = {d_ab:+.4f} ± {se_ab:.4f} (90% {lo:+.3f}~{hi:+.3f}) → 「{v1["cell"]}」')
print(f'2. 되찾은 비율 = {num:+.4f} ± {se_l:.4f} ÷ {den:.4f} = {ratio:.3f} (90% {rlo:.3f}~{rhi:.3f}) → 「{v2["cell"]}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
