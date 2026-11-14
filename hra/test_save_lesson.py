"""
「돈 모으기」 수업 점검 검사(hra/save_lesson.py). 끝의 검사 하나는 판을 실제로 돌려서 느리다(20초쯤).

실행: python -m hra.test_save_lesson
"""
from hra.save_lesson import after, before_interest, ceiling, checks, early, first_difference, income, seat, verdict, walk
from hra.plan_bot import safe_play
from hra.spend_lesson import MADE, lesson
from meta.lobby import N_PLAYERS

# [칸, 레벨, 골드, 체력]. 2-1에 4골드를 쓰고 지고, 2-2를 지고, 2-3·2-5·2-6을 이기고, 크립에게 지고(연속 그대로), 3-1을 이긴 자리
CURVE = [[1, 2, 4, 100], [2, 2, 7, 100], [3, 3, 11, 100], [4, 4, 12, 98], [5, 4, 19, 95], [6, 4, 27, 95], [7, 4, 36, 95],
         [8, 4, 46, 95], [9, 4, 56, 90], [10, 4, 69, 90]]


def before_interest_inverts_gold_plus_interest_test():
    for gold in range(130):
        assert before_interest(gold + min(gold // 10, 5)) == gold
    # 9골드는 9, 10골드는 11이 된다: 「골드 + 이자」가 10인 골드는 없다
    assert [before_interest(t) for t in (10, 21, 32, 43, 54)] == [None] * 5


def walk_reads_wins_streaks_and_interest_from_a_curve_test():
    rows = {r['slot']: r for r in walk(CURVE)}
    assert rows[3] == {'slot': 3, 'before': 7, 'interest': 0, 'streak': 0, 'won': None, 'wins': 0, 'losses': 0}
    assert rows[4] == {'slot': 4, 'before': 7, 'interest': 0, 'streak': 0, 'won': False, 'wins': 0, 'losses': 1}
    assert rows[5] == {'slot': 5, 'before': 12, 'interest': 1, 'streak': 1, 'won': False, 'wins': 0, 'losses': 2}
    # 이기면 그 자리에서 +1이고 그 골드에 이자가 붙는다(19 + 1 = 20 → 이자 2)
    assert rows[6] == {'slot': 6, 'before': 20, 'interest': 2, 'streak': 0, 'won': True, 'wins': 1, 'losses': 0}
    assert rows[8] == {'slot': 8, 'before': 37, 'interest': 3, 'streak': 1, 'won': True, 'wins': 3, 'losses': 0}
    # 크립 라운드(8번째 칸)는 져서 체력이 깎여도 연속이 그대로이고 승리 골드도 없다
    assert rows[9] == {'slot': 9, 'before': 46, 'interest': 4, 'streak': 1, 'won': None, 'wins': 3, 'losses': 0}
    assert rows[10] == {'slot': 10, 'before': 57, 'interest': 5, 'streak': 2, 'won': True, 'wins': 4, 'losses': 0}


def walk_stops_at_4_1_test():
    long = CURVE + [[s, 6, 60, 90] for s in range(11, 20)]
    assert walk(long)[-1]['slot'] == 15


def walk_marks_an_income_it_cannot_explain_test():
    # 2-1을 15골드로 시작했는데 다음 수입 뒤가 15골드(이자 붙기 직전 골드 + 이자 = 10)인 자리는 없다
    odd = walk([[3, 3, 15, 100], [4, 4, 15, 98]])
    assert odd[0]['before'] is None and odd[0]['interest'] is None and odd[0]['losses'] == 1


def early_strategy_is_read_back_from_wins_and_losses_test():
    r = lambda slot, wins, losses: {'slot': slot, 'wins': wins, 'losses': losses}
    # 2-3(5번째 칸)을 시작할 때 2연승이면 연승형
    assert early([r(4, 1, 0), r(5, 2, 0), r(6, 3, 0), r(7, 0, 1), r(8, 1, 0)]) == 'win'
    # 그 뒤 4-1 전에 2연패를 보면 연패형으로 바뀐다
    assert early([r(4, 1, 0), r(5, 2, 0), r(6, 0, 1), r(7, 0, 2)]) == 'switch'
    assert early([r(4, 1, 0), r(5, 0, 1), r(6, 1, 0), r(7, 2, 0)]) == 'lose'
    # 4-1(15번째 칸)에 본 2연패로는 바뀌지 않는다
    assert early([r(4, 1, 0), r(5, 2, 0), r(14, 0, 1), r(15, 0, 2)]) == 'win'
    assert early(walk(CURVE)) == 'lose'


def ceiling_follows_the_income_rules_test():
    wins = ceiling([True] * 10)
    assert [wins[s] for s in (3, 4, 5, 6, 7, 8, 9)] == [10, 17, 25, 34, 45, 58, 71]   # 크립 라운드 뒤에도 연속 골드는 받는다
    losses = ceiling([False] * 10)
    assert [losses[s] for s in (3, 4, 5, 6, 7, 8, 9)] == [10, 16, 23, 31, 41, 53, 66]
    assert sorted(wins) == list(range(3, 16))


def verdict_uses_the_preregistered_cuts_test():
    assert [verdict(x) for x in (1.0, 0.8, 0.79, 0.5, 0.49, 0.0)] == ['맞춘다', '맞춘다', '절반 넘게 맞춘다', '절반 넘게 맞춘다',
                                                                   '못 맞춘다', '못 맞춘다']


def _row(curve, place=1):
    return {'curve': curve, 'place': place, 'deck': 'Chosen Dusks'}


def checks_count_seats_meeting_each_benchmark_test():
    rich = CURVE + [[11, 6, 60, 90], [12, 6, 63, 90], [13, 6, 64, 90], [14, 6, 66, 90], [15, 6, 70, 90]]
    # 2-1부터 대전을 모두 지고 돈을 써서 20골드 근처에 머무는 자리
    poor = [[1, 2, 4, 100], [2, 2, 7, 100], [3, 3, 10, 100], [4, 3, 11, 98], [5, 4, 18, 96], [6, 4, 20, 94], [7, 4, 18, 92],
            [8, 4, 19, 90], [9, 4, 22, 90], [10, 4, 30, 88], [11, 4, 30, 86], [12, 4, 30, 84], [13, 4, 30, 82], [14, 4, 30, 80],
            [15, 4, 30, 80]]
    out = checks([[seat(_row(rich)), seat(_row(poor, 5))]])
    assert out[1]['met'] == 1.0            # 2-1 시작 골드 11, 10
    assert out[2]['met'] == 1.0            # 2-3이 끝난 뒤 이자 붙기 직전 골드 20, 13
    assert out[3]['met'] == 0.5 and out[3]['above'] == 0.5 and out[3]['below'] == 0.0   # 3-1 시작 골드 56, 22
    assert out[4]['met'] == 0.5 and out[5]['met'] == 0.5                                # 3-7·4-1 시작 골드 66·70, 30·30
    assert out[6]['met'] == 1.0 and out[7]['met'] == 0.0 and out[8]['met'] == 0.5       # 레벨
    assert out[3]['median'] == 39 and out[3]['games'] == 1


def income_splits_the_twelve_incomes_and_gives_what_was_spent_test():
    rich = CURVE + [[11, 6, 60, 90], [12, 6, 63, 90], [13, 6, 64, 90], [14, 6, 66, 90], [15, 6, 70, 90]]
    i = income(seat(_row(rich)))
    assert (i['interest2'], i['interest3'], i['missed']) == (12, 29, 19)
    assert (i['streak'], i['wins']) == (21, 8)
    # 2단계에는 2-1의 4골드만 썼다. 2~3단계 합은 4 + 22 + 11 + 13 + 12 + 9
    assert (i['spent2'], i['spent']) == (4, 71)


def after_relates_gold_and_health_at_4_1_to_the_final_place_test():
    def one(gold, hp, place):
        return {'at': {15: (7, gold, hp)}, 'place': place}
    out = after([one(60, 90, 1), one(65, 70, 3), one(70, 50, 5)])
    # 골드가 많을수록 등수 숫자가 크고(나쁘고), 체력이 많을수록 작다(좋다)
    assert abs(out['gold_place_corr'] - 1.0) < 1e-9 and abs(out['hp_place_corr'] + 1.0) < 1e-9
    assert [(b['from'], b['seats']) for b in out['by_gold']] == [(0, 0), (60, 2), (67, 1)]
    assert out['by_gold'][1] == {'from': 60, 'seats': 2, 'gold': 62.5, 'hp': 80, 'place': 2}
    assert [(b['from'], b['seats']) for b in out['by_hp']] == [(0, 0), (45, 1), (65, 1), (85, 1)]


def first_difference_finds_where_two_runs_part_test():
    a = [[{'curve': [[1, 2, 4, 100], [2, 2, 7, 100], [3, 3, 11, 100]]}, {'curve': [[1, 2, 4, 100], [2, 2, 7, 100]]}]]
    b = [[{'curve': [[1, 2, 4, 100], [2, 2, 7, 100], [3, 3, 10, 100]]}, {'curve': [[1, 2, 4, 100], [2, 2, 7, 100]]}]]
    assert first_difference(a, b) == {3: 1, None: 1}


class Spy(lesson(None)):
    """교과서 자리. 라운드의 첫 행동 때 시뮬레이터가 실제로 준 이자, 연승·연패 수, 그때의 초반 전략을 적는다."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.seen = {}

    def __call__(self, player, shop, game_round, mask):
        first = game_round != self.last_round
        act = super().__call__(player, shop, game_round, mask)
        if first:
            self.seen[game_round] = (player.last_interest, player.win_streak, player.loss_streak, self.mode)
        return act


def walk_matches_the_simulator_in_a_real_game_test():
    MADE.clear()
    out, err = safe_play(990004, [Spy] * N_PLAYERS)
    assert err is None and len(MADE) == N_PLAYERS
    for pol in MADE:
        rows = walk(pol.curve)
        assert [r['slot'] for r in rows] == list(range(2, 16))
        for r in rows:
            interest, wins, losses, _ = pol.seen[r['slot']]
            assert (r['interest'], r['wins'], r['losses']) == (interest, wins, losses), (r, pol.seen[r['slot']])
        was_win, still_win = pol.seen[5][3] == 'win', pol.seen[14][3] == 'win'
        assert early(rows) == ('win' if still_win else 'switch' if was_win else 'lose')


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
