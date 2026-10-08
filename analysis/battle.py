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
from Simulator.champion import champion
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


def build_player(base_pool, index, units, place='random'):
    p = Player(base_pool, index)
    n = len(units)
    # 레벨은 유닛 수를 담을 만큼만 올린다. 여기서는 경제를 재지 않으니 레벨 비용은 무시한다.
    p.level = max(3, n)
    p.max_units = n
    # 아지르는 보드에 놓일 때 옆 빈칸에 모래 병사 둘을 만든다. 마지막에 놓아야 정해 둔 칸을 병사가 먼저 차지하지 않는다.
    units = sorted(units, key=lambda u: u.name == 'azir')
    spots = range_positions(units) if place == 'range' else corner_positions(units) if place == 'corner' else None
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
