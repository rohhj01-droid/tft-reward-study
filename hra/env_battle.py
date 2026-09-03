"""
전투를 붙인 경제 환경.

hra/env.py는 board_value라는 대리 지표만 본다. board_value는 시너지도 유닛 수도
세지 않아서, 이 값 기준으로 최적인 보드가 실제 전투에서는 지는 일이 생긴다.
그 간극을 눈으로 보려고 만든 환경이다. 에피소드 마지막에 전투를 한 번 돌려
승패를 board / econ 옆에 win 요인으로 붙인다.

시뮬레이터 저장소가 필요하다(README 참고).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import (LEVEL_ODDS, COST_STAR_VALUE, POOL_SIZE, UNIQUE_PER_COST,
                  LEVEL_XP, PASSIVE_XP, MAX_INTEREST)
from analysis.battle import battle, to_units
from analysis.comps import COMPS
from hra.env import ACTIONS

DEFAULT_COMP = COMPS['low_coherent']
_NAMES = [n for n, _ in DEFAULT_COMP]

# 난이도 사다리. 어느 수준의 상대까지 이기는지로 학습 상태를 본다.
# hard는 유닛을 더 붙이는 대신 앞 유닛 하나를 3성으로 올렸다. 유닛 수에 지는지
# 별 등급에 지는지 갈라 보려고 그렇게 나눴다.
LADDER = {
    'easy':   [{'name': n, 'stars': 2, 'items': []} for n in _NAMES[:6]],
    'medium': [{'name': n, 'stars': 2, 'items': []} for n in _NAMES[:8]],
    'hard':   [{'name': n, 'stars': 3 if i == 0 else 2, 'items': []}
               for i, n in enumerate(_NAMES[:7])],
}
TIERS = list(LADDER)


class BattleEconEnv:
    """상대는 매 판 LADDER에서 무작위로 뽑는다. opponent를 주면 그 보드로 고정한다."""

    def __init__(self, comp=DEFAULT_COMP, opponent=None, n_rounds=24, fixed_tier=None):
        self.comp = list(comp)
        self.names = [n for n, _ in self.comp]
        self.costs = [c for _, c in self.comp]
        self.opponent = opponent
        self.fixed_tier = fixed_tier
        self.n_rounds = n_rounds

    def reset(self):
        self.gold, self.level, self.exp, self.rnd = 2, 3, 0, 3
        self.copies = [0] * len(self.comp)
        self.pool = [POOL_SIZE[c - 1] for c in self.costs]
        self.tier = self.fixed_tier or random.choice(TIERS)
        return self.state()

    # _stars / board_value / interest / state 는 hra/env.py와 같은 계산이다.
    # 여기 comp는 코스트만이 아니라 이름까지 들고 있어야 해서 상속으로 묶지 않고 복사했다.
    @staticmethod
    def _stars(copies):
        return 3 if copies >= 9 else 2 if copies >= 3 else (1 if copies >= 1 else 0)

    def board_value(self):
        values = sorted((COST_STAR_VALUE[self.costs[i] - 1][self._stars(self.copies[i]) - 1]
                         for i in range(len(self.comp)) if self.copies[i] > 0), reverse=True)
        return sum(values[:self.level])

    def board_spec(self):
        # 정렬 기준과 자르는 개수를 board_value()와 똑같이 맞춰야 한다. 어긋나면
        # 보상이 재는 보드와 실제로 싸우는 보드가 달라진다.
        units = [(COST_STAR_VALUE[self.costs[i] - 1][self._stars(self.copies[i]) - 1],
                  self.names[i], self._stars(self.copies[i]))
                 for i in range(len(self.comp)) if self.copies[i] > 0]
        units.sort(reverse=True)
        return [{'name': n, 'stars': s, 'items': []} for _, n, s in units[:self.level]]

    def interest(self):
        return min(self.gold // 10, MAX_INTEREST)

    def state(self):
        counts = {1: 0, 2: 0, 3: 0}
        for i in range(len(self.comp)):
            star = self._stars(self.copies[i])
            if star:
                counts[star] += 1
        return [self.gold / 60., self.level / 9., self.rnd / self.n_rounds,
                self.board_value() / 120., counts[2] / 8., counts[3] / 8.]

    def _roll_once(self):
        self.gold -= 2
        odds = LEVEL_ODDS[self.level]
        for _ in range(5):
            r = random.random()
            cost = 5
            for tier in range(5):
                if r < odds[tier]:
                    cost = tier + 1
                    break
            candidates = [i for i in range(len(self.comp))
                          if self.costs[i] == cost and self.copies[i] < 9 and self.pool[i] > 0]
            if not candidates:
                continue
            denom = POOL_SIZE[cost - 1] * UNIQUE_PER_COST[cost - 1]
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

        self.exp += PASSIVE_XP
        while self.level < 9 and self.exp >= LEVEL_XP.get(self.level, 10 ** 9):
            self.exp -= LEVEL_XP[self.level]
            self.level += 1
        self.gold += 5 + self.interest()
        self.rnd += 1

        done = self.rnd > self.n_rounds
        win = 0
        if done:
            spec = self.board_spec()
            if spec:
                enemy = self.opponent if self.opponent is not None else LADDER[self.tier]
                # battle()은 1=A승, 2=B승, 0=무승부다. 무승부는 패로 친다.
                # analysis/battle.py의 win_rate와 달리 좌우를 바꾸지 않는다. 내 보드가
                # 항상 A 자리라 진영 유리가 섞인다. 절대 승률 말고 티어 간 비교로 읽어야 한다.
                win = 10 if battle(to_units(spec), to_units(enemy)) == 1 else 0

        return self.state(), {'board': self.board_value() - before,
                              'econ': self.interest(),
                              'win': win}, done
