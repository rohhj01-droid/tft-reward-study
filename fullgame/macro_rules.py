"""
매크로 의사결정 규칙.

LLM에게 상태마다 행동 하나를 라벨링시키면 한쪽 행동으로 쏠렸다(labeling/README 참고).
같은 지식을 "조건 -> 행동" 형태로 옮기면 상태에 따라 행동이 갈린다.
decide_conditional 이 그 형태다.

decide_slowroll 은 풀게임 A/B에 실제로 투입한 단순화 버전이다.
경제 환경에서 학습기가 찾아낸 정책(레벨 목표까지만 올리고 그 뒤로는 리롤)을 옮긴 것.
"""

# 스테이지별 목표 레벨. 실제 TFT의 표준 레벨 타이밍(6렙 3-2, 7렙 4-1, 8렙 4-5)에서 가져왔다.
TARGET_LEVEL = {1: 3, 2: 5, 3: 6, 4: 7, 5: 8, 6: 8, 7: 9, 8: 9}

# 이 레벨까지만 올리고 그 뒤로는 리롤에 골드를 쓴다.
SLOWROLL_CAP = 8

ACTIONS = ('level', 'roll', 'save')


def decide_conditional(f):
    """
    다요인 조건부 규칙. f 는 상태 dict.
        health, gold, level, stage, win_streak, loss_streak, num_3star

    반환: (행동, 발동한 조건 이름)
    """
    hp, gold, level, stage = f['health'], f['gold'], f['level'], f['stage']
    target = TARGET_LEVEL.get(stage, 8)
    # 골드 50 이상이면 이자가 최대라, 초과분은 써도 이자가 깎이지 않는다.
    surplus = gold >= 50

    if hp <= 35 or f.get('loss_streak', 0) >= 3:
        # 체력이 빠지는 중이면 경제보다 지금 보드를 세우는 것이 우선이다.
        return ('roll', '체력/연패 안정화') if gold >= 10 else ('save', '응급이나 골드 부족')

    if f.get('num_3star', 0) >= 2:
        return 'save', '이미 충분히 강함'

    if level < target and surplus:
        return 'level', f'레벨 목표 {target} 미달'

    if level >= target and gold >= 54:
        return 'roll', '이자 위 초과분 리롤'

    if f.get('win_streak', 0) >= 3 and gold >= 54:
        return 'roll', '연승 유지'

    return 'save', '이자 회복'


def decide_slowroll(f):
    """풀게임 A/B에 넣은 단순 버전. (행동, 이유)"""
    hp, gold, level = f['health'], f['gold'], f['level']
    if hp <= 25:
        return 'roll', '체력 응급'
    if level < SLOWROLL_CAP and gold >= 52:
        return 'level', f'캡 {SLOWROLL_CAP}까지'
    if level >= SLOWROLL_CAP:
        return 'roll', '슬로우롤'
    return 'save', '이자 회복'


def to_action_token(decision, player, roll_floor=32):
    """
    규칙 결과를 시뮬레이터 액션 토큰으로 옮긴다.
        "0" 패스 / "1" 경험치 구매 / "2" 상점 새로고침
    골드가 부족하면 그냥 패스한다.
    """
    if decision == 'level' and player.level < 9 and player.gold >= 8:
        return '1'
    if decision == 'roll' and player.gold >= roll_floor:
        return '2'
    return '0'


if __name__ == '__main__':
    # 조건부 규칙이 상태에 따라 실제로 갈리는지 눈으로 확인
    samples = [
        dict(stage=3, level=6, gold=56, health=63, win_streak=0, loss_streak=0, num_3star=1),
        dict(stage=3, level=6, gold=48, health=86, win_streak=0, loss_streak=0, num_3star=0),
        dict(stage=4, level=7, gold=44, health=60, win_streak=0, loss_streak=3, num_3star=1),
        dict(stage=4, level=8, gold=33, health=54, win_streak=0, loss_streak=0, num_3star=2),
        dict(stage=2, level=4, gold=13, health=87, win_streak=3, loss_streak=0, num_3star=0),
    ]
    for f in samples:
        action, why = decide_conditional(f)
        print(f"stage{f['stage']} lv{f['level']} gold{f['gold']} hp{f['health']} "
              f"ls{f['loss_streak']} 3성{f['num_3star']}  ->  {action:5} ({why})")
