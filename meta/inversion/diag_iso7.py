"""떼어 재기 4(코드 안 바꿈): 느린 리롤 덱 대비책. 느린 덱이 4-5(칸 18)까지 캐리 3성을 못 맞추면 머무는 레벨을 그만두고
보통 덱처럼 간다(목표 레벨 8, 보통 덱의 리롤·경험치 규칙). 가이드(B24): 제드는 3성을 노리면 6~7에서 느린 리롤, 아니면
8~9로 올리고 5코스트. LOBBY=real이면 diag_iso6의 실제 몫 로비(덱 고정), self면 봇이 덱을 스스로 고르는 판(diag_dusk)."""
import json, os, random, statistics, sys
from collections import Counter
import meta.human_bot as hb

LOBBY = os.environ.get('LOBBY', 'self')
if LOBBY == 'real':
    os.environ['DIAG_VARIANT'] = 'real'
    import diag_iso6 as base
else:
    import diag_dusk as base
import diag_dusk as dd

FALLBACK = os.environ.get('FALLBACK', '1') == '1'
orig_macro = hb.HumanPolicy.macro
def macro(self, player, game_round):
    if game_round >= 18 and self.board and self.board['slow']:
        saved = hb.carry3
        hb.carry3 = lambda p, b: True  # 「캐리 3성」으로 쳐서 느린 리롤을 끝낸다
        try:
            return orig_macro(self, player, game_round)
        finally:
            hb.carry3 = saved
    return orig_macro(self, player, game_round)
if FALLBACK:
    hb.HumanPolicy.macro = macro

SIX = ['warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter']

def spearman(bot, real):
    keys = [k for k in SIX if k in bot and k in real]
    rank = lambda v: {k: i for i, k in enumerate(sorted(keys, key=v.get))}
    rb, rr, n = rank(bot), rank(real), len(keys)
    return round(1 - 6 * sum((rb[k] - rr[k]) ** 2 for k in keys) / (n * (n * n - 1)), 2) if n >= 3 else '-'

def report(rows):
    from meta import lobby
    from meta.human_five import deck_family
    from meta.play_stats import real_families
    real = {f: a for f, s, a in real_families()}
    fam_of = {b['name']: deck_family(b) or 'other' for b in lobby.BOARDS}
    by_deck = {f: statistics.mean(r['place'] for r in rows if fam_of.get(r['deck']) == f) for f in SIX
               if sum(fam_of.get(r['deck']) == f for r in rows) >= 20}
    by_final = {f: statistics.mean(r['place'] for r in rows if r['fam'] == f) for f in SIX if sum(r['fam'] == f for r in rows) >= 20}
    print('덱 계열별 평균 등수:', {f: round(v, 2) for f, v in sorted(by_deck.items(), key=lambda t: t[1])}, '| 실제와 순위 상관', spearman(by_deck, real))
    print('마지막 보드 계열별:', {f: round(v, 2) for f, v in sorted(by_final.items(), key=lambda t: t[1])}, '| 실제와 순위 상관', spearman(by_final, real))
    for name in ['Ninja Shades', 'Chosen Duelists', 'Chosen Dusks', 'Chosen Warlords', 'Chosen Cultists', 'Chosen Divines', 'Chosen Sharpshooters']:
        rs = [r for r in rows if r['deck'] == name]
        if rs:
            print(f'  {name}: {len(rs)}명, 평균 등수 {statistics.mean(r["place"] for r in rs):.2f}, 4등 안 {sum(r["place"] <= 4 for r in rs) / len(rs):.0%}, '
                  f'레벨 {sorted(Counter(r["level"] for r in rs).items())}')
    rs = [r for r in rows if r['deck'] == 'Ninja Shades']
    if rs:
        print('  제드 별:', sorted(Counter(max([u[2] for u in r['units'] if u[0] == 'zed'] or [0]) for r in rs).items()),
              '| 5코스트', round(statistics.mean(sum(u[1] == 5 for u in r['units']) for r in rs), 2))

if __name__ == '__main__':
    from multiprocessing import Pool
    from meta import lobby
    n = int(sys.argv[1])
    if LOBBY == 'real':
        games = [(g, None) for g in range(n)]
    else:
        rng = random.Random(0)
        games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    here = os.path.dirname(os.path.abspath(__file__))
    with Pool(7) as pool:
        rows = [r for out in pool.map(base.run, games, chunksize=1) for r in out]
    tag = 'fb' if FALLBACK else 'base'
    json.dump(rows, open(os.path.join(here, f'diag_iso7_{LOBBY}_{tag}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('=== 로비', LOBBY, '| 느린 덱 대비책', '있음' if FALLBACK else '없음')
    report(rows)
