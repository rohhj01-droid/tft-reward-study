"""진행 보상 실험 판정(results/README 「진행 보상 실험」 절의 미리 정한 판정). 판은 안 돌리고 평가 결과 JSON만 읽는다.

A/B = 탐침 400판에서 판(시드)마다 낸 「규칙 평균 등수 − AI 평균 등수」의 평균, 표준오차 = 표본표준편차 ÷ √판 수.
c = 3천 판 점검(200판)과 탐침을 표준오차 역제곱으로 무게 준 평균, S = (2000판 점검 + 2500판 점검 + c) ÷ 3.

실행(저장소 맨 위에서): python meta/inversion/dense_verdict.py . results/plan_dense_verdict.json
첫 인자는 meta/inversion(탐침 기록)과 results(일치율·곡선)가 있는 저장소 폴더, 둘째 인자는 판별 차와 판정을 적을 JSON이다.
"""
import json
import os
import statistics
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = sys.argv[2] if len(sys.argv) > 2 else None
INV = os.path.join(ROOT, 'meta', 'inversion')
RES = os.path.join(ROOT, 'results')


def per_seed(path):
    d = json.load(open(path, encoding='utf-8'))
    assert not d['errors'], d['errors']
    by = {}
    for r in d['rows']:
        by.setdefault(int(r['seed']), {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert sorted(by) == list(range(700000, 700000 + d['games'])), '시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values())
    return {s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()}, d


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def band(x):
    return '−0.2 위' if x > -0.2 else '−0.6 위·−0.2 이하' if x > -0.6 else '−0.6 이하'


def cell(ab, level, floor):
    off = level < 0.9 or floor < 0.9
    if ab > -0.2:
        return '성공' if off else '규칙 곁 버팀: 이번 질문에 답 못 함'
    return ('부분' if ab > -0.6 else '실패') + ('·벗어남' if off else '·규칙 곁')


def curve(tag):
    c = json.load(open(os.path.join(RES, f'{tag}.json'), encoding='utf-8'))['curve']
    return {row['games']: (row['diff'], row['se']) for row in c}


probes = {
    'A': 'probe_rows_plan_dense_value_s1_latest.json', 'B': 'probe_rows_plan_dense_both_s1_latest.json',
    '2차(재탐침)': 'probe_rows_margin_deck_s1_latest_920e0be.json',
    'A best(2000판)': 'probe_rows_plan_dense_value_s1_best.json', 'B best(500판)': 'probe_rows_plan_dense_both_s1_best.json'}
seeds, record = {}, {'probes': {}, 'paired': {}, 'verdict': {}}
print('## 탐침 A/B (판 400개, 반올림 전)')
for k, f in probes.items():
    s, d = per_seed(os.path.join(INV, f))
    seeds[k] = s
    m, se = mse(list(s.values()))
    print(f'{k}: {m:+.5f} ± {se:.5f}  (신경망 {d["net"]}, 가중치 {d["weights"]})')
    record['probes'][k] = {'file': f, 'net': d['net'], 'weights': d['weights'], 'games': d['games'], 'mean': m, 'se': se,
                           'per_seed': [s[x] for x in sorted(s)]}

print('\n## 같은 시드끼리 짝지은 차')
for a, b in (('A', '2차(재탐침)'), ('B', '2차(재탐침)'), ('A', 'B')):
    m, se = mse([seeds[a][s] - seeds[b][s] for s in seeds[a]])
    print(f'{a} − {b}: {m:+.4f} ± {se:.4f} (z {m / se:+.2f})')
    record['paired'][f'{a} − {b}'] = {'mean': m, 'se': se}

old = os.path.join(RES, 'plan_eval_ab_margin_deck_s1_latest.json')
if os.path.exists(old):
    o = json.load(open(old, encoding='utf-8'))
    new = sorted(seeds['2차(재탐침)'].values())
    print(f'\n## 2차 재탐침 대 옛 hra.evaluate ab: 옛 평균 {statistics.mean(o["per_game"]):+.5f}, '
          f'판별 차를 정렬하면 같은가: {sorted(o["per_game"]) == new}')

print('\n## 일치율 50판 (덱 / 레벨 / 남길 골드 / 셋 다, 판단 수)')
agree = {}
for tag in ('plan_dense_value_s1', 'plan_dense_both_s1'):
    for g in (500, 1000, 1500, 2000, 2500, 3000):
        d = json.load(open(os.path.join(RES, f'plan_eval_agree_{tag}_g{g}.json'), encoding='utf-8'))
        assert not d['errors'] and d['decisions'] == 9479
        agree[tag, g] = d
        print(f'{tag} g{g}: {d["deck"]:.4f} / {d["level"]:.4f} / {d["floor"]:.4f} / {d["all"]:.4f}')

print('\n## 판정')
for name, tag, key in (('A (판정)', 'plan_dense_value_s1', 'A'), ('B (설명만)', 'plan_dense_both_s1', 'B')):
    ab, se = mse(list(seeds[key].values()))
    g3 = agree[tag, 3000]
    cv = curve(tag)
    (c3, s3), (c2, _), (c25, _) = cv[3000], cv[2000], cv[2500]
    c = (c3 / s3 ** 2 + ab / se ** 2) / (1 / s3 ** 2 + 1 / se ** 2)
    S = (c2 + c25 + c) / 3
    main = cell(ab, g3['level'], g3['floor'])
    flag = band(S) != band(ab)
    print(f'{name}: A/B {ab:+.4f} ± {se:.4f} → {band(ab)}; 레벨 {g3["level"]:.4f}, 남길 골드 {g3["floor"]:.4f} → 칸 「{main}」')
    print(f'   c {c:+.4f}, S ({c2:+.4f} + {c25:+.4f} + {c:+.4f}) ÷ 3 = {S:+.4f} → {band(S)}' + (' → 「판정 불안정」' if flag else ''))
    record['verdict'][name] = {'ab': ab, 'se': se, 'level': g3['level'], 'floor': g3['floor'], 'cell': main, 'c': c, 'S': S,
                               'unstable': flag}

print('\n## 점검 곡선(여백 0 구간 1000~3000판): 저장본 사이 흔들림과 같은 판 수끼리 2차와 짝지은 차')
G = (1000, 1500, 2000, 2500, 3000)
curves = {'A': curve('plan_dense_value_s1'), 'B': curve('plan_dense_both_s1'), '2차': curve('plan_margin_deck_s1')}
record['curve'] = {}
for k, cv in curves.items():
    x, se2 = [cv[g][0] for g in G], statistics.mean(cv[g][1] ** 2 for g in G)
    near = statistics.mean((x[i + 1] - x[i]) ** 2 - cv[G[i]][1] ** 2 - cv[G[i + 1]][1] ** 2 for i in range(4)) / 2
    drift = [max(v, 0) ** 0.5 for v in (statistics.pvariance(x) - se2, statistics.variance(x) - se2, near)]
    print(f'{k}: 평균 {statistics.mean(x):+.4f}, 흔들림(모분산 / 표본분산 / 이웃 차) ' + ' / '.join(f'{v:.3f}' for v in drift))
    record['curve'][k] = {'mean': statistics.mean(x), 'drift': drift}
    if k != '2차':
        d = [cv[g][0] - curves['2차'][g][0] for g in G]
        m, s = statistics.mean(d), statistics.stdev(d) / len(d) ** 0.5
        print(f'   {k} − 2차: {" ".join(f"{v:+.4f}" for v in d)}, 평균 {m:+.4f}, 다섯 차의 흩어짐으로 센 표준오차 {s:.4f} ({m / s:.2f}배)')
        record['curve'][k].update(paired=d, paired_mean=m, paired_se=s)
six = {c: [json.load(open(os.path.join(RES, f'plan_eval_ab_{c}_s{s}_latest.json'), encoding='utf-8'))['diff'] for s in (1, 2, 3)]
       for c in ('none', 'both')}
dev = [v - statistics.mean(vs) for vs in six.values() for v in vs]
record['seed_sd'] = (sum(e * e for e in dev) / (len(dev) - len(six))) ** 0.5
print(f'본 학습 여섯 실행(옛 실행기, 여백 늘 1)의 마지막 A/B를 설정 안에서 묶은 표준편차 {record["seed_sd"]:.3f}')

if OUT:
    json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
