"""
「돈 쓰는 때」 수업 규칙 대조 검사(hra/spend_lesson.py). 끝의 네 검사는 판을 실제로 돌려서 느리다(판 하나에 20초쯤).

실행: python -m hra.test_spend_lesson
"""
import json
import os
import random
import tempfile

from hra.spend_lesson import adjusted, cap_effect, gap_stats, lesson, lesson_game, lesson_plan, line, parse, run, summary
from hra.plan_bot import safe_play
from meta.human_bot import KNOBS
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


def arms_are_knobs_on_top_of_the_textbook_test():
    # 수업 자리는 교과서의 손잡이만 바꾼다. 팔 lv5는 「연패형도 2-5에 레벨 5」(lose_5)이고, 나머지 팔은 「돈 쓰는 때」 규칙(spend)이다
    seat = lambda arm: lesson(arm)(None, None, [], random.Random(0)).knobs
    assert (seat('lv5')['lose_5'], seat('lv5')['spend']) == (True, KNOBS['spend'])
    assert (seat('era')['spend'], seat('era')['lose_5']) == ('era', KNOBS['lose_5'])
    assert (seat(None)['spend'], seat(None)['lose_5']) == (KNOBS['spend'], KNOBS['lose_5'])
    assert parse(['--arm', 'lv5', '--out', 'x.json']).arm == 'lv5'


def tracked_rule_seats_play_the_same_game_as_plain_rule_seats_test():
    plain, _ = safe_play(990001, ['rule'] * N_PLAYERS)
    tracked, _ = safe_play(990001, [lesson(None)] * N_PLAYERS)
    assert [s['place'] for s in plain['seats']] == [s['place'] for s in tracked['seats']]
    assert [s['deck'] for s in plain['seats']] == [s['deck'] for s in tracked['seats']]


def rule_seats_under_the_fixed_textbook_play_like_era_lesson_seats_test():
    # 교과서의 손잡이를 켠 규칙 자리 8명(고친 교과서)과, 옛 교과서 위에 팔 era를 얹은 수업 자리 8명은 같은 판을 둔다
    lessons, _ = safe_play(990005, [lesson('era')] * N_PLAYERS)
    old = KNOBS['spend']
    KNOBS['spend'] = 'era'
    try:
        fixed, _ = safe_play(990005, ['rule'] * N_PLAYERS)
    finally:
        KNOBS['spend'] = old
    assert [s['place'] for s in fixed['seats']] == [s['place'] for s in lessons['seats']]
    assert [s['deck'] for s in fixed['seats']] == [s['deck'] for s in lessons['seats']]
    assert [s['board'] for s in fixed['seats']] == [s['board'] for s in lessons['seats']]
    plain, _ = safe_play(990005, ['rule'] * N_PLAYERS)
    assert [s['board'] for s in plain['seats']] != [s['board'] for s in fixed['seats']]   # 옛 교과서와는 다른 판이다


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
        assert first['textbook'] == {'spend': KNOBS['spend'], 'lose_5': KNOBS['lose_5']}   # 양쪽 자리의 바탕 교과서를 적는다
        again = run('roll', 1, jobs=1, seed0=990003, partial=path)   # 다시 부르면 판을 돌리지 않고 기록을 읽는다
        assert again['rows'] == first['rows'] and len(open(path, encoding='utf-8').read().splitlines()) == 1


def late_low30_counts_health_in_the_30s_as_40_from_stage_5_test():
    """5단계 돈과 생존 규칙 후보 low30·combo: 5-1(칸 21)부터 체력 30~39를 40으로 친다. 다른 때와 다른 팔은 그대로다."""
    from meta.human_macro import late_hp
    assert [late_hp('low30', 21, h) for h in (29, 30, 39, 40)] == [29, 40, 40, 40]
    assert late_hp('combo', 21, 35) == 40 and late_hp('low30', 20, 35) == 35   # 4단계는 그대로
    assert late_hp('stop', 21, 35) == 35 and late_hp('keep30', 21, 35) == 35 and late_hp(None, 21, 35) == 35


def late_plan_changes_only_stage_5_low_health_rounds_test():
    """체력 20~39, 5단계부터, 느린 리롤 덱이 아닐 때만 남길 골드를 바꾼다. stop: 보드가 세면 50을 지킨다. keep30: 30을 남긴다.
    combo: 보드가 세면 50, 아니면 30이다. 경험치 우선과 목표 레벨은 건드리지 않는다."""
    from meta.human_macro import late_plan
    base = (8, 10, True)
    call = lambda arm, hp=30, is_strong=False, slot=22, slow=False: late_plan(base, arm, slot, hp, is_strong, slow, KNOBS)
    assert call(None) == base and call('low30') == base
    assert call('stop') == base and call('stop', is_strong=True) == (8, 50, True)
    assert call('keep30') == (8, 30, True) and call('keep30', is_strong=True) == (8, 30, True)
    assert call('combo') == (8, 30, True) and call('combo', is_strong=True) == (8, 50, True)
    for arm in ('stop', 'keep30', 'combo'):
        assert call(arm, hp=19, is_strong=True) == base and call(arm, hp=40, is_strong=True) == base   # 다 쓰는 구간과 체력 40 이상은 그대로
        assert call(arm, slot=20, is_strong=True) == base and call(arm, slow=True, is_strong=True) == base   # 4단계와 느린 리롤 덱은 그대로


def strong_board_has_all_carries_two_star_or_six_two_star_units_test():
    """보드가 센가: 캐리가 모두 2성이거나, 보드의 2성 이상 유닛이 여섯 이상이다."""
    from types import SimpleNamespace as Unit
    from meta.human_macro import strong
    from meta.lobby import BOARDS, carriers
    deck = next(b for b in BOARDS if all(c in b['units'] for c in carriers(b)) and len(carriers(b)) >= 1 and not b['slow'])
    other = next(n for n in ('garen', 'vayne', 'elise') if n not in carriers(deck))
    field = lambda units: Unit(board=[units + [None] * (7 - len(units))])
    two = lambda n, name=other: [Unit(name=name, stars=2, items=[]) for _ in range(n)]
    assert not strong(field(two(5)), deck, KNOBS)
    assert strong(field(two(6)), deck, KNOBS)
    assert strong(field([Unit(name=c, stars=2, items=[]) for c in carriers(deck)]), deck, KNOBS)


def late_arms_are_a_knob_on_top_of_the_textbook_test():
    seat = lambda arm: lesson(arm)(None, None, [], random.Random(0)).knobs
    assert seat('stop')['late'] == 'stop' and seat('stop')['spend'] == KNOBS['spend']
    assert seat(None)['late'] is None and seat('era')['late'] is None
    assert parse(['--arm', 'combo', '--out', 'x.json']).arm == 'combo'
    assert parse(['--arm', 'none', '--everyone', '--out', 'x.json']).everyone
    assert not parse(['--arm', 'stop', '--out', 'x.json']).everyone


def nine_plan_changes_only_level_8_rounds_from_stage_5_with_health_40_test():
    """레벨 9 관문 규칙 후보(묶음 B). 5-1(칸 21)부터, 레벨 8, 체력 40 이상, 느린 리롤 덱이 아닐 때만 바꾼다.
    carry1: 가장 비싼 4코스트 이하 캐리가 2성이면 안정으로 친다(50을 지키고 넘는 몫을 경험치로).
    stage6: 6-1(칸 27)부터 안정과 상관없이 30을 남기고 경험치를 산다(레벨 8에서 리롤하지 않는다).
    fast: 빠른 9를 시작한 자리(fast_on, fast_start가 정한다)는 라운드와 연승에 상관없이 레벨 9가 될 때까지 30을 남기고 경험치를 산다.
    b_all: fast, stage6, carry1을 이 차례로 본다."""
    from meta.human_macro import NINE_ARMS, nine_plan
    base = (8, 20, False)

    def call(arm, slot=22, gold=60, hp=50, fast_on=False, steady=False, top2=False, level=8, slow=False):
        return nine_plan(base, arm, slot, level, gold, hp, fast_on, steady, top2, slow, KNOBS)

    assert call(None) == base and call(None, fast_on=True, top2=True, slot=27) == base
    assert call('carry1') == base and call('carry1', top2=True) == (8, 50, True)
    assert call('carry1', slot=21, top2=True) == (8, 50, True) and call('carry1', slot=20, top2=True) == base   # 5-1부터
    assert call('carry1', top2=True, steady=True) == base   # 이미 안정이면 교과서 그대로
    assert call('stage6', slot=26) == base and call('stage6', slot=27) == (9, 50, False)
    assert call('stage6', slot=27, gold=33) == (8, 50, False)   # 30 아래로는 사지 않고, 레벨 8에서 리롤도 하지 않는다
    assert call('stage6', slot=27, gold=34) == (9, 50, False) and call('stage6', slot=27, steady=True) == (9, 50, False)
    assert call('fast') == base and call('fast', fast_on=True) == (9, 50, False)
    for slot in (21, 24, 27, 30):   # 한 번 시작하면 5-5 뒤에도, 6단계에도 이어 간다
        assert call('fast', slot=slot, fast_on=True) == (9, 50, False) and call('fast', slot=slot, fast_on=True, gold=33) == (8, 50, False)
    assert call('fast', fast_on=True, hp=40) == (9, 50, False) and call('fast', fast_on=True, hp=39) == base   # 체력 40 아래로 내려가면 교과서
    assert call('fast', slot=27, top2=True) == base   # fast는 stage6·carry1을 겸하지 않는다
    assert call('b_all', fast_on=True) == (9, 50, False) and call('b_all', top2=True) == (8, 50, True)
    assert call('b_all', slot=27, top2=True) == (9, 50, False) and call('b_all') == base
    for arm in NINE_ARMS:
        assert call(arm, slot=27, hp=39, top2=True, fast_on=True) == base   # 체력 40 아래는 그대로
        assert call(arm, slot=20, hp=70, top2=True, fast_on=True) == base   # 4단계는 그대로
        for kw in ({'level': 7}, {'level': 9}, {'slow': True}):
            assert call(arm, slot=27, hp=70, top2=True, fast_on=True, **kw) == base   # 레벨 8이 아니거나 느린 리롤 덱은 그대로
    assert call('carry1', top2=True, hp=40) == (8, 50, True) and call('stage6', slot=27, hp=40) == (9, 50, False)   # 체력 40은 걸린다


def fast_start_needs_5_1_to_5_3_level_8_health_70_two_wins_and_50_gold_test():
    """fast·b_all의 빠른 9 시작: 5-1~5-3(칸 21~23)에 레벨 8, 체력 70 이상, 2연승 이상, 50골드 이상, 느린 리롤 덱이 아닐 때."""
    from meta.human_macro import fast_start

    def start(arm='fast', slot=22, level=8, gold=50, hp=70, streak=2, slow=False):
        return fast_start(arm, slot, level, gold, hp, streak, slow, KNOBS)

    assert start() and start('b_all') and start(slot=21) and start(slot=23)
    assert not start(slot=20) and not start(slot=24)
    assert not start(hp=69) and not start(streak=1) and not start(gold=49)
    assert not start(level=7) and not start(level=9) and not start(slow=True)
    assert not start('carry1') and not start('stage6') and not start(None) and not start('low30')


def top_carry_two_star_needs_one_of_the_most_expensive_carries_test():
    """가장 비싼 4코스트 이하 캐리가 보드에 2성 이상이면 참이다(값이 같은 캐리가 여럿이면 그중 하나). 그런 캐리가 없으면 stable과 같다.
    캐리 하나가 5코스트인 덱(신성: 워윅 4·요네 5)은 4코스트 캐리 하나만 보므로 stable과 같다(carry1이 바꾸지 않는다)."""
    from types import SimpleNamespace as Unit
    from meta.human_macro import stable, top_carry2
    from meta.lobby import BOARDS
    by = {b['name']: b for b in BOARDS}
    field = lambda *units: Unit(board=[[Unit(name=n, stars=s, items=[])] for n, s in units] + [[None]] * (7 - len(units)))
    hunters, sharp, divines = by['Chosen Hunters'], by['Chosen Sharpshooters'], by['Chosen Divines']   # 캐리 킨드레드(3)·애쉬(4), 진(4)·리븐(4), 워윅(4)·요네(5)
    assert top_carry2(field(('ashe', 2)), hunters) and not top_carry2(field(('kindred', 2), ('ashe', 1)), hunters)
    assert top_carry2(field(('riven', 2)), sharp) and top_carry2(field(('jhin', 2)), sharp) and not top_carry2(field(('jhin', 1)), sharp)
    for units in ((('warwick', 2),), (('warwick', 1), ('yone', 2)), (('warwick', 2), ('yone', 1)), ()):
        assert top_carry2(field(*units), divines) == stable(field(*units), divines)
    assert top_carry2(field(('warwick', 2)), divines) and not top_carry2(field(('yone', 2)), divines)


def nine_arms_are_a_knob_on_top_of_the_textbook_test():
    seat = lambda arm: lesson(arm)(None, None, [], random.Random(0)).knobs
    assert seat('stage6')['nine'] == 'stage6' and seat('stage6')['late'] is None and seat('stage6')['spend'] == KNOBS['spend']
    assert seat('low30')['nine'] is None and seat(None)['nine'] is None
    assert parse(['--arm', 'b_all', '--everyone', '--out', 'x.json']).arm == 'b_all'


def everyone_run_seats_the_arm_in_all_eight_seats_test():
    """--everyone: 여덟 자리 모두 그 팔이다. 판 전체의 모습(살아 있는 자리, 등수별 레벨)을 재려고 쓴다. 등수 차는 없다."""
    seed, rows, err = lesson_game((990006, 'stop', True))
    assert err is None and seed == 990006 and all(r['lesson'] for r in rows) and len(rows) == N_PLAYERS
    res = run('stop', 1, jobs=1, seed0=990006, everyone=True)
    assert res['everyone'] and res['games'] == 1 and res['diff'] is None and len(res['rows'][0]) == N_PLAYERS
    assert 'stop' in line(res)


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
