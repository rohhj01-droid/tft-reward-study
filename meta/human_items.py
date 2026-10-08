"""
사람 봇의 아이템 판단(meta/human_bot_design.md 5절). item_action은 행동 하나("6_유닛칸_아이템칸") 또는 None을 돌려준다.

위에서부터 처음 맞는 것 하나를 한다.
0. 만들다 만 아이템 마저 만들기: 보드 유닛의 마지막 아이템이 조각이고, 합쳐질 조각이 아이템 칸에 있으면 올린다.
   회전초밥 유닛이 조각을 들고 온 경우도 여기서 마무리한다. 덱 아이템, 방어 아이템이 되는 짝을 먼저 고른다.
1. 아이템 칸의 완성 아이템 주기(맡겨 둔 유닛을 팔아 돌아온 것 등): 덱 캐리 아이템이면 캐리, 방어 아이템이면 앞줄,
   그 밖은 별이 가장 높은 유닛.
2. 목표 덱 캐리 아이템 만들기: 두 조각이 다 있으면 캐리에게(없으면 맡아 둘 유닛에게) 첫 조각을 올린다.
   맡아 둘 유닛은 보드의 목표 덱 밖 유닛 중 별이 가장 높은 유닛이고, 없으면 만들지 않는다.
3. 방어 아이템(연승형, 2~3단계): 앞줄 유닛(1코스트 2성 포함)에게 첫 조각을 올린다.
4. 조각이 4개를 넘으면: 방어 아이템(전략·단계와 상관없이), 그다음 아무 완성 아이템 순서로 하나를 시작한다.
시뮬레이터는 조각 둘을 같은 유닛에 연달아 올리면 합친다. 그래서 첫 조각을 올린 다음 행동에서 0이 마저 올린다.
"""
from collections import Counter

from Simulator.default_agent_stats import FRONT_LINE_UNITS
from Simulator.item_stats import basic_items, item_builds, trait_items
from Simulator.stats import BASE_CHAMPION_LIST, round_stage
from Simulator.utils import x_y_to_1d_coord
from meta.lobby import carriers

DEFENSIVE = ['sunfire_cape', 'gargoyle_stoneplate', 'bramble_vest', 'dragons_claw', 'warmogs_armor']
# 만들지도 주지도 않는 것: 주걱과 주걱으로 만든 것(특성 아이템, 자연의 힘), 도적의 장갑(설계 5절)
SKIP = {'spatula', 'thieves_gloves', 'force_of_nature'} | set(trait_items.values())
PAIR = {tuple(sorted(parts)): item for item, parts in item_builds.items()
        if item not in SKIP and not SKIP & set(parts)}


def _board(player):
    """(유닛 칸, 유닛) 목록. 소환물(모래 병사 등)은 뺀다."""
    return [(x_y_to_1d_coord(x, y), u) for x, row in enumerate(player.board) for y, u in enumerate(row)
            if u and u.name in BASE_CHAMPION_LIST]


def _room(u):
    """완성 아이템을 더 받을 수 있는지."""
    return len(u.items) < 3 and 'thieves_gloves' not in u.items


def _open(u):
    """새로 만들기 시작할 수 있는지: 자리가 있고 조각 하나를 들고 있지 않다."""
    return _room(u) and not (u.items and u.items[-1] in basic_items)


def _best(cands):
    """별이 가장 높은 유닛의 칸. 후보가 없으면 None."""
    return max(cands, key=lambda cu: cu[1].stars)[0] if cands else None


def _held_completed(player):
    everyone = [u for row in player.board for u in row if u] + [u for u in player.bench if u]
    held = [it for u in everyone for it in u.items] + [it for it in player.item_bench if it]
    return Counter(it for it in held if it in item_builds and it not in SKIP)


def _recipient(player, board, item, starting):
    """아이템을 줄 유닛 칸. 캐리 아이템이면 캐리 → 맡아 둘 유닛, 방어 아이템이면 앞줄, 그 밖은 별이 높은 유닛."""
    fits = _open if starting else _room
    units = [(c, u) for c, u in _board(player) if fits(u)]
    names = carriers(board) if board else []
    if any(item in board['items'][n] for n in names):
        carrier = [(c, u) for c, u in units if u.name in names and item in board['items'][u.name]]
        if carrier:
            return _best(carrier)
        return _best([(c, u) for c, u in units if u.name not in board['units']])
    if item in DEFENSIVE:
        front = [(c, u) for c, u in units if u.name in FRONT_LINE_UNITS]
        if front:
            return _best(front)
    return _best(units)


def item_action(player, board, mode, game_round, mask):
    ok = lambda idx, coord: coord is not None and bool(mask[37 + idx][coord])
    comps = [(i, it) for i, it in enumerate(player.item_bench) if it in basic_items and it not in SKIP]
    deck_items = {it for held in board['items'].values() for it in held} if board else set()

    for coord, u in _board(player):  # 0. 만들다 만 아이템 마저 만들기
        if u.items and u.items[-1] in basic_items and len(u.items) <= 3:
            partners = [(idx, PAIR[key]) for idx, c in comps
                        if (key := tuple(sorted((u.items[-1], c)))) in PAIR]
            partners.sort(key=lambda p: (p[1] not in deck_items, p[1] not in DEFENSIVE))
            for idx, _ in partners:
                if ok(idx, coord):
                    return f'6_{coord}_{idx}'

    for idx, it in enumerate(player.item_bench):  # 1. 아이템 칸의 완성 아이템 주기
        if it in item_builds and it not in SKIP:
            coord = _recipient(player, board, it, starting=False)
            if ok(idx, coord):
                return f'6_{coord}_{idx}'

    slots = {}
    for idx, c in comps:
        slots.setdefault(c, []).append(idx)

    def start(item, coord):
        """item의 두 조각이 아이템 칸에 있으면 coord의 유닛에게 첫 조각을 올리는 행동."""
        a, b = item_builds[item]
        if len(slots.get(a, [])) >= 1 + (a == b) and slots.get(b) and ok(slots[a][0], coord):
            return f'6_{coord}_{slots[a][0]}'
        return None

    def defensive():
        coord = _best([(c, u) for c, u in _board(player) if u.name in FRONT_LINE_UNITS and _open(u)])
        if coord is None:
            return None
        return next((act for item in DEFENSIVE if (act := start(item, coord))), None)

    if board:  # 2. 목표 덱 캐리 아이템 만들기
        have = _held_completed(player)
        wanted = [it for n in carriers(board) for it in board['items'][n] if it not in SKIP]
        need = Counter(wanted)
        for item in wanted:
            if have[item] < need[item] and (act := start(item, _recipient(player, board, item, starting=True))):
                return act

    if mode == 'win' and round_stage(game_round) in (2, 3) and (act := defensive()):  # 3. 방어 아이템
        return act

    if len(comps) > 4:  # 4. 조각 4개 초과
        if act := defensive():
            return act
        for item in PAIR.values():
            if act := start(item, _recipient(player, board, item, starting=True)):
                return act
    return None
