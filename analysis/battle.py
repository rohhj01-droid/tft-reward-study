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
from Simulator.utils import coord_to_x_y
from Simulator.observation.token.action import ActionToken


def build_player(base_pool, index, units):
    """유닛 리스트를 실제 Player 보드 위에 올린다. 배치는 빈 칸 중 무작위."""
    p = Player(base_pool, index)
    n = len(units)
    p.level = max(3, n)
    p.max_units = n
    for unit in units:
        p.add_to_bench(unit)
        token = ActionToken(p)
        _, bench_mask = token.create_move_and_sell_action_mask(p)
        valid = [c for c in range(28) if bench_mask[0][c]]
        if not valid:
            continue
        x, y = coord_to_x_y(random.choice(valid))
        p.move_bench_to_board(0, x, y)
    return p


def to_units(spec):
    """dict 리스트 -> champion 객체 리스트.

    주의: champion()의 두 번째 위치 인자는 stars가 아니라 team이다.
    반드시 stars= 로 넘겨야 한다.
    """
    return [champion(u['name'], stars=u['stars'], itemlist=list(u.get('items', [])))
            for u in spec]


def battle(units_a, units_b):
    """전투 1회. 반환값 1 = A승, 2 = B승, 0 = 무승부."""
    base_pool = pool()
    pa = build_player(base_pool, 0, units_a)
    pb = build_player(base_pool, 1, units_b)
    pa.opponent, pb.opponent = pb, pa
    config.WARLORD_WINS['blue'] = 0
    config.WARLORD_WINS['red'] = 0
    result, _ = champion_module.run(champion_module.champion, pa, pb, 0)
    return result


def win_rate(spec_a, spec_b, n=40):
    """A의 승률. 진영 유리를 없애기 위해 매 판 좌우를 바꿔 붙인다."""
    wins = draws = 0
    for i in range(n):
        if i % 2 == 0:
            result = battle(to_units(spec_a), to_units(spec_b))
            if result == 1:
                wins += 1
            elif result == 0:
                draws += 1
        else:
            result = battle(to_units(spec_b), to_units(spec_a))
            if result == 2:
                wins += 1
            elif result == 0:
                draws += 1
    return (wins + 0.5 * draws) / n
