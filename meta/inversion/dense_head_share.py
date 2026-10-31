"""진행 보상 실험: 마지막 신경망에서 보조 갈래(보드 세기, 또는 시너지·유닛 수)가 판단을 직접 바꾸는 몫(results/README 「진행 보상 실험」
결과, 2026-10-31). 판은 안 돌리고 따라 하기 자료(규칙 봇이 지나간 상태 381,835개, 옛 실행기 10/13)에서 저장본이 고르는 계획만 센다.
「뺌」은 판단할 때 보조 갈래 가중치만 0으로 바꾼 것이다(그 갈래 없이 배운 신경망이 아니다). 여섯 갈래 저장본을 읽으니 가지
dense-reward(cf18e52)의 hra 코드가 있어야 돈다.

실행(저장소 맨 위에서, 둘째 인자는 견줄 신경망):
    python meta/inversion/dense_head_share.py checkpoints/plan_dense_value_s1_g3000.pt checkpoints/plan_margin_deck_s1_g3000.pt
    python meta/inversion/dense_head_share.py checkpoints/plan_dense_both_s1_g3000.pt checkpoints/plan_margin_deck_s1_g3000.pt
"""
import sys

import numpy as np
import torch

from hra.plan_net import combined, load, masked_argmax

torch.set_num_threads(1)
z = np.load('checkpoints/plan_demos.npz')
S, MASK, RULE = z['s'], z['m'], z['a']
LATE = np.round(S[:, 0] * 40) >= 15  # 4-1(15번째 칸)부터


def decide(path, drop=()):
    """-> 상태마다 (덱, 레벨, 남길 골드) 칸 번호. 레벨은 그대로 / +1 / +2, 남길 골드는 안 함 / 50 / 30 / 20 / 10 / 0 순서다."""
    net, w, _ = load(path)
    w = dict(w, **{h: 0.0 for h in drop})
    out = np.empty((len(S), 3), np.int64)
    with torch.no_grad():
        for lo in range(0, len(S), 40000):
            q = net(torch.as_tensor(S[lo:lo + 40000]))
            out[lo:lo + 40000] = masked_argmax(combined(q, w), torch.as_tensor(MASK[lo:lo + 40000])).numpy()
    return out


AUX = tuple(h for h in ('synergy', 'units', 'value') if load(sys.argv[1])[1].get(h))  # 가중치가 있는 보조 갈래
a, a0, base = decide(sys.argv[1]), decide(sys.argv[1], AUX), decide(sys.argv[2])
flip = a != a0
print(f'상태 {len(S)}개(4-1부터 {LATE.sum()}개), 뺀 갈래 {AUX}')
print('보조 갈래를 빼면 바뀌는 판단(덱 / 레벨 / 남길 골드): ' + ' / '.join(f'{x:.2%}' for x in flip.mean(0)) +
      f', 하나라도 {flip.any(1).mean():.2%}')
for i, name in ((1, '레벨'), (2, '남길 골드')):
    f = flip[:, i]
    print(f'  {name}: 바뀐 판단 중 더 쓰는 쪽(칸 번호가 큼) {(a[f, i] > a0[f, i]).mean():.1%}')
print('규칙과 같은 판단 비율 차(있음 − 뺌, 덱 / 레벨 / 남길 골드): ' +
      ' / '.join(f'{x:+.4f}' for x in (a == RULE).mean(0) - (a0 == RULE).mean(0)))
none = {k: (v[LATE, 2] == 0).mean() for k, v in (('AI', a), ('뺌', a0), ('비교', base), ('규칙', RULE))}
print('4-1부터 「리롤 안 함」: ' + ', '.join(f'{k} {v:.2%}' for k, v in none.items()) +
      f'; 비교 신경망과의 차 중 보조 갈래를 빼서 메워지는 몫 {(none["뺌"] - none["AI"]) / (none["비교"] - none["AI"]):.3f}')
