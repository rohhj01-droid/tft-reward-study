"""
시뮬레이터(june)의 플레이어 피해를 실제 Set 4와 패치별로 대조한다.

전투에서 지면 받는 피해 = 스테이지 기본 피해 + 살아남은 적 유닛 수에 따른 피해.
기대값의 출처:
  공식: 라이엇 공식 패치노트. 10.19~10.25에서 플레이어 피해가 바뀐 건 두 번뿐이다.
        10.22 "Players now take a minimum of 1 damage on losses"
        10.24 "Base Player Damage Per Stage: 0/0/1/2/5/10/15 ⇒ 0/0/2/3/5/8/15"
  위키 패치 기록 TFT:V10.8: 스테이지 기본 피해 0/0/1/2/5/10/15,
        살아남은 유닛 피해 2/4/6/8/10/11/12/13/14/15/... (10.9~10.23 사이 변경 없음)
  위키 TFT:Monster 2020-09-21 판(Set 4 진행 중): PvE에서 져도 일반 라운드처럼 피해를 받는다.

시뮬레이터 값은 표를 옮겨 적지 않고 실제 함수를 불러서 잰다. 라운드 진행 함수
(Game_Round.combat_phase, minion.minion_round)를 부르고, 전투 함수 champion.run만 가짜로 바꿔
넘어오는 기본 피해와 플레이어 체력 변화를 기록한다.

    PYTHONPATH=<june> python audit/diff_stage_damage.py

결과: audit/mismatch_stage_damage.csv (일치한 칸은 쓰지 않는다)
"""
import csv
import os

import Simulator.champion as champion_module
import Simulator.game_round as gr
import Simulator.minion as minion
import Simulator.patch_manager as pm
from Simulator.stats import DAMAGE_PER_UNIT

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']

# 스테이지 1~7의 기본 피해. 스테이지 8은 자료가 없어 마지막 값으로 본다.
BASE_OLD = [0, 0, 1, 2, 5, 10, 15]
BASE_1024 = [0, 0, 2, 3, 5, 8, 15]
BASE = {p: (BASE_1024 if p == '10.24' else BASE_OLD) for p in PATCHES}
BASE_SRC = {p: ('공식 10.24' if p == '10.24' else '위키 V10.8, 공식 10.24 변경 전 값') for p in PATCHES}
UNIT = [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15]  # 살아남은 유닛 0~10명
MIN_ONE_FROM = '10.22'
PVE_SURVIVORS = 3  # PvE 패배 확인용: 몬스터 3마리가 살아남았다고 친다


class FakePlayer:
    """combat_phase와 minion_combat이 쓰는 속성만 가진 플레이어."""

    def __init__(self, num):
        self.player_num = num
        self.health = 100
        self.win_streak = 0
        self.opponent = None
        self.combat = False
        self.start_time = 0

    def loss_round(self, damage):
        pass

    def won_round(self, damage):
        pass

    def spill_reward(self, damage):
        pass

    def end_turn_actions(self):
        pass


def expected_base(patch, stage):
    table = BASE[patch]
    return table[min(stage, len(table)) - 1]


def round_table(g):
    """game_rounds 칸마다 (칸 번호, 스테이지, 라운드 이름, 종류). 종류는 칸에 든 함수 이름으로 정한다.
    실제 Set 4: 스테이지 1은 1-1 회전초밥과 1-2~1-4 몬스터, 2부터는 x-1~x-3 대전, x-4 회전초밥,
    x-5·x-6 대전, x-7 몬스터."""
    out = []
    for i, fns in enumerate(g.game_rounds):
        names = [f.__name__ for f in fns]
        kind = 'PvP' if 'combat_round' in names else 'PvE'
        if i < 3:
            stage, label = 1, ['1-2', '1-3', '1-4'][i]  # 0번 칸은 1-1 회전초밥 + 1-2 몬스터
            assert kind == 'PvE', (i, names)
        else:
            stage, pos = 2 + (i - 3) // 6, (i - 3) % 6
            label = f'{stage}-{[1, 2, 3, 5, 6, 7][pos]}'
            assert (pos == 5) == (kind == 'PvE'), (i, names)  # 칸 배치가 실제 라운드 구조와 같은지
        out.append((i, stage, label, kind))
    return out


def fight(result):
    """champion.run 자리에 넣을 가짜. 넘어온 기본 피해를 기록하고 정해 둔 결과를 돌려준다."""
    seen = []

    def fake_run(champ_cls, p1, p2, round_damage=0):
        seen.append(round_damage)
        return result(round_damage)
    return seen, fake_run


def measure_pvp(g, i, result):
    seen, fake = fight(result)
    champion_module.run = fake
    a, b = FakePlayer(0), FakePlayer(1)
    g.matchups = [['player_0', 'player_1']]
    g.combat_phase({'player_0': a, 'player_1': b}, i)
    return seen[0], 100 - b.health  # 파란 쪽이 이기게 했으니 빨간 쪽 체력 변화가 받은 피해


def measure_pve(i):
    seen, fake = fight(lambda rd: (2, rd + DAMAGE_PER_UNIT[PVE_SURVIVORS]))  # 몬스터 승
    champion_module.run = fake
    p = FakePlayer(0)
    minion.minion_round(p, i, [p])  # game_round의 round_1·minion_round와 같은 인자
    return (seen[0] if seen else None), 100 - p.health


def main():
    gr.log_to_file_start = gr.log_to_file_combat = lambda: None
    g = gr.Game_Round({}, None, None)
    rounds = round_table(g)
    real_run = champion_module.run
    rows, cells = [], 0
    try:
        for patch in PATCHES:
            pm.apply_patch(patch)
            for i, stage, label, kind in rounds:
                exp = expected_base(patch, stage)
                src = BASE_SRC[patch] + (', 스테이지 8은 마지막 값으로 가정' if stage >= 8 else '')
                if kind == 'PvP':
                    rd, _ = measure_pvp(g, i, lambda rd: (1, rd))
                    cells += 1
                    if rd != exp:
                        rows.append([patch, 'PvP 기본 피해', label, exp, rd, src])
                else:
                    rd, taken = measure_pve(i)
                    exp_taken = exp + UNIT[PVE_SURVIVORS]
                    cells += 2
                    if rd != exp:
                        rows.append([patch, 'PvE 기본 피해', label, exp, '싸움 없음' if rd is None else rd, src])
                    if taken != exp_taken:
                        rows.append([patch, f'PvE 패배 피해(몬스터 {PVE_SURVIVORS}마리 생존)', label, exp_taken, taken,
                                     '위키 TFT:Monster 2020-09 판: 일반 라운드처럼 피해를 받는다'])
            # 최소 1 피해: 기본 피해 0인 2-1에서 남은 유닛 없이 지게 한다
            _, taken = measure_pvp(g, 3, lambda rd: (1, 0))
            exp = 1 if not pm.PATCH_NAMES.index(patch) < pm.PATCH_NAMES.index(MIN_ONE_FROM) else 0
            cells += 1
            if taken != exp:
                rows.append([patch, '패배 최소 피해', '2-1', exp, taken, '공식 10.22'])
            for n, exp in enumerate(UNIT):
                cells += 1
                if DAMAGE_PER_UNIT[n] != exp:
                    rows.append([patch, '살아남은 유닛 피해', f'{n}명', exp, DAMAGE_PER_UNIT[n], '위키 V10.8'])
    finally:
        champion_module.run = real_run

    path = os.path.join(HERE, 'mismatch_stage_damage.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['patch', 'field', 'round', 'expected', 'sim', 'source'])
        w.writerows(rows)
    print(f'\n비교한 칸 {cells}개, 불일치 {len(rows)}개')
    for r in rows:
        print(f'  {r[0]:7}{r[1]:26}{r[2]:6} 기대 {str(r[3]):6} 시뮬 {r[4]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
