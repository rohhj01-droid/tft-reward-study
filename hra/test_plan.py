"""
계획 AI 빠른 검사(판을 돌리지 않는다).

실행: python -m hra.test_plan
"""
import numpy as np


def board_scores_count_value_traits_units_test():
    """사람 봇 덱 Chosen Duelists(완성, 모두 2성): 보드 값 3+3+5+8+5+11+14+14 = 63(1학기 값표), 발동한 특성 단계 10, 유닛 8."""
    from hra.score_rank import board_scores
    from meta.lobby import BOARDS
    from meta.pit import chosen_of
    b = next(b for b in BOARDS if b['name'] == 'Chosen Duelists')
    assert board_scores(b['units'], b['items'], chosen_of(b)[1]) == (63, 10, 8)


def rho_skips_constant_lists_test():
    """8명 보드끼리는 유닛 수 점수가 모두 같아 순위 상관을 낼 수 없다. 그때는 None이다."""
    from hra.score_rank import rho
    assert rho([8, 8, 8], [0.1, 0.5, 0.3]) is None
    assert rho([1, 2, 3], [10, 20, 30]) == 1.0


def plan_sizes_and_slices_test():
    from hra.plan_state import HEADS, MASK_SIZE, PLAN_SIZES, SLICES
    assert HEADS == ('place', 'hp', 'econ', 'synergy', 'units')
    assert PLAN_SIZES == (28, 3, 6) and MASK_SIZE == 37
    assert SLICES == ((0, 28), (28, 31), (31, 37))


def masks_hide_impossible_plans_test():
    """덱이 없으면(2-1) 「그대로」를 가리고, 덱이 있으면 지금 덱을 다시 고르는 칸을 가린다. 레벨은 9를 넘는 목표를 가린다."""
    from hra.plan_state import masks
    from meta.lobby import BOARDS
    m = masks(3, None)
    assert not m[0] and m[1:28].all() and m[28:31].all() and m[31:].all()
    m = masks(8, BOARDS[4])
    assert m[0] and not m[5] and m[28] and m[29] and not m[30]
    assert list(masks(9, BOARDS[0])[28:31]) == [True, False, False]


def decode_turns_numbers_into_a_plan_test():
    from hra.plan_state import decode
    from meta.lobby import BOARDS
    assert decode((0, 1, 3), 5, BOARDS[2]) == (BOARDS[2], 6, 20)
    assert decode((5, 0, 0), 4, None) == (BOARDS[4], 4, None)


def floor_index_picks_nearest_floor_test():
    from hra.plan_state import floor_index
    assert [floor_index(f) for f in (None, 50, 20, 10, 0, 35, 45, 60)] == [0, 1, 3, 4, 5, 2, 1, 1]


def rule_label_maps_one_round_of_rule_play_test():
    """규칙의 한 라운드 -> 계획 번호. 레벨은 올릴 단계 수(0~2, 9를 넘지 않게), 남길 골드는 가장 가까운 칸."""
    from hra.plan_state import rule_label
    from meta.lobby import BOARDS
    assert rule_label(None, BOARDS[3], 3, 4, None) == (4, 1, 0)      # 2-1 첫 덱, 레벨 4 목표, 리롤 없음
    assert rule_label(BOARDS[3], BOARDS[3], 6, 7, 20) == (0, 1, 3)   # 4-1: 그대로, 7로, 20 남기고
    assert rule_label(BOARDS[3], BOARDS[7], 5, 9, 0) == (8, 2, 5)    # 갈아타기, 두 단계로 자름, 다 쓰기
    assert rule_label(BOARDS[3], BOARDS[3], 8, 9, 50) == (0, 1, 1)   # 레벨 8은 한 단계까지만


def _player(units, bench=(), index=0, **attrs):
    """시뮬레이터 플레이어. units는 보드(구석 배치), bench는 벤치, attrs는 골드·체력·레벨 같은 값."""
    from analysis.battle import build_player, to_units
    from Simulator.pool import pool
    p = build_player(pool(), index, to_units(list(units)), 'corner')
    for u in to_units(list(bench)):
        p.add_to_bench(u)
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


def state_counts_what_a_player_can_see_test():
    """2성 야스오(선택받은 결투가, 무한의 대검)·1성 피오라·3성 잭스가 보드에, 1성 칼리스타가 벤치에 있다. 살아 있는 상대
    다섯(체력 80·70·50·90·64, 레벨 6·6·5·7·6, 첫째가 2성 야스오를 든다), 죽은 상대 둘(2성 리 신을 든 쪽은 정찰에서 빠진다).
    목표 덱은 Chosen Duelists(4번), 고른 뒤 2라운드, 3-1(칸 9)."""
    from hra.plan_state import STATE_SIZE, state
    from meta.lobby import BOARDS
    me = _player([{'name': 'yasuo', 'stars': 2, 'items': ['infinity_edge'], 'chosen': 'duelist'},
                  {'name': 'fiora', 'stars': 1, 'items': []}, {'name': 'jax', 'stars': 3, 'items': []}],
                 bench=[{'name': 'kalista', 'stars': 1, 'items': []}],
                 gold=35, health=64, level=5, exp=10, win_streak=0, loss_streak=3)
    others = [_player([{'name': 'yasuo', 'stars': 2, 'items': []}], index=1, health=80, level=6)]
    others += [_player([{'name': 'garen', 'stars': 1, 'items': []}], index=i, health=h, level=lv)
               for i, h, lv in ((2, 70, 6), (3, 50, 5), (4, 90, 7), (5, 64, 6))]
    others += [_player([{'name': 'leesin', 'stars': 2, 'items': []}], index=6, health=0, level=9),
               _player([{'name': 'garen', 'stars': 1, 'items': []}], index=7, health=0, level=9)]
    x = state(me, others, BOARDS[4], 2, 9)
    assert x.shape == (STATE_SIZE,) == (153,) and x.dtype == np.float32
    # 내 상태: 칸/40, 체력/100, 골드/60, 레벨/9, 경험치 10/20, 연승/5, 연패/5, 살아 있는 상대/7
    # 내 보드: 보드 값 3+1+17=21 /120, 2성 1/9, 3성 1/9, 특성 단계(결투가 4 → 2, 추방자 1 → 1) 3/11, 유닛 3/9, 완성 1/10, 조각 0
    assert np.allclose(x[:15], [9 / 40, 0.64, 35 / 60, 5 / 9, 0.5, 0.0, 0.6, 5 / 7,
                                21 / 120, 1 / 9, 1 / 9, 3 / 11, 3 / 9, 0.1, 0.0]), x[:15]
    assert np.allclose(x[15:20], [0.0, 0.0, 0.0, 0.125, 0.0]), x[15:20]       # 0번 Chosen Dusks: 무한의 대검 하나 만들 수 있음
    assert np.allclose(x[35:40], [25 / 40, 0.3, 1.0, 0.0, 1.0]), x[35:40]     # 4번 Chosen Duelists: 몫 25, 남의 야스오 3장
    assert np.allclose(x[150:], [3 / 7, 6 / 9, 0.1]), x[150:]                 # 나보다 체력 많은 3명, 평균 레벨 6, 이력 2


def finish_without_a_decision_does_nothing_test():
    """판단 없이 끝난 자리(2-1 전 탈락)는 경험이 없고, finish를 두 번 불러도 한 번만 닫는다."""
    from hra.plan_bot import Recorder
    r = Recorder()
    r.start_recording()
    r.current_plan = lambda player: None
    me = _player([{'name': 'garen', 'stars': 1, 'items': []}])
    r.finish(me, 8)
    r.finish(me, 8)
    assert r.transitions == [] and r.finished


def plan_net_outputs_five_heads_by_37_cells_test():
    import torch
    from hra.plan_net import PlanNet
    assert tuple(PlanNet()(torch.zeros(4, 153)).shape) == (4, 5, 37)


def masked_choice_never_picks_a_hidden_cell_test():
    """가중합으로 고르든 무작위로 고르든(탐험 몫 100%) 가린 칸은 고르지 않는다. 2-1에 「그대로」를 고르면 덱 없이 판이 돈다."""
    import random
    import torch
    from hra.plan_net import PlanNet, choose, weights
    from hra.plan_state import masks
    from meta.lobby import BOARDS
    torch.manual_seed(0)
    net, w, rng = PlanNet(), weights('both', 0.1), random.Random(0)
    for level, deck in ((3, None), (8, BOARDS[4]), (9, BOARDS[0])):
        m = masks(level, deck)
        for eps in ((0, 0, 0), (1, 1, 1)):
            for _ in range(300):
                d, lv, fl = choose(net, np.zeros(153, np.float32), m, w, eps, rng)
                assert m[d] and m[28 + lv] and m[31 + fl], (level, eps, d, lv, fl)


def exploration_rate_is_per_branch_test():
    """덱 갈래만 탐험 몫 100%, 나머지 0%면 레벨·남길 골드는 늘 가중합 선택과 같고 덱은 여러 칸이 나온다."""
    import random
    import torch
    from hra.plan_net import PlanNet, choose, weights
    from hra.plan_state import masks
    torch.manual_seed(1)
    net, w, rng, m = PlanNet(), weights('none', 0.1), random.Random(1), masks(5, None)
    s = np.full(153, 0.3, np.float32)
    greedy = choose(net, s, m, w)
    picks = [choose(net, s, m, w, (1, 0, 0), rng) for _ in range(200)]
    assert all(p[1:] == greedy[1:] for p in picks) and len({p[0] for p in picks}) > 10


def weights_follow_config_test():
    from hra.plan_net import weights
    assert weights('none', 0.1) == {'place': 1.0, 'hp': 1.0, 'econ': 0.3, 'synergy': 0.0, 'units': 0.0}
    assert weights('both', 0.3)['synergy'] == weights('both', 0.3)['units'] == 0.3
    assert weights('units', 0.1)['synergy'] == 0.0 and weights('synergy', 0.1)['units'] == 0.0


def plan_net_save_load_and_flip_rate_test():
    """저장했다 불러온 신경망은 같은 값과 같은 선택을 낸다. 보조 갈래 가중치가 0이면 보조 갈래가 뒤집는 판단은 없다."""
    import os
    import tempfile
    import torch
    from hra.plan_net import PlanNet, flip_rate, load, save, weights
    from hra.plan_state import masks
    net, w = PlanNet(), weights('both', 0.1)
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(net, path, w, config='both', seed=1, games=0)
    net2, w2, meta = load(path)
    x = torch.rand(16, 153)
    assert torch.equal(net(x), net2(x)) and w2 == w and meta == {'config': 'both', 'seed': 1, 'games': 0}
    states = np.random.default_rng(0).random((50, 153)).astype(np.float32)
    ms = np.stack([masks(5, None)] * 50)
    assert flip_rate(net, states, ms, weights('none', 0.3)) == 0.0
    assert 0.0 <= flip_rate(net, states, ms, weights('both', 5.0)) <= 1.0


def _bandit_transition(d, s, m):
    """판단 한 번에 끝나는 판의 경험: 덱 3번이면 등수 +1, 아니면 -1."""
    return (s, m, np.array([d, 0, 0]), np.array([1.0 if d == 3 else -1.0, 0, 0, 0, 0], np.float32),
            np.zeros(153, np.float32), True, np.ones(37, bool))


def replay_wraps_around_test():
    from hra.plan_learn import Replay
    r = Replay(3)
    s, m = np.zeros(153, np.float32), np.ones(37, bool)
    for d in range(5):
        r.add(_bandit_transition(d, s, m))
    assert len(r) == 3 and sorted(r.a[:, 0].tolist()) == [2, 3, 4]
    back = Replay.from_arrays(r.arrays())
    assert len(back) == 3 and np.array_equal(back.a, r.a)


def td_loss_learns_a_one_round_bandit_test():
    """무작위로 고른 경험 600개로 배우면 가중합 선택이 등수 +1을 주는 덱 3번이다."""
    import torch
    from hra.plan_learn import Replay, learn_step
    from hra.plan_net import PlanNet, choose, weights
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    s, m = np.full(153, 0.5, np.float32), np.ones(37, bool)
    m[0] = False
    replay = Replay(1000)
    for _ in range(600):
        replay.add(_bandit_transition(int(rng.integers(1, 28)), s, m))
    net, target, w = PlanNet(), PlanNet(), weights('none', 0.1)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ in range(400):
        learn_step(net, target, opt, w, batch=replay.sample(64, rng))
    assert choose(net, s, m, w)[0] == 3


def margin_loss_makes_demo_choices_win_test():
    """여백 손실로 상태 다섯 개의 정답 계획을 외운다(보상은 모두 0)."""
    import torch
    from hra.plan_learn import Replay, learn_step
    from hra.plan_net import PlanNet, choose, weights
    torch.manual_seed(2)
    rng = np.random.default_rng(2)
    states = rng.random((5, 153)).astype(np.float32)
    labels = [(4, 1, 2), (9, 0, 5), (17, 2, 0), (1, 1, 1), (26, 0, 3)]
    demos = Replay(10)
    for s, a in zip(states, labels):
        demos.add((s, np.ones(37, bool), np.array(a), np.zeros(5, np.float32), np.zeros(153, np.float32), True,
                   np.ones(37, bool)))
    net, target, w = PlanNet(), PlanNet(), weights('none', 0.1)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ in range(300):
        learn_step(net, target, opt, w, demo=demos.sample(5, rng))
    assert [choose(net, s, np.ones(37, bool), w) for s in states] == labels


def _fake_demos(n, seed=0):
    """정답이 상태 첫 칸으로 정해지는 가짜 따라 하기 자료(덱 = 1 + 첫 칸을 27칸으로 나눈 번호, 레벨 0, 남길 골드 1)."""
    rng = np.random.default_rng(seed)
    s = rng.random((n, 153)).astype(np.float32)
    deck = 1 + (s[:, 0] * 27).astype(int).clip(0, 26)
    return {'s': s, 'm': np.ones((n, 37), bool), 'a': np.stack([deck, np.zeros(n, int), np.ones(n, int)], 1),
            'r': np.zeros((n, 5), np.float32), 's2': np.zeros((n, 153), np.float32), 'd': np.ones(n, bool),
            'm2': np.ones((n, 37), bool), 'game': np.arange(n) // 10}


def split_by_game_keeps_games_whole_test():
    """같은 판의 경험은 학습과 점검 중 한쪽에만 간다. 20판(판마다 10개) 중 10%인 2판을 떼어 둔다.
    상태 첫 칸은 경험마다 다른 무작위 값이라 그 값으로 경험의 판을 찾는다."""
    from hra.pretrain import split_by_game
    data = _fake_demos(200)
    game_of = {float(v): int(g) for v, g in zip(data['s'][:, 0], data['game'])}
    train, test = split_by_game(data, held=0.1, seed=0)
    test_games = {game_of[float(v)] for v in test['s'][:, 0]}
    train_games = {game_of[float(v)] for v in train['s'][:, 0]}
    assert len(test['s']) == 20 and len(train['s']) == 180
    assert len(test_games) == 2 and not test_games & train_games


def pretrain_learns_a_simple_rule_test():
    """가짜 자료 300개를 데우면 셋 다 맞는 비율이 0.9를 넘는다."""
    from hra.plan_net import weights
    from hra.pretrain import agreement, pretrain
    data = _fake_demos(300)
    w = weights('none', 0.1)
    net, _, _ = pretrain(data, w, steps=1500, seed=0)
    assert agreement(net, data, w)['all'] > 0.9


def eps_shrinks_per_branch_test():
    """탐험 몫은 덱 3%→1%, 레벨·남길 골드 15%→5%로 학습 판 수에 따라 곧게 준다."""
    from hra.selfplay import eps_at
    assert np.allclose(eps_at(0, 100), (0.03, 0.15, 0.15))
    assert np.allclose(eps_at(50, 100), (0.02, 0.10, 0.10))
    assert np.allclose(eps_at(200, 100), (0.01, 0.05, 0.05))


def best_checkpoint_only_moves_up_test():
    """최고 저장본은 처음이거나 더 나은 점검 결과로만 바뀐다. 점검이 모두 실패해 값이 없으면(nan) 안 바뀐다."""
    from hra.selfplay import is_better
    assert is_better(0.1, None) and is_better(0.3, 0.2)
    assert not is_better(0.1, 0.2) and not is_better(float('nan'), 0.2) and not is_better(float('nan'), None)


def greedy_planner_reloads_a_rewritten_file_test():
    """같은 경로에 신경망을 새로 저장하면(자기 대전 중간 점검의 latest처럼) 평가 계획기도 새 신경망을 쓴다. 예전에는 경로만으로
    기억해서 첫 점검 뒤의 점검이 모두 첫 점검 때의 신경망을 다시 쟀다."""
    import os
    import tempfile
    import torch
    from hra.evaluate import greedy_planner
    from hra.plan_net import PlanNet, save, weights
    path = os.path.join(tempfile.mkdtemp(), 'latest.pt')
    s, m = np.zeros(153, np.float32), np.ones(37, bool)
    for deck in (1, 2):
        net = PlanNet()
        with torch.no_grad():
            net.out.weight.zero_()
            net.out.bias.zero_()
            net.out.bias[deck] = 10.0  # 등수 갈래의 덱 칸 하나만 크게
        save(net, path, weights('none', 0.1))
        os.utime(path, (deck * 1000, deck * 1000))  # 두 저장이 같은 시각 눈금에 겹치지 않게
        assert greedy_planner(path)(s, m)[0] == deck


def round_rewards_match_hand_counted_values_test():
    """라운드 보상 다섯 갈래를 손으로 센 값과 맞춘다(설계 7절). 라운드 시작 체력 70이 55가 되면 -15/20 = -0.75, 골드 35로
    라운드 시작 수입을 받으면 이자 3이라 3/5 = 0.6, 보드가 야스오·피오라·가렌이면 켜진 특성 단계는 결투가 2명과 추방자 1명으로
    2단계라 2/11, 유닛 3명은 3/9다. 등수 보상은 판 중에는 0이고 끝 표시는 없다. 3등으로 탈락하면 마지막 경험에 1 - 2·2/7이
    붙고 끝 표시가 서며 이자는 0이다."""
    from hra.plan_bot import Recorder
    me = _player([{'name': 'yasuo', 'stars': 2, 'items': []}, {'name': 'fiora', 'stars': 1, 'items': []},
                  {'name': 'garen', 'stars': 1, 'items': []}], gold=35, health=55)
    me.gold_income(5)  # 라운드 시작 수입: 감싼 함수가 그때의 이자(35 -> 3)를 적어 둔다
    assert me.last_interest == 3 and me.gold == 35 + 5 + 3
    r = Recorder()
    r.start_recording()
    r.current_plan = lambda player: (4, 1, 2)
    s, m = np.zeros(153, np.float32), np.ones(37, bool)
    r.pending = (s, m, (4, 1, 2), 70, 9)
    r.close(me, (4, 1, 2), s, m, False)
    assert np.allclose(r.transitions[-1][3], [0.0, -0.75, 0.6, 2 / 11, 3 / 9]) and not r.transitions[-1][5]
    r.pending = (s, m, (4, 1, 2), 55, 10)
    r.finish(me, 3)
    assert np.allclose(r.transitions[-1][3], [1 - 2 * 2 / 7, 0.0, 0.0, 2 / 11, 3 / 9]) and r.transitions[-1][5]


def pinned_pool_gives_workers_the_same_hash_seed_test():
    """일꾼 풀은 해시 시드를 고정한다(meta/lobby와 같은 까닭: 시뮬레이터가 집합·사전을 도는 순서가 문자열 해시에 따라
    프로세스마다 달라진다). 따로 띄운 두 풀의 일꾼이 같은 문자열에 같은 해시를 낸다. 고정하지 않으면 프로세스마다 다른
    무작위 시드를 받아 거의 늘 다르다."""
    from hra.plan_bot import pinned_pool
    hashes = []
    for _ in range(2):
        with pinned_pool(1) as p:
            hashes.append(p.apply(hash, ('plan',)))
    assert hashes[0] == hashes[1]


def cli_defaults_follow_the_chosen_weight_test():
    """명령줄 기본 보조 가중치는 사전 시험에서 고른 0.3이다(--aux-w 없이 둘 다 켬을 돌려도 같은 실험이 되게)."""
    from hra.pretrain import parser as pretrain_parser
    from hra.selfplay import parser as selfplay_parser
    assert selfplay_parser().parse_args(['--config', 'both']).aux_w == 0.3
    assert pretrain_parser().parse_args(['--config', 'both']).aux_w == 0.3


def missing_inputs_are_reported_test():
    """자기 대전의 데우기 신경망(--warm)과 따라 하기 자료(--demos): 직접 준 파일이 없으면 오류이고, 기본 경로에 없으면
    경고를 내고 없이 간다(데우기 없음은 무작위 초기값, 자료 없음은 여백 손실 없음). 둘 다 말없이 넘어가지 않는다."""
    import os
    import tempfile
    from hra.selfplay import inputs
    root = tempfile.mkdtemp()
    try:
        inputs('none', os.path.join(root, 'no.pt'), None, root)
        assert False, '없는 파일을 직접 줬는데 넘어갔다'
    except FileNotFoundError:
        pass
    warm, demos, warnings = inputs('none', None, None, root)
    assert warm is None and demos is None and len(warnings) == 2
    os.makedirs(os.path.join(root, 'checkpoints'))
    open(os.path.join(root, 'checkpoints', 'plan_warm_none.pt'), 'wb').close()
    warm, demos, warnings = inputs('none', None, None, root)
    assert warm == os.path.join(root, 'checkpoints', 'plan_warm_none.pt') and demos is None and len(warnings) == 1


def greedy_planner_pins_one_torch_thread_test():
    """평가 계획기는 일꾼 안에서 torch 스레드를 하나로 둔다(일꾼 7개가 저마다 스레드 여덟을 돌리면 서로 기다리느라 느려진다.
    자기 대전 일꾼과 같다)."""
    import os
    import tempfile
    import torch
    from hra.evaluate import greedy_planner
    from hra.plan_net import PlanNet, save, weights
    torch.set_num_threads(2)
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(PlanNet(), path, weights('none', 0.3))
    greedy_planner(path)
    assert torch.get_num_threads() == 1


def pruning_policy_files_survives_an_open_file_test():
    """일꾼이 아직 읽고 있는 정책 파일은 지우지 못해도(Windows PermissionError) 본체가 죽지 않고 나머지를 지운다."""
    import os
    import tempfile
    from hra.selfplay import prune_policies
    d = tempfile.mkdtemp()
    paths = []
    for i in range(7):
        p = os.path.join(d, f'x_policy_v0_{i}.pt')
        open(p, 'wb').write(b'x')
        os.utime(p, (1000 + i, 1000 + i))
        paths.append(p)
    with open(paths[0], 'rb'):
        prune_policies(d, 'x', 5)
    remaining = os.listdir(d)
    assert os.path.basename(paths[1]) not in remaining and all(os.path.basename(p) in remaining for p in paths[2:])


def finished_run_is_not_restarted_test():
    """끝난 실행(저장된 판 수가 목표와 같음)에 같은 명령을 다시 내리면 바로 돌려주고 정책 파일을 새로 쓰지 않는다."""
    import os
    import tempfile
    import torch
    from hra.plan_net import PlanNet
    from hra.selfplay import train
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'checkpoints'))
    net = PlanNet()
    opt = torch.optim.Adam(net.parameters())
    torch.save({'net': net.state_dict(), 'target': net.state_dict(), 'opt': opt.state_dict(), 'games': 5, 'best': 0.1,
                'updates': 40}, os.path.join(root, 'checkpoints', 'plan_none_s9.pt'))
    assert train('none', 0.3, seed=9, games=5, jobs=1, root=root) == {'games': 5, 'best': 0.1}
    assert not [f for f in os.listdir(os.path.join(root, 'checkpoints')) if 'policy' in f]


def margin_weight_fades_to_zero_by_margin_until_test():
    """여백 손실 가중치(여백 떼기 시험): 줄이는 판 수 N을 주면 0판에서 1, N/2판에서 0.5, N판부터 0. 주지 않으면 늘 1
    (여섯 실행과 같은 학습 규칙)."""
    from hra.selfplay import margin_weight
    assert margin_weight(0, 1000) == 1.0
    assert margin_weight(500, 1000) == 0.5
    assert margin_weight(1000, 1000) == 0.0
    assert margin_weight(1500, 1000) == 0.0
    assert margin_weight(7000, None) == 1.0


def cli_margin_until_reaches_train_test():
    """--margin-until은 기본이 없음(여백 손실을 끝까지 건다)이고, 주면 그 판 수가 그대로 train까지 간다."""
    import sys
    import hra.selfplay as sp
    got, real = {}, sp.train
    sp.train = lambda *a, **k: got.update(k) or {'games': 0, 'best': None}
    try:
        sys.argv = ['selfplay', '--config', 'none', '--games', '0', '--jobs', '1']
        sp.main()
        assert got['margin_until'] is None
        sys.argv += ['--margin-until', '1000']
        sp.main()
        assert got['margin_until'] == 1000
    finally:
        sp.train = real


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
