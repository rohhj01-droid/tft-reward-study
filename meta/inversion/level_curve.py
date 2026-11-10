"""학습 몫 가르기 읽기용 숫자(판정 아님, 2026-11-10, results/README 「읽은 것 (학습 몫 가르기)」): B와 2차의 새 시드 2~5마다
세 탐침(본래, 레벨만, 틀)에서 AI 자리의 라운드 시작 평균 레벨·골드를 낸다(탐침 기록의 curve 줄, 모든 판).
실행(저장소 맨 위에서): python meta/inversion/level_curve.py
"""
import json
import statistics

INV = 'meta/inversion/'
SLOTS = {9: '3-1', 13: '3-6', 15: '4-1', 21: '5-1'}

for stem in ('plan_dense_both', 'plan_margin_deck'):
    for s in (2, 3, 4, 5):
        probes = []
        for p in ('probe_rows_', 'probe_rows_level_', 'probe_rows_frame_'):
            ai = [r for r in json.load(open(f'{INV}{p}{stem}_s{s}_latest.json', encoding='utf-8'))['rows'] if r['kind'] == 'ai']
            probes.append({k: [statistics.mean(c[i] for r in ai for c in r['curve'] if c[0] == k) for i in (1, 2)] for k in SLOTS})
        print(f'{stem}_s{s} (본래 / 레벨만 / 틀): ' + ' | '.join(
            f'{n} 레벨 ' + '/'.join(f'{q[k][0]:.2f}' for q in probes) + ' 골드 ' + '/'.join(f'{q[k][1]:.1f}' for q in probes)
            for k, n in SLOTS.items()))
