"""
사람 봇의 초반 전략과 레벨·리롤(meta/human_bot_design.md 3·4절).

plan()이 이번 행동의 (목표 레벨, 남길 골드)를 정하고, action()이 행동 하나("1" 경험치, "2" 리롤, "0" 넘김)로 바꾼다.
칸 번호(game_round): 2-1 = 3, 2-5 = 6, 3-1 = 9, 3-2 = 10, 4-1 = 15, 4-5 = 18, 5-1 = 21.
"""
import math

from Simulator.stats import COST, round_stage
from meta.lobby import carriers

STAY = {1: 5, 2: 6, 3: 7}  # 느린 리롤 캐리 비용 -> 머무는 레벨
# 「돈 쓰는 때」 수업 규칙(spend_plan, 손잡이 spend로 켠다. 팔의 뜻은 hra/spend_lesson.py 머리말)
KEEP_AFTER = 30      # 레벨 8을 올린 뒤 남아야 하는 골드. 'era'·'deep'이 4-1에 남기는 골드이기도 하다
SPEND_FLOORS = ((60, 30), (40, 20))  # 레벨 8에서 캐리 2성 전까지 (체력 하한, 남길 골드)
DEEP_FLOORS = ((60, 20), (40, 10))
SPEND = {'roll': (False, False, SPEND_FLOORS), 'full': (True, False, SPEND_FLOORS),  # 이름 -> (레벨 8을 기다리나, 4-1에 조금만 굴리나, 레벨 8 남길 골드)
         'era': (True, True, SPEND_FLOORS), 'deep': (True, True, DEEP_FLOORS)}
FIRST_41, FIRST_SLOT, LAST_WAIT = 15, 18, 21  # 4-1, 4-5(여기부터 레벨 8 규칙을 바꾼다), 5-1(기다리지 않는다)
# 5단계 돈과 생존 규칙 후보(손잡이 late, 팔의 뜻은 hra/spend_lesson.py 머리말)
LATE_ARMS = ('stop', 'keep30', 'low30', 'combo')
LATE_KEEP = 30       # keep30·combo: 체력 20~39에서 남길 골드
# 레벨 9 관문 규칙 후보(손잡이 nine, 팔의 뜻은 hra/spend_lesson.py 머리말)
NINE_ARMS = ('carry1', 'stage6', 'fast', 'b_all')
NINE_KEEP, FAST_HP, FAST_LAST, STAGE_6 = 30, 70, 23, 27  # 레벨 9로 갈 때 남길 골드, fast를 시작하는 체력 하한·마지막 칸(5-3), 6-1
FAST_GOLD = 50  # fast를 시작할 때 쥔 골드 하한(보고서 B4 시험값 50·70골드의 낮은 값. 70골드는 대조 기록에서 거의 없다)


def early_mode(player, k):
    """2-3에 첫 대전 성적으로 연승형('win')·연패형('lose')을 고른다. 연승이 손잡이 값(2) 이상이면 연승형.
    처음에는 2-1의 초반 세기(2성 수 + 완성 아이템 수)로 골랐는데, 시뮬레이터의 2-1 보드는 거의 모두 0이라 바꿨다
    (유저 결정 2026-10-09). 전략은 목표일 뿐이고, 실제 연승·연패는 마음대로 안 되는 경우가 많다(유저)."""
    return 'win' if player.win_streak >= k['win_threshold'] else 'lose'


def stay_level(board):
    """느린 리롤 덱이 머무는 레벨(캐리 중 가장 싼 유닛의 비용으로). 보통 덱이나 목표 덱이 없으면 None."""
    return STAY[min(COST[c] for c in carriers(board))] if board and board['slow'] else None


def stable(player, board):
    """4코스트 이하 캐리가 모두 보드에 2성 이상으로 있는가. 캐리가 모두 5코스트면 보드에 있기만 하면 된다."""
    on = {}
    for row in player.board:
        for u in row:
            if u:
                on[u.name] = max(on.get(u.name, 0), u.stars)
    core = [c for c in carriers(board) if COST[c] <= 4]
    if not core:
        return all(c in on for c in carriers(board))
    return all(on.get(c, 0) >= 2 for c in core)


def carry3(player, board):
    """느린 리롤 덱의 가장 싼 캐리가 보드에 3성으로 있는가."""
    cheapest = min(carriers(board), key=lambda c: COST[c])
    return any(u and u.name == cheapest and u.stars >= 3 for row in player.board for u in row)


def plan(slot, level, hp, mode, rebuilt, stay, done3, steady, k, rebuild_now=False):
    """(목표 레벨, 남길 골드). 남길 골드가 None이면 리롤하지 않는다.
    stay: 느린 리롤 머무는 레벨(보통 덱 None), done3: 느린 리롤 캐리가 3성, steady: 안정,
    rebuild_now: 연패형이 이번 라운드에 보드를 세운다.
    보통 덱은 정해진 라운드에만 리롤한다: 4-1 라운드에 20까지, 4-5 라운드에 10까지(안정이 아닐 때), 연패형이 보드를
    세우는 라운드에 20까지. 그 밖의 라운드는 안정 여부와 상관없이 50을 지킨다(유저 결정 2026-10-09).
    손잡이 lose_5를 켜면 연패형도 2-5부터 목표 레벨이 5다(보드를 세우기 전에는 여전히 리롤하지 않는다)."""
    if slot < 3:
        return level, None
    if slot < 15:
        target = (6 if slot >= 9 else 5 if slot >= 6 else 4) if mode == 'win' else (
            6 if rebuilt else 5 if k.get('lose_5') and slot >= 6 else 4)
    else:
        target = 8 if slot >= 18 else 7
    banking = mode == 'lose' and not rebuilt and slot < 15
    if stay is not None and not done3:  # 느린 리롤: 머무는 레벨에서 50 넘는 몫으로 리롤
        if banking:
            return target, None
        target = stay if rebuilt or slot >= 15 else min(target, stay)
        floor = k['keep'] if level >= target else None
    else:
        if stay is not None:
            target = max(target, 8)  # 캐리가 3성이면 8로 빠르게
        if banking:
            floor = None
        elif steady:
            floor = k['keep']
        elif slot == 18 and level >= 8:
            floor = k['floor_45']
        elif (slot == 15 and level >= 7) or (mode == 'lose' and rebuild_now):
            floor = k['floor_41']
        else:
            floor = k['keep']
    if round_stage(slot) >= 4 and hp < k['hp_all_in']:
        floor = 0
    elif round_stage(slot) >= 4 and hp < k['hp_low']:
        floor = k['floor_45'] if floor is None else min(floor, k['floor_45'])
    return target, floor


def spend_plan(base, arm, slot, level, gold, need, hp, steady, slow, k):
    """교과서의 (목표 레벨, 남길 골드, 경험치 우선) base를 「돈 쓰는 때」 수업 규칙 arm(SPEND의 이름)으로 고친다.
    need는 다음 레벨까지 모자란 경험치다."""
    target, floor, exp_first = base
    wait, small41, floors = SPEND[arm]
    if slow or hp < k['hp_low'] or level >= 9:
        return base
    if slot < FIRST_SLOT:
        if small41 and slot >= FIRST_41 and floor is not None and floor < KEEP_AFTER:
            return target, KEEP_AFTER, exp_first
        return base
    if level < 8:
        if wait and level == 7 and slot < LAST_WAIT and gold - 4 * math.ceil(need / 4) < KEEP_AFTER:
            return level, None, False
        return base
    if steady:
        return base
    return target, next(f for h, f in floors if hp >= h), False


def strong(player, board, k):
    """보드가 센가: 4코스트 이하 캐리가 모두 2성이거나(stable), 보드의 2성 이상 유닛이 손잡이 값(6)명 이상이다."""
    twos = sum(1 for row in player.board for u in row if u and u.stars >= 2)
    return twos >= k['strong_twos'] or stable(player, board)


def late_hp(arm, slot, hp):
    """low30·combo: 5-1부터 체력 30~39를 40으로 친다(레벨·리롤 숫자를 정할 때만)."""
    return 40 if arm in ('low30', 'combo') and slot >= LAST_WAIT and 30 <= hp < 40 else hp


def late_plan(base, arm, slot, hp, is_strong, slow, k):
    """교과서의 (목표 레벨, 남길 골드, 경험치 우선) base를 5단계 돈과 생존 규칙 arm으로 고친다. 5-1부터 체력 20~39인 자리만 바꾼다.
    stop: 보드가 세면 50을 지킨다. keep30: 30을 남긴다. combo: 보드가 세면 50, 아니면 30이다(체력 30~39는 late_hp가 먼저 40으로 친다)."""
    target, floor, exp_first = base
    if arm is None or slow or slot < LAST_WAIT or not k['hp_all_in'] <= hp < k['hp_low']:
        return base
    if arm in ('stop', 'combo') and is_strong:
        return target, k['keep'], exp_first
    if arm in ('keep30', 'combo'):
        return target, LATE_KEEP, exp_first
    return base


def top_carry2(player, board):
    """가장 비싼 4코스트 이하 캐리가 보드에 2성 이상으로 있는가(값이 같은 캐리가 여럿이면 그중 하나). 그런 캐리가 없으면 stable과 같다."""
    core = [c for c in carriers(board) if COST[c] <= 4]
    if not core:
        return stable(player, board)
    top = max(COST[c] for c in core)
    return any(u and u.name in core and COST[u.name] == top and u.stars >= 2 for row in player.board for u in row)


def fast_start(arm, slot, level, gold, hp, streak, slow, k):
    """fast·b_all: 5-1~5-3에 레벨 8, 체력 70 이상, 2연승 이상, 50골드 이상이면 이 자리는 「빠른 9」를 시작한다.
    시작한 자리는 기억해 두고(HumanPolicy.fast9) 레벨 9가 될 때까지 nine_plan의 fast_on으로 넘긴다."""
    return (arm in ('fast', 'b_all') and not slow and level == 8 and LAST_WAIT <= slot <= FAST_LAST and hp >= FAST_HP
            and streak >= k['win_threshold'] and gold >= FAST_GOLD)


def nine_plan(base, arm, slot, level, gold, hp, fast_on, steady, top2, slow, k):
    """교과서의 (목표 레벨, 남길 골드, 경험치 우선) base를 레벨 9 관문 규칙 arm으로 고친다. 5-1부터 레벨 8, 체력 40 이상만 바꾼다.
    fast: 빠른 9를 시작한 자리(fast_on)는, stage6: 6-1부터는 안정과 상관없이 30을 남기고 경험치(레벨 8에서 리롤 안 함).
    carry1: 가장 비싼 캐리가 2성이면(top2) 안정으로 친다. b_all: 셋을 함께."""
    if arm is None or slow or level != 8 or slot < LAST_WAIT or hp < k['hp_low']:
        return base
    go9 = (9 if gold >= NINE_KEEP + 4 else base[0]), k['keep'], False
    if arm in ('fast', 'b_all') and fast_on:
        return go9
    if arm in ('stage6', 'b_all') and slot >= STAGE_6:
        return go9
    if arm in ('carry1', 'b_all') and top2 and not steady:
        return base[0], k['keep'], True
    return base


def action(gold, level, target, floor, exp_first):
    """목표 레벨까지 경험치 → 5단계 레벨 8에서 안정이면 50 넘는 몫을 경험치(9로) → 남길 골드까지 리롤."""
    if level < target and gold >= 4:
        return '1'
    if exp_first and level < 9 and gold >= 54:
        return '1'
    if floor is not None and gold >= floor + 2:
        return '2'
    return '0'
