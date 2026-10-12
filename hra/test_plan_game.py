"""
계획 AI 판 검사(시뮬레이터 판을 실제로 돌려서 느리다, 판 하나에 20초쯤).

실행: python -m hra.test_plan_game
"""
import numpy as np

from hra.plan_bot import play, safe_play
from hra.plan_state import MASK_SIZE, SLICES, STATE_SIZE
from meta.lobby import BOARDS

DUELISTS = next(i for i, b in enumerate(BOARDS) if b['name'] == 'Chosen Duelists') + 1


def recorded_game_chains_round_experiences_test():
    """규칙 기록기 8명 한 판: 등수는 1~8이 하나씩 나가고, 자리마다 경험이 라운드마다 하나씩 이어진다(다음 상태 = 다음 경험의
    상태). 끝 표시는 마지막 하나뿐이고 등수 보상은 마지막 경험에만 1 - 2(등수-1)/7로 붙는다. 정답은 가리지 않은 칸이다."""
    out = play(11, ['record'] * 8)
    assert not out['capped']
    assert sorted(s['place'] for s in out['seats']) == list(range(1, 9))
    for seat in out['seats']:
        ts = seat['transitions']
        assert ts, seat['place']
        assert ts[0][2][0] != 0  # 2-1에 첫 덱을 고른다
        for k, (s, m, a, r, s2, d, m2) in enumerate(ts):
            assert s.shape == (STATE_SIZE,) and m.shape == (MASK_SIZE,) and r.shape == (5,)
            assert all(m[lo + i] for (lo, _), i in zip(SLICES, a))
            assert r[1] <= 0 and 0 <= r[2] <= 1 and r[3] >= 0 and r[4] >= 0
            last = k == len(ts) - 1
            assert d == last
            assert abs(r[0] - (1 - 2 * (seat['place'] - 1) / 7 if last else 0.0)) < 1e-6
            if not last:
                assert np.array_equal(s2, ts[k + 1][0]) and np.array_equal(m2, ts[k + 1][1])


def plan_seat_rolls_buys_and_keeps_its_deck_test():
    """계획 자리 하나(0번): 2-1~2-3에는 Chosen Duelists로 가서 골드를 다 써 리롤(남길 골드 0), 그 뒤로는 그대로·레벨 그대로·
    리롤 안 함. 다른 자리는 규칙 사람 봇. 앞 라운드들에는 리롤('2')과 사기('3_')가 섞여 나오고, 뒤 라운드에는 리롤이 없다.
    덱은 끝까지 Chosen Duelists이고 갈아탄 횟수는 0이다. 한 계획이 여러 행동으로 실행된다는 뜻이다."""
    def planner(s, m):
        if not m[0]:
            return DUELISTS, 0, 5
        return (0, 0, 5) if round(float(s[0]) * 40) <= 5 else (0, 0, 0)
    out = play(12, [planner] + ['rule'] * 7, trace=True)
    seat = out['seats'][0]
    assert seat['deck'] == 'Chosen Duelists' and seat['switches'] == 0
    early = [t for r, t in seat['tokens'] if 3 <= r <= 5]
    late = [t for r, t in seat['tokens'] if r > 5]
    assert '2' in early and any(t.startswith('3_') for t in early), early
    assert '2' not in late


def deck_hopping_planner_does_not_break_the_game_test():
    """최악의 탐험: 0번 자리가 라운드마다 다른 덱으로 갈아탄다. 판이 끝까지 돌고, 갈아탄 횟수가 판단 수 - 1이다."""
    calls = []

    def planner(s, m):
        calls.append(1)
        d = len(calls) % 27 + 1
        if not m[d]:
            d = d % 27 + 1
        return d, 0, 1
    out = play(14, [planner] + ['rule'] * 7)
    seat = out['seats'][0]
    assert not out['capped'] and seat['switches'] == len(calls) - 1 == len(seat['transitions']) - 1


def rule_recorder_labels_follow_rule_rolls_test():
    """규칙 기록기의 남길 골드 정답: 그 라운드에 리롤('2')이 있었으면 「리롤 안 함」(0번)이 아니다."""
    out = play(13, ['record'] + ['rule'] * 7, trace=True)
    seat = out['seats'][0]
    rolled = {r for r, t in seat['tokens'] if t == '2'}
    assert rolled
    for r, t in zip(seat['rounds'], seat['transitions']):
        if r in rolled:
            assert t[2][2] != 0, r


def safe_play_returns_the_error_instead_of_raising_test():
    """계획기가 판 중간(3-1)에 예외를 내면 safe_play는 판을 버리고 (None, 오류 문자열)을 돌려준다."""
    def planner(s, m):
        if round(float(s[0]) * 40) >= 9:
            raise RuntimeError('boom')
        return (1 if not m[0] else 0), 0, 1
    out, err = safe_play(15, [planner] + ['rule'] * 7)
    assert out is None and 'RuntimeError: boom' in err


def one_recorded_game_stacks_into_arrays_test():
    """기록 판 하나를 모으면 KEYS별 배열이 같은 길이로 쌓이고 끝 표시는 자리 수(8)만큼이다. 판 번호 열이 붙는다."""
    from hra.collect import one_game, stack
    ts, err = one_game(901)
    assert err is None and ts
    data = stack(ts, games=[0] * len(ts))
    n = len(ts)
    assert data['s'].shape == (n, 153) and data['m'].shape == (n, 37) and data['a'].shape == (n, 3)
    assert data['r'].shape == (n, 5) and data['d'].sum() == 8 and (data['game'] == 0).all()


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
