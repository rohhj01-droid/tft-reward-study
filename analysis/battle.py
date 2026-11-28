"""
전투 하네스.

시뮬레이터의 전투 엔진을 감싸서, 보드 두 개를 넣으면 승자를 돌려준다.
경제/의사결정을 배제하고 "이 보드가 저 보드를 이기는가"만 떼어내서 볼 때 쓴다.

보드는 dict 리스트로 표현한다.
    [{"name": "yasuo", "stars": 2, "items": []}, ...]

시뮬레이터 저장소가 필요하다(README 참고).
"""
import random

import Simulator.config as config
import Simulator.champion as champion_module
import Simulator.field as field
from Simulator.champion import champion
from Simulator.origin_class_stats import origin_class
from Simulator.pool import pool
from Simulator.player import Player
from Simulator.stats import RANGE
from Simulator.utils import coord_to_x_y
from Simulator.observation.token.action import ActionToken

# 가운데 칸부터 바깥으로 채운다
CENTER_OUT = [3, 2, 4, 1, 5, 0, 6]
# 구석 칸부터 안으로 채운다
CORNER_OUT = [0, 6, 1, 5, 2, 4, 3]


def range_positions(units):
    """근접(사거리 1)은 맨 앞줄(y=3), 원거리는 맨 뒷줄(y=0)에 가운데부터 놓는다. 줄이 차면 한 줄 안쪽으로.
    전투는 두 보드의 y=3끼리 마주 보게 놓는다(champion.run)."""
    # ponytail: 캐리를 구석에 숨기는 것 같은 사람의 판단은 없다. 배치가 결과를 가르면 여기부터 고친다.
    rows = {True: [3, 2], False: [0, 1]}
    used = {True: 0, False: 0}
    spots = []
    for unit in units:
        melee = RANGE[unit.name] <= 1
        k = used[melee]
        used[melee] += 1
        spots.append((CENTER_OUT[k % 7], rows[melee][k // 7]))
    return spots


def corner_positions(units):
    """원거리는 뒷줄 구석부터 아이템이 많은 순으로, 근접은 range_positions처럼 앞줄 가운데부터 놓는다. 사람이 캐리를
    구석에 숨기는 배치를 흉내 낸 것이고, 상대를 보고 바꾸는 배치는 아니다. 롤체지지 10.24 최종 보드 대전에서 가운데부터
    놓을 때보다 실제 평균 등수와 더 맞았다(results/README 「원인 떼어 재기 2차」)."""
    spots = [None] * len(units)
    ranged = sorted((i for i, u in enumerate(units) if RANGE[u.name] > 1), key=lambda i: -len(units[i].items))
    melee = [i for i, u in enumerate(units) if RANGE[u.name] <= 1]
    for k, i in enumerate(ranged):
        spots[i] = (CORNER_OUT[k % 7], [0, 1][k // 7])
    for k, i in enumerate(melee):
        spots[i] = (CENTER_OUT[k % 7], [3, 2][k // 7])
    return spots


# 든 유닛과 같은 줄 옆 칸의 같은 편에게 효과를 주는 아이템
ROW_ITEMS = ('zekes_herald', 'chalice_of_power', 'locket_of_the_iron_solari')


def effect_positions(units):
    """구석 배치(corner_positions)에, 배치에 따라 달라지는 효과 셋을 살리는 규칙을 더한다(2026-11-26, 유저: 「그런 효과들
    고려 안 하고 막 배치하면 안 돼」). 규칙은 효과 설명에서 바로 나오는 것만이고, 해당하는 효과가 없는 보드는 구석 배치 그대로다.
      1. 추방자는 옆 칸에 같은 편이 없어야 보호막을 받는다 -> 앞줄 양 끝에 혼자 세우고 그 옆 칸을 비운다.
      2. ROW_ITEMS를 든 유닛은 제 줄(근접 앞줄, 원거리 뒷줄)에서 아이템이 가장 많은 유닛 바로 옆에 서고, 그 줄의 나머지는
         가까운 칸부터 붙어 선다. 든 유닛끼리는 자리가 있으면 붙이지 않는다(사이에 선 유닛이 둘 다 받게).
      3. 수호자는 자기와 옆 칸에 보호막을 준다 -> 특성이 켜지면 수호자들을 아이템이 가장 많은 유닛(추방자 제외) 옆 칸으로 모은다.
         근접 수호자는 앞쪽 칸, 원거리 수호자는 뒤쪽 칸부터다. ROW_ITEMS를 든 수호자는 그 유닛과 같은 줄부터다.
    """
    # ponytail: 상대 자리에 걸리는 효과(서풍, 침묵의 장막, 암살자), 아지르 모래 병사 자리, 든 유닛을 다른 줄로 옮기는 것,
    # 수호자가 아닌 유닛까지 뭉치는 것은 다루지 않는다. 그때 자료를 조사해서 넣는다.
    n = range(len(units))
    melee = [RANGE[u.name] <= 1 for u in units]
    count = lambda i: len(units[i].items)
    row_item = lambda i: any(it in units[i].items for it in ROW_ITEMS)
    exile = [i for i in n if 'exile' in origin_class[units[i].name]][:2]
    keeper = [i for i in n if 'keeper' in origin_class[units[i].name]]
    if len(keeper) + any(u.chosen == 'keeper' for u in units) < 2:  # 수호자로 선택받은 유닛은 둘로 센다
        keeper = []
    holder = [i for i in n if i not in exile and i not in keeper and row_item(i)]
    if not (exile or keeper or holder):
        return corner_positions(units)

    cells = [(x, y) for y in range(4) for x in range(7)]
    dist = lambda a, b: field.distance({'y': a[1], 'x': a[0]}, {'y': b[1], 'x': b[0]}, False)
    order = {True: [(x, y) for y in (3, 2) for x in CENTER_OUT], False: [(x, y) for y in (0, 1) for x in CORNER_OUT]}  # 구석 배치의 칸 순서
    spots, blocked = {}, set()
    free = lambda c: c not in blocked and c not in spots.values()
    first = lambda m: next(c for c in order[m] if free(c))
    for i, c in zip(exile, [(6, 3), (0, 3)]):
        spots[i] = c
        blocked.update(d for d in cells if dist(c, d) == 1)
    rest = [i for i in n if i not in exile]
    if rest:
        anchor = max(rest, key=lambda i: (count(i), not melee[i]))  # 아이템이 가장 많은 유닛. 같으면 원거리, 그다음은 앞 순서
        if keeper:
            spots[anchor] = first(melee[anchor])
        for m in (melee[anchor], not melee[anchor]):
            held = [i for i in holder if melee[i] == m]
            if not held:
                continue
            row = sorted((i for i in rest if melee[i] == m and (i not in keeper or i == anchor)), key=lambda i: -count(i))
            top = row[0]
            spots.setdefault(top, first(m))
            home = spots[top]
            line = lambda: sorted((c for c in cells if c[1] == home[1] and free(c)), key=lambda c: (abs(c[0] - home[0]), c[0]))
            taken = [home] if row_item(top) else []
            for i in held + row:  # 든 유닛 먼저, 그다음 그 줄의 나머지
                if i in spots or not line():
                    continue
                apart = [c for c in line() if all(abs(c[0] - t[0]) != 1 for t in taken)] if i in held else []
                spots[i] = (apart or line())[0]
                if i in held:
                    taken.append(spots[i])
        for k in sorted(keeper, key=lambda i: -count(i)):
            if k not in spots:
                a = spots[anchor]
                spots[k] = min((c for c in cells if free(c)),
                               key=lambda c: (dist(a, c), row_item(k) and c[1] != a[1], -c[1] if melee[k] else c[1], c[0]))
    left = {True: [i for i in n if i not in spots and melee[i]],
            False: sorted((i for i in n if i not in spots and not melee[i]), key=lambda i: -count(i))}
    for m in (True, False):
        for i in left[m]:
            spots[i] = next((c for c in order[m] + cells if free(c)), None) or next(c for c in cells if c not in spots.values())
    return [spots[i] for i in n]


def aim_positions(units, enemy):
    """효과 배치(effect_positions)에서 서풍을 든 유닛만 옮긴다(2026-11-28, results/README 「마지막 대전 붙이기: 서풍 겨누기 —
    미리 정한 읽기」). 서풍은 든 유닛 칸을 판 한가운데 기준으로 돌린 상대 칸에서 가장 가까운 적을 5초 동안 뺀다. 그래서 겨눌 적이
    자기 보드에서 선 칸과 같은 내 칸에 든 유닛을 놓는다(그때 배치 조사). 겨눌 적은 상대 보드에서 아이템이 가장 많은 유닛이다
    (같으면 원거리, 그다음은 앞 순서). 10.24에서 수은을 든 유닛은 서풍에 뜨지 않았으니 수은 든 유닛은 겨누지 않는다. 든 유닛이
    둘이면 둘째는 다음 유닛을 겨눈다. 그 칸에 내 유닛이 있으면 자리를 맞바꾼다. 상대 자리는 상대의 효과 배치다."""
    # ponytail: 상대도 서풍으로 옮긴 뒤의 자리와, 서풍을 맞은 상대가 캐리를 옮기는 것은 보지 않는다(늘 맞히는 쪽의 위쪽 끝)
    spots = effect_positions(units)
    holders = [i for i, u in enumerate(units) if 'zephyr' in u.items]
    if not holders:
        return spots
    enemy = sorted(enemy, key=lambda u: u.name == 'azir')  # build_player와 같은 순서라야 상대 자리가 보드와 같다
    where = effect_positions(enemy)
    targets = sorted((j for j, u in enumerate(enemy) if 'quicksilver' not in u.items),
                     key=lambda j: (-len(enemy[j].items), RANGE[enemy[j].name] <= 1, j))
    for i, j in zip(holders, targets):
        if where[j] in spots:
            spots[spots.index(where[j])] = spots[i]
        spots[i] = where[j]
    return spots


POSITIONS = {'range': range_positions, 'corner': corner_positions, 'effect': effect_positions}


def build_player(base_pool, index, units, place='random', enemy=None):
    p = Player(base_pool, index)
    n = len(units)
    # 레벨은 유닛 수를 담을 만큼만 올린다. 여기서는 경제를 재지 않으니 레벨 비용은 무시한다.
    p.level = max(3, n)
    p.max_units = n
    # 아지르는 보드에 놓일 때 옆 빈칸에 모래 병사 둘을 만든다. 마지막에 놓아야 정해 둔 칸을 병사가 먼저 차지하지 않는다.
    units = sorted(units, key=lambda u: u.name == 'azir')
    spots = aim_positions(units, enemy) if place == 'aim' else POSITIONS[place](units) if place in POSITIONS else None
    for i, unit in enumerate(units):
        p.add_to_bench(unit)
        if spots:
            x, y = spots[i]
        else:
            token = ActionToken(p)
            _, bench_mask = token.create_move_and_sell_action_mask(p)
            # 마스크는 이미 유닛이 있는 칸도 허용한다. 그 칸으로 옮기면 두 유닛이 자리를 맞바꿔서
            # 한 명이 벤치로 밀려난다(8명 보드에서 평균 1명). 그래서 빈칸만 고른다.
            valid = [c for c in range(28) if bench_mask[0][c] and p.board[c // 4][c % 4] is None]
            if not valid:
                # 자리가 없으면 그 유닛은 벤치에 남는다. 보드가 조용히 작아지니 승률이 흔들리면 여기를 의심한다.
                continue
            # 좌표는 무작위다. 전열/후열 배치까지 맞추면 그건 다른 실험이 된다.
            x, y = coord_to_x_y(random.choice(valid))
        p.move_bench_to_board(0, x, y)
    if place in ('effect', 'aim'):
        # 시뮬레이터가 아지르 옆(자리가 없으면 앞줄 오른쪽 끝 둘레)에 놓는 모래 병사가 추방자 옆에 서면 추방자 보호막이 꺼진다.
        # 그런 병사는 추방자 옆이 아닌 가장 가까운 빈칸으로 옮긴다.
        cells = [(cx, cy) for cx in range(7) for cy in range(4)]
        dist = lambda a, b: field.distance({'y': a[1], 'x': a[0]}, {'y': b[1], 'x': b[0]}, False)
        beside = lambda c: any(dist(c, e) == 1 for e in cells if p.board[e[0]][e[1]] and 'exile' in origin_class[p.board[e[0]][e[1]].name])
        for c in cells:
            if p.board[c[0]][c[1]] and p.board[c[0]][c[1]].name == 'sandguard' and beside(c):
                to = min((d for d in cells if not p.board[d[0]][d[1]] and not beside(d)), key=lambda d: (dist(c, d), d))
                p.move_board_to_board(*c, *to)
    return p


def to_units(spec):
    # champion()의 두 번째 위치 인자는 stars가 아니라 team이다. 반드시 stars= 로 넘긴다.
    # chosen은 선택받은 자 특성 이름이다. 없으면 선택받은 자가 아니다.
    return [champion(u['name'], stars=u['stars'], itemlist=list(u.get('items', [])),
                     chosen=u.get('chosen', False))
            for u in spec]


def battle(units_a, units_b, place='random'):
    """전투 1회. 반환값 1 = A승, 2 = B승, 0 = 무승부. place는 'random'(무작위), 'range'(range_positions),
    'corner'(corner_positions)다."""
    base_pool = pool()
    pa = build_player(base_pool, 0, units_a, place)
    pb = build_player(base_pool, 1, units_b, place)
    pa.opponent, pb.opponent = pb, pa
    # Warlord 승수는 config 전역이라 판을 넘어 쌓인다. 안 지우면 뒤로 갈수록 이긴 쪽이 더 세진다.
    config.WARLORD_WINS['blue'] = 0
    config.WARLORD_WINS['red'] = 0
    result, _ = champion_module.run(champion_module.champion, pa, pb, 0)
    return result


def win_rate(spec_a, spec_b, n=40, place='random'):
    """A의 승률. 진영 유리를 없애기 위해 매 판 좌우를 바꿔 붙인다."""
    wins = draws = 0
    for i in range(n):
        if i % 2 == 0:
            result = battle(to_units(spec_a), to_units(spec_b), place)
            if result == 1:
                wins += 1
            elif result == 0:
                draws += 1
        else:
            result = battle(to_units(spec_b), to_units(spec_a), place)
            if result == 2:
                wins += 1
            elif result == 0:
                draws += 1
    # 무승부는 0.5로 센다. n=40이면 표준오차가 8%p쯤이라 몇 %p 차이는 노이즈로 본다.
    return (wins + 0.5 * draws) / n
