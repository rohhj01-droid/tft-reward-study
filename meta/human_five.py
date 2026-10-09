"""
사람 봇의 덱 밖 5코스트 넣기(meta/human_bot_design.md 9절). 레벨 8부터 상점의 5코스트를 사고(덱 유닛 다음), 보드에
빈자리가 없으면 싼 덱 유닛(1~4코스트, 캐리·선택받은 자 아님, 큰 특성이 4명 아래로 안 떨어짐)과 바꾼다.
규칙은 롤체지지 10.24 1등 보드 25개와 대조했다(설계 9절 표).
"""
from Simulator.origin_class_stats import tiers
from Simulator.stats import BASE_CHAMPION_LIST, COST
from meta.decks_1024 import CHAMPION_TRAITS, trait_counts
from meta.human_deck import copies, units_of
from meta.lobby import carriers

FIVE_COSTS = sorted(name for name, cost in COST.items() if cost == 5)


def board_units(player):
    """보드의 (x, y, 유닛). 소환물(모래 병사 등)은 뺀다."""
    return [(x, y, u) for x, row in enumerate(player.board) for y, u in enumerate(row)
            if u and u.name in BASE_CHAMPION_LIST]


def trait_table(units, chosen):
    """유닛 목록의 특성 수. 시뮬레이터와 같은 방식이다(같은 유닛은 한 번, 상징 아이템은 든 개수만큼, 선택받은 자 특성 +1)."""
    return trait_counts([u.name for u in units], {u.name: u.items for u in units}, chosen or None)


def active_traits(player):
    """보드에 켜진 특성(첫 단계 이상)."""
    counts = trait_table([u for _, _, u in board_units(player)], player.chosen)
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
    빼고 five를 넣어도 big_trait(4)명 이상이던 특성이 그 아래로 안 떨어지는 유닛. 큰 특성에 안 드는 곁가지 유닛 먼저,
    그다음 큰 특성 유닛. 같은 묶음에서는 싼 것, 그다음 별이 낮은 것. 없으면 None."""
    units = board_units(player)
    before = trait_table([u for _, _, u in units], player.chosen)
    big = {t for t, n in before.items() if n >= k['big_trait']}
    picks = []
    for x, y, u in units:
        if COST[u.name] > k['swap_cost_max'] or u.name in carriers(board) or u.chosen:
            continue
        after = trait_table([v for _, _, v in units if v is not u], player.chosen)
        for t in CHAMPION_TRAITS[five]:
            after[t] = after.get(t, 0) + 1
        if any(after.get(t, 0) < k['big_trait'] for t in big):
            continue
        picks.append((any(t in big for t in CHAMPION_TRAITS[u.name]), COST[u.name], u.stars, x, y))
    if not picks:
        return None
    return min(picks)[3:]
