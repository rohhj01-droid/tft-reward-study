"""돈 쓰는 때까지 가르친 AI의 판정 밖 읽을거리(results/README 「돈 쓰는 때까지 가르친 AI: 결과」, 2026-11-18). 판은 안 돌리고 탐침 기록만
읽는다. 미리 적어 둔 「판정 없이 함께 적는 것」 가운데 AI 자리의 레벨·골드와 끝 덱, 그리고 대조 탐침이 판정 값을 얼마나 옮겼는지를 낸다.
실행(저장소 맨 위에서, teach_share.py 다음에): python meta/inversion/teach_read.py results/plan_teach_read.json
"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

INV = 'meta/inversion/'
SEEDS = (2, 3, 4, 5)
SLOTS = {9: '3-1', 13: '3-6', 15: '4-1', 21: '5-1'}  # 라운드 시작(basics_share.py와 같다)


def rows(name):
    return json.load(open(INV + name, encoding='utf-8'))['rows']


def diff(rs):
    """-> {판 시드: 규칙 자리 평균 등수 − AI 자리 평균 등수}"""
    by = defaultdict(lambda: {'ai': [], 'rule': []})
    for r in rs:
        by[r['seed']][r['kind']].append(r['place'])
    return {s: st.mean(v['rule']) - st.mean(v['ai']) for s, v in by.items()}


def curve(rs):
    """-> {칸: [평균 레벨, 평균 골드]} (그 칸 시작 때 살아 있던 자리)"""
    return {n: [st.mean(c[i] for r in rs for c in r['curve'] if c[0] == k) for i in (1, 2)] for k, n in SLOTS.items()}


def decks(rs, top=None):
    """-> 끝 덱 [덱, 몫, 그 덱의 평균 등수](몫이 큰 차례, top을 주면 그만큼)와 갈아타기 평균"""
    n = Counter(r['deck'] for r in rs)
    return {'top': [[d, c / len(rs), st.mean(r['place'] for r in rs if r['deck'] == d)] for d, c in n.most_common(top)],
            'switches': st.mean(r['switches'] for r in rs)}


base = {s: rows(f'probe_rows_plan_teach_s{s}_latest.json') for s in SEEDS}
frame = {s: rows(f'probe_rows_frame_plan_teach_s{s}_latest.json') for s in SEEDS}
ctrl_rows = rows('probe_rows_rule8_teach.json')
of = lambda runs, kind: {s: [r for r in rs if r['kind'] == kind] for s, rs in runs.items()}
groups = {'AI 본래': of(base, 'ai'), 'AI 틀': of(frame, 'ai'), '규칙 자리(본래 탐침)': of(base, 'rule')}
out = {'levels': {}, 'decks': {}}
for name, g in groups.items():
    per = {s: curve(rs) for s, rs in g.items()}
    out['levels'][name] = {n: {'level': st.mean(per[s][n][0] for s in SEEDS), 'gold': st.mean(per[s][n][1] for s in SEEDS),
                               'level_range': [min(per[s][n][0] for s in SEEDS), max(per[s][n][0] for s in SEEDS)]} for n in SLOTS.values()}
    out['decks'][name] = {'all': decks([r for rs in g.values() for r in rs]), 'by_seed': {f's{s}': decks(rs, 3) for s, rs in g.items()}}
out['decks']['대조 탐침(여덟 자리 모두 규칙)'] = {'all': decks(ctrl_rows)}

c, b = diff(ctrl_rows), {s: diff(rs) for s, rs in base.items()}
games = sorted(set(c).intersection(*b.values()))
m = [st.mean(b[s][g] for s in SEEDS) for g in games]
x = [c[g] for g in games]
share = json.load(open('results/plan_teach_share.json', encoding='utf-8'))
fixed = st.mean(m) - st.mean(x)
assert math.isclose(fixed, share['verdict']['fixed'], abs_tol=1e-9), '판정 값과 다르다'
beta = st.covariance(m, x) / st.variance(x)
se_c, between = st.stdev(x) / len(x) ** 0.5, st.stdev(st.mean(b[s][g] - c[g] for g in games) for s in SEEDS) / 2
out['control'] = {'raw_mean': st.mean(m), 'control_mean': st.mean(x), 'control_se': se_c, 'fixed': fixed,
                  'corr_each_run': {f's{s}': st.correlation([b[s][g] for g in games], x) for s in SEEDS},
                  'corr_four_run_mean': st.correlation(m, x), 'beta': beta, 'adjusted': st.mean(m) - beta * st.mean(x),
                  'se_between_runs': between, 'se_with_control_noise': math.hypot(between, se_c),
                  'ratio_with_control_noise': fixed / math.hypot(between, se_c), 'ratio_raw': st.mean(m) / between}
json.dump(out, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
