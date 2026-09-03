"""
다중 보상(HRA) Q 네트워크.

보상 요인마다 출력 헤드를 따로 두고 행동을 고를 때만 Q_total = Σ w_i * Q_i 로 합친다.
헤드가 자기 요인의 보상만 보고 학습하니 요인 신호가 서로 섞이지 않는다.
그리고 어떤 요인이 그 행동을 밀었는지 헤드별 Q를 열어보면 그대로 보인다.
보상 설계를 실험하는 저장소라 이 해석 가능성이 성능만큼 중요하다.
"""
import torch
import torch.nn as nn


class HRANet(nn.Module):
    def __init__(self, state_dim, n_actions, heads, hidden=64):
        super().__init__()
        self.heads = list(heads)
        # trunk는 공유한다. 상태 표현은 요인과 무관하니 나눌 이유가 없다.
        # 헤드만 갈라도 보상 신호는 안 섞인다.
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        # ModuleDict 키에는 점을 못 쓴다. 헤드 이름을 'reward.board' 식으로 지으면 여기서 터진다.
        self.out = nn.ModuleDict({h: nn.Linear(hidden, n_actions) for h in self.heads})

    def forward(self, x):
        z = self.trunk(x)
        return {h: self.out[h](z) for h in self.heads}

    def combined(self, q, weights):
        # 합치는 건 행동 선택할 때뿐이다. 학습은 헤드별로 따로 돈다.
        # 그래서 weights를 바꾸면 재학습 없이 다른 정책을 뽑아볼 수 있다.
        return sum(weights[h] * q[h] for h in self.heads)

    def explain(self, state, weights):
        """상태 하나에 대해 헤드별 Q값과 최종 선택을 같이 돌려준다."""
        with torch.no_grad():
            q = self.forward(torch.tensor(state, dtype=torch.float32))
        detail = {h: q[h].tolist() for h in self.heads}
        choice = int(self.combined(q, weights).argmax())
        return choice, detail
