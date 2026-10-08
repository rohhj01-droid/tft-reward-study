"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

지금(0단계)은 덱 봇(meta.lobby.DeckPolicy)과 같은 규칙을 1라운드부터 쓰고, 자리 맞추기만 구석 배치다. 아이템(1단계),
초반 전략과 레벨·리롤(2단계), 덱 고르기(3단계)를 차례로 더한다.
"""
from analysis.battle import corner_positions
from Simulator.utils import x_y_to_1d_coord
from meta.lobby import DeckPolicy

KNOBS = {}  # 손잡이 값(설계 6절). 단계마다 채운다


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

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


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고(0~2단계), 주지 않으면 스스로 고른다(3단계)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
