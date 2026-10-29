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


def collect_saves_as_it_goes_and_resumes_test():
    """1판마다 저장하며 2판을 모은 뒤 같은 파일로 3판까지 부르면 3번째 판만 더 돌고 뒤에 이어 붙는다(모으다 꺼져도 다시
    부르면 이어 간다)."""
    import os
    import tempfile
    from hra.collect import collect
    out = os.path.join(tempfile.mkdtemp(), 'demos.npz')
    collect(2, jobs=1, out=out, save_every=1)
    first = dict(np.load(out))
    assert int(first['seeds_done']) == 2 and sorted(set(first['game'].tolist())) == [0, 1]
    collect(3, jobs=1, out=out, save_every=1)
    second = dict(np.load(out))
    assert int(second['seeds_done']) == 3 and sorted(set(second['game'].tolist())) == [0, 1, 2]
    assert np.array_equal(second['s'][:len(first['s'])], first['s']) and int(second['n_games']) == 3


def ab_rule_against_rule_runs_test():
    """배관 검사 판짜기: 규칙 대 규칙 두 판. 판마다 등수 차는 -4~4이고 결과에 판정이 있다."""
    from hra.evaluate import ab
    res = ab(None, games=2, jobs=1)
    assert res['games'] == 2 and all(-4 <= d <= 4 for d in res['per_game']) and 'pass' in res


def agree_and_meta_run_with_a_fresh_net_test():
    """학습 안 한 신경망으로도 행동 일치율과 AI 메타가 끝까지 나온다(덱을 엉뚱하게 갈아타도 판이 돈다)."""
    import os
    import tempfile
    from hra.evaluate import agree, meta
    from hra.plan_net import PlanNet, save, weights
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(PlanNet(), path, weights('both', 0.1), config='both', seed=0, games=0)
    a = agree(path, games=1, jobs=1)
    assert a['decisions'] > 0 and 0 <= a['all'] <= 1
    m = meta(path, games=1, jobs=1)
    assert m['families'] and abs(sum(share for _, share, _ in m['families']) - 1) < 1e-9


def selfplay_runs_saves_and_resumes_test():
    """아주 작은 자기 대전: 2판 학습, 2판마다 저장과 점검(점검 1판). 같은 설정으로 3판까지 다시 부르면 이어서 1판만 더 돌고
    곡선이 한 줄 는다(컴퓨터가 꺼진 뒤 같은 명령으로 이어 가기). 여백 손실을 2판까지 1→0으로 줄이게 하면 학습 걸음마다
    그 가중치가 실제로 들어가고(레벨·남길 골드 갈래가 1판 뒤 0.5, 2판 뒤 0, 덱 갈래는 1로 그대로), 곡선과 결과 파일에 남는다."""
    import json
    import os
    import tempfile
    import hra.selfplay as sp
    from hra.selfplay import train
    root = tempfile.mkdtemp()
    seen, real = [], sp.learn_step
    sp.learn_step = lambda *a, **k: seen.append(k.get('lam')) or real(*a, **k)
    try:
        first = train('both', 0.1, seed=5, games=2, jobs=1, save_every=2, eval_games=1, root=root, margin_until=2,
                      margin_keep_deck=True)
    finally:
        sp.learn_step = real
    assert seen and set(seen) <= {(1.0, 0.5, 0.5), (1.0, 0.0, 0.0)} and seen[-1] == (1.0, 0.0, 0.0)
    log = json.load(open(os.path.join(root, 'results', 'plan_both_s5.json'), encoding='utf-8'))
    assert first['games'] == 2 and [c['games'] for c in log['curve']] == [2]
    assert log['margin_until'] == 2 and log['margin_keep_deck'] is True and log['curve'][0]['margin'] == 0.0
    second = train('both', 0.1, seed=5, games=3, jobs=1, save_every=2, eval_games=1, root=root, margin_until=2,
                   margin_keep_deck=True)
    log = json.load(open(os.path.join(root, 'results', 'plan_both_s5.json'), encoding='utf-8'))
    assert second['games'] == 3 and [c['games'] for c in log['curve']] == [2, 3]
    assert os.path.exists(os.path.join(root, 'checkpoints', 'plan_both_s5_best.pt'))
    # 이어 간 뒤의 첫 점검 줄에는 이어 하기 표시가 붙는다(경험 더미는 저장하지 않아 그 구간은 빈 더미에서 다시 배운다)
    assert [c.get('resumed', False) for c in log['curve']] == [False, True]
    # 본체는 스레드 하나로 배운다. 일꾼 6개가 CPU를 다 쓸 때 스레드 둘이면 학습 한 걸음이 35ms에서 480ms로 늘어
    # 자기 대전이 1분에 9판으로 막혔다(2026-10-13 측정)
    import torch
    assert torch.get_num_threads() == 1


def capped_games_count_as_stopped_test():
    """걸음 상한에 걸린 판은 살아남은 자리의 등수가 자리 순서라 쓸 수 없다. 모으기·평가·자기 대전 모두 그 판을 버리고
    멈춘 판으로 센다(상한을 40걸음으로 낮춰 일부러 걸리게 한다)."""
    import os
    import tempfile
    import hra.plan_bot as pb
    from hra.collect import one_game
    from hra.evaluate import ab_game, agree_game, meta_game
    from hra.plan_net import PlanNet, save, weights
    from hra.selfplay import selfplay_game
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(PlanNet(), path, weights('none', 0.3))
    old = pb.MAX_STEPS
    pb.MAX_STEPS = 40
    try:
        assert one_game(31) == ([], 'capped')
        assert ab_game((32, None))[1:] == (None, 'capped')
        assert agree_game((33, path)) == ([], 'capped')
        assert meta_game((34, path)) == ([], 'capped')
        assert selfplay_game((35, path, (0.0, 0.0, 0.0)))[1:] == (None, 'capped')
    finally:
        pb.MAX_STEPS = old


def switching_decks_acts_in_that_round_test():
    """덱을 갈아타는 라운드에 실행기가 실제로 리롤·사기·바꾸기를 하고, 그 뒤 벤치가 차면 옛 덱 유닛을 판다(설계 7절).
    0번 자리는 2-1에 Chosen Duelists로 가서 골드를 모으다(남길 골드 50) 3-2(칸 10)에 Chosen Warlords로 갈아타며 골드를 다
    쓴다(남길 골드 0)."""
    WARLORDS = next(i for i, b in enumerate(BOARDS) if b['name'] == 'Chosen Warlords') + 1

    def planner(s, m):
        if not m[0]:
            return DUELISTS, 0, 1
        return (WARLORDS, 0, 5) if round(float(s[0]) * 40) == 10 else (0, 0, 1)
    out = play(16, [planner] + ['rule'] * 7, trace=True)
    seat = out['seats'][0]
    assert seat['switches'] == 1 and seat['deck'] == 'Chosen Warlords'
    kinds = lambda lo, hi: {t[0] for r, t in seat['tokens'] if lo <= r <= hi}
    assert {'2', '3', '5'} <= kinds(10, 10), sorted(kinds(10, 10))   # 갈아탄 라운드: 리롤·사기·바꾸기
    assert '4' in kinds(10, 14)                                        # 그 뒤 벤치가 차면 팔기


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
