"""행동 상한 진단(코드 안 바꿈, 2026-11-13): 규칙 사람 봇 8명 판에서 자리·라운드마다 쓴 행동의 종류를 센다. 시뮬레이터는 한
라운드에 행동을 config.ACTIONS_PER_TURN(15)번만 받는다. 레벨을 올리는 라운드와 리롤하려던 라운드가 그 상한에서 얼마나 끊기는지 본다.
「끊김」은 그 라운드의 마지막 행동이 넘김이 아닌 것이다. 판 목록은 diag_flex와 같은 시드 0의 앞 N판이다.

실행(저장소 맨 위에서, PYTHONPATH에 june·stubs·. 를 넣고):
    python meta/inversion/diag_cap.py 8 <결과.json>     요약만: python meta/inversion/diag_cap.py summary <결과.json>
"""
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

os.environ.setdefault('PYTHONHASHSEED', '0')
import meta.human_bot as hb
from meta import lobby

LOG = []
_call = hb.HumanPolicy.__call__


def call(self, player, shop, game_round, mask):
    gold, level = player.gold, player.level
    act = _call(self, player, shop, game_round, mask)
    target, floor, _ = self.macro_plan(player, game_round)
    LOG.append((id(self), game_round, (act or '0')[0], gold, level, target, floor))
    return act


hb.HumanPolicy.__call__ = call


def run(game):
    LOG.clear()
    lobby.play(game, bot='human')
    rounds = defaultdict(list)
    for pid, r, *rest in LOG:
        rounds[(pid, r)].append(rest)
    out = []
    for (_, r), acts in rounds.items():
        kinds = Counter(a[0] for a in acts)
        out.append(dict(slot=r, n=len(acts), xp=kinds['1'], rolls=kinds['2'], buys=kinds['3'], passes=kinds['0'],
                        last=acts[-1][0], gold0=acts[0][1], gold1=acts[-1][1], level0=acts[0][2], level1=acts[-1][2],
                        floor=acts[-1][4]))
    return out


def summary(path):
    rows = json.load(open(path, encoding='utf-8'))
    m = lambda xs: statistics.mean(xs) if xs else float('nan')
    print('| 라운드 | 자리·라운드 | 경험치 | 리롤 | 사기 | 그 밖 | 넘김 | 상한에서 끊김 | 골드 시작 → 끝 |')
    print('|---|---|---|---|---|---|---|---|---|')
    picks = [('4-1 (15번째 칸)', lambda r: r['slot'] == 15), ('4-5 (18번째 칸)', lambda r: r['slot'] == 18),
             ('레벨 6 → 7을 찍은 라운드', lambda r: r['level0'] == 6 and r['level1'] == 7),
             ('레벨 7 → 8을 찍은 라운드', lambda r: r['level0'] == 7 and r['level1'] == 8),
             ('레벨 8, 계획이 50 지키기', lambda r: r['level0'] == 8 and r['level1'] == 8 and r['floor'] in (None, 50)),
             ('레벨 8, 계획이 10골드까지', lambda r: r['level0'] == 8 and r['level1'] == 8 and r['floor'] == 10),
             ('레벨 8, 계획이 다 쓰기', lambda r: r['level0'] == 8 and r['level1'] == 8 and r['floor'] == 0)]
    for name, cond in picks:
        rs = [r for r in rows if cond(r)]
        if rs:
            other = [r['n'] - r['xp'] - r['rolls'] - r['buys'] - r['passes'] for r in rs]
            print(f"| {name} | {len(rs)} | {m([r['xp'] for r in rs]):.1f} | {m([r['rolls'] for r in rs]):.1f} | "
                  f"{m([r['buys'] for r in rs]):.1f} | {m(other):.1f} | {m([r['passes'] for r in rs]):.1f} | "
                  f"{sum(r['last'] != '0' for r in rs) / len(rs):.0%} | {m([r['gold0'] for r in rs]):.0f} → {m([r['gold1'] for r in rs]):.0f} |")
    print('한 라운드 리롤 최대', max(r['rolls'] for r in rows), '번')


if __name__ == '__main__':
    if sys.argv[1] == 'summary':
        summary(sys.argv[2])
        sys.exit()
    n, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    json.dump([r for g in games for r in run(g)], open(out, 'w', encoding='utf-8'))
    summary(out)
