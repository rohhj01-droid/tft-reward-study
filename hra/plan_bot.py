"""
계획 AI의 실행기, 따라 하기 기록기, 판 돌리기(hra/plan_ai_design.md 2·4절).

PlanPolicy  : 사람 봇(meta/human_bot.HumanPolicy)을 물려받아, 2-1부터 라운드마다 한 번 계획기에게 계획(덱, 레벨, 남길
              골드)을 받아 실행한다. 사기·팔기·바꾸기·배치·아이템은 사람 봇 규칙 그대로 계획의 목표 덱을 따르므로,
              한 계획이 그 라운드의 여러 행동(리롤, 사기, 팔기)으로 이뤄진다.
RuleRecorder: 규칙 사람 봇을 그대로 두고, 라운드마다 규칙이 한 일을 계획 번호(따라 하기 정답)로 적는다.
둘 다 라운드마다 경험 (상태, 가림, 계획, 보상 5갈래, 다음 상태, 끝, 다음 가림)을 쌓는다(Recorder).
play()      : 자리 8개에 정책을 붙여 한 판을 돌린다(meta/lobby.play와 같은 틀).
"""
import os
import random
from math import floor
from multiprocessing import Pool

import numpy as np

import config
import Simulator.config as sim_config
from Simulator.observation.token.basic_observation import ObservationToken
from Simulator.player import Player
from Simulator.tft_simulator import TFTConfig, parallel_env
from fullgame.board_stars import quiet
from hra.plan_state import MASK_SIZE, SLICES, STATE_SIZE, active_tiers, board_units, decode, masks, rule_label, state
from meta.human_bot import HumanPolicy
from meta.human_macro import action
from meta.lobby import N_PLAYERS, board_record, finish_order

try:
    import utils
except ImportError:
    from Simulator import utils

FIRST_ROUND = 3   # 2-1. 그 전(1단계)은 규칙이 맡는다
MAX_STEPS = 5000  # meta/lobby.play와 같은 걸음 상한

# 이자 보상(설계 4절): 시뮬레이터는 라운드 시작 수입(Player.gold_income)에서 그때 골드로 이자를 준다. 준 이자를 남겨 둔다.
_gold_income = Player.gold_income


def _gold_income_recording(self, t_round):
    self.last_interest = min(floor(self.gold / 10), 5)
    return _gold_income(self, t_round)


Player.gold_income = _gold_income_recording


def pinned_pool(jobs, **kw):
    """일꾼 풀. 시뮬레이터가 집합·사전을 도는 순서가 문자열 해시에 따라 프로세스마다 달라서(meta/lobby와 같은 까닭), 일꾼의
    해시 시드를 고정한다. 일꾼은 이 환경 변수를 물려받고 새로 시작한다. 값은 늘 0이라 이어 하기 때도 같다."""
    os.environ['PYTHONHASHSEED'] = '0'
    return Pool(jobs, **kw)


def legal(plan, mask):
    """계획 세 갈래가 모두 가리지 않은 칸인가."""
    return all(mask[lo + a] for (lo, _), a in zip(SLICES, plan))


class Recorder:
    """라운드마다 경험을 쌓는다. 라운드 r의 보상은 라운드 r+1의 첫 판단 때 센다(그때 보드가 라운드 r에 싸운 보드이고,
    라운드 r+1 시작 수입에서 라운드 r 끝 골드로 이자를 받는다). 물려받는 쪽이 current_plan(player)을 정한다."""

    def start_recording(self):
        self.transitions, self.rounds, self.tokens = [], [], []
        self.pending = None   # (상태, 가림, 계획 또는 None, 라운드 시작 체력, 라운드)
        self.finished = False

    def close(self, player, plan, next_state, next_mask, done, place=None):
        """미뤄 둔 판단 하나를 경험으로 닫는다. 정답이 가린 칸이면 버린다."""
        if self.pending is None:
            return
        s, m, _, hp0, game_round = self.pending
        self.pending = None
        if plan is None or not legal(plan, m):
            return
        units = board_units(player)
        r = np.array([0.0 if place is None else 1 - 2 * (place - 1) / (N_PLAYERS - 1),
                      -min((hp0 - max(player.health, 0)) / 20, 1.0),
                      0.0 if done else getattr(player, 'last_interest', 0) / 5,
                      active_tiers(units) / 11,
                      len(units) / 9], dtype=np.float32)
        self.transitions.append((s, m, np.array(plan, dtype=np.int64), r, next_state, done, next_mask))
        self.rounds.append(game_round)

    def finish(self, player, place):
        """탈락하거나 판이 끝났을 때 한 번. 마지막 판단에 등수 보상과 끝 표시를 붙인다."""
        if self.finished:
            return
        self.finished = True
        self.close(player, self.current_plan(player), np.zeros(STATE_SIZE, np.float32),
                   np.ones(MASK_SIZE, bool), True, place)


class PlanPolicy(Recorder, HumanPolicy):
    """계획기를 따르는 사람 봇. planner(상태, 가림) -> (덱, 레벨, 남길 골드) 번호."""

    def __init__(self, agent, others, rng, planner):
        HumanPolicy.__init__(self, agent, None, others, rng)
        self.planner = planner
        self.target, self.floor, self.deck_age, self.plan_round = None, None, 0, None
        self.start_recording()

    def __call__(self, player, shop, game_round, mask):
        if game_round >= FIRST_ROUND and game_round != self.plan_round:
            self.plan_round = game_round
            self.begin_round(player, game_round)
        token = HumanPolicy.__call__(self, player, shop, game_round, mask)
        self.tokens.append((game_round, token))
        return token

    def current_plan(self, player):
        return self.pending[2] if self.pending else None

    def begin_round(self, player, game_round):
        if self.board is not None:
            self.deck_age += 1
        s, m = state(player, self.others, self.board, self.deck_age, game_round), masks(player.level, self.board)
        self.close(player, self.current_plan(player), s, m, False)
        plan = tuple(int(i) for i in self.planner(s, m))
        assert legal(plan, m), (plan, game_round)
        deck, self.target, self.floor = decode(plan, player.level, self.board)
        if deck is not self.board:
            if self.board is not None:
                self.switches += 1
            self.set_board(deck)
            self.deck_age = 0
        self.pending = (s, m, plan, player.health, game_round)

    def pick_deck(self, player, game_round):
        """덱은 계획이 고른다(begin_round)."""

    def macro(self, player, game_round):
        if self.target is None:  # 2-1 전(1단계)은 규칙 그대로
            return HumanPolicy.macro(self, player, game_round)
        return action(player.gold, player.level, self.target, self.floor, False)


class RuleRecorder(Recorder, HumanPolicy):
    """규칙 사람 봇을 그대로 두고 라운드마다 한 일을 계획 번호로 적는다(따라 하기 자료, 설계 2절). 덱은 그 라운드 첫 행동의
    덱 고르기 결과, 레벨은 그 라운드에 규칙이 낸 가장 높은 목표 레벨 - 시작 레벨(0~2), 남길 골드는 그 라운드에 규칙이 낸
    가장 낮은 값(리롤 판단이 없었으면 리롤 안 함)이다. 상태는 덱 고르기 전에 센다(AI가 판단하는 자리와 같다)."""

    def __init__(self, agent, others, rng):
        HumanPolicy.__init__(self, agent, None, others, rng)
        self.deck_age, self.plan_round = 0, None
        self.old_deck, self.level_start, self.best_target, self.min_floor = None, 0, 0, None
        self.start_recording()

    def __call__(self, player, shop, game_round, mask):
        if game_round >= FIRST_ROUND and game_round != self.plan_round:
            self.plan_round = game_round
            self.begin_round(player, game_round)
        token = HumanPolicy.__call__(self, player, shop, game_round, mask)  # 라운드 첫 호출이면 여기서 규칙이 덱을 고른다
        self.tokens.append((game_round, token))
        return token

    def current_plan(self, player):
        if self.pending is None:
            return None
        return rule_label(self.old_deck, self.board, self.level_start, self.best_target, self.min_floor)

    def begin_round(self, player, game_round):
        if self.board is not None:
            self.deck_age += 1
        s, m = state(player, self.others, self.board, self.deck_age, game_round), masks(player.level, self.board)
        self.close(player, self.current_plan(player), s, m, False)
        self.old_deck, self.level_start, self.best_target, self.min_floor = self.board, player.level, player.level, None
        self.pending = (s, m, None, player.health, game_round)

    def set_board(self, board):
        if board is not getattr(self, 'board', None):
            self.deck_age = 0
        HumanPolicy.set_board(self, board)

    def macro(self, player, game_round):
        target, floor_, exp_first = self.macro_plan(player, game_round)
        if self.pending is not None:
            eff = 9 if exp_first and player.level < 9 and player.gold >= 54 else target
            self.best_target = max(self.best_target, eff)
            if floor_ is not None:
                self.min_floor = floor_ if self.min_floor is None else min(self.min_floor, floor_)
        return action(player.gold, player.level, target, floor_, exp_first)


def make_policy(seat, player, others, rng):
    """seat: 'rule'(규칙 사람 봇), 'record'(규칙 + 기록), 또는 계획기(부를 수 있는 것)."""
    if seat == 'rule':
        policy = HumanPolicy(player.default_agent, None, others, rng)
    elif seat == 'record':
        policy = RuleRecorder(player.default_agent, others, rng)
    else:
        policy = PlanPolicy(player.default_agent, others, rng, seat)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy


def play(seed, seats, trace=False):
    """한 판. seats는 자리 8개의 정책(make_policy). 돌려주는 값:
    {'seats': [{'place', 'deck', 'switches', 'board', 'transitions', ('rounds', 'tokens': trace일 때)}], 'capped'}.
    transitions는 기록하는 정책(계획기, 'record')만 채운다."""
    sim_config.LOGMESSAGES = False
    random.seed(seed)
    np.random.seed(seed)
    with quiet():
        env = parallel_env(TFTConfig(observation_class=ObservationToken,
                                     max_actions_per_round=config.ACTIONS_PER_TURN))
        obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
        agents = list(info)
        players = {a: info[a]['player'] for a in agents}
        policies = {a: make_policy(seats[i], players[a], [players[o] for o in agents if o != a],
                                   random.Random(seed * N_PLAYERS + i)) for i, a in enumerate(agents)}
        placement, start_hp, seen, ties, rank, steps = {}, {}, set(), random.Random(seed), N_PLAYERS, 0
        while obs and steps < MAX_STEPS:
            steps += 1
            alive = list(obs)
            actions = []
            for a in alive:
                game_round, p = info[a]['game_round'], players[a]
                if (a, game_round) not in seen:
                    seen.add((a, game_round))
                    start_hp[a] = p.health
                actions.append(p.default_policy(game_round, info[a]['shop'], obs[a]['action_mask']))
            decoded = utils.decode_action(actions)
            obs, _, terminated, _, info = env.step({a: decoded[i] for i, a in enumerate(alive)})
            ended = [a for a, e in terminated.items() if e and a not in placement]
            for a in finish_order(ended, players, start_hp, ties):
                placement[a], rank = rank, rank - 1
        for a in agents:  # 걸음 상한에 걸려 끝까지 terminated가 안 온 플레이어
            if a not in placement:
                placement[a], rank = rank, rank - 1
    out = []
    for a in agents:
        pol = policies[a]
        if isinstance(pol, Recorder):
            pol.finish(players[a], placement[a])
        row = {'place': placement[a], 'deck': pol.board['name'] if pol.board else None, 'switches': pol.switches,
               'board': board_record(players[a]), 'transitions': getattr(pol, 'transitions', [])}
        if trace:
            row['rounds'], row['tokens'] = getattr(pol, 'rounds', []), getattr(pol, 'tokens', [])
        out.append(row)
    return {'seats': out, 'capped': steps >= MAX_STEPS}


def safe_play(seed, seats, trace=False):
    """play()와 같지만 시뮬레이터나 계획기가 판 중간에 예외를 내면 그 판을 버리고 (None, 오류 문자열)을 돌려준다
    (설계 8절). 걸음 상한에 걸린 판도 버린다(살아남은 자리의 등수가 자리 순서라 쓸 수 없다, (None, 'capped')).
    정상이면 (결과, None)."""
    try:
        out = play(seed, seats, trace)
    except Exception as e:  # 어느 예외든 그 판만 버리고 부른 쪽이 센다
        return None, f'{type(e).__name__}: {e}'
    if out['capped']:
        return None, 'capped'
    return out, None
