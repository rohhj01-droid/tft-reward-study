"""노선 강제 대조(2026-10-30, 보상 실험 전 확인 3번): 같은 판에서 규칙 사람 봇 4자리는 그대로 두고 4자리에는 4단계 노선을 강제해, 노선의
선택이 등수를 얼마나 가르는지(그리고 체력·골드 상태에 따라 달라지는지)를 잰다. 실행기가 노선 차이를 결과로 만들어 내지 못하면 학습 AI에
노선 결정을 맡겨도 배울 게 없다.

DIAG_VARIANT=stab7 : 4-1~4-3(15~17번째 칸)에 레벨 7을 넘지 않고 10골드까지 리롤한다(7에서 안정). 4-5부터는 규칙대로.
DIAG_VARIANT=fast8 : 4-1~4-3에 리롤하지 않고(50 지킴) 레벨 7까지만, 4-5(18)에 레벨 8로 올리고 10골드까지 리롤한다(빠른 8). 4-6부터는 규칙대로.
자리 뽑기는 hra.evaluate ab와 같다(시드마다 4자리). 판 목록은 diag_flex와 같은 시드 0의 앞 N판.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    DIAG_VARIANT=stab7 python meta/inversion/diag_line.py 200 2 meta/inversion/diag_line_rows_stab7.json
    요약만: python meta/inversion/diag_line.py summary <json> [<json> ...]
"""
import json
import os
import random
import statistics
import sys
from collections import defaultdict
from multiprocessing import Pool

os.environ.setdefault('PYTHONHASHSEED', '0')
from Simulator.stats import COST
import meta.human_bot as hb
from meta import lobby
from meta.human_five import board_units
from meta.lobby import BOARDS

VARIANT = os.environ.get('DIAG_VARIANT', 'stab7')
POL, LOG = [], []
_attach = hb.attach_human
_plan = hb.HumanPolicy.macro_plan
_call = hb.HumanPolicy.__call__
FORCED = set()


def attach(player, *a, **k):
    pol = _attach(player, *a, **k)
    pol.player_ref = player
    pol.forced = len(POL) in FORCED
    POL.append(pol)
    return pol


def macro_plan(self, player, game_round):
    target, floor, exp_first = _plan(self, player, game_round)
    if not getattr(self, 'forced', False):
        return target, floor, exp_first
    if VARIANT == 'stab7' and 15 <= game_round <= 17:
        return min(target, 7), 10, False
    if VARIANT == 'fast8':
        if 15 <= game_round <= 17:
            return min(target, 7), None, False
        if game_round == 18:
            return max(target, 8), 10, False
    return target, floor, exp_first


def call(self, player, shop, game_round, mask):
    if game_round != self.last_round:
        units = [u for _, _, u in board_units(player)]
        LOG.append((id(self), game_round, player.level, player.gold, player.health,
                    sum(COST[u.name] * 3 ** (u.stars - 1) for u in units)))
    return _call(self, player, shop, game_round, mask)


hb.attach_human = attach
hb.HumanPolicy.macro_plan = macro_plan
hb.HumanPolicy.__call__ = call
LATE = {b['name'] for b in BOARDS if not b['slow'] and sum(COST[u] >= 4 for u in b['units']) > len(b['units']) / 2}


def run(game):
    POL.clear()
    LOG.clear()
    FORCED.clear()
    FORCED.update(random.Random(game[0]).sample(range(lobby.N_PLAYERS), lobby.N_PLAYERS // 2))
    res = lobby.play(game, bot='human')
    curve = defaultdict(list)
    for pid, *row in LOG:
        curve[pid].append(row)
    out = []
    for pol, rec in zip(POL, res['players']):
        out.append(dict(game=game[0], forced=pol.forced, deck=pol.board['name'] if pol.board else None, place=rec['place'],
                        level=pol.player_ref.level, switches=pol.switches, curve=curve[id(pol)]))
    return out


def se(xs):
    return statistics.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0.0


def mean(xs):
    return statistics.mean(xs) if xs else float('nan')


def at(curve, slot):
    return next((c for c in curve if c[0] == slot), None)


def summary(files):
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        rows, var = d['rows'], d['variant']
        by = defaultdict(lambda: {'f': [], 'r': []})
        for r in rows:
            by[r['game']]['f' if r['forced'] else 'r'].append(r)
        diffs = [mean([x['place'] for x in v['f']]) - mean([x['place'] for x in v['r']]) for v in by.values() if v['f'] and v['r']]
        forced = [r for r in rows if r['forced']]
        rule = [r for r in rows if not r['forced']]
        print(f'\n### {var}: 판 {len(by)}개. 강제 자리 등수 {mean([r["place"] for r in forced]):.2f}, 규칙 자리 {mean([r["place"] for r in rule]):.2f}, '
              f'판마다 짝지은 차(강제−규칙) {mean(diffs):+.2f} ± {se(diffs):.2f}; 4등 안 {sum(r["place"] <= 4 for r in forced) / len(forced):.0%} 대 '
              f'{sum(r["place"] <= 4 for r in rule) / len(rule):.0%}, 8등 {sum(r["place"] == 8 for r in forced) / len(forced):.0%} 대 {sum(r["place"] == 8 for r in rule) / len(rule):.0%}')
        print('| 4-1 시작 상태 | 강제 자리 수, 등수 | 규칙 자리 수, 등수 | 차 |')
        print('|---|---|---|---|')
        bands = [('체력 60 이상', lambda c: c[3] >= 60), ('체력 40~59', lambda c: 40 <= c[3] < 60), ('체력 40 미만', lambda c: c[3] < 40),
                 ('골드 50 이상', lambda c: c[2] >= 50), ('골드 50 미만', lambda c: c[2] < 50),
                 ('후반 덱', None), ('그 밖의 덱', None)]
        for name, cond in bands:
            def pick(rs):
                out = []
                for r in rs:
                    c = at(r['curve'], 15)
                    if c is None:
                        continue
                    if cond is None:
                        if (name == '후반 덱') == (r['deck'] in LATE):
                            out.append(r)
                    elif cond(c):
                        out.append(r)
                return out
            fa, ru = pick(forced), pick(rule)
            print(f'| {name} | {len(fa)}, {mean([r["place"] for r in fa]):.2f} | {len(ru)}, {mean([r["place"] for r in ru]):.2f} | {mean([r["place"] for r in fa]) - mean([r["place"] for r in ru]):+.2f} |')
        print('칸 시작 레벨 / 골드 / 체력 (강제 자리 → 규칙 자리):')
        for slot in [15, 18, 21, 24]:
            cells = []
            for rs in (forced, rule):
                pts = [at(r['curve'], slot) for r in rs]
                pts = [p for p in pts if p]
                cells.append(f'{mean([p[1] for p in pts]):.2f} / {mean([p[2] for p in pts]):.0f} / {mean([p[3] for p in pts]):.0f} ({len(pts) / len(rs):.0%} 생존)')
            print(f'  {slot}: {cells[0]} → {cells[1]}')


if __name__ == '__main__':
    if sys.argv[1] == 'summary':
        summary(sys.argv[2:])
        sys.exit()
    n, jobs, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    print('변형:', VARIANT)
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(jobs) as pool:
        rows = [r for o in pool.map(run, games, chunksize=1) for r in o]
    json.dump({'variant': VARIANT, 'rows': rows}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    summary([out])
