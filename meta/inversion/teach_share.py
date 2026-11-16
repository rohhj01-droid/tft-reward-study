"""돈 쓰는 때까지 가르친 AI 판정(results/README 「돈 쓰는 때까지 가르친 AI: 미리 정한 판정」, 2026-11-16). 판은 안 돌리고 탐침 기록만
읽는다.

가르친 AI(plan_teach) 시드 2~5의 본래·틀 탐침과 대조 탐침(probe_rule.py: 같은 판, 여덟 자리 모두 규칙) 하나를 읽는다. 판(시드)마다
「규칙 평균 등수 − AI 자리 평균 등수」를 낸다. 대조 탐침에서는 AI가 앉았을 자리의 규칙 봇이 「AI 자리」다.
고친 A/B = 본래 탐침 값 − 대조 탐침 값(판마다 짝). 조건 평균은 네 시드의 평균이고, 표준오차는 실행 사이 흩어짐으로 내되 판
표준오차(판마다 네 실행을 평균한 뒤 대조를 뺀 값의 표준오차)보다 작으면 그 값을 쓴다(대조 실행 하나를 네 실행이 함께 쓰므로).
판정: 고친 A/B가 표준오차의 2배 이상이면 「넘는다」, −2배 이하면 「못 미친다」, 그 사이면 「구별되지 않는다」.
학습 몫 L = 본래 − 틀(레벨·남길 골드를 교과서 칸으로 바꾼 탐침)은 판정 없이 함께 낸다.
모든 기록의 교과서 손잡이와 행동 상한이 같은지 확인한다(다르면 셈을 멈춘다).
실행(저장소 맨 위에서): python meta/inversion/teach_share.py results/plan_teach_share.json
셈 확인: 둘째 인자로 check를 주면 본래 탐침 자리에 대조 탐침을 넣는다(고친 A/B가 0.000 ± 0.000, 「구별되지 않는다」).
"""
import hashlib
import json
import statistics
import sys

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
SEEDS = (2, 3, 4, 5)
GAMES = set(range(700000, 700400))
CONTROL = 'probe_rows_rule8_teach.json'
record = {'check': CHECK, 'inputs': {}}
ENV = set()


def probe(path, net=None):
    """-> {판 시드: 규칙 − AI 자리}. net을 주면 그 실행의 마지막 신경망을 가중치 덮어쓰기 없이 쟀는지도 본다."""
    raw = open(INV + path, 'rb').read()
    record['inputs'][path] = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    assert d['games'] == 400, path
    assert net is None or (d['weights'] == d['saved_weights'] and d['net'] == net), path
    ENV.add(json.dumps({'textbook': d['textbook'], 'actions_per_turn': d['actions_per_turn']}, sort_keys=True))
    by = {}
    for r in d['rows']:
        by.setdefault(r['seed'], {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert set(by) | {e[0] for e in d['errors']} == GAMES, f'{path}: 시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values()), path
    return {s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()}


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def pooled(runs, key):
    """조건 평균(시드 넷)과 표준오차: 실행 사이 흩어짐으로 내고, 실행별 판 표준오차 평균 ÷ 2보다 작으면 그 값을 쓴다(앞 판정들과 같은 식)."""
    vals = [r[key][0] for r in runs]
    return statistics.mean(vals), max((statistics.variance(vals) / len(vals)) ** 0.5, statistics.mean(r[key][1] for r in runs) / len(vals) ** 0.5)


ctrl = probe(CONTROL)
R, base = [], {}
print('## 실행마다 (판별 짝, ± 판 표준오차)')
for s in SEEDS:
    tag = f'plan_teach_s{s}'
    b = dict(ctrl) if CHECK else probe(f'probe_rows_{tag}_latest.json', f'{tag}_latest.pt')
    f = probe(f'probe_rows_frame_{tag}_latest.json', f'{tag}_latest.pt')
    base[s] = b
    gc, gf = sorted(set(b) & set(ctrl)), sorted(set(b) & set(f))
    R.append({'games': len(gc), 'games_frame': len(gf), 'AB': mse([b[g] for g in gc]), 'fixed': mse([b[g] - ctrl[g] for g in gc]),
              'L': mse([b[g] - f[g] for g in gf]), 'frame_fixed': mse([f[g] - ctrl[g] for g in sorted(set(f) & set(ctrl))])})
    x = R[-1]
    print(f'시드 {s}: 본래 A/B {x["AB"][0]:+.4f} ± {x["AB"][1]:.4f}, 고친 A/B {x["fixed"][0]:+.4f} ± {x["fixed"][1]:.4f}, '
          f'학습 몫 {x["L"][0]:+.4f} ± {x["L"][1]:.4f}, 틀 탐침의 고친 A/B {x["frame_fixed"][0]:+.4f} ± {x["frame_fixed"][1]:.4f}, '
          f'판 {x["games"]} (틀과 짝 {x["games_frame"]})')
assert len(ENV) == 1, f'교과서 손잡이나 행동 상한이 기록마다 다르다: {ENV}'
record['environment'] = json.loads(next(iter(ENV)))
common = sorted(set(ctrl).intersection(*(base[s] for s in SEEDS)))
M = {k: pooled(R, k) for k in ('AB', 'fixed', 'L', 'frame_fixed')}
game_se = mse([statistics.mean(base[s][g] for s in SEEDS) - ctrl[g] for g in common])[1]
theta, se = M['fixed'][0], max((statistics.variance([r['fixed'][0] for r in R]) / len(R)) ** 0.5, game_se)
cell = ('돈 쓰는 때까지 가르친 AI는 고친 교과서 봇을 넘는다' if theta >= 2 * se and theta > 0 else
        '돈 쓰는 때까지 가르친 AI는 고친 교과서 봇에 못 미친다' if theta <= -2 * se and theta < 0 else
        '돈 쓰는 때까지 가르친 AI는 고친 교과서 봇과 구별되지 않는다')
record['runs'] = {f's{s}': x for s, x in zip(SEEDS, R)}
record['means'] = M
record['control'] = mse([ctrl[g] for g in sorted(ctrl)])
record['verdict'] = {'fixed': theta, 'se': se, 'game_se': game_se, 'games_common': len(common), 'ratio': theta / se if se else 0.0, 'cell': cell}
print(f'\n환경: 교과서 손잡이 {record["environment"]["textbook"]}, 행동 상한 {record["environment"]["actions_per_turn"]}')
print(f'대조 탐침(여덟 자리 모두 규칙): {record["control"][0]:+.4f} ± {record["control"][1]:.4f} (판 {len(ctrl)})')
print('\n## 조건 평균 (시드 넷, ± 표준오차)')
print(', '.join(f'{n} {M[k][0]:+.4f} ± {M[k][1]:.4f}' for k, n in (('AB', '본래 A/B'), ('L', '학습 몫'), ('frame_fixed', '틀 탐침의 고친 A/B'))))
print('\n## 판정')
print(f'고친 A/B = {theta:+.4f} ± {se:.4f} (실행 사이 {(statistics.variance([r["fixed"][0] for r in R]) / len(R)) ** 0.5:.4f}, 판 {game_se:.4f}, '
      f'표준오차의 {record["verdict"]["ratio"]:.2f}배, 함께 있는 판 {len(common)}) → 「{cell}」')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
