"""
사람 봇의 초반 전략과 레벨·리롤(meta/human_bot_design.md 3·4절).

plan()이 이번 행동의 (목표 레벨, 남길 골드)를 정하고, action()이 행동 하나("1" 경험치, "2" 리롤, "0" 넘김)로 바꾼다.
칸 번호(game_round): 2-1 = 3, 2-5 = 6, 3-1 = 9, 3-2 = 10, 4-1 = 15, 4-5 = 18, 5-1 = 21.
"""
from Simulator.stats import COST, round_stage
from meta.lobby import carriers

STAY = {1: 5, 2: 6, 3: 7}  # 느린 리롤 캐리 비용 -> 머무는 레벨


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
    세우는 라운드에 20까지. 그 밖의 라운드는 안정 여부와 상관없이 50을 지킨다(유저 결정 2026-10-09)."""
    if slot < 3:
        return level, None
    if slot < 15:
        target = (6 if slot >= 9 else 5 if slot >= 6 else 4) if mode == 'win' else (6 if rebuilt else 4)
    else:
        target = 8 if slot >= 18 else 7
    banking = mode == 'lose' and not rebuilt and slot < 15
    if stay is not None and not done3:  # 느린 리롤: 머무는 레벨에서 50 넘는 몫으로 리롤
        if banking:
            return 4, None
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


def action(gold, level, target, floor, exp_first):
    """목표 레벨까지 경험치 → 5단계 레벨 8에서 안정이면 50 넘는 몫을 경험치(9로) → 남길 골드까지 리롤."""
    if level < target and gold >= 4:
        return '1'
    if exp_first and level < 9 and gold >= 54:
        return '1'
    if floor is not None and gold >= floor + 2:
        return '2'
    return '0'
