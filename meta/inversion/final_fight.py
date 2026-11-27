"""실제 판의 마지막 대전(1등과 2등의 끝 보드)을 시뮬레이터에서 붙인다(판정 없음, 읽기만, 2026-11-25,
results/README 「실제 판의 마지막 대전을 시뮬레이터에서 붙이기: 미리 정한 읽기」).

입력은 meta/inversion/final_pairs.py가 뽑은 대전이다(저장소 밖). 봇 운영이 섞이지 않고, 두 보드와 실제로 이긴 쪽(1등)을 안다.

보드 만들기: 유닛·별·아이템·선택받은 자는 기록 그대로다. 기록에 없어서 정해 넣는 것은 다음과 같다.
  배치: 근접은 앞줄 가운데부터, 원거리는 뒷줄 구석부터 아이템이 많은 순(analysis/battle.corner_positions).
        --place effect는 여기에 추방자·수호자·같은 줄 아이템을 살리는 규칙을 더한 배치다(analysis/battle.effect_positions).
  총사령관 승리 수: 상한 5(끝까지 간 보드라서). 케인 형태: 없음(meta/real_boards.py와 같다).
  도적의 장갑(99): 기록에 그 대전에서 나온 두 아이템이 같이 적혀 있다. 장갑은 빼고 그 두 아이템을 그대로 든다.
  값: 시뮬레이터의 지금 값(10.24 중간 패치 뒤). 기록은 10.24 전체다.
아이템 번호는 재료 번호(1 대검, 2 곡궁, 3 지팡이, 4 눈물, 5 조끼, 6 망토, 7 벨트, 8 뒤집개, 9 장갑) 둘을 이은 것이다.

만든 보드의 특성 수가 기록과 다른 보드가 낀 대전은 쓰지 않는다(기록에 안 보이는 유닛이나 아이템이 있다).
대전마다 n번 붙이고(자리를 번갈아), 앞 절반과 뒤 절반에서 1등 보드가 이긴 수를 따로 적는다(비김은 0.5).
읽기: 시뮬레이터가 맞힌 몫(승률이 0.5를 넘는 쪽이 실제 1등인 대전의 몫, 0.5면 반)을 전투 없이 세는 어림 셋(보드 값, 완성 아이템 수,
      레벨이 큰 쪽) 가운데 가장 잘 맞힌 것과 견준다.
함께 적는 값(읽기 아님): W = 실제로 이긴 보드의 시뮬레이터 승률 평균. N = 실제 승패가 시뮬레이터의 승률대로 뽑혔다면 W가 가졌을 값
      (두 절반의 승률 a, b로 a·b + (1-a)(1-b)의 평균. 절반을 나눠야 치우치지 않는다). S = (W - 0.5) ÷ (N - 0.5).
      마지막 대전은 진 쪽이 죽어야 마지막이 되므로 체력이 넉넉했던 쪽이 이긴 것으로 치우쳐 잡힌다. 그래서 S로는 맞고 틀림을 정하지 않는다.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·.):
    python meta/inversion/final_fight.py check PAIRS    (보드 만들기 확인: 만든 보드의 특성 수가 기록과 같은가)
    python meta/inversion/final_fight.py run PAIRS --pairs 6000 --n 20 --jobs 4 --partial logs/final_fight.jsonl --out meta/inversion/final_fight_rows.json
    python meta/inversion/final_fight.py read PAIRS meta/inversion/final_fight_rows.json results/final_fight.json
    python meta/inversion/final_fight.py selfcheck      (읽는 셈만 본다. 시뮬레이터 없이 돈다)
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter

from set4 import CHAMPION_TRAITS, COST_STAR_VALUE, cost_of
from meta.real_games import family

COMPONENT = [None, 'bf_sword', 'recurve_bow', 'needlessly_large_rod', 'tear_of_the_goddess', 'chain_vest', 'negatron_cloak',
             'giants_belt', 'spatula', 'sparring_gloves']
WARLORD_WINS = 5
BASELINES = ('value', 'items', 'level')
BOOT, BOOT_SEED = 1000, 0
BINS = (0.6, 0.7, 0.8, 0.9, 1.0)


def trait(name):
    return 'the_boss' if name == 'Boss' else name.lower()


def item_names():
    """아이템 번호 -> 시뮬레이터 이름."""
    from Simulator.item_stats import item_builds
    made = {tuple(sorted(parts)): name for name, parts in item_builds.items()}
    out = {i: COMPONENT[i] for i in range(1, 10)}
    out.update({10 * a + b: made[tuple(sorted((COMPONENT[a], COMPONENT[b])))] for a in range(1, 10) for b in range(a, 10)})
    return out


def spec(board, items):
    """기록의 보드 -> analysis/battle 형식."""
    out = []
    for name, stars, ids in board['units']:
        u = {'name': name.lower(), 'stars': stars, 'items': [items[i] for i in ids if i != 99]}
        if board['chosen'] and board['chosen'][0] == name:
            u['chosen'] = trait(board['chosen'][1])
        out.append(u)
    return out


def counted(units):
    """analysis/battle 형식의 보드 -> 특성 수(선택받은 자는 그 특성에 둘로 세고, 상징 아이템은 없는 특성을 하나 더한다)."""
    from Simulator.item_stats import trait_items
    emblem = {item: t for t, item in trait_items.items()}
    c = Counter()
    for u in units:
        c.update(set(CHAMPION_TRAITS[u['name']]) | {emblem[i] for i in u['items'] if i in emblem})
        if u.get('chosen'):
            c[u['chosen']] += 1
    return dict(c)


def faithful(board, items):
    """만든 보드의 특성 수가 기록과 같은가. 다르면 기록에 안 보이는 유닛이나 아이템이 있는 것이다(같은 유닛 두 장 등)."""
    return counted(spec(board, items)) == {trait(t): n for t, n in board['traits'].items()}


def usable(pairs):
    """두 보드 모두 특성 수가 기록과 같은 대전의 번호."""
    items = item_names()
    return [k for k, p in enumerate(pairs) if all(faithful(b, items) for b in p['boards'])]


def check(pairs):
    items = item_names()
    boards = [b for p in pairs for b in p['boards']]
    same = sum(faithful(b, items) for b in boards)
    print(f'보드 {len(boards)}개 가운데 특성 수가 기록과 같은 보드 {same}개({same / len(boards):.4f}), 두 보드 모두 같은 대전 {len(usable(pairs))}개')


def check_stars():
    """별 처리 셋이 싸우는 유닛을 뜻한 대로 만드는가. 선택받은 자 베인 3성(기본 체력 500, 스킬 값 90·140)과 달빛이 올린 다이애나."""
    import Simulator.champion as cm
    from Simulator.pool import pool
    from Simulator.stats import ACTIVE_DMG
    from analysis.battle import build_player
    board = [{'name': 'vayne', 'stars': 3, 'items': [], 'chosen': 'sharpshooter'}]
    import Simulator.origin_class_stats as ocs
    assert DUELISTS == {k for k, v in ocs.origin_class.items() if 'duelist' in v}, '결투가 유닛 목록이 시뮬레이터와 다르다'
    got = {}
    for variant in ('harness', 'june', 'fixed'):
        unit = build_player(pool(), 0, make_units(board, variant), 'corner').board[0][0]  # 구석 배치는 원거리 첫 유닛을 (0, 0)에 둔다
        fighter = (fixed_champion() if variant == 'fixed' else cm.champion)('vayne', 'blue', 0, 0, unit.stars, unit.items, False, None, unit.chosen)
        got[variant] = (fighter.stars, fighter.max_health, fighter.AD, ACTIVE_DMG['vayne'][fighter.stars])
    # 체력 = 기본 500 x 1.8^(별 - 1) + 선택받은 자 200, 공격력 = 기본 40 x 1.8^(별 - 1)
    assert got == {'harness': (2, 1100.0, 72.0, 90), 'june': (2, 1820.0, 129.6, 90), 'fixed': (3, 1820.0, 129.6, 140)}, got
    for stars, want in ((1, (900.0, 90.0)), (2, (1620.0, 162.0)), (3, (2916.0, 291.6))):  # 다이애나 기본 체력 500, 공격력 50
        d = fixed_champion()('diana', 'blue', 0, 0, stars, [])
        d.golden()
        assert (d.stars, d.max_health, d.health, d.AD) == (stars + 1, *want[:1], want[0], want[1]), (stars, d.max_health, d.AD)
    d = cm.champion('diana', 'blue', 0, 0, 2, [])
    d.golden()
    assert (d.max_health, d.AD) == (2916.0, 291.6)  # 시뮬레이터 그대로: 3성이 4성 값이 된다
    print('별 처리 확인 통과:', got)


ITEMS = None
FIXED = None
# 별 처리(2026-11-25에 찾은 결함 둘, results/README 「마지막 대전 붙이기: 별 처리 결함」).
#   harness: 처음 실행 그대로. 선택받은 자 3성이 2성으로 싸운다(틀의 결함: 유닛을 만들 때 시뮬레이터가 선택받은 자의 별을 2로
#            되돌리고, 그 별로 보드에 올라가 전투가 2성 체력·공격력으로 다시 만든다). 앞 실행을 다시 만들 때만 쓴다.
#   june:    시뮬레이터가 봇 판에서 하는 그대로. 선택받은 자 3성은 체력·공격력만 3성이고 별로 찾는 값(스킬 값 등)은 2성이다.
#            달빛이 별을 올릴 때 (새 별 - 1)제곱을 한 번 더 곱한다(2성을 올리면 1.8배가 아니라 3.24배, 3성이면 5.83배).
#   fixed:   두 결함을 실제 게임대로 고친다. 선택받은 자 3성은 온전한 3성이고, 달빛은 한 단계만 올린다.
# 동작 바꾸기(2026-11-27, results/README 「마지막 대전 붙이기: 결투가·추방자 동작 하나씩 바꾸기 — 미리 정한 읽기」).
# 모두 fixed 위에 하나씩 바꾼다. 시뮬레이터 파일은 그대로 두고, 이 프로세스 안에서만 함수를 감싼다.
#   jax:    잭스 회피(그동안 공격 피해 0)가 고속 연사포를 든 유닛의 공격과 사냥꾼 공격은 막지 않는다
#   stacks: 결투가 중첩은 결투가 본인의 기본 공격으로만 쌓인다(스킬로 하는 공격, 아이템 공격, 특성 공격은 안 쌓는다)
#   move:   결투가의 이동 속도 증가를 뺀다
#   blind:  실명인 야스오의 스킬 공격은 빗나간다
# 야스오 3성 장점 끄기(2026-11-28, results/README 「마지막 대전 붙이기: 야스오 3성 장점 하나씩 끄기 — 미리 정한 읽기」).
# 실제 규칙을 고치는 것이 아니라, 시뮬레이터의 야스오 3성이 무엇으로 이기는지 보려고 야스오 3성에게서만 하나씩 뺀다.
#   no_shield:  추방자 보호막을 받지 않는다(흡혈은 그대로)
#   no_steal:   추방자 흡혈을 받지 않는다(보호막은 그대로)
#   no_duelist: 결투가 공격 속도 중첩을 쌓지 않는다
#   no_dash:    스킬을 쓸 때 돌진하지 않는다. 지금 자리에서 두 명을 칠 수 있으면 그대로 치고, 못 치면 시뮬레이터대로 앞 두 칸을 친다
YASUO_OFF = ('no_shield', 'no_steal', 'no_duelist', 'no_dash')
BEHAVIORS = ('jax', 'stacks', 'move', 'blind') + YASUO_OFF
VARIANTS = ('harness', 'june', 'fixed') + BEHAVIORS
DUELISTS = {'fiora', 'jax', 'kalista', 'leesin', 'xinzhao', 'yasuo'}  # 결투가 유닛(check가 시뮬레이터와 같은지 본다). 결투가의 열정은 28
BASIC = []  # 지금 처리 중인 공격들이 기본 공격인가(안쪽 공격이 끝에)


def chosen_three(board):
    return bool(board['chosen']) and any(u[0] == board['chosen'][0] and u[1] == 3 for u in board['units'])


def affected(pair, variant):
    """앞 실행(별 처리 셋은 harness, 동작 바꾸기는 fixed)과 결과가 달라질 수 있는 대전인가(아니면 같은 시드라 승수가 같다)."""
    names = [{u[0].lower() for u in b['units']} for b in pair['boards']]
    if variant == 'jax':
        return any('jax' in s for s in names)
    if variant in ('stacks', 'move'):
        return any(s & DUELISTS or any(28 in u[2] for u in b['units']) for s, b in zip(names, pair['boards']))
    if variant == 'blind':
        return any('yasuo' in names[i] and 'teemo' in names[1 - i] for i in (0, 1))
    if variant in YASUO_OFF:
        return any(u[0] == 'Yasuo' and u[1] == 3 for b in pair['boards'] for u in b['units'])
    return variant != 'harness' and any(chosen_three(b) or (variant == 'fixed' and b['traits'].get('Moonlight', 0) >= 3) for b in pair['boards'])


def behavior_attack(orig, change):
    """시뮬레이터 champion 모듈의 attack(기본 공격과 스킬·아이템·특성 공격이 모두 지나는 곳)을 감싼다."""
    def attack(champion, target, bonus_dmg=0, item_attack=False, trait_attack='', set_ad=None, on_attack=True, set_true=0):
        casting = getattr(champion, 'harness_casting', False)
        if change == 'blind' and casting and champion.name == 'yasuo' and champion.blinded:
            return  # 10.24부터 야스오 스킬 공격은 실명이면 빗나간다(공식 10.24 노트)
        lift = change == 'jax' and target is not None and target.autoimmune and \
            (trait_attack == 'hunter' or 'rapid_firecannon' in champion.items)
        if lift:
            target.autoimmune = False
        BASIC.append(not (item_attack or trait_attack or casting))
        try:
            return orig(champion, target, bonus_dmg, item_attack, trait_attack, set_ad, on_attack=on_attack, set_true=set_true)
        finally:
            BASIC.pop()
            if lift:
                target.autoimmune = True
    return attack


def behavior_helper(orig):
    """결투가 중첩(origin_class.duelist_helper)을 기본 공격일 때만 쌓는다."""
    def helper(champion):
        if not BASIC or BASIC[-1]:
            orig(champion)
    return helper


def yasuo3(c):
    return c.name == 'yasuo' and c.stars == 3


def yasuo_exile(orig, change, lifesteal):
    """추방자 특성(origin_class.exile)을 둘로 나눠 건다. 야스오 3성이 아닌 유닛은 그대로, 야스오 3성은 보호막(no_shield)이나
    흡혈(no_steal)을 뺀다. 단계는 팀 수로 정하고 옆 칸은 보드에서 보므로 나눠 걸어도 같다. lifesteal = origin_class_stats.lifesteal."""
    def exile(blue_team, red_team):
        orig([c for c in blue_team if not yasuo3(c)], [c for c in red_team if not yasuo3(c)])
        ys = [c for c in blue_team + red_team if yasuo3(c)]
        saved = lifesteal['exile']
        for c in ys:
            if change == 'no_shield':  # 이 호출 동안만 보호막 예약을 버린다(0짜리 보호막도 남기지 않는다)
                c.add_que = (lambda q: lambda action, *a, **kw: None if action == 'shield' else q(action, *a, **kw))(c.add_que)
        if change == 'no_steal':
            lifesteal['exile'] = [0] * len(saved)
        try:
            orig([c for c in blue_team if yasuo3(c)], [c for c in red_team if yasuo3(c)])
        finally:
            lifesteal['exile'] = saved
            for c in ys:
                vars(c).pop('add_que', None)
    return exile


def skip_yasuo3(orig):
    """결투가 중첩(origin_class.duelist_helper)을 야스오 3성만 쌓지 않는다."""
    def helper(champion):
        if not yasuo3(champion):
            orig(champion)
    return helper


def no_dash(orig):
    """야스오 스킬이 칠 자리를 찾는 함수(ability.yasuo_ability)에서 야스오 3성은 지금 자리만 남긴다."""
    def find(champion, data):
        got = orig(champion, data)
        return [p for p in got if list(p[0][0]) == [champion.y, champion.x]] if yasuo3(champion) else got
    return find


def behavior_champion(change):
    """fixed 위에 동작 하나를 바꾼 유닛 틀. 시전 중인지를 유닛에 적어 둔다(스킬로 하는 공격을 가리려고)."""
    import Simulator.ability as ab
    import Simulator.champion as cm
    import Simulator.origin_class as oc
    import Simulator.origin_class_stats as ocs
    Fixed = fixed_champion()
    if change == 'move':
        ocs.movement_delay['duelist'] = 1.0
    if change in ('jax', 'stacks', 'blind'):
        cm.attack = behavior_attack(cm.attack, change)
    if change == 'stacks':
        oc.duelist_helper = behavior_helper(oc.duelist_helper)
    if change in ('no_shield', 'no_steal'):
        oc.exile = yasuo_exile(oc.exile, change, ocs.lifesteal)  # origin_class가 특성 이름으로 찾아 부른다
    if change == 'no_duelist':
        oc.duelist_helper = skip_yasuo3(oc.duelist_helper)
    if change == 'no_dash':
        ab.yasuo_ability = no_dash(ab.yasuo_ability)

    class Behavior(Fixed):
        def cast(self):
            self.harness_casting = True
            try:
                super().cast()
            finally:
                self.harness_casting = False
    return Behavior


def fixed_champion():
    """시뮬레이터를 건드리지 않고 싸우는 유닛만 고친다(champion.run에 넘기는 유닛 틀)."""
    import Simulator.active as active
    import Simulator.champion as cm
    import Simulator.config as config
    from Simulator.stats import AD, HEALTH, INITIATIVE_ACTIVE

    class Fixed(cm.champion):
        def __init__(self, name, team=None, y=-1, x=-1, stars=1, *args, **kwargs):
            super().__init__(name, team, y, x, stars, *args, **kwargs)
            if stars == 3 and self.stars == 2:  # 선택받은 자 3성: 시뮬레이터가 별을 2로 되돌린 것을 3으로
                self.stars = 3
                if name in INITIATIVE_ACTIVE:  # 별로 정하는 처음 값(진 공속, 탐 켄치 피해 감소)을 3성 값으로 다시
                    getattr(active, name + '_init')(self)

        def golden(self):  # 달빛: 기본 체력·공격력의 한 단계 몫만 더한다
            grow = config.STARMULTIPLIER ** self.stars - config.STARMULTIPLIER ** (self.stars - 1)
            self.stars += 1
            self.max_health = round(self.max_health + HEALTH[self.name] * grow, 1)
            self.health = self.max_health
            self.AD = round(self.AD + AD[self.name] * grow, 1)
    return Fixed


def make_units(board, variant):
    """analysis/battle 형식의 보드 -> 보드에 올릴 유닛들."""
    from analysis.battle import to_units
    made = to_units(board)
    if variant != 'harness':
        for u, s in zip(made, board):
            if s.get('chosen') and s['stars'] == 3:
                u.stars = 3  # 보드에 3성으로 올라가야 전투가 3성 체력·공격력으로 만든다(봇 판에서 합쳐 만든 유닛처럼)
    return made


def fights(job):
    """(번호, 대전, n, 배치, 별 처리) -> (번호, [앞 절반에서 1등 보드가 이긴 수, 뒤 절반에서 이긴 수], 오류). 비김은 0.5."""
    global ITEMS, FIXED
    k, pair, n, place, variant = job
    try:
        import Simulator.champion as cm
        import Simulator.config as config
        from Simulator.pool import pool
        from analysis.battle import build_player
        ITEMS = ITEMS or item_names()
        if variant not in ('harness', 'june'):
            FIXED = FIXED or (behavior_champion(variant) if variant in BEHAVIORS else fixed_champion())  # 한 프로세스는 한 실행만 돈다
        fighter = cm.champion if variant in ('harness', 'june') else FIXED
        first, second = (spec(b, ITEMS) for b in pair['boards'])
        random.seed(k)
        won = [0, 0]
        for i in range(n):
            blue, red = (first, second) if i % 2 == 0 else (second, first)  # 진영 유리를 없애려고 자리를 번갈아 붙인다
            base = pool()
            pa, pb = build_player(base, 0, make_units(blue, variant), place), build_player(base, 1, make_units(red, variant), place)
            pa.opponent, pb.opponent = pb, pa
            config.WARLORD_WINS['blue'] = config.WARLORD_WINS['red'] = WARLORD_WINS
            result = cm.run(fighter, pa, pb, 0)[0]
            won[i * 2 // n] += 0.5 if result == 0 else float(result == 1 + i % 2)
        return k, won, None
    except Exception as e:  # 한 대전이 터져도 나머지는 돌린다. 오류는 세어서 적는다
        return k, None, repr(e)


def run(pairs, count, n, jobs, partial, place='corner', variant='harness', reuse=None):
    from hra.deck_baseline import load_partial
    from hra.plan_bot import pinned_pool
    assert n % 4 == 0, 'n은 4의 배수여야 한다(절반마다 두 자리를 같은 수로)'
    used = usable(pairs)[:count]  # 섞어 둔 순서의 앞에서부터, 만든 보드가 기록과 맞는 대전만
    assert len(used) == count, '쓸 수 있는 대전이 모자란다'
    done = load_partial(partial)
    kept = {}
    if reuse:  # 앞 실행과 승수가 같을 대전(바꾼 것이 걸리지 않는 대전)은 다시 붙이지 않고 가져온다
        before = 'fixed' if variant in BEHAVIORS else 'harness'
        assert reuse['used'] == used and reuse['n'] == n and reuse['place'] == place and reuse.get('variant', 'harness') == before
        errors = dict(map(tuple, reuse['errors']))
        kept = {k: [k, w, errors.get(k)] for k, w in zip(used, reuse['won']) if not affected(pairs[k], variant)}
        done.update(kept)
    todo = [(k, pairs[k], n, place, variant) for k in used if k not in done]
    if todo:
        with pinned_pool(jobs) as p, open(partial or os.devnull, 'a', encoding='utf-8') as f:
            for row in p.imap_unordered(fights, todo, chunksize=4):
                done[row[0]] = row
                f.write(json.dumps(row) + '\n')
                f.flush()
    rows = [done[k] for k in used]
    return {'kind': 'final_fight', 'pairs': count, 'n': n, 'warlord_wins': WARLORD_WINS, 'place': place, 'variant': variant, 'reused': len(kept),
            'used': used,
            'errors': [[k, e] for k, _, e in rows if e is not None], 'won': [w for _, w, _ in rows]}


# ---- 읽는 셈(시뮬레이터 없이 돈다) ----

def value(board):
    return sum(COST_STAR_VALUE[cost_of(name.lower()) - 1][stars - 1] for name, stars, _ in board['units'])


def made_items(board):
    return sum(i >= 10 for _, _, ids in board['units'] for i in ids)


def rows_of(pairs, won, n):
    """대전마다 읽는 데 쓰는 값들. p = 1등 보드의 시뮬레이터 승률, a·b = 두 절반의 승률."""
    out = []
    for pair, w in zip(pairs, won):
        if w is None:
            continue
        one, two = pair['boards']
        fam = [family({t.lower(): c for t, c in b['traits'].items()}) for b in (one, two)]
        out.append({'p': sum(w) / n, 'a': 2 * w[0] / n, 'b': 2 * w[1] / n, 'fam': fam, 'levels': [one['level'], two['level']],
                    'value': value(one) - value(two), 'items': made_items(one) - made_items(two), 'level': one['level'] - two['level'],
                    'clean': all(len(b['units']) >= b['level'] for b in (one, two))})
    return out


def stats(rows):
    """W, N, S와 맞힌 몫(큰 쪽이 실제로 이긴 몫. 같으면 반으로 센다)."""
    m = len(rows)
    W = sum(r['p'] for r in rows) / m
    N = sum(r['a'] * r['b'] + (1 - r['a']) * (1 - r['b']) for r in rows) / m

    def hit(key, mid):
        return sum(1 if r[key] > mid else 0.5 if r[key] == mid else 0 for r in rows) / m
    acc = {'sim': hit('p', 0.5), **{k: hit(k, 0) for k in BASELINES}}
    return {'W': W, 'N': N, 'S': (W - 0.5) / (N - 0.5) if N != 0.5 else float('nan'), 'acc': acc,
            **{'sim_minus_' + k: acc['sim'] - acc[k] for k in BASELINES}}


def interval(values):
    v = sorted(values)
    return [round(v[int(0.025 * len(v))], 4), round(v[int(0.975 * len(v)) - 1], 4)]


def boot(rows):
    rng = random.Random(BOOT_SEED)
    draws = [stats(rng.choices(rows, k=len(rows))) for _ in range(BOOT)]
    return {key: interval([d[key] for d in draws]) for key in ('W', 'N', 'S') + tuple('sim_minus_' + k for k in BASELINES)}


def reading(lo, hi):
    """미리 정한 읽기: 시뮬레이터가 맞힌 몫 - 가장 잘 맞힌 어림이 맞힌 몫의 구간."""
    if lo > 0:
        return '시뮬레이터 전투가 세기만 한 어림보다 실제 승자를 더 잘 맞힌다'
    if hi < 0:
        return '시뮬레이터 전투가 세기만 한 어림보다 실제 승자를 못 맞힌다'
    return '세기만 한 어림과 구별되지 않는다'


def calibration(rows):
    """앞 절반으로 「시뮬레이터가 미는 쪽」과 확신을 정하고, 그 쪽이 뒤 절반에서 이긴 몫과 실제로 이긴 몫을 본다."""
    cells = {b: [0, 0.0, 0] for b in ('0.5',) + BINS}
    for r in rows:
        if r['a'] == 0.5:
            cell, later, real = cells['0.5'], 0.5, 0.5
        else:
            first = r['a'] > 0.5  # 시뮬레이터가 미는 쪽이 1등인가
            cell = cells[next(b for b in BINS if max(r['a'], 1 - r['a']) <= b)]
            later, real = (r['b'] if first else 1 - r['b']), float(first)
        cell[0] += 1
        cell[1] += later
        cell[2] += real
    return {str(b): {'fights': c[0], 'sim': round(c[1] / c[0], 4), 'real': round(c[2] / c[0], 4)} for b, c in cells.items() if c[0]}


def one_sided(rows, side):
    """side(대전) -> 0(1등 쪽)·1(2등 쪽)·None(해당 없음). 그 쪽이 실제로 이긴 몫과 시뮬레이터 승률."""
    got = [(s, r['p']) for r in rows for s in [side(r)] if s is not None]
    if not got:
        return None
    return {'fights': len(got), 'real': round(sum(s == 0 for s, _ in got) / len(got), 4),
            'sim': round(sum(p if s == 0 else 1 - p for s, p in got) / len(got), 4)}


def tables(rows):
    fams = sorted({f for r in rows for f in r['fam']})
    by_family = {f: one_sided(rows, lambda r: None if (r['fam'][0] == f) == (r['fam'][1] == f) else int(r['fam'][1] == f)) for f in fams}

    def higher(want):
        def side(r):
            hi, lo = max(r['levels']), min(r['levels'])
            return None if hi == lo or (want and (hi, lo) != want) else int(r['levels'][1] == hi)
        return side
    by_level = {'all': one_sided(rows, higher(None)), '9 vs 8': one_sided(rows, higher((9, 8))), '8 vs 7': one_sided(rows, higher((8, 7)))}
    return {'by_family': by_family, 'higher_level': by_level, 'same_level_fights': sum(r['level'] == 0 for r in rows)}


def read(pairs, rec, src=None):
    rows = rows_of([pairs['pairs'][k] for k in rec['used']], rec['won'], rec['n'])
    s, b = stats(rows), boot(rows)
    best = max(BASELINES, key=lambda k: s['acc'][k])  # 가장 잘 맞힌 어림. 시뮬레이터에게 가장 까다로운 쪽과 견준다
    clean = [r for r in rows if r['clean']]
    out = {'source': {'name': pairs['source']['name'], 'csv_sha256': pairs['source']['csv_sha256'], 'patch': pairs['patch'],
                      'games': pairs['games'], 'dropped': pairs['dropped'], 'pairs_available': len(pairs['pairs'])},
           'sim_record': dict(src or {}, pairs=rec['pairs'], n=rec['n'], warlord_wins=rec['warlord_wins'], place=rec['place'], variant=rec.get('variant', 'harness'),
                              errors=len(rec['errors'])),
           'fights_read': len(rows), 'hit': {k: round(v, 4) for k, v in s['acc'].items()}, 'best_baseline': best,
           'sim_minus_best': round(s['sim_minus_' + best], 4), 'reading': reading(*b['sim_minus_' + best]),
           **{k: round(s[k], 4) for k in ('W', 'N', 'S')}, 'interval': b,
           'calibration': calibration(rows), **tables(rows),
           'clean': {'fights': len(clean), **{k: round(v, 4) for k, v in stats(clean).items() if k in ('W', 'N', 'S')},
                     'interval_S': boot(clean)['S']}}
    return out


def selfcheck():
    def b(level, units, traits):
        return {'level': level, 'units': units, 'traits': traits, 'chosen': None}
    big = b(9, [['Yone', 2, [15, 19]], ['Riven', 2, []]], {'Dusk': 4})
    small = b(8, [['Vayne', 1, [2]]], {'Sharpshooter': 4})
    rows = rows_of([{'boards': [big, small]}, {'boards': [small, big]}, {'boards': [big, big]}, {'boards': [big, small]}],
                   [[10, 8], [2, 4], [5, 5], None], 20)
    assert len(rows) == 3 and [r['p'] for r in rows] == [0.9, 0.3, 0.5] and rows[0]['a'] == 1.0 and rows[0]['b'] == 0.8
    assert rows[0]['fam'] == ['dusk', 'sharpshooter'] and rows[0]['value'] == 14 + 11 - 1 and rows[0]['items'] == 2 and rows[1]['items'] == -2
    assert rows[0]['clean'] is False
    s = stats(rows)
    assert abs(s['W'] - (0.9 + 0.3 + 0.5) / 3) < 1e-9
    assert abs(s['N'] - (0.8 + (0.2 * 0.4 + 0.8 * 0.6) + 0.5) / 3) < 1e-9
    assert s['acc'] == {'sim': 0.5, 'value': 0.5, 'items': 0.5, 'level': 0.5} and s['sim_minus_level'] == 0
    assert stats(rows[:1])['acc'] == {'sim': 1, 'value': 1, 'items': 1, 'level': 1} and stats(rows[1:2])['acc']['items'] == 0
    # 실제 승패가 시뮬레이터 승률대로 뽑히면 S는 1 가까이, 승패가 승률과 무관하면 0 가까이 나온다
    rng = random.Random(1)

    def fake(p, calibrated):
        first = rng.random() < (p if calibrated else 0.5)  # 1등이 될 쪽
        q = p if first else 1 - p
        return {'p': 0, 'a': sum(rng.random() < q for _ in range(10)) / 10, 'b': sum(rng.random() < q for _ in range(10)) / 10,
                'value': 0, 'items': 0, 'level': 0, 'levels': [8, 8], 'fam': ['dusk', 'dusk'], 'clean': True}
    for calibrated, want in ((True, 1), (False, 0)):
        sim = [fake(rng.choice((0.2, 0.35, 0.65, 0.9)), calibrated) for _ in range(20000)]
        for r in sim:
            r['p'] = (r['a'] + r['b']) / 2
        assert abs(stats(sim)['S'] - want) < 0.08, stats(sim)
    cal = calibration(sim[:0] + [{'a': 0.9, 'b': 0.7}, {'a': 0.2, 'b': 0.4}, {'a': 0.5, 'b': 1.0}])
    assert cal == {'0.5': {'fights': 1, 'sim': 0.5, 'real': 0.5}, '0.8': {'fights': 1, 'sim': 0.6, 'real': 0.0},
                   '0.9': {'fights': 1, 'sim': 0.7, 'real': 1.0}}, cal
    t = tables(rows)
    assert t['by_family']['dusk'] == {'fights': 2, 'real': 0.5, 'sim': 0.8} and t['higher_level']['9 vs 8'] == {'fights': 2, 'real': 0.5, 'sim': 0.8}
    assert t['same_level_fights'] == 1
    vayne3 = dict(b(8, [['Vayne', 3, []], ['Diana', 2, []]], {'Sharpshooter': 2}), chosen=['Vayne', 'Sharpshooter'])
    moon = b(8, [['Diana', 3, []]], {'Moonlight': 3})
    assert chosen_three(vayne3) and not chosen_three(dict(vayne3, chosen=['Diana', 'Moonlight'])) and not chosen_three(moon)
    stars = ('harness', 'june', 'fixed')
    assert [affected({'boards': [big, vayne3]}, v) for v in stars] == [False, True, True]
    assert [affected({'boards': [moon, big]}, v) for v in stars] == [False, False, True] and not affected({'boards': [big, small]}, 'fixed')
    # 동작 바꾸기: 잭스가 있는 대전, 결투가(유닛이나 결투가의 열정 28)가 있는 대전, 야스오와 티모가 맞붙는 대전만 다시 붙인다
    jax, zeal = b(8, [['Jax', 2, []]], {}), b(8, [['Ahri', 2, [28]]], {})
    yasuo, teemo = b(8, [['Yasuo', 3, []]], {}), b(8, [['Teemo', 2, []]], {})
    assert [affected({'boards': [jax, big]}, v) for v in BEHAVIORS] == [True, True, True, False] + [False] * 4
    assert [affected({'boards': [big, zeal]}, v) for v in BEHAVIORS] == [False, True, True, False] + [False] * 4
    assert [affected({'boards': [yasuo, teemo]}, v) for v in BEHAVIORS] == [False, True, True, True] + [True] * 4
    assert not any(affected({'boards': [big, teemo]}, v) for v in BEHAVIORS) and not affected({'boards': [yasuo, big]}, 'blind')
    # 야스오 3성 장점 끄기: 야스오 3성이 있는 대전만 다시 붙인다(2성 야스오는 그대로)
    assert all(affected({'boards': [big, yasuo]}, v) for v in YASUO_OFF) and not any(affected({'boards': [b(8, [['Yasuo', 2, []]], {}), big]}, v) for v in YASUO_OFF)
    check_behavior_wrappers()
    assert reading(0.01, 0.05).endswith('더 잘 맞힌다') and reading(-0.05, -0.01).endswith('못 맞힌다') and reading(-0.01, 0.01).endswith('구별되지 않는다')
    big, small = dict(big, level=2), dict(small, level=1)  # 유닛 수 = 레벨인 보드(빠진 유닛이 안 보이는 대전)
    out = read({'source': {'name': 'x', 'csv_sha256': 'y'}, 'patch': '10.24', 'games': 3, 'dropped': {},
                'pairs': [{'boards': [big, small]}, {'boards': [small, big]}, {'boards': [big, big]}]},
               {'pairs': 2, 'n': 20, 'warlord_wins': 5, 'place': 'corner', 'errors': [], 'used': [0, 2], 'won': [[10, 8], [5, 5]]})
    assert out['fights_read'] == 2 and out['hit'] == {'sim': 0.75, 'value': 0.75, 'items': 0.75, 'level': 0.75} and out['sim_minus_best'] == 0
    assert out['clean']['fights'] == 2 and out['reading'] == '세기만 한 어림과 구별되지 않는다'
    print('selfcheck 통과')


def check_behavior_wrappers():
    """동작 바꾸기의 감싸는 함수가 뜻한 대로인가(시뮬레이터 없이 가짜 유닛으로)."""
    from types import SimpleNamespace as U
    seen = []

    def orig(champion, target, bonus_dmg=0, item_attack=False, trait_attack='', set_ad=None, on_attack=True, set_true=0):
        seen.append((champion.name, target.autoimmune, BASIC[-1]))
    unit = lambda name, items=(), **kw: U(name=name, items=list(items), blinded=kw.get('blinded', False), autoimmune=kw.get('autoimmune', False),
                                         **({'harness_casting': True} if kw.get('casting') else {}))
    jax = unit('jax', autoimmune=True)
    a = behavior_attack(orig, 'jax')
    a(unit('ashe'), jax, 10, False, 'hunter')  # 사냥꾼 공격은 잭스 회피를 지난다
    a(unit('vayne', ['rapid_firecannon']), jax)  # 고속 연사포를 든 유닛의 공격도
    a(unit('vayne'), jax)  # 그 밖의 공격은 막힌다
    assert seen == [('ashe', False, False), ('vayne', False, True), ('vayne', True, True)] and jax.autoimmune and BASIC == [], seen
    seen.clear()
    a = behavior_attack(orig, 'blind')
    a(unit('yasuo', casting=True, blinded=True), jax, 50)  # 실명인 야스오의 스킬 공격은 빗나간다
    a(unit('yasuo', casting=True), jax, 50)
    a(unit('yasuo', blinded=True), jax)
    a(unit('ashe'), jax, 30, True)  # 아이템 공격
    assert seen == [('yasuo', True, False), ('yasuo', True, True), ('ashe', True, False)], seen
    stacked = []
    h = behavior_helper(lambda c: stacked.append(c))
    BASIC.append(True)
    h('basic')
    BASIC[-1] = False
    h('ability')
    BASIC.pop()
    assert stacked == ['basic'] and BASIC == [], stacked

    # 야스오 3성 장점 끄기. 가짜 추방자 특성: 유닛마다 보호막을 예약하고, 흡혈 값이 있으면 흡혈을 준다(시뮬레이터 exile과 같은 꼴)
    class Fake:
        def __init__(self, name, stars):
            self.name, self.stars, self.got = name, stars, []

        def add_que(self, action, *a, **kw):
            self.got.append(action)

    table = {'exile': [0, 0, 0.8]}

    def exile(blue, red):
        for c in blue + red:
            c.add_que('shield', -1)
            if table['exile'][2]:
                c.got.append('lifesteal')
    for change, want in (('no_shield', ['lifesteal']), ('no_steal', ['shield'])):
        y3, y2, yone = Fake('yasuo', 3), Fake('yasuo', 2), Fake('yone', 2)
        yasuo_exile(exile, change, table)([y3, yone], [y2])
        assert y3.got == want and y2.got == yone.got == ['shield', 'lifesteal'] and table['exile'] == [0, 0, 0.8], (change, y3.got, y2.got)
        assert 'add_que' not in vars(y3)  # 끝나면 유닛의 보호막 예약은 원래대로
    stacked.clear()
    skip_yasuo3(stacked.append)(Fake('yasuo', 3))
    skip_yasuo3(stacked.append)(Fake('yasuo', 2))
    assert [c.stars for c in stacked] == [2]  # 야스오 3성만 결투가 중첩을 안 쌓는다
    y3, y2 = Fake('yasuo', 3), Fake('yasuo', 2)
    y3.y = y3.x = y2.y = y2.x = 1
    spots = lambda champion, data: [[[[1, 2], 'a', 'b'], 1], [[[1, 1], 'c', 'd'], 0]]  # 시뮬레이터 yasuo_ability 꼴: [[자리, 대상1, 대상2], 거리]
    assert no_dash(spots)(y3, {}) == [[[[1, 1], 'c', 'd'], 0]] and no_dash(spots)(y2, {}) == spots(y2, {})  # 3성은 지금 자리에서만
    assert no_dash(lambda c, d: [[[[1, 2], 'a', 'b'], 1]])(y3, {}) == []  # 지금 자리에서 못 치면 돌진하지 않는다


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('check', 'run', 'read', 'selfcheck'))
    ap.add_argument('files', nargs='*')
    ap.add_argument('--pairs', type=int, default=6000)
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--partial')
    ap.add_argument('--place', choices=('corner', 'range', 'effect'), default='corner')  # range = 원거리도 뒷줄 가운데부터, effect = 효과를 살리는 배치
    ap.add_argument('--variant', choices=VARIANTS, default='harness')  # 별 처리
    ap.add_argument('--reuse')  # harness 실행 기록. 별 처리가 걸리지 않는 대전의 승수를 가져온다
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.mode == 'selfcheck':
        selfcheck()
        sys.exit()
    pairs = json.load(open(a.files[0], encoding='utf-8'))
    if a.mode == 'check':
        check_stars()
        check(pairs['pairs'])
    elif a.mode == 'run':
        res = run(pairs['pairs'], a.pairs, a.n, a.jobs, a.partial, a.place, a.variant, a.reuse and json.load(open(a.reuse, encoding='utf-8')))
        json.dump(res, open(a.out, 'w', encoding='utf-8'))
        print(f"final_fight 대전 {res['pairs']} 오류 {len(res['errors'])} 대전당 {res['n']}번 배치 {res['place']} 별 처리 {res['variant']} 가져온 대전 {res['reused']}")
    else:
        rec = json.load(open(a.files[1], encoding='utf-8'))
        out = read(pairs, rec, {'file': os.path.basename(a.files[1]), 'sha256': sha(a.files[1])})
        json.dump(out, open(a.files[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps({k: out[k] for k in ('fights_read', 'hit', 'best_baseline', 'sim_minus_best', 'reading', 'W', 'N', 'S', 'interval')}, ensure_ascii=False))
