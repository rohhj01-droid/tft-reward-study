"""4단계 보드 기록 진단(판정 없음, 2026-11-24, results/README 「밸류덱의 4단계 보드」): 교과서 여덟 자리 판을 다시 돌리면서
대전마다 두 보드와 승패를 적는다. 판 자체는 바꾸지 않는다(같은 시드면 hra/spend_lesson의 대조 기록과 자리별 곡선이 같다).

대전 하나 = {'round': 칸, 'ghost': 유령 대전인가, 'pnum': [파랑, 빨강], 'deck': 두 쪽 정책의 지금 목표 덱, 'mode': 연승·연패형,
'level', 'hp': 대전 직전 값, 'tiers': 시뮬레이터가 센 켜진 특성 단계(0이 아닌 것), 'board': 유닛마다 [이름, 별, 아이템, 선택받은 자],
'won': 0 비김 · 1 파랑 이김 · 2 빨강 이김, 'damage': 진 쪽 피해}. 3-1(칸 9)부터 5-5(칸 24)까지의 대전만 적는다.
유령 대전은 파랑만 결과를 받는다(빨강은 다른 살아 있는 자리의 보드다).

실행(저장소 맨 위에서, TEXTBOOK=era ACTIONS_PER_TURN=30 PYTHONHASHSEED=0, PYTHONPATH에 june·stubs·.):
    python meta/inversion/board4.py --games 400 --jobs 4 --seed0 790000 --partial logs/board4.jsonl --out meta/inversion/board4_rows.json
확인: python meta/inversion/board4.py --check 2 meta/inversion/nine_none.json  (그 기록 앞 2판을 다시 돌려 곡선과 대전 기록을 맞춘다)
"""
import argparse
import json
import os
import sys

import config  # june의 config(실행기와 같은 가져오기 순서: PYTHONPATH의 june이 먼저다)
import hra.spend_lesson as sl
from hra.deck_baseline import load_partial
from hra.plan_bot import pinned_pool
from meta.human_bot import KNOBS
from meta.inversion.hp_split import pvp
from Simulator import champion
from Simulator.game_round import Game_Round

FIRST, LAST = 9, 24  # 3-1 ~ 5-5
FIGHTS, POL, NOW = [], {}, {'round': None, 'ghost': [], 'k': 0}

_call = sl.Lesson.__call__


def call(self, player, shop, game_round, mask):
    self.pnum = player.player_num
    POL[player.player_num] = self
    return _call(self, player, shop, game_round, mask)


_combat = Game_Round.combat_phase


def combat_phase(self, players, player_round):
    keep = FIRST <= player_round <= LAST
    NOW.update(round=player_round if keep else None, ghost=[m[1] == 'ghost' for m in self.matchups], k=0)
    try:
        out = _combat(self, players, player_round)
    finally:
        NOW['round'] = None
    assert not keep or NOW['k'] == len(self.matchups), (player_round, NOW['k'], len(self.matchups))
    return out


def side(p):
    pol = POL.get(p.player_num)
    deck = pol.board['name'] if pol is not None and pol.board else None
    units = [[u.name, u.stars, list(u.items), u.chosen or None] for row in p.board for u in row if u]
    return deck, getattr(pol, 'mode', None), p.level, p.health, {t: v for t, v in p.team_tiers.items() if v}, units


_run = champion.run


def run_battle(champion_q, p1, p2, round_damage=0):
    if NOW['round'] is None:  # 몬스터 라운드와 기록 칸 밖
        return _run(champion_q, p1, p2, round_damage)
    a, b = side(p1), side(p2)
    rec = {'round': NOW['round'], 'ghost': NOW['ghost'][NOW['k']], 'pnum': [p1.player_num, p2.player_num]}
    NOW['k'] += 1
    rec.update(zip(('deck', 'mode', 'level', 'hp', 'tiers', 'board'), map(list, zip(a, b))))
    won, damage = _run(champion_q, p1, p2, round_damage)
    rec.update(won=won, damage=damage)
    FIGHTS.append(rec)
    return won, damage


sl.Lesson.__call__, Game_Round.combat_phase, champion.run = call, combat_phase, run_battle


def game(seed):
    """시드 -> (시드, {'rows': hra.spend_lesson과 같은 자리 기록 + 'pnum', 'fights': 대전 기록}, 오류)."""
    FIGHTS.clear()
    POL.clear()
    s, rows, err = sl.lesson_game((seed, None, False))
    if err is not None:
        return seed, None, err
    for row, pol in zip(rows, sl.MADE):
        row['pnum'] = pol.pnum
    return seed, {'rows': rows, 'fights': list(FIGHTS)}, None


def run(games, jobs, seed0, partial):
    done = load_partial(partial)
    todo = [seed0 + k for k in range(games) if seed0 + k not in done]
    if todo:
        with pinned_pool(jobs) as p, open(partial or os.devnull, 'a', encoding='utf-8') as f:
            for row in p.imap_unordered(game, todo):
                done[row[0]] = row
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
    rows = [done[seed0 + k] for k in range(games)]
    good = [(s, r) for s, r, e in rows if e is None]
    return {'kind': 'board4', 'seed0': seed0, 'games_asked': games, 'actions_per_turn': config.ACTIONS_PER_TURN,
            'textbook': {k: KNOBS[k] for k in ('spend', 'lose_5')}, 'record': [FIRST, LAST],
            'errors': [[s, e] for s, _, e in rows if e is not None], 'seeds': [s for s, _ in good],
            'rows': [r['rows'] for _, r in good], 'fights': [r['fights'] for _, r in good]}


def consistent(rows, fights):
    """한 판의 대전 기록이 자리 곡선과 맞는지 본다. 맞으면 대전 수를 돌려준다."""
    by = {r['pnum']: r for r in rows}
    hp = {r['pnum']: {c[0]: c[3] for c in r['curve']} for r in rows}
    n = 0
    for slot in range(FIRST, LAST + 1):
        alive = sorted(p for p in by if slot in hp[p])
        got = [f for f in fights if f['round'] == slot]
        if not pvp(slot) or not alive:
            assert not got, slot
            continue
        own = sorted(x for f in got for x in (f['pnum'] if not f['ghost'] else f['pnum'][:1]))
        assert own == alive, (slot, own, alive)  # 살아 있는 자리마다 자기 대전이 꼭 하나
        for f in got:
            sides = (0,) if f['ghost'] else (0, 1)
            for i in sides:
                p = f['pnum'][i]
                assert f['hp'][i] == hp[p][slot], (slot, p)  # 대전 직전 체력 = 그 라운드 시작 체력
                lost = f['won'] == 0 or f['won'] == 2 - i
                nxt = hp[p].get(slot + 1)
                if nxt is not None:
                    assert nxt == hp[p][slot] - (f['damage'] if lost else 0), (slot, p, f['won'], f['damage'])
            n += 1
    return n


def check(n, ref):
    d = json.load(open(ref, encoding='utf-8'))
    assert d['textbook'] == {k: KNOBS[k] for k in ('spend', 'lose_5')} and d['actions_per_turn'] == config.ACTIONS_PER_TURN, '환경이 기록과 다르다'
    assert d['arm'] is None and not d['everyone']
    total = 0
    for k in range(n):
        seed = d['seeds'][k]
        s, out, err = game(seed)
        assert err is None, err
        mine = [{x: v for x, v in r.items() if x != 'pnum'} for r in out['rows']]
        assert mine == d['rows'][k], f'시드 {seed}: 자리 기록이 대조와 다르다'
        assert sorted(r['pnum'] for r in out['rows']) == list(range(len(mine)))
        total += consistent(out['rows'], out['fights'])
        print(f'시드 {seed}: 자리 기록 같음, 대전 {len(out["fights"])}개 맞음')
    print(f'확인 끝: {n}판, 체력까지 맞춘 대전 쪽 {total}개')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', nargs=2, metavar=('N', 'REF'))
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--seed0', type=int, default=790000)
    ap.add_argument('--partial')
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.check:
        check(int(a.check[0]), a.check[1])
        sys.exit()
    res = run(a.games, a.jobs, a.seed0, a.partial)
    json.dump(res, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"board4 판 {len(res['rows'])} 오류 {len(res['errors'])} 대전 {sum(map(len, res['fights']))}")
