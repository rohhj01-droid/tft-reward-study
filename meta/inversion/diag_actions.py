"""행동 수 진단(코드 안 바꿈): DIAG_VARIANT=rolldown 패치 위에서, 라운드마다 봇이 쓴 행동(15번)과 리롤 수, 라운드 끝 골드를 센다.
리븐(덱 캐리 4코스트)이 아직 2성이 아니고 레벨 8 이상인 라운드만 본다."""
import os, random, sys, statistics
from collections import Counter, defaultdict
from multiprocessing import Pool
import diag_iso4  # 변형 패치(환경 변수)와 diag_dusk의 attach 감싸기
import meta.human_bot as hb
from meta.human_deck import copies, units_of
from meta.lobby import carriers
from Simulator.stats import COST
from meta import lobby

LOG = []
orig_call = hb.HumanPolicy.__call__
def call(self, player, shop, game_round, mask):
    act = orig_call(self, player, shop, game_round, mask)
    need = bool(self.board and player.level >= 8 and any(
        COST[c] == 4 and copies(units_of(player)).get(c, 0) < 3 for c in carriers(self.board)))
    LOG.append((id(self), self.board['name'] if self.board else None, game_round, act[0] if act else '0', player.gold, need))
    return act
hb.HumanPolicy.__call__ = call

def run(game):
    LOG.clear()
    lobby.play(game, bot='human')
    rounds = defaultdict(list)
    for pid, deck, r, kind, gold, need in LOG:
        rounds[(pid, r)].append((deck, kind, gold, need))
    out = []
    for (pid, r), acts in rounds.items():
        deck = acts[-1][0]
        if not acts[0][3]:  # 라운드 시작 때 롤다운 조건이 아니면 뺀다
            continue
        kinds = Counter(k for _, k, _, _ in acts)
        out.append(dict(deck=deck, n=len(acts), rolls=kinds['2'], buys=kinds['3'], xp=kinds['1'], passes=kinds['0'],
                        other=len(acts) - kinds['2'] - kinds['3'] - kinds['1'] - kinds['0'],
                        gold_start=acts[0][2], gold_end=acts[-1][2], still=acts[-1][3]))
    return out

if __name__ == '__main__':
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(7) as pool:
        rows = [r for out in pool.map(run, games, chunksize=1) for r in out]
    for label, rs in [('Chosen Dusks', [r for r in rows if r['deck'] == 'Chosen Dusks']), ('4코스트 캐리 덱 전체', rows)]:
        if not rs:
            continue
        m = lambda k: statistics.mean(r[k] for r in rs)
        print(f'{label}: 롤다운 조건 라운드 {len(rs)}개 | 라운드당 행동 {m("n"):.1f}(리롤 {m("rolls"):.1f}, 사기 {m("buys"):.1f}, 경험치 {m("xp"):.1f}, '
              f'넘김 {m("passes"):.1f}, 그 밖 {m("other"):.1f}) | 골드 시작 {m("gold_start"):.1f} → 끝 {m("gold_end"):.1f} | '
              f'끝에도 조건 남음 {sum(r["still"] for r in rs) / len(rs):.0%}, 그중 골드 4 이상 남음 {sum(r["still"] and r["gold_end"] >= 4 for r in rs) / len(rs):.0%}')
