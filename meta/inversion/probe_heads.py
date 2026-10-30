"""헤드 가중치 사후 재조합 탐침(2026-10-30, 보상 실험 전 확인 1번): 학습한 계획 AI 저장본의 보상 갈래 가중치(등수·체력·이자·시너지·
유닛 수)를 결정 때만 바꿔서, AI 4자리 + 규칙 4자리 판(hra.evaluate ab와 같은 시드·같은 자리 뽑기)을 돌리고 자리마다 라운드별
레벨·골드·체력·계획(덱·레벨·남길 골드)을 적는다. 규칙 자리는 기록기(RuleRecorder: 규칙 그대로 두고 적기만 함)라 같은 항목을 같은
모양으로 남긴다. 요약은 등수·4등 안·1등·8등, 노선(4단계에 레벨 7에서 골드를 쓰고 안정 / 5-1까지 레벨 8 / 기다림), 덱 선택 조건
(후반 덱으로 갈 때 선택받은 자가 맞았나)을 AI와 규칙으로 나눠 낸다.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/probe_heads.py --net checkpoints/plan_margin_deck_s1_best.pt --hp 2 --games 400 --jobs 2 --out meta/inversion/probe_rows_best_hp2.json
    요약만(여러 파일을 나란히): python meta/inversion/probe_heads.py summary <json> [<json> ...]
가중치를 안 주면 저장본에 든 값 그대로다(등수 1, 체력 1, 이자 0.3, ...). 결과 JSON은 git에 안 올린다(meta/inversion/*.json).
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter

os.environ.setdefault('PYTHONHASHSEED', '0')
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Simulator.stats import COST
from hra.plan_bot import pinned_pool, safe_play
from hra.plan_net import choose, load
from hra.plan_state import FLOORS
from meta.lobby import BOARDS, N_PLAYERS

SEED_AB = 700000  # hra.evaluate와 같은 시드
HEADS = ('place', 'hp', 'econ', 'synergy', 'units')
LATE = {b['name'] for b in BOARDS if not b['slow'] and sum(COST[u] >= 4 for u in b['units']) > len(b['units']) / 2}
_cache = {}


def planner_for(path, overrides):
    """저장본 + 가중치 덮어쓰기 -> 탐험 없는 계획기(일꾼마다 하나 붙들어 둔다)."""
    key = (path, os.path.getmtime(path), overrides)
    if key not in _cache:
        _cache.clear()
        torch.set_num_threads(1)
        net, w, _ = load(path)
        w = dict(w)
        w.update(dict(overrides))
        _cache[key] = lambda s, m: choose(net, s, m, w)
    return _cache[key]


def trace(seat):
    """기록기의 경험 -> 라운드별 [칸, 레벨, 골드, 체력, 계획 덱 번호, 계획 레벨 단계, 계획 남길 골드 번호, 선택받은 자 맞음, 덱 유닛 값].
    상태 칸: 0 라운드/40, 1 체력/100, 2 골드/60, 3 레벨/9, 덱 i의 다섯 칸은 15 + 5i부터(값/40, 겹침, 선택받은 자 맞음, 아이템, 지금 덱)."""
    rows = []
    for s, m, a, *_ in seat['transitions']:
        d = int(a[0])
        base = 15 + 5 * (d - 1) if d > 0 else None
        rows.append([int(round(float(s[0]) * 40)), int(round(float(s[3]) * 9)), int(round(float(s[2]) * 60)),
                     int(round(float(s[1]) * 100)), d, int(a[1]), int(a[2]),
                     float(s[base + 2]) if base is not None else None, round(float(s[base]) * 40, 1) if base is not None else None])
    return rows


def game(job):
    seed, path, overrides = job
    ai = set(random.Random(seed).sample(range(N_PLAYERS), N_PLAYERS // 2))
    planner = planner_for(path, overrides)
    out, err = safe_play(seed, [planner if i in ai else 'record' for i in range(N_PLAYERS)])
    if out is None:
        return seed, None, err
    rows = []
    for i, seat in enumerate(out['seats']):
        rows.append(dict(seed=seed, seat=i, kind='ai' if i in ai else 'rule', place=seat['place'], deck=seat['deck'],
                         switches=seat['switches'], curve=trace(seat)))
    return seed, rows, None


# ---------- 요약 ----------

def slot_name(i):
    if i < 3:
        return f'1-{i + 2}'
    s, k = divmod(i - 3, 6)
    return f'{s + 2}-{[1, 2, 3, 5, 6, 7][k]}'


def se(xs):
    return statistics.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0.0


def mean(xs):
    return statistics.mean(xs) if xs else float('nan')


def line(curve):
    """노선: 4단계(15~20번째 칸)에 레벨 7로 골드를 20 아래까지 쓰면 「7 안정」, 아니면서 5-1(21) 시작까지 레벨 8이면 「빠른 8」
    (그 뒤 레벨 8로 20 아래까지 쓰면 「빠른 8 리롤」, 아니면 「빠른 8 안 씀」), 둘 다 아니면 「기다림」. 4-1 전에 죽으면 「4-1 전 탈락」."""
    if not curve or curve[-1][0] < 15:
        return '4-1 전 탈락'
    g7 = [c[2] for c in curve if 15 <= c[0] <= 20 and c[1] == 7]
    t8 = next((c[0] for c in curve if c[1] >= 8), None)
    g8 = [c[2] for c in curve if 18 <= c[0] <= 26 and c[1] >= 8]
    if g7 and min(g7) <= 20:
        return '7 안정'
    if t8 is not None and t8 <= 21:
        return '빠른 8 리롤' if g8 and min(g8) <= 20 else '빠른 8 안 씀'
    return '기다림'


def at(curve, slot):
    return next((c for c in curve if c[0] == slot), None)


def summary(files):
    data = []
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        data.append((d.get('label') or os.path.basename(f), d))
    print('### 조건 | 가중치(등수·체력·이자·시너지·유닛) | 판 | AI 등수 ± 표준오차 | 규칙 등수 | 차(규칙−AI, 판마다 짝) | AI 4등 안 / 1등 / 8등 | 규칙 4등 안 / 1등 / 8등 | AI 등수 표준편차')
    for label, d in data:
        rows = d['rows']
        ai = [r for r in rows if r['kind'] == 'ai']
        ru = [r for r in rows if r['kind'] == 'rule']
        by = {}
        for r in rows:
            by.setdefault(r['seed'], {'ai': [], 'rule': []})[r['kind']].append(r['place'])
        diffs = [mean(v['rule']) - mean(v['ai']) for v in by.values() if v['ai'] and v['rule']]
        w = d['weights']
        rate = lambda rs, f: f'{sum(f(r["place"]) for r in rs) / len(rs):.0%}'
        print(f'| {label} | {w["place"]:.1f}·{w["hp"]:.1f}·{w["econ"]:.1f}·{w["synergy"]:.1f}·{w["units"]:.1f} | {len(by)} | '
              f'{mean([r["place"] for r in ai]):.2f} ± {se([r["place"] for r in ai]):.2f} | {mean([r["place"] for r in ru]):.2f} | '
              f'{mean(diffs):+.2f} ± {se(diffs):.2f} | {rate(ai, lambda p: p <= 4)} / {rate(ai, lambda p: p == 1)} / {rate(ai, lambda p: p == 8)} | '
              f'{rate(ru, lambda p: p <= 4)} / {rate(ru, lambda p: p == 1)} / {rate(ru, lambda p: p == 8)} | '
              f'{statistics.pstdev([r["place"] for r in ai]):.2f} |')
    print('\n### 노선(AI 자리): 조건 | 7 안정 | 빠른 8 리롤 | 빠른 8 안 씀 | 기다림 | 4-1 전 탈락 | 노선별 등수(7 안정 / 빠른 8 리롤 / 빠른 8 안 씀 / 기다림)')
    for label, d in data:
        for kind in ['ai', 'rule']:
            rs = [r for r in d['rows'] if r['kind'] == kind]
            cl = Counter(line(r['curve']) for r in rs)
            n = len(rs)
            pl = lambda k: mean([r['place'] for r in rs if line(r['curve']) == k])
            print(f'| {label} {kind} | ' + ' | '.join(f'{cl[k] / n:.0%}' for k in ['7 안정', '빠른 8 리롤', '빠른 8 안 씀', '기다림', '4-1 전 탈락'])
                  + f' | {pl("7 안정"):.2f} / {pl("빠른 8 리롤"):.2f} / {pl("빠른 8 안 씀"):.2f} / {pl("기다림"):.2f} |')
    print('\n### 칸 시작 때 레벨 / 골드 / 체력 (살아 있던 자리 평균): 조건 | 4-1 | 4-5 | 5-1 | 5-5 | 4단계 최저 골드 | 5단계 최저 골드')
    for label, d in data:
        for kind in ['ai', 'rule']:
            rs = [r for r in d['rows'] if r['kind'] == kind]
            cells = []
            for slot in [15, 18, 21, 24]:
                pts = [at(r['curve'], slot) for r in rs]
                pts = [p for p in pts if p]
                cells.append(f'{mean([p[1] for p in pts]):.2f} / {mean([p[2] for p in pts]):.0f} / {mean([p[3] for p in pts]):.0f}' if pts else '-')
            low4 = [min(c[2] for c in r['curve'] if 15 <= c[0] <= 20) for r in rs if any(15 <= c[0] <= 20 for c in r['curve'])]
            low5 = [min(c[2] for c in r['curve'] if 21 <= c[0] <= 26) for r in rs if any(21 <= c[0] <= 26 for c in r['curve'])]
            print(f'| {label} {kind} | ' + ' | '.join(cells) + f' | {mean(low4):.0f} | {mean(low5):.0f} |')
    print('\n### 계획 갈래(AI 자리, 15~26번째 칸의 판단): 조건 | 레벨 그대로 / +1 / +2 | 남길 골드 안 함 / 50 / 30 / 20 / 10 / 0')
    for label, d in data:
        for kind in ['ai', 'rule']:
            pts = [c for r in d['rows'] if r['kind'] == kind for c in r['curve'] if 15 <= c[0] <= 26]
            if not pts:
                continue
            lv = Counter(c[5] for c in pts)
            fl = Counter(c[6] for c in pts)
            n = len(pts)
            print(f'| {label} {kind} | ' + ' / '.join(f'{lv[i] / n:.0%}' for i in range(3)) + ' | ' + ' / '.join(f'{fl[i] / n:.0%}' for i in range(len(FLOORS))) + ' |')
    print('\n### 덱: 조건 | 끝 덱 상위 5 | 후반 덱 몫 / 등수 | 갈아타기 | 후반 덱으로 들어간 때 선택받은 자 맞음 비율 / 들어간 칸(가운데)')
    for label, d in data:
        for kind in ['ai', 'rule']:
            rs = [r for r in d['rows'] if r['kind'] == kind]
            n = len(rs)
            top = Counter(r['deck'] for r in rs).most_common(5)
            late = [r for r in rs if r['deck'] in LATE]
            enters = [c for r in rs for c in r['curve'] if c[4] > 0 and BOARDS[c[4] - 1]['name'] in LATE]
            print(f'| {label} {kind} | ' + ', '.join(f'{k} {v / n:.0%}' for k, v in top) + f' | {len(late) / n:.0%} / {mean([r["place"] for r in late]):.2f} | '
                  f'{mean([r["switches"] for r in rs]):.2f} | ' + (f'{mean([c[7] for c in enters]):.0%} / {slot_name(statistics.median_low(c[0] for c in enters))}' if enters else '-') + ' |')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'summary':
        summary(sys.argv[2:])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('--net', required=True)
    for h in HEADS:
        ap.add_argument(f'--{h}', type=float, default=None, help=f'{h} 갈래 가중치 덮어쓰기(없으면 저장본 값)')
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--seed0', type=int, default=SEED_AB)
    ap.add_argument('--label', default=None)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    overrides = tuple((h, getattr(args, h)) for h in HEADS if getattr(args, h) is not None)
    _, saved, meta = load(args.net)
    weights = dict(saved)
    weights.update(dict(overrides))
    print('저장본 가중치', saved, '-> 쓰는 가중치', weights, flush=True)
    jobs = [(args.seed0 + k, args.net, overrides) for k in range(args.games)]
    rows, errors = [], []
    with pinned_pool(args.jobs) as pool:
        for seed, out, err in pool.imap_unordered(game, jobs):
            if out is None:
                errors.append((seed, err))
            else:
                rows.extend(out)
    label = args.label or (os.path.basename(args.net).replace('.pt', '') + ''.join(f'_{h}{v:g}' for h, v in overrides))
    json.dump({'label': label, 'net': os.path.basename(args.net), 'weights': weights, 'saved_weights': dict(saved), 'games': args.games,
               'errors': errors, 'rows': rows}, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'판 {len(rows) // N_PLAYERS}개(버림 {len(errors)}), 저장: {args.out}')
    summary([args.out])


if __name__ == '__main__':
    main()
