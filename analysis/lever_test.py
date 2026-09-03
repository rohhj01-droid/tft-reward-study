"""
밸런스 레버의 통계적 유의성.

특정 챔피언의 스탯을 하나씩 깎아보고, 그 조합의 승률이 실제로 떨어지는지 잰다.
승률은 이항 비율이므로 표준오차가 sqrt(p(1-p)/n) 이고, 95% 신뢰구간은 p +- 1.96*SE 다.
너프 전 구간과 너프 후 구간이 겹치면 "이 스탯이 레버다"라고 말할 수 없다.

표본이 작을 때(N=15) 나온 순위는 다시 재면 바뀐다. 처음에 이 실험을 N=15로 돌렸다가
공격속도가 가장 큰 레버라는 결론을 얻었는데, N=60으로 다시 재니 공격속도는 신뢰구간이
겹쳐 유의하지 않았고 공격력이 실제 레버였다.

실행: python -m analysis.lever_test yasuo --n 60
"""
import argparse
import math

import Simulator.stats as stats

from analysis.battle import win_rate
from analysis.comps import COMPS, BENCHMARK, spec

# 값을 잠깐 바꿨다가 되돌리는 방식이라, 챔피언 이름을 키로 갖는 dict인 스탯만 쓸 수 있다.
CANDIDATES = ['AD', 'AS', 'HEALTH', 'MANA', 'MR', 'ARMOR']


def available_stats():
    return [s for s in CANDIDATES if isinstance(getattr(stats, s, None), dict)]


def ci95(p, n):
    half = 1.96 * math.sqrt(max(p * (1 - p), 1e-9) / n)
    return p - half, p + half


def measure(comp_spec, n):
    return win_rate(comp_spec, BENCHMARK, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('unit', help='너프할 챔피언 이름')
    ap.add_argument('--comp', default='low_coherent')
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--mult', type=float, default=0.6, help='스탯 배율')
    args = ap.parse_args()

    comp_spec = spec(COMPS[args.comp], stars=2)

    base = measure(comp_spec, args.n)
    lo, hi = ci95(base, args.n)
    print(f'기준(너프 없음)  {base * 100:5.1f}%   95% CI [{lo * 100:.1f}, {hi * 100:.1f}]')
    print()

    for stat_name in available_stats():
        table = getattr(stats, stat_name)
        if args.unit not in table:
            continue
        original = table[args.unit]
        table[args.unit] = original * args.mult
        try:
            nerfed = measure(comp_spec, args.n)
        finally:
            table[args.unit] = original  # 전역 테이블이다. 안 되돌리면 너프가 다음 스탯 측정까지 남는다

        nlo, nhi = ci95(nerfed, args.n)
        # 두 비율 검정 대신 구간 겹침으로 판정한다. 이쪽이 더 보수적이라 진짜 레버를
        # 놓칠 수는 있는데, 출력만 보고 왜 그런 판정인지 알 수 있는 게 낫다고 봤다.
        overlap = not (nhi < lo or nlo > hi)
        verdict = '유의하지 않음(구간 겹침)' if overlap else '유의함'
        print(f'{stat_name:>8} x{args.mult}  {nerfed * 100:5.1f}%   '
              f'95% CI [{nlo * 100:5.1f}, {nhi * 100:5.1f}]   {verdict}')

    print()
    print(f'N={args.n}. 표본이 작으면 구간이 넓어져 대부분 "유의하지 않음"으로 나온다.')
    print('반대로 작은 표본에서 나온 순위를 그대로 믿으면 잘못된 레버를 고르게 된다.')


if __name__ == '__main__':
    main()
