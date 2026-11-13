"""
「돈 쓰는 때」 수업 규칙 대조(2026-11-13). 학습은 없다.

같은 판에서 규칙 사람 봇(교과서) 4자리는 그대로 두고 4자리에는 레벨 8 무렵의 돈 쓰는 규칙만 바꿔, 등수와 밸류덱(후반 덱)
완성이 달라지는지 잰다. 바꾸는 규칙은 2020년 10.24 무렵 글과 최근 시즌 글에서 모은 것이다(조사 보고서 「세트 4 덱별 운영법
조사」·「세트 4 운영법 최근 시즌 보충」). 4-5(18번째 칸) 전, 느린 리롤 덱, 체력이 40 아래인 자리는 교과서 그대로다.

팔 'roll' (굴리기만): 레벨 8이 되면 4코스트 이하 캐리가 모두 2성이 될 때까지 매 라운드 리롤한다. 남길 골드는 체력 60 이상이면
                     30, 40~59면 20이다. 그때까지는 5단계의 「50 넘는 몫은 레벨 9 경험치」를 미룬다. 교과서는 레벨 8을 찍는
                     4-5 라운드에만 10골드까지 리롤하고 그 밖에는 50을 지킨다.
팔 'full' (수업 전체): 위에 더해, 레벨 8은 올린 뒤에도 30골드가 남을 때 올린다. 5-1(21번째 칸)에는 돈과 상관없이 올린다.
                     기다리는 동안은 레벨 7에서 리롤하지 않는다. 교과서는 4-5부터 돈과 상관없이 올린다.
팔 'era' (4-1에는 조금만): 'full'에 더해, 4-1~4-3에 교과서가 20골드까지 리롤하려 할 때 30골드까지만 리롤한다. 행동 상한을
                     올리면 교과서의 4-1 리롤이 실제로 일어나 레벨 8에 빈손으로 가므로, 상한을 올린 조건에서 쓴다.
팔 'deep' (레벨 8에서 깊게): 'era'와 같되 레벨 8에서 남길 골드가 체력 60 이상이면 20, 40~59면 10이다.
팔 'none' (대조): 양쪽 모두 교과서다. 같은 시드에서 자리 뽑기만으로 생기는 차를 잰다.

자리 뽑기는 hra.evaluate.ab_game과 같고, 모든 팔이 같은 시드를 쓴다. 덱 묶음은 규칙이 바뀌기 전에 든 덱으로 나눈다
(두 쪽이 같은 기준이다. 기본은 4-5 시작 때 덱 deck18이고, 4-1부터 바꾸는 팔이 있으면 --group deck15로 4-1 시작 때 덱을 쓴다.
그 전에 탈락한 자리는 끝 덱).

실행: python -m hra.spend_lesson --arm full --games 400 --jobs 2 --partial logs/spend_full.jsonl --out results/spend_lesson_full.json
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
import config
from hra.deck_baseline import load_partial
from hra.plan_bot import pinned_pool, safe_play
from meta.human_bot import KNOBS, HumanPolicy, late_deck
from meta.human_macro import stable
from meta.lobby import BOARDS, N_PLAYERS
from Simulator.stats import COST

SEED_SPEND = 740000  # 다른 구간(100000, 700000, 710000, 720000, 730000, 800000, 900000)과 겹치지 않는다
KEEP_AFTER = 30      # 레벨 8을 올린 뒤 남아야 하는 골드. 'era'·'deep' 팔이 4-1에 남기는 골드이기도 하다
FLOORS = ((60, 30), (40, 20))  # 레벨 8에서 캐리 2성 전까지 (체력 하한, 남길 골드)
DEEP_FLOORS = ((60, 20), (40, 10))
ARMS = {'roll': (False, False, FLOORS), 'full': (True, False, FLOORS),  # 팔 -> (레벨 8을 기다리나, 4-1에 조금만 굴리나, 레벨 8 남길 골드)
        'era': (True, True, FLOORS), 'deep': (True, True, DEEP_FLOORS)}
FIRST_41, FIRST_SLOT, LAST_WAIT = 15, 18, 21  # 4-1, 4-5(여기부터 레벨 8 규칙을 바꾼다), 5-1(기다리지 않는다)
BOOT, BOOT_SEED = 1000, 0
LATE = {b['name'] for b in BOARDS if late_deck(b, KNOBS)}
SLOW = {b['name'] for b in BOARDS if b['slow']}
MADE = []  # 이 판에서 만든 정책(자리 순서). lesson_game이 판마다 비운다


def lesson_plan(base, arm, slot, level, gold, need, hp, steady, slow, k=KNOBS):
    """교과서의 (목표 레벨, 남길 골드, 경험치 우선) base를 수업 규칙으로 고친다. need는 다음 레벨까지 모자란 경험치다."""
    target, floor, exp_first = base
    wait, small41, floors = ARMS[arm]
    if slow or hp < k['hp_low'] or level >= 9:
        return base
    if slot < FIRST_SLOT:
        if small41 and slot >= FIRST_41 and floor is not None and floor < KEEP_AFTER:
            return target, KEEP_AFTER, exp_first
        return base
    if level < 8:
        if wait and level == 7 and slot < LAST_WAIT and gold - 4 * math.ceil(need / 4) < KEEP_AFTER:
            return level, None, False
        return base
    if steady:
        return base
    return target, next(f for h, f in floors if hp >= h), False


class Lesson(HumanPolicy):
    """수업 규칙 자리(arm이 None이면 교과서 그대로). 두 쪽 모두 라운드마다 [칸, 레벨, 골드, 체력]과 끝 상태를 적는다."""
    arm = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.curve, self.rolls8, self.deck15, self.deck18, self.carry2, self.four2 = [], 0, None, None, False, 0
        MADE.append(self)

    def __call__(self, player, shop, game_round, mask):
        first = game_round != self.last_round
        act = super().__call__(player, shop, game_round, mask)  # 라운드 첫 호출이면 여기서 덱을 고르거나 갈아탄다
        if first:
            self.curve.append([game_round, player.level, player.gold, player.health])
            if game_round >= FIRST_41 and self.deck15 is None and self.board:
                self.deck15 = self.board['name']
            if game_round >= FIRST_SLOT and self.deck18 is None and self.board:
                self.deck18 = self.board['name']
            self.carry2 = bool(self.board) and stable(player, self.board)
            self.four2 = sum(1 for row in player.board for u in row if u and COST.get(u.name) == 4 and u.stars >= 2)
        if act == '2' and player.level >= 8:
            self.rolls8 += 1
        return act

    def macro_plan(self, player, game_round):
        base = super().macro_plan(player, game_round)
        if self.arm is None or not self.board:
            return base
        need = player.level_costs[player.level] - player.exp if player.level < player.max_level else 0
        return lesson_plan(base, self.arm, game_round, player.level, player.gold, need, player.health,
                           stable(player, self.board), bool(self.board['slow']), self.knobs)


_classes = {}


def lesson(arm):
    """팔 arm(ARMS의 이름, 또는 교과서 그대로인 None)의 자리. hra.plan_bot.make_policy에 넘기는 정책 클래스다."""
    if arm not in _classes:
        _classes[arm] = type(f'Lesson_{arm}', (Lesson,), {'arm': arm})
    return _classes[arm]


def lesson_game(job):
    """(시드, 팔) -> (시드, 자리마다 기록, 오류). 수업 자리 4개는 hra.evaluate.ab_game처럼 시드로 뽑는다."""
    seed, arm = job
    picked = set(random.Random(seed).sample(range(N_PLAYERS), N_PLAYERS // 2))
    MADE.clear()
    out, err = safe_play(seed, [lesson(arm if i in picked else None) for i in range(N_PLAYERS)])
    if out is None:
        return seed, [], err
    return seed, [{'lesson': i in picked, 'deck': s['deck'], 'deck15': pol.deck15, 'deck18': pol.deck18, 'place': s['place'],
                   'carry2': pol.carry2, 'four2': pol.four2, 'rolls8': pol.rolls8, 'curve': pol.curve}
                  for i, (pol, s) in enumerate(zip(MADE, out['seats']))], None


def group(row, key='deck18'):
    deck = row.get(key) or row['deck']
    return 'late' if deck in LATE else 'slow' if deck in SLOW else 'normal'


def _arrival(row):
    """처음 레벨 8 이상으로 라운드를 시작한 [칸, 골드]. 없으면 None."""
    return next(([c[0], c[2]] for c in row['curve'] if c[1] >= 8), None)


FIELDS = ('seats', 'place', 'first', 'top4', 'carry2', 'four2', 'rolls8', 'reach8', 'lv8_slot', 'lv8_gold')


def _vector(row):
    a = _arrival(row)
    return (1, row['place'], row['place'] == 1, row['place'] <= 4, bool(row['carry2']), row['four2'] >= 1, row['rolls8'],
            a is not None, a[0] if a else 0, a[1] if a else 0)


def _rates(c):
    """(..., 필드) 합 -> 자리당 평균(레벨 8 도착 칸·골드는 도착한 자리당). 자리가 없으면 nan."""
    with np.errstate(invalid='ignore', divide='ignore'):
        r = c / c[..., :1]
        r[..., 8:] = c[..., 8:] / c[..., 7:8]
    return r


def _clean(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def summary(games, key='deck18'):
    """판마다 짝지은 등수 차(교과서 자리 평균 − 수업 자리 평균, 양수면 수업 쪽이 낫다)와 덱 묶음별 표.
    묶음 안의 차와 표준오차는 판 단위 부트스트랩이다(place_diff = 교과서 − 수업, 나머지 _diff = 수업 − 교과서)."""
    diffs = [statistics.mean(r['place'] for r in rows if not r['lesson']) - statistics.mean(r['place'] for r in rows if r['lesson'])
             for rows in games]
    names = ('late', 'normal', 'slow', 'all')
    c = np.zeros((len(games), len(names), 2, len(FIELDS)))  # 판, 묶음, (수업, 교과서), 필드
    for g, rows in enumerate(games):
        for r in rows:
            for n in (group(r, key), 'all'):
                c[g, names.index(n), 0 if r['lesson'] else 1] += _vector(r)
    w = np.random.default_rng(BOOT_SEED).multinomial(len(games), [1 / len(games)] * len(games), size=BOOT)
    total, boot = _rates(c.sum(0)), _rates(np.einsum('bg,gnsf->bnsf', w, c))
    groups = {}
    for i, n in enumerate(names):
        cell = {}
        for j, side in enumerate(('lesson', 'rule')):
            cell[side] = {'seats': int(c[:, i, j, 0].sum()), 'mean_place': _clean(float(total[i, j, 1])),
                          **{f: _clean(float(total[i, j, k])) for k, f in enumerate(FIELDS) if k >= 2}}
        for f, k, sign in (('place', 1, -1), ('first', 2, 1), ('top4', 3, 1), ('carry2', 4, 1), ('four2', 5, 1)):
            cell[f + '_diff'] = _clean(float(sign * (total[i, 0, k] - total[i, 1, k])))
            cell[f + '_se'] = _clean(float(np.nanstd(boot[:, i, 0, k] - boot[:, i, 1, k], ddof=1))) if len(games) > 1 else None
        groups[n] = cell
    return {'games': len(games), 'diff': statistics.mean(diffs) if diffs else None,
            'se': statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else None, 'per_game': diffs, 'groups': groups}


def gap_stats(games, key='deck18'):
    """8자리 모두 교과서인 실행(팔 none)의 묶음별 표와 「밸류덱 − 보통 덱」 평균 등수 차 gap(클수록 밸류덱이 밀린다).
    수업 자리 표시는 보지 않는다. 표준오차는 판 단위 부트스트랩이다."""
    names = ('late', 'normal', 'slow')
    c = np.zeros((len(games), len(names), len(FIELDS)))
    for g, rows in enumerate(games):
        for r in rows:
            c[g, names.index(group(r, key))] += _vector(r)
    w = np.random.default_rng(BOOT_SEED).multinomial(len(games), [1 / len(games)] * len(games), size=BOOT)
    total, boot = _rates(c.sum(0)), _rates(np.einsum('bg,gnf->bnf', w, c))
    se = lambda x: _clean(float(np.nanstd(x, ddof=1)))
    out = {n: {'seats': int(c[:, i, 0].sum()), 'mean_place': _clean(float(total[i, 1])),
               **{f: _clean(float(total[i, k])) for k, f in enumerate(FIELDS) if k >= 2},
               'mean_place_se': se(boot[:, i, 1]), 'first_se': se(boot[:, i, 2]), 'top4_se': se(boot[:, i, 3]),
               'carry2_se': se(boot[:, i, 4])} for i, n in enumerate(names)}
    out['gap'] = float(total[0, 1] - total[1, 1])
    out['gap_se'] = se(boot[:, 0, 1] - boot[:, 1, 1])
    return out


def cap_effect(low, high):
    """행동 상한이 낮은 실행과 높은 실행의 gap_stats -> 밸류덱이 밀리는 폭이 준 양(gap_drop, 양수면 상한을 올렸을 때 덜 밀린다)과
    밸류덱 안정 비율이 는 양(carry2_rise). 두 실행은 따로 돈 판이라 표준오차를 제곱해 더한다."""
    return {'gap_drop': low['gap'] - high['gap'], 'gap_drop_se': math.hypot(low['gap_se'], high['gap_se']),
            'carry2_rise': high['late']['carry2'] - low['late']['carry2'],
            'carry2_rise_se': math.hypot(low['late']['carry2_se'], high['late']['carry2_se'])}


def _by_seed(res):
    seeds = res.get('seeds') or [res['seed0'] + k for k in range(res['games_asked'])]
    assert len(seeds) == len(res['per_game']), '버린 판이 있는 옛 결과는 시드를 맞출 수 없다'
    return dict(zip(seeds, res['per_game']))


def adjusted(arm, none):
    """수업 팔의 판별 차에서 같은 시드의 대조 실행(양쪽 모두 교과서) 판별 차를 뺀 값. 자리 뽑기만으로 생긴 차를 덜어 낸다."""
    a, n = _by_seed(arm), _by_seed(none)
    d = [a[s] - n[s] for s in a if s in n]
    return {'games': len(d), 'diff': statistics.mean(d), 'se': statistics.stdev(d) / len(d) ** 0.5 if len(d) > 1 else None}


def run(arm, games, jobs=None, seed0=SEED_SPEND, partial=None, key='deck18'):
    """팔 arm을 games판. partial을 주면 끝난 판마다 그 파일에 한 줄씩 적고, 다시 부르면 적힌 판은 건너뛴다(노트북이 꺼져도 이어 간다)."""
    done = load_partial(partial)
    todo = [seed0 + k for k in range(games) if seed0 + k not in done]
    if todo:
        with pinned_pool(jobs) as p, open(partial or os.devnull, 'a', encoding='utf-8') as f:
            for row in p.imap_unordered(lesson_game, [(s, arm) for s in todo]):
                done[row[0]] = row
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
    rows = [done[seed0 + k] for k in range(games)]
    good = [list(r) for _, r, e in rows if e is None]
    return {'kind': 'spend', 'arm': arm, 'games_asked': games, 'seed0': seed0, 'actions_per_turn': config.ACTIONS_PER_TURN,
            'keep_after': KEEP_AFTER, 'floors': FLOORS, 'errors': [[s, e] for s, _, e in rows if e is not None],
            'seeds': [s for s, _, e in rows if e is None],
            'group_key': key, **summary(good, key), 'rows': good}


def line(res):
    """끝에 찍는 한 줄. 판이 하나면 표준오차가 없다."""
    se = '' if res['se'] is None else f" ± {res['se']:.3f}"
    return f"{res['arm']} 판 {res['games']} 오류 {len(res['errors'])} 차 {res['diff']:+.3f}{se}"


def parse(argv=None):
    """명령줄 인자. --arm none은 양쪽 모두 교과서인 대조 실행이다(자리 뽑기 흔들림을 잰다)."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=(*ARMS, 'none'), required=True)
    ap.add_argument('--group', choices=('deck15', 'deck18'), default='deck18')
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--seed0', type=int, default=SEED_SPEND)
    ap.add_argument('--partial')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    a.arm = None if a.arm == 'none' else a.arm
    return a


if __name__ == '__main__':
    a = parse()
    res = run(a.arm, a.games, a.jobs, a.seed0, a.partial, a.group)
    json.dump(res, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)  # 자리별 곡선이 들어 있어 줄바꿈 없이 적는다
    print(line(res), {n: (g['place_diff'], g['place_se']) for n, g in res['groups'].items()})
