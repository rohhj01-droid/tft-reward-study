"""
시뮬레이터 10.24 값을 Riot 공식 게임 데이터(CommunityDragon, 패치 10.24 파일)와 칸마다 대조한다.

기본 스탯 8개와 스킬 변수 전부를 본다. 스킬 변수는 공식 이름과 시뮬레이터 표를 아래 MAP에서 하나씩 짝지었다.
공식 파일은 10.24 첫 배포본이라 2020-12-01 핫픽스(10.24b)가 없다. 시뮬레이터 10.24는 핫픽스 뒤 값이므로
공식 10.24 노트의 핫픽스 항목은 HOTFIX로 고쳐서 비교한다. 10.25 값과 같은 칸은 따로 표시한다
(시뮬레이터 기본값에 다음 패치 값이 섞였는지 보려고).

실행: python audit/diff_cdragon.py   (시뮬레이터 저장소가 PYTHONPATH에 있어야 한다)
결과: audit/mismatch_cdragon.csv
"""
import csv
import json
import os
import sys

from Simulator import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REF = {v: json.load(open(os.path.join(HERE, f'cdragon_{v}_set4.json'), encoding='utf-8'))
       for v in ('10.24', '10.25')}

MS = lambda x: x * 1000           # 초 -> 밀리초
ONE_PLUS = lambda x: 1 + x        # +45% -> 1.45 배율
ONE_MINUS = lambda x: 1 - x       # 50% 감소 -> 0.5 배율
PCT = lambda x: x / 100           # 20(%) -> 0.2
SAME = lambda x: x

# 챔피언: [(공식 변수 이름, 시뮬레이터 표, 변환)]
MAP = {
    'aatrox': [('Damage', 'ABILITY_DMG', SAME), ('NumberOfTargets', 'ABILITY_TARGETS', SAME)],
    'ahri': [('Damage', 'ABILITY_DMG', SAME), ('CastTime', 'ABILITY_LENGTH', MS)],
    'akali': [('Damage', 'ABILITY_DMG', SAME)],
    'annie': [('Damage', 'ABILITY_DMG', SAME), ('ShieldAmount', 'SHIELD_AMOUNT', SAME),
              ('ShieldDuration', 'SHIELD_LENGTH', MS)],
    'aphelios': [('Duration', 'ABILITY_LENGTH', MS)],
    'ashe': [('Duration', 'ABILITY_LENGTH', MS), ('AttackSpeed', 'ABILITY_AS_GAIN', ONE_PLUS),
             ('PercentADPerArrow', 'ABILITY_DAMAGE_MULTIPLIER', SAME), ('NumArrows', 'ABILITY_SLICES', SAME)],
    'azir': [('WallDamage', 'ABILITY_DMG', SAME), ('KnockupDuration', 'ABILITY_STUN_DURATION', MS),
             ('SlowDuration', 'ABILITY_SLOW_DURATION', MS)],
    'cassiopeia': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS),
                   ('DamageAmp', 'ABILITY_TARGET_INCREASE_DAMAGE_RECEIVING', ONE_PLUS)],
    'diana': [('Orbs', 'ABILITY_TARGETS', SAME), ('OrbDamage', 'ABILITY_DMG', SAME),
              ('ShieldValue', 'SHIELD_AMOUNT', SAME), ('ShieldDuration', 'SHIELD_LENGTH', MS)],
    'elise': [('Lifesteal', 'ABILITY_HEALTH_PER_ATTACK', SAME),
              ('PercentHealth', 'ABILITY_HEALTH_GAIN_PERCENTAGES', ONE_PLUS)],
    'evelynn': [('Damage', 'ABILITY_DMG', SAME), ('CritMultiplier', 'ABILITY_DAMAGE_MULTIPLIER', SAME)],
    'ezreal': [('BaseDamage', 'ABILITY_DMG', SAME), ('BaseHeal', 'ABILITY_HEAL', SAME),
               ('Duration', 'ABILITY_AS_CHANGE_LENGTH', MS)],
    'fiora': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS),
              ('BlockDuration', 'ABILITY_LENGTH', MS)],
    'garen': [('SpinDuration', 'ABILITY_LENGTH', MS),
              ('MagicDamageReduction', 'ABILITY_SPELL_DAMAGE_REDUCTION_PERCENTAGE', ONE_MINUS)],
    'hecarim': [('Damage', 'ABILITY_DMG', SAME), ('Healing', 'ABILITY_HEAL', SAME),
                ('Duration', 'ABILITY_LENGTH', MS)],
    'irelia': [('Damage', 'ABILITY_DMG', SAME), ('DisarmDuration', 'ABILITY_DISARM_DURATION', MS)],
    'janna': [('NumAllies', 'ABILITY_TARGETS', SAME), ('ShieldAmount', 'SHIELD_AMOUNT', SAME),
              ('Duration', 'SHIELD_LENGTH', MS), ('ShieldAD', 'ABILITY_DMG_GAIN', SAME)],
    'jarvaniv': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'jax': [('Duration', 'ABILITY_LENGTH', MS), ('Damage', 'ABILITY_DMG', SAME),
            ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'jhin': [('PercentOfAD', 'ACTIVE_DMG_PERCENT', SAME), ('AttackSpeed', 'ATTACKS_PER_SECOND_FIXED', SAME)],
    'jinx': [('RocketDamage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'kalista': [('PercentHealthDamage', 'ACTIVE_TARGET_HEALT_THRESHOLD', SAME)],
    'katarina': [('TotalDamage', 'ABILITY_DMG', SAME), ('Duration', 'ABILITY_LENGTH', MS),
                 ('NumberOfTargets', 'ABILITY_TARGETS', SAME),
                 ('GrievousWoundsDuration', 'ABILITY_HEALING_REDUCE_LENGTH', MS)],
    'kayn': [('Damage', 'ABILITY_DMG', SAME), ('PercentRestored', 'ABILITY_HEALTH_PER_CAST_DAMAGE_PERCENTAGES', SAME),
             ('ShadowDamagePercent', 'ABILITY_EXTRA_DAMAGE', lambda x: 1 + x / 100),
             ('ShadowDuration', 'ABILITY_EXTRA_DAMAGE_LENGTH', MS)],
    'kennen': [('Damage', 'ABILITY_DMG', SAME), ('Duration', 'ABILITY_LENGTH', MS),
               ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'kindred': [('Damage', 'ABILITY_DMG', SAME), ('GrievousWoundsDuration', 'ABILITY_HEALING_REDUCE_LENGTH', MS)],
    'leesin': [('Damage', 'ABILITY_DMG', SAME), ('PrimaryStunDuration', 'ABILITY_STUN_DURATION', MS),
               ('SecondaryStunDuration', 'ABILITY_SECONDARY_STUN_DURATION', MS)],
    'lillia': [('NumTargets', 'ABILITY_TARGETS', SAME), ('Duration', 'ABILITY_STUN_DURATION', MS),
               ('BreakDamage', 'ABILITY_STUN_STOP_DMG_THRESHOLD', SAME), ('Damage', 'ABILITY_DMG', SAME)],
    'lissandra': [('Damage', 'ABILITY_DMG', SAME), ('SecondaryDamage', 'ABILITY_SECONDARY_DMG', SAME)],
    'lulu': [('BonusHealth', 'ABILITY_HEALTH_GAIN_TOTAL', SAME), ('CCDuration', 'ABILITY_STUN_DURATION', MS)],
    'lux': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'maokai': [('Damage', 'ABILITY_DMG', SAME), ('ASSlowDuration', 'ABILITY_AS_CHANGE_LENGTH', MS)],
    'morgana': [('Damage', 'ABILITY_DMG', SAME), ('Duration', 'ABILITY_LENGTH', MS),
                ('HealPercent', 'ABILITY_HEAL_PER_DAMAGE', PCT)],
    'nami': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS)],
    'nidalee': [('BaseDamage', 'ABILITY_DMG', SAME), ('PercentPerHex', 'ABILITY_DAMAGE_ADDITION_PERCENTAGE', SAME)],
    'nunu': [('Damage', 'ABILITY_DMG', SAME), ('DamageAmp', 'ABILITY_DAMAGE_ADDITION_PERCENTAGE', SAME)],
    'pyke': [('Damage', 'ABILITY_DMG', SAME), ('StunDuration', 'ABILITY_STUN_DURATION', MS),
             ('StunDelay', 'ABILITY_LENGTH', MS)],
    'riven': [('Damage', 'ABILITY_DMG', SAME), ('DamageFinal', 'ABILITY_SECONDARY_DMG', SAME),
              ('Shield', 'SHIELD_AMOUNT', SAME)],
    'sejuani': [('ExplosionDelay', 'ABILITY_LENGTH', MS), ('Damage', 'ABILITY_DMG', SAME),
                ('StunDuration', 'ABILITY_STUN_DURATION', MS), ('HexRadius', 'ABILITY_RADIUS', SAME)],
    'sett': [('PercentMaxHealthDamagePrimary', 'ABILITY_DMG', SAME),
             ('PercentMaxHealthDamageSecondary', 'ABILITY_SECONDARY_DMG', SAME)],
    'shen': [('ShieldAmount', 'SHIELD_AMOUNT', SAME), ('Duration', 'ABILITY_LENGTH', MS)],
    'sylas': [('BaseDamage', 'ABILITY_DMG', SAME)],
    'tahmkench': [('DamageReduction', 'ACTIVE_DAMAGE_REDUCTION', SAME)],
    'talon': [('PercentOfAD', 'ABILITY_DAMAGE_MULTIPLIER', SAME), ('Damage', 'ABILITY_DMG', SAME)],
    'teemo': [('TotalDamage', 'ABILITY_DMG', SAME), ('Duration', 'ABILITY_BLIND_DURATION', MS)],
    'thresh': [('ShieldAmount', 'SHIELD_AMOUNT', SAME), ('Duration', 'SHIELD_LENGTH', MS)],
    'twistedfate': [('BaseDamage', 'ABILITY_DMG', SAME)],
    'vayne': [('BonusDamage', 'ACTIVE_DMG', SAME)],
    'veigar': [('Damage', 'ABILITY_DMG', SAME), ('APToAdd', 'ABILITY_SP_GAIN', PCT)],
    'vi': [('Damage', 'ABILITY_DMG', SAME), ('ArmorReduction', 'ABILITY_ARMOR_DECREASE', ONE_MINUS),
           ('Duration', 'ABILITY_LENGTH', MS)],
    'warwick': [('AttackSpeedPercent', 'ABILITY_AS_GAIN', SAME), ('LifestealPercent', 'LIFESTEAL', PCT),
                ('AllyAS', 'ABILITY_AS_SECONDARY_GAIN', ONE_PLUS), ('AllyASDuration', 'ABILITY_LENGTH', MS)],
    'wukong': [('PercentAD', 'ABILITY_DAMAGE_MULTIPLIER', SAME), ('Duration', 'ABILITY_STUN_DURATION', MS)],
    'xinzhao': [('PercentOfAttackDamage', 'ABILITY_DAMAGE_MULTIPLIER', SAME),
                ('ArmorAndMR', 'ABILITY_ARMOR_MR_INCREASE', SAME)],
    'yasuo': [('ADPercent', 'ABILITY_DAMAGE_MULTIPLIER', SAME)],
    'yone': [('Damage', 'ABILITY_DMG', SAME), ('UnforgottenDamage', 'ABILITY_SECONDARY_DMG', SAME),
             ('ShredPercent', 'ABILITY_ARMOR_MR_DECREASE', lambda x: 1 - x / 100)],
    'yuumi': [('Healing', 'ABILITY_HEALTH_GAIN_PERCENTAGES', SAME), ('AttackSpeed', 'ABILITY_AS_GAIN', ONE_PLUS),
              ('Duration', 'ABILITY_AS_CHANGE_LENGTH', MS)],
    'zed': [('Damage', 'ACTIVE_DMG', SAME), ('ADSteal', 'ACTIVE_STOLEN_AD', SAME)],
    'zilean': [('NumTargets', 'ABILITY_TARGETS', SAME), ('HealthAmount', 'ABILITY_HEAL', SAME),
               ('ReviveDelay', 'ABILITY_LENGTH', MS), ('AttackSpeed', 'ABILITY_AS_GAIN', ONE_PLUS)],
}

STATS = [('hp', 'HEALTH'), ('damage', 'AD'), ('attackSpeed', 'AS'), ('armor', 'ARMOR'),
         ('magicResist', 'MR'), ('initialMana', 'MANA'), ('mana', 'MAXMANA'), ('range', 'RANGE')]

# 공식 10.24 노트의 핫픽스(10.24b) 항목. (챔피언, 공식 이름) -> 1~3성 값
HOTFIX = {
    ('zed', 'attackSpeed'): [0.75] * 3,
    ('zed', 'ADSteal'): [0.25, 0.30, 0.35],
    ('yone', 'mana'): [60] * 3,
    ('yone', 'ShredPercent'): [60] * 3,
}

# 값을 적는 방식이 달라서 칸 비교가 뜻이 없는 것(이유를 적어 둔다)
SKIP = {
    ('jhin', 'attackSpeed'): '공식 2.0은 자리값이다. 진은 고정 공속(ATTACKS_PER_SECOND_FIXED)으로 대조한다',
    ('jhin', 'mana'): '공식 4는 네 번째 공격 표시다. 시뮬레이터는 ACTIVATE_EVERY_X_ATTACKS로 센다',
    ('galio', 'hp'): '갈리오는 사교도 별 단계로 체력이 정해진다. 시뮬레이터는 핫픽스 뒤 800/1400/2000(노트와 같다)',
    ('galio', 'damage'): '갈리오 공격력도 단계별 표다. 시뮬레이터는 핫픽스 뒤 75/160/280(노트와 같다)',
}


def ref_values(version, champ, name):
    c = REF[version][champ]
    if name in c['stats']:
        return [c['stats'][name]] * 3
    for v in c['ability']['variables']:
        if v['name'] == name:
            return list(v['value'][1:4])
    return None


def sim_values(table, champ):
    v = getattr(stats, table).get(champ)
    if v is None:
        return None
    return list(v[1:4]) if isinstance(v, list) else [v] * 3


def close(a, b):
    return a is not None and b is not None and all(abs(x - y) <= 1e-3 * max(1, abs(y)) for x, y in zip(a, b))


def main():
    rows = []
    checked = 0
    for champ in sorted(REF['10.24']):
        pairs = [(n, t, SAME) for n, t in STATS] + MAP.get(champ, [])
        for name, table, f in pairs:
            if (champ, name) in SKIP:
                continue
            sim = sim_values(table, champ)
            ref = HOTFIX.get((champ, name)) or ref_values('10.24', champ, name)
            if ref is None:
                rows.append([champ, name, table, '', sim, '공식 변수 없음'])
                continue
            want = [f(x) for x in ref]
            checked += 1
            if not close(sim, want):
                nxt = ref_values('10.25', champ, name)
                note = '10.25 값과 같다' if nxt and close(sim, [f(x) for x in nxt]) else ''
                rows.append([champ, name, table, want, sim, note])
    with open(os.path.join(HERE, 'mismatch_cdragon.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['champion', 'official_name', 'sim_table', 'official_1to3', 'sim_1to3', 'note'])
        w.writerows(rows)
    print(f'{checked}칸 대조, 불일치 {len(rows)}')
    for r in rows:
        print('  ', r)


if __name__ == '__main__':
    sys.exit(main())
