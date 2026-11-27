"""실제 판의 마지막 대전을 두 가지로 붙인 실행을 견준다(판정 없음, 읽기만, 2026-11-25,
results/README 「마지막 대전 붙이기: 별 처리 결함을 고치고 다시 붙이기 — 미리 정한 읽기」).

두 실행은 같은 대전을 같은 시드로 붙인 것이고 한 가지만 다르다(meta/inversion/final_fight.py run).
  place: 배치. 앞(base) = 구석 배치(원거리는 뒷줄 구석부터 아이템이 많은 순), 뒤(new) = 가운데 배치(원거리도 뒷줄 가운데부터).
  fix:   별 처리. 앞 = 시뮬레이터 그대로(june), 뒤 = 결함 둘을 고친 것(fixed).
  effect: 배치. 앞 = 구석 배치, 뒤 = 배치에 따라 달라지는 효과를 살리는 배치(analysis/battle.effect_positions, 2026-11-26,
          results/README 「마지막 대전 붙이기: 효과를 살리는 배치 — 미리 정한 읽기」). 보드 특징은 배치에 걸리는 것 일곱을 더 읽는다.
  behavior: 동작 하나. 앞 = 고침(fixed), 뒤 = 결투가·추방자 동작 하나를 바꾼 것(jax, stacks, move, blind), 배치는 같다(2026-11-27,
          results/README 「마지막 대전 붙이기: 결투가·추방자 동작 하나씩 바꾸기 — 미리 정한 읽기」). 결투가·추방자 유닛 특징 열을 더 읽는다.
          야스오 3성 장점 하나를 끈 것(no_shield, no_steal, no_duelist, no_dash, 2026-11-28)도 같은 견주기로 읽는다.
읽기 1: 실제 1등을 맞힌 몫의 차(뒤 - 앞). 읽기 2: 한쪽만 그 계열(또는 보드 특징)인 대전에서 「시뮬레이터 승률 - 그 쪽이 실제 1등인 몫」이
앞 실행에서 0을 벗어났으면, 뒤 실행에서도 남는가. 구간은 대전을 다시 뽑는 부트스트랩 1,000번(시드 0)이다.

    python meta/inversion/final_place.py place|fix|effect|behavior <뽑아 둔 대전 파일> <앞 실행 기록> <뒤 실행 기록> <결과 json>
    python meta/inversion/final_place.py selfcheck
(저장소 맨 위에서, PYTHONPATH에 저장소 맨 위)
"""
import json
import os
import sys

import numpy as np

from meta.inversion import final_fight as ff
from set4 import FIVE_COST_UNITS, FOUR_COST_UNITS

BOOT, SEED = 1000, 0
BIG = set(FOUR_COST_UNITS) | set(FIVE_COST_UNITS)
OVERALL = {'place': ('가운데 배치가 실제 승자를 더 잘 맞힌다', '구석 배치가 실제 승자를 더 잘 맞힌다', '두 배치가 구별되지 않는다'),
           'fix': ('별 처리를 고치면 실제 승자를 더 잘 맞힌다', '별 처리를 고치면 실제 승자를 못 맞힌다', '고치기 전과 구별되지 않는다'),
           'effect': ('효과를 살린 배치가 실제 승자를 더 잘 맞힌다', '구석 배치가 실제 승자를 더 잘 맞힌다', '두 배치가 구별되지 않는다'),
           'behavior': ('동작을 바꾸면 실제 승자를 더 잘 맞힌다', '동작을 바꾸면 실제 승자를 못 맞힌다', '바꾸기 전과 구별되지 않는다')}


def count(trait, lo, hi=99):
    return lambda b: lo <= b['traits'].get(trait, 0) <= hi


# 한쪽만 가진 대전에서 읽는 보드 특징. 아이템 번호는 재료 번호 둘을 이은 것이다(17 = 대검 + 벨트 = 지크의 전령, 46 = 눈물 + 망토 = 힘의 성배).
FEATURES = {
    'chosen 3-star': ff.chosen_three, 'moonlight 3+': count('Moonlight', 3),
    '3-star any': lambda b: any(u[1] == 3 for u in b['units']),
    '3-star, chosen not 3-star': lambda b: any(u[1] == 3 for u in b['units']) and not ff.chosen_three(b),
    '3-star 4-5 cost': lambda b: any(u[1] == 3 and u[0].lower() in BIG for u in b['units']),
    'chosen 3-star 4-5 cost': lambda b: ff.chosen_three(b) and b['chosen'][0].lower() in BIG,
    '3-star 4-5 cost not chosen': lambda b: any(u[1] == 3 and u[0].lower() in BIG and not (b['chosen'] and u[0] == b['chosen'][0]) for u in b['units']),
    'keeper 2~3': count('Keeper', 2, 3), 'keeper 4+': count('Keeper', 4), 'adept 2': count('Adept', 2, 2), 'adept 3+': count('Adept', 3),
    'dazzler 2+': count('Dazzler', 2), 'divine 4~5': count('Divine', 4, 5), 'divine 6+': count('Divine', 6), 'assassin 2+': count('Assassin', 2),
    'azir': lambda b: any(u[0] == 'Azir' for u in b['units']),
    'zekes_herald': lambda b: any(17 in u[2] for u in b['units']), 'chalice_of_power': lambda b: any(46 in u[2] for u in b['units']),
}


def mean_ci(x):
    """대전별 값 -> [평균, [아래, 위]]."""
    x = np.asarray(x, float)
    rng = np.random.RandomState(SEED)
    m = [x[rng.randint(0, len(x), len(x))].mean() for _ in range(BOOT)]
    return [round(float(x.mean()), 4), [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]]

# 효과 배치(effect)를 읽을 때 더 보는 특징 일곱. 모두 배치에 따라 달라지는 효과다(35 = 지팡이 + 조끼 = 솔라리의 펜던트,
# 67 = 망토 + 벨트 = 서풍, 59 = 조끼 + 장갑 = 침묵의 장막, 45 = 눈물 + 조끼 = 얼어붙은 심장, 36 = 지팡이 + 망토 = 이온 충격기).
FEATURES_EFFECT = dict(FEATURES, **{
    'exile': count('Exile', 1), 'exile 2': count('Exile', 2),
    **{name: (lambda i: lambda b: any(i in u[2] for u in b['units']))(i) for name, i in (
        ('locket_of_the_iron_solari', 35), ('zephyr', 67), ('shroud_of_stillness', 59), ('frozen_heart', 45), ('ionic_spark', 36))}})

# 동작 바꾸기(behavior)를 읽을 때 더 보는 특징 열(결투가·추방자 유닛과 결투가 단계).
unit = lambda name, star=None: (lambda b: any(u[0] == name and (star is None or u[1] == star) for u in b['units']))
FEATURES_BEHAVIOR = dict(FEATURES_EFFECT, **{
    'yasuo 3-star': unit('Yasuo', 3), 'yone 2-star': unit('Yone', 2), 'jax': unit('Jax'), 'fiora': unit('Fiora'), 'kalista': unit('Kalista'),
    'leesin': unit('LeeSin'), 'xinzhao': unit('XinZhao'),
    'duelist 2~3': count('Duelist', 2, 3), 'duelist 4~5': count('Duelist', 4, 5), 'duelist 6+': count('Duelist', 6)})


def hit(p):
    return np.where(p > 0.5, 1.0, np.where(p == 0.5, 0.5, 0.0))


def overall_reading(kind, lo, hi):
    """읽기 1: 맞힌 몫의 차(뒤 - 앞)의 구간."""
    return OVERALL[kind][0 if lo > 0 else 1 if hi < 0 else 2]


def row_reading(gap_base, gap_new, change):
    """읽기 2: 앞 실행의 차가 뒤 실행에서도 같은 쪽으로 남는가. 인자는 모두 [값, [아래, 위]]."""
    if gap_base[1][0] <= 0 <= gap_base[1][1]:
        return '앞 실행에서 차가 보이지 않는다'
    sign = 1 if gap_base[0] > 0 else -1
    lo, hi = sorted(sign * v for v in gap_new[1])  # 앞 실행의 차와 같은 쪽을 +로
    if lo > 0:
        moved = not change[1][0] <= 0 <= change[1][1]
        return '움직이지만 남는다' if moved else '그대로 남는다'
    return '뒤집힌다' if hi < 0 else '보이지 않게 된다'


def one_sided(ra, rb, sides):
    """sides = 대전마다 0(1등 쪽)·1(2등 쪽)·None. 그 쪽이 실제 1등인 몫, 두 실행의 시뮬레이터 승률, 차와 구간, 읽기."""
    got = [(s, a['p'], b['p']) for a, b, s in zip(ra, rb, sides) if s is not None]
    if not got:
        return {'fights': 0}
    real = np.array([float(s == 0) for s, _, _ in got])
    sa = np.array([p if s == 0 else 1 - p for s, p, _ in got])
    sb = np.array([p if s == 0 else 1 - p for s, _, p in got])
    out = {'fights': len(got), 'real': round(float(real.mean()), 4), 'base': round(float(sa.mean()), 4), 'new': round(float(sb.mean()), 4),
           'gap_base': mean_ci(sa - real), 'gap_new': mean_ci(sb - real), 'change': mean_ci(sb - sa)}
    out['reading'] = row_reading(out['gap_base'], out['gap_new'], out['change'])
    return out


def compare(kind, pairs, base, new, src=None):
    tag = lambda r: (r['place'], r.get('variant', 'harness'))
    assert base['used'] == new['used'] and base['n'] == new['n']
    if kind in ('place', 'effect'):
        assert (base['place'], new['place']) == ('corner', {'place': 'range', 'effect': 'effect'}[kind]) and tag(base)[1] == tag(new)[1], (tag(base), tag(new))
    elif kind == 'behavior':
        assert base['place'] == new['place'] and tag(base)[1] == 'fixed' and tag(new)[1] in ff.BEHAVIORS, (tag(base), tag(new))
    else:
        assert base['place'] == new['place'] and (tag(base)[1], tag(new)[1]) == ('june', 'fixed'), (tag(base), tag(new))
    keep = [i for i in range(len(base['used'])) if base['won'][i] is not None and new['won'][i] is not None]  # 두 실행 모두 붙은 대전
    boards = [pairs['pairs'][base['used'][i]]['boards'] for i in keep]
    ra = ff.rows_of([{'boards': b} for b in boards], [base['won'][i] for i in keep], base['n'])
    rb = ff.rows_of([{'boards': b} for b in boards], [new['won'][i] for i in keep], base['n'])
    pa, pb = np.array([r['p'] for r in ra]), np.array([r['p'] for r in rb])
    change = mean_ci(hit(pb) - hit(pa))
    both = (pa != 0.5) & (pb != 0.5)
    by_family = {}
    for f in sorted({f for r in ra for f in r['fam']}):
        sides = [None if (r['fam'][0] == f) == (r['fam'][1] == f) else int(r['fam'][1] == f) for r in ra]
        if sum(s is not None for s in sides) >= 100:  # 대전이 100개 안 되는 계열은 표에서 뺀다
            by_family[f] = one_sided(ra, rb, sides)
    by_feature = {name: one_sided(ra, rb, [None if has(one) == has(two) else int(has(two)) for one, two in boards])
                  for name, has in {'effect': FEATURES_EFFECT, 'behavior': FEATURES_BEHAVIOR}.get(kind, FEATURES).items()}
    return {'kind': kind, 'records': dict(src or {}), 'base': list(tag(base)), 'new': list(tag(new)), 'n': base['n'],
            'fights_read': len(keep), 'dropped_errors': len(base['used']) - len(keep),
            'hit': {'base': round(float(hit(pa).mean()), 4), 'new': round(float(hit(pb).mean()), 4),
                    'mean_of_two': round(float(hit((pa + pb) / 2).mean()), 4)},
            'hit_change': change, 'reading': overall_reading(kind, *change[1]),
            'flip_share': round(float(((pa > 0.5) != (pb > 0.5))[both].mean()), 4), 'both_decided': int(both.sum()),
            'mean_abs_change': round(float(np.abs(pb - pa).mean()), 4),
            'S': {'base': round(ff.stats(ra)['S'], 4), 'new': round(ff.stats(rb)['S'], 4)},
            'by_family': by_family, 'by_feature': by_feature,
            'higher_level': one_sided(ra, rb, [None if r['level'] == 0 else int(r['level'] < 0) for r in ra])}


def selfcheck():
    def b(level, units, traits):
        return {'level': level, 'units': units, 'traits': traits, 'chosen': None}
    big = b(9, [['Yone', 2, [15, 19]], ['Riven', 2, []]], {'Dusk': 4})
    big3 = dict(big, units=[['Yone', 2, [15, 19]], ['Riven', 3, []]], chosen=['Riven', 'Dusk'])  # 선택받은 자 4코스트 3성이 있는 보드
    small = b(8, [['Vayne', 1, [2]]], {'Sharpshooter': 4})
    pairs = {'pairs': [{'boards': [big, small]}, {'boards': [small, big3]}, {'boards': [big, small]}, {'boards': [big, big]}]}
    rec = {'n': 12, 'used': [0, 1, 2, 3]}
    corner, rng_rec = dict(rec, place='corner', won=[[6, 6], [0, 0], [3, 3], [3, 3]]), dict(rec, place='range', won=[[3, 3], [6, 6], [6, 6], None])
    out = compare('place', pairs, corner, rng_rec)
    # 손으로 센 값: 앞 실행의 1등 보드 승률 1·0·0.5, 뒤 실행 0.5·1·1. 넷째 대전은 뒤 실행에서 터져서 뺀다
    assert out['fights_read'] == 3 and out['dropped_errors'] == 1 and out['base'] == ['corner', 'harness'] and out['new'] == ['range', 'harness']
    # 두 실행 승률의 평균은 0.75·0.5·0.75라서 맞힌 몫 (1 + 0.5 + 1)/3
    assert out['hit'] == {'base': 0.5, 'new': 0.8333, 'mean_of_two': 0.8333} and out['hit_change'][0] == 0.3333
    assert out['both_decided'] == 1 and out['flip_share'] == 1.0 and out['mean_abs_change'] == 0.6667
    assert out['by_family'] == {}  # 대전이 100개 안 되는 계열은 뺀다
    star = out['by_feature']['chosen 3-star']  # 선택받은 자 3성이 있는 보드 = 둘째 대전의 2등. 그 쪽 승률은 앞 1 - 0 = 1, 뒤 1 - 1 = 0
    assert (star['fights'], star['real'], star['base'], star['new'], star['change'][0]) == (1, 0.0, 1.0, 0.0, -1.0)
    assert out['by_feature']['chosen 3-star 4-5 cost']['fights'] == 1 and out['by_feature']['3-star 4-5 cost not chosen'] == {'fights': 0}
    assert FEATURES['3-star 4-5 cost not chosen'](dict(big3, chosen=['Yone', 'Exile'])) and FEATURES['3-star, chosen not 3-star'](dict(big3, chosen=None))
    assert out['by_feature']['3-star 4-5 cost']['fights'] == 1 and out['by_feature']['keeper 4+'] == {'fights': 0} == out['by_feature']['zekes_herald']
    assert FEATURES['zekes_herald'](b(8, [['Shen', 2, [17]]], {})) and FEATURES['keeper 2~3'](b(8, [], {'Keeper': 3})) and not FEATURES['keeper 2~3'](b(8, [], {'Keeper': 4}))
    level = out['higher_level']  # 레벨이 높은 쪽 = 황혼 보드: 실제 1등 2/3, 앞 실행 승률 (1 + 1 + 0.5)/3, 뒤 실행 (0.5 + 0 + 1)/3
    assert (level['fights'], level['real'], level['base'], level['new']) == (3, 0.6667, 0.8333, 0.5)
    assert (level['gap_base'][0], level['gap_new'][0], level['change'][0]) == (0.1667, -0.1667, -0.3333)
    # 별 처리 견주기는 배치가 같고 앞이 june, 뒤가 fixed여야 한다
    fix = compare('fix', pairs, dict(corner, variant='june'), dict(corner, variant='fixed', won=rng_rec['won']))
    assert fix['hit_change'][0] == 0.3333 and fix['base'] == ['corner', 'june'] and fix['new'] == ['corner', 'fixed']
    # 효과 배치 견주기는 별 처리가 같고 앞이 구석(corner), 뒤가 효과(effect)여야 한다. 배치에 걸리는 특징 일곱을 더 읽는다
    eff = compare('effect', pairs, dict(corner, variant='fixed'), dict(rng_rec, place='effect', variant='fixed'))
    assert eff['hit_change'][0] == 0.3333 and eff['base'] == ['corner', 'fixed'] and eff['new'] == ['effect', 'fixed']
    assert len(eff['by_feature']) == len(FEATURES) + 7 and eff['by_feature']['exile'] == {'fights': 0} and len(out['by_feature']) == len(FEATURES)
    assert FEATURES_EFFECT['exile'](b(8, [], {'Exile': 1})) and not FEATURES_EFFECT['exile 2'](b(8, [], {'Exile': 1}))
    assert FEATURES_EFFECT['locket_of_the_iron_solari'](b(8, [['Shen', 2, [35]]], {})) and not FEATURES_EFFECT['zephyr'](b(8, [['Shen', 2, [35]]], {}))
    assert [overall_reading('effect', *v)[:2] for v in ((0.01, 0.03), (-0.03, -0.01), (-0.01, 0.01))] == ['효과', '구석', '두 ']
    # 동작 바꾸기 견주기는 배치가 같고 앞이 fixed, 뒤가 바꾼 동작 하나여야 한다. 결투가·추방자 유닛 특징 열을 더 읽는다
    beh = compare('behavior', pairs, dict(corner, place='effect', variant='fixed'), dict(rng_rec, place='effect', variant='jax'))
    assert beh['hit_change'][0] == 0.3333 and beh['new'] == ['effect', 'jax'] and len(beh['by_feature']) == len(FEATURES_EFFECT) + 10
    assert FEATURES_BEHAVIOR['yasuo 3-star'](b(8, [['Yasuo', 3, []]], {})) and not FEATURES_BEHAVIOR['yasuo 3-star'](b(8, [['Yasuo', 2, []]], {}))
    assert FEATURES_BEHAVIOR['duelist 4~5'](b(8, [], {'Duelist': 4})) and not FEATURES_BEHAVIOR['duelist 6+'](b(8, [], {'Duelist': 5}))
    assert [overall_reading('behavior', *v).split()[-2] for v in ((0.01, 0.03), (-0.03, -0.01), (-0.01, 0.01))] == ['잘', '못', '구별되지']
    for wrong in (lambda: compare('behavior', pairs, dict(corner, variant='fixed'), dict(rng_rec, variant='jax')),
                  lambda: compare('behavior', pairs, dict(corner, variant='june'), dict(corner, variant='jax')),
                  lambda: compare('behavior', pairs, dict(corner, variant='fixed'), dict(corner, variant='fixed'))):
        try:
            wrong()
            raise SystemExit('잘못 짝지은 두 실행을 받아들였다')
        except AssertionError:
            pass
    for wrong in (lambda: compare('fix', pairs, corner, rng_rec), lambda: compare('place', pairs, corner, dict(rng_rec, variant='fixed')),
                  lambda: compare('effect', pairs, corner, rng_rec), lambda: compare('effect', pairs, corner, dict(rng_rec, place='effect', variant='fixed'))):
        try:
            wrong()
            raise SystemExit('잘못 짝지은 두 실행을 받아들였다')
        except AssertionError:
            pass
    assert mean_ci([0.25] * 40) == [0.25, [0.25, 0.25]]
    assert [overall_reading('place', *v)[:2] for v in ((0.01, 0.03), (-0.03, -0.01), (-0.01, 0.01))] == ['가운', '구석', '두 ']
    assert [overall_reading('fix', *v).split()[-2] for v in ((0.01, 0.03), (-0.03, -0.01), (-0.01, 0.01))] == ['잘', '못', '구별되지']
    neg, zero = [-0.10, [-0.13, -0.07]], [0.0, [-0.02, 0.02]]
    assert row_reading(neg, [-0.09, [-0.12, -0.06]], zero) == '그대로 남는다'
    assert row_reading(neg, [-0.05, [-0.08, -0.02]], [0.05, [0.03, 0.07]]) == '움직이지만 남는다'
    assert row_reading(neg, [-0.01, [-0.04, 0.02]], [0.09, [0.06, 0.12]]) == '보이지 않게 된다'
    assert row_reading(neg, [0.06, [0.03, 0.09]], [0.16, [0.12, 0.2]]) == '뒤집힌다'
    assert row_reading([0.09, [0.08, 0.11]], [0.08, [0.06, 0.1]], zero) == '그대로 남는다'
    assert row_reading([0.09, [0.08, 0.11]], [-0.05, [-0.08, -0.02]], [-0.14, [-0.17, -0.1]]) == '뒤집힌다'
    assert row_reading([0.01, [-0.01, 0.03]], [0.08, [0.06, 0.1]], [0.07, [0.05, 0.09]]) == '앞 실행에서 차가 보이지 않는다'
    print('selfcheck 통과')


if __name__ == '__main__':
    if sys.argv[1] == 'selfcheck':
        selfcheck()
        sys.exit()
    kind = sys.argv[1]
    pairs, base, new = (json.load(open(f, encoding='utf-8')) for f in sys.argv[2:5])
    out = compare(kind, pairs, base, new, {name: {'file': os.path.basename(f), 'sha256': ff.sha(f)} for name, f in zip(('base', 'new'), sys.argv[3:5])})
    json.dump(out, open(sys.argv[5], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('fights_read', 'base', 'new', 'hit', 'hit_change', 'reading', 'flip_share', 'mean_abs_change', 'S')}, ensure_ascii=False))
    for f, v in list(out['by_family'].items()) + list(out['by_feature'].items()) + [('higher level', out['higher_level'])]:
        print(f, v['fights'], 'gap', v['gap_base'], '->', v['gap_new'], 'change', v['change'], v['reading'])
