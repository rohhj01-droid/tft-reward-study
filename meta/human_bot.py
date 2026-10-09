"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

행동할 때마다 할 일이 있는 첫 단계만 움직인다: 보드 채우기 → 벤치 정리 → 다른 특성 선택받은 자 팔기 → 사기 → 교체
→ 캐리 아이템 옮기기 → 아이템 → 자리 맞추기 → 레벨·리롤. 라운드의 첫 행동 때 초반 전략을 정하거나 바꾸고, 2-1부터
목표 덱을 고르거나 갈아탄다. 아이템은 meta/human_items.py, 레벨·리롤은 meta/human_macro.py, 덱 고르기는
meta/human_deck.py에 있고, 자리 맞추기는 구석 배치(analysis.battle.corner_positions)다.
"""
from analysis.battle import corner_positions
from Simulator.stats import COST, round_stage
from Simulator.utils import x_y_to_1d_coord
from meta.human_deck import SPREAD, choose, copies, held_items, score, scout, units_of
from meta.human_items import item_action, transfer_action
from meta.human_macro import action, carry3, early_mode, plan, stable, stay_level
from meta.lobby import BOARDS, DeckPolicy

KNOBS = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20,
         'chosen_bonus': 10, 'item_point': 3, 'tier_weight': 3, 'contest': 1, 'temperature': 3,
         'switch': {2: 0.1, 3: 0.3, 4: 0.6}, 'early_spread': 6}


class HumanPolicy(DeckPolicy):
    # 덱에 들어가는 유닛이면 특성이 달라도 선택받은 자를 산다(실제 1등의 52%가 그랬다, 유저 결정 2026-10-09)
    chosen_any_trait = True

    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.rebuilt_at = None  # 연패형이 보드를 세운 라운드(그 라운드에만 리롤한다)
        self.choose_decks = board is None
        self.set_board(board)

    def set_board(self, board):
        if board is None:
            self.board, self.units, self.trait, self.slow = None, set(), None, False
        else:
            super().set_board(board)

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        if game_round != self.last_round:
            self.last_round = game_round
            self.update_mode(player, game_round)
            if self.choose_decks and game_round >= 3:
                self.pick_deck(player, game_round)
        return (self.fill(player, shop, mask) or self.sell(player) or self.sell_chosen(player)
                or self.buy(player, shop, mask) or self.swap(player) or transfer_action(player, self.board)
                or item_action(player, self.board, self.mode or 'win', game_round, mask)
                or self.reposition(player, game_round) or self.macro(player, game_round))

    def pick_deck(self, player, game_round):
        """라운드 첫 행동 때 후보 27개의 점수를 매겨 목표 덱을 고르거나 갈아탄다(설계 2절)."""
        completed, components = held_items(player)
        mine, others = copies(units_of(player)), scout(self.others)
        scores = [score(b, mine, player.chosen or None, completed, components, others, self.knobs) for b in BOARDS]
        current = BOARDS.index(self.board) if self.board else None
        new = choose(scores, current, round_stage(game_round), self.rng, self.knobs)
        if new != current:
            if current is not None:
                self.switches += 1
            self.set_board(BOARDS[new])

    def sell(self, player):
        if self.board is None:  # 목표 덱이 없으면 기본 봇 규칙(짝 아닌 1성부터)
            return self.agent.sell_bench_full(player) if player.bench_full() else None
        return super().sell(player)

    def sell_chosen(self, player):
        """덱을 갈아타서 들고 있는 선택받은 자 유닛이 새 목표 덱에 없으면 판다. 특성이 덱 특성과 달라도 덱 유닛이면
        둔다(유저 결정 2026-10-09). 시뮬레이터는 선택받은 자를 들고 있으면 상점에 다른 선택받은 자를 내지 않는다
        (pool.sample)."""
        if not (self.choose_decks and self.board and player.chosen):
            return None
        for x, row in enumerate(player.board):
            for y, u in enumerate(row):
                if u and u.chosen and u.name not in self.units:
                    return f'4_{x_y_to_1d_coord(x, y)}'
        for i, u in enumerate(player.bench):
            if u and u.chosen and u.name not in self.units:
                return f'4_{28 + i}'
        return None

    def buy(self, player, shop, mask):
        """목표 덱이 없으면 짝·두루 들어가는 유닛·처음 본 선택받은 자를, 있으면 덱 유닛·덱 유닛의 선택받은 자(특성
        상관없이)를 사고 4-1 전까지는 보드 유닛의 짝도 산다."""
        if self.board is None:
            owned = {u.name for u in units_of(player)}
            for i, unit in enumerate(shop):
                if not mask[47 + i][0]:
                    continue
                if unit.endswith('_c'):
                    name = unit.split('_')[0]
                    if not player.chosen and COST[name] > 1 and 3 * COST[name] <= player.gold:
                        return '3_' + str(i)
                elif (unit in owned or SPREAD[unit] >= self.knobs['early_spread']) and COST[unit] <= player.gold:
                    return '3_' + str(i)
            return None
        act = super().buy(player, shop, mask)
        if act or (self.last_round or 0) >= 15:
            return act
        on_board = {u.name for row in player.board for u in row if u}
        for i, unit in enumerate(shop):
            if mask[47 + i][0] and not unit.endswith('_c') and unit in on_board and COST[unit] <= player.gold:
                return '3_' + str(i)
        return None

    def update_mode(self, player, game_round):
        """2-3에 첫 대전 성적으로 초반 전략을 고르고, 연승형이 2~3단계에 두 번 연달아 지면 연패형으로 바꾼다.
        연패형은 3-2가 되거나 체력이 손잡이 값(50) 아래로 내려가면 보드를 세운다(rebuilt, 그 라운드는 rebuilt_at)."""
        if game_round < 5:
            return
        if self.mode is None:
            self.mode = early_mode(player, self.knobs)
        if self.mode == 'win' and game_round < 15 and player.loss_streak >= 2:
            self.mode, self.rebuilt = 'lose', False
        if self.mode == 'lose' and not self.rebuilt and (game_round >= 10 or player.health < self.knobs['lose_hp']):
            self.rebuilt, self.rebuilt_at = True, game_round

    def reposition(self, player, game_round):
        """자리 맞추기(설계 1절 7번): 원거리는 뒷줄 구석부터 아이템 많은 순, 근접은 앞줄 가운데부터
        (analysis.battle.corner_positions). 한 라운드에 8번까지. 자리가 다른 첫 유닛을 제자리로 옮긴다(그 칸에 유닛이
        있으면 맞바꾼다). 유닛 순서를 이름순으로 고정해서, 옮긴 뒤 아이템 수가 같은 유닛끼리 자리를 계속 바꾸지 않게 한다."""
        if self.moves.get(game_round, 0) >= 8:
            return None
        units = sorted(((x, y, u) for x, row in enumerate(player.board) for y, u in enumerate(row)
                        if u and u.name != 'sandguard'), key=lambda t: (t[2].name, -t[2].stars))
        for (x, y, _), (tx, ty) in zip(units, corner_positions([u for _, _, u in units])):
            target = player.board[tx][ty]
            if (x, y) != (tx, ty) and not (target and target.name == 'sandguard'):
                self.moves[game_round] = self.moves.get(game_round, 0) + 1
                return f'5_{x_y_to_1d_coord(x, y)}_{x_y_to_1d_coord(tx, ty)}'
        return None

    def macro(self, player, game_round):
        board = self.board
        stay = stay_level(board)
        done3 = stay is not None and carry3(player, board)
        steady = bool(board) and stable(player, board)
        target, floor = plan(game_round, player.level, player.health, self.mode or 'win', self.rebuilt, stay,
                             done3, steady, self.knobs, rebuild_now=self.rebuilt_at == game_round)
        # 5단계 레벨 8이면 안정 여부와 상관없이 50 넘는 몫으로 9로 간다(유저 결정 2026-10-09). 9가 되면 넘는 몫은 리롤
        exp_first = round_stage(game_round) >= 5 and player.level == 8
        return action(player.gold, player.level, target, floor, exp_first)


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고, 주지 않으면 스스로 고른다(3단계부터 측정은 주지 않는다)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
