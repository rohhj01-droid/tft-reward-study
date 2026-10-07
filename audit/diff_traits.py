"""
시뮬레이터(june)의 Set 4 특성 26종 수치를 실제 값과 패치별로 대조한다.

챔피언 대조와 달리 "어느 표에든 같은 숫자가 있으면 일치"로 보지 않는다. 특성마다 시뮬레이터의
어느 표 어느 칸이 무엇인지 정해 두고 그 칸만 비교한다. 기대값은 아래 EXPECTED에 출처와 함께 적었다.
  공식: 라이엇 공식 패치노트 10.20~10.25 (A ⇒ B 줄과 본문 문장)
  위키: LoL 위키 Module:TFTTraitData/data 의 Set 4 항목과 특성 문서의 패치 이력
둘이 다르면 공식을 따른다. 공식끼리도 다른 곳은 AMBIGUOUS로 따로 뺐다.

    PYTHONPATH=<june> python audit/diff_traits.py

결과: audit/mismatch_traits.csv (일치한 칸은 쓰지 않는다)
"""
import copy
import csv
import os

import Simulator.config as sim_config
import Simulator.origin_class_stats as o
import Simulator.patch_manager as pm
import Simulator.stats as champ_stats

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']
COMBAT = '전투 끝까지'


def steps(*pairs):
    """('10.20', a), ('10.23', b) -> 10.20~10.22는 a, 10.23~10.24는 b."""
    out, cur = {}, None
    marks = dict(pairs)
    for p in PATCHES:
        if p in marks:
            cur = marks[p]
        out[p] = cur
    return out


def every(value):
    return steps(('10.20', value))


TIERS = {
    'cultist': [3, 6, 9], 'divine': [2, 4, 6, 8], 'dusk': [2, 4, 6], 'elderwood': [3, 6, 9],
    'enlightened': [2, 4, 6], 'exile': [1, 2], 'fortune': [3, 6], 'ninja': [1, 4], 'spirit': [2, 4],
    'the_boss': [1], 'warlord': [3, 6, 9], 'adept': [2, 3, 4], 'assassin': [2, 4, 6],
    'brawler': [2, 4, 6, 8], 'dazzler': [2, 4], 'duelist': [2, 4, 6, 8], 'emperor': [1],
    'hunter': [2, 3, 4, 5], 'keeper': [2, 4, 6], 'mage': [3, 6, 9], 'mystic': [2, 4, 6],
    'shade': [2, 3, 4], 'sharpshooter': [2, 4, 6], 'tormented': [1],
}

# (특성, 항목, 시뮬레이터 값 읽는 법, 패치별 기대값, 출처). 기대값은 시뮬레이터 표기로 적었다.
EXPECTED = [(t, '발동 인원', lambda t=t: o.tiers[t], every(v), '위키 Set 4 출시') for t, v in TIERS.items()] + [
    ('moonlight', '발동 인원', lambda: o.tiers['moonlight'], steps(('10.20', [3]), ('10.21', [3, 5])),
     '공식 10.21: Moonlight (5) now exists'),
    ('vanguard', '발동 인원', lambda: o.tiers['vanguard'], steps(('10.20', [2, 4, 6]), ('10.21', [2, 4, 6, 8])),
     '공식 10.21: Vanguard Armor 100/250/500 ⇒ 100/250/600/1500'),

    ('spirit', '공속(마나 비용의 %)', lambda: o.AS['spirit'], every([0, 0.35, 0.70]),
     '공식 10.20 핫픽스: Spirit 35/80 ⇒ 35/70. 이후 변경 없음'),
    ('dusk', '아군 전체 주문력', lambda: o.SP_secondary['dusk'], every([0, 0.20, 0.20, 0.40]),
     '공식 10.20: Dusk Team Spell Power 20/20/50 ⇒ 20/20/40'),
    ('dusk', '황혼 유닛 추가 주문력', lambda: o.SP['dusk'], every([0, 0, 0.50, 0.70]),
     '공식 10.20: Dusk Spell Power 0/50/75 ⇒ 0/50/70'),
    ('elderwood', '방어력·마저(2초마다)', lambda: [o.armor['elderwood'], o.MR['elderwood']],
     every([[0, 15, 25, 40], [0, 15, 25, 40]]), '위키 10.19. 10.25에 20/30/40'),
    ('elderwood', '공격력·주문력', lambda: [o.AD['elderwood'], o.SP['elderwood']],
     every([[0, 5, 10, 20], [0, 0.05, 0.10, 0.20]]), '위키 10.19'),
    ('elderwood', '간격', lambda: o.length['elderwood'], every(2000), '위키: Every 2 seconds'),
    ('enlightened', '마나 생성', lambda: o.mana_generation['enlightened'], every([0, 1.40, 1.70, 2.00]),
     '위키 10.19: 40/70/100%'),
    ('exile', '보호막·흡혈', lambda: [o.shield['exile'], o.lifesteal['exile']],
     every([[0, 0.50, 0.50], [0, 0, 0.80]]), '위키 10.19'),
    ('ninja', '공격력·주문력', lambda: [o.AD['ninja'], o.SP['ninja']],
     steps(('10.20', [[0, 50, 120], [0, 0.5, 1.20]]), ('10.21', [[0, 50, 150], [0, 0.5, 1.50]]),
           ('10.22', [[0, 50, 140], [0, 0.5, 1.40]])), '공식 10.21 50/120 ⇒ 50/150, 10.22 150 ⇒ 140'),
    ('warlord', '체력·주문력', lambda: [o.health['warlord'], o.SP['warlord']],
     every([[0, 200, 450, 700], [0, 0.20, 0.40, 0.70]]), '위키 10.19'),
    ('warlord', '승리당 증가·최대', lambda: [o.increasement['warlord'], o.threshold['warlord']],
     every([0.10, 5]), '위키: 10% with each victorious combat, up to 5'),
    ('adept', '적 공속 감소', lambda: o.AS['adept'], every(0.5), '위키: by 50%'),
    ('adept', '지속', lambda: o.length['adept'],
     steps(('10.20', [0, 2000, 3000, 5000]), ('10.21', [0, 2000, 3500, 6000])),
     '공식 10.21 2/3/5 ⇒ 2.5/4/7, 같은 패치 핫픽스 ⇒ 2/3.5/6'),
    ('assassin', '치명타 확률·피해', lambda: [o.crit_chance['assassin'], o.crit_damage['assassin']],
     every([[0, 0.10, 0.25, 0.40], [0, 0.30, 0.60, 0.90]]), '위키 10.19'),
    ('brawler', '체력', lambda: o.health['brawler'], every([0, 400, 800, 1200, 1800]), '위키 10.19'),
    ('dazzler', '공격력 감소(남는 비율)', lambda: o.AD['dazzler'],
     steps(('10.20', [0, 0.5, 0.5]), ('10.22', [0, 0.5, 0.2]), ('10.23', [0, 0.6, 0.2])),
     '공식 10.22 50% ⇒ 50/80%, 10.23 50/80 ⇒ 40/80%'),
    ('duelist', '중첩당 공속·최대 중첩', lambda: [o.AS['duelist'], o.threshold['duelist']],
     every([[0, 1.12, 1.20, 1.35, 1.60], 8]), '위키: +12/20/35/60% per stack, up to 8'),
    ('hunter', '추가 피해', lambda: o.AD['hunter'],
     steps(('10.20', [0, 1.75, 1.75, 1.75, 1.75]), ('10.21', [0, 1.50, 1.75, 2.00, 2.25]),
           ('10.23', [0, 1.25, 1.50, 1.75, 2.00])), '공식 10.21 175% ⇒ 150/175/200/225, 10.23 ⇒ 125/150/175/200'),
    ('hunter', '간격', lambda: o.threshold['hunter'][1:], every([3500, 3000, 2500, 2000]), '위키 10.19'),
    ('keeper', '보호막', lambda: o.shield['keeper'],
     steps(('10.20', [0, 175, 250, 400]), ('10.23', [0, 175, 250, 350]), ('10.24', [0, 150, 225, 350])),
     '공식 10.20 325 ⇒ 400, 10.23 400 ⇒ 350, 10.24 핫픽스 ⇒ 150/225/350'),
    ('keeper', '지속', lambda: o.length['keeper'],
     steps(('10.20', [0, 8000, 8000, 8000]), ('10.23', [0, 8000, 10000, 14000]), ('10.24', [0, 8000, 10000, 12000])),
     '공식 10.23 8초 ⇒ 8/10/14, 10.24 핫픽스 ⇒ 8/10/12'),
    ('keeper', '수호자 본인 보호막 증가', lambda: o.increasement['keeper'], every(0.50), '위키: 50% stronger on Keepers'),
    ('mage', '주문력 배율', lambda: o.SP['mage'], every([0, 0.80, 1.10, 1.80]),
     '공식 10.20 70/110/180 ⇒ 80/110/180. 10.25에 120'),
    ('mystic', '마법 저항', lambda: o.MR['mystic'],
     steps(('10.20', [0, 35, 95, 175]), ('10.21', [0, 40, 100, 200])), '공식 10.21 35/95/175 ⇒ 40/100/200'),
    ('shade', '추가 피해', lambda: o.damage['shade'],
     steps(('10.20', [0, 100, 325, 650]), ('10.21', [0, 125, 400, 750])), '공식 10.21 100/325/650 ⇒ 125/400/750'),
    ('sharpshooter', '튕김 수', lambda: o.targets['sharpshooter'], every([0, 1, 2, 3]), '위키 10.19'),
    ('sharpshooter', '튕김 피해(남는 비율)', lambda: o.damage['sharpshooter'],
     steps(('10.20', [0, 0.35, 0.50, 0.65]), ('10.22', [0, 0.45, 0.50, 0.55])),
     '공식 10.22 감소 65/50/35% ⇒ 55/50/45%'),
    ('vanguard', '방어력', lambda: o.armor['vanguard'],
     steps(('10.20', [0, 100, 250, 500]), ('10.21', [0, 100, 250, 600, 1500])), '공식 10.21'),
    ('divine', '받는 피해(남는 비율)', lambda: o.receive_decreased_damage['divine'],
     steps(('10.20', 0.75), ('10.21', 0.6), ('10.23', 0.5)),
     '위키 10.19: 25% 감소. 공식 10.21 핫픽스 50 ⇒ 40%, 10.23 40 ⇒ 50%'),
    ('divine', '추가 고정 피해', lambda: o.deal_bonus_true_damage['divine'],
     steps(('10.20', [0, 0.20, 0.40, 0.65, 1.00]), ('10.21', 0.4), ('10.23', 0.5)),
     '위키 10.19: 20/40/65/100%(전투 끝까지). 공식 10.21 리워크 후 핫픽스 40%, 10.23 50%'),
    ('divine', '지속', lambda: COMBAT if o.length['divine'][1:] == [getattr(pm, 'COMBAT_LENGTH', None)] * 4
                             else o.length['divine'],
     steps(('10.20', COMBAT), ('10.21', [0, 4000, 6000, 9000, 13000]), ('10.23', [0, 3000, 6000, 9000, 15000])),
     '위키 10.19: 전투 끝까지. 공식 10.21 리워크 4/6/9/13초, 공식 10.23 4/6/9/13 ⇒ 3/6/9/15'),
    ('divine', '승천까지 공격 수', lambda: o.threshold['divine'], every(6), '위키: Upon attacking 6 times'),
    ('the_boss', '퇴장 체력·회복·공속', lambda: [o.threshold['the_boss'], o.heal['the_boss'], o.AS['the_boss']],
     every([0.4, 0.15, 1.40]), '위키: below 40%, restores 15%, 40% bonus attack speed'),
    ('fortune', '연패 보상(골드)', lambda: o.fortune_returns[:10] if len(o.fortune_returns) >= 10 else o.fortune_returns,
     steps(('10.20', [3, 6.5, 11.5, 17, 24, 31, 38, 45, 55, 70]), ('10.21', [2.5, 6, 10.5, 17, 24, 31, 38, 45, 55, 70])),
     '공식 10.20 0~9연패 3/6.5/11.5/17/24/31/38/45/55/70, 10.21 0~2연패 2.5/6/10.5'),
    ('fortune', '연패 보상 칸 수', lambda: len(o.fortune_returns), steps(('10.20', 10), ('10.23', 13)),
     '공식 10.23: 10, 11, 12연패 표 추가'),
    ('cultist', '갈리오 체력', lambda: champ_stats.HEALTH['galio'],
     steps(('10.20', [0, 1600, 3800, 6666]), ('10.21', [0, 1000, 1750, 2500]), ('10.23', [0, 1000, 1650, 2250]),
           ('10.24', [0, 800, 1400, 2000])), '공식 10.20, 10.21, 10.23, 10.24 핫픽스'),
    ('cultist', '갈리오 시작 마나', lambda: champ_stats.MANA['galio'], steps(('10.20', 50), ('10.23', 75)),
     '공식 10.23: All Galios Mana 50/150 ⇒ 75/150'),
    ('cultist', '갈리오 별 수준당 증가', lambda: sim_config.GALIO_MULTIPLIER,
     steps(('10.20', 0), ('10.21', 0.12), ('10.24', 0.14)), '공식 10.21 +12%, 10.24 핫픽스 12 ⇒ 14%'),
    ('cultist', '선택받은 사교도 2배', lambda: o.cultist_chosen_double,
     steps(('10.20', False), ('10.22', True), ('10.24', False)), '공식 10.22 2배로, 10.24 +1로'),
    ('cultist', 'CC 면역(ms)', lambda: o.cc_immune['cultist'], steps(('10.20', 0), ('10.23', 8000)),
     '공식 10.23: Supreme Overlord Galio (Cultist 9) 8초'),
    ('chosen', '공격력 보너스', lambda: o.chosen_AD, steps(('10.20', 30), ('10.24', 20)), '공식 10.24: 30 ⇒ 20'),
]

# 공식 노트끼리 어긋나서 정하지 못한 칸
AMBIGUOUS = [
    ('cultist', '갈리오 공격력 1성(3 사교도)', lambda: champ_stats.AD['galio'][1],
     '공식 10.21은 80, 10.24 핫픽스는 "85/180/320 ⇒ 75/160/280"이라 10.23 값이 80인지 85인지 갈린다'),
]


def main():
    rows = []
    for patch in PATCHES:
        pm.apply_patch(patch)
        for trait, label, get, exp, src in EXPECTED:
            # apply_patch가 연패 보상 같은 목록을 제자리에서 바꾼다. 읽는 순간 복사해 둔다.
            sim = copy.deepcopy(get())
            want = exp[patch]
            if want == COMBAT:
                ok = sim == COMBAT  # 시뮬레이터는 patch_manager.COMBAT_LENGTH로 나타낸다
            elif all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (sim, want)):
                ok = abs(sim - want) < 1e-9
            else:
                ok = sim == want
            if not ok:
                rows.append([trait, patch, label, want, sim, 'MISMATCH', src])
        if patch == '10.23':
            for trait, label, get, why in AMBIGUOUS:
                rows.append([trait, patch, label, '', get(), 'AMBIGUOUS', why])

    path = os.path.join(HERE, 'mismatch_traits.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['trait', 'patch', 'field', 'expected', 'sim', 'status', 'source'])
        w.writerows(rows)
    checked = len(EXPECTED) * len(PATCHES)
    print(f'\n비교한 칸 {checked}개, 불일치 {sum(r[5] == "MISMATCH" for r in rows)}개')
    for r in rows:
        print(f'  {r[0]:12}{r[1]:7}{r[2]:22} 기대 {str(r[3]):34} 시뮬 {r[4]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
