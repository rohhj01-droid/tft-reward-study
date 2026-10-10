"""떼어 재기 3(코드 안 바꿈): 로비 덱 구성. 봇마다 덱을 판 내내 고정해서 나눠 준다(갈아타기 없음). DIAG_VARIANT:
real: 실제 메타 트렌드 계열 몫(meta.play_stats.real_families)대로. 계열마다 티어가 가장 높은 덱에 몫을 준다(같으면 나눔).
bot: 지금 사람 봇이 스스로 고른 마지막 덱 몫(diag_dusk_rows.json, 200판)대로.
판마다 덱 8개를 그 몫으로 뽑는다(같은 덱 중복 가능)."""
import json, os, random, statistics, sys
from collections import Counter
import diag_dusk as dd
import meta.human_bot as hb
from meta import lobby
from meta.human_five import deck_family
from meta.play_stats import real_families

VARIANT = os.environ.get('DIAG_VARIANT', 'real')
HERE = os.path.dirname(os.path.abspath(__file__))
TIER = {'S': 3, 'A': 2, 'B': 1}
FAM = [deck_family(b) or 'other' for b in lobby.BOARDS]

def weights():
    names = [b['name'] for b in lobby.BOARDS]
    if VARIANT == 'bot':
        rows = json.load(open(os.path.join(HERE, 'diag_dusk_rows.json'), encoding='utf-8'))
        count = Counter(r['deck'] for r in rows if r['deck'])
        return [count.get(n, 0) for n in names]
    w = [0.0] * len(names)
    for fam, share, _ in real_families():
        cands = [i for i, f in enumerate(FAM) if f == fam]
        if cands:
            top = max(TIER[lobby.BOARDS[i]['tier']] for i in cands)
            best = [i for i in cands if TIER[lobby.BOARDS[i]['tier']] == top]
            for i in best:
                w[i] += share / len(best)
    return w

W = weights()
QUEUE = []
orig_attach = hb.attach_human
def attach(player, others, rng, knobs=None, board=None):
    return orig_attach(player, others, rng, knobs, board=lobby.BOARDS[QUEUE.pop(0)])
hb.attach_human = attach

def run(game):
    seed = game[0]
    decks = random.Random(seed + 7919).choices(range(len(lobby.BOARDS)), weights=W, k=lobby.N_PLAYERS)
    QUEUE[:] = decks
    return dd.run((seed, decks))

SIX = ['warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter']

def spearman(bot, real):
    keys = [k for k in SIX if k in bot and k in real]
    rank = lambda v: {k: i for i, k in enumerate(sorted(keys, key=v.get))}
    rb, rr = rank(bot), rank(real)
    n = len(keys)
    return (round(1 - 6 * sum((rb[k] - rr[k]) ** 2 for k in keys) / (n * (n * n - 1)), 2) if n >= 3 else '-'), n

if __name__ == '__main__':
    from multiprocessing import Pool
    n = int(sys.argv[1])
    games = [(g, None) for g in range(n)]
    with Pool(7) as pool:
        rows = [r for out in pool.map(run, games, chunksize=1) for r in out]
    json.dump(rows, open(os.path.join(HERE, f'diag_iso6_{VARIANT}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    total = len(rows)
    print('변형:', VARIANT, '| 덱 몫:', [(d, f'{c / total:.1%}') for d, c in Counter(r['deck'] for r in rows).most_common(9)])
    real = {f: a for f, s, a in real_families()}
    by_deck_fam = {}
    for f in SIX:
        ps = [r['place'] for r in rows if (deck_family(next(b for b in lobby.BOARDS if b['name'] == r['deck'])) or 'other') == f]
        if len(ps) >= 20:
            by_deck_fam[f] = statistics.mean(ps)
    by_final = {f: statistics.mean(r['place'] for r in rows if r['fam'] == f) for f in SIX if sum(r['fam'] == f for r in rows) >= 20}
    print('덱 계열별 평균 등수:', {f: round(v, 2) for f, v in sorted(by_deck_fam.items(), key=lambda t: t[1])}, '| 실제와 순위 상관(계열 수)', spearman(by_deck_fam, real))
    print('마지막 보드 계열별 평균 등수:', {f: round(v, 2) for f, v in sorted(by_final.items(), key=lambda t: t[1])}, '| 실제와 순위 상관(계열 수)', spearman(by_final, real))
    for name in ['Chosen Dusks', 'Chosen Warlords', 'Ninja Shades', 'Chosen Cultists', 'Chosen Divines', 'Chosen Duelists', 'Chosen Sharpshooters']:
        dd.summary(name, [r for r in rows if r['deck'] == name])
