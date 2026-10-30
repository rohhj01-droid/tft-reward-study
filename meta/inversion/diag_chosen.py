"""선택받은 자 진단(코드 안 바꿈, 2026-10-30): 사람 봇 판을 돌려 자리마다 상점에 나온 선택받은 자(덱 유닛인지, 그때 골드·벤치·들고 있던
선택받은 자·살 수 있었는지·샀는지), 선택받은 자를 산 때와 판 때, 칸마다 들고 있던 선택받은 자를 모은다. 판 목록은 diag_flex와 같은
시드 0의 앞 N판이라 같은 N이면 같은 판이다. 왜: Chosen Dusks 자리의 34%가 덱의 선택받은 자 없이 끝나고 그 자리가 6.25등(있으면
4.74등)이라, 안 나온 것인지 나왔는데 못 산 것인지 가른다(results/README 「4-1~4-5 전환 시험」 읽은 것 5).

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/diag_chosen.py 200 4 <결과.json>     요약만: python meta/inversion/diag_chosen.py summary <결과.json>
"""
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

os.environ.setdefault('PYTHONHASHSEED', '0')
from Simulator.stats import COST
from Simulator.utils import x_y_to_1d_coord
import meta.human_bot as hb
from meta import lobby
from meta.human_deck import units_of
from meta.human_five import board_units
from meta.lobby import BOARDS

POL, OFFERS, EVENTS, HELD = [], {}, [], []
_attach = hb.attach_human


def attach(player, *a, **k):
    pol = _attach(player, *a, **k)
    pol.player_ref = player
    POL.append(pol)
    return pol


hb.attach_human = attach
_call = hb.HumanPolicy.__call__


def held_chosen(player):
    """들고 있는 선택받은 자 유닛(보드나 벤치). 없으면 None."""
    return next((u for u in units_of(player) if u.chosen), None)


def unit_at(player, coord):
    if coord >= 28:
        return player.bench[coord - 28]
    return next((u for x, y, u in board_units(player) if x_y_to_1d_coord(x, y) == coord), None)


def bucket(slot):
    return '4-1 전' if slot < 15 else ('4-1~4-5' if slot < 18 else '4-5부터')


def call(self, player, shop, game_round, mask):
    pid = id(self)
    deck = self.units or set()
    if game_round != self.last_round:  # 라운드 첫 행동: 들고 있는 선택받은 자
        h = held_chosen(player)
        HELD.append((pid, game_round, h.name if h else None, bool(h and h.name in deck)))
    new = []
    for i, unit in enumerate(shop):
        if not unit or not unit.endswith('_c'):  # 산 칸은 None
            continue
        key = (pid, game_round, i, unit)
        if key in OFFERS:
            continue
        name, trait = unit.split('_')[:2]
        h = held_chosen(player)
        OFFERS[key] = dict(slot=game_round, name=name, trait=trait, deck=name in deck, cost=3 * COST[name], gold=player.gold,
                           holding=h.name if h else None, holding_deck=bool(h and h.name in deck), bench_full=player.bench_full(),
                           mask=bool(mask[47 + i][0]), level=player.level, flex=self.flex(), bought=False, act=None)
        new.append(key)
    act = _call(self, player, shop, game_round, mask)
    for key in new:  # 처음 본 때 봇이 대신 한 행동(「규칙이 안 삼」을 읽을 때 쓴다)
        OFFERS[key]['act'] = act
    if act and act.startswith('3_'):
        i = int(act[2:])
        unit = shop[i]
        if unit and unit.endswith('_c'):
            OFFERS[(pid, game_round, i, unit)]['bought'] = True
            name = unit.split('_')[0]
            EVENTS.append((pid, game_round, 'buy', name, name in deck))
    elif act and act.startswith('4_'):
        u = unit_at(player, int(act[2:]))
        if u is not None and u.chosen:
            EVENTS.append((pid, game_round, 'sell', u.name, u.name in deck))
    return act


hb.HumanPolicy.__call__ = call


def run(game):
    POL.clear()
    OFFERS.clear()
    EVENTS.clear()
    HELD.clear()
    res = lobby.play(game, bot='human')
    out = []
    for pol, rec in zip(POL, res['players']):
        pid = id(pol)
        p = pol.player_ref
        h = held_chosen(p)
        units = pol.units or set()
        out.append(dict(deck=pol.board['name'] if pol.board else None, place=rec['place'], level=p.level, switches=pol.switches,
                        end_chosen=h.name if h else None, end_deck_chosen=bool(h and h.name in units),
                        offers=[v for k, v in OFFERS.items() if k[0] == pid],
                        events=[(r, kind, n, d) for q, r, kind, n, d in EVENTS if q == pid],
                        held=[(r, n, d) for q, r, n, d in HELD if q == pid]))
    return out


def slot_name(i):
    if i < 3:
        return f'1-{i + 2}'
    s, k = divmod(i - 3, 6)
    return f'{s + 2}-{[1, 2, 3, 5, 6, 7][k]}'


def reason(o):
    """덱 선택받은 자를 안 산 까닭(처음 본 때의 상태). 사는 규칙: 덱 유닛이고, 선택받은 자가 없고, 골드가 비용 이상이고, 마스크가 열림."""
    if o['holding'] is not None:
        return '덱 선택받은 자 이미 있음' if o['holding_deck'] else '덱 밖 선택받은 자 들고 있음'
    if o['gold'] < o['cost']:
        return '골드 모자람'
    if not o['mask']:
        return '마스크 닫힘(벤치 등)'
    return '규칙이 안 삼'


def first_deck_buy(r):
    return next((slot for slot, kind, n, d in r['events'] if kind == 'buy' and d), None)


def group(title, rows):
    n = len(rows)
    if n < 10:
        return
    deck_offers = [[o for o in r['offers'] if o['deck']] for r in rows]
    got = [r for r in rows if r['end_deck_chosen']]
    miss = [r for r in rows if not r['end_deck_chosen']]
    mean_place = lambda rs: statistics.mean(r['place'] for r in rs) if rs else float('nan')
    print(f'\n### {title}: {n}자리, 평균 등수 {mean_place(rows):.2f}, 끝에 덱 선택받은 자 {len(got) / n:.0%}'
          f'(있음 {mean_place(got):.2f}등, 없음 {mean_place(miss):.2f}등)')
    print(f'- 상점에 나온 선택받은 자: 자리마다 {statistics.mean(len(r["offers"]) for r in rows):.1f}개, 그중 덱 유닛 '
          f'{statistics.mean(len(d) for d in deck_offers):.2f}개, 덱 유닛이 한 번도 안 나온 자리 {sum(not d for d in deck_offers) / n:.0%}')
    flat = [o for d in deck_offers for o in d]
    if flat:
        print(f'- 덱 선택받은 자가 나왔을 때: 산 비율 {sum(o["bought"] for o in flat) / len(flat):.0%}, 안 산 까닭 '
              f'{Counter(reason(o) for o in flat if not o["bought"]).most_common()}')
        odd = [o for o in flat if not o['bought'] and reason(o) == '규칙이 안 삼']
        if odd:
            print(f'  - 「규칙이 안 삼」 때 봇이 대신 한 행동(앞 글자): {Counter((o["act"] or "0")[0] for o in odd).most_common()}, '
                  f'칸 {Counter(slot_name(o["slot"]) for o in odd).most_common(5)}')
        for k in ['4-1 전', '4-1~4-5', '4-5부터']:
            os_ = [o for o in flat if bucket(o['slot']) == k]
            if os_:
                print(f'  - {k}: 나옴 {len(os_)}개(자리마다 {len(os_) / n:.2f}), 삼 {sum(o["bought"] for o in os_) / len(os_):.0%}, '
                      f'비용별 {sorted(Counter(o["cost"] for o in os_).items())}, 안 산 까닭 '
                      f'{Counter(reason(o) for o in os_ if not o["bought"]).most_common(3)}')
    if miss:
        seen = [r for r in miss if any(o['deck'] for o in r['offers'])]
        print(f'- 끝에 덱 선택받은 자가 없는 {len(miss)}자리 중 덱 선택받은 자를 본 자리 {len(seen)}개({len(seen) / len(miss):.0%}); 본 자리의 안 산 까닭 '
              f'{Counter(reason(o) for r in seen for o in r["offers"] if o["deck"] and not o["bought"]).most_common()}')
        held_nondeck = [r for r in miss if any(nm is not None and not d for _, nm, d in r['held'][2:])]
        print(f'  - 그중 2-1 뒤에 덱 밖 선택받은 자를 들고 있던 자리 {len(held_nondeck)}개, 끝에 덱 밖 선택받은 자를 든 자리 '
              f'{sum(r["end_chosen"] is not None for r in miss)}개, 갈아타기 평균 {statistics.mean(r["switches"] for r in miss):.2f}번')
    firsts = [(r, first_deck_buy(r)) for r in got]
    firsts = [(r, f) for r, f in firsts if f is not None]
    if firsts:
        c = Counter(bucket(f) for _, f in firsts)
        print(f'- 덱 선택받은 자를 처음 산 때: {dict(c)} (가운데 {slot_name(statistics.median_low(f for _, f in firsts))})')
        for k in ['4-1 전', '4-1~4-5', '4-5부터']:
            rs = [r for r, f in firsts if bucket(f) == k]
            if rs:
                print(f'  - {k}에 산 자리 {len(rs)}개: 평균 등수 {mean_place(rs):.2f}')
    sells = [e for r in rows for e in r['events'] if e[1] == 'sell']
    buys_nd = [e for r in rows for e in r['events'] if e[1] == 'buy' and not e[3]]
    print(f'- 덱 밖 선택받은 자 삼 {len(buys_nd)}번(자리마다 {len(buys_nd) / n:.2f}), 선택받은 자 팖 {len(sells)}번'
          f'(덱 밖 {sum(not e[3] for e in sells)}, 덱 {sum(e[3] for e in sells)})')


def summary(rows):
    n = len(rows)
    print(f'자리 {n}개, 판 {n // lobby.N_PLAYERS}개')
    allo = [o for r in rows for o in r['offers']]
    share = {l: f'{sum(o["cost"] == 12 for o in allo if o["level"] == l) / max(1, sum(o["level"] == l for o in allo)):.0%}'
             for l in range(3, 10)}
    print(f'상점 선택받은 자 전체 {len(allo)}개: 비용별 {sorted(Counter(o["cost"] // 3 for o in allo).items())}, 레벨별 4코스트 몫 {share}')
    group('모든 자리', rows)
    for name in ['Chosen Dusks', 'Dusk Cultists', 'Chosen Divines', 'Chosen Warlords', 'Chosen Cultists', 'Chosen Duelists', 'Chosen Keepers']:
        group(name, [r for r in rows if r['deck'] == name])
    group('후반 덱 아닌 Chosen 덱 전부', [r for r in rows if r['deck'] and r['deck'].startswith('Chosen')
                                 and r['deck'] not in ('Chosen Dusks', 'Chosen Divines')])


if __name__ == '__main__':
    if sys.argv[1] == 'summary':
        summary(json.load(open(sys.argv[2], encoding='utf-8')))
        sys.exit()
    n, jobs, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(jobs) as pool:
        rows = [r for o in pool.map(run, games, chunksize=1) for r in o]
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    summary(rows)
