"""덱별 단계 곡선 진단(코드 안 바꿈): 라운드마다 봇의 첫 행동 때 레벨·골드·체력·초반 전략·보드 유닛 수·별 합을 덱별로 모은다.
덱은 그 판 끝의 목표 덱으로 묶는다(중간에 갈아탄 봇도 끝 덱으로)."""
import os, random, sys, statistics
from collections import defaultdict
from multiprocessing import Pool
os.environ.setdefault('PYTHONHASHSEED', '0')
import meta.human_bot as hb
from meta import lobby
from Simulator.stats import COST

POL, LOG = [], []
orig = hb.attach_human
def attach(player, *a, **k):
    pol = orig(player, *a, **k)
    POL.append(pol)
    return pol
hb.attach_human = attach
orig_call = hb.HumanPolicy.__call__
def call(self, player, shop, game_round, mask):
    if game_round != self.last_round:  # 라운드 첫 행동(정책이 last_round를 바꾸기 전)
        units = [u for row in player.board for u in row if u and u.name in COST]
        LOG.append((id(self), game_round, player.level, player.gold, player.health, self.mode,
                    len(units), sum(u.stars for u in units), sum(COST[u.name] * 3 ** (u.stars - 1) for u in units), sum(u.name in self.units for u in units), sum(v > 0 for v in player.team_tiers.values()), sum(player.team_tiers.values()), max([player.team_composition.get(t, 0) for t in ([self.trait] if self.trait else [])] or [0]),
                    player.win_streak, player.loss_streak))
    return orig_call(self, player, shop, game_round, mask)
hb.HumanPolicy.__call__ = call

CHECK = [(4, '2-1'), (7, '2-4'), (10, '3-2'), (13, '3-5'), (16, '4-1'), (19, '4-5'), (22, '5-1')]

def run(game):
    POL.clear(); LOG.clear()
    res = lobby.play(game, bot='human')
    deck = {id(p): (p.board['name'] if p.board else None) for p in POL}
    place = {id(p): r['place'] for p, r in zip(POL, res['players'])}
    return [(deck[pid], place[pid]) + row[1:] for row in LOG for pid in [row[0]]]

if __name__ == '__main__':
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(7) as pool:
        rows = [r for out in pool.map(run, games, chunksize=1) for r in out]
    for name in ['Chosen Dusks', 'Chosen Warlords', 'Chosen Divines', 'Chosen Cultists']:
        print(name)
        for slot, label in CHECK:
            rs = [r for r in rows if r[0] == name and r[2] == slot]
            if not rs:
                continue
            m = lambda i: statistics.mean(r[i] for r in rs)
            lose = sum(r[6] == 'lose' for r in rs) / len(rs)
            print(f'  {label} 시작: 살아 {len(rs):3d} | 레벨 {m(3):.2f} 골드 {m(4):5.1f} 체력 {m(5):5.1f} | 유닛 {m(7):.1f} 별 합 {m(8):.1f} '
                  f'값 {m(9):5.1f} | 덱 유닛 {m(10):.1f} 켜진 특성 {m(11):.1f} 단계 합 {m(12):.1f} 덱 특성 인원 {m(13):.1f} | 연패형 {lose:.0%} 연패 {m(15):.1f}')
