"""
계획 AI 평가(hra/plan_ai_design.md 6절).

ab   : AI 4자리 대 규칙 사람 봇 4자리(자리는 판마다 섞음). --net이 없으면 규칙 대 규칙(배관 검사). 등수 차는 규칙 자리 평균
       등수 - AI 자리 평균 등수라 양수면 AI가 낫다. 판정(신청서): 차 >= 0 이고 차 > 표준오차의 2배.
agree: 규칙 기록기 8명 판의 상태에서 AI가 고른 계획과 규칙의 계획이 같은 비율(갈래별, 셋 다). 어긋난 덱 짝을 센다.
meta : AI 8명 판의 계열별 몫·평균 등수. 롤체지지 10.24(실제)와, 사람 봇 덱 27개 고정 보드 대전(시뮬레이터 순서)과 순위
       상관을 여섯 큰 계열로 낸다. --net이 없으면 규칙 사람 봇 8명(비교 기준).

실행: python -m hra.evaluate ab --net checkpoints/plan_both_s1_best.pt --games 400 --jobs 7 --out results/plan_eval_ab_both_s1.json
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_bot import safe_play
from hra.plan_net import choose, load
from hra.score_rank import ROOT
from meta.decks_1024 import trait_counts
from meta.lobby import BOARDS, N_PLAYERS
from meta.pit import average, chosen_of
from meta.play_stats import family, family_table, real_families
from meta.real_boards import spearman

SIX = ('warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter')  # 사람 봇 메타 비교와 같은 여섯 큰 계열
SEED_AB, SEED_AGREE, SEED_META = 700000, 710000, 720000
_cache = {}


def greedy_planner(path):
    """저장한 신경망 -> 탐험 없는 계획기. 일꾼마다 마지막 하나만 붙들어 둔다(긴 학습에서 기억이 쌓이지 않게)."""
    if path not in _cache:
        _cache.clear()
        net, w, _ = load(path)
        _cache[path] = lambda s, m: choose(net, s, m, w)
    return _cache[path]


def ab_game(job):
    """(시드, 신경망 경로 또는 None) -> (시드, 규칙 평균 등수 - AI 평균 등수 또는 None, 오류)."""
    seed, path = job
    ai = set(random.Random(seed).sample(range(N_PLAYERS), N_PLAYERS // 2))
    planner = greedy_planner(path) if path else 'rule'
    out, err = safe_play(seed, [planner if i in ai else 'rule' for i in range(N_PLAYERS)])
    if out is None:
        return seed, None, err
    places = [s['place'] for s in out['seats']]
    return seed, (statistics.mean(places[i] for i in range(N_PLAYERS) if i not in ai)
                  - statistics.mean(places[i] for i in ai)), None


def ab(path, games, jobs=None, pool=None, seed0=SEED_AB):
    """A/B 결과. pool을 주면 그 일꾼들을 쓴다(자기 대전의 중간 점검)."""
    jobs_list = [(seed0 + k, path) for k in range(games)]
    if pool is not None:
        rows = list(pool.imap_unordered(ab_game, jobs_list))
    else:
        with Pool(jobs) as p:
            rows = list(p.imap_unordered(ab_game, jobs_list))
    diffs = [d for _, d, _ in rows if d is not None]
    errors = [e for _, _, e in rows if e]
    if not diffs:
        return {'diff': float('nan'), 'se': float('nan'), 'games': 0, 'errors': errors, 'pass': False, 'per_game': []}
    diff = statistics.mean(diffs)
    se = statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else float('nan')
    return {'diff': diff, 'se': se, 'games': len(diffs), 'errors': errors,
            'pass': bool(diff >= 0 and diff > 2 * se), 'per_game': diffs}


def agree_game(job):
    seed, path = job
    out, err = safe_play(seed, ['record'] * N_PLAYERS)
    if out is None:
        return [], err
    planner = greedy_planner(path)
    return [(tuple(int(i) for i in a), planner(s, m)) for seat in out['seats'] for s, m, a, *_ in seat['transitions']], None


def agree(path, games, jobs=None):
    with Pool(jobs) as p:
        results = p.map(agree_game, [(SEED_AGREE + k, path) for k in range(games)])
    pairs = [row for rows, _ in results for row in rows]
    same = np.array([[x == y for x, y in zip(rule, ai)] for rule, ai in pairs])
    name = lambda d: 'keep' if d == 0 else BOARDS[d - 1]['name']
    wrong = Counter((rule[0], ai[0]) for rule, ai in pairs if rule[0] != ai[0])
    return {'deck': float(same[:, 0].mean()), 'level': float(same[:, 1].mean()), 'floor': float(same[:, 2].mean()),
            'all': float(same.all(1).mean()), 'decisions': len(pairs),
            'deck_disagreements': [[name(a), name(b), n] for (a, b), n in wrong.most_common(10)],
            'errors': [e for _, e in results if e]}


def meta_game(job):
    seed, path = job
    planner = greedy_planner(path) if path else 'rule'
    out, err = safe_play(seed, [planner] * N_PLAYERS)
    if out is None:
        return [], err
    return [{'place': s['place'], 'board': s['board'], 'deck': s['deck'], 'switches': s['switches']}
            for s in out['seats']], None


def deck_family(board):
    """사람 봇 덱의 계열(완성 보드의 특성으로, meta/play_stats.family)."""
    return family(trait_counts(board['units'], board['items'], (chosen_of(board) or (None, None))[1]))[0]


def sim_order():
    """시뮬레이터 순서: 계열마다 그 계열 덱들의 고정 보드 대전 평균 승률(results/pit_1024.json의 human)."""
    win = average(json.load(open(os.path.join(ROOT, 'results', 'pit_1024.json'), encoding='utf-8'))['human'])
    rows = defaultdict(list)
    for b in BOARDS:
        rows[deck_family(b)].append(win[b['name']])
    return {f: statistics.mean(v) for f, v in rows.items()}


def meta(path, games, jobs=None):
    with Pool(jobs) as p:
        results = p.map(meta_game, [(SEED_META + k, path) for k in range(games)])
    players = [row for rows, _ in results for row in rows]
    table = family_table(players)  # (계열, 몫, 평균 등수)
    mine = {f: place for f, _, place in table}
    real = {f: place for f, _, place in real_families()}
    sim = sim_order()
    common = [f for f in SIX if f in mine and f in real]
    common_sim = [f for f in SIX if f in mine and f in sim]
    winners = [p['board'] for p in players if p['place'] == 1]
    fives = [u for b in winners for u in b['units'] if u[1] == 5]
    return {'families': [[f, share, place] for f, share, place in table],
            'rho_real': spearman([-mine[f] for f in common], [-real[f] for f in common]) if len(common) > 2 else None,
            'rho_sim': spearman([-mine[f] for f in common_sim], [sim[f] for f in common_sim]) if len(common_sim) > 2 else None,
            'families_compared': common, 'switches': statistics.mean(p['switches'] for p in players),
            'winner_level9': sum(b['level'] >= 9 for b in winners) / len(winners) if winners else None,
            'winner_five_two_star': sum(u[2] >= 2 for u in fives) / len(fives) if fives else None,
            'errors': [e for _, e in results if e]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['ab', 'agree', 'meta'])
    ap.add_argument('--net', default=None, help='저장한 신경망. 없으면 규칙 사람 봇(ab는 규칙 대 규칙)')
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    if args.kind == 'agree' and not args.net:
        ap.error('agree에는 --net이 필요하다')
    run = {'ab': ab, 'agree': agree, 'meta': meta}[args.kind]
    result = run(args.net, args.games, args.jobs)
    shown = {k: v for k, v in result.items() if k != 'per_game'}
    print(json.dumps(shown, ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'kind': args.kind, 'net': args.net and os.path.basename(args.net), 'games': args.games, **result},
                      f, ensure_ascii=False, indent=1)
        print(f'저장: {args.out}')


if __name__ == '__main__':
    main()
