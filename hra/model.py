"""
다중 보상(HRA) Q 네트워크.

보상 요인마다 출력 헤드를 따로 두고 행동을 고를 때만 Q_total = Σ w_i * Q_i 로 합친다.
헤드가 자기 요인의 보상만 보고 학습하니 요인 신호가 서로 섞이지 않는다.
그리고 어떤 요인이 그 행동을 밀었는지 헤드별 Q를 열어보면 그대로 보인다.
보상 설계를 실험하는 저장소라 이 해석 가능성이 성능만큼 중요하다.
"""
import os

import torch
import torch.nn as nn


class HRANet(nn.Module):
    def __init__(self, state_dim, n_actions, heads, hidden=64):
        super().__init__()
        self.heads = list(heads)
        # 불러올 때 같은 모양으로 다시 짓기 위해 남긴다. 상태를 6차원에서 늘리면
        # 옛 체크포인트를 새 모양에 넣는 실수를 여기서 막는다.
        self.args = {'state_dim': state_dim, 'n_actions': n_actions,
                     'heads': self.heads, 'hidden': hidden}
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


def save(net, path, weights, **meta):
    # 보상 가중치를 같이 저장한다. 정책은 헤드 Q값이 아니라 그 가중합의 argmax라,
    # 가중치 없이 망만 있으면 학습 때와 같은 행동을 다시 고를 수 없다.
    # meta 값은 int/float/str 같은 기본형만 넣는다. 불러올 때 그 외는 거부된다.
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    torch.save({'args': net.args, 'state_dict': net.state_dict(),
                'weights': dict(weights), 'meta': meta}, path)


def load(path):
    ck = torch.load(path, map_location='cpu', weights_only=True)
    net = HRANet(**ck['args'])
    net.load_state_dict(ck['state_dict'])
    net.eval()
    return net, ck['weights'], ck['meta']


if __name__ == '__main__':
    # 저장했다 불러온 망이 같은 상태에서 같은 Q, 같은 행동을 내는지 확인한다.
    import tempfile

    net = HRANet(6, 4, ['board', 'econ'])
    weights = {'board': 1.0, 'econ': 0.3}
    path = os.path.join(tempfile.mkdtemp(), 'roundtrip.pt')
    save(net, path, weights, seed=0, episodes=10)
    net2, weights2, meta = load(path)

    xs = torch.rand(256, 6)
    with torch.no_grad():
        q1, q2 = net(xs), net2(xs)
    assert all(torch.equal(q1[h], q2[h]) for h in net.heads), '헤드 Q값이 다르다'
    assert torch.equal(net.combined(q1, weights).argmax(1),
                       net2.combined(q2, weights2).argmax(1)), '고르는 행동이 다르다'
    assert weights2 == weights and meta == {'seed': 0, 'episodes': 10}
    print('저장 -> 불러오기: 상태 256개에서 Q값과 행동 전부 일치')
