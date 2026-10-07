"""
시뮬레이터(june)의 Set 4 아이템 수치를 실제 값과 패치별로 대조한다.

특성처럼 칸을 정해 두고 비교한다. 기대값의 출처:
  공식: 라이엇 공식 패치노트 10.19~10.25 (10.19는 Set 4 출시 때 Set 3.5 대비 변경)
  위키 2020-12: LoL 위키 아이템 문서의 2020년 12월 판(Set 4 진행 중 저장본). 지금 위키의
                아이템 모듈은 Set 10 이후 값만 있어서 쓰지 않았다. 원본: audit/wiki_set4_items_2020.json
기본 능력치는 Set 4 규칙대로 재료 두 개의 합이고, 2020-12 문서가 따로 적은 값만 덮어쓴다.

    PYTHONPATH=<june> python audit/diff_items.py

결과: audit/mismatch_items.csv (일치한 칸은 쓰지 않는다)
"""
import copy
import csv
import os

import Simulator.item_stats as it
import Simulator.patch_manager as pm
import Simulator.stats as champ_stats

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']


def steps(*pairs):
    out, cur, marks = {}, None, dict(pairs)
    for p in PATCHES:
        cur = marks.get(p, cur)
        out[p] = cur
    return out


def every(v):
    return steps(('10.20', v))


# Set 4 재료 능력치. 문장(엠블럼) 아이템이 재료 하나의 능력치를 그대로 가져서 교차 확인했다
# (위키 Set 4: 선봉대 흉갑 방어 25, 군주의 깃발 체력 200, 유령검 치명 10·회피 10, 결투가의 열정 공속 15%).
COMPONENTS = {
    'bf_sword': {'AD': 15}, 'chain_vest': {'armor': 25}, 'giants_belt': {'health': 200},
    'needlessly_large_rod': {'SP': 0.15}, 'negatron_cloak': {'MR': 25}, 'recurve_bow': {'AS': 1.15},
    'sparring_gloves': {'crit_chance': 0.10, 'dodge': 0.10}, 'spatula': {}, 'tear_of_the_goddess': {'mana': 15},
}
# 2020-12 문서가 재료 합과 다르게 적은 능력치. None은 그 능력치가 없다는 뜻이다.
OVERRIDE = {
    'infinity_edge': {'crit_chance': 0.75, 'dodge': None},     # 치명 75(총), 회피 없음
    'jeweled_gauntlet': {'crit_chance': 0.20, 'dodge': None},
    'last_whisper': {'crit_chance': 0.20, 'dodge': None},
    'quicksilver': {'dodge': 0.20, 'crit_chance': None},
    'shroud_of_stillness': {'dodge': 0.20, 'crit_chance': None},
    'trap_claw': {'dodge': 0.20, 'crit_chance': None},
    'rabadons_deathcap': {'SP': 0.80},                         # 10.22 핫픽스 이후 총 80
    'warmogs_armor': {'health': 1000},
    'deathblade': {'AD': 50},                                  # 30 + 처음부터 1중첩(20)
}
# 기본 능력치로 비교하지 않는 칸(효과용 값. 아래에서 따로 비교한다)
NOT_STAT = {'will_revive', 'lifesteal', 'spell_damage_reduction_percentage', 'crit_damage'}


def expected_base(item):
    if item in COMPONENTS:
        return dict(COMPONENTS[item])
    a, b = it.item_builds[item]
    out = {}
    for comp in (a, b):
        for k, v in COMPONENTS[comp].items():
            if k == 'AS':
                out[k] = round(out.get(k, 1.0) + (v - 1), 4)
            else:
                out[k] = round(out.get(k, 0) + v, 4)
    for k, v in OVERRIDE.get(item, {}).items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def sim_base(item):
    stats = {k: v for k, v in it.items[item].items() if k not in NOT_STAT}
    if item == 'infinity_edge':  # 시뮬레이터는 기본 0.2와 전투 시작 때 더하는 0.55로 나눠 둔다
        stats['crit_chance'] = round(stats.get('crit_chance', 0) + it.crit_chance['infinity_edge'], 4)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in stats.items()}


ITEMS = sorted(set(COMPONENTS) | set(it.item_builds))

EXPECTED = [(i, '기본 능력치', lambda i=i: sim_base(i), every(expected_base(i)), '재료 합 + 위키 2020-12') for i in ITEMS
            if i != 'rabadons_deathcap'] + [
    ('rabadons_deathcap', '기본 능력치', lambda: sim_base('rabadons_deathcap'),
     steps(('10.20', {'SP': 0.70}), ('10.22', {'SP': 0.80})), '공식 10.22 70 ⇒ 75, 같은 패치 핫픽스 ⇒ 80'),
    ('chalice_of_power', '주문력', lambda: it.SP['chalice_of_power'],
     steps(('10.20', 0.30), ('10.21', 0.40), ('10.22', 0.35)), '공식 10.21 30 ⇒ 40, 10.22 핫픽스 40 ⇒ 35'),
    ('ludens_echo', '피해', lambda: it.damage['ludens_echo'], steps(('10.20', 200), ('10.21', 180)),
     '공식 10.20 180 ⇒ 200, 10.21 200 ⇒ 180'),
    ('ludens_echo', '대상·범위', lambda: [it.item_targets['ludens_echo'], it.item_range['ludens_echo']],
     every([3, 2]), '위키 2020-12: 첫 대상과 2칸 안 적 최대 3명'),
    ('statikk_shiv', '피해', lambda: it.damage['statikk_shiv'],
     steps(('10.20', 85), ('10.21', 75), ('10.22', 80)), '공식 10.20 80 ⇒ 85, 10.21 85 ⇒ 75, 10.22 75 ⇒ 80'),
    ('statikk_shiv', '보호막 대상 고정 피해', lambda: it.true_damage['statikk_shiv'],
     steps(('10.20', 85), ('10.21', 175), ('10.22', 240)), '공식 10.20 85, 10.21 85 ⇒ 175, 10.22 175 ⇒ 240'),
    ('statikk_shiv', '추가 대상(별)·주기', lambda: [it.item_targets['statikk_shiv'], it.item_activate_every_x_attacks['statikk_shiv']],
     every([[0, 2, 3, 4, 8], 3]), '위키 2020-12: 세 번째 공격마다 대상과 2/3/4/8명'),
    ('sunfire_cape', '간격·범위', lambda: [it.cooldown['sunfire_cape'], it.item_range['sunfire_cape']],
     every([2000, 2]), '공식 10.20 1초 ⇒ 2초, 위키 2020-12: 2칸 안'),
    ('gargoyle_stoneplate', '적 하나당 방어·마저', lambda: [it.armor['gargoyle_stoneplate'], it.MR['gargoyle_stoneplate']],
     steps(('10.20', [12, 12]), ('10.21', [15, 15])), '공식 10.21 12 ⇒ 15'),
    ('locket_of_the_iron_solari', '보호막(별)', lambda: it.shield['locket_of_the_iron_solari'],
     steps(('10.20', [0, 250, 300, 375, 500]), ('10.21', [0, 300, 375, 500, 800])),
     '공식 10.21 250/300/375/500 ⇒ 350/450/600/800, 같은 패치 핫픽스 ⇒ 300/375/500/800'),
    ('locket_of_the_iron_solari', '지속', lambda: it.item_change_length['locket_of_the_iron_solari'], every(8000),
     '위키 2020-12: 8초'),
    ('quicksilver', 'CC 면역 지속', lambda: it.item_change_length['quicksilver'],
     steps(('10.20', 12000), ('10.21', 10000)), '공식 10.21 12 ⇒ 10초'),
    ('zekes_herald', '공속', lambda: it.item_as_increase['zekes_herald'],
     steps(('10.20', 1.30), ('10.21', 1.40), ('10.22', 1.35)), '공식 10.21 30 ⇒ 40%, 10.22 40 ⇒ 35%'),
    ('zzrot_portal', '도발 지속', lambda: it.item_change_length['zzrot_portal'],
     steps(('10.20', 2000), ('10.22', 1000)), '공식 10.22 2초 ⇒ 1초'),
    ('zzrot_portal', '구조물 공격력', lambda: champ_stats.AD['construct'],
     steps(('10.20', 70), ('10.21', 150), ('10.24', 100)), '공식 10.21 70 ⇒ 150, 10.24 150 ⇒ 100'),
    ('zzrot_portal', '구조물 체력(별)', lambda: champ_stats.HEALTH['construct'], every([0, 1500, 2250, 3000, 5000]),
     '위키 2020-12: 1500/2250/3000/5000'),
    ('runaans_hurricane', '추가 화살 피해(공격력 비율)', lambda: it.damage['runaans_hurricane'],
     steps(('10.20', 0.75), ('10.22', 1.00), ('10.24', 0.90)), '공식 10.22 75 ⇒ 100%, 10.24 핫픽스 100 ⇒ 90%'),
    ('jeweled_gauntlet', '치명타 피해', lambda: it.items['jeweled_gauntlet'].get('crit_damage'),
     steps(('10.20', 0.50), ('10.22', 0.40)), '공식 10.19 30 ⇒ 50%, 10.22 핫픽스 50 ⇒ 40%'),
    ('last_whisper', '방어력 감소(남는 비율)·지속', lambda: [it.item_armor_decrease['last_whisper'], it.item_change_length['last_whisper']],
     every([0.25, 3000]), '공식 10.25 75 ⇒ 80%(그 전 75%), 위키 2020-12: 3초'),
    ('deathblade', '중첩당 공격력', lambda: it.AD['deathblade'], every(20), '공식 10.19 25 ⇒ 20'),
    ('hextech_gunblade', '회복 비율·보호막 상한', lambda: [it.heal_percentage['hextech_gunblade'], it.shield_max['hextech_gunblade']],
     every([0.33, 400]), '공식 10.19 45 ⇒ 33%, 위키 2020-12: 보호막 최대 400'),
    ('ionic_spark', '마저 감소(남는 비율)·마나 피해·범위',
     lambda: [it.item_mr_decrease['ionic_spark'], it.damage['ionic_spark'], it.item_range['ionic_spark']],
     every([0.60, 2.25, 2]), '위키 2020-12: 2칸 안 마저 40% 감소, 최대 마나의 225%'),
    ('bramble_vest', '가시 피해(별)·대기', lambda: [it.damage['bramble_vest'], it.cooldown['bramble_vest']],
     every([[0, 80, 100, 150], 2500]), '공식 10.19 100/140/200 ⇒ 80/100/150, 위키 2020-12: 2.5초'),
    ('guardian_angel', '부활 체력·대기', lambda: [it.heal['guardian_angel'], it.cooldown['guardian_angel']],
     every([400, 2000]), '위키 2020-12: 2초 뒤 체력 400'),
    ('redemption', '죽을 때 아군 회복', lambda: it.heal['redemption'], every(800), '위키 2020-12: 800'),
    ('frozen_heart', '공속 감소(남는 비율)', lambda: it.item_as_decrease['frozen_heart'], every(0.5), '위키 2020-12: 50%'),
    ('guinsoos_rageblade', '공격당 공속', lambda: it.item_as_increase['guinsoos_rageblade'], every(1.06),
     '공식 10.19 5 ⇒ 6%'),
    ('spear_of_shojin', '공격당 마나', lambda: it.mana['spear_of_shojin'], every(5), '공식 10.19: 5 Mana per auto'),
    ('shroud_of_stillness', '최대 마나 증가', lambda: it.item_mana_cost_increase['shroud_of_stillness'], every(0.33),
     '위키 2020-12: 33%'),
    ('trap_claw', '기절', lambda: it.item_stun_duration['trap_claw'], every(4000), '위키 2020-12: 4초'),
    ('zephyr', '추방', lambda: it.item_stun_duration['zephyr'], every(5000), '위키 2020-12: 5초'),
    ('titans_resolve', '중첩당 피해·최대 중첩·최대 때 방어·마저',
     lambda: [it.item_deal_increased_damage_increase['titans_resolve'], it.item_max_stacks['titans_resolve'],
              it.armor['titans_resolve'], it.MR['titans_resolve']],
     every([0.02, 25, 25, 25]), '위키 2020-12: 2%씩 25번, 최대 때 방어·마저 25'),
    ('bloodthirster', '흡혈', lambda: it.items['bloodthirster'].get('lifesteal'), every(0.40), '공식 10.19 45 ⇒ 40%'),
    ('dragons_claw', '받는 마법 피해(남는 비율)', lambda: it.items['dragons_claw'].get('spell_damage_reduction_percentage'),
     every(0.4), '공식 10.19 50 ⇒ 60% 감소'),
]


def same(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)):
        return abs(a - b) < 1e-6
    return a == b


def main():
    rows = []
    for patch in PATCHES:
        pm.apply_patch(patch)
        for item, label, get, exp, src in EXPECTED:
            sim = copy.deepcopy(get())
            if not same(sim, exp[patch]):
                rows.append([item, patch, label, exp[patch], sim, src])
    path = os.path.join(HERE, 'mismatch_items.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['item', 'patch', 'field', 'expected', 'sim', 'source'])
        w.writerows(rows)
    print(f'\n비교한 칸 {len(EXPECTED) * len(PATCHES)}개, 불일치 {len(rows)}개')
    for r in rows:
        print(f'  {r[0]:26}{r[1]:7}{r[2]:24} 기대 {str(r[3]):40} 시뮬 {r[4]}')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
