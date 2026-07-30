"""
전투를 연결한 경제 환경.

hra/env.py 는 board_value(대리 지표)만 본다. 이 파일은 에피소드 마지막에 실제 전투를
한 번 돌려 승패를 보상 요인으로 추가한다. 요인이 board / econ / win 세 개가 된다.

board_value 는 시너지와 유닛 수를 세지 않는다. 그래서 board_value 기준으로 최적인
보드가 실제 전투에서는 지는 경우가 생긴다. 이 환경은 그 차이를 확인하기 위한 것이다.

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

# 난이도 사다리. 상대를 바꿔가며 어느 수준까지 이길 수 있는지 본다.
LADDER = {
    'easy':   [{'name': n, 'stars': 2, 'items': []} for n in _NAMES[:6]],
    'medium': [{'name': n, 'stars': 2, 'items': []} for n in _NAMES[:8]],
    'hard':   [{'name': n, 'stars': 3 if i == 0 else 2, 'items': []}
               for i, n in enumerate(_NAMES[:7])],
}
TIERS = list(LADDER)


class BattleEconEnv:
    """
    comp     : [(챔피언 이름, 코스트), ...]
    opponent : 고정 상대 보드 스펙. None이면 LADDER에서 매 판 무작위로 고른다.
    """

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

    @staticmethod
    def _stars(copies):
        return 3 if copies >= 9 else 2 if copies >= 3 else (1 if copies >= 1 else 0)

    def board_value(self):
        values = sorted((COST_STAR_VALUE[self.costs[i] - 1][self._stars(self.copies[i]) - 1]
                         for i in range(len(self.comp)) if self.copies[i] > 0), reverse=True)
        return sum(values[:self.level])

    def board_spec(self):
        """전투에 넘길 보드. 가치 높은 순으로 레벨 수만큼 자른다."""
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
                win = 10 if battle(to_units(spec), to_units(enemy)) == 1 else 0

        return self.state(), {'board': self.board_value() - before,
                              'econ': self.interest(),
                              'win': win}, done
