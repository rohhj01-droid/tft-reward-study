"""밸류덱의 4단계 보드 기록을 읽는다(results/README 「밸류덱의 4단계 보드: 미리 정한 읽기」, 2026-11-24). 판정 없음, 판은 안 돌린다.

읽는 것: meta/inversion/board4_rows.json(meta/inversion/board4.py, 시드 790000~790399). 먼저 그 자리 기록이 hp3 대조
(meta/inversion/hp3_none.json)와 판마다 같은지, 대전 기록이 자리 곡선의 체력과 맞는지 본다.

자리의 덱 갈래는 4-1에 든 덱(deck15)으로 밸류덱(late)·느린 리롤 덱(slow)·보통 덱(normal)이다(hra.spend_lesson.group, 나눔 표와 같다).
보드 잣대 다섯: 보드 유닛 수, 보드 값(유닛마다 비용 × 3^(별 - 1)), 2성 이상 유닛 수, 보드 유닛이 든 아이템 수, 켜진 특성 단계의 합
(시뮬레이터가 대전 직전에 센 값). 비용이 0인 소환 유닛(아지르의 모래 병사)은 유닛으로 세지 않는다.
4단계 대전(4-1, 4-2, 4-3, 4-5, 4-6)에서 유령 대전과 비김을 뺀 대전마다 「파랑이 이겼나」를 두 쪽 차로 맞춘다(로지스틱 회귀).
  틀 0: 상수(파랑 쪽) + 밸류덱 차 + 느린 리롤 덱 차(각 쪽이 그 갈래면 1, 보통 덱이 기준)
  틀 1: 틀 0 + 보드 잣대 다섯의 차
설명된 몫 = 1 - (틀 1의 밸류덱 계수) / (틀 0의 밸류덱 계수). 판을 다시 뽑는 부트스트랩(200번, 난수 0)으로 95% 구간을 낸다.
실행(저장소 맨 위에서, june을 PYTHONPATH에): python meta/inversion/board4_read.py results/board4_read.json
셈 확인: python meta/inversion/board4_read.py selfcheck  (답을 아는 가짜 대전으로 회귀와 설명된 몫을 본다)
"""
import hashlib
import json
import sys
from collections import defaultdict

import numpy as np

SEED0, GAMES = 790000, 400
ENV = {'actions_per_turn': 30, 'textbook': {'spend': 'era', 'lose_5': False}}
STAGE4 = (15, 16, 17, 18, 19)  # 4-1, 4-2, 4-3, 4-5, 4-6
SHOW = {13: '3-6', 15: '4-1', 16: '4-2', 17: '4-3', 18: '4-5', 19: '4-6', 21: '5-1'}
FEATURES = ('units', 'worth', 'two_star', 'items', 'tiers')
BOOT, BOOT_SEED = 200, 0
IN, REF = 'meta/inversion/board4_rows.json', 'meta/inversion/hp3_none.json'


def features(f, i, cost, deck_units):
    b = [u for u in f['board'][i] if cost[u[0]]]  # 아지르의 모래 병사처럼 비용이 0인 소환 유닛은 뺀다
    return {'units': len(b), 'worth': sum(cost[n] * 3 ** (s - 1) for n, s, _, _ in b), 'two_star': sum(s >= 2 for _, s, _, _ in b),
            'items': sum(len(it) for _, _, it, _ in b), 'tiers': sum(f['tiers'][i].values()),
            'deck_units': sum(n in deck_units.get(f['deck'][i], ()) for n, _, _, _ in b),
            'four': sum(cost[n] == 4 for n, _, _, _ in b), 'four2': sum(cost[n] == 4 and s >= 2 for n, s, _, _ in b)}


def fit(X, y, iters=50):
    """로지스틱 회귀(뉴턴법). 계수를 돌려준다."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        step = np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (y - p))  # 아주 작은 값: 빈 갈래가 있어도 풀린다
        w += step
        if np.abs(step).max() < 1e-10:
            break
    return w


def design(rows):
    """rows: (판 번호, 파랑 갈래, 빨강 갈래, 파랑 잣대, 빨강 잣대, 파랑이 이겼나) -> 틀 0·틀 1의 X와 y."""
    g = lambda a, b, k: (a == k) - (b == k)
    x0 = np.array([[1.0, g(a, b, 'late'), g(a, b, 'slow')] for _, a, b, _, _, _ in rows])
    x1 = np.hstack([x0, np.array([[fa[k] - fb[k] for k in FEATURES] for _, _, _, fa, fb, _ in rows], float)])
    return x0, x1, np.array([w for *_, w in rows], float)


def explained(rows):
    x0, x1, y = design(rows)
    w0, w1 = fit(x0, y), fit(x1, y)
    return w0, w1, 1 - w1[1] / w0[1]


def model(rows, boot=BOOT, seed=BOOT_SEED):
    w0, w1, share = explained(rows)
    by = defaultdict(list)
    for r in rows:
        by[r[0]].append(r)
    keys = sorted(by)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(boot):
        pick = rng.integers(0, len(keys), len(keys))
        b0, b1, s = explained([r for k in pick for r in by[keys[k]]])
        bs.append((b0[1], b1[1], s))
    bs = np.array(bs)
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    # 밸류덱과 보통 덱이 맞붙은 대전에서 잣대 차의 평균 × 틀 1 계수 = 그 잣대가 맡은 몫(로그 오즈)
    vn = [(fa, fb) if a == 'late' else (fb, fa) for _, a, b, fa, fb, _ in rows if {a, b} == {'late', 'normal'}]
    gap = {k: float(np.mean([v[k] - n[k] for v, n in vn])) for k in FEATURES}
    return {'fights': len(rows), 'late_coef_0': [float(w0[1]), float(lo[0]), float(hi[0])],
            'late_coef_1': [float(w1[1]), float(lo[1]), float(hi[1])], 'explained': [float(share), float(lo[2]), float(hi[2])],
            'slow_coef_0': float(w0[2]), 'slow_coef_1': float(w1[2]), 'blue_side': float(w0[0]),
            'feature_coef': dict(zip(FEATURES, map(float, w1[3:]))), 'late_vs_normal_fights': len(vn),
            'late_minus_normal': gap, 'part': {k: float(w1[3 + i] * gap[k]) for i, k in enumerate(FEATURES)}}


def reading(m):
    """미리 정한 읽기(README)."""
    c0, s = m['late_coef_0'], m['explained']
    if not c0[2] < 0:
        return '밸류덱이 4단계 맞대결에서 더 진다고 말할 수 없다(읽기 없음)'
    if s[0] >= 2 / 3 and s[1] > 1 / 3:
        return '대부분 잰 보드 잣대로 설명된다'
    if s[0] <= 1 / 3 and s[2] < 2 / 3:
        return '같은 잣대에서도 밸류덱이 더 진다'
    return '둘 다이거나 가르지 못한다'


def main(out):
    from Simulator.stats import COST
    from hra.spend_lesson import group
    from meta.inversion.board4 import consistent
    from meta.lobby import BOARDS
    deck_units = {b['name']: set(b['units']) for b in BOARDS}
    raw = open(IN, 'rb').read()
    d = json.loads(raw)
    assert d['kind'] == 'board4' and d['seed0'] == SEED0 and d['games_asked'] == GAMES and d['record'] == [9, 24]
    assert {'actions_per_turn': d['actions_per_turn'], 'textbook': d['textbook']} == ENV, '미리 정한 환경이 아니다'
    ref = json.load(open(REF, encoding='utf-8'))
    same = dict(zip(ref['seeds'], ref['rows']))
    for seed, rows, fights in zip(d['seeds'], d['rows'], d['fights']):
        assert [{k: v for k, v in r.items() if k != 'pnum'} for r in rows] == same[seed], f'시드 {seed}: 대조와 다르다'
        consistent(rows, fights)
    pair, own = [], defaultdict(list)
    for gi, (rows, fights) in enumerate(zip(d['rows'], d['fights'])):
        grp = {r['pnum']: group(r, 'deck15') for r in rows}
        for f in fights:
            fa = [features(f, i, COST, deck_units) for i in (0, 1)]
            for i in ((0,) if f['ghost'] else (0, 1)):
                won = f['won'] == 1 + i
                own[(grp[f['pnum'][i]], f['round'])].append(dict(fa[i], win=won, level=f['level'][i], hp=f['hp'][i]))
            if f['round'] in STAGE4 and not f['ghost'] and f['won'] in (1, 2):
                pair.append((gi, grp[f['pnum'][0]], grp[f['pnum'][1]], fa[0], fa[1], f['won'] == 1))
    table = {}
    for (g, slot), xs in sorted(own.items()):
        if slot in SHOW:
            table[f'{g} {SHOW[slot]}'] = {'fights': len(xs), **{k: round(float(np.mean([x[k] for x in xs])), 3)
                                                              for k in ('win', 'level', 'hp', *FEATURES, 'deck_units', 'four', 'four2')}}
    m = model(pair)
    rec = {'input': hashlib.sha256(raw).hexdigest(), 'games': len(d['rows']), 'errors': len(d['errors']), 'table': table,
           'model': m, 'reading': reading(m)}
    json.dump(rec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return rec


def selfcheck():
    """답을 아는 가짜 대전: (가) 이김이 잣대 차로만 정해지고 밸류덱은 잣대가 낮다 -> 설명된 몫이 1 근처,
    (나) 잣대는 같고 밸류덱이라서 진다 -> 0 근처, (다) 밸류덱이 덜 지지 않는다 -> 읽기 없음."""
    rng = np.random.default_rng(1)

    def fake(kind, n=6000):
        rows = []
        for k in range(n):
            a, b = rng.choice(['late', 'normal', 'slow'], 2)
            fa, fb = ({f: float(rng.normal(5, 1)) for f in FEATURES} for _ in range(2))
            if kind == 'board':
                for fx, gx in ((fa, a), (fb, b)):
                    fx['two_star'] -= 1.0 * (gx == 'late')
            z = 0.8 * (fa['two_star'] - fb['two_star']) if kind != 'deck' else 0.0
            if kind == 'deck':
                z += -0.8 * ((a == 'late') - (b == 'late'))
            rows.append((k // 20, a, b, fa, fb, bool(rng.random() < 1 / (1 + np.exp(-z)))))
        return rows

    mb, md, mn = model(fake('board'), boot=50), model(fake('deck'), boot=50), model(fake('none'), boot=50)
    print('잣대 탓:', [round(x, 2) for x in mb['explained']], reading(mb))
    print('덱 탓:', [round(x, 2) for x in md['explained']], reading(md))
    print('차 없음:', [round(x, 2) for x in mn['late_coef_0']], reading(mn))
    assert reading(mb) == '대부분 잰 보드 잣대로 설명된다' and reading(md) == '같은 잣대에서도 밸류덱이 더 진다'
    assert reading(mn).startswith('밸류덱이 4단계 맞대결에서 더 진다고 말할 수 없다')
    assert abs(mb['feature_coef']['two_star'] - 0.8) < 0.1 and abs(md['late_coef_1'][0] + 0.8) < 0.15
    print('셈 확인 통과')


if __name__ == '__main__':
    if sys.argv[1] == 'selfcheck':
        selfcheck()
        sys.exit()
    r = main(sys.argv[1])
    m = r['model']
    print(f"판 {r['games']} 오류 {r['errors']} | 4단계 맞대결 {m['fights']}개(밸류덱 대 보통 덱 {m['late_vs_normal_fights']}개)")
    print(f"밸류덱 계수 틀 0 {m['late_coef_0'][0]:+.3f} [{m['late_coef_0'][1]:+.3f}, {m['late_coef_0'][2]:+.3f}] "
          f"틀 1 {m['late_coef_1'][0]:+.3f} [{m['late_coef_1'][1]:+.3f}, {m['late_coef_1'][2]:+.3f}]")
    print(f"설명된 몫 {m['explained'][0]:.2f} [{m['explained'][1]:.2f}, {m['explained'][2]:.2f}] → 「{r['reading']}」")
    print('잣대별 몫(로그 오즈)', {k: round(v, 3) for k, v in m['part'].items()})
