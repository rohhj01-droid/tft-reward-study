"""
TFT 경제 의사결정 환경.

전투를 안 돌린다. 보드 강도를 board_value = Σ(코스트 × 3^(별-1)) 로 근사하고,
"제한된 골드를 레벨업과 리롤에 어떻게 나눠 쓸 것인가"만 떼어내 학습시킨다.
상점 확률, 풀, 레벨 비용은 시뮬레이터 값 그대로다(set4.py).
보상은 스칼라가 아니라 {board, econ} dict로 나간다. 학습기가 요인별 헤드로 나눠 받는다.
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

    ROLL50은 이자를 안 깨는 선에서만 리롤한다는 뜻인데 완전히 지켜지지는 않는다.
    새로고침 2골드 말고 유닛 값도 같이 나가서 한 번에 50 밑으로 떨어질 때가 있다.
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

    @staticmethod
    def _stars(copies):
        if copies >= 9:
            return 3
        if copies >= 3:
            return 2
        return 1 if copies >= 1 else 0

    def board_value(self):
        """보유 유닛 중 가치 상위 (레벨)개만 보드에 올린다고 보고 합산.

        시너지도 유닛 수도 안 센다. 이 환경에서 최적인 정책이 실제 게임에서는
        등수가 더 나빴던 원인이 여기다.
        """
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
        # 나누는 값은 관측된 최댓값 근처로 잡은 것뿐이다. 클리핑을 안 하므로
        # 골드가 60을 넘으면 1보다 큰 값이 그대로 망에 들어간다.
        return [self.gold / 60.0,
                self.level / 9.0,
                self.rnd / self.n_rounds,
                self.board_value() / 120.0,
                counts[2] / 8.0,
                counts[3] / 8.0]

    def _roll_once(self):
        """상점 한 번 새로고침. 슬롯 5칸을 레벨 확률표대로 굴린다."""
        self.gold -= 2
        odds = LEVEL_ODDS[self.level]
        for _ in range(5):
            r = random.random()
            cost = 5
            for tier in range(5):
                if r < odds[tier]:
                    cost = tier + 1
                    break
            candidates = [i for i in range(len(self.comp_costs))
                          if self.comp_costs[i] == cost and self.copies[i] < 9 and self.pool[i] > 0]
            if not candidates:
                continue
            # 해당 코스트 전체 풀에서 내가 원하는 유닛이 뜰 확률
            denom = POOL_SIZE[cost - 1] * UNIQUE_PER_COST[cost - 1]
            # 한 슬롯에는 유닛이 하나만 뜬다. 그래서 후보를 다 굴리지 않고 break로 끊는다.
            # 골드가 모자라면 떴는데도 못 사고 슬롯을 버린다. 실제 게임과 같은 동작이다.
            for i in candidates:
                if random.random() < self.pool[i] / denom:
                    if self.gold >= cost:
                        self.gold -= cost
                        self.copies[i] += 1
                        self.pool[i] -= 1
                    break

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

        # 라운드 기본 수입 5. 연승/연패 보너스는 안 넣었다.
        self.gold += 5 + self.interest()
        self.rnd += 1

        # board 증가분은 3성이 뜨는 라운드에 한 번에 10 이상 뛴다.
        # 스케일 조정 없이 그대로 넣으면 board 헤드의 Q가 발산한다.
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
