"""기초의 남은 학습 몫 단계 가르기 판정(results/README 「기초의 남은 학습 몫 단계 가르기: 미리 정한 판정」, 2026-11-16). 판은 안 돌리고
탐침 기록만 읽는다.

기초(plan_dense_basics) 시드 2~5의 본래·틀·4-1부터 탐침(probe_late.py)에서 판(시드)별 「규칙 평균 등수 − AI 평균 등수」를 내고, 세
탐침에 다 있는 판만 짝짓는다. 학습 몫 L = 본래 − 틀, 4-1부터의 몫 S = 본래 − 4-1부터 탐침, 4-1 전 몫 E = 4-1부터 탐침 − 틀(S + E = L).
판정: 비율 σ = S ÷ L(칸 1/3·2/3). 비율의 표준오차는 판마다 S − σ × L을 내서 앞 판정들과 같은 식으로 구한 값을 |L|로 나눈다.
흐름(판정 없음): 판마다 본래와 틀 탐침의 여덟 자리 기록이 4-1 시작(라운드 15)까지 모두 같은지 본다. 같은 판은 4-1부터 탐침이 틀
탐침과 같은 판이 되므로, 그 판의 본래 − 틀은 모두 4-1부터의 몫이다. B도 견줄 값으로 함께 낸다.
실행(저장소 맨 위에서): python meta/inversion/late_share.py results/plan_late_share.json
흐름만: 둘째 인자로 flow를 주면 4-1부터 탐침 없이 흐름 표만 낸다.
셈 확인: 둘째 인자로 check-frame을 주면 4-1부터 탐침 자리에 틀 탐침을 넣는다(S = L, E = 0, σ = 1, 구간 폭 0). check-base면 본래 탐침을
넣는다(S = 0, σ = 0, 구간 폭 0). 두 경우 모두 L이 results/plan_basics_share.json의 기초 학습 몫과 같아야 한다.
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else ''
LATE = {'': 'probe_rows_late_', 'flow': None, 'check-frame': 'probe_rows_frame_', 'check-base': 'probe_rows_'}[MODE]
INV = 'meta/inversion/'
STEM = {'기초': 'plan_dense_basics', 'B': 'plan_dense_both'}
SEEDS = (2, 3, 4, 5)
LATE_ROUND = 15  # 4-1(probe_late.py와 같다)
CUTS, Z90 = (1 / 3, 2 / 3), 1.645
record = {'mode': MODE, 'inputs': {}}


def probe(prefix, tag):
    """-> ({판 시드: 규칙 − AI}, {(판, 자리): (자리 종류, 등수, 라운드별 기록)})"""
    path = f'{prefix}{tag}_latest.json'
    raw = open(INV + path, 'rb').read()
    record['inputs'][path] = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    assert d['games'] == 400 and d['weights'] == d['saved_weights'] and d['net'] == f'{tag}_latest.pt', path
    by = {}
    for r in d['rows']:
        by.setdefault(r['seed'], {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert set(by) | {e[0] for e in d['errors']} == set(range(700000, 700400)), f'{path}: 시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values()), path
    return ({s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()},
            {(r['seed'], r['seat']): (r['kind'], r['place'], r['curve']) for r in d['rows']})


def head(rows, g):
    """판 g의 여덟 자리 기록 가운데 4-1 시작(라운드 15)까지. 규칙 자리의 4-1 기록에서는 계획 칸 둘(레벨 단계, 남길 골드 번호)을 뺀다:
    규칙 기록기는 그 라운드에 한 일을 보고 이 두 칸을 적으므로, 4-1 기록의 이 칸에는 4-1에 한 일이 들어간다(README 「넣는 조건 고침」)."""
    return [[c[:5] + c[7:] if kind == 'rule' and c[0] == LATE_ROUND else c for c in curve if c[0] <= LATE_ROUND]
            for kind, _, curve in (rows[g, i] for i in range(8))]


def split_round(x, y):
    """4-1 시작까지의 두 기록이 처음 달라지는 라운드(같으면 None). 그 앞 라운드에 한 일이 달랐다는 뜻이다."""
    if x == y:
        return None
    return min(next((a[0] for a, b in zip(p, q) if a != b), LATE_ROUND) for p, q in zip(x, y) if p != q)


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def pooled(runs, key):
    """조건 평균(시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다(앞 판정들과 같은 식)."""
    vals = [r[key][0] for r in runs]
    return statistics.mean(vals), max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(r[key][1] for r in runs) / len(vals) ** 0.5)


# ---------- 흐름: 본래와 틀 탐침이 4-1 시작까지 같은 판 ----------
P = {(c, s): {k: probe(p, f'{STEM[c]}_s{s}') for k, p in (('본래', 'probe_rows_'), ('틀', 'probe_rows_frame_'))} for c in STEM for s in SEEDS}
FLOW, SAME = {}, {}
print('## 흐름: 본래와 틀 탐침의 여덟 자리 기록이 4-1 시작까지 같은 판 (± 판 표준오차)')
for (c, s), p in P.items():
    (b, br), (f, fr) = p['본래'], p['틀']
    games = sorted(set(b) & set(f))
    at = {g: split_round(head(br, g), head(fr, g)) for g in games}
    assert all(r is None or r > 3 for r in at.values()), f'{c} s{s}: 2-1 시작부터 다르다'
    SAME[c, s] = {g for g in games if at[g] is None}
    FLOW[c, s] = {'games': len(games), 'same': len(SAME[c, s]),
                  'stage2': sum(r is not None and r <= 9 for r in at.values()),  # 3-1 시작(라운드 9) 기록까지에서 갈림 = 2단계에 한 일이 다름
                  'stage3': sum(r is not None and r > 9 for r in at.values()),
                  'L_same': mse([(b[g] - f[g]) * (g in SAME[c, s]) for g in games]),
                  'L_diff': mse([(b[g] - f[g]) * (g not in SAME[c, s]) for g in games])}
    x = FLOW[c, s]
    print(f'{c} 시드 {s}: 판 {x["games"]}, 같은 판 {x["same"]}, 2단계에서 갈린 판 {x["stage2"]}, 3단계에서 갈린 판 {x["stage3"]}, '
          f'학습 몫 가운데 같은 판이 낸 양 {x["L_same"][0]:+.4f} ± {x["L_same"][1]:.4f}, 갈린 판이 낸 양 {x["L_diff"][0]:+.4f} ± {x["L_diff"][1]:.4f}')
record['flow'] = {f'{c} s{s}': x for (c, s), x in FLOW.items()}
record['flow_means'] = {c: {k: pooled([FLOW[c, s] for s in SEEDS], k) for k in ('L_same', 'L_diff')} for c in STEM}
for c in STEM:
    m = record['flow_means'][c]
    print(f'{c} 평균: 같은 판 {statistics.mean(FLOW[c, s]["same"] / FLOW[c, s]["games"] for s in SEEDS):.1%}, '
          f'같은 판이 낸 양 {m["L_same"][0]:+.4f} ± {m["L_same"][1]:.4f}, 갈린 판이 낸 양 {m["L_diff"][0]:+.4f} ± {m["L_diff"][1]:.4f}')

# ---------- 판정: 4-1부터의 몫 ----------
if LATE:
    R = []
    print('\n## 기초 실행마다 (판별 짝, ± 판 표준오차)')
    for s in SEEDS:
        (b, br), (f, fr) = P['기초', s]['본래'], P['기초', s]['틀']
        l, lr = probe(LATE, f'{STEM["기초"]}_s{s}')
        games = sorted(set(b) & set(f) & set(l))
        assert MODE or all(head(br, g) == head(lr, g) for g in games), f's{s}: 4-1부터 탐침이 4-1 전에 본래 탐침과 다르다'  # 셈 확인 때는 안 본다
        same = [g for g in games if g in SAME['기초', s]]
        R.append({'games': len(games), 'dropped': sorted(set(range(700000, 700400)) - set(games)),
                  'same': len(same), 'same_equal_frame': sum(all(lr[g, i] == fr[g, i] for i in range(8)) for g in same),
                  'AB': mse([b[g] for g in games]), 'L': mse([b[g] - f[g] for g in games]),
                  'S': mse([b[g] - l[g] for g in games]), 'E': mse([l[g] - f[g] for g in games]),
                  'pairs': [(b[g] - l[g], b[g] - f[g]) for g in games]})
        x = R[-1]
        print(f'시드 {s}: 본래 A/B {x["AB"][0]:+.4f}, 학습 몫 {x["L"][0]:+.4f} ± {x["L"][1]:.4f}, 4-1부터의 몫 {x["S"][0]:+.4f} ± {x["S"][1]:.4f}, '
              f'4-1 전 몫 {x["E"][0]:+.4f} ± {x["E"][1]:.4f}, 판 {x["games"]}' + (f' (뺀 판 {x["dropped"]})' if x['dropped'] else '')
              + f', 흐름이 같은 판 {x["same"]} 가운데 틀 탐침과 끝까지 같은 판 {x["same_equal_frame"]}')
    M = {k: pooled(R, k) for k in ('L', 'S', 'E')}
    assert M['L'][0] < 0, '학습 몫이 0 이상이라 가를 것이 없다'
    ratio = M['S'][0] / M['L'][0]
    for x in R:
        x['resid'] = mse([sv - ratio * lv for sv, lv in x.pop('pairs')])
    se = pooled(R, 'resid')[1] / -M['L'][0]
    lo, hi = ratio - Z90 * se, ratio + Z90 * se
    cell = ('기초의 남은 학습 몫은 대부분 4-1부터의 판단에서 난다' if ratio >= CUTS[1] else
            '기초의 남은 학습 몫은 대부분 4-1 전 판단에서 난다' if ratio <= CUTS[0] else
            '기초의 남은 학습 몫은 4-1 전과 4-1부터에 걸쳐 있다')
    record['runs'] = {f'기초 s{s}': x for s, x in zip(SEEDS, R)}
    record['means'] = M
    record['verdict'] = {'ratio': ratio, 'se': se, 'ci90': (lo, hi), 'cell': cell + (' (경계 걸침)' if any(lo < x < hi for x in CUTS) else '')}
    print('\n## 기초 평균 (시드 넷, ± 표준오차)')
    print(', '.join(f'{n} {M[k][0]:+.4f} ± {M[k][1]:.4f}' for k, n in (('L', '학습 몫'), ('S', '4-1부터의 몫'), ('E', '4-1 전 몫'))))
    print('\n## 판정')
    print(f'비율 σ = {M["S"][0]:+.4f} ÷ {M["L"][0]:+.4f} = {ratio:.3f} ± {se:.3f} (90% {lo:.3f}~{hi:.3f}) → 「{record["verdict"]["cell"]}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
