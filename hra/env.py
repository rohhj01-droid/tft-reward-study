"""
TFT 경제 의사결정 환경.

전투를 직접 돌리지 않고 보드 강도를 board_value로 근사한 단순화 환경이다.
"제한된 골드를 레벨업과 리롤에 어떻게 배분할 것인가"만 떼어내서 학습시키는 것이 목적.

    board_value = Σ (코스트 × 3^(별-1))   # 상위 (레벨) 개 유닛만 합산

상점 확률, 유닛 풀, 레벨업 비용, 패시브 경험치는 시뮬레이터 값을 그대로 쓴다(set4.py).

보상은 스칼라 하나가 아니라 요인별 dict로 돌려준다.
    board : 이번 라운드의 board_value 증가분
    econ  : 이번 라운드에 받은 이자
학습기(hra/train.py)가 이 요인들을 각각 별도 헤드로 학습한다.
"""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import (LEVEL_ODDS, COST_STAR_VALUE, POOL_SIZE, UNIQUE_PER_COST,
                  LEVEL_XP, PASSIVE_XP, MAX_INTEREST)

ACTIONS = ['SAVE', 'LEVEL', 'ROLL50', 'ROLLHARD']

# 기본 조합의 코스트 구성. 1코 4장 + 2코 1장 + 3코 3장.
DEFAULT_COMP = (1, 1, 1, 1, 2, 3, 3, 3)


class EconEnv:
    """
    상태: [gold, level, round, board_value, 2성 수, 3성 수] (모두 0~1 정규화)
    행동: SAVE / LEVEL / ROLL50 / ROLLHARD

    ROLL50   - 이자가 깨지지 않는 선(골드 52 초과분)에서만 리롤
    ROLLHARD - 골드 12까지 공격적으로 리롤
    """

    def __init__(self, comp_costs=DEFAULT_COMP, n_rounds=24):
        self.comp_costs = list(comp_costs)
        self.n_rounds = n_rounds

    def reset(self):
        self.gold = 2
        self.level = 3
        self.exp = 0
        self.rnd = 3
        self.copies = [0] * len(self.comp_costs)
        self.pool = [POOL_SIZE[c - 1] for c in self.comp_costs]
        return self.state()

    # --- 내부 계산 -------------------------------------------------------

    @staticmethod
    def _stars(copies):
        """모은 매수 -> 별 등급. 3장이면 2성, 9장이면 3성."""
        if copies >= 9:
            return 3
        if copies >= 3:
            return 2
        return 1 if copies >= 1 else 0

    def board_value(self):
        """보유 유닛 중 가치 상위 (레벨)개만 보드에 올린다고 보고 합산."""
        values = sorted(
            (COST_STAR_VALUE[self.comp_costs[i] - 1][self._stars(self.copies[i]) - 1]
             for i in range(len(self.comp_costs)) if self.copies[i] > 0),
            reverse=True)
        return sum(values[:self.level])

    def star_counts(self):
        counts = {1: 0, 2: 0, 3: 0}
        for i in range(len(self.comp_costs)):
            star = self._stars(self.copies[i])
            if star:
                counts[star] += 1
        return counts

    def interest(self):
        return min(self.gold // 10, MAX_INTEREST)

    def state(self):
        counts = self.star_counts()
        return [self.gold / 60.0,
                self.level / 9.0,
                self.rnd / self.n_rounds,
                self.board_value() / 120.0,
                counts[2] / 8.0,
                counts[3] / 8.0]

    def _roll_once(self):
        """상점 한 번 새로고침(2골드). 슬롯 5칸을 레벨 확률표대로 굴린다."""
        self.gold -= 2
        odds = LEVEL_ODDS[self.level]
        for _ in range(5):
            r = random.random()
            cost = 5
            for tier in range(5):
                if r < odds[tier]:
                    cost = tier + 1
                    break
            # 이 코스트에서 내 조합에 필요하고 아직 덜 모은 유닛
            candidates = [i for i in range(len(self.comp_costs))
                          if self.comp_costs[i] == cost and self.copies[i] < 9 and self.pool[i] > 0]
            if not candidates:
                continue
            # 해당 코스트 전체 풀에서 내가 원하는 유닛이 뜰 확률
            denom = POOL_SIZE[cost - 1] * UNIQUE_PER_COST[cost - 1]
            for i in candidates:
                if random.random() < self.pool[i] / denom:
                    if self.gold >= cost:
                        self.gold -= cost
                        self.copies[i] += 1
                        self.pool[i] -= 1
                    break

    # --- 한 라운드 -------------------------------------------------------

    def step(self, action_idx):
        before = self.board_value()
        action = ACTIONS[action_idx]

        if action == 'LEVEL':
            for _ in range(3):
                if self.gold >= 4 and self.level < 9:
                    self.gold -= 4
                    self.exp += 4
        elif action == 'ROLL50':
            while self.gold > 52:
                self._roll_once()
        elif action == 'ROLLHARD':
            while self.gold >= 12:
                self._roll_once()

        # 패시브 경험치는 행동과 무관하게 매 라운드 들어온다.
        # 이 때문에 "특정 레벨에 머무는" 전략은 시간이 지나면 유지되지 않는다.
        self.exp += PASSIVE_XP
        while self.level < 9 and self.exp >= LEVEL_XP.get(self.level, 10 ** 9):
            self.exp -= LEVEL_XP[self.level]
            self.level += 1

        self.gold += 5 + self.interest()
        self.rnd += 1

        reward = {'board': self.board_value() - before, 'econ': self.interest()}
        done = self.rnd > self.n_rounds
        return self.state(), reward, done


# 비교용 수동 정책들. 학습 결과를 이 기준선과 대조한다.
HAND_POLICIES = {
    'always_save': lambda env: 0,
    'fast8':       lambda env: 1 if env.level < 8 else 3,
    'slowroll':    lambda env: 3 if env.level >= 6 else 0,
    'random':      lambda env: random.randint(0, len(ACTIONS) - 1),
}


if __name__ == '__main__':
    import statistics

    def run(policy, n=500):
        env = EconEnv()
        out = []
        for _ in range(n):
            env.reset()
            done = False
            while not done:
                _, _, done = env.step(policy(env))
            out.append(env.board_value())
        return statistics.mean(out)

    print('정책별 최종 board_value (n=500)')
    for name, policy in HAND_POLICIES.items():
        print(f'  {name:12} {run(policy):6.1f}')
