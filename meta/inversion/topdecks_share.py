"""가르친 AI와 좋은 덱만 고르는 규칙 봇 견주기 판정(results/README 「가르친 AI와 좋은 덱만 고르는 규칙 봇 견주기: 미리 정한 판정」, 2026-11-18).
판은 안 돌리고 탐침 기록만 읽는다.

가르친 AI(plan_teach) 시드 2~5의 본래·틀 탐침, 기준선 탐침(probe_topdecks.py: 같은 판, AI 자리에 상위 세 덱만 고르는 규칙 봇), 대조 탐침
(probe_rule.py)을 읽는다. 판(시드)마다 「규칙 평균 등수 − AI(기준선) 자리 평균 등수」를 낸다.
차 = 가르친 AI의 본래 A/B(네 시드 평균) − 기준선의 본래 A/B. 같은 판끼리 빼므로 대조 탐침을 빼든 안 빼든 값이 같다.
표준오차 = √(AI 쪽² + 기준선 쪽²). AI 쪽은 네 시드 값의 표준편차 ÷ 2이고, 판 표준오차(판마다 네 실행을 평균한 값의 표준오차)보다 작으면 그
값을 쓴다. 기준선 쪽은 기준선 탐침의 판 표준오차다.
판정: 차가 표준오차의 2배 이상이면 「넘는다」, −2배 이하면 「기준선이 넘는다」, 그 사이면 「구별되지 않는다」.
틀 탐침과 견준 차, 대조를 뺀 값, 판별로 짝지은 표준오차, 기준선 자리의 끝 덱은 판정 없이 함께 낸다.
모든 기록의 교과서 손잡이와 행동 상한이 같은지, 기준선 자리가 후보 셋 안의 덱으로 끝났는지 확인한다(아니면 셈을 멈춘다).
실행(저장소 맨 위에서): python meta/inversion/topdecks_share.py results/plan_topdecks_share.json
셈 확인: 둘째 인자로 check를 주면 기준선 자리에 가르친 AI 네 실행의 판별 평균을 넣는다(차가 0.000, 「구별되지 않는다」).
"""
import hashlib
import json
import math
import statistics
import sys
from collections import Counter

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
SEEDS = (2, 3, 4, 5)
GAMES = set(range(700000, 700400))
RISK, TOP, CONTROL = 'results/deck_risk_rule_teach.json', 'probe_rows_topdecks_teach.json', 'probe_rows_rule8_teach.json'
record = {'check': CHECK, 'inputs': {}}
ENV = set()


def note_env(d):
    ENV.add(json.dumps({'textbook': d['textbook'], 'actions_per_turn': d['actions_per_turn']}, sort_keys=True))


def probe(path, net=None):
    """-> ({판 시드: 규칙 − AI 자리}, 자리별 기록). net을 주면 그 실행의 마지막 신경망을 가중치 덮어쓰기 없이 쟀는지도 본다."""
    raw = open(INV + path, 'rb').read()
    record['inputs'][path] = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    assert d['games'] == 400, path
    assert net is None or (d['weights'] == d['saved_weights'] and d['net'] == net), path
    note_env(d)
    by = {}
    for r in d['rows']:
        by.setdefault(r['seed'], {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert set(by) | {e[0] for e in d['errors']} == GAMES, f'{path}: 시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values()), path
    return {s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()}, d['rows']


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def side(runs, games):
    """네 실행의 {판: 값} -> (평균, 표준오차, 실행별 평균). 표준오차는 실행 사이 흩어짐이고, 판 표준오차보다 작으면 그 값이다."""
    per = [statistics.mean(r[g] for g in games) for r in runs]
    return statistics.mean(per), max(statistics.stdev(per) / len(per) ** 0.5, mse([statistics.mean(r[g] for r in runs) for g in games])[1]), per


raw = open(RISK, 'rb').read()
record['inputs'][RISK] = hashlib.sha256(raw).hexdigest()
risk = json.loads(raw)
assert risk['games_asked'] == 800 and len(risk['top3']) == 3, RISK
note_env(risk)
top, top_rows = probe(TOP)
seats = [r for r in top_rows if r['kind'] == 'ai']
assert {r['deck'] for r in seats} <= set(risk['top3']), '기준선 자리가 후보 밖의 덱으로 끝났다'
ctrl = probe(CONTROL)[0]
base = [probe(f'probe_rows_plan_teach_s{s}_latest.json', f'plan_teach_s{s}_latest.pt')[0] for s in SEEDS]
frame = [probe(f'probe_rows_frame_plan_teach_s{s}_latest.json', f'plan_teach_s{s}_latest.pt')[0] for s in SEEDS]
assert len(ENV) == 1, f'교과서 손잡이나 행동 상한이 기록마다 다르다: {ENV}'
games = sorted(set(top).intersection(ctrl, *base, *frame))
if CHECK:
    top = {g: statistics.mean(r[g] for r in base) for g in games}
base_mean, base_se, base_per = side(base, games)
frame_mean, frame_se, frame_per = side(frame, games)
top_mean, top_se = mse([top[g] for g in games])
ctrl_mean = statistics.mean(ctrl[g] for g in games)
diff, se = base_mean - top_mean, math.hypot(base_se, top_se)
cell = ('가르친 AI는 좋은 덱만 고르는 규칙 봇을 넘는다' if diff >= 2 * se and diff > 0 else
        '좋은 덱만 고르는 규칙 봇이 가르친 AI를 넘는다' if diff <= -2 * se and diff < 0 else
        '가르친 AI와 좋은 덱만 고르는 규칙 봇은 구별되지 않는다')
record['environment'] = json.loads(next(iter(ENV)))
record['decks'] = {'top3': risk['top3'], 'table': {d: risk['first'][d] for d in risk['top3']},
                   'end': {d: n / len(seats) for d, n in Counter(r['deck'] for r in seats).most_common()},
                   'switches': statistics.mean(r['switches'] for r in seats)}
record['values'] = {'games_common': len(games), 'ai': [base_mean, base_se], 'ai_by_seed': dict(zip(map(str, SEEDS), base_per)),
                    'ai_frame': [frame_mean, frame_se], 'baseline': [top_mean, top_se], 'control_mean': ctrl_mean,
                    'ai_fixed': base_mean - ctrl_mean, 'baseline_fixed': mse([top[g] - ctrl[g] for g in games]),
                    'diff_by_seed': {str(s): v - top_mean for s, v in zip(SEEDS, base_per)},
                    'frame_diff': [frame_mean - top_mean, math.hypot(frame_se, top_se)],
                    'paired_game_se': mse([statistics.mean(r[g] for r in base) - top[g] for g in games])[1]}
record['verdict'] = {'diff': diff, 'se': se, 'ratio': diff / se if se else 0.0, 'cell': cell}
print(f'환경: 교과서 손잡이 {record["environment"]["textbook"]}, 행동 상한 {record["environment"]["actions_per_turn"]}, 함께 있는 판 {len(games)}')
print(f'상위 세 덱: {", ".join(risk["top3"])}')
print(f'본래 A/B: 가르친 AI {base_mean:+.4f} ± {base_se:.4f}, 기준선 {top_mean:+.4f} ± {top_se:.4f} (대조 탐침 {ctrl_mean:+.4f})')
print(f'차(가르친 AI − 기준선) = {diff:+.4f} ± {se:.4f}, 표준오차의 {record["verdict"]["ratio"]:.2f}배 → 「{cell}」')
print(f'판정 밖: 틀 탐침과 견준 차 {frame_mean - top_mean:+.4f} ± {record["values"]["frame_diff"][1]:.4f}, 판별로 짝지은 표준오차 {record["values"]["paired_game_se"]:.4f}')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
