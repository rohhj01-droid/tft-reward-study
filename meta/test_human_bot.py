"""
사람 봇(meta/human_bot.py) 검사.

실행: python -m meta.test_human_bot
"""
import random
from types import SimpleNamespace as Unit

from Simulator.item_stats import item_builds
from meta.test_lobby import OPEN, SHARPSHOOTERS, deck_player

FULL = [[1] * 37 for _ in range(60)]  # 상점·아이템을 모두 허락하는 마스크(mask[47 + i][0], mask[37 + 칸][유닛 칸])


def attach_human_takes_over_from_round_one_test():
    """사람 봇은 1라운드부터 정책을 맡는다(덱 봇은 11라운드까지 기본 봇이었다)."""
    from meta.human_bot import attach_human
    p = deck_player(['jhin'])
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(1, ['garen', 'vayne', 'garen', 'garen', 'garen'], OPEN) == '3_1'
    assert policy.choose_decks is False and policy.switches == 0


def human_bot_puts_ranged_carry_in_back_corner_test():
    """자리 맞추기는 구석 배치다(analysis.battle.corner_positions): 원거리는 뒷줄 구석부터 아이템 많은 순, 근접은 앞줄
    가운데부터. 자리가 맞으면 아무것도 하지 않는다."""
    from Simulator.utils import x_y_to_1d_coord
    from meta.human_bot import attach_human
    p = deck_player(['garen', 'jinx'])  # 가렌 (0, 0), 징크스 (1, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) == f'5_{x_y_to_1d_coord(0, 0)}_{x_y_to_1d_coord(3, 3)}'  # 근접은 앞줄 가운데로
    p = deck_player(['jinx'])  # 원거리 하나가 이미 뒷줄 구석 (0, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) is None


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
