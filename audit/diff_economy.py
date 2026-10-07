"""
시뮬레이터(june)의 경제 규칙을 실제 Set 4와 대조한다.

기대값의 출처:
  위키 TFT:Gold 2020-09-19 판(Set 4 진행 중):
      기본 수입은 계획 단계마다 5. 게임의 2/3/4/5번째 라운드(1-2, 1-3, 1-4, 2-1)는 2/2/3/4.
      이자는 기본 수입 전 골드 10당 1, 최대 5. 연승·연패는 2~3이면 +1, 4면 +2, 5 이상이면 +3.
      대전에서 이기면 +1. 연승·연패 골드는 PvE 라운드에도 준다(10.6).
      판매(10.12): 1성과 1코스트는 산 값 그대로, 나머지는 1골드 덜.
  위키 TFT:Experience 2020-09-21 판: 4골드에 4경험치, 라운드가 끝날 때마다 2경험치, 레벨 2는 첫 웨이브 뒤.
  공식 10.19: 선택받은 자는 처음부터 2성이라 1성 가격의 세 배.
  공식 노트 10.19~10.25에는 수입, 이자, 연승, 경험치 규칙을 바꾼 줄이 없다.
가정: 회전초밥 라운드(x-4)는 계획 단계가 없어 수입과 경험치가 따로 없다. 시뮬레이터도 회전초밥을 x-5와
한 칸으로 묶는다.

두 가지를 잰다.
  1) 게임 흐름: 실제 환경(tft_simulator)을 8명 모두 넘기기만 하게 돌리고, 계획 단계가 시작될 때마다
     player_0의 골드, 레벨, 경험치를 기록한다. 전투 함수는 가짜로 바꿔 player_0이 대전에서 늘 이기거나
     늘 지게 하고, PvE는 늘 지게 해서 전리품이 섞이지 않게 한다. 같은 조건을 위 규칙으로 계산해 비교한다.
  2) 행동 하나씩: 경험치 구매, 새로고침, 챔피언 구매(선택받은 자 포함), 판매, 이자 상한, 연승 골드.

    PYTHONPATH=<june> python audit/diff_economy.py

결과: audit/mismatch_economy.csv (일치한 칸은 쓰지 않는다)
"""
import csv
import os

import numpy as np

import Simulator.champion as champion_module
import Simulator.config as sim_config
from Simulator.champion import champion
from Simulator.observation.token.basic_observation import ObservationToken
from Simulator.player import Player
from Simulator.pool import pool
from Simulator.tft_simulator import TFTConfig, parallel_env

HERE = os.path.dirname(os.path.abspath(__file__))
LEVEL_XP = {1: 2, 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 56, 8: 80}  # 레벨 2는 첫 웨이브 뒤라 2로 둔다
PASSIVE = {'1-2': 2, '1-3': 2, '1-4': 3, '2-1': 4}  # 그 밖은 5
LAST = '4-1'  # 흐름은 여기까지 비교한다. 그 뒤는 이자가 5로 차서 차이가 그대로 이어진다
SRC_GOLD = '위키 TFT:Gold 2020-09'
SRC_XP = '위키 TFT:Experience 2020-09'


def label(i):
    """game_rounds 칸 번호의 계획 단계 이름. 칸 0은 1-1 회전초밥 + 1-2, x-4 회전초밥은 x-5와 한 칸이다."""
    if i < 3:
        return ['1-2', '1-3', '1-4'][i]
    s, pos = 2 + (i - 3) // 6, (i - 3) % 6
    return f'{s}-{[1, 2, 3, 5, 6, 7][pos]}'


def planning_labels():
    out = ['1-2', '1-3', '1-4']
    for s in range(2, 5):
        out += [f'{s}-{r}' for r in (1, 2, 3, 5, 6, 7)]
    return out[:out.index(LAST) + 1]


def streak_gold(n):
    return 0 if n < 2 else 1 if n <= 3 else 2 if n == 4 else 3


def level_up(level, exp):
    while level < 9 and exp >= LEVEL_XP[level]:
        exp -= LEVEL_XP[level]
        level += 1
    return level, exp


def expected_flow(win):
    """규칙대로 계산한 계획 단계 시작 때의 (골드, 레벨, 경험치). 아무것도 사지 않는다."""
    gold, level, exp, ws, ls = 0, 1, 0, 0, 0
    out = {}
    for lab in planning_labels():
        gold += min(gold // 10, 5) + PASSIVE.get(lab, 5) + streak_gold(max(ws, ls))
        out[lab] = (gold, level, exp)
        stage, r = map(int, lab.split('-'))
        if stage >= 2 and r != 7:  # 대전
            if win:
                gold, ws, ls = gold + 1, ws + 1, 0
            else:
                ls, ws = ls + 1, 0
        level, exp = level_up(level, exp + 2)  # 라운드가 끝날 때마다 2
    return out


def sim_flow(win):
    """실제 환경을 돌려 계획 단계 시작 때 player_0의 (골드, 레벨, 경험치)를 기록한다."""
    def fake_run(champ_cls, p1, p2, round_damage=0):
        if p1.player_num == -1 or p2.player_num == -1:
            return (1, 0) if p1.player_num == -1 else (2, 0)  # PvE는 플레이어가 진다. 전리품이 없다
        if p1.player_num == 0:
            return (1 if win else 2), 0
        if p2.player_num == 0:
            return (2 if win else 1), 0
        return 0, 0

    snaps = {}
    real_run, real_start, real_log = champion_module.run, Player.start_round, sim_config.LOGMESSAGES

    def record(self, t_round):
        real_start(self, t_round)
        if self.player_num == 0:
            snaps[label(t_round)] = (self.gold, self.level, self.exp)

    # 로그를 끈다. 켜 두면 실행한 폴더에 log.txt가 생긴다
    champion_module.run, Player.start_round, sim_config.LOGMESSAGES = fake_run, record, False
    try:
        env = parallel_env(TFTConfig(observation_class=ObservationToken, max_actions_per_round=1))
        obs, info = env.reset()
        p0 = info['player_0']['player']
        snaps['1-3'] = (p0.gold, p0.level, p0.exp)  # reset 뒤 첫 계획 단계(칸 1)
        while obs and len(snaps) < len(planning_labels()) + 2:
            obs, _, _, _, _ = env.step({a: np.array([0, 0, 0]) for a in obs})
    finally:
        champion_module.run, Player.start_round, sim_config.LOGMESSAGES = real_run, real_start, real_log
    return snaps


def fresh():
    return Player(pool(), 0)


def gold_delta(p, act):
    before = p.gold
    act(p)
    return before - p.gold


def actions():
    rows, cells = [], 0

    def check(item, exp, sim, src):
        nonlocal cells
        cells += 1
        if exp != sim:
            rows.append(['행동', item, '', exp, sim, src])

    p = fresh()
    p.gold, p.level = 10, 3
    xp_before = p.exp + sum(LEVEL_XP[lv] for lv in range(1, p.level))
    paid = gold_delta(p, lambda q: q.buy_exp_action())
    xp_after = p.exp + sum(LEVEL_XP[lv] for lv in range(1, p.level))
    check('경험치 구매 비용', 4, paid, SRC_XP)
    check('경험치 구매로 얻는 경험치', 4, xp_after - xp_before, SRC_XP)

    p = fresh()
    p.gold = 10
    check('새로고침 비용', 2, gold_delta(p, lambda q: q.refresh_shop_action()), '위키 TFT:Gold 2020-09(상점)')

    one_per_cost = {1: ('garen', 'vanguard'), 2: ('jax', 'duelist'), 3: ('kennen', 'ninja'),
                    4: ('riven', 'keeper'), 5: ('sett', 'brawler')}
    for c, (name, trait) in one_per_cost.items():
        p = fresh()
        p.gold = 100
        check(f'{c}코스트 구매 가격', c, gold_delta(p, lambda q: q.buy_champion(champion(name))), '1성 가격')
        p = fresh()
        p.gold = 100
        check(f'{c}코스트 선택받은 자 구매 가격', 3 * c,
              gold_delta(p, lambda q: q.buy_champion(champion(name, chosen=trait))), '공식 10.19')
        for stars in (1, 2, 3):
            p = fresh()
            p.add_to_bench(champion(name, stars=stars))
            idx = next(i for i, u in enumerate(p.bench) if u)
            full = c * 3 ** (stars - 1)
            exp = full if (stars == 1 or c == 1) else full - 1
            check(f'{c}코스트 {stars}성 판매', exp, -gold_delta(p, lambda q: q.sell_from_bench(idx)),
                  '위키 TFT:Gold 10.12')

    # 이자: 골드 80일 때와 0일 때 수입 차이. 초반(칸 4 이하)과 그 뒤를 따로 본다
    for t in (2, 4, 10):
        a, b = fresh(), fresh()
        a.gold, b.gold = 80, 0
        a.gold_income(t)
        b.gold_income(t)
        check(f'골드 80일 때 이자({label(t)} 계획 단계)', 5, (a.gold - 80) - b.gold, SRC_GOLD)

    for kind in ('win', 'loss'):
        for n in range(7):
            p = fresh()
            setattr(p, f'{kind}_streak', n)
            p.gold_income(10)
            name = '연승' if kind == 'win' else '연패'
            check(f'{name} {n}일 때 골드', streak_gold(n), p.gold - 5, SRC_GOLD)

    p = fresh()
    p.opponent = fresh()
    before = p.gold
    p.won_round(0)
    check('대전 승리 골드', 1, p.gold - before, SRC_GOLD)
    return rows, cells


def main():
    rows, cells = [], 0
    for win in (True, False):
        scenario = '흐름(대전 늘 이김)' if win else '흐름(대전 늘 짐)'
        exp, sim = expected_flow(win), sim_flow(win)
        for lab in planning_labels():
            for k, field in enumerate(('골드', '레벨', '경험치')):
                cells += 1
                e = exp[lab][k]
                s = sim[lab][k] if lab in sim else '계획 단계 없음'
                if e != s:
                    rows.append([scenario, field, lab, e, s, SRC_XP if k else SRC_GOLD])
    r, c = actions()
    rows += r
    cells += c

    path = os.path.join(HERE, 'mismatch_economy.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['scenario', 'field', 'round', 'expected', 'sim', 'source'])
        w.writerows(rows)
    print(f'\n비교한 칸 {cells}개, 불일치 {len(rows)}개')
    for row in rows:
        print(f'  {row[0]:12}{row[1]:24}{row[2]:5} 기대 {str(row[3]):10} 시뮬 {row[4]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
