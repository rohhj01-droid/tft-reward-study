"""
시뮬레이터(june)의 전투 제한 시간과 연장전을 실제 Set 4와 대조한다.

기대값의 출처(위키 TFT 패치 기록, 10.19~10.25 공식 노트에는 바뀐 줄이 없다):
  TFT:V9.16 URF 연장전: 전투 30초가 지나면 비기는 대신 15초 동안 연장전. 공격 속도 300%, 스킬 피해 200%,
            군중 제어 지속 시간 66% 감소, 회복 66% 감소. 그 뒤에도 끝나지 않으면 비김.
  TFT:V10.8: 연장전에서 보호막도 66% 약해진다(회복과 같다).
"300%", "200%"는 세 배, 두 배로 본다. 비겼을 때 받는 플레이어 피해는 Set 4 자료를 못 찾아 대조하지 않는다.

서로 행동하지 않는 가렌 1 대 1로 끝나지 않는 전투를 만든다. 전투가 끝나는 시각과 결과를 보고, 30초 전(20초대)과
연장전(31초대)에 같은 일을 시켜 결과를 비교한다: 공격 속도, 스킬 피해 100, 1초 기절, 회복 100, 보호막 100.

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
REDUCED = round(1 - 0.66, 2)


def dummy_fight():
    """가렌 1 대 1. 둘 다 target_dummy라 행동하지 않아 제한 시간까지 간다. 정해 둔 시각에 일을 시키고 결과를 적는다."""
    p1, p2 = Player(pool(), 0), Player(pool(), 1)
    for p in (p1, p2):
        p.board[3][0] = cm.champion('garen', stars=2, target_dummy=True)
        p.board[3][0].x, p.board[3][0].y = 3, 0
    sim_config.WARLORD_WINS['blue'] = sim_config.WARLORD_WINS['red'] = 0
    out, mem = {}, {}

    def at(t):
        me, foe = cm.blue[0], cm.red[0]
        phase = '전' if t < 30000 else '연장'
        base = 20000 if t < 30000 else 31000
        step = t - base
        if step == 0:          # 공격 속도, 스킬 피해 100
            out[f'공속_{phase}'] = me.AS
            mem['h'] = foe.health
            me.spell(foe, 100)
            out[f'스킬피해_{phase}'] = round(mem['h'] - foe.health, 2)
        elif step == 500:      # 아이템 피해 100은 스킬이 아니라 그대로여야 한다
            mem['h'] = foe.health
            me.spell(foe, 100, item_damage=True)
            out[f'아이템피해_{phase}'] = round(mem['h'] - foe.health, 2)
        elif step == 1000:     # 1초 기절
            foe.add_que('change_stat', -1, None, 'stunned', True)
            foe.add_que('change_stat', 1000, None, 'stunned', False)
        elif step == 1400:
            out[f'기절_{phase}'] = foe.stunned
        elif step == 2000:     # 회복 100
            me.health -= 300
            mem['h'] = me.health
            me.add_que('heal', -1, None, None, 100)
        elif step == 2100:
            out[f'회복_{phase}'] = round(me.health - mem['h'], 2)
        elif step == 3000:     # 보호막 100. 만료를 달아야 같은 양의 앞 보호막을 '갱신'으로 지우지 않는다
            mem['s'] = me.shield_amount()
            me.add_que('shield', 0, None, None, {'amount': 100, 'identifier': t, 'applier': me, 'original_amount': 100},
                       {'increase': True, 'expires': 5000})
            out[f'보호막_{phase}'] = round(me.shield_amount() - mem['s'], 2)

    hooks = {base + s for base in (20000, 31000) for s in (0, 500, 1000, 1400, 2000, 2100, 3000)}
    real_inc = cm.MILLISECONDS_INCREASE

    def inc():
        real_inc()
        if cf.MILLIS() in hooks and cm.blue and cm.red:
            at(cf.MILLIS())

    cm.MILLISECONDS_INCREASE = inc
    try:
        idx, _ = cm.run(cm.champion, p1, p2, 0)
    finally:
        cm.MILLISECONDS_INCREASE = real_inc
    out['끝'] = cf.MILLIS() / 1000
    out['결과'] = idx
    return out


def ratio(out, key):
    a, b = out.get(f'{key}_전'), out.get(f'{key}_연장')
    if a is None or b is None:
        return '연장전 전에 끝남'
    return round(b / a, 2) if a else '0으로 나눔'


def main():
    rows, cells = [], 0
    for patch in PATCHES:
        pm.apply_patch(patch)
        o = dummy_fight()
        end = 45 if abs(o['끝'] - 45) <= TICK / 1000 else round(o['끝'], 1)
        checks = [
            ('끝나지 않는 전투가 끝나는 시각(초)', 45, end),
            ('그때 결과(0은 비김)', 0, o['결과']),
            ('연장전 공격 속도 배수(300%)', 3.0, ratio(o, '공속')),
            ('연장전 스킬 피해 배수(200%)', 2.0, ratio(o, '스킬피해')),
            ('연장전 아이템 피해 배수(스킬이 아니라 그대로)', 1.0, ratio(o, '아이템피해')),
            ('30초 전 1초 기절이 0.4초 뒤에도 걸려 있음', True, o.get('기절_전')),
            ('연장전 1초 기절이 0.4초 뒤에는 풀림(0.34초)', False, o.get('기절_연장')),
            ('연장전 회복 배수(66% 감소)', REDUCED, ratio(o, '회복')),
            ('연장전 보호막 배수(66% 감소, 10.8)', REDUCED, ratio(o, '보호막')),
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
        print(f'  {r[0]:7}{r[1]:36} 기대 {str(r[2]):8} 시뮬 {r[3]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
