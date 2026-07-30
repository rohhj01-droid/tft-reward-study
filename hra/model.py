"""
다중 보상(Hybrid Reward Architecture) Q 네트워크.

보상 요인마다 독립된 출력 헤드를 두고, 행동을 고를 때만 가중합한다.

    Q_total(s, a) = Σ_i  w_i * Q_i(s, a)

일반적인 DQN과 다른 점은 두 가지다.
1. 각 헤드가 자기 요인의 보상만 보고 학습하므로, 요인별 신호가 섞이지 않는다.
2. 어떤 요인이 그 행동을 선택하게 했는지 헤드별 Q값으로 확인할 수 있다.
   (의사결정 해석 목적)
"""
import torch
import torch.nn as nn


class HRANet(nn.Module):
    def __init__(self, state_dim, n_actions, heads, hidden=64):
        super().__init__()
        self.heads = list(heads)
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.out = nn.ModuleDict({h: nn.Linear(hidden, n_actions) for h in self.heads})

    def forward(self, x):
        z = self.trunk(x)
        return {h: self.out[h](z) for h in self.heads}

    def combined(self, q, weights):
        """헤드별 Q를 가중합해서 행동 선택용 Q를 만든다."""
        return sum(weights[h] * q[h] for h in self.heads)

    def explain(self, state, weights):
        """
        상태 하나에 대해 헤드별 Q값과 최종 선택을 함께 돌려준다.
        어떤 요인이 그 행동을 밀었는지 보기 위한 용도.
        """
        with torch.no_grad():
            q = self.forward(torch.tensor(state, dtype=torch.float32))
        detail = {h: q[h].tolist() for h in self.heads}
        choice = int(self.combined(q, weights).argmax())
        return choice, detail
