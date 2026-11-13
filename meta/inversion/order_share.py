"""학습 몫 가르기 반대 순서 (라)와 레벨 손해 단계 가르기 (마)의 판정(results/README 「학습 몫 가르기 반대 순서와 레벨 손해 단계
가르기: 미리 정한 판정」, 2026-11-13). 판은 안 돌리고 탐침 기록만 읽는다.

B의 시드 2~5마다 다섯 탐침(본래, 레벨만 = probe_level.py, 틀 = probe_frame.py, 골드만 = probe_gold.py, 4-1 전 레벨 = probe_early.py)에서
판(시드)별 「규칙 평균 등수 − AI 평균 등수」를 내고, 다섯 탐침에 다 있는 판만 짝짓는다(시뮬레이터가 멈춘 판은 빠진다).
- 학습 몫 L = 본래 − 틀. 레벨을 먼저 고치는 순서(앞 판정): 레벨 몫 = 본래 − 레벨만, 남길 골드 몫 = 레벨만 − 틀.
- 남길 골드를 먼저 고치는 순서(라): 남길 골드 몫 G = 본래 − 골드만, 레벨 몫 = 골드만 − 틀. 얽힌 몫 I = G − (레벨만 − 틀).
- 단계 가르기(마): 2·3단계 레벨 몫 E = 본래 − 4-1 전 레벨, 4단계부터 레벨 몫 = 4-1 전 레벨 − 레벨만. 둘의 합이 레벨 몫이다.
실행(저장소 맨 위에서): python meta/inversion/order_share.py results/plan_order_share.json
셈 확인: 셋째·넷째 인자로 골드만·4-1 전 레벨 탐침 자리에 쓸 앞머리를 준다. probe_rows_ probe_rows_level_ 이면 G = 0·E = 레벨 몫이고,
probe_rows_frame_ probe_rows_ 이면 G = L·E = 0이다. 어느 때나 L·레벨 몫·남길 골드 몫이 results/plan_level_share.json의 B와 같다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
GOLD, EARLY = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ('probe_rows_gold_', 'probe_rows_early_')
INV = 'meta/inversion/'
STEM, SEEDS = 'plan_dense_both', (2, 3, 4, 5)
PROBES = {'b': 'probe_rows_', 'v': 'probe_rows_level_', 'f': 'probe_rows_frame_', 'g': GOLD, 'e': EARLY}
SLOTS = {9: '3-1', 13: '3-6', 15: '4-1', 21: '5-1'}  # 라운드 시작(level_curve.py와 같다)
Z90 = 1.645
record = {'gold_prefix': GOLD, 'early_prefix': EARLY, 'inputs': {}, 'runs': {}}


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


def run(s):
    tag = f'{STEM}_s{s}'
    P = {k: probe(f'{p}{tag}_latest.json', tag) for k, p in PROBES.items()}
    b, v, f, g, e = (P[k][0] for k in 'bvfge')
    games = sorted(set(b) & set(v) & set(f) & set(g) & set(e))
    d21 = [P[k][1] for k in 'bvfge']
    assert all(len({d[x] for d in d21}) == 1 for x in d21[0] if x[0] in games), f'{tag}: 2-1 덱이 어긋난다'
    return {'L': mse([b[x] - f[x] for x in games]), 'Llv': mse([b[x] - v[x] for x in games]), 'Lfl': mse([v[x] - f[x] for x in games]),
            'G': mse([b[x] - g[x] for x in games]), 'Glv': mse([g[x] - f[x] for x in games]),
            'I': mse([(b[x] - g[x]) - (v[x] - f[x]) for x in games]),
            'E': mse([b[x] - e[x] for x in games]), 'La': mse([e[x] - v[x] for x in games]),
            'games': len(games), 'dropped': sorted(set(range(700000, 700400)) - set(games)),
            'curve': {k: P[k][2] for k in 'bvfge'}}


def pooled(key):
    """평균(시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다(앞 판정들과 같은 식)."""
    vals = [R[s][key][0] for s in SEEDS]
    se = max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(R[s][key][1] for s in SEEDS) / len(vals) ** 0.5)
    return statistics.mean(vals), se


def judge(num, se, den, cuts, labels):
    """비율 num ÷ den과 90% 구간((num ± 1.645 × se) ÷ den, 분모는 고정). cuts = (아래, 위), labels = (위 이상, 아래 이하, 그 사이)."""
    ratio = num / den
    lo, hi = sorted(((num - Z90 * se) / den, (num + Z90 * se) / den))
    cell = labels[0] if ratio >= cuts[1] else labels[1] if ratio <= cuts[0] else labels[2]
    return {'num': num, 'se': se, 'den': den, 'ratio': ratio, 'ratio_90': (lo, hi),
            'cell': cell + (' (경계 걸침)' if any(lo < x < hi for x in cuts) else '')}


R = {s: run(s) for s in SEEDS}
print(f'## 실행마다 (골드만 {GOLD}, 4-1 전 레벨 {EARLY}, 판별 짝, ± 판 표준오차)')
for s, r in R.items():
    record['runs'][f'B s{s}'] = r
    print(f'B 시드 {s}: 학습 몫 {r["L"][0]:+.4f}, 레벨 먼저 {r["Llv"][0]:+.4f} / {r["Lfl"][0]:+.4f}, 골드 먼저 {r["G"][0]:+.4f} ± {r["G"][1]:.4f} / '
          f'{r["Glv"][0]:+.4f}, 얽힌 몫 {r["I"][0]:+.4f} ± {r["I"][1]:.4f}, 2·3단계 {r["E"][0]:+.4f} ± {r["E"][1]:.4f} / 4단계부터 {r["La"][0]:+.4f}, '
          f'판 {r["games"]}' + (f' (뺀 판 {r["dropped"]})' if r['dropped'] else ''))
    for k, name in zip('bvfge', ('본래', '레벨만', '틀', '골드만', '4-1 전 레벨')):
        print(f'    {name}: ' + ', '.join(f'{SLOTS[t]} 레벨 {lv:.2f} 골드 {gd:.1f}' for t, (lv, gd) in r['curve'][k].items()))

M = {k: pooled(k) for k in ('L', 'Llv', 'Lfl', 'G', 'Glv', 'I', 'E', 'La')}
record['means'] = M
print('\n## 평균 (시드 넷, ± 표준오차)')
print(', '.join(f'{k} {m:+.4f} ± {se:.4f}' for k, (m, se) in M.items()))

L, LLV = M['L'][0], M['Llv'][0]
V = [judge(*M['G'], L, (1 / 3, 2 / 3), ('남길 골드만 규칙처럼 고쳐도 B의 학습 몫을 대부분 되찾는다',
                                          '남길 골드만 규칙처럼 고쳐서는 B의 학습 몫을 조금만 되찾는다',
                                          '남길 골드만 규칙처럼 고치면 B의 학습 몫을 절반쯤 되찾는다')),
     judge(*M['I'], L, (-1 / 3, 1 / 3), ('두 결정이 얽힌 몫이 크다: 남길 골드는 먼저 고칠 때 더 많이 되찾는다',
                                           '두 결정이 얽힌 몫이 크다: 남길 골드는 레벨 뒤에 고칠 때 더 많이 되찾는다',
                                           '두 결정이 얽힌 몫은 작다: 어느 쪽을 먼저 고쳐도 몫이 비슷하다')),
     judge(*M['E'], LLV, (1 / 3, 2 / 3), ('B의 레벨 손해는 대부분 2·3단계에서 난다', 'B의 레벨 손해는 대부분 4단계부터 난다',
                                           'B의 레벨 손해는 2·3단계와 4단계부터 둘 다에서 난다'))]
record['verdict'] = V
print('\n## 판정')
for i, (v, what) in enumerate(zip(V, ('남길 골드 먼저 고친 몫 ÷ 학습 몫', '얽힌 몫 ÷ 학습 몫', '2·3단계 레벨 몫 ÷ 레벨 몫')), 1):
    print(f'{i}. {what} = {v["num"]:+.4f} ± {v["se"]:.4f} ÷ {v["den"]:+.4f} = {v["ratio"]:.3f} '
          f'(90% {v["ratio_90"][0]:.3f}~{v["ratio_90"][1]:.3f}) → 「{v["cell"]}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
