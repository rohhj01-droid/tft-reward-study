"""
풀게임용 정책.

시뮬레이터의 기본 봇(default_agent)은 우선순위 캐스케이드로 되어 있는데,
앞쪽 단계(보드 채우기, 구매, 배치, 판매)가 매 턴 액션을 반환해서 뒤쪽에 있는
레벨/리롤 판단까지 도달하지 못한다. 실제로 계측해 보면 매크로 판단 함수의
호출 횟수가 0이었다.

그래서 훅을 끼워넣는 대신 정책 자체를 다시 썼다. 핵심은 각 단계를 "할 일이 있을
때만 발동"하도록 만드는 것이다. 그러면 할 일이 없는 턴에는 매크로 판단까지 반드시
도달한다.

  1. 벤치가 꽉 참        -> 조합 외 유닛 판매
  2. 상점에 조합/보유 유닛 -> 구매 (같은 유닛을 모아 별을 올리기 위함)
  3. 매크로 판단          -> 레벨 / 리롤 / 패스
"""
from fullgame.macro_rules import decide_slowroll, to_action_token

ROUND_STAGE_THRESHOLDS = [3, 9, 15, 21, 27]


def round_to_stage(game_round):
    for i, threshold in enumerate(ROUND_STAGE_THRESHOLDS):
        if game_round <= threshold:
            return i + 1
    return 6


def board_features(player, game_round):
    n_3star = sum(1 for row in player.board for unit in row
                  if unit and getattr(unit, 'stars', 1) == 3)
    return {
        'stage': round_to_stage(game_round),
        'level': player.level,
        'gold': player.gold,
        'health': player.health,
        'win_streak': getattr(player, 'win_streak', 0),
        'loss_streak': getattr(player, 'loss_streak', 0),
        'num_3star': n_3star,
    }


class RerollPolicy:
    """
    시뮬레이터의 Default_Agent 인스턴스에 붙여 쓰는 정책.

    agent      : 시뮬레이터 Default_Agent (max_unit_check 등 유틸을 빌려 쓴다)
    comp       : 커밋할 조합의 챔피언 이름 리스트
    decide     : 매크로 규칙 함수
    roll_floor : 이 골드 위로만 리롤한다
    """

    def __init__(self, agent, comp, decide=decide_slowroll, roll_floor=32):
        self.agent = agent
        self.comp = set(comp)
        self.decide = decide
        self.roll_floor = roll_floor
        self.calls = 0
        self.macro_calls = 0

    def __call__(self, player, shop, game_round, mask):
        self.calls += 1
        self.agent.current_round = game_round

        # 보드에 자리가 비어 있으면 시뮬레이터의 기본 배치 로직을 그대로 쓴다.
        placement = self.agent.max_unit_check(player, shop, mask)
        if placement != ' ':
            return placement

        if player.bench_full():
            return self.agent.sell_bench_full(player)

        # 조합 유닛과 이미 가진 유닛만 산다. 시너지가 오른다는 이유로
        # 서로 다른 1성 유닛을 넓게 사면 별이 영영 오르지 않는다.
        owned = {unit.name for row in player.board for unit in row if unit}
        owned |= {unit.name for unit in player.bench if unit}
        from Simulator.default_agent_stats import COST
        for i, shop_unit in enumerate(shop):
            if not mask[47 + i][0] or shop_unit.endswith('_c'):
                continue
            if (shop_unit in self.comp or shop_unit in owned) and COST.get(shop_unit, 99) <= player.gold:
                self.agent.require_pair_update = True
                return '3_' + str(i)

        self.macro_calls += 1
        decision, _ = self.decide(board_features(player, game_round))
        return to_action_token(decision, player, self.roll_floor)


def attach(player, comp, **kwargs):
    """플레이어 한 명에게만 이 정책을 붙인다. 같은 게임 안에서 A/B가 가능하다."""
    agent = player.default_agent
    policy = RerollPolicy(agent, comp, **kwargs)
    agent._reroll_policy = policy
    original = agent.policy

    def patched(p, shop, game_round, mask):
        if game_round <= 2:
            return original(p, shop, game_round, mask)
        return policy(p, shop, game_round, mask)

    agent.policy = patched
    return policy
