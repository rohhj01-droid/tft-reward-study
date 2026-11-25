"""실제 판의 마지막 대전을 배치를 바꿔 다시 붙인 실행을 구석 배치 실행과 견준다(판정 없음, 읽기만, 2026-11-25,
results/README 「마지막 대전을 배치를 바꿔 다시 붙이기: 미리 정한 읽기」).

두 실행은 같은 대전을 같은 시드로 붙인 것이고 배치만 다르다(meta/inversion/final_fight.py run --place).
  구석 배치(corner): 원거리는 뒷줄 구석부터 아이템이 많은 순, 근접은 앞줄 가운데부터.
  가운데 배치(range): 원거리도 뒷줄 가운데부터, 근접은 같다.
읽기 1: 실제 1등을 맞힌 몫의 차(가운데 - 구석). 읽기 2: 구석 배치에서 한쪽으로 치우쳤던 여섯 계열의 차(시뮬레이터 승률 - 실제
1등인 몫)가 가운데 배치에서도 남는가. 구간은 대전을 다시 뽑는 부트스트랩 1,000번(시드 0)이다.

    python meta/inversion/final_place.py <뽑아 둔 대전 파일> <구석 배치 실행 기록> <가운데 배치 실행 기록> results/final_place.json
    python meta/inversion/final_place.py selfcheck
(저장소 맨 위에서, PYTHONPATH에 저장소 맨 위)
"""
import json
import os
import sys

import numpy as np

from meta.inversion import final_fight as ff

SIX = ('divine', 'duelist', 'elderwood', 'ninja', 'sharpshooter', 'warlord')  # 구석 배치에서 차의 구간이 0을 벗어난 계열
BOOT, SEED = 1000, 0


def mean_ci(x):
    """대전별 값 -> [평균, [아래, 위]]."""
    x = np.asarray(x, float)
    rng = np.random.RandomState(SEED)
    m = [x[rng.randint(0, len(x), len(x))].mean() for _ in range(BOOT)]
    return [round(float(x.mean()), 4), [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]]


def hit(p):
    return np.where(p > 0.5, 1.0, np.where(p == 0.5, 0.5, 0.0))


def overall_reading(lo, hi):
    """읽기 1: 맞힌 몫의 차(가운데 - 구석)의 구간."""
    if lo > 0:
        return '가운데 배치가 실제 승자를 더 잘 맞힌다'
    if hi < 0:
        return '구석 배치가 실제 승자를 더 잘 맞힌다'
    return '두 배치가 구별되지 않는다'


def family_reading(gap_corner, gap_range, change):
    """읽기 2: 구석 배치의 차와 같은 쪽으로 가운데 배치의 차가 남는가. 인자는 모두 [값, [아래, 위]]."""
    sign = 1 if gap_corner[0] > 0 else -1
    lo, hi = sorted(sign * v for v in gap_range[1])  # 구석 배치의 차와 같은 쪽을 +로
    if lo > 0:
        moved = not change[1][0] <= 0 <= change[1][1]
        return '배치에 따라 움직이지만 남는다' if moved else '배치를 바꿔도 그대로 남는다'
    return '배치를 바꾸면 뒤집힌다' if hi < 0 else '배치를 바꾸면 보이지 않는다'


def one_sided(ra, rb, side):
    """side(대전) -> 0(1등 쪽)·1(2등 쪽)·None. 그 쪽이 실제 1등인 몫, 두 배치의 시뮬레이터 승률, 차와 구간."""
    got = [(s, a['p'], b['p']) for a, b in zip(ra, rb) for s in [side(a)] if s is not None]
    real = np.array([float(s == 0) for s, _, _ in got])
    sa = np.array([p if s == 0 else 1 - p for s, p, _ in got])
    sb = np.array([p if s == 0 else 1 - p for s, _, p in got])
    return {'fights': len(got), 'real': round(float(real.mean()), 4), 'corner': round(float(sa.mean()), 4), 'range': round(float(sb.mean()), 4),
            'gap_corner': mean_ci(sa - real), 'gap_range': mean_ci(sb - real), 'change': mean_ci(sb - sa)}


def compare(pairs, corner, rng_rec, src=None):
    assert corner['place'] == 'corner' and rng_rec['place'] == 'range' and corner['used'] == rng_rec['used'] and corner['n'] == rng_rec['n']
    keep = [i for i in range(len(corner['used'])) if corner['won'][i] is not None and rng_rec['won'][i] is not None]  # 두 실행 모두 붙은 대전
    boards = [pairs['pairs'][corner['used'][i]] for i in keep]
    ra = ff.rows_of(boards, [corner['won'][i] for i in keep], corner['n'])
    rb = ff.rows_of(boards, [rng_rec['won'][i] for i in keep], corner['n'])
    pa, pb = np.array([r['p'] for r in ra]), np.array([r['p'] for r in rb])
    change = mean_ci(hit(pb) - hit(pa))
    both = (pa != 0.5) & (pb != 0.5)
    by_family = {}
    for f in sorted({f for r in ra for f in r['fam']}):
        n = sum((r['fam'][0] == f) != (r['fam'][1] == f) for r in ra)
        if f in SIX or n >= 100:  # 대전이 100개 안 되는 계열은 표에서 뺀다
            by_family[f] = v = one_sided(ra, rb, lambda r: None if (r['fam'][0] == f) == (r['fam'][1] == f) else int(r['fam'][1] == f))
            if f in SIX:
                v['reading'] = family_reading(v['gap_corner'], v['gap_range'], v['change'])
    return {'records': dict(src or {}), 'n': corner['n'], 'fights_read': len(keep), 'dropped_errors': len(corner['used']) - len(keep),
            'hit': {'corner': round(float(hit(pa).mean()), 4), 'range': round(float(hit(pb).mean()), 4),
                    'mean_of_two': round(float(hit((pa + pb) / 2).mean()), 4)},
            'hit_change': change, 'reading': overall_reading(*change[1]),
            'flip_share': round(float(((pa > 0.5) != (pb > 0.5))[both].mean()), 4), 'both_decided': int(both.sum()),
            'mean_abs_change': round(float(np.abs(pb - pa).mean()), 4),
            'S': {'corner': round(ff.stats(ra)['S'], 4), 'range': round(ff.stats(rb)['S'], 4)},
            'by_family': by_family, 'higher_level': one_sided(ra, rb, lambda r: None if r['level'] == 0 else int(r['level'] < 0))}


def selfcheck():
    def b(level, units, traits):
        return {'level': level, 'units': units, 'traits': traits, 'chosen': None}
    big = b(9, [['Yone', 2, [15, 19]], ['Riven', 2, []]], {'Dusk': 4})
    small = b(8, [['Vayne', 1, [2]]], {'Sharpshooter': 4})
    pairs = {'pairs': [{'boards': [big, small]}, {'boards': [small, big]}, {'boards': [big, small]}, {'boards': [big, big]}]}
    rec = {'n': 12, 'used': [0, 1, 2, 3]}
    out = compare(pairs, dict(rec, place='corner', won=[[6, 6], [0, 0], [3, 3], [3, 3]]),
                  dict(rec, place='range', won=[[3, 3], [6, 6], [6, 6], None]))
    # 손으로 센 값: 구석 배치의 1등 보드 승률 1·0·0.5, 가운데 배치 0.5·1·1. 넷째 대전은 가운데 배치에서 터져서 뺀다
    assert out['fights_read'] == 3 and out['dropped_errors'] == 1
    assert set(out['by_family']) == {'sharpshooter'} and out['by_family']['sharpshooter']['reading']  # 황혼은 여섯 계열이 아니고 100개가 안 된다
    # 두 배치 승률의 평균은 0.75·0.5·0.75라서 맞힌 몫 (1 + 0.5 + 1)/3
    assert out['hit'] == {'corner': 0.5, 'range': 0.8333, 'mean_of_two': 0.8333} and out['hit_change'][0] == 0.3333
    assert out['both_decided'] == 1 and out['flip_share'] == 1.0 and out['mean_abs_change'] == 0.6667
    sharp = one_sided(*[ff.rows_of(pairs['pairs'][:3], w, 12) for w in ([[6, 6], [0, 0], [3, 3]], [[3, 3], [6, 6], [6, 6]])],
                      lambda r: None if (r['fam'][0] == 'sharpshooter') == (r['fam'][1] == 'sharpshooter') else int(r['fam'][1] == 'sharpshooter'))
    assert (sharp['fights'], sharp['real'], sharp['corner'], sharp['range']) == (3, 0.3333, 0.1667, 0.5)
    assert sharp['gap_corner'][0] == -0.1667 and sharp['gap_range'][0] == 0.1667 and sharp['change'][0] == 0.3333
    level = out['higher_level']  # 레벨이 높은 쪽 = 황혼 보드: 실제 1등 2/3, 구석 배치 승률 (1 + 1 + 0.5)/3, 가운데 배치 (0.5 + 0 + 1)/3
    assert (level['fights'], level['real'], level['corner'], level['range']) == (3, 0.6667, 0.8333, 0.5)
    assert mean_ci([0.25] * 40) == [0.25, [0.25, 0.25]]
    assert overall_reading(0.01, 0.03).startswith('가운데') and overall_reading(-0.03, -0.01).startswith('구석') and overall_reading(-0.01, 0.01).startswith('두 배치')
    neg, zero = [-0.10, [-0.13, -0.07]], [0.0, [-0.02, 0.02]]
    assert family_reading(neg, [-0.09, [-0.12, -0.06]], zero) == '배치를 바꿔도 그대로 남는다'
    assert family_reading(neg, [-0.05, [-0.08, -0.02]], [0.05, [0.03, 0.07]]) == '배치에 따라 움직이지만 남는다'
    assert family_reading(neg, [-0.01, [-0.04, 0.02]], [0.09, [0.06, 0.12]]) == '배치를 바꾸면 보이지 않는다'
    assert family_reading(neg, [0.06, [0.03, 0.09]], [0.16, [0.12, 0.2]]) == '배치를 바꾸면 뒤집힌다'
    assert family_reading([0.09, [0.08, 0.11]], [0.08, [0.06, 0.1]], zero) == '배치를 바꿔도 그대로 남는다'
    assert family_reading([0.09, [0.08, 0.11]], [-0.05, [-0.08, -0.02]], [-0.14, [-0.17, -0.1]]) == '배치를 바꾸면 뒤집힌다'
    print('selfcheck 통과')


if __name__ == '__main__':
    if sys.argv[1] == 'selfcheck':
        selfcheck()
        sys.exit()
    pairs, corner, rng_rec = (json.load(open(f, encoding='utf-8')) for f in sys.argv[1:4])
    out = compare(pairs, corner, rng_rec, {name: {'file': os.path.basename(f), 'sha256': ff.sha(f)} for name, f in zip(('corner', 'range'), sys.argv[2:4])})
    json.dump(out, open(sys.argv[4], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('fights_read', 'hit', 'hit_change', 'reading', 'flip_share', 'mean_abs_change', 'S')}, ensure_ascii=False))
    for f in SIX:
        v = out['by_family'][f]
        print(f, v['fights'], 'gap', v['gap_corner'], '->', v['gap_range'], 'change', v['change'], v['reading'])
