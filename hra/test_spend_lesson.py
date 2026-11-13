"""
「돈 쓰는 때」 수업 규칙 대조 검사(hra/spend_lesson.py). 끝의 세 검사는 판을 실제로 돌려서 느리다(판 하나에 20초쯤).

실행: python -m hra.test_spend_lesson
"""
import json
import os
import tempfile

from hra.spend_lesson import adjusted, cap_effect, gap_stats, lesson, lesson_game, lesson_plan, line, parse, run, summary
from hra.plan_bot import safe_play
from meta.lobby import N_PLAYERS

BASE7 = (7, 50, False)   # 교과서: 4-2쯤 레벨 7에서 50을 지킨다
BASE8 = (8, 50, False)   # 교과서: 4-5부터 목표 레벨 8
BASE8_XP = (8, 50, True)  # 교과서: 5단계 레벨 8이면 50 넘는 몫으로 9로 간다


def plan(base, arm='full', slot=18, level=7, gold=60, need=50, hp=70, steady=False, slow=False):
    return lesson_plan(base, arm, slot, level, gold, need, hp, steady, slow)


def rounds_before_4_5_follow_the_textbook_test():
    assert plan(BASE7, slot=17, level=7) == BASE7
    assert plan((7, 20, False), slot=15, level=7) == (7, 20, False)


def slow_decks_and_low_health_follow_the_textbook_test():
    assert plan(BASE8, slow=True) == BASE8
    assert plan((8, 10, False), hp=39) == (8, 10, False)
    assert plan((8, 0, False), hp=15, level=8) == (8, 0, False)


def full_arm_waits_for_level_8_until_30_gold_would_remain_test():
    # 60골드에서 경험치 50이 모자라면 52골드가 들어 8이 남는다: 아직 올리지 않고 리롤도 하지 않는다
    assert plan(BASE8, gold=60, need=50) == (7, None, False)
    # 84골드면 32가 남는다: 올린다
    assert plan(BASE8, gold=84, need=50) == BASE8
    # 올리는 도중에도 남는 돈은 그대로라 판단이 뒤집히지 않는다(경험치 4를 사면 골드 4가 준다)
    assert plan(BASE8, gold=80, need=46) == BASE8


def full_arm_levels_at_5_1_whatever_the_gold_test():
    assert plan(BASE8, slot=21, gold=50, need=44) == BASE8


def roll_arm_levels_when_the_textbook_does_test():
    assert plan(BASE8, arm='roll', gold=60, need=50) == BASE8


def level_6_first_goes_to_7_like_the_textbook_test():
    assert plan(BASE8, level=6, gold=60, need=20) == BASE8


def unstable_level_8_board_rolls_to_a_floor_set_by_health_test():
    assert plan(BASE8, level=8, hp=70) == (8, 30, False)
    assert plan(BASE8, level=8, hp=60) == (8, 30, False)
    assert plan(BASE8, level=8, hp=45, arm='roll') == (8, 20, False)
    # 5단계 레벨 8의 「50 넘는 몫은 경험치」도 캐리가 2성이 될 때까지 미룬다
    assert plan(BASE8_XP, slot=22, level=8, hp=70) == (8, 30, False)


def stable_level_8_board_follows_the_textbook_test():
    assert plan(BASE8_XP, slot=22, level=8, steady=True) == BASE8_XP
    assert plan((9, 50, False), slot=27, level=9) == (9, 50, False)


BASE41 = (7, 20, False)  # 교과서: 4-1에 레벨 7이면 20골드까지 리롤


def era_arm_rolls_only_down_to_30_at_4_1_test():
    assert plan(BASE41, arm='era', slot=15, level=7, hp=70) == (7, 30, False)
    assert plan(BASE41, arm='deep', slot=15, level=7, hp=45) == (7, 30, False)
    # 체력 40 미만, 느린 리롤 덱, 이미 50을 지키는 계획은 그대로다
    assert plan(BASE41, arm='era', slot=15, level=7, hp=39) == BASE41
    assert plan(BASE41, arm='era', slot=15, level=7, slow=True) == BASE41
    assert plan(BASE7, arm='era', slot=16, level=7) == BASE7
    # 다른 팔은 4-1을 건드리지 않는다
    assert plan(BASE41, arm='full', slot=15, level=7) == BASE41
    assert plan(BASE41, arm='roll', slot=15, level=7) == BASE41


def era_arm_keeps_the_full_lesson_from_4_5_test():
    assert plan(BASE8, arm='era', gold=60, need=50) == (7, None, False)
    assert plan(BASE8, arm='era', level=8, hp=70) == (8, 30, False)
    assert plan(BASE8, arm='era', level=8, hp=45) == (8, 20, False)


def deep_arm_rolls_further_down_at_level_8_test():
    assert plan(BASE8, arm='deep', gold=60, need=50) == (7, None, False)
    assert plan(BASE8, arm='deep', level=8, hp=70) == (8, 20, False)
    assert plan(BASE8, arm='deep', level=8, hp=45) == (8, 10, False)
    assert plan(BASE8_XP, arm='deep', slot=22, level=8, steady=True) == BASE8_XP


def summary_can_group_by_the_deck_held_at_4_1_test():
    # 4-1에 든 덱(deck15)으로 묶으면 4-1부터 규칙을 바꾸는 팔도 바꾸기 전 덱으로 나뉜다
    a = dict(_seat(True, 1, 'Chosen Warlords'), deck15='Chosen Dusks')
    b = dict(_seat(False, 5), deck15='Chosen Dusks')
    assert summary([[a, b]])['groups']['late']['lesson']['seats'] == 0
    assert summary([[a, b]], key='deck15')['groups']['late']['lesson']['seats'] == 1


def _seat(lesson_seat, place, deck18='Chosen Dusks', deck=None, carry2=False, four2=0, rolls8=0, curve=()):
    return {'lesson': lesson_seat, 'deck': deck or deck18, 'deck18': deck18, 'place': place, 'carry2': carry2,
            'four2': four2, 'rolls8': rolls8, 'curve': [list(c) for c in curve]}


def summary_pairs_games_and_groups_by_deck_at_4_5_test():
    # 판 둘. 수업 자리 평균 등수가 교과서보다 판마다 2, 1 좋다
    g1 = [_seat(True, 1, carry2=True, four2=2), _seat(True, 3, 'Chosen Warlords'),
          _seat(False, 4), _seat(False, 4, 'Chosen Warlords')]
    g2 = [_seat(True, 2, carry2=True, four2=1), _seat(True, 5, 'Ninja Shades'),
          _seat(False, 6, deck='Chosen Warlords'), _seat(False, 3, 'Ninja Shades')]
    s = summary([g1, g2])
    assert s['diff'] == 1.5 and s['games'] == 2
    late = s['groups']['late']
    # 4-5에 든 덱으로 묶는다: 판 2의 교과서 자리는 끝 덱이 총사령관이어도 4-5에는 황혼이었다
    assert late['lesson']['seats'] == 2 and late['rule']['seats'] == 2
    assert late['lesson']['mean_place'] == 1.5 and late['rule']['mean_place'] == 5.0
    assert late['place_diff'] == 3.5                      # 교과서 − 수업, 양수면 수업 쪽이 낫다
    assert late['lesson']['carry2'] == 1.0 and late['rule']['carry2'] == 0.0 and late['carry2_diff'] == 1.0
    assert s['groups']['normal']['lesson']['seats'] == 1 and s['groups']['slow']['rule']['seats'] == 1
    assert s['groups']['all']['lesson']['seats'] == 4


def summary_reads_level_8_arrival_from_the_curve_test():
    # 곡선 = [칸, 레벨, 골드, 체력]. 처음 레벨 8로 시작한 칸과 그때 골드
    g = [_seat(True, 1, curve=[(18, 7, 60, 80), (21, 7, 90, 70), (22, 8, 45, 70)]),
         _seat(False, 2, curve=[(18, 7, 60, 80), (19, 8, 12, 80)])]
    late = summary([g])['groups']['late']
    assert late['lesson']['lv8_slot'] == 22 and late['lesson']['lv8_gold'] == 45
    assert late['rule']['lv8_slot'] == 19 and late['rule']['lv8_gold'] == 12


def last_line_prints_without_a_standard_error_for_a_single_game_test():
    assert line({'arm': 'roll', 'games': 1, 'errors': [], 'diff': 0.5, 'se': None}) == 'roll 판 1 오류 0 차 +0.500'
    assert line({'arm': 'full', 'games': 400, 'errors': [[1, 'x']], 'diff': -0.25, 'se': 0.0871}) == 'full 판 400 오류 1 차 -0.250 ± 0.087'


def arm_none_on_the_command_line_means_textbook_on_both_sides_test():
    assert parse(['--arm', 'none', '--out', 'x.json']).arm is None
    assert parse(['--arm', 'full', '--out', 'x.json']).arm == 'full'
    assert parse(['--arm', 'deep', '--group', 'deck15', '--out', 'x.json']).group == 'deck15'
    assert parse(['--arm', 'era', '--out', 'x.json']).group == 'deck18'


def gap_stats_compares_value_decks_with_ordinary_decks_over_all_seats_test():
    # 8자리 모두 교과서인 실행. 수업 자리 표시는 보지 않는다
    g1 = [_seat(True, 6, carry2=True), _seat(False, 8), _seat(True, 2, 'Chosen Warlords'), _seat(False, 4, 'Chosen Warlords'),
          _seat(False, 1, 'Ninja Shades')]
    g2 = [_seat(False, 5), _seat(True, 3, 'Chosen Warlords'), _seat(True, 7, 'Ninja Shades')]
    s = gap_stats([g1, g2])
    assert s['late']['seats'] == 3 and s['normal']['seats'] == 3
    assert abs(s['late']['mean_place'] - 19 / 3) < 1e-9 and s['normal']['mean_place'] == 3.0
    assert abs(s['gap'] - (19 / 3 - 3.0)) < 1e-9          # 밸류덱 − 보통 덱, 클수록 밸류덱이 밀린다
    assert abs(s['late']['carry2'] - 1 / 3) < 1e-9


def cap_effect_is_the_change_between_two_runs_with_combined_error_test():
    low = {'gap': 0.8, 'gap_se': 0.03, 'late': {'carry2': 0.20, 'carry2_se': 0.04}}
    high = {'gap': 0.5, 'gap_se': 0.04, 'late': {'carry2': 0.32, 'carry2_se': 0.03}}
    e = cap_effect(low, high)
    assert abs(e['gap_drop'] - 0.3) < 1e-9 and abs(e['gap_drop_se'] - 0.05) < 1e-9   # 양수면 상한을 올렸을 때 밸류덱이 덜 밀린다
    assert abs(e['carry2_rise'] - 0.12) < 1e-9 and abs(e['carry2_rise_se'] - 0.05) < 1e-9


def adjusted_subtracts_the_control_run_game_by_game_on_shared_seeds_test():
    arm = {'seed0': 100, 'seeds': [100, 101, 102, 103], 'per_game': [1.0, 0.5, -0.5, 2.0]}
    none = {'seed0': 100, 'seeds': [100, 102, 103], 'per_game': [0.5, -1.0, 1.0]}     # 대조 실행은 101번 판을 버렸다
    a = adjusted(arm, none)
    assert a['games'] == 3 and abs(a['diff'] - (0.5 + 0.5 + 1.0) / 3) < 1e-9
    assert abs(a['se'] - (((0.5 - 2 / 3) ** 2 * 2 + (1.0 - 2 / 3) ** 2) / 2) ** 0.5 / 3 ** 0.5) < 1e-9
    # 옛 결과 파일에는 seeds가 없다. 버린 판이 없으면 seed0부터 차례다
    old = {'seed0': 100, 'games_asked': 3, 'per_game': [0.5, 0.0, -1.0]}
    assert adjusted(old, none)['games'] == 2


def tracked_rule_seats_play_the_same_game_as_plain_rule_seats_test():
    plain, _ = safe_play(990001, ['rule'] * N_PLAYERS)
    tracked, _ = safe_play(990001, [lesson(None)] * N_PLAYERS)
    assert [s['place'] for s in plain['seats']] == [s['place'] for s in tracked['seats']]
    assert [s['deck'] for s in plain['seats']] == [s['deck'] for s in tracked['seats']]


def lesson_game_gives_eight_rows_with_four_lesson_seats_test():
    seed, rows, err = lesson_game((990002, 'full'))
    assert err is None and seed == 990002 and len(rows) == N_PLAYERS
    assert sum(r['lesson'] for r in rows) == N_PLAYERS // 2
    assert sorted(r['place'] for r in rows) == list(range(1, N_PLAYERS + 1))
    assert all(r['curve'] and r['curve'][0][0] <= 3 for r in rows)
    json.dumps(rows)


def run_resumes_from_partial_file_test():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'p.jsonl')
        first = run('roll', 1, jobs=1, seed0=990003, partial=path)
        assert first['games'] == 1 and len(open(path, encoding='utf-8').read().splitlines()) == 1
        again = run('roll', 1, jobs=1, seed0=990003, partial=path)   # 다시 부르면 판을 돌리지 않고 기록을 읽는다
        assert again['rows'] == first['rows'] and len(open(path, encoding='utf-8').read().splitlines()) == 1


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
