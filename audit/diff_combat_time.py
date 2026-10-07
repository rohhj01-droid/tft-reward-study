"""
시뮬레이터(june)의 전투 제한 시간과 연장전을 실제 Set 4와 대조한다.

기대값의 출처(위키 TFT 패치 기록, 10.19~10.25 공식 노트에는 바뀐 줄이 없다):
  TFT:V9.16 URF 연장전: 전투 30초가 지나면 비기는 대신 15초 동안 연장전. 공격 속도 300%, 스킬 피해 200%,
            군중 제어 지속 시간 66% 감소, 회복 66% 감소. 그 뒤에도 끝나지 않으면 비김.
  TFT:V10.8: 연장전에서 보호막도 66% 약해진다(회복과 같다).
비겼을 때 받는 플레이어 피해는 Set 4 자료를 못 찾아 대조하지 않는다.

공격하지 않는 모래 병사끼리 붙여 끝나지 않는 전투를 만들고, 전투가 끝나는 시각과 결과, 25초와 35초의
공격 속도를 잰다.

    PYTHONPATH=<june> python audit/diff_combat_time.py

결과: audit/mismatch_combat_time.csv (일치한 칸은 쓰지 않는다)
"""
import csv
import os

import Simulator.champion as cm
import Simulator.champion_functions as cf
import Simulator.config as sim_config
import Simulator.patch_manager as pm
from Simulator.player import Player
from Simulator.pool import pool

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']
TICK = 25  # 시뮬레이터 전투 시계가 한 번에 가는 밀리초


def dummy_fight():
    """모래 병사 1 대 1. 둘 다 공격하지 않아 제한 시간까지 간다."""
    p1, p2 = Player(pool(), 0), Player(pool(), 1)
    for p in (p1, p2):
        p.board[3][0] = cm.champion('sandguard', target_dummy=True)
        p.board[3][0].x, p.board[3][0].y = 3, 0
    sim_config.WARLORD_WINS['blue'] = sim_config.WARLORD_WINS['red'] = 0
    snaps = {}
    real_inc = cm.MILLISECONDS_INCREASE

    def inc():
        real_inc()
        if cf.MILLIS() in (25000, 35000) and cm.blue:
            snaps[cf.MILLIS()] = cm.blue[0].AS

    cm.MILLISECONDS_INCREASE = inc
    try:
        idx, damage = cm.run(cm.champion, p1, p2, 0)
    finally:
        cm.MILLISECONDS_INCREASE = real_inc
    return idx, cf.MILLIS() / 1000, snaps


def main():
    rows, cells = [], 0
    for patch in PATCHES:
        pm.apply_patch(patch)
        idx, end, snaps = dummy_fight()
        checks = [
            ('끝나지 않는 전투가 끝나는 시각(초)', 45, round(end, 1) if abs(end - 45) > TICK / 1000 else 45),
            ('그때 결과(0은 비김)', 0, idx),
            ('35초 공격 속도 / 25초 공격 속도(연장전 300%)', 3.0,
             round(snaps[35000] / snaps[25000], 2) if 25000 in snaps and 35000 in snaps else '35초 전에 끝남'),
        ]
        for what, exp, sim in checks:
            cells += 1
            if exp != sim:
                rows.append([patch, what, exp, sim, '위키 TFT:V9.16, V10.8'])
    path = os.path.join(HERE, 'mismatch_combat_time.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['patch', 'field', 'expected', 'sim', 'source'])
        w.writerows(rows)
    print(f'\n비교한 칸 {cells}개, 불일치 {len(rows)}개')
    for r in rows:
        print(f'  {r[0]:7}{r[1]:40} 기대 {str(r[2]):8} 시뮬 {r[3]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
