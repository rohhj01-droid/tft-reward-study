"""떼어 재기 1(코드 안 바꿈): 4코스트를 2성으로 올리기. 환경 변수 DIAG_VARIANT로 고른다.
rolldown: 레벨 8 이상이고 덱 캐리 중 4코스트가 아직 2성(1성으로 쳐서 3장)이 안 되면 골드를 다 써서 리롤한다.
cap: 모든 사람 봇이 4코스트 유닛을 3장(2성)보다 더 사지 않는다(상점에서 그 칸을 덱 밖 이름으로 바꿔 본다).
diag_dusk와 같은 판 목록(시드 0의 앞 N판)."""
import json, os, statistics, sys
from collections import Counter
import meta.human_bot as hb
from meta.human_deck import copies, units_of
from meta.lobby import carriers
from Simulator.stats import COST
import diag_dusk as dd

VARIANT = os.environ.get('DIAG_VARIANT', 'base')
if VARIANT in ('rolldown', 'both'):
    orig_macro = hb.HumanPolicy.macro
    def macro(self, player, game_round):
        if self.board and player.level >= 8 and player.gold >= 2:
            held = copies(units_of(player))
            if any(COST[c] == 4 and held.get(c, 0) < 3 for c in carriers(self.board)):
                return '2'
        return orig_macro(self, player, game_round)
    hb.HumanPolicy.macro = macro
if VARIANT in ('cap', 'both'):
    orig_buy = hb.HumanPolicy.buy
    def buy(self, player, shop, mask):
        held = copies(units_of(player))
        shop = ['zz' if (u in COST and COST[u] == 4 and held.get(u, 0) >= 3) else u for u in shop]
        return orig_buy(self, player, shop, mask)
    hb.HumanPolicy.buy = buy

SIX = ['warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter']

def ranking(rows):
    from meta.play_stats import real_families
    real = {f: a for f, s, a in real_families() if f in SIX}
    bot = {f: statistics.mean(r['place'] for r in rows if r['fam'] == f) for f in SIX}
    rank = lambda v: {k: i for i, k in enumerate(sorted(v, key=v.get))}
    rb, rr = rank(bot), rank(real)
    rho = 1 - 6 * sum((rb[k] - rr[k]) ** 2 for k in SIX) / (6 * 35)
    return bot, rho

if __name__ == '__main__':
    from multiprocessing import Pool
    import random
    from meta import lobby
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    if VARIANT == 'base':
        rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diag_dusk_rows.json'), encoding='utf-8'))
    else:
        with Pool(7) as pool:
            rows = [r for out in pool.map(dd.run, games, chunksize=1) for r in out]
        json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f'diag_iso4_{VARIANT}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('변형:', VARIANT, '| 플레이어', len(rows))
    for name in ['Chosen Dusks', 'Chosen Warlords', 'Chosen Divines', 'Chosen Cultists']:
        dd.summary(name, [r for r in rows if r['deck'] == name])
    bot, rho = ranking(rows)
    print('계열 평균 등수(마지막 보드):', {f: round(v, 2) for f, v in sorted(bot.items(), key=lambda t: t[1])}, '| 실제와 순위 상관', round(rho, 2))
    four = [u for r in rows for u in r['units'] if u[1] == 4]
    print('모든 봇 4코스트 2성 이상', f'{sum(u[2] >= 2 for u in four) / len(four):.0%}', '| 1등 계열', Counter(r['fam'] for r in rows if r['place'] == 1).most_common(6))
    lv9 = [r for r in rows if r['place'] == 1]
    print('1등 레벨 9', f'{sum(r["level"] >= 9 for r in lv9) / len(lv9):.0%}', '| 1등 보드 3성', round(sum(u[2] == 3 for r in lv9 for u in r['units']) / len(lv9), 2))
