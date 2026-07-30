"""
별 등급이 전투에서 실제로 얼마나 중요한가.

두 가지를 잰다.
  1) 같은 조합 2성 vs 1성       - 별 자체의 가치
  2) 6유닛 2성 vs 8유닛 1성      - 별을 올리는 것과 유닛 수를 늘리는 것 중 무엇이 나은가

(1)에서 미러 매치(2성 vs 2성)를 함께 재는 이유는, 하네스에 진영 유리가 없는지
확인하기 위해서다. 50% 근처가 나와야 나머지 숫자를 믿을 수 있다.

실행: python -m analysis.star_value
"""
import statistics

from analysis.battle import win_rate
from analysis.comps import COMPS, spec

N = 40


def main():
    print(f'별 등급 가치 (N={N}, 좌우 교대)')
    print(f"{'조합':>18}{'미러 2성':>12}{'2성 vs 1성':>14}{'6유닛2성 vs 8유닛1성':>24}")

    mirrors, values, tradeoffs = [], [], []
    for name, comp in COMPS.items():
        mirror = win_rate(spec(comp, 2), spec(comp, 2), N)
        value = win_rate(spec(comp, 2), spec(comp, 1), N)
        tradeoff = win_rate(spec(comp, 2, size=6), spec(comp, 1, size=8), N)

        mirrors.append(mirror)
        values.append(value)
        tradeoffs.append(tradeoff)
        print(f'{name:>18}{mirror*100:>11.1f}%{value*100:>13.1f}%{tradeoff*100:>23.1f}%')

    print()
    print(f'미러 평균        {statistics.mean(mirrors)*100:5.1f}%  (50%에서 크게 벗어나면 하네스 편향)')
    print(f'2성 vs 1성 평균  {statistics.mean(values)*100:5.1f}%')
    print(f'적은 유닛 2성 평균 {statistics.mean(tradeoffs)*100:5.1f}%  (50% 초과면 별 > 유닛 수)')


if __name__ == '__main__':
    main()
