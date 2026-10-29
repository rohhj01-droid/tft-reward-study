"""후반 덱의 초반 운영 진단(코드 안 바꿈, 2026-10-29): 사람 봇 판을 돌려 자리마다 라운드별 곡선(레벨·골드·체력·보드 값·2성 수·
덱 유닛 수)과 끝 상태(목표 덱·등수·레벨·끝 칸·4코스트 별·캐리 2성·선택받은 자)를 모은다. 판 목록은 diag_loot와 같은 시드 0의
앞 N판이라 같은 N이면 같은 판이다.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/diag_flex.py 200 4 <결과.json>     요약만: python meta/inversion/diag_flex.py summary <결과.json>
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
import meta.human_bot as hb
from meta import lobby
from meta.human_five import board_units
from meta.lobby import BOARDS, carriers
from meta.play_stats import family, real_families

POL, LOG = [], []
_attach = hb.attach_human


def attach(player, *a, **k):
    pol = _attach(player, *a, **k)
    pol.player_ref = player
    POL.append(pol)
    return pol


hb.attach_human = attach
_call = hb.HumanPolicy.__call__


def worth(units):
    """보드 값: 유닛마다 비용 × 3^(별 - 1)의 합."""
    return sum(COST[u.name] * 3 ** (u.stars - 1) for u in units)


def call(self, player, shop, game_round, mask):
    if game_round != self.last_round:  # 라운드 첫 행동(정책이 last_round를 바꾸기 전)
        units = [u for _, _, u in board_units(player)]
        LOG.append((id(self), game_round, player.level, player.gold, player.health, worth(units),
                    sum(u.stars >= 2 for u in units), sum(u.name in self.units for u in units)))
    return _call(self, player, shop, game_round, mask)


hb.HumanPolicy.__call__ = call


def run(game):
    POL.clear()
    LOG.clear()
    res = lobby.play(game, bot='human')
    curve = defaultdict(list)
    for pid, *row in LOG:
        curve[pid].append(row)
    out = []
    for pol, rec in zip(POL, res['players']):
        p = pol.player_ref
        units = [u for _, _, u in board_units(p)]
        four = [u for u in units if COST[u.name] == 4]
        car = carriers(pol.board) if pol.board else []
        out.append(dict(deck=pol.board['name'] if pol.board else None, place=rec['place'], level=p.level,
                        fam=family(rec['board']['traits'])[0], end=curve[id(pol)][-1][0], switches=pol.switches,
                        mode=pol.mode, four=len(four), four2=sum(u.stars >= 2 for u in four),
                        carry2=sum(any(u.name == c and u.stars >= 2 for u in units) for c in car) / max(1, len(car)),
                        five=sum(COST[u.name] == 5 for u in units),
                        chosen=next((u.chosen for u in units if u.chosen), None), curve=curve[id(pol)]))
    return out


# 후반 덱: 느린 리롤 덱이 아니고 4코스트 이상 유닛이 절반을 넘는 덱(meta.human_bot.late_deck와 같은 기준)
LATE = {b['name'] for b in BOARDS if not b['slow'] and sum(COST[u] >= 4 for u in b['units']) > len(b['units']) / 2}
CHECK = [3, 6, 10, 13, 15, 18, 21, 24, 27]  # 2-1, 2-5, 3-2, 3-6, 4-1, 4-5, 5-1, 5-5, 6-1
SIX = ['warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter']


def slot_name(i):
    if i < 3:
        return f'1-{i + 2}'
    s, k = divmod(i - 3, 6)
    return f'{s + 2}-{[1, 2, 3, 5, 6, 7][k]}'


def se(xs):
    return statistics.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0.0


def group(title, rows):
    n = len(rows)
    if n < 10:
        return
    pl = [r['place'] for r in rows]
    four = sum(r['four'] for r in rows)
    print(f'\n### {title}: {n}자리, 평균 등수 {statistics.mean(pl):.2f} ± {se(pl):.2f}, 4등 안 {sum(p <= 4 for p in pl) / n:.0%}, '
          f'8등 {sum(p == 8 for p in pl) / n:.0%}, 끝 칸(가운데) {slot_name(statistics.median_low(r["end"] for r in rows))}, '
          f'레벨 {statistics.mean(r["level"] for r in rows):.2f}, 4코스트 {four / n:.2f}장(2성 이상 {sum(r["four2"] for r in rows) / max(1, four):.0%}), '
          f'캐리 2성 {statistics.mean(r["carry2"] for r in rows):.0%}, 5코스트 {statistics.mean(r["five"] for r in rows):.2f}장, '
          f'선택받은 자 없음 {sum(r["chosen"] is None for r in rows) / n:.0%}, 갈아타기 {statistics.mean(r["switches"] for r in rows):.2f}번, '
          f'연패형 {sum(r["mode"] == "lose" for r in rows) / n:.0%}')
    print('| 칸 시작 | 살아 있음 | 체력 | 골드 | 레벨 | 보드 값 | 2성 수 | 덱 유닛 |')
    print('|---|---|---|---|---|---|---|---|')
    for slot in CHECK:
        pts = [c for r in rows for c in r['curve'] if c[0] == slot]
        if not pts:
            continue
        m = lambda i: statistics.mean(c[i] for c in pts)
        print(f'| {slot_name(slot)} | {len(pts) / n:.0%} | {m(3):.1f} | {m(2):.1f} | {m(1):.2f} | {m(4):.1f} | {m(5):.2f} | {m(6):.2f} |')


def summary(rows):
    n = len(rows)
    print(f'자리 {n}개, 판 {n // lobby.N_PLAYERS}개. 후반 덱: {sorted(LATE)}')
    print('목표 덱 몫(마지막):', [(d, f'{c / n:.1%}') for d, c in Counter(r['deck'] for r in rows).most_common(12)])
    group('후반 덱(4코스트 이상이 절반 넘는 덱)', [r for r in rows if r['deck'] in LATE])
    group('그 밖의 덱', [r for r in rows if r['deck'] not in LATE])
    for name in ['Chosen Dusks', 'Dusk Cultists', 'Chosen Divines', 'Vanguard Mystics', 'Adept Mystics',
                 'Chosen Warlords', 'Chosen Cultists', 'Ninja Shades', 'Chosen Duelists']:
        group(name, [r for r in rows if r['deck'] == name])
    print('\n### 덱별(30자리 이상), 끝났을 때')
    print('| 덱 | 자리 | 평균 등수 | 끝 칸(가운데) | 레벨 | 4코스트 2성 이상 | 캐리 2성 |')
    print('|---|---|---|---|---|---|---|')
    for name, c in Counter(r['deck'] for r in rows).most_common():
        rs = [r for r in rows if r['deck'] == name]
        if len(rs) < 30:
            continue
        pl = [r['place'] for r in rs]
        print(f'| {name}{" (후반)" if name in LATE else ""} | {len(rs)} | {statistics.mean(pl):.2f} ± {se(pl):.2f} | '
              f'{slot_name(statistics.median_low(r["end"] for r in rs))} | {statistics.mean(r["level"] for r in rs):.2f} | '
              f'{sum(r["four2"] for r in rs) / max(1, sum(r["four"] for r in rs)):.0%} | {statistics.mean(r["carry2"] for r in rs):.0%} |')
    bot = {f: statistics.mean(r['place'] for r in rows if r['fam'] == f) for f in SIX if any(r['fam'] == f for r in rows)}
    real = {f: a for f, s, a in real_families() if f in bot}
    print('\n### 마지막 보드 계열(여섯): 봇 몫, 봇 평균 등수 / 실제 평균 등수')
    for f in sorted(bot, key=bot.get):
        print(f'- {f}: {sum(r["fam"] == f for r in rows) / n:.1%}, {bot[f]:.2f} / {real[f]:.2f}' if f in real else f'- {f}: {bot[f]:.2f}')
    if len(bot) == 6 and len(real) == 6:
        rank = lambda v: {k: i for i, k in enumerate(sorted(v, key=v.get))}
        rb, rr = rank(bot), rank(real)
        print(f'실제와 순위 상관: {1 - 6 * sum((rb[k] - rr[k]) ** 2 for k in bot) / 210:.2f}')
    first = [r for r in rows if r['place'] == 1]
    print(f'\n1등 {len(first)}자리: 레벨 9 {sum(r["level"] >= 9 for r in first) / len(first):.0%}, '
          f'5코스트 {statistics.mean(r["five"] for r in first):.2f}장, 계열 {Counter(r["fam"] for r in first).most_common(6)}')


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
