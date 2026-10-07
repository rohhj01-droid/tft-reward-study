"""
시뮬레이터(june)의 Set 4 챔피언 58종 수치를 실제 값과 패치별로 대조한다.

출처 두 가지를 따로 대조한다. 둘이 어긋나는 곳이 있어서 한쪽만 믿으면 안 된다.
  riot  audit/riot_notes_set4.json            라이엇 공식 패치노트 10.20~10.25의 변경 줄 (A ⇒ B)
  wiki  audit/wiki_set4_units.json            LoL 위키 Set 4 섹션 값 (세트 마지막 상태, 11.1 포함)
        audit/wiki_set4_patch_history.json    위키 챔피언별 패치 이력 V10.19~V11.1

시뮬레이터 패치 "10.2x"는 그 패치의 핫픽스까지 적용된 상태로 본다.
patch_manager 의 10.20이 핫픽스 값(영혼 70%)을 쓰고, 10.24가 12/01 핫픽스를 쓰기 때문이다.
시뮬레이터 값은 patch_manager.apply_patch 를 실제로 호출한 뒤 stats 표에서 읽는다.

    PYTHONPATH=<june> python audit/diff_set4.py

결과: audit/mismatch_set4.csv (일치한 항목은 쓰지 않는다)
"""
import collections
import csv
import json
import os
import re

import Simulator.stats as champ_stats
import Simulator.patch_manager as pm

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = ['10.20', '10.21', '10.22', '10.23', '10.24']
# 위키 키 -> 시뮬레이터 표 이름
BASE = {'hp': 'HEALTH', 'ad': 'AD', 'as': 'AS', 'arm': 'ARMOR', 'mr': 'MR',
        'startmana': 'MANA', 'mana': 'MAXMANA', 'range': 'RANGE'}
# 스킬 값을 찾을 때 뺄 표. 기본 스탯과 코스트는 우연히 같은 숫자로 걸리기 쉽다.
NOT_ABILITY = set(BASE.values()) | {'COST'}

DISPLAY = {
    'aatrox': 'Aatrox', 'ahri': 'Ahri', 'akali': 'Akali', 'annie': 'Annie', 'aphelios': 'Aphelios',
    'ashe': 'Ashe', 'azir': 'Azir', 'cassiopeia': 'Cassiopeia', 'diana': 'Diana', 'elise': 'Elise',
    'evelynn': 'Evelynn', 'ezreal': 'Ezreal', 'fiora': 'Fiora', 'garen': 'Garen', 'hecarim': 'Hecarim',
    'irelia': 'Irelia', 'janna': 'Janna', 'jarvaniv': 'Jarvan IV', 'jax': 'Jax', 'jhin': 'Jhin',
    'jinx': 'Jinx', 'kalista': 'Kalista', 'katarina': 'Katarina', 'kayn': 'Kayn', 'kennen': 'Kennen',
    'kindred': 'Kindred', 'leesin': 'Lee Sin', 'lillia': 'Lillia', 'lissandra': 'Lissandra',
    'lulu': 'Lulu', 'lux': 'Lux', 'maokai': 'Maokai', 'morgana': 'Morgana', 'nami': 'Nami',
    'nidalee': 'Nidalee', 'nunu': 'Nunu', 'pyke': 'Pyke', 'riven': 'Riven', 'sejuani': 'Sejuani',
    'sett': 'Sett', 'shen': 'Shen', 'sylas': 'Sylas', 'tahmkench': 'Tahm Kench', 'talon': 'Talon',
    'teemo': 'Teemo', 'thresh': 'Thresh', 'twistedfate': 'Twisted Fate', 'vayne': 'Vayne',
    'veigar': 'Veigar', 'vi': 'Vi', 'warwick': 'Warwick', 'wukong': 'Wukong', 'xinzhao': 'Xin Zhao',
    'yasuo': 'Yasuo', 'yone': 'Yone', 'yuumi': 'Yuumi', 'zed': 'Zed', 'zilean': 'Zilean',
}
# 패치노트가 줄여 쓴 이름도 받는다. 긴 이름부터 맞춰야 'Nunu and Willump'가 'Nunu'에 먹히지 않는다.
NAME2SIM = {v: k for k, v in DISPLAY.items()}
NAME2SIM.update({'Jarvan': 'jarvaniv', 'Nunu and Willump': 'nunu'})
NAMES_LONGEST_FIRST = sorted(NAME2SIM, key=len, reverse=True)

NUM = r'\d+(?:\.\d+)?'
NUMS = NUM + r'(?:/' + NUM + r')*'

# 출처 쪽 오류나 이 도구의 한계로 확인이 끝난 줄. (출처, 챔피언, 필드, 기대값) -> 이유.
# 시뮬레이터를 고친 뒤 다시 돌렸을 때 열린 줄만 남기려고 둔다. 근거 없이 늘리지 않는다.
KNOWN = {
    ('wiki', 'jax', 'startmana', '110'): '위키 이력 오기. 공식 10.21 노트는 50/100 ⇒ 60/110',
    ('wiki', 'jinx', 'mana', '150'): '위키 이력 오기. 공식 10.24 노트는 0/50 ⇒ 70/120',
    ('wiki', 'jhin', 'mana', '4'): '위키는 네 번째 발사를 마나 4로 적는다. 진은 마나를 안 쓴다',
    ('wiki', 'diana', 'ability', '200/300/450/650'): '위키 이력 오기(650을 600으로 적음). 공식 10.24 노트로 시뮬레이터가 맞다',
    ('wiki', 'diana', 'ability-chain', ''): '위 줄과 같은 위키 오기',
    ('wiki', 'talon', 'ability', '125/250/600'): '위키 출시 설명 오기. 공식 10.24 노트는 125/200/600이고 시뮬레이터가 맞다',
    ('wiki', 'talon', 'ability-chain', ''): '위 줄과 같은 위키 오기',
    # 아래 다섯은 공식 게임 데이터(CommunityDragon)·공식 노트·롤체지지 10.24 보관본으로 판정했다(audit/README 맨 아래).
    # 노트가 명시한 변경은 노트를, 노트가 말하지 않으면 게임 데이터를 따른다.
    ('wiki', 'zed', 'hp', '650'): '공식 게임 데이터 10.19~11.1 모두 600, 롤체지지 10.24도 600. 위키가 틀렸다',
    ('wiki', 'lillia', 'ability', '500/750/1000'): '위키는 잠을 깨는 피해 기준(10.20~21 500/750/1000, 10.22부터 500)을 '
                                                    '스킬 피해로 적었다. 공식 10.22 노트·게임 데이터·롤체지지 모두 깨어날 때 '
                                                    '피해는 500/750/5000',
    ('wiki', 'leesin', 'ability', '1/2/10'): '위키 2020-12 판은 2성 보조 기절 2초. 공식 10.24 노트는 "1.5 -> 1초", 게임 '
                                             '데이터 10.24는 1/1/10이라 게임 데이터를 따른다',
    ('wiki', 'irelia', 'ability', '200/300/600'): '출처가 갈린다. 위키·롤체지지 10.24는 600(게임 데이터 10.19 값), 게임 '
                                                  '데이터 10.20~11.1은 550. 노트에 없어 게임 데이터를 따른다',
    ('wiki', 'nami', 'ability', '225/325/450'): '출처가 갈린다. 위키·롤체지지 10.24는 325, 게임 데이터 10.19~11.1은 300. '
                                                '노트에 없어 게임 데이터를 따른다',
    ('wiki', 'yone', 'ability', '800/1300/9999'): '위키가 10.24 너프(600/1200/9999)를 빠뜨렸다. 공식 10.24 노트를 따른다',
    ('wiki', 'yone', 'ability', '250/400/1000'): '위키가 10.24 너프(200/400/1000)를 빠뜨렸다. 공식 10.24 노트를 따른다',
    ('wiki', 'evelynn', 'ability', '1050/1500/2700'): '도구 한계. 처형 피해(기본 x3)가 기본 피해 변경을 안 따라간다. '
                                                      '시뮬레이터는 피해와 배율 3을 따로 들고 있고 맞다',
    ('riot', 'xinzhao', 'crescent guard attack damage', '300/325/350'): '10.23 리워크가 노트에 A ⇒ B로 안 적혔다. '
                                                                        '10.22까지는 옛 스킬 200/250/350%이고 시뮬레이터가 맞다',
    ('riot', 'warwick', 'fear duration', '0.75/0.75/3'): '10.24 리워크로 공포가 없어졌고 시뮬레이터도 10.24에서 뺐다',
}

# ---------- 위키 ----------
# 패치 이력에서 기본 스탯을 바꾸는 문장은 이 말로 시작한다. 'mama'는 위키 오타(룰루 11.1)다.
BASE_LINE = re.compile(
    r'^(base health|base attack damage|base attack speed|attack speed|maximum ma[nm]a|'
    r'starting mana|base armor|base magic resist\w*|attack range)\b', re.I)
# "increased to 600 from 650", "increased 30 from 20"(to 빠진 오타), "to 2 hexes from 3"
PAIR = re.compile(r'(?:\bto\s+)?(' + NUM + r')\s*%?\s*(?:hexes|hex|seconds|second)?\s+from\s+(' + NUM + r')')
# "500/700/3000", "350*2.5/600*2.5/1500*2.5"
TRIP = r'(?:\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)?/)+\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)?'
TPAIR = re.compile(r'to\s+(' + TRIP + r')[^/]*?\bfrom\s+(' + TRIP + r')')
TRIP_RE = re.compile(TRIP)

# ---------- 라이엇 ----------
# "Attack Speed: 0.65 ⇒ 0.75", "Armor 25 ⇒ 20", "1000 Daggers damage: 300/400/600/900 ⇒ ..."
NOTE = re.compile(r'^(?P<what>.*?)[:\s]\s*(?P<before>' + NUMS + r')\s*%?\s*(?:seconds?|sec)?\s*'
                  r'⇒\s*(?P<after>' + NUMS + r')')
BASE_WHAT = {'attack speed': ['as'], 'health': ['hp'], 'armor': ['arm'], 'magic resist': ['mr'],
             'attack damage': ['ad'], 'starting/total mana': ['startmana', 'mana'],
             'total mana': ['mana'], 'max mana': ['mana'], 'starting mana': ['startmana']}


def vernum(v):
    m = re.match(r'V?(\d+)\.(\d+)', v)
    return (int(m.group(1)), int(m.group(2))) if m else None


def base_key(phrase):
    p = phrase.lower()
    if p.startswith('base magic resist'):
        return 'mr'
    return {'base health': 'hp', 'base attack damage': 'ad', 'base attack speed': 'as',
            'attack speed': 'as', 'maximum mana': 'mana', 'maximum mama': 'mana',
            'starting mana': 'startmana', 'base armor': 'arm', 'attack range': 'range'}[p]


def parse_trip(s):
    out = []
    for part in s.split('/'):
        v = 1.0
        for f in part.split('*'):
            v *= float(f)
        out.append(v)
    return out


def matches(t, s):
    if not isinstance(s, list):
        s = [s]
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in s):
        return False
    s2 = s[1:] if (len(s) > len(t) and s[0] == 0) else s  # 시뮬레이터는 [0, 1성, 2성, 3성]
    if len(s2) < len(t):
        return False
    # 시뮬레이터 표기: 45% -> 0.45, 2.5초 -> 2500(ms), 공속 증가 45% -> 1.45(배율),
    # 방어력 50% 감소 -> 0.5(남는 비율. 바이 ABILITY_ARMOR_DECREASE, 요네 ABILITY_ARMOR_MR_DECREASE)
    for f in (lambda a: a, lambda a: a * 0.01, lambda a: a * 1000, lambda a: 1 + a * 0.01,
              lambda a: 1 - a * 0.01):
        # 절대 허용치 2e-4: 바이 3성 방어력 100% 감소를 0 대신 0.0001로 둔다
        if all(abs(f(float(a)) - float(b)) <= 2e-4 + 1e-3 * abs(float(b))
               for a, b in zip(t, s2[:len(t)])):
            return True
    return False


def fmt(x):
    if isinstance(x, list):
        return '/'.join(fmt(v) for v in x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def snapshot():
    """패치별로 apply_patch 를 실제로 돌리고 챔피언마다 기본 스탯과 스킬 표를 떠 둔다."""
    tables = [n for n in dir(champ_stats)
              if not n.startswith('_') and isinstance(getattr(champ_stats, n), dict)]
    snap = {}
    for patch in PATCHES:
        pm.apply_patch(patch)
        snap[patch] = {}
        for champ in DISPLAY:
            base = {wk: getattr(champ_stats, sk).get(champ) for wk, sk in BASE.items()}
            abil = {n: getattr(champ_stats, n)[champ] for n in tables
                    if n not in NOT_ABILITY and champ in getattr(champ_stats, n)}
            snap[patch][champ] = {'base': base, 'abil': abil}
    return snap


def found(t, abil):
    return any(matches(t, v) for v in abil.values())


# ---------- 위키 대조 ----------

def wiki_base_at(unit, hist, target):
    """섹션 값(11.1 상태)에서 target 패치 이후의 변경을 전부 되돌린다. hist는 최신순."""
    vals = {k: unit.get(k) for k in BASE}
    for block in hist:
        v = vernum(block['v'])
        if v is None or v <= target:
            continue
        for line in block['l']:
            m = BASE_LINE.match(line)
            if not m:
                continue
            p = PAIR.search(line[m.end():])
            if p:
                vals[base_key(m.group(1))] = float(p.group(2))  # from 값
    return vals


def wiki_abilities_at(hist, target):
    """V10.19 설명문의 수치에서 출발해 target 까지의 변경을 앞으로 적용한다."""
    # 같은 패치 안에서는 본 패치가 먼저, 핫픽스("V10.22 - October 30th Hotfix")가 나중이다.
    blocks = sorted((b for b in hist if vernum(b['v'])),
                    key=lambda b: (vernum(b['v']), ' - ' in b['v']))
    cur, singles, unresolved, notes = [], [], [], []
    for i, b in enumerate(blocks):
        if vernum(b['v']) > target:
            break
        for line in b['l']:
            if i == 0:  # 출시 설명문. "from behind him" 같은 문장도 설명문이다
                cur += [parse_trip(t) for t in TRIP_RE.findall(line)]
            elif line.startswith('New Effect'):  # 리워크. 새 수치가 들어온다
                cur += [parse_trip(t) for t in TRIP_RE.findall(line)]
                notes.append((b['v'], line))
            elif line.startswith('Old Effect'):
                for t in map(parse_trip, TRIP_RE.findall(line)):
                    if t in cur:
                        cur.remove(t)
            elif line.startswith('Removed'):
                notes.append((b['v'], line))
            elif ' from ' in line:
                m = TPAIR.search(line)
                if m:
                    to, frm = parse_trip(m.group(1)), parse_trip(m.group(2))
                    if frm in cur:
                        cur[cur.index(frm)] = to
                    else:
                        unresolved.append((b['v'], line))
                        cur.append(to)
                elif not BASE_LINE.match(line):
                    singles.append((b['v'], line))
    return cur, singles, unresolved, notes


def wiki_pass(snap, units, hist_all):
    rows = []
    for champ, u in units.items():
        if u['tier'] != champ_stats.COST.get(champ):
            rows.append(['wiki', champ, '*', 'cost', u['tier'], champ_stats.COST.get(champ), 'MISMATCH', ''])
    for patch in PATCHES:
        target = vernum(patch)
        for champ, u in units.items():
            hist = hist_all[champ]
            s = snap[patch][champ]
            wb = wiki_base_at(u, hist, target)
            for wk in BASE:
                sv, wv = s['base'][wk], wb[wk]
                if sv is None or wv is None or abs(float(sv) - float(wv)) > 1e-6:
                    rows.append(['wiki', champ, patch, wk, fmt(wv), fmt(sv), 'MISMATCH', ''])
            trips, singles, unresolved, notes = wiki_abilities_at(hist, target)
            for t in trips:
                if not found(t, s['abil']):
                    rows.append(['wiki', champ, patch, 'ability', fmt(t), s['abil'], 'NOT_FOUND', ''])
            if patch == PATCHES[-1]:  # 아래는 패치마다 같으니 한 번만 적는다
                for ver, line in unresolved:
                    rows.append(['wiki', champ, ver, 'ability-chain', '', '', 'UNRESOLVED', line])
                for ver, line in singles + notes:
                    rows.append(['wiki', champ, ver, 'scalar/mechanic', '', '', 'REVIEW', line])
    return rows


# ---------- 라이엇 대조 ----------

def split_champ(line):
    for name in NAMES_LONGEST_FIRST:
        if line.startswith(name) and line[len(name):len(name) + 1] in (' ', ':'):
            return NAME2SIM[name], line[len(name):].strip(' :')
    return None, None


def riot_chains(notes):
    """챔피언별로 같은 값의 변경을 이어 붙인다. 이름이 패치마다 달라도(리븐 Sweeping Strikes /
    Energy Slash) 앞 변경의 결과가 다음 변경의 출발값이면 같은 값으로 본다."""
    base = collections.defaultdict(list)    # (champ, field) -> [(pkey, before, after, line)]
    abil = collections.defaultdict(list)    # champ -> [{'what':.., 'steps':[...]}]
    mech = []
    for patch, d in notes.items():
        if patch.startswith('_'):
            continue
        for hotfix, lines in ((False, d['main']), (True, d['hotfix'])):
            pkey = (vernum(patch), hotfix)
            for line in lines:
                champ, rest = split_champ(line)
                if not champ:
                    continue
                m = NOTE.match(rest)
                if not m:
                    mech.append((champ, patch, line))
                    continue
                what = m['what'].strip().lower()
                before, after = parse_trip(m['before']), parse_trip(m['after'])
                if what in BASE_WHAT:
                    for f, b, a in zip(BASE_WHAT[what], before, after):
                        base[(champ, f)].append((pkey, b, a, line))
                    continue
                chain = next((c for c in abil[champ] if c['steps'][-1][2] == before), None) or \
                    next((c for c in abil[champ] if c['what'] == what), None)
                if chain is None:
                    chain = {'what': what, 'steps': []}
                    abil[champ].append(chain)
                chain['steps'].append((pkey, before, after, line))
    for steps in list(base.values()) + [c['steps'] for cs in abil.values() for c in cs]:
        steps.sort(key=lambda s: s[0])
    return base, abil, mech


def expected_at(steps, patch):
    val, src = steps[0][1], '(첫 변경 전 값) ' + steps[0][3]
    for pkey, before, after, line in steps:
        if pkey <= (vernum(patch), True):
            val, src = after, line
    return val, src


def riot_pass(snap, notes):
    base, abil, mech = riot_chains(notes)
    rows = []
    for patch in PATCHES:
        for (champ, field), steps in base.items():
            exp, src = expected_at(steps, patch)
            sv = snap[patch][champ]['base'][field]
            if sv is None or abs(float(sv) - exp) > 1e-6:
                rows.append(['riot', champ, patch, field, fmt(exp), fmt(sv), 'MISMATCH', src])
        for champ, chains in abil.items():
            for c in chains:
                exp, src = expected_at(c['steps'], patch)
                a = snap[patch][champ]['abil']
                hit = {n for n, v in a.items() if matches(exp, v)}
                c.setdefault('hits', []).append(hit)
                if not hit:
                    rows.append(['riot', champ, patch, c['what'], fmt(exp), a, 'NOT_FOUND', src])
    # 같은 값이 패치마다 다른 표에서 잡히면 다른 표의 같은 숫자에 우연히 걸린 것일 수 있다.
    # 리 신 10.23 주변 적 기절(1.5/2/10)이 같은 숫자의 주 대상 기절 표에 걸려 놓쳤던 적이 있다.
    for champ, chains in abil.items():
        for c in chains:
            hits = [h for h in c['hits'] if h]
            if hits and not set.intersection(*hits):
                rows.append(['riot', champ, '*', c['what'], '', [sorted(h) for h in c['hits']],
                             'TABLE_SHIFT', '패치마다 다른 표에서 잡혔다'])
    for champ, patch, line in mech:
        rows.append(['riot', champ, patch, 'mechanic', '', '', 'REVIEW', line])
    return rows


def main():
    with open(os.path.join(HERE, 'wiki_set4_units.json'), encoding='utf-8') as f:
        units = json.load(f)
    with open(os.path.join(HERE, 'wiki_set4_patch_history.json'), encoding='utf-8') as f:
        hist_all = json.load(f)
    with open(os.path.join(HERE, 'riot_notes_set4.json'), encoding='utf-8') as f:
        notes = json.load(f)
    assert set(units) == set(DISPLAY) == set(hist_all), '챔피언 목록이 어긋난다'

    snap = snapshot()
    rows = riot_pass(snap, notes) + wiki_pass(snap, units, hist_all)
    for r in rows:
        reason = KNOWN.get((r[0], r[1], r[3], str(r[4])))
        if reason:
            r[6], r[7] = 'KNOWN', reason

    path = os.path.join(HERE, 'mismatch_set4.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['source', 'champ', 'patch', 'field', 'expected', 'sim', 'status', 'note'])
        w.writerows(rows)

    print()
    for src in ('riot', 'wiki'):
        cnt = collections.Counter(r[6] for r in rows if r[0] == src)
        print(src, dict(cnt))
    print(f'\n저장: {path}  ({len(rows)}줄)')


if __name__ == '__main__':
    main()
