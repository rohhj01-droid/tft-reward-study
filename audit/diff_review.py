"""
챔피언 대조(diff_set4.py)에서 숫자가 아닌 변경이라 사람이 봐야 했던 검토 줄 35개 중, 코드로 확인할 수 있는
것을 패치별로 다시 잰다. 줄 번호는 audit/README.md "챔피언 검토 줄 35개" 표와 같다.

  1) 패치별 값과 켜짐 여부(아칼리, 카시오페아, 자르반, 징크스, 케인, 릴리아, 룰루, 니달리, 쉔, 탈론, 바이, 신 짜오, 요네).
     표에 항목이 없을 때 스킬 코드가 쓰는 기본값으로 읽는다.
  2) 선택받은 자 보너스 종류: 공식 10.19 목록에 10.22(피오라·바이 마나 감소, 세트 주문력)와 10.24(징크스 마나 감소)를 더한 값.
  3) 선택받은 자 보너스가 전투 유닛에 실제로 붙는지: 58명을 전투 상태 2성으로 선택받은 자와 일반으로 하나씩 만들어 비교한다.
     기대: 체력 +200에 종류별 체력 +400, 주문력 +0.30, 공격력 +30(10.24부터 +20), 최대 마나 ×0.75.
  4) 워윅 10.24 본인 공격 속도: 스킬을 쓴 뒤 공격 속도가 기본 × (1 + 135/150/500%)인지(주문력 100%일 때).

    PYTHONPATH=<june> python audit/diff_review.py

결과: audit/mismatch_review.csv (일치한 칸은 쓰지 않는다)
"""
import csv
import os

import Simulator.ability as ability
import Simulator.origin_class_stats as ocs
import Simulator.patch_manager as pm
import Simulator.stats as st
from Simulator.champion import champion

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']


def steps(*pairs):
    out, cur, marks = {}, None, dict(pairs)
    for p in PATCHES:
        cur = marks.get(p, cur)
        out[p] = cur
    return out


def get(table, name, default):
    return getattr(st, table).get(name, default)


# (줄 번호, 내용, 읽는 법, 패치별 기대, 출처)
VALUES = [
    ('11', '아칼리 마나 잠금', lambda: get('MANALOCK', 'akali', None), steps(('10.20', 1000), ('10.22', 1250)), '위키 V10.22'),
    ('14', '카시오페아 피해 증폭(받는 피해 배수)', lambda: get('ABILITY_TARGET_INCREASE_DAMAGE_RECEIVING', 'cassiopeia', None),
     steps(('10.20', 1.1), ('10.24', 1.2)), '위키 V10.24'),
    ('15', '자르반 기절', lambda: get('ABILITY_STUN_DURATION', 'jarvaniv', None),
     steps(('10.20', [0, 2000, 2000, 2000]), ('10.24', [0, 1000, 1000, 1000])), '위키 V10.24'),
    ('16', '징크스 기절', lambda: get('ABILITY_STUN_DURATION', 'jinx', None),
     steps(('10.20', [0, 1500, 1500, 1500]), ('10.24', [0, 1500, 2000, 2500])), '위키 V10.24'),
    ('8·17', '징크스 기절이 주 대상에게만', lambda: get('ABILITY_STUN_SINGLE_TARGET', 'jinx', False),
     steps(('10.20', True), ('10.24', False)), '공식 10.24'),
    ('18', '케인 그림자 암살자 추가 피해 배수', lambda: get('ABILITY_EXTRA_DAMAGE', 'kayn', None),
     steps(('10.20', [0, 1.75, 1.75, 1.75]), ('10.21', [0, 1.5, 1.5, 1.5])), '위키 V10.21'),
    # 위키 V10.22의 변경은 깨울 때 피해가 아니라 잠을 깨는 피해 기준이다(공식 데이터 BreakDamage, 10.20~10.24 대조).
    ('20', '릴리아 잠을 깨는 피해 기준', lambda: get('ABILITY_STUN_STOP_DMG_THRESHOLD', 'lillia', None),
     steps(('10.20', [0, 500, 750, 1000]), ('10.22', [0, 500, 500, 500])), '공식 데이터 BreakDamage'),
    ('20', '릴리아 깨울 때 피해', lambda: get('ABILITY_DMG', 'lillia', None),
     steps(('10.20', [0, 500, 750, 5000])), '공식 데이터 Damage'),
    ('21', '룰루 띄우기', lambda: get('ABILITY_STUN_DURATION', 'lulu', None),
     steps(('10.20', [0, 1500, 1500, 1500]), ('10.24', [0, 1000, 1000, 1000])), '위키 V10.24'),
    ('6·22', '룰루 거대화 지속(-1은 전투 끝까지)', lambda: get('ABILITY_GROWTH_DURATION', 'lulu', -1),
     steps(('10.20', 6000), ('10.24', -1)), '공식 10.24'),
    ('23', '니달리 칸당 피해 증폭', lambda: get('ABILITY_DAMAGE_ADDITION_PERCENTAGE', 'nidalee', None),
     steps(('10.20', 0.1), ('10.21', 0.2)), '위키 V10.21'),
    ('24', '쉔 보호막·도발 지속', lambda: get('ABILITY_LENGTH', 'shen', None),
     steps(('10.20', [0, 4000, 4000, 8000])), '위키 V10.20'),
    ('25', '탈론 처치 시 마나 회복', lambda: get('ABILITY_MANA_ON_KILL', 'talon', False),
     steps(('10.20', True), ('10.24', False)), '위키 V10.24'),
    ('26', '탈론 도약 중 무적', lambda: get('ABILITY_IMMUNE_ON_LEAP', 'talon', False),
     steps(('10.20', True), ('10.24', False)), '위키 V10.24'),
    ('28', '바이 방어력 감소 지속', lambda: get('ABILITY_LENGTH', 'vi', None),
     steps(('10.20', 6000), ('10.22', 8000)), '위키 V10.22'),
    ('31', '신 짜오 휩쓸기 공격력 배수(10.23부터)', lambda: get('ABILITY_DAMAGE_MULTIPLIER', 'xinzhao', None),
     {'10.23': [0, 3.0, 3.25, 3.5], '10.24': [0, 3.0, 3.25, 3.5]}, '위키 V10.23'),
    ('31', '신 짜오 방어력·마법 저항(10.23부터)', lambda: get('ABILITY_ARMOR_MR_INCREASE', 'xinzhao', None),
     {'10.23': [0, 50, 60, 75], '10.24': [0, 50, 60, 75]}, '위키 V10.23'),
    ('32·33', '요네 저항 감소(남는 비율, 10.24는 12월 1일 핫픽스 뒤)', lambda: get('ABILITY_ARMOR_MR_DECREASE', 'yone', None),
     steps(('10.20', 0.4)), '위키 V10.24, 12월 1일 핫픽스'),
    ('35', '요네 띄우기', lambda: 'yone' in st.ABILITY_STUN_DURATION, steps(('10.20', True), ('10.24', False)), '위키 V10.24'),
]

# 공식 10.19 선택받은 자 보너스 목록
CHOSEN_1019 = {
    'health': ['garen', 'fiora', 'irelia', 'aatrox', 'wukong', 'jax', 'leesin', 'tahmkench', 'sejuani', 'maokai',
               'sylas', 'shen', 'yone', 'jarvaniv', 'hecarim', 'nunu', 'sett', 'vi', 'elise'],
    'SP': ['morgana', 'twistedfate', 'jinx', 'annie', 'veigar', 'lissandra', 'diana', 'kennen', 'kalista', 'akali',
           'vayne', 'riven', 'kindred', 'ahri', 'nidalee', 'kayn', 'katarina', 'evelynn'],
    'AD': ['talon', 'aphelios', 'zed', 'ashe', 'warwick', 'xinzhao', 'yasuo', 'jhin'],
    'maxmana': ['nami', 'janna', 'zilean', 'lux', 'thresh', 'cassiopeia', 'lillia', 'teemo', 'yuumi', 'azir', 'lulu',
                'ezreal', 'pyke'],
}
CHOSEN_CHANGES = {'10.22': {'fiora': 'maxmana', 'vi': 'maxmana', 'sett': 'SP'}, '10.24': {'jinx': 'maxmana'}}


def expected_chosen_kind(patch):
    kind = {c: k for k, cs in CHOSEN_1019.items() for c in cs}
    for p in PATCHES[:PATCHES.index(patch) + 1]:
        kind.update(CHOSEN_CHANGES.get(p, {}))
    return kind


def chosen_trait(name):
    return next(t for t in ocs.origin_class[name] if t not in ocs.chosen_exclude)


def same(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-6
    return a == b


def main():
    rows, cells = [], 0
    for patch in PATCHES:
        pm.apply_patch(patch)
        for no, what, read, exp, src in VALUES:
            if patch not in exp:
                continue
            cells += 1
            if not same(read(), exp[patch]):
                rows.append([patch, no, what, exp[patch], read(), src])

        kinds = expected_chosen_kind(patch)
        sim_kind = {c['champion']: c['stat'] for c in ocs.chosen}
        ad = 20 if patch == '10.24' else 30
        for name, kind in sorted(kinds.items()):
            cells += 1
            if sim_kind.get(name) != kind:
                rows.append([patch, '1·3·4·7', f'{name} 선택받은 자 보너스 종류', kind, sim_kind.get(name), '공식 10.19, 10.22, 10.24'])
            base = champion(name, team='blue', stars=2)
            ch = champion(name, team='blue', stars=2, chosen=chosen_trait(name))
            cells += 1
            exp = {'health': 400, 'SP': 0.30, 'AD': ad, 'maxmana': base.maxmana * 0.75 - base.maxmana}[kind]
            stat = 'health' if kind == 'health' else kind
            got = getattr(ch, stat) - getattr(base, stat) - (200 if stat == 'health' else 0)
            if abs(got - exp) > 1e-6:
                rows.append([patch, '선택받은 자', f'{name} 보너스({kind})가 전투 유닛에 붙은 양', round(exp, 2),
                             round(got, 2), '공식 10.19(200 기본 + 종류별 보너스), 위키 선택받은 자 문서'])

    pm.apply_patch('10.24')
    for s, bonus in ((1, 1.35), (2, 1.50), (3, 5.00)):
        w = champion('warwick', team='blue', stars=s)
        before = w.AS
        ability.warwick(w)
        cells += 1
        exp = round(before * (1 + bonus), 2)
        if abs(w.AS - exp) > 1e-6:
            rows.append(['10.24', '29', f'워윅 {s}성 스킬 뒤 공격 속도(기본 {before})', exp, round(w.AS, 2), '위키 V10.24'])

    path = os.path.join(HERE, 'mismatch_review.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['patch', 'row', 'field', 'expected', 'sim', 'source'])
        w.writerows(rows)
    print(f'\n비교한 칸 {cells}개, 불일치 {len(rows)}개')
    for r in rows[:40]:
        print(f'  {r[0]:7}{r[1]:8}{r[2]:44} 기대 {str(r[3]):12} 시뮬 {r[4]}')
    if len(rows) > 40:
        print(f'  ...({len(rows) - 40}개 더, 결과 파일 참고)')
    print(f'저장: {path}')


if __name__ == '__main__':
    main()
