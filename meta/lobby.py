"""
10.24 메타 덱을 풀게임에서 붙인다.

한 판에 기본 봇 8명이 tftactics 보드 27개 중 서로 다른 덱을 하나씩 맡는다. 봇은 11라운드에 그 덱을 목표로 정하고
(기본 봇의 decide_comp), 그때부터 덱을 따라가는 정책(DeckPolicy)으로 사고·팔고·레벨·리롤하며, 라운드마다 덱의 추천
아이템을 받는다(hand_out_items). 덱별 평균 등수를 낸다. 고정 보드 대전(meta.pit)과 달리 경제, 유닛 겹침, 레벨, 별,
선택받은 자를 봇이 게임 안에서 겪는다.

실행: python -m meta.lobby --games 200 --jobs 7 --out results/lobby_1024.json
"""
import argparse
import json
import os
import random
import statistics
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import Simulator.config as sim_config
from Simulator import default_agent_stats
from Simulator.item_stats import basic_items, item_builds, trait_items
from Simulator.observation.token.basic_observation import ObservationToken
from Simulator.stats import BASE_CHAMPION_LIST, COST, round_stage
from Simulator.tft_simulator import TFTConfig, parallel_env
from Simulator.utils import x_y_to_1d_coord
from fullgame.board_stars import quiet
from meta.decks_1024 import classify, trait_counts
from meta.pit import BUNNY_1024B, average, chosen_of, load_boards

try:
    import utils
except ImportError:
    from Simulator import utils

N_PLAYERS = config.NUM_PLAYERS
BOARDS = load_boards()
FIRST_DECK = len(default_agent_stats.TEAM_COMPS)  # 기본 봇 덱 목록 뒤에 보드 27개를 붙인다

# 나눠 주기에서 건드리지 않는 아이템: 주걱과 주걱으로 만든 것(특성 아이템, 자연의 힘), 도적의 장갑.
# 소모품(복제기, 제거기, 재련기, 케인 아이템)은 basic_items·item_builds에 없어서 저절로 빠진다.
UNTOUCHED = {'spatula', 'thieves_gloves', 'force_of_nature'} | set(trait_items.values())


def _worth(item):
    if item in UNTOUCHED:
        return 0
    return 1 if item in basic_items else 2 if item in item_builds else 0


def _components(item):
    return [item] if item in basic_items else list(item_builds[item])


def hand_out_items(player, deck_items):
    """덱 추천 아이템을 캐리에게 준다(11라운드부터 라운드마다). 봇이 가진 일반 아이템을 조각 1, 완성 2로 세어 그 절반만큼
    추천 아이템을 앞에서부터 준다. 캐리가 없는 아이템과 남는 몫은 조각으로 아이템 칸에 남겨 다음 라운드에 다시 센다."""
    units = [u for row in player.board for u in row if u] + [u for u in player.bench if u]
    taken = []
    for u in units:
        taken += [i for i in u.items if _worth(i)]
        u.items = [i for i in u.items if not _worth(i)]
    for k, item in enumerate(player.item_bench):
        if item and _worth(item):
            taken.append(item)
            player.item_bench[k] = None
    worth = sum(map(_worth, taken))
    wanted = [(i, c) for c, held in deck_items.items() for i in held if _worth(i) == 2][:worth // 2]
    spare = []
    for item, carrier in wanted:
        holders = [u for u in units if u.name == carrier and len(u.items) < 3 and 'thieves_gloves' not in u.items]
        if holders:
            max(holders, key=lambda u: u.stars).items.append(item)
        else:
            spare += _components(item)
    spare += [c for i in taken for c in _components(i)][:worth - 2 * len(wanted)]
    for c in spare:
        if None not in player.item_bench:
            break  # ponytail: 아이템 칸(10칸)이 차면 남는 조각은 버린다. 드물어서 세지 않는다
        player.item_bench[player.item_bench.index(None)] = c


def completion(player, board):
    """마지막 보드에 덱 유닛이 몇 할 있었는지."""
    names = {u.name for row in player.board for u in row if u}
    target = set(board['units'])
    return len(names & target) / len(target)


def carriers(board):
    """덱의 캐리: 추천 아이템을 가장 많이 드는 유닛들(보드마다 1~2명)."""
    most = max(len(held) for held in board['items'].values())
    return [u for u, held in board['items'].items() if len(held) == most]


def board_record(player):
    """보드 기록: 레벨, 유닛(이름, 비용, 별, 완성 아이템 수), 켜진 특성 인원, 선택받은 자 특성, 들고 있는 아이템 수.
    completed_all·components_all은 보드·벤치 유닛과 아이템 칸 전부의 완성 아이템·조각 수다(주걱·소모품 제외)."""
    units = [u for row in player.board for u in row if u and u.name in BASE_CHAMPION_LIST]
    everyone = [u for row in player.board for u in row if u] + [u for u in player.bench if u]
    held = [i for u in everyone for i in u.items] + [i for i in player.item_bench if i]
    return {'level': player.level,
            'units': [[u.name, u.cost, u.stars, sum(i in item_builds for i in u.items)] for u in units],
            'traits': {t: n for t, n in player.team_composition.items() if player.team_tiers.get(t, 0) > 0},
            'chosen': player.chosen or None,
            'completed_all': sum(_worth(i) == 2 for i in held), 'components_all': sum(_worth(i) == 1 for i in held)}


def finish_order(ended, players, start_hp, rng):
    """같은 걸음에 끝난 에이전트를 낮은 등수부터 줄 세운다. 같은 라운드 탈락자는 라운드 전 체력(start_hp)이 적은 쪽이
    아래이고(공식 10.14 노트: 그 라운드 전 체력이 많은 순서), 체력이 남은 사람(우승자)은 맨 위다. 라운드 전 체력이 같으면
    rng로 섞은 순서를 따른다. 예전에는 이름순이라 마지막 두 명 중 번호가 큰 쪽이 1등이 됐다."""
    ended = list(ended)
    rng.shuffle(ended)
    return sorted(ended, key=lambda a: (players[a].health > 0, start_hp.get(a, 0)))


def carry_share(player, board):
    """목표 덱 캐리 중 보드에서 완성 아이템을 하나 이상 든 비율(보드에 없는 캐리는 못 든 것으로 센다).
    목표 덱이 없으면 None."""
    if board is None:
        return None
    holding = {u.name for row in player.board for u in row if u and any(_worth(i) == 2 for i in u.items)}
    names = carriers(board)
    return sum(c in holding for c in names) / len(names)


class DeckPolicy:
    """기본 봇에 얹어 목표 덱을 따라가게 하는 정책(11라운드에 기본 봇이 덱을 정한 뒤부터). fullgame/policy.py의
    RerollPolicy처럼 할 일이 있는 단계만 발동해서, 할 일이 없는 턴에는 레벨·리롤 판단까지 간다.
    기본 봇은 54골드가 넘는 몫만, 그것도 레벨 8에서만 리롤해서 덱을 거의 완성하지 못했다(살아 있는 봇의 덱 완성도가
    11라운드 9%, 가장 높을 때 약 30%)."""

    chosen_any_trait = False  # True면 덱 유닛의 선택받은 자를 특성과 상관없이 산다(사람 봇)

    def __init__(self, agent, board):
        self.agent = agent
        self.moves = {}  # 라운드별 자리 맞추기 횟수. 자리가 안 맞는 보드에서 같은 이동을 되풀이하지 않게 한다
        self.set_board(board)

    def set_board(self, board):
        """목표 덱을 정한다. 사람 봇은 덱을 갈아탈 때 다시 부른다."""
        self.board = board
        self.units = set(board['units'])
        self.trait = chosen_of(board)[1]
        self.slow = board['slow']

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        return (self.fill(player, shop, mask) or self.sell(player) or self.buy(player, shop, mask)
                or self.swap(player) or self.reposition(player, game_round) or self.macro(player, game_round))

    def fill(self, player, shop, mask):
        """보드 빈자리 채우기(기본 봇 규칙)."""
        placement = self.agent.max_unit_check(player, shop, mask)
        return None if placement == ' ' else placement

    def sell(self, player):
        """벤치가 꽉 차면 덱 밖 유닛부터 판다."""
        if not player.bench_full():
            return None
        for i, u in enumerate(player.bench):
            if u.name not in self.units:
                return '4_' + str(28 + i)
        return self.agent.sell_bench_full(player)

    def buy(self, player, shop, mask):
        """덱 유닛과 덱 특성의 선택받은 자를 산다."""
        for i, unit in enumerate(shop):
            if not mask[47 + i][0]:
                continue
            if unit.endswith('_c'):  # 선택받은 자 "이름_특성_c". 값은 1성의 세 배(pool_stats.buy_cost)
                name, trait = unit.split('_')[:2]
                if (name in self.units and (self.chosen_any_trait or trait == self.trait) and not player.chosen
                        and 3 * COST[name] <= player.gold):
                    return '3_' + str(i)
            elif unit in self.units and COST[unit] <= player.gold:
                return '3_' + str(i)
        return None

    def swap(self, player):
        """벤치의 덱 유닛을 보드의 덱 밖 유닛과 바꾼다. 보드에 이미 있는 유닛의 사본은 올리지 않는다."""
        on_board = {u.name for row in player.board for u in row if u}
        for i, u in enumerate(player.bench):
            if u and u.name in self.units and u.name not in on_board:
                for x, row in enumerate(player.board):
                    for y, b in enumerate(row):
                        if b and b.name in BASE_CHAMPION_LIST and b.name not in self.units:
                            return f'5_{x_y_to_1d_coord(x, y)}_{28 + i}'
        return None

    def reposition(self, player, game_round):
        """앞줄·뒷줄 자리 맞추기(기본 봇 규칙). 한 라운드에 8번까지."""
        if self.moves.get(game_round, 0) >= 8:
            return None
        for x, row in enumerate(player.board):
            for y, b in enumerate(row):
                move = b and self.agent.check_unit_location(player, x, y, b.name)
                if move:
                    self.moves[game_round] = self.moves.get(game_round, 0) + 1
                    return move
        return None

    def macro(self, player, game_round):
        """레벨·리롤. 느린 리롤 덱은 레벨 6에서 50골드 넘는 몫으로 리롤하고 5단계부터 8로 간다. 보통 덱은 4단계에 7,
        4단계 후반(18번째 칸부터)에 8로 가서 20골드를 남기고 리롤한다."""
        stage = round_stage(game_round)
        if self.slow:
            target, floor = (5 if stage <= 2 else 6 if stage <= 4 else 8), 50
        else:
            target, floor = (5 if stage <= 2 else 6 if stage == 3 else 7 if game_round < 18 else 8), 20
        if player.level < target and player.gold >= 4:
            return '1'
        if player.level >= target and (self.slow or player.level >= 8) and player.gold >= floor + 2:
            return '2'
        return '0'


def attach(player, board):
    """플레이어의 기본 봇에 DeckPolicy를 얹는다. 기본 봇이 11라운드에 덱 밖 유닛과 다른 특성 선택받은 자를 정리하는
    단계(decide_comp)까지는 기본 봇이 하고, 그 뒤부터 이 정책이 한다."""
    agent = player.default_agent
    policy = DeckPolicy(agent, board)
    original = agent.policy

    def patched(p, shop, game_round, mask):
        if game_round < 11 or agent.round_11_clean_up:
            return original(p, shop, game_round, mask)
        return policy(p, shop, game_round, mask)

    agent.policy = patched
    return policy


def _register():
    """기본 봇 덱 목록에 보드 27개(유닛, 선택받은 자 특성)를 붙인다. 프로세스마다 한 번."""
    if len(default_agent_stats.TEAM_COMPS) == FIRST_DECK:
        for b in BOARDS:
            default_agent_stats.TEAM_COMPS.append(list(b['units']))
            default_agent_stats.TEAM_COMP_TRAITS.append(chosen_of(b)[1])


def play(game, bot='deck', knobs=None):
    """한 판. game = (시드, 덱 번호 8개). bot은 'default'(덱을 정해 주지 않은 기본 봇), 'deck'(덱 봇),
    'human'(사람 봇, meta/human_bot.py). knobs는 사람 봇 손잡이 값을 바꿀 때 쓴다(meta.play_stats --knob).
    돌려주는 값: {'curve': [(칸, 레벨, 골드, 체력, 초반 전략, 느린 리롤 덱인가), ...] 살아 있는 봇이 그 칸에서 처음
                 움직일 때,
                 'players': [{'deck', 'place', 'complete', 'complete21', 'carry21', 'mode', 'switches', 'board'}, ...]}
    탈락 때 완성도(complete)는 일찍 죽은 덱일수록 낮게 나와 등수와 엉킨다. 그래서 5단계 시작(21번째 칸) 때 살아 있던
    봇의 완성도(complete21)와 캐리 아이템 비율(carry21)을 따로 잰다(그 전에 탈락하면 None). board는 탈락하거나 끝날
    때의 board_record다. 덱 번호는 덱 봇의 목표 덱이다(사람 봇은 스스로 고른다)."""
    seed, decks = game
    sim_config.LOGMESSAGES = False  # 켜 두면 실행한 곳에 log.txt가 생긴다
    if bot == 'deck':
        _register()
    random.seed(seed)
    np.random.seed(seed)
    with quiet():
        env = parallel_env(TFTConfig(observation_class=ObservationToken,
                                     max_actions_per_round=config.ACTIONS_PER_TURN))
        obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
        deck_of = dict(zip(info, decks))
        players = {a: info[a]['player'] for a in info}
        policies = {}
        if bot == 'deck':
            for a, deck in deck_of.items():
                players[a].default_agent.comp_number = FIRST_DECK + deck
                policies[a] = attach(players[a], BOARDS[deck])
        elif bot == 'human':
            from meta.human_bot import attach_human  # human_bot이 이 파일을 불러서, 여기서 늦게 부른다
            for i, (a, deck) in enumerate(deck_of.items()):
                others = [players[o] for o in players if o != a]
                policies[a] = attach_human(players[a], others, random.Random(seed * N_PLAYERS + i), knobs)
        mode = lambda a: getattr(policies.get(a), 'mode', None)
        curve, seen, handed, placement, done, mid, carry, boards = [], set(), {}, {}, {}, {}, {}, {}
        start_hp, ties = {}, random.Random(seed)  # 라운드 시작 체력, 등수 동점 가르기(게임 난수와 따로)
        rank, guard = N_PLAYERS, 0
        # 종료 신호를 놓치면 루프가 안 끝난다(fullgame/ab_test.py와 같은 상한). 상한에 걸린 판은 아래에서 등수를 메운다.
        while obs and guard < 5000:
            guard += 1
            alive = list(obs)
            actions = []
            for a in alive:
                game_round, p = info[a]['game_round'], players[a]
                if (a, game_round) not in seen:
                    seen.add((a, game_round))
                    start_hp[a] = p.health
                    curve.append((game_round, p.level, p.gold, p.health, mode(a), BOARDS[deck_of[a]]['slow']))
                if game_round >= 21 and a not in mid:
                    mid[a] = completion(p, BOARDS[deck_of[a]])
                    carry[a] = carry_share(p, getattr(policies.get(a), 'board', None))
                if bot == 'deck' and game_round >= 11 and handed.get(a) != game_round:
                    hand_out_items(p, BOARDS[deck_of[a]]['items'])
                    handed[a] = game_round
                actions.append(p.default_policy(game_round, info[a]['shop'], obs[a]['action_mask']))
            decoded = utils.decode_action(actions)
            obs, _, terminated, _, info = env.step({a: decoded[i] for i, a in enumerate(alive)})
            ended = [a for a, e in terminated.items() if e and a not in placement]
            for a in finish_order(ended, players, start_hp, ties):
                placement[a], rank = rank, rank - 1
                done[a], boards[a] = completion(players[a], BOARDS[deck_of[a]]), board_record(players[a])
    for a in deck_of:  # 끝까지 terminated가 안 온 플레이어
        if a not in placement:
            placement[a], rank = rank, rank - 1
            done[a], boards[a] = completion(players[a], BOARDS[deck_of[a]]), board_record(players[a])
    return {'curve': curve,
            'players': [{'deck': deck_of[a], 'place': placement[a], 'complete': done[a], 'complete21': mid.get(a),
                         'carry21': carry.get(a), 'mode': mode(a), 'switches': getattr(policies.get(a), 'switches', 0),
                         'board': boards[a]} for a in deck_of]}


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    for r, i in enumerate(order):
        out[i] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=200)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=None, help='판별 기록 JSON 저장 경로')
    args = ap.parse_args()

    rng = random.Random(args.seed)
    games = [(args.seed * 100000 + g, rng.sample(range(len(BOARDS)), N_PLAYERS)) for g in range(args.games)]
    # 시뮬레이터가 집합·사전을 도는 순서가 문자열 해시에 따라 프로세스마다 달라서, 시드가 같아도 판이 달라졌다(200판 두 번에서
    # 1600줄 중 266줄만 같았다). 일꾼 프로세스의 해시를 고정한다. 일꾼은 이 환경 변수를 물려받고 새로 시작한다.
    os.environ['PYTHONHASHSEED'] = str(args.seed)
    with Pool(args.jobs) as workers:
        results = workers.map(play, games, chunksize=1)

    rows = [(g, p['deck'], p['place'], p['complete'], p['complete21'])
            for g, result in enumerate(results) for p in result['players']]
    by_deck = {d: [r for r in rows if r[1] == d] for d in range(len(BOARDS))}
    pit_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 'pit_1024.json')
    fixed = average(json.load(open(pit_path, encoding='utf-8'))['human']) if os.path.exists(pit_path) else {}

    stats = []
    for d, b in enumerate(BOARDS):
        places = [r[2] for r in by_deck[d]]
        if len(places) < 2:  # 판 수가 적으면 한 번도 안 나온 덱이 있다
            continue
        mids = [r[4] for r in by_deck[d] if r[4] is not None]
        pick = chosen_of(b)
        ours = ','.join(classify(b['units'], trait_counts(b['units'], b['items'], pick[1]))) or '-'
        stats.append({'name': b['name'], 'tier': b['tier'], 'bunny': BUNNY_1024B.get(b['name'], '-'), 'ours': ours,
                      'n': len(places), 'place': statistics.mean(places),
                      'se': statistics.stdev(places) / len(places) ** 0.5,
                      'top4': sum(p <= 4 for p in places) / len(places),
                      'complete': statistics.mean(r[3] for r in by_deck[d]),
                      'alive21': len(mids) / len(places), 'complete21': statistics.mean(mids) if mids else None,
                      'fixed': fixed.get(b['name'])})
    stats.sort(key=lambda s: s['place'])

    print(f'\n덱별 풀게임 성적 ({args.games}판, 한 판에 봇 8명이 서로 다른 덱), 평균 등수 순')
    print(f'{"보드":22} {"tftactics":>9} {"10.24b":>7} {"우리 덱":>16} {"판":>4} {"평균 등수":>10} {"4등 안":>7} '
          f'{"5단계 생존":>8} {"5단계 완성도":>9} {"탈락 때 완성도":>10} {"고정 대전":>8}')
    for s in stats:
        fixed_cell = f'{s["fixed"] * 100:7.1f}%' if s['fixed'] is not None else '       -'
        mid_cell = f'{s["complete21"] * 100:8.0f}%' if s['complete21'] is not None else '        -'
        print(f'{s["name"]:22} {s["tier"]:>9} {s["bunny"]:>7} {s["ours"]:>16} {s["n"]:4d} '
              f'{s["place"]:5.2f}±{s["se"]:.2f} {s["top4"] * 100:6.1f}% {s["alive21"] * 100:9.0f}% {mid_cell} '
              f'{s["complete"] * 100:13.0f}% {fixed_cell}')

    print('\n티어별 평균 등수')
    for label, key in [('tftactics 10.24(핫픽스 전)', 'tier'), ('bunnymuffins 10.24b(핫픽스 뒤)', 'bunny')]:
        for tier in 'SABC':
            members = [s['place'] for s in stats if s[key] == tier]
            if members:
                print(f'  {label} {tier} ({len(members)}개)  {statistics.mean(members):.2f}')
    if all(s['fixed'] is not None for s in stats):
        a, b = _ranks([-s['place'] for s in stats]), _ranks([s['fixed'] for s in stats])
        print(f'\n고정 보드 대전(사람 근사)과의 순위 상관: {np.corrcoef(a, b)[0, 1]:.2f}')
    known = [s for s in stats if s['complete21'] is not None]
    a, b = _ranks([-s['place'] for s in known]), _ranks([s['complete21'] for s in known])
    print(f'5단계 완성도와의 순위 상관: {np.corrcoef(a, b)[0, 1]:.2f}')

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'games': args.games, 'seed': args.seed, 'decks': [b['name'] for b in BOARDS],
                       'rows': rows, 'stats': stats}, f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
