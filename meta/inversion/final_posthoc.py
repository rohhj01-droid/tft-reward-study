"""실제 판의 마지막 대전 붙이기: 결과를 본 뒤에 한 셈(미리 정한 읽기가 아니다). results/README 「실제 판의 마지막 대전을
시뮬레이터에서 붙이기: 결과」의 사후 표를 다시 만든다.

    python meta/inversion/final_posthoc.py <뽑아 둔 대전 파일> <실행 기록>      (저장소 맨 위에서, PYTHONPATH는 final_fight.py와 같게)

구간은 모두 대전을 다시 뽑는 부트스트랩 1,000번(시드 0)이다.
"""
import json
import sys

import numpy as np

sys.path.insert(0, 'meta/inversion')
import final_fight as ff  # noqa: E402

pairs = json.load(open(sys.argv[1], encoding='utf-8'))
rec = json.load(open(sys.argv[2], encoding='utf-8'))
rows = ff.rows_of([pairs['pairs'][k] for k in rec['used']], rec['won'], rec['n'])
n = len(rows)


def pc(x):
    return f'{100 * x:.1f}%'


def interval(diff):
    """대전별 차의 평균과 95% 구간(%p)."""
    diff = np.asarray(diff, float)
    m = diff[np.random.RandomState(0).randint(0, len(diff), (1000, len(diff)))].mean(axis=1)
    return f'{100 * diff.mean():+.1f}%p [{100 * np.percentile(m, 2.5):+.1f}, {100 * np.percentile(m, 97.5):+.1f}]'


# 1. 시뮬레이터와 보드 값이 같은 쪽을 미나
both = [r for r in rows if r['p'] != 0.5 and r['value'] != 0]
agree = [r for r in both if (r['p'] > 0.5) == (r['value'] > 0)]
dis = [r for r in both if (r['p'] > 0.5) != (r['value'] > 0)]
print(f'1. 둘 다 한쪽을 미는 대전 {len(both):,}개: 같은 쪽 {len(agree):,}개({pc(len(agree) / len(both))}), 그때 맞힌 몫 '
      f'{pc(np.mean([r["p"] > 0.5 for r in agree]))}. 다른 쪽 {len(dis):,}개, 그때 시뮬레이터가 맞힌 몫 {pc(np.mean([r["p"] > 0.5 for r in dis]))}')

# 2. 보드 값이 큰 쪽이 실제 1등인 몫을, 그 쪽의 시뮬레이터 승률 칸으로
print('2. 보드 값이 큰 쪽의 시뮬레이터 승률 | 대전 수 | 그 쪽이 실제 1등인 몫')
for name, lo, hi in (('0.25 미만', 0, 0.25), ('0.25부터 0.5 미만', 0.25, 0.5), ('0.5', 0.5, 0.5001), ('0.5 넘고 0.75 미만', 0.5001, 0.75),
                     ('0.75부터', 0.75, 1.01)):
    g = [r for r in rows if r['value'] != 0 and lo <= (r['p'] if r['value'] > 0 else 1 - r['p']) < hi]
    print(f'   | {name} | {len(g):,} | {pc(np.mean([r["value"] > 0 for r in g]))} |')


# 3. 합치면 더 맞히나: 절편 없는 로지스틱(1등 쪽 - 2등 쪽의 차만 쓴다). 반으로 나눠 한쪽에서 맞추고 다른 쪽에서 센다
def fit(X):
    b = np.zeros(X.shape[1])
    for _ in range(50):  # 뉴턴법
        s = 1 / (1 + np.exp(-X @ b))
        b = b + np.linalg.solve((X * (s * (1 - s))[:, None]).T @ X + 1e-6 * np.eye(X.shape[1]), X.T @ (1 - s))
    return b


def hits(cols):
    """대전별로 맞혔나(1·0.5·0). 대전 순서 그대로."""
    X = np.array([[r[c] - 0.5 if c == 'p' else r[c] for c in cols] for r in rows], float)
    X = X / X.std(axis=0)
    order = np.random.RandomState(0).permutation(n)
    out = np.zeros(n)
    for train, test in ((order[: n // 2], order[n // 2:]), (order[n // 2:], order[: n // 2])):
        score = X[test] @ fit(X[train])
        out[test] = np.where(score > 0, 1.0, np.where(score == 0, 0.5, 0.0))
    return out


H = {name: hits(cols) for name, cols in (('보드 값', ['value']), ('시뮬레이터', ['p']), ('세 어림', ['value', 'level', 'items']),
                                         ('시뮬레이터 + 보드 값', ['p', 'value']), ('시뮬레이터 + 세 어림', ['p', 'value', 'level', 'items']))}
print('3. 나눠 잰 맞힌 몫: ' + ', '.join(f'{k} {pc(v.mean())}' for k, v in H.items()))
print('   시뮬레이터 + 보드 값 - 보드 값:', interval(H['시뮬레이터 + 보드 값'] - H['보드 값']))
print('   시뮬레이터 + 세 어림 - 세 어림:', interval(H['시뮬레이터 + 세 어림'] - H['세 어림']))

# 4. 계열 표와 레벨 표의 차에 구간
print('4. 계열 | 대전 수 | 실제 1등인 몫 | 시뮬레이터 승률 | 차')
table = []
for f in sorted({f for r in rows for f in r['fam']}):
    d = [((1.0, r['p']) if r['fam'][0] == f else (0.0, 1 - r['p'])) for r in rows if (r['fam'][0] == f) != (r['fam'][1] == f)]
    if len(d) >= 100:
        table.append((len(d), f, np.mean([x for x, _ in d]), np.mean([s for _, s in d]), interval([s - x for x, s in d])))
for count, f, real, sim, diff in sorted(table, reverse=True):
    print(f'   | {f} | {count:,} | {pc(real)} | {pc(sim)} | {diff} |')
print('   레벨이 높은 쪽(시뮬레이터 - 실제):', interval([(r['p'] if r['level'] > 0 else 1 - r['p']) - float(r['level'] > 0) for r in rows if r['level']]))

# 5. 레벨이 같은 대전과 다른 대전, 시뮬레이터가 12번 모두 한쪽으로 본 대전
for name, g in (('레벨이 같은', [r for r in rows if r['level'] == 0]), ('레벨이 다른', [r for r in rows if r['level'] != 0])):
    sim = [1.0 if r['p'] > 0.5 else 0.5 if r['p'] == 0.5 else 0.0 for r in g]
    val = [1.0 if r['value'] > 0 else 0.5 if r['value'] == 0 else 0.0 for r in g]
    print(f'5. {name} 대전 {len(g):,}개: 시뮬레이터 {pc(np.mean(sim))}, 보드 값 {pc(np.mean(val))}, 차 {interval(np.array(sim) - np.array(val))}')
full = [r for r in rows if r['p'] in (0.0, 1.0)]
print(f'   12번 모두 한쪽이 이긴 대전 {len(full):,}개({pc(len(full) / n)}): 그 쪽이 실제 1등인 몫 {pc(np.mean([r["p"] == 1.0 for r in full]))}')
