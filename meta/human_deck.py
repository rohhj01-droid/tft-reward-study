"""
사람 봇의 덱 고르기(meta/human_bot_design.md 2절).

후보는 tftactics 10.24 보드 27개(meta.lobby.BOARDS). 점수 = 유닛 점수(비용 × 사본 수) + 선택받은 자 덤
+ 아이템 점수 + 티어 점수 - 겹침 감점. 처음엔 점수가 높을수록 잘 뽑히는 제비뽑기로 고르고, 그 뒤로는 문턱을 넘어야
갈아탄다.
"""
import math
from collections import Counter

from Simulator.item_stats import basic_items, item_builds
from Simulator.stats import COST
from meta.lobby import BOARDS, carriers
from meta.pit import chosen_of

TIER_POINTS = {'S': 3, 'A': 2, 'B': 1}


def copies(units):
    """유닛 목록 -> {이름: 1성으로 친 장수}(1성 1, 2성 3, 3성 9)."""
    count = Counter()
    for u in units:
        count[u.name] += 3 ** (u.stars - 1)
    return count


def units_of(player):
    return [u for row in player.board for u in row if u] + [u for u in player.bench if u]


def scout(others):
    """살아 있는 다른 플레이어들이 들고 있는 유닛 장수."""
    return copies(u for o in others if o.health > 0 for u in units_of(o))


def buildable(board, completed, components):
    """들고 있는 완성 아이템과 조각으로 이 덱의 추천 아이템을 몇 개 만들 수 있는지(앞에서부터 센다)."""
    done, parts = Counter(completed), Counter(components)
    n = 0
    for held in board['items'].values():
        for item in held:
            if done[item]:
                done[item] -= 1
                n += 1
            elif item in item_builds and not Counter(item_builds[item]) - parts:
                parts -= Counter(item_builds[item])
                n += 1
    return n


def key_units(board):
    """핵심 유닛: 캐리와 4·5코스트."""
    return set(carriers(board)) | {u for u in board['units'] if COST[u] >= 4}


def score(board, mine, chosen_trait, completed, components, others, k):
    s = sum(COST[u] * min(mine.get(u, 0), 9) for u in set(board['units']))
    if chosen_trait and chosen_trait == chosen_of(board)[1]:
        s += k['chosen_bonus']
    s += k['item_point'] * buildable(board, completed, components)
    s += k['tier_weight'] * TIER_POINTS[board['tier']]
    s -= k['contest'] * sum(others.get(u, 0) for u in key_units(board))
    return s


def choose(scores, current, stage, rng, k):
    """current가 None이면 제비뽑기(확률은 exp((점수 - 최고점) / 온도)에 비례). 아니면 최고점이 지금 덱보다
    문턱(단계별 비율 × 지금 점수, 지금 점수가 1보다 작으면 1로) 넘게 높을 때만 갈아탄다."""
    if current is None:
        top = max(scores)
        weights = [math.exp((s - top) / k['temperature']) for s in scores]
        return rng.choices(range(len(scores)), weights=weights)[0]
    best = max(range(len(scores)), key=lambda i: scores[i])
    margin = k['switch'][min(max(stage, 2), 4)]
    return best if scores[best] - scores[current] > margin * max(scores[current], 1) else current


SPREAD = Counter()  # 1단계 사기 기준: 유닛마다 그 유닛이 든 후보 덱들의 티어 점수 합(가운데 값 6)
for _board in BOARDS:
    for _unit in set(_board['units']):
        SPREAD[_unit] += TIER_POINTS[_board['tier']]


def held_items(player):
    """(완성 아이템 목록, 조각 목록). 보드·벤치 유닛과 아이템 칸 전부. 주걱은 뺀다."""
    held = [it for u in units_of(player) for it in u.items] + [it for it in player.item_bench if it]
    return ([it for it in held if it in item_builds],
            [it for it in held if it in basic_items and it != 'spatula'])
