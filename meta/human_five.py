"""
사람 봇의 덱 밖 5코스트 넣기(meta/human_bot_design.md 9절). 레벨 8부터 상점의 5코스트를 사고(덱 유닛 다음), 보드에
빈자리가 없으면 싼 덱 유닛(1~4코스트, 캐리·선택받은 자 아님, 큰 특성이 4명 아래로 안 떨어짐)과 바꾼다.
규칙은 롤체지지 10.24 1등 보드 25개와 대조했다(설계 9절 표). 목표 덱의 계열이 기준 인원에 모자라면 5코스트보다 계열
유닛을 먼저 사고 먼저 보드에 올린다(family_buy, family_in).
"""
from Simulator.origin_class_stats import tiers
from Simulator.stats import BASE_CHAMPION_LIST, COST
from meta.decks_1024 import CHAMPION_TRAITS, trait_counts
from meta.human_deck import copies, units_of
from meta.lobby import carriers
from meta.pit import chosen_of
from meta.play_stats import FAMILIES, family

FIVE_COSTS = sorted(name for name, cost in COST.items() if cost == 5)
# 계열 특성의 기준 인원(결투가·사교도·총사령관 6, 사냥꾼·엘더우드·포츈 3, 나머지 4). 평가와 실제 자료 분류에 쓰는 표 그대로다
FAMILY_MIN = {name: n for name, n, _ in FAMILIES}


def board_units(player):
    """보드의 (x, y, 유닛). 소환물(모래 병사 등)은 뺀다."""
    return [(x, y, u) for x, row in enumerate(player.board) for y, u in enumerate(row)
            if u and u.name in BASE_CHAMPION_LIST]


def trait_table(units):
    """유닛 목록의 특성 수. 시뮬레이터와 같은 방식이다(같은 유닛은 한 번, 상징 아이템은 든 개수만큼, 목록에 든 선택받은 자의
    특성 +1. 벤치의 선택받은 자는 안 센다, june fe92c2b)."""
    chosen = next((u.chosen for u in units if u.chosen), None)
    return trait_counts([u.name for u in units], {u.name: u.items for u in units}, chosen)


def deck_family(board):
    """목표 덱 표의 계열(FAMILIES에서 처음 맞는 것, 선택받은 자 특성 포함). 계열이 없는 덱이면 None."""
    name = family(trait_counts(board['units'], board['items'], chosen_of(board)[1]))[0]
    return None if name == 'other' else name


def family_short(player, board):
    """목표 덱의 계열 특성이 보드에서 기준 인원(FAMILY_MIN)에 모자라면 그 특성. 채웠거나 계열이 없는 덱이면 None."""
    trait = deck_family(board)
    counts = trait_table([u for _, _, u in board_units(player)])
    return trait if trait and counts.get(trait, 0) < FAMILY_MIN[trait] else None


def family_buy(player, shop, mask, units, trait):
    """계열이 모자랄 때 먼저 살 상점 칸: 아직 없는 계열 유닛(목표 덱 유닛 units 중 계열 특성 trait이 있는 것).
    선택받은 자 칸은 덱 규칙에 맡긴다. 없으면 None(2026-10-09 유저 결정)."""
    owned = {u.name for u in units_of(player)}
    for i, unit in enumerate(shop):
        if (mask[47 + i][0] and unit in units and unit not in owned and trait in CHAMPION_TRAITS[unit]
                and COST[unit] <= player.gold):
            return i
    return None


def family_in(player, board, units, trait):
    """계열이 모자랄 때 벤치의 계열 유닛을 올릴 자리: (벤치 칸, x, y). 올릴 유닛은 목표 덱 유닛 중 계열 특성이 있고 보드에
    없는 이름이다. 내릴 유닛은 캐리·선택받은 자가 아니고, 빼도 계열 특성이 줄지 않는 유닛(계열 아닌 유닛이나 같은 이름
    사본. 계열 상징 아이템을 든 유닛은 빠진다)이다. 덱 밖 유닛 먼저, 그다음 싼 것, 별이 낮은 것. 없으면 None
    (2026-10-09 유저 결정)."""
    on_board = board_units(player)
    names = {u.name for _, _, u in on_board}
    before = trait_table([u for _, _, u in on_board]).get(trait, 0)
    for i, b in enumerate(player.bench):
        if not b or b.name not in units or b.name in names or trait not in CHAMPION_TRAITS[b.name]:
            continue
        picks = [(u.name in units, COST[u.name], u.stars, x, y) for x, y, u in on_board
                 if u.name not in carriers(board) and not u.chosen
                 and trait_table([v for _, _, v in on_board if v is not u]).get(trait, 0) >= before]
        if picks:
            return (i,) + min(picks)[3:]
    return None


def active_traits(player):
    """보드에 켜진 특성(첫 단계 이상)."""
    counts = trait_table([u for _, _, u in board_units(player)])
    return {t for t, n in counts.items() if t in tiers and n >= tiers[t][0]}


def pick_five(player, shop, mask, k):
    """살 5코스트의 상점 칸 번호. 레벨이 five_level(8) 아래거나 골드가 5 미만이면 None. 켜진 특성에 보태는 수가 많은 쪽을
    고르고 같으면 앞 칸이다. 같은 이름은 1성으로 쳐서 five_cap(3)장까지만 산다. 선택받은 자 칸('_c')은 덱 규칙에 맡긴다."""
    if player.level < k['five_level'] or player.gold < 5:
        return None
    active = active_traits(player)
    held = copies(units_of(player))
    best = None
    for i, unit in enumerate(shop):
        if not mask[47 + i][0] or unit.endswith('_c') or unit not in FIVE_COSTS or held.get(unit, 0) >= k['five_cap']:
            continue
        score = sum(t in active for t in CHAMPION_TRAITS[unit])
        if best is None or score > best[0]:
            best = (score, i)
    return None if best is None else best[1]


def swap_out(player, board, five, k):
    """벤치의 5코스트 five를 올리려고 내릴 보드 유닛의 (x, y). 후보는 1~swap_cost_max(4)코스트이고 캐리·선택받은 자가 아니며,
    빼고 five를 넣어도 지키는 특성이 정한 인원 아래로 안 떨어지는 유닛. 지키는 특성은 big_trait(4)명 이상인 특성(4명 위로)과,
    이미 계열 기준 인원(FAMILY_MIN)을 넘은 계열 특성(그 인원 위로, 2026-10-09 유저 결정)이다. 지키는 특성에 안 드는 곁가지
    유닛 먼저, 그다음 지키는 특성 유닛. 같은 묶음에서는 싼 것, 그다음 별이 낮은 것. 목표 덱의 계열이 아직 기준 인원에
    못 미치면 아무것도 바꾸지 않는다(2026-10-09 유저 결정: 5코스트가 자리를 차지해 마지막 계열 유닛이 못 들어왔다). 없으면 None."""
    if family_short(player, board):
        return None
    units = board_units(player)
    before = trait_table([u for _, _, u in units])
    floor = {t: k['big_trait'] for t, n in before.items() if n >= k['big_trait']}
    for t, n in FAMILY_MIN.items():
        if before.get(t, 0) >= n:
            floor[t] = max(floor.get(t, 0), n)
    picks = []
    for x, y, u in units:
        if COST[u.name] > k['swap_cost_max'] or u.name in carriers(board) or u.chosen:
            continue
        after = trait_table([v for _, _, v in units if v is not u])
        for t in CHAMPION_TRAITS[five]:
            after[t] = after.get(t, 0) + 1
        if any(after.get(t, 0) < n for t, n in floor.items()):
            continue
        picks.append((any(t in floor for t in CHAMPION_TRAITS[u.name]), COST[u.name], u.stars, x, y))
    if not picks:
        return None
    return min(picks)[3:]
