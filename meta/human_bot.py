"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

행동할 때마다 할 일이 있는 첫 단계만 움직인다: 보드 채우기 → 벤치 정리 → 사기 → 교체 → 아이템 → 자리 맞추기 → 레벨·리롤.
라운드의 첫 행동 때 초반 전략(연승형·연패형)을 정하거나 바꾼다. 아이템은 meta/human_items.py, 레벨·리롤은
meta/human_macro.py에 있고, 자리 맞추기는 구석 배치(analysis.battle.corner_positions)다. 덱 고르기(3단계)는 다음에 더한다.
"""
from analysis.battle import corner_positions
from Simulator.stats import round_stage
from Simulator.utils import x_y_to_1d_coord
from meta.human_items import item_action
from meta.human_macro import action, carry3, early_mode, plan, stable, stay_level
from meta.lobby import DeckPolicy

KNOBS = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20}


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        if game_round != self.last_round:
            self.last_round = game_round
            self.update_mode(player, game_round)
        return (self.fill(player, shop, mask) or self.sell(player) or self.buy(player, shop, mask)
                or self.swap(player) or item_action(player, self.board, self.mode or 'win', game_round, mask)
                or self.reposition(player, game_round) or self.macro(player, game_round))

    def update_mode(self, player, game_round):
        """2-1에 초반 전략을 고르고, 연승형이 2~3단계에 두 번 연달아 지면 연패형으로 바꾼다.
        연패형은 3-2가 되거나 체력이 손잡이 값(50) 아래로 내려가면 보드를 세운다(rebuilt)."""
        if game_round < 3:
            return
        if self.mode is None:
            self.mode = early_mode(player, self.knobs)
        if self.mode == 'win' and game_round < 15 and player.loss_streak >= 2:
            self.mode, self.rebuilt = 'lose', False
        if self.mode == 'lose' and not self.rebuilt and (game_round >= 10 or player.health < self.knobs['lose_hp']):
            self.rebuilt = True

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
                             done3, steady, self.knobs)
        exp_first = round_stage(game_round) >= 5 and player.level == 8 and steady
        return action(player.gold, player.level, target, floor, exp_first)


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고(0~2단계), 주지 않으면 스스로 고른다(3단계)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
