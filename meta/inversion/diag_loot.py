"""전리품 진단(코드 안 바꿈): 사람 봇 판을 돌리면서 자리마다 PvE 구슬과 회전초밥에서 받은 아이템, 아이템 칸이 꽉 차서 잃은 아이템,
PvE 승패, 살아 있던 마지막 칸을 기록한다. diag_dusk와 같은 판 목록(시드 0)의 앞 N판이라 판이 같다.
쓰는 법: python -m meta.inversion.diag_loot 200 2          (N판, 일꾼 수; 자리별 기록은 diag_loot_rows.json)
        python -m meta.inversion.diag_loot summary <rows.json>
칸 번호는 시뮬레이터 game_round 표의 번호다: 0 = 1-1 회전초밥 + 1-2, 1 = 1-3, 2 = 1-4, 3 = 2-1, …, 6 = 2-4 회전초밥 + 2-5,
8 = 2-7(돌거북), 14 = 3-7(늑대), 20 = 4-7(칼날부리), 26 = 5-7(넥서스 미니언), 32 = 6-7, 38 = 7-7(협곡의 전령)."""
import json
import os
import random
import statistics
import sys
from collections import Counter
from multiprocessing import Pool

os.environ.setdefault('PYTHONHASHSEED', '0')
from meta import lobby
from meta.play_stats import family
from Simulator import game_round as gr
from Simulator import minion as mn
from Simulator.item_stats import basic_items, item_builds
from Simulator.player import Player
from Simulator.stats import COST
import meta.human_bot as hb

POL = []
orig_attach = hb.attach_human


def attach(player, *a, **k):
    pol = orig_attach(player, *a, **k)
    pol.player_ref = player
    POL.append(pol)
    return pol


hb.attach_human = attach

LOG = []            # (player_num, 칸, 종류, 값)  종류: orb(구슬 보상 이름) / carousel(아이템 이름) / lost(아이템 이름) / pve(win·loss)
ALIVE = []          # (칸, 살아 있는 player_num 목록)
CUR = {'round': 0}

_play = gr.Game_Round.play_game_round


def play_game_round(self):
    CUR['round'] = self.current_round
    ALIVE.append((self.current_round, [p.player_num for p in self.PLAYERS.values() if p]))
    return _play(self)


gr.Game_Round.play_game_round = play_game_round


def holdings(p):
    """플레이어가 가진 아이템 전부(아이템 칸 + 벤치 유닛 + 보드 유닛)."""
    c = Counter(it for it in p.item_bench if it)
    for u in list(p.bench) + [u for row in p.board for u in row]:
        if u:
            c.update(u.items)
    return c


_carousel = gr.carousel


def carousel(players, r, pool_obj):
    live = [p for p in players if p]
    before = {p.player_num: holdings(p) for p in live}
    _carousel(players, r, pool_obj)
    for p in live:
        gained = holdings(p) - before[p.player_num]
        if not gained:
            LOG.append((p.player_num, r, 'carousel', 'none'))
        for it, n in gained.items():
            LOG.extend([(p.player_num, r, 'carousel', it)] * n)


gr.carousel = carousel

_combat = mn.minion_combat


def minion_combat(player, enemy, round, *a, **k):
    won = _combat(player, enemy, round, *a, **k)
    LOG.append((player.player_num, round, 'pve', 'win' if won else 'loss'))
    return won


mn.minion_combat = minion_combat

_give = mn.give_loot


def give_loot(player, reward):
    LOG.append((player.player_num, CUR['round'], 'orb', reward))
    return _give(player, reward)


mn.give_loot = give_loot

_add = Player.add_to_item_bench


def add_to_item_bench(self, item):
    ok = _add(self, item)
    if ok is False:
        LOG.append((self.player_num, CUR['round'], 'lost', f'{item}@{sys._getframe(1).f_code.co_name}'))
    return ok


Player.add_to_item_bench = add_to_item_bench


def run(game):
    POL.clear()
    LOG.clear()
    ALIVE.clear()
    res = lobby.play(game, bot='human')
    game_end = max(r for r, _ in ALIVE)
    out = []
    for pol, rec in zip(POL, res['players']):
        p = pol.player_ref
        mine = [(r, kind, v) for num, r, kind, v in LOG if num == p.player_num]
        out.append(dict(deck=pol.board['name'] if pol.board else None, place=rec['place'], level=p.level,
                        fam=family(rec['board']['traits'])[0], num=p.player_num,
                        end=max(r for r, alive in ALIVE if p.player_num in alive), game_end=game_end,
                        orb=[(r, v) for r, k, v in mine if k == 'orb'],
                        carousel=[(r, v) for r, k, v in mine if k == 'carousel'],
                        lost=[(r, v) for r, k, v in mine if k == 'lost'],
                        pve=[(r, v) for r, k, v in mine if k == 'pve'],
                        held=dict(holdings(p)),
                        board_done=sum(1 for row in p.board for u in row if u and u.name in COST
                                       for it in u.items if it in item_builds),
                        units=[(u.name, COST[u.name], u.stars, [it for it in u.items if it in item_builds])
                               for row in p.board for u in row if u and u.name in COST]))
    return out


# ---- 집계 ----
ORB_ITEM = {'one_item': 1, 'full_item': 2, 'spatula': 1}
ORB_GOLD = {'three_gold': 3, 'six_gold': 6, 'ten_gold': 10, 'two_cost_one_gold': 1, 'champion_duplicator_one_gold': 1,
            'champion_duplicator_one_gold_two_cost': 1, 'champion_duplicator_five_gold': 5}
ORB_CHAMP = {'three_cost': 3, 'two_cost_one_gold': 2, 'three_one_costs': 3, 'three_two_costs': 6, 'two_three_costs': 6,
             'two_five_costs': 10, 'champion_duplicator_one_gold_two_cost': 2}
CONSUMABLE = {'champion_duplicator', 'reforger', 'magnetic_remover', 'loaded_dice', 'neekos_help', 'item_remover'}
STAGE_END = [(2, '1-4'), (8, '2-7'), (14, '3-7'), (20, '4-7'), (26, '5-7'), (32, '6-7'), (38, '7-7')]


def label(i):
    if i < 3:
        return f'1-{i + 2}'
    s, k = divmod(i - 3, 6)
    return f'{s + 2}-{[1, 2, 3, 5, 6, 7][k]}'


def item_value(it):
    """조각 환산: 조각·뒤집개 1, 완성 아이템(상징·자연의 힘·도적의 장갑 포함) 2, 소모품 0."""
    if it in basic_items:
        return 1
    if it in item_builds:
        return 2
    return 0


def orb_value(r, upto):
    return sum(ORB_ITEM.get(v, 0) for rr, v in r['orb'] if rr <= upto)


def car_value(r, upto):
    return sum(item_value(v) for rr, v in r['carousel'] if rr <= upto and v != 'none')


def m(xs):
    return statistics.mean(xs) if xs else 0


def sd(xs):
    return statistics.pstdev(xs) if len(xs) > 1 else 0


def summary(rows):
    n = len(rows)
    print(f'자리 {n}개, 판 {n // 8}개')
    print('목표 덱 몫(마지막):', [(d, f'{c / n:.1%}') for d, c in Counter(r['deck'] for r in rows).most_common(6)])
    print()
    print('### 칸별 누적 아이템(조각 환산, 그 칸까지 살아 있던 자리)')
    print('| 칸 | 자리 | PvE 구슬 | 회전초밥 | 합 | 합의 표준편차 | 합 분포(개: 자리 비율) |')
    print('|---|---|---|---|---|---|---|')
    for upto, name in STAGE_END:
        alive = [r for r in rows if r['end'] >= upto]
        if not alive:
            continue
        tot = [orb_value(r, upto) + car_value(r, upto) for r in alive]
        dist = ' '.join(f'{k}:{c / len(alive):.0%}' for k, c in sorted(Counter(tot).items()))
        print(f'| {name}까지 | {len(alive)} | {m([orb_value(r, upto) for r in alive]):.2f} | {m([car_value(r, upto) for r in alive]):.2f} | '
              f'{m(tot):.2f} | {sd(tot):.2f} | {dist} |')
    games = [rows[i:i + 8] for i in range(0, n, 8)]
    print('같은 판 안의 자리 사이 표준편차(판마다 재서 평균): 1단계 PvE 조각', f'{m([sd([orb_value(r, 2) for r in g]) for g in games]):.2f}',
          '| 4-7까지 받은 합(4-7까지 살아 있던 자리)', f'{m([sd([orb_value(r, 20) + car_value(r, 20) for r in g if r["end"] >= 20]) for g in games]):.2f}')
    print()
    s1 = Counter(orb_value(r, 2) for r in rows)
    print('1단계(1-2~1-4) PvE 조각 수 분포:', {k: f'{c / n:.0%}' for k, c in sorted(s1.items())},
          f'| 1단계 구슬 골드 평균 {m([sum(ORB_GOLD.get(v, 0) for rr, v in r["orb"] if rr <= 2) for r in rows]):.1f}, '
          f'챔피언 값 평균 {m([sum(ORB_CHAMP.get(v, 0) for rr, v in r["orb"] if rr <= 2) for r in rows]):.1f}')
    print()
    print('### 등수별, 끝났을 때')
    print('| 등수 | 자리 | 끝 칸(가운데) | PvE 구슬 | 회전초밥 | 받은 합 | 잃음 | 가진 것(환산) | 보드 완성 아이템 | 받은 복제기 | 받은 뒤집개 | 구슬 골드 | 구슬 챔피언 값 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for place in range(1, 9):
        rs = [r for r in rows if r['place'] == place]
        if not rs:
            continue
        ends = sorted(r['end'] for r in rs)
        held = [sum(item_value(it) * k for it, k in r['held'].items()) for r in rs]
        print(f'| {place} | {len(rs)} | {label(ends[len(ends) // 2])} | {m([orb_value(r, 99) for r in rs]):.2f} | {m([car_value(r, 99) for r in rs]):.2f} | '
              f'{m([orb_value(r, 99) + car_value(r, 99) for r in rs]):.2f} | {m([len(r["lost"]) for r in rs]):.2f} | {m(held):.2f} | '
              f'{m([r["board_done"] for r in rs]):.2f} | {m([sum(1 for _, v in r["orb"] if v.startswith("champion_duplicator")) for r in rs]):.2f} | '
              f'{m([sum(1 for _, v in r["orb"] if v == "spatula") + sum(1 for _, v in r["carousel"] if v == "spatula") for r in rs]):.2f} | '
              f'{m([sum(ORB_GOLD.get(v, 0) for _, v in r["orb"]) for r in rs]):.1f} | {m([sum(ORB_CHAMP.get(v, 0) for _, v in r["orb"]) for r in rs]):.1f} |')
    print()
    first = [r for r in rows if r['place'] == 1]
    print('1등 보드 완성 아이템 분포:', sorted(Counter(r['board_done'] for r in first).items()),
          '| 가운데 값', sorted(r['board_done'] for r in first)[len(first) // 2])
    print('1등이 받은 합 분포:', sorted(Counter(orb_value(r, 99) + car_value(r, 99) for r in first).items()))
    print('판 길이(마지막 칸) 분포:', sorted(Counter(label(r['game_end']) for r in rows if r['place'] == 1).items(), key=lambda kv: int(kv[0].split('-')[0]) * 10 + int(kv[0].split('-')[1])),
          '| 가운데 값', label(sorted(r['game_end'] for r in first)[len(first) // 2]))
    print()
    pve = Counter((label(r_), v) for r in rows for r_, v in r['pve'])
    rounds = sorted({r_ for r in rows for r_, _ in r['pve']})
    print('PvE 진 비율(칸: 진 자리/싸운 자리):', {label(x): f'{pve[(label(x), "loss")]}/{pve[(label(x), "loss")] + pve[(label(x), "win")]}' for x in rounds})
    lost = Counter(v for r in rows for _, v in r['lost'])
    print('아이템 칸이 꽉 차서 잃은 것(전체 자리 합):', sum(lost.values()), lost.most_common(6))
    car_none = sum(1 for r in rows for _, v in r['carousel'] if v == 'none')
    car_all = sum(len(r['carousel']) for r in rows)
    print(f'회전초밥에서 아이템을 못 받은 경우: {car_none}/{car_all}', Counter(v for r in rows for _, v in r['carousel'] if v not in basic_items and v != 'none').most_common(6))
    print('구슬 보상 종류(전체 자리 합):', Counter(v for r in rows for _, v in r['orb']).most_common())
    print()
    print('### 덱별(목표 덱), 끝났을 때')
    print('| 덱 | 자리 | 평균 등수 | 끝 칸(가운데) | 받은 합 | 4-7까지 받은 합(살아 있던 자리) | 보드 완성 |')
    print('|---|---|---|---|---|---|---|')
    for deck, _ in Counter(r['deck'] for r in rows).most_common(9):
        rs = [r for r in rows if r['deck'] == deck]
        ends = sorted(r['end'] for r in rs)
        a47 = [r for r in rs if r['end'] >= 20]
        print(f'| {deck} | {len(rs)} | {m([r["place"] for r in rs]):.2f} | {label(ends[len(ends) // 2])} | {m([orb_value(r, 99) + car_value(r, 99) for r in rs]):.2f} | '
              f'{m([orb_value(r, 20) + car_value(r, 20) for r in a47]):.2f} ({len(a47)}) | {m([r["board_done"] for r in rs]):.2f} |')


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1] == 'summary':
        summary(json.load(open(sys.argv[2], encoding='utf-8')))
        sys.exit()
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    with Pool(jobs) as pool:
        rows = [r for out in pool.map(run, games, chunksize=1) for r in out]
    json.dump(rows, open(os.path.join(here, 'diag_loot_rows.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    summary(rows)
