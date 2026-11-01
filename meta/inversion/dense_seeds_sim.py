"""진행 보상 실험 시드 반복 판정(results/README 「시드 반복: 미리 정한 판정」)의 오판·검정력 모의실험(2026-11-01). 판은 안 돌린다. 한 프로세스, 20만 번.
실행(저장소 맨 위에서): python meta/inversion/dense_seeds_sim.py
실행 값 y = 참값 + 실행 사이 흔들림 tau·z + 탐침 잡음 p·z' (p = 0.105). 시드 1 관측: 2차 -1.108, A -0.663, B -0.135.
(가) 새 시드(2·3)만: d = B평균 - 2차평균, s = sqrt(세 조건 표본분산 평균) (자유도 3), 바닥 0.105, 비율 d/s.
"""
import sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
rng = np.random.default_rng(20261101)
N, P, FLOOR = 200_000, 0.105, 0.105
T3, T2, T9_05, T9_025, T3_025 = 2.353, 2.920, 1.833, 2.262, 3.182
OBS = {'N': -1.108, 'A': -0.663, 'B': -0.135}


def runs(mu, tau, k):
    """조건 하나의 새 실행 k개 (N, k)"""
    return mu + rng.standard_normal((N, k)) * np.sqrt(tau ** 2 + P ** 2)


def case_ga(dB, dA=0.0, tauN=0.47, tauA=None, tauB=None, k=2):
    tauA = tauN if tauA is None else tauA
    tauB = tauN if tauB is None else tauB
    yN, yA, yB = runs(0, tauN, k), runs(dA, tauA, k), runs(dB, tauB, k)
    s2 = (yN.var(1, ddof=1) + yA.var(1, ddof=1) + yB.var(1, ddof=1)) / 3
    s = np.maximum(np.sqrt(s2), FLOOR)
    se = s * np.sqrt(2 / k)
    d = yB.mean(1) - yN.mean(1)
    dA_ = yA.mean(1) - yN.mean(1)
    return d, dA_, se, yB, yN, yA, s


def cells(d, ratio, thr=T3):
    conf = ratio > thr
    amb = ~conf & (d > 0.30)
    small = ~conf & (d > 0) & (d <= 0.30)
    none = ~conf & (d <= 0)
    return conf, amb, small, none


def pct(x):
    return f'{100 * np.mean(x):5.1f}'


print('== (가) 주 판정: 확정(비율>2.353) / 애매(차>0.30) / 작음(0<차<=0.30) / 방향 없음(차<=0), %')
for tau in (0.2, 0.47, 0.7, 0.9):
    row = []
    for eff in (0.0, 0.49, 0.97):
        d, _, se, *_ = case_ga(eff, tauN=tau)
        c = cells(d, d / se)
        row.append(f'효과 {eff}: ' + '·'.join(pct(x) for x in c))
    print(f'흔들림 {tau}: ' + ' | '.join(row))

print('\n== (가) 흔들림이 조건마다 다를 때 (2차 0.20, A 0.55, B 0.35) / B만 두 배(2차·A 0.35, B 0.70)')
for lab, kw in (('다름', dict(tauN=0.2, tauA=0.55, tauB=0.35)), ('B 두 배', dict(tauN=0.35, tauA=0.35, tauB=0.70))):
    out = []
    for eff in (0.0, 0.49, 0.97):
        d, _, se, *_ = case_ga(eff, **kw)
        out.append(f'효과 {eff}: 확정 {pct(d / se > T3)}')
    print(lab + ': ' + ', '.join(out))

print('\n== (가) 고정 순서: B 확정일 때만 A를 같은 문턱으로. 둘 다 효과 없음 → 하나라도 확정 %; 둘 다 시드 1 크기(A 0.445, B 0.97) → A 확정 %')
for tau in (0.2, 0.47, 0.7):
    d, dA, se, *_ = case_ga(0.0, 0.0, tauN=tau)
    anyc = (d / se > T3)  # 고정 순서면 A는 B 확정일 때만 → 하나라도 = B 확정
    sep = (d / se > T3) | (dA / se > T3)
    d2, dA2, se2, *_ = case_ga(0.97, 0.445, tauN=tau)
    aconf = (d2 / se2 > T3) & (dA2 / se2 > T3)
    print(f'흔들림 {tau}: 고정 순서 {pct(anyc)}, 따로 {pct(sep)}; A 확정(고정 순서) {pct(aconf)}')

print('\n== (가) 부 주장 하한: B 새 시드 평균 - 2.353 × s/√2 > -0.30. 참 B 레벨·골드 몫별 주장 확률 %')
for tau in (0.2, 0.47, 0.7):
    out = []
    for muB in (-0.135, -0.30, -0.5):
        d, _, se, yB, yN, yA, s = case_ga(0.0, tauN=tau)
        yB = yB + muB  # 효과 0으로 뽑은 B를 참값 muB로 옮김
        lb = yB.mean(1) - T3 * s / np.sqrt(2)
        out.append(f'{muB}: {pct(lb > -0.30)}')
    print(f'흔들림 {tau}: ' + ', '.join(out))

print('\n== (가) 두 단계: 1단계 애매면 시드 4·5를 더해 새 시드 넷으로 다시 봄 (자유도 9). 전체 확정 %')
for tau in (0.2, 0.47, 0.7):
    out = []
    for thr1, thr2, lab in ((T3, T9_05, '2.353→1.833'), (T3, T9_025, '2.353→2.262'), (T3_025, T9_025, '3.182→2.262')):
        res = []
        for eff in (0.0, 0.97):
            yN, yA, yB = runs(0, tau, 4), runs(0, tau, 4), runs(eff, tau, 4)
            def stage(k):
                s2 = (yN[:, :k].var(1, ddof=1) + yA[:, :k].var(1, ddof=1) + yB[:, :k].var(1, ddof=1)) / 3
                s = np.maximum(np.sqrt(s2), FLOOR)
                d = yB[:, :k].mean(1) - yN[:, :k].mean(1)
                return d, d / (s * np.sqrt(2 / k))
            d1, r1 = stage(2)
            c1 = r1 > thr1
            amb = ~c1 & (d1 > 0.30)
            _, r2 = stage(4)
            tot = c1 | (amb & (r2 > thr2))
            res.append(f'효과 {eff}: 1단계 {pct(c1)} 전체 {pct(tot)}')
        out.append(lab + ' [' + '; '.join(res) + ']')
    print(f'흔들림 {tau}: ' + ' || '.join(out))

print('\n== (나) 2차는 시드 1뿐: 「B 새 평균 - 2차 시드 1 < 0.30」 확률 % (시드 1 관측 조건부: 2차 시드 1 오차 | 관측 차)')
for tau in (0.2, 0.47, 0.7):
    v = tau ** 2 + P ** 2
    out = []
    for eff in (0.0, 0.49, 0.97):
        D = eff - (OBS['B'] - OBS['N'])  # e_N1 - e_B1
        eN1 = D / 2 + rng.standard_normal(N) * np.sqrt(v / 2)
        newB = eff + rng.standard_normal(N) * np.sqrt(v / 2)  # 새 B 두 시드 평균(2차 참값 기준)
        diff = newB - eN1
        t_naive = diff / np.sqrt(v)
        out.append(f'효과 {eff}: <0.30 {pct(diff < 0.30)}, 평균 {diff.mean():+.2f}, z>1.645 {pct(t_naive > 1.645)}')
    print(f'흔들림 {tau}: ' + ' | '.join(out))

print('\n== (나) 부 주장 하한: s를 A·B 새 실행 넷으로(자유도 2), B 새 평균 - 2.920 × s/√2 > -0.30. 참 B별 %')
for tau in (0.2, 0.47, 0.7):
    out = []
    for muB in (-0.135, -0.30):
        yA, yB = runs(0, tau, 2), runs(muB, tau, 2)
        s = np.maximum(np.sqrt((yA.var(1, ddof=1) + yB.var(1, ddof=1)) / 2), FLOOR)
        out.append(f'{muB}: {pct(yB.mean(1) - T2 * s / np.sqrt(2) > -0.30)}')
    print(f'흔들림 {tau}: ' + ', '.join(out))

print('\n== 확정된 경우만 본 새 시드 차의 평균 (참 0.97 / 0.49)')
for tau in (0.2, 0.47, 0.7):
    out = []
    for eff in (0.97, 0.49):
        d, _, se, *_ = case_ga(eff, tauN=tau)
        m = d[d / se > T3]
        out.append(f'참 {eff}: {m.mean():.2f}')
    print(f'흔들림 {tau}: ' + ', '.join(out))
