"""진행 보상 실험 시드 반복 판정(results/README 「시드 반복: 미리 정한 판정」, 2026-11-01). 판은 안 돌리고 평가 결과만 읽는다.

레벨·골드 몫(실행마다) = 판별 (본래 A/B − 하이브리드 A/B)의 평균. 덱 맞춘 값 = 0.28 × (2-1 덱이 느린 리롤 덱인 AI 자리의 몫)
+ 0.72 × (보통 덱 자리의 몫), 자리 몫 = 2 × (하이브리드 등수 − 본래 등수). 판정은 새 시드(2 이상)만 쓰고, 2차도 같은 새 시드가
다 있어야 한다(없으면 「미완」). 시드 1은 크기 보고에만 쓴다.
실행(저장소 맨 위에서): python meta/inversion/dense_seeds_verdict.py . results/plan_dense_seeds_verdict.json 1,2,3
셋째 인자 = 세 조건(A·B·2차)에 같이 쓰는 시드. 시드 2 이상의 파일은 dense 작업 폴더에서 이 저장소로 복사해 둔다.
"""
import hashlib
import json
import os
import statistics
import sys

import numpy as np
import torch

ROOT, OUT = sys.argv[1], sys.argv[2]
SEEDS = [int(x) for x in sys.argv[3].split(',')]
INV, RES, CK = os.path.join(ROOT, 'meta', 'inversion'), os.path.join(ROOT, 'results'), os.path.join(ROOT, 'checkpoints')
SLOW = {2, 5, 8, 13, 14, 19, 20, 21, 24, 25, 26, 27}  # 실행기 덱 표(1부터 번호)의 느린 리롤 덱 12개
W_SLOW, MIN_SEATS, MARGIN = 0.28, 100, 0.30
THR = {2: 2.353, 4: 2.262}  # 조건마다 새 시드 2개: t(자유도 3) 한쪽 5%; 4개(시드 4·5를 더한 2단계): t(자유도 9) 한쪽 2.5%
CFG = {'A': 'value', 'B': 'both', '2차': 'none'}
STEM = {'A': 'plan_dense_value', 'B': 'plan_dense_both', '2차': 'plan_margin_deck'}
CONDS = ('A', 'B', '2차')
record = {'inputs': {}, 'versions': {'numpy': np.__version__, 'torch': torch.__version__}, 'runs': {}}


def names(cond, s):
    if cond == '2차' and s == 1:  # 시드 1 2차는 옛 이름(같은 실행기로 다시 잰 탐침)
        return 'plan_margin_deck_s1', 'probe_rows_margin_deck_s1_latest_920e0be.json', \
            'probe_rows_hybrid_margin_deck_s1_latest.json', 'plan_eval_agree_margin_deck_s1_g3000.json'
    t = f'{STEM[cond]}_s{s}'
    return t, f'probe_rows_{t}_latest.json', f'probe_rows_hybrid_{t}_latest.json', f'plan_eval_agree_{t}_g3000.json'


def read(path):
    raw = open(path, 'rb').read()
    record['inputs'][os.path.relpath(path, ROOT)] = hashlib.sha256(raw).hexdigest()
    return raw


def probe(path):
    d = json.loads(read(path))
    assert not d['errors'] and d['games'] == 400, (path, d['errors'])
    assert d['weights'] == d['saved_weights'], f'{path}: 가중치를 덮어쓴 탐침이다'
    rows = {(r['seed'], r['seat']): r for r in d['rows']}
    by = {}
    for r in d['rows']:
        by.setdefault(int(r['seed']), {'ai': [], 'rule': []})[r['kind']].append(r['place'])
    assert sorted(by) == list(range(700000, 700400)), f'{path}: 시드가 빠졌다'
    assert all(len(v['ai']) == 4 and len(v['rule']) == 4 for v in by.values()), path
    return d, rows, {s: statistics.mean(v['rule']) - statistics.mean(v['ai']) for s, v in by.items()}


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def run(cond, s):
    tag, fp, fh, fa = names(cond, s)
    paths = [os.path.join(INV, fp), os.path.join(INV, fh), os.path.join(RES, fa), os.path.join(RES, f'{tag}.json'),
             os.path.join(CK, f'{tag}_latest.pt'), os.path.join(CK, f'{tag}_g3000.pt')]
    missing = [os.path.relpath(p, ROOT) for p in paths if not os.path.exists(p)]
    if missing:
        return {'missing': missing}
    (dp, op, base), (dh, oh, hyb) = probe(paths[0]), probe(paths[1])
    assert dp['net'] == dh['net'] and dp['net'].endswith(f'{tag}_latest.pt'), (dp['net'], dh['net'])
    cj = json.loads(read(paths[3]))
    assert (cj['config'], cj['seed'], cj['margin_until'], cj['margin_keep_deck'], cj.get('econ_w', 0.3)) == \
        (CFG[cond], s, 1000, True, 0.3), f'{tag}: 곡선 설정이 다르다'
    curve = cj['curve']
    assert [c['games'] for c in curve] == [500, 1000, 1500, 2000, 2500, 3000], f'{tag}: 곡선이 3천 판까지 없다'
    assert not any(c['resumed'] for c in curve), f'{tag}: 이어 한 실행이다. 빼지 말고 처음부터 다시 돌린다'
    ag = json.loads(read(paths[2]))
    assert not ag['errors'] and ag['decisions'] == 9479, fa
    assert read(paths[4]) == read(paths[5]), f'{tag}: latest와 g3000이 다르다'
    meta = torch.load(paths[4], map_location='cpu', weights_only=False)['meta']
    assert meta.get('games') == 3000 and meta.get('seed') == s and meta.get('config', CFG[cond]) == CFG[cond] \
        and meta.get('aux_w', 0.3) == 0.3, (tag, meta)
    lg = {x: base[x] - hyb[x] for x in base}
    # 자리 단위: 2-1 덱(첫 판단 칸)은 두 탐침에서 같아야 한다(둘 다 2-1 전에는 규칙 레벨·골드)
    ai = [k for k in op if op[k]['kind'] == 'ai']
    d21 = [op[k]['curve'][0][4] for k in ai]
    assert all(oh[k]['curve'][0][4] == d for k, d in zip(ai, d21)), f'{tag}: 2-1 덱이 어긋난다. 탐침을 다시 잰다'
    seat_v = np.array([2 * (oh[k]['place'] - op[k]['place']) for k in ai], float)
    slow = np.array([d in SLOW for d in d21])
    game = np.array([k[0] - 700000 for k in ai])
    n_slow, n_fast = int(slow.sum()), int((~slow).sum())
    rule_slow = float(np.mean([op[k]['curve'][0][4] in SLOW for k in op if op[k]['kind'] == 'rule']))  # 0.28의 근거(시드 1)

    def adj(w):
        return W_SLOW * (w * seat_v * slow).sum() / (w * slow).sum() + (1 - W_SLOW) * (w * seat_v * ~slow).sum() / (w * ~slow).sum()
    if min(n_slow, n_fast) >= MIN_SEATS:
        rng = np.random.default_rng(0)
        boots = [adj(np.bincount(rng.integers(0, 400, 400), minlength=400)[game].astype(float)) for _ in range(1000)]
        adjusted = (float(adj(np.ones(len(ai)))), float(np.std(boots, ddof=1)))
    else:
        adjusted = None  # 층 하나가 100자리 미만: 이 실행의 맞춘 값은 못 낸다
    end_same = np.mean([op[k]['deck'] == oh[k]['deck'] for k in ai])
    cnt = lambda rr: {d: sum(rr[k]['deck'] == d for k in ai) / len(ai) for d in {rr[k]['deck'] for k in ai}}
    co, ch = cnt(op), cnt(oh)
    tv = 0.5 * sum(abs(co.get(d, 0) - ch.get(d, 0)) for d in set(co) | set(ch))
    cv = {c['games']: (c['diff'], c['se']) for c in curve}
    jump = cv[3000][0] - (cv[2000][0] + cv[2500][0]) / 2
    jump_se = (cv[3000][1] ** 2 + (cv[2000][1] ** 2 + cv[2500][1] ** 2) / 4) ** 0.5
    ab, ab_se = mse(list(base.values()))
    return {'tag': tag, 'ab': ab, 'ab_se': ab_se, 'hybrid': mse(list(hyb.values())), 'lg': mse(list(lg.values())),
            'lg_adj': adjusted, 'seats_slow_fast': (n_slow, n_fast), 'slow_share': n_slow / len(ai), 'rule_slow_share': rule_slow,
            'level': ag['level'], 'floor': ag['floor'], 'end_deck_same': float(end_same), 'end_deck_tv': float(tv),
            'deck_path_changed': bool(end_same < 0.85 or tv > 0.05), 'jump': jump, 'jump_flag': bool(abs(jump) > 2 * jump_se),
            'curve_errors': sum(c['errors'] for c in curve), 'check_errors': sum(c['check_errors'] for c in curve),
            'per_game_lg': [lg[x] for x in sorted(lg)]}


def cell(ab, level, floor):  # 처음 판정 표(dense_verdict.py와 같음)
    off = level < 0.9 or floor < 0.9
    if ab > -0.2:
        return '성공' if off else '규칙 곁 버팀: 이번 질문에 답 못 함'
    return ('부분' if ab > -0.6 else '실패') + ('·벗어남' if off else '·규칙 곁')


R = {(c, s): run(c, s) for c in CONDS for s in SEEDS}
print('## 실행별 (레벨·골드 몫 = 본래 − 하이브리드, 반올림 전)')
for (c, s), r in R.items():
    record['runs'][f'{c} s{s}'] = r
    if 'missing' in r:
        print(f'{c} 시드 {s}: 없음 {r["missing"]}')
        continue
    a = r['lg_adj']
    print(f'{c} 시드 {s}: A/B {r["ab"]:+.4f}, 하이브리드 {r["hybrid"][0]:+.4f}, 레벨·골드 {r["lg"][0]:+.4f} ± {r["lg"][1]:.4f}, '
          f'덱 맞춘 값 ' + (f'{a[0]:+.4f} ± {a[1]:.4f}' if a else '못 냄') + f' (느린 몫 AI {r["slow_share"]:.2f}·규칙 {r["rule_slow_share"]:.4f}), '
          f'끝 덱 같음 {r["end_deck_same"]:.3f}·차 {r["end_deck_tv"]:.3f}' + (' [덱 경로 바뀜]' if r['deck_path_changed'] else '')
          + f', 3천 판 점검 튐 {r["jump"]:+.2f}' + (' [튐]' if r['jump_flag'] else '') + f', 칸 「{cell(r["ab"], r["level"], r["floor"])}」'
          + (f', 버린 판 {r["curve_errors"]}' if r['curve_errors'] else ''))


def pooled(seeds, key):
    """조건 안 표본분산의 평균(세 조건), 바닥 = 실행별 판 표준오차 평균"""
    vals = {c: [R[c, s][key][0] for s in seeds] for c in CONDS}
    s = statistics.mean(statistics.variance(v) for v in vals.values()) ** 0.5
    floor = statistics.mean(R[c, x][key][1] for c in CONDS for x in seeds)
    return vals, max(s, floor), s, floor


def seed1_diff(key):
    """시드 1의 B − 2차(같은 지표). 「되풀이 안 됨」에서 시드 1 크기를 배제하는지 볼 때만 쓴다."""
    b, n = R.get(('B', 1)), R.get(('2차', 1))
    if not b or not n or 'missing' in b or 'missing' in n or b[key] is None or n[key] is None:
        return None
    return b[key][0] - n[key][0]


new = [s for s in SEEDS if s >= 2]
ready = new and len(new) in THR and all('missing' not in R[c, s] for c in CONDS for s in new)
v = record['verdict'] = {}
print('\n## 판정 (새 시드만. 시드 1은 크기 보고에만)')
if ready:
    k, thr = len(new), THR[len(new)]
    for key, name in (('lg', '원래'), ('lg_adj', '덱 맞춘')):
        if key == 'lg_adj' and any(R[c, s]['lg_adj'] is None for c in CONDS for s in new):
            v[name] = None
            print(f'{name}: 못 냄(층 하나가 100자리 미만인 실행이 있다)')
            continue
        vals, s_used, s_raw, floor = pooled(new, key)
        se = s_used * (2 / k) ** 0.5
        d = statistics.mean(vals['B']) - statistics.mean(vals['2차'])
        dA = statistics.mean(vals['A']) - statistics.mean(vals['2차'])
        lb = statistics.mean(vals['B']) - thr * s_used / k ** 0.5
        ub, ref = d + thr * se, seed1_diff(key)
        out = {'B − 2차': d, 'se': se, 'ratio': d / se, 'spread': s_raw, 'floor': floor, 'A − 2차': dA, 'A ratio': dA / se,
               'B lower bound': lb, 'upper bound': ub, 'seed1 B − 2차': ref}
        if key == 'lg':  # 칸은 원래 지표에만 매긴다. 덱 맞춘 값은 확정일 때 이름만 가른다
            if d / se > thr:
                c = '확정'
            elif d > MARGIN:
                c = '애매(후보 유지)'
            elif d > 0:
                c = '되풀이 안 됨: ' + ('시드 1 크기는 되풀이되지 않음' if ref is not None and ub < ref
                                       else '작게 나왔지만 이 시드 수로는 시드 1 크기를 배제하지 못함')
            else:
                c = '되풀이 안 됨: 방향도 되풀이되지 않음'
            out['cell'] = c
        v[name] = out
        print(f'{name}: B − 2차 {d:+.4f}, 흔들림 {s_raw:.4f}(바닥 {floor:.4f}) → 표준오차 {se:.4f}, 비율 {d / se:+.2f} (문턱 {thr})'
              + (f' → 「{out["cell"]}」' if 'cell' in out else '') + f'; 위 한쪽 95% {ub:+.4f}(시드 1 ' + (f'{ref:+.4f}' if ref is not None else '없음') + ')')
        print(f'   A − 2차 {dA:+.4f} (비율 {dA / se:+.2f}), B 하한 {lb:+.4f} (−0.30 위면 「규칙보다 0.3등 넘게 덜 하지 않는다」)')
    raw = v['원래']
    if raw['cell'] == '확정':
        adj = v['덱 맞춘']
        v['label'] = ('확정(덱 맞춤 못 냄)' if adj is None else
                      '확정: 덱 섞임을 맞춰도 덜 잃는다' if adj['ratio'] > thr else '확정(덱 선택을 거친 차이)')
        v['A'] = '확정' if raw['A ratio'] > thr else '확정 안 됨'  # 고정 순서: B가 확정일 때만 A를 본다
    else:
        v['label'], v['A'] = raw['cell'], '숫자만(B가 확정이 아니라 칸을 매기지 않음)'
    print(f'→ 판정 「{v["label"]}」, A 「{v["A"]}」')
else:
    v['label'] = '미완(세 조건의 새 시드 실행이 다 있지 않다)'
    print(v['label'])

print('\n## 크기 보고: 세 시드 평균(시드 1 포함, 부풀 수 있음)과 처음 판정 표의 칸(덧붙임, 「확정」이라 부르지 않음)')
for c in CONDS:
    rs = [R[c, s] for s in SEEDS if 'missing' not in R[c, s]]
    if not rs:
        continue
    m = {key: statistics.mean(r[key] if key != 'lg' else r['lg'][0] for r in rs) for key in ('ab', 'level', 'floor', 'lg')}
    record.setdefault('means', {})[c] = dict(m, n=len(rs))
    print(f'{c} ({len(rs)}실행): A/B {m["ab"]:+.4f}, 레벨·골드 {m["lg"]:+.4f}, 일치율 레벨 {m["level"]:.3f}·남길 골드 {m["floor"]:.3f} '
          f'→ 칸 「{cell(m["ab"], m["level"], m["floor"])}」' + (' (A의 처음 질문)' if c == 'A' else ' (설명)'))
if len(SEEDS) > 1 and all('missing' not in R[c, s] for c in CONDS for s in SEEDS):
    vals, s_used, _, _ = pooled(SEEDS, 'lg')
    d3, se3 = statistics.mean(vals['B']) - statistics.mean(vals['2차']), s_used * (2 / len(SEEDS)) ** 0.5
    record['size_all_seeds'] = {'B − 2차': d3, 'se': se3}
    print(f'레벨·골드 몫 B − 2차, 시드 {SEEDS} 평균: {d3:+.4f} ± {se3:.4f} (시드 1 포함, 판정에 안 씀)')
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
