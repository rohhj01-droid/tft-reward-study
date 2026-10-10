"""황혼 진단(코드 안 바꿈): 사람 봇 판을 돌려 목표 덱별 마지막 보드를 모은다. play_stats와 같은 판 목록(시드 0)의 앞 N판."""
import os, random, sys, statistics
from collections import Counter, defaultdict
from multiprocessing import Pool
os.environ.setdefault('PYTHONHASHSEED', '0')
from meta import lobby
from meta.play_stats import family
from meta.human_five import deck_family
from Simulator.item_stats import item_builds
from Simulator.stats import COST
import meta.human_bot as hb

POL = []
orig = hb.attach_human
def attach(player, *a, **k):
    pol = orig(player, *a, **k)
    pol.player_ref = player
    POL.append(pol)
    return pol
hb.attach_human = attach

def run(game):
    POL.clear()
    res = lobby.play(game, bot='human')
    decks = [pol.board['name'] if pol.board else None for pol in POL]
    out = []
    for i, (pol, rec) in enumerate(zip(POL, res['players'])):
        p = pol.player_ref
        units = [u for row in p.board for u in row if u and u.name in COST]
        chosen = next(((u.name, u.chosen) for u in units if u.chosen), None)
        bench_chosen = next(((u.name, u.chosen) for u in p.bench if u and u.chosen), None)
        out.append(dict(deck=decks[i], place=rec['place'], level=p.level, fam=family(rec['board']['traits'])[0],
                        traits=rec['board']['traits'], contest=decks.count(decks[i]) - 1,
                        units=[(u.name, COST[u.name], u.stars, [it for it in u.items if it in item_builds]) for u in units],
                        chosen=chosen, bench_chosen=bench_chosen, switches=pol.switches, gold=p.gold))
    return out

def summary(label, rows):
    if not rows:
        print(label, '없음'); return
    n = len(rows)
    pl = [r['place'] for r in rows]
    def share(f): return f'{sum(f(r) for r in rows) / n:.0%}'
    four = [u for r in rows for u in r['units'] if u[1] == 4]
    riven = [next((u for u in r['units'] if u[0] == 'riven'), None) for r in rows]
    jhin = [next((u for u in r['units'] if u[0] == 'jhin'), None) for r in rows]
    print(f'{label}: {n}명, 평균 등수 {statistics.mean(pl):.2f}, 4등 안 {share(lambda r: r["place"] <= 4)}, 8등 {share(lambda r: r["place"] == 8)}, '
          f'레벨 {statistics.mean(r["level"] for r in rows):.2f}, 유닛 {statistics.mean(len(r["units"]) for r in rows):.2f}')
    print(f'   마지막 계열: {Counter(r["fam"] for r in rows).most_common(4)} | 황혼 인원 {Counter(r["traits"].get("dusk", 0) for r in rows).most_common()}')
    print(f'   4코스트 {len(four) / n:.2f}장/보드, 그중 2성 이상 {sum(u[2] >= 2 for u in four) / max(1, len(four)):.0%} | '
          f'5코스트 {sum(u[1] == 5 for r in rows for u in r["units"]) / n:.2f}장 | 완성 아이템 {statistics.mean(sum(len(u[3]) for u in r["units"]) for r in rows):.2f}')
    have = [u for u in riven if u]
    print(f'   리븐 보드에 {len(have) / n:.0%}, 별 {Counter(u[2] for u in have).most_common()}, 아이템 {statistics.mean(len(u[3]) for u in have) if have else 0:.2f}개 | '
          f'진 보드에 {sum(1 for u in jhin if u) / n:.0%}, 진 아이템 {statistics.mean(len(u[3]) for u in jhin if u) if any(jhin) else 0:.2f}개')
    print(f'   보드 선택받은 자 {Counter((c[0], c[1]) for c in (r["chosen"] for r in rows) if c).most_common(5)} | 없음 {share(lambda r: r["chosen"] is None)} | 벤치에만 {share(lambda r: r["chosen"] is None and r["bench_chosen"] is not None)}')
    print(f'   같은 덱을 고른 다른 봇: {Counter(r["contest"] for r in rows).most_common()} / 혼자일 때 평균 등수 '
          f'{statistics.mean([r["place"] for r in rows if r["contest"] == 0] or [0]):.2f}, 겹칠 때 {statistics.mean([r["place"] for r in rows if r["contest"] > 0] or [0]):.2f}')
    print(f'   갈아타기 {statistics.mean(r["switches"] for r in rows):.2f}번, 남은 골드 {statistics.mean(r["gold"] for r in rows):.1f}')

if __name__ == '__main__':
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(7) as pool:
        rows = [r for out in pool.map(run, games, chunksize=1) for r in out]
    fam_of = {b['name']: deck_family(b) for b in lobby.BOARDS}
    print('목표 덱 몫(마지막):', [(d, f'{c / len(rows):.1%}') for d, c in Counter(r['deck'] for r in rows).most_common(10)])
    for name in ['Chosen Dusks', 'Dusk Mages', 'Chosen Keepers', 'Dusk Cultists', 'Chosen Warlords', 'Warlords Fortune', 'Chosen Divines']:
        summary(name, [r for r in rows if r['deck'] == name])
    summary('마지막 보드가 황혼 계열', [r for r in rows if r['fam'] == 'dusk'])
    summary('마지막 보드가 총사령관 계열', [r for r in rows if r['fam'] == 'warlord'])
    import json
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diag_dusk_rows.json'), 'w', encoding='utf-8'), ensure_ascii=False)
