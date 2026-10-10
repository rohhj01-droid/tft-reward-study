"""떼어 재기 2(코드 안 바꿈): 가이드대로 황혼 운영(B24: 초반 사교도로 연승, 3-2에 6 또는 4-1에 7에서 안정될 때까지 리롤,
4-5에 8에서 리롤). 목표 덱이 황혼 계열(Chosen Dusks 등)인 봇만 바꾼다. DIAG_VARIANT:
roll: 3-2(칸 10)에 레벨 6, 4-1(칸 15)에 레벨 7로 올리고, 캐리가 2성(stable)이 아니면 10골드까지 리롤한다.
guide: roll + 4-1 전에는 사교도 오프너(엘리스·트위스티드 페이트·파이크·칼리스타·이블린)도 덱 유닛으로 치고, 초반 전략은
연승형으로 둔다. 4-1부터 오프너 유닛은 덱 밖 유닛이 된다."""
import json, os, random, statistics, sys
from collections import Counter
import diag_dusk as dd
import diag_curves as dc
import meta.human_bot as hb
from meta.human_five import deck_family
from meta.human_macro import stable

VARIANT = os.environ.get('DIAG_VARIANT', 'base')
OPENER = {'elise', 'twistedfate', 'pyke', 'kalista', 'evelynn'}
def dusk(pol):
    return bool(pol.board) and deck_family(pol.board) == 'dusk'

if VARIANT in ('roll', 'guide'):
    orig_macro = hb.HumanPolicy.macro
    def macro(self, player, game_round):
        if dusk(self):
            for slot, level in ((10, 6), (15, 7)):
                if game_round == slot:
                    if player.level < level and player.gold >= 4:
                        return '1'
                    if player.level >= level and not stable(player, self.board) and player.gold >= 12:
                        return '2'
        return orig_macro(self, player, game_round)
    hb.HumanPolicy.macro = macro
if VARIANT == 'guide':
    orig_mode = hb.HumanPolicy.update_mode
    def update_mode(self, player, game_round):
        orig_mode(self, player, game_round)
        if dusk(self) and self.mode is not None:
            self.mode = 'win'
    hb.HumanPolicy.update_mode = update_mode
    orig_call = hb.HumanPolicy.__call__
    def call(self, player, shop, game_round, mask):
        if dusk(self):
            deck = set(self.board['units']) - self.dropped
            self.units = (deck | OPENER) if game_round < 15 else (self.units - (OPENER - deck))
        return orig_call(self, player, shop, game_round, mask)
    hb.HumanPolicy.__call__ = call

SIX = ['warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter']

def run(game):
    dc.POL.clear(); dc.LOG.clear()
    rows = dd.run(game)
    deck = {id(p): (p.board['name'] if p.board else None) for p in dc.POL}
    return rows, [(deck[r[0]],) + r[1:] for r in dc.LOG]

if __name__ == '__main__':
    from multiprocessing import Pool
    from meta import lobby
    from meta.play_stats import real_families
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(7) as pool:
        out = pool.map(run, games, chunksize=1)
    rows = [r for o in out for r in o[0]]
    curves = [c for o in out for c in o[1]]
    print('변형:', VARIANT)
    dusk_decks = {b['name'] for b in lobby.BOARDS if deck_family(b) == 'dusk'}
    for slot, label in [(10, '3-2'), (13, '3-5'), (16, '4-1 뒤'), (19, '4-5 뒤'), (22, '5-1')]:
        cs = [c for c in curves if c[0] == 'Chosen Dusks' and c[1] == slot]
        if cs:
            print(f'  Chosen Dusks {label} 시작: 살아 {len(cs)} 레벨 {statistics.mean(c[2] for c in cs):.2f} 골드 {statistics.mean(c[3] for c in cs):.1f} '
                  f'체력 {statistics.mean(c[4] for c in cs):.1f} 연패형 {sum(c[5] == "lose" for c in cs) / len(cs):.0%} 연승 {statistics.mean(c[9] for c in cs):.1f} 연패 {statistics.mean(c[10] for c in cs):.1f}')
    for name in ['Chosen Dusks', 'Chosen Warlords']:
        dd.summary(name, [r for r in rows if r['deck'] == name])
    real = {f: a for f, s, a in real_families() if f in SIX}
    bot = {f: statistics.mean(r['place'] for r in rows if r['fam'] == f) for f in SIX if any(r['fam'] == f for r in rows)}
    real = {f: a for f, a in real.items() if f in bot}
    rank = lambda v: {k: i for i, k in enumerate(sorted(v, key=v.get))}
    rb, rr = rank(bot), rank(real)
    print('계열 평균 등수:', {f: round(v, 2) for f, v in sorted(bot.items(), key=lambda t: t[1])}, len(bot),
          '| 실제와 순위 상관', round(1 - 6 * sum((rb[k] - rr[k]) ** 2 for k in bot) / 210, 2) if len(bot) == 6 else '-')
    print('1등 계열', Counter(r['fam'] for r in rows if r['place'] == 1).most_common(6))
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f'diag_iso5_{VARIANT}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
