"""
실제 보드 대전(meta/real_boards.py)에서 시뮬레이터가 실제와 어긋난 원인을 떼어 잰다.

조건을 하나만 바꾸고, 그 조건에 걸리는 보드가 낀 매치업만 다시 붙인다. 나머지 매치업은 기본 결과
(results/real_boards_1024.json의 main: 핫픽스 전, 모두 2성)를 그대로 쓴다. 그 뒤 보드별 평균 승률과 실제 평균 등수와의
순위 상관을 다시 낸다.

조건
  warlord2, warlord5   총사령관 승리 수를 2, 5(시뮬레이터 상한)로 둔다. 기본 대전은 0이다.
  kayn_assassin        케인 형태를 그림자 암살자로 둔다. 기본 대전은 형태가 없다.
  kayn_rhaast          케인 형태를 라아스트로 둔다.
  ricochet_counts      명사수 튕김도 베인 은화살·진 네 번째 사격 횟수에 넣는다(june dd18cfa 전 규칙).
                       코드 한 줄을 바꿔야 해서, 그 줄만 되돌린 june 복사본을 PYTHONPATH에 걸고 돌린다.
  cast_time            스킬을 쓴 유닛이 시전 시간(10.24 게임 파일) 동안 공격·이동하지 않는다. 값이 없는 챔피언은 0초.
  cast_time_half       위와 같고, 값이 없는 챔피언은 0.5초(위키: 대부분 0.5초).
  reroll3              1~2코스트인데 추천 아이템 3개를 든 캐리(닌자의 제드, 결투가의 야스오)를 3성으로 둔다.
  corner               원거리를 뒷줄 구석부터 아이템이 많은 순으로 놓는다. 기본은 가운데부터다.
  drop --board 이름    그 보드에서 유닛을 하나씩 빼 본다(조건이 아니라 보드를 바꾼다).

실행: python -m meta.isolate warlord5 --n 60 --jobs 7 --out results/isolate_1024.json
"""
import argparse
import inspect
import json
import os
import re
import sys
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import cost_of
from meta.pit import average, round_robin
from meta.real_boards import groups, load_trends, prehotfix, spearman, spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'results', 'real_boards_1024.json')
CAST_TIME = os.path.join(ROOT, 'audit', 'cast_time_10.24.json')


def _warlord(wins):
    # analysis.battle.battle이 판마다 승리 수를 0으로 지운 뒤 run을 부르므로, run 바로 앞에서 다시 넣는다.
    import Simulator.config as config
    import Simulator.champion as cm
    run = cm.run

    def patched(*args, **kwargs):
        config.WARLORD_WINS['blue'] = config.WARLORD_WINS['red'] = wins
        return run(*args, **kwargs)
    cm.run = patched


def _kayn(form):
    # 케인은 상점에서 살 때 플레이어의 형태를 받는다(Player.buy_champion). 대전은 유닛을 벤치에 바로 넣어 그 길을 안
    # 타서, 유닛을 만들 때 넣는다. 전투 유닛도 보드 유닛의 형태를 받아 새로 만든다(champion.run).
    import Simulator.champion as cm
    init = cm.champion.__init__

    def patched(self, name, *args, **kwargs):
        init(self, name, *args, **kwargs)
        if name == 'kayn':
            self.kayn_form = form
    cm.champion.__init__ = patched


def _cast_time(missing):
    # 스킬을 쓴 유닛은 시전 시간 동안 공격·이동하지 않는다(효과는 지금처럼 바로 난다). 시전 시간은 10.24 게임 파일 값이고
    # (audit/cast_time_10.24.json), 파일에 값이 없는 챔피언은 missing초로 둔다. 이미 걸린 행동 금지가 더 길면 그대로 둔다.
    import Simulator.champion as cm
    table = json.load(open(CAST_TIME, encoding='utf-8'))
    seconds = {k: missing if v['cast_time'] is None else v['cast_time'] for k, v in table.items() if k != '_source'}
    cast = cm.champion.cast

    def patched(self):
        cast(self)
        ms = seconds.get(self.name, 0) * 1000
        if ms > 0:
            end = max([cm.MILLIS() + ms] + [q[2] for q in cm.que if q[1] is self and q[0] == 'clear_idle'])
            self.idle = False
            self.clear_que_idle()
            self.add_que('clear_idle', end - cm.MILLIS())
    cm.champion.cast = patched


def _old_ricochet():
    # 공격 패시브(베인 은화살·진 네 번째 사격) 조건이 dd18cfa 전처럼 아이템 공격만 빼는지 본다.
    from Simulator import champion_functions
    assert re.search(r'ATTACK_PASSIVES:\s+if not item_attack:', inspect.getsource(champion_functions.attack)), \
        '튕김 규칙을 되돌린 june 복사본을 PYTHONPATH에 걸어야 한다'


def _rerolled(name, items):
    """1~2코스트인데 추천 아이템 3개를 든 유닛(닌자의 제드, 결투가의 야스오)은 리롤로 3성을 만든 캐리로 본다."""
    return cost_of(name) <= 2 and len(items) >= 3


def _reroll_spec(board):
    out = spec(board, 2)
    for unit in out:
        if _rerolled(unit['name'], unit['items']):
            unit['stars'] = 3
    return out


def _corner():
    # 원거리는 뒷줄 구석부터 아이템이 많은 순으로 놓는다(사람이 캐리를 구석에 숨기는 배치). 근접은 지금처럼 앞줄 가운데부터.
    import analysis.battle as ab
    from Simulator.stats import RANGE

    def positions(units):
        spots = [None] * len(units)
        ranged = sorted((i for i, u in enumerate(units) if RANGE[u.name] > 1), key=lambda i: -len(units[i].items))
        melee = [i for i, u in enumerate(units) if RANGE[u.name] <= 1]
        for k, i in enumerate(ranged):
            spots[i] = ([0, 6, 1, 5, 2, 4, 3][k % 7], [0, 1][k // 7])
        for k, i in enumerate(melee):
            spots[i] = (ab.CENTER_OUT[k % 7], [3, 2][k // 7])
        return spots
    ab.range_positions = positions


# 조건 이름 -> (일꾼에서 부를 함수, 그 조건에 걸리는 보드인가, 보드 만들기(None이면 기본 2성))
VARIANTS = {
    'warlord2': (partial(_warlord, 2), lambda b: 'warlord' in b['traits'], None),
    'warlord5': (partial(_warlord, 5), lambda b: 'warlord' in b['traits'], None),
    'kayn_assassin': (partial(_kayn, 'kayn_shadowassassin'), lambda b: 'kayn' in b['units'], None),
    'kayn_rhaast': (partial(_kayn, 'kayn_rhast'), lambda b: 'kayn' in b['units'], None),
    'ricochet_counts': (_old_ricochet, lambda b: 'sharpshooter' in b['traits'], None),
    'cast_time': (partial(_cast_time, 0), lambda b: True, None),
    'cast_time_half': (partial(_cast_time, 0.5), lambda b: True, None),
    'reroll3': (lambda: None, lambda b: any(_rerolled(u, i) for u, i in b['items'].items()), _reroll_spec),
    'corner': (_corner, lambda b: True, None),
}


def setup(name):
    prehotfix()
    VARIANTS[name][0]()


def drop_units(board, boards, n, jobs):
    """board에서 유닛을 하나씩 뺀 보드를 나머지 26개와 붙여 평균 승률을 낸다. 빼서 많이 떨어지는 유닛이 시뮬레이터에서
    그 보드의 힘이다. 유닛을 빼면 그 유닛의 특성 몫과 아이템, 선택받은 자·상징도 같이 빠진다."""
    others = {b['key']: spec(b, 2) for b in boards if b is not board}
    full = spec(board, 2)
    out = {}
    for unit in board['units']:
        key = f'{board["key"]} -{unit}'
        m = round_robin({**others, key: [u for u in full if u['name'] != unit]}, n, 'range', jobs,
                        init=prehotfix, only={key})
        out[unit] = sum(m[key].values()) / len(m[key])
        print(f'  -{unit:12} {out[unit] * 100:5.1f}%', flush=True)
    return out


def save(path, name, entry):
    saved = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    saved[name] = entry
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(saved, f, ensure_ascii=False, indent=1)
    print(f'저장: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('variant', choices=[*VARIANTS, 'drop'], help='drop은 --board의 유닛을 하나씩 빼 본다')
    ap.add_argument('--board', default=None, help='drop할 보드 조합 이름의 앞부분(예: 5hunter)')
    ap.add_argument('--n', type=int, default=60, help='매치업당 판 수(기본 결과와 같아야 한다)')
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=None, help='결과를 더해 둘 JSON. 있으면 다른 조건은 두고 이 조건만 바꾼다')
    args = ap.parse_args()

    base = json.load(open(MAIN, encoding='utf-8'))
    assert base['n'] == args.n, f'기본 결과의 판 수({base["n"]})와 같아야 섞을 수 있다'
    boards = load_trends()
    if args.variant == 'drop':
        board, = [b for b in boards if b['key'].startswith(args.board)]
        print(f'{board["key"]}: 실제 {board["place"]:.2f}, 다 있을 때 {base["average"]["main"][board["key"]] * 100:.1f}%')
        out = drop_units(board, boards, args.n, args.jobs)
        if args.out:
            save(args.out, f'drop:{board["key"]}', {'n': args.n, 'full': base['average']['main'][board['key']],
                                                    'without': out})
        return
    _, affected, make = VARIANTS[args.variant]
    hit = {b['key'] for b in boards if affected(b)}
    part = round_robin({b['key']: make(b) if make else spec(b, 2) for b in boards}, args.n, 'range', args.jobs,
                       init=partial(setup, args.variant), only=hit)
    matrix = {a: {**row, **part[a]} for a, row in base['main'].items()}
    before, after = base['average']['main'], average(matrix)

    print(f'{args.variant}: 다시 붙인 보드 {len(hit)}개 (매치업당 N={args.n}), 실제 평균 등수 순')
    for b in sorted(boards, key=lambda b: b['place']):
        if b['key'] in hit:
            print(f'  {b["key"][:58]:58} 실제 {b["place"]:.2f}  {before[b["key"]] * 100:5.1f}% -> '
                  f'{after[b["key"]] * 100:5.1f}%')
    print('실제 평균 등수와의 순위 상관 (기본 -> 이 조건)')
    rho = {}
    for label, group in groups(boards):
        real = [-b['place'] for b in group]
        rho[label] = [spearman(real, [avg[b['key']] for b in group]) for avg in (before, after)]
        print(f'  {label:12} ({len(group):2d}개)  {rho[label][0]:+.2f} -> {rho[label][1]:+.2f}')

    if args.out:
        save(args.out, args.variant, {'n': args.n, 'boards': sorted(hit), 'average': after, 'rho': rho,
                                      'matrix': {a: row for a, row in part.items() if row}})


if __name__ == '__main__':
    main()
