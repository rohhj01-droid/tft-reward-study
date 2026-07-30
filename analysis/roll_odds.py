"""
레벨별 리롤 효율.

같은 유닛을 2성(3장) / 3성(9장)까지 모으는 데 드는 골드를, 플레이어 레벨별로 잰다.
구매 판단은 완벽하다고 가정하고(뜨면 무조건 산다) 상점 확률과 풀 고갈만 반영한다.
즉 "낮은 레벨에서 굴리는 것이 골드 효율상 유리한가"만 격리해서 보는 실험.

시뮬레이터가 필요 없다. set4.py 상수만 쓴다.

실행: python -m analysis.roll_odds
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import LEVEL_ODDS, POOL_SIZE, UNIQUE_PER_COST


def draw_cost(level):
    """상점 슬롯 하나의 코스트를 뽑는다."""
    r = random.random()
    odds = LEVEL_ODDS[level]
    for tier in range(5):
        if r < odds[tier]:
            return tier + 1
    return 5


def gold_to_collect(level, need, cost=1, trials=3000):
    """cost 코스트 유닛 1종을 need장 모으는 데 든 평균 골드."""
    target_pool = POOL_SIZE[cost - 1]
    other_pool = POOL_SIZE[cost - 1] * (UNIQUE_PER_COST[cost - 1] - 1)
    total = 0
    for _ in range(trials):
        got, pool_left, others, gold = 0, target_pool, other_pool, 0
        while got < need and gold < 2000:
            gold += 2  # 새로고침 비용
            for _ in range(5):
                if draw_cost(level) != cost:
                    continue
                if random.random() < pool_left / (pool_left + others):
                    got += 1
                    pool_left -= 1
                    if got >= need:
                        break
        total += gold
    return total / trials


def main():
    print('1코스트 유닛 1종을 모으는 데 든 골드 (완벽 구매 가정)')
    print(f"{'':8}{'2성(3장)':>12}{'3성(9장)':>12}")
    for level in (5, 6, 7, 8):
        two = gold_to_collect(level, 3)
        three = gold_to_collect(level, 9)
        print(f'  레벨 {level}{two:>11.0f}{three:>12.0f}')
    print()
    print('레벨이 낮을수록 저코스트가 자주 등장하므로 같은 유닛을 모으는 비용이 싸다.')
    print('한 게임에서 쓸 수 있는 총 골드는 200 안팎이므로, 3성 가격과 비교하면')
    print('3성 완성이 현실적으로 가능한 구간이 어디까지인지 알 수 있다.')


if __name__ == '__main__':
    main()
