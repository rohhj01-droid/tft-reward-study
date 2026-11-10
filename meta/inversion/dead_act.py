"""죽은 유닛의 행동 진단(2026-11-10, results/README 「멈춘 판의 원인 바로잡기」). june 전투 틱 루프는 (파랑, 빨강) 짝마다 파랑이
먼저 행동하는데, 그 행동으로 죽은 같은 짝의 빨강도 그 틱에 한 번 더 행동시킨다. 판은 위 탐침들과 같은 판(B 시드 5 신경망, 시드 700000부터)이다.
실행(dense 작업 폴더 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/dead_act.py dump        # 멈춘 판 700299를 다시 돌려, 리 신 스킬이 멈추는 순간의 판 상태를 적는다
    python meta/inversion/dead_act.py count 20    # 시드 700000부터 20판에서 죽은 유닛(팀 목록에 없는 유닛)의 행동을 센다
시뮬레이터가 판 중에 표준 출력을 막으므로 표준 오류로 적는다.
"""
import sys
from collections import Counter

import Simulator.ability as ability
import Simulator.champion as chm
import Simulator.field as field
from meta.inversion import probe_heads

NET = 'checkpoints/plan_dense_both_s5_latest.pt'
orig_action = field.action


def say(*a):
    print(*a, file=sys.stderr, flush=True)


def who(u):
    return u and f'{u.name}({u.team}, {u.stars}성, y{u.y} x{u.x}, 체력 {round(u.health)})'


def dump():
    prev = {}
    orig_leesin = ability.leesin

    def action(c):  # 차례가 돈 유닛과 그 행동 전 빨강 팀 목록을 바로 앞 것까지 둘 들고 있는다
        prev['before'], prev['last'] = prev.get('last'), (who(c), [u.name for u in chm.red])
        return orig_action(c)

    def leesin(ch):
        try:
            return orig_leesin(ch)
        except ValueError:
            units = chm.blue + chm.red
            say('리 신:', who(ch), '| 팀 목록에 있나:', ch in units)
            say('대상:', who(ch.target), '| 리 신 칸에 적힌 유닛:', who(field.coordinates[ch.y][ch.x]))
            say('양 팀 목록:', [who(u) for u in units])
            raise

    field.action, ability.leesin = action, leesin
    seed, rows, err = probe_heads.game((700299, NET, ()))
    say('리 신 바로 앞에 차례가 돈 유닛과 그 행동 전 빨강 팀:', prev.get('before'))
    say('결과:', err or 'ok')


def count(n):
    cnt, games, names, state = Counter(), Counter(), Counter(), {'dead': False}

    def action(c):
        if c in chm.blue or c in chm.red:
            return orig_action(c)
        cnt[f'죽은 유닛 차례({c.team})'] += 1
        state['dead'] = True
        try:
            return orig_action(c)
        finally:
            state['dead'] = False

    def spy(kind, orig):
        def f(self, *a, **k):
            if state['dead']:
                cnt[kind] += 1
                names[kind, self.name] += 1
            return orig(self, *a, **k)
        return f

    field.action = action
    for kind in ('ability', 'attack', 'move'):
        setattr(chm.champion, kind, spy(kind, getattr(chm.champion, kind)))
    for k in range(n):
        before = cnt.copy()
        err = probe_heads.game((700000 + k, NET, ()))[2]
        d = cnt - before
        games.update(d.keys())
        say(700000 + k, err or 'ok', dict(d))
    say('합계:', dict(cnt))
    say(f'그런 일이 한 번 이상 있었던 판 수({n}판 가운데):', dict(games))
    say('죽은 뒤 한 행동(종류, 유닛):', names.most_common(10))


if __name__ == '__main__':
    dump() if sys.argv[1] == 'dump' else count(int(sys.argv[2]))
