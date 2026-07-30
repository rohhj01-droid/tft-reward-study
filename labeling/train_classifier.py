"""
상태 -> 매크로 행동 분류기.

sample_states.py 의 수치 피처와 label_states.py 의 LLM 라벨을 id로 붙여서 학습한다.
검증 정확도만 보면 안 되고, 예측 분포를 함께 봐야 한다. 라벨이 한쪽으로 쏠려 있으면
모델은 그 클래스만 찍고도 높은 정확도를 얻는다.

실행: python -m labeling.train_classifier states.json labels.json
"""
import argparse
import json
from collections import Counter

import numpy as np
import torch
import torch.nn as nn

FEATURES = ['stage', 'level', 'gold', 'interest', 'health', 'win_streak', 'loss_streak',
            'num_units', 'board_value', 'num_high_cost', 'num_3star',
            'num_synergies', 'max_synergy', 'num_items']
ACTIONS = ['level_up', 'roll_down', 'save_econ', 'hold']


def load(states_path, labels_path):
    with open(states_path, encoding='utf-8') as f:
        states = {s['id']: s['features'] for s in json.load(f)}
    with open(labels_path, encoding='utf-8') as f:
        labels = json.load(f)

    X, y = [], []
    for item in labels:
        feats = states.get(item['id'])
        action = item['label'].get('primary_action')
        if feats is None or action not in ACTIONS:
            continue
        X.append([float(feats.get(k, 0)) for k in FEATURES])
        y.append(ACTIONS.index(action))
    return np.array(X, dtype=np.float32), np.array(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('states')
    ap.add_argument('labels')
    ap.add_argument('--epochs', type=int, default=300)
    args = ap.parse_args()

    X, y = load(args.states, args.labels)
    print(f'데이터 {len(X)}개')
    dist = Counter(ACTIONS[i] for i in y)
    print('행동 분포:', dict(dist))
    majority = dist.most_common(1)[0]
    print(f'다수 클래스만 찍었을 때의 정확도: {100 * majority[1] / len(y):.0f}% ({majority[0]})')

    mean, std = X.mean(0), X.std(0) + 1e-6
    X = (X - mean) / std
    idx = np.random.permutation(len(X))
    cut = int(len(X) * 0.8)
    train_idx, val_idx = idx[:cut], idx[cut:]

    Xt = torch.tensor(X[train_idx])
    yt = torch.tensor(y[train_idx])
    Xv = torch.tensor(X[val_idx])
    yv = torch.tensor(y[val_idx])

    model = nn.Sequential(nn.Linear(len(FEATURES), 32), nn.ReLU(), nn.Linear(32, len(ACTIONS)))
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(Xt), yt)
        loss.backward()
        opt.step()
        if epoch % 50 == 0:
            model.eval()
            with torch.no_grad():
                acc = (model(Xv).argmax(1) == yv).float().mean().item()
            print(f'  ep{epoch:3d}  loss {loss.item():.3f}  val {acc * 100:.0f}%')

    model.eval()
    with torch.no_grad():
        pred = model(Xv).argmax(1)
        acc = (pred == yv).float().mean().item()
    print(f'\n검증 정확도 {acc * 100:.0f}%')
    print('예측 분포:', dict(Counter(ACTIONS[i] for i in pred.tolist())))
    print('예측이 한 클래스로 몰려 있으면, 정확도가 높아도 상태를 구분하지 못하는 것이다.')


if __name__ == '__main__':
    main()
