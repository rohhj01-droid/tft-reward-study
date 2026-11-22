"""충실도 성적표(audit/fidelity.md) 12절: 레벨 9 관문 규칙 후보(meta/human_macro.nine_plan의 팔)를 여덟 자리 모두에 켜고 ⑤를 잰다.

hra.evaluate meta와 같은 판(시드 720000부터)을 같은 셈으로 센다. 다른 점은 자리가 교과서('rule') 대신 hra.spend_lesson의
팔 자리라는 것뿐이다. 팔 none은 교과서 그대로라 hra.evaluate meta와 같은 값이 나와야 한다(--check가 함께 돌려 견준다).

    TEXTBOOK=era ACTIONS_PER_TURN=60 python -m audit.fidelity_nine fast --games 400 --jobs 2 --out <파일>
    TEXTBOOK=era ACTIONS_PER_TURN=60 python -m audit.fidelity_nine none --games 4 --jobs 1 --check
"""
import argparse
import json
import statistics

import Simulator.pool
from hra.evaluate import SEED_META, SIX, sim_order
from hra.plan_bot import environment, pinned_pool, safe_play
from hra.spend_lesson import MADE, lesson
from meta.human_macro import NINE_ARMS
from meta.lobby import N_PLAYERS
from meta.play_stats import family_table, real_families
from meta.real_boards import spearman


def game(job):
    """(시드, 팔 또는 None) -> (자리마다 등수·보드·덱·갈아탄 수, 오류). hra.evaluate.meta_game과 같다."""
    seed, arm = job
    MADE.clear()  # 팔 자리가 판마다 쌓이지 않게(hra.spend_lesson.lesson_game과 같다)
    out, err = safe_play(seed, [lesson(arm)] * N_PLAYERS)
    if out is None:
        return [], err
    return [{'place': s['place'], 'board': s['board'], 'deck': s['deck'], 'switches': s['switches']} for s in out['seats']], None


def meta_arm(arm, games, jobs):
    """hra.evaluate.meta와 같은 셈(그 함수의 몸통을 옮겼다)."""
    with pinned_pool(jobs) as p:
        results = p.map(game, [(SEED_META + k, arm) for k in range(games)])
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


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('arm', choices=(*NINE_ARMS, 'none'))
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--out', default=None)
    ap.add_argument('--check', action='store_true', help='hra.evaluate meta를 같은 판으로 돌려 값이 같은지 본다(팔 none일 때)')
    a = ap.parse_args()
    arm = None if a.arm == 'none' else a.arm
    res = meta_arm(arm, a.games, a.jobs)
    print(json.dumps({k: v for k, v in res.items() if k != 'families'}, ensure_ascii=False))
    if a.check:
        from hra.evaluate import meta
        ref = meta(None, a.games, a.jobs)
        assert ref == res, {k: (ref[k], res[k]) for k in ref if ref[k] != res[k]}
        print('check: hra.evaluate meta와 같다')
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump({'kind': 'meta_nine', 'arm': a.arm, 'games': a.games, **environment(),
                       'chosen_shop_chance': getattr(Simulator.pool, 'CHOSEN_SHOP_CHANCE', 0.5), **res}, f, ensure_ascii=False, indent=1)
        print(f'저장: {a.out}')
