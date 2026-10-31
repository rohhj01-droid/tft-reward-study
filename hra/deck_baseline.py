"""
덱 고르기 기준선과 덱별 위험(돌아보기 2026-10-31의 6.1 3·4번). 학습은 없다.

risk     : 규칙 사람 봇 8명 판(기록기 자리. 행동은 규칙과 같다)에서 자리마다 2-1에 고른 덱, 끝 덱, 등수를 모아 덱마다
           자리 수, 평균 등수, 1등 비율, 4등 안 비율을 판 단위 부트스트랩 표준오차와 함께 낸다. 본 표는 2-1 덱으로 센
           것이다(덱을 고른 뒤 못 만든 판까지 들어간다). 끝 덱 표와 후반 덱 묶음 표는 참고로 함께 낸다.
           미리 정한 판정(결과 전, 2026-10-31): 2-1 덱으로 세어 Chosen Divines의 1등 비율이 Chosen Warlords보다 높고,
           Chosen Warlords의 4등 안 비율이 Chosen Divines보다 높으며, 두 차가 모두 표준오차의 2배를 넘으면 「덱 수준
           맞바꿈이 버틴다」. 하나라도 못 넘으면 「버티지 않는다」. 이 짝은 앞선 200판(「초반 시너지 필러」 기록)에서 본
           후보라 새 시드 구간으로 다시 잰다.
baseline : 덱 후보를 risk 결과(2-1 덱 표)에서 자리 100개 이상인 덱 가운데 평균 등수가 가장 좋은 셋으로만 줄인 규칙 사람 봇
           4자리 대 규칙 사람 봇 4자리 맞대결이다. 덱 점수, 갈아타기, 레벨, 골드, 사기는 규칙 그대로다. 시드와 자리 뽑기는
           계획 AI 맞대결(hra.evaluate.ab)과 같다.
           미리 정한 읽기(결과 전, 2026-10-31): AI 기준값은 같은 실행기(e707e5d)에서 잰 2차 최고 저장본
           (results/plan_eval_ab_margin_deck_s1_e707e5d.json)이다. 기준선 차가 「AI 차 - 2 × √(두 표준오차의 제곱합)」 이상이면
           「AI의 이득은 좋은 덱 고르기로 설명된다」. AI 차 - 기준선 차가 그 문턱을 넘으면 「AI가 기준선보다 낫다」.

실행: python -m hra.deck_baseline risk --games 800 --jobs 2 --out results/deck_risk_rule.json
      python -m hra.deck_baseline baseline --risk results/deck_risk_rule.json --games 400 --jobs 2 --out results/plan_eval_ab_topdecks.json
"""
import argparse
import json
import math
import os
import random
import statistics
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.evaluate import ab
from hra.plan_bot import pinned_pool, safe_play
from meta.human_bot import KNOBS, HumanPolicy, late_deck
from meta.human_deck import choose, copies, held_items, score, scout, units_of
from meta.lobby import BOARDS, N_PLAYERS
from Simulator.stats import round_stage

SEED_RISK = 730000  # 자기 대전·평가 구간(100000, 700000, 710000, 720000, 800000, 900000)과 겹치지 않는다
PAIR = ('Chosen Divines', 'Chosen Warlords')
BOOT, BOOT_SEED = 1000, 0


def risk_game(seed):
    """규칙 기록기 8명 한 판 -> (시드, 자리마다 {'first': 2-1 덱, 'final': 끝 덱, 'place'}, 오류). 기록기의 첫 경험은 늘
    2-1 판단이고(그때는 덱이 없어 「그대로」만 가린다), 그 덱 번호가 2-1에 고른 덱이다(hra/test_plan_game.py 첫 검사)."""
    out, err = safe_play(seed, ['record'] * N_PLAYERS)
    if out is None:
        return seed, [], err
    return seed, [{'first': BOARDS[int(s['transitions'][0][2][0]) - 1]['name'], 'final': s['deck'], 'place': s['place']}
                  for s in out['seats']], None


def _counts(games, key, names):
    """판마다 덱별 (자리 수, 등수 합, 1등 수, 4등 안 수) -> 배열 (판, 덱, 4)."""
    idx = {n: i for i, n in enumerate(names)}
    c = np.zeros((len(games), len(names), 4))
    for g, rows in enumerate(games):
        for r in rows:
            if r[key] in idx:
                c[g, idx[r[key]]] += (1, r['place'], r['place'] == 1, r['place'] <= 4)
    return c


def _rates(c):
    """(..., 덱, 4) 합 -> (평균 등수, 1등 비율, 4등 안 비율). 자리가 없으면 nan."""
    with np.errstate(invalid='ignore', divide='ignore'):
        return c[..., 1] / c[..., 0], c[..., 2] / c[..., 0], c[..., 3] / c[..., 0]


def _boot(c):
    """판을 다시 뽑은 BOOT번의 덱별 합 (BOOT, 덱, 4). 판마다 뽑힌 횟수(다항분포)를 가중치로 더한다."""
    w = np.random.default_rng(BOOT_SEED).multinomial(len(c), [1 / len(c)] * len(c), size=BOOT)
    return np.einsum('bg,gdk->bdk', w, c)


def _se(x):
    return float(np.nanstd(x, ddof=1))


def deck_table(games, key, boot=False):
    """덱 이름 -> {'seats', 'mean_place', 'first', 'top4'}(boot이면 각 표준오차 '..._se'도). key는 'first'나 'final'."""
    names = sorted({r[key] for rows in games for r in rows})
    c = _counts(games, key, names)
    mean, first, top4 = _rates(c.sum(0))
    table = {n: {'seats': int(c[:, i, 0].sum()), 'mean_place': float(mean[i]), 'first': float(first[i]),
                 'top4': float(top4[i])} for i, n in enumerate(names)}
    if boot:
        bm, bf, bt = _rates(_boot(c))
        for i, n in enumerate(names):
            table[n].update(mean_place_se=_se(bm[:, i]), first_se=_se(bf[:, i]), top4_se=_se(bt[:, i]))
    return table


def pair_check(games, a, b, key='first'):
    """덱 a가 b보다 1등이 많고 b가 a보다 4등 안이 많은가. first_diff = 1등 비율(a) - (b), top4_diff = 4등 안 비율(b) - (a).
    표준오차는 판 단위 부트스트랩이다. 두 차가 모두 표준오차의 2배를 넘으면 holds."""
    c = _counts(games, key, [a, b])
    _, f, t = _rates(c.sum(0))
    _, bf, bt = _rates(_boot(c))
    fd, td = float(f[0] - f[1]), float(t[1] - t[0])
    fse, tse = _se(bf[:, 0] - bf[:, 1]), _se(bt[:, 1] - bt[:, 0])
    return {'pair': [a, b], 'key': key, 'first_diff': fd, 'first_se': fse, 'top4_diff': td, 'top4_se': tse,
            'holds': bool(fd > 2 * fse and td > 2 * tse)}


def group_table(games, key='first'):
    """후반 덱(meta.human_bot.late_deck) 묶음 대 나머지."""
    late = {b['name'] for b in BOARDS if late_deck(b, KNOBS)}
    return deck_table([[dict(r, group='late' if r[key] in late else 'normal') for r in rows] for rows in games],
                      'group', boot=True)


def top_decks(table, k=3, min_seats=100):
    """자리가 min_seats 이상인 덱 가운데 평균 등수가 가장 좋은 k개(좋은 순서)."""
    return sorted((n for n, r in table.items() if r['seats'] >= min_seats), key=lambda n: table[n]['mean_place'])[:k]


class TopDecks(HumanPolicy):
    """덱 후보를 allowed로만 줄인 규칙 사람 봇(나머지는 규칙 그대로). pick_deck은 HumanPolicy.pick_deck을 그대로 옮기고
    후보 밖 덱의 점수만 -inf로 둔 것이다. 실행기의 pick_deck이 바뀌면 같이 고친다."""
    allowed = frozenset()

    def pick_deck(self, player, game_round):
        if self.board and self.flex():
            return
        completed, components = held_items(player)
        mine, others = copies(units_of(player)), scout(self.others)
        scores = [score(b, mine, player.chosen or None, completed, components, others, self.knobs)
                  if b['name'] in self.allowed else -math.inf for b in BOARDS]
        current = BOARDS.index(self.board) if self.board else None
        new = choose(scores, current, round_stage(game_round), self.rng, self.knobs)
        if new != current:
            if current is not None:
                self.switches += 1
            self.set_board(BOARDS[new])


_classes = {}


def topdecks(names):
    """덱 후보 names의 기준선 자리. hra.plan_bot.make_policy에 넘기는 정책 클래스다."""
    key = tuple(sorted(names))
    if key not in _classes:
        _classes[key] = type('TopDecks', (TopDecks,), {'allowed': frozenset(key)})
    return _classes[key]


def topdecks_game(job):
    """(시드, 덱 후보) -> (시드, 규칙 평균 등수 - 기준선 평균 등수 또는 None, 오류). 자리 뽑기는 hra.evaluate.ab_game과 같다."""
    seed, names = job
    base = set(random.Random(seed).sample(range(N_PLAYERS), N_PLAYERS // 2))
    out, err = safe_play(seed, [topdecks(names) if i in base else 'rule' for i in range(N_PLAYERS)])
    if out is None:
        return seed, None, err
    places = [s['place'] for s in out['seats']]
    return seed, (statistics.mean(places[i] for i in range(N_PLAYERS) if i not in base)
                  - statistics.mean(places[i] for i in base)), None


def risk(games, jobs=None, seed0=SEED_RISK):
    with pinned_pool(jobs) as p:
        rows = sorted(p.imap_unordered(risk_game, [seed0 + k for k in range(games)]), key=lambda r: r[0])
    ok, errors = [r for _, r, e in rows if not e], [e for _, _, e in rows if e]
    first = deck_table(ok, 'first', boot=True)
    return {'games': len(ok), 'errors': errors, 'pair': pair_check(ok, *PAIR, 'first'),
            'pair_final': pair_check(ok, *PAIR, 'final'), 'groups': group_table(ok, 'first'),
            'top3': top_decks(first), 'first': first, 'final': deck_table(ok, 'final', boot=True), 'rows': ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['risk', 'baseline'])
    ap.add_argument('--risk', default=None, help='baseline: 덱 후보를 고를 risk 결과 파일')
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    if args.kind == 'risk':
        result = risk(args.games, args.jobs)
    else:
        if not args.risk:
            ap.error('baseline에는 --risk가 필요하다')
        names = json.load(open(args.risk, encoding='utf-8'))['top3']
        result = {'decks': names, **ab(tuple(names), args.games, args.jobs, game=topdecks_game)}
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'per_game', 'first', 'final')},
                     ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'kind': args.kind, 'games_asked': args.games, **result}, f, ensure_ascii=False, indent=1)
        print(f'저장: {args.out}')


if __name__ == '__main__':
    main()
