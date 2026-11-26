"""
배치에 따라 달라지는 효과가 배치마다 얼마나 사는지 대전 없이 센다(2026-11-26, results/README 「마지막 대전 붙이기: 효과를 살리는 배치」).

    python meta/inversion/place_cover.py PAIRS OUT.json [대전 수]     (PYTHONPATH에 시뮬레이터 저장소와 이 저장소 맨 위)

마지막 대전의 보드(meta/inversion/final_pairs.py가 뽑은 파일)를 배치 셋(구석 corner, 가운데 range, 효과 effect)으로 실제 보드에
올린 뒤 칸을 본다. 시뮬레이터가 아지르 옆에 놓는 모래 병사까지 올라간 보드를 본다(추방자 옆의 모래 병사도 같은 편으로 친다).
  추방자: 옆 칸에 같은 편이 없는 추방자 유닛의 몫.
  수호자(특성이 켜진 보드): 유닛 하나가 받는 수호자 보호막의 수(자기 것 포함), 하나도 못 받는 유닛의 몫,
        아이템이 가장 많은 유닛이 받는 수.
  같은 줄 아이템(지크의 전령·힘의 성배는 양옆 1칸, 솔라리의 펜던트는 양옆 2칸): 든 유닛 말고 받는 같은 편의 수,
        아이템이 가장 많은 유닛이 받는(또는 들고 있는) 몫.
보드만 읽고 합친 값만 낸다. 뽑아 둔 파일은 저장소에 넣지 않는다.
"""
import contextlib
import io
import json
import sys

import Simulator.field as field
from Simulator.origin_class_stats import origin_class
from Simulator.pool import pool

import final_fight as ff
from analysis.battle import ROW_ITEMS, build_player

PLACES = ('corner', 'range', 'effect')
REACH = {'zekes_herald': 1, 'chalice_of_power': 1, 'locket_of_the_iron_solari': 2}
assert set(REACH) == set(ROW_ITEMS)


def near(a, b):
    return field.distance({'y': a[1], 'x': a[0]}, {'y': b[1], 'x': b[0]}, False) == 1


def cover(board, items, place):
    """보드 하나를 그 배치로 올려 센 값들. {이름: [합, 개수]}"""
    with contextlib.redirect_stdout(io.StringIO()):
        p = build_player(pool(), 0, ff.make_units(ff.spec(board, items), 'fixed'), place)
    on = [((x, y), p.board[x][y]) for x in range(7) for y in range(4) if p.board[x][y]]
    real = [(c, u) for c, u in on if u.name != 'sandguard']
    assert len(real) == len(board['units']), (len(real), len(board['units']))
    out = {}

    def add(name, value, n=1):
        s = out.setdefault(name, [0, 0])
        s[0] += value
        s[1] += n
    top = max(real, key=lambda cu: len(cu[1].items))
    for c, u in real:
        if 'exile' in origin_class[u.name]:
            add('exile alone', not any(near(c, d) for d, _ in on if d != c))
    k = board['traits'].get('Keeper', 0)
    if k >= 2:
        g = 'keeper 2~3' if k < 4 else 'keeper 4+'
        keepers = [c for c, u in real if 'keeper' in origin_class[u.name]]
        got = {c: sum(c == d or near(c, d) for d in keepers) for c, _ in real}
        add(g + ' shields per unit', sum(got.values()), len(real))
        add(g + ' units with none', sum(v == 0 for v in got.values()), len(real))
        add(g + ' shields on top unit', got[top[0]])
        add(g + ' keeper units', len(keepers))
    for c, u in real:
        for it in set(u.items) & set(REACH):
            inside = [d for d, _ in real if d != c and d[1] == c[1] and abs(d[0] - c[0]) <= REACH[it]]
            add(it + ' allies covered', len(inside))
            add(it + ' reaches top unit', top[0] == c or top[0] in inside)
    return out


def tally(pairs, count):
    items = ff.item_names()
    total = {place: {} for place in PLACES}
    for pair in pairs[:count]:
        for board in pair['boards']:
            for place in PLACES:
                for name, (s, n) in cover(board, items, place).items():
                    t = total[place].setdefault(name, [0, 0])
                    t[0] += s
                    t[1] += n
    return {place: {name: {'n': n, 'mean': round(s / n, 4)} for name, (s, n) in sorted(v.items())} for place, v in total.items()}


if __name__ == '__main__':
    pairs = json.load(open(sys.argv[1], encoding='utf-8'))['pairs']
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 15205
    out = {'boards': 2 * min(count, len(pairs)), 'places': tally(pairs, count)}
    json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('place_cover 보드', out['boards'])
    for name in out['places']['corner']:
        print(name, out['places']['corner'][name]['n'], *(out['places'][p].get(name, {}).get('mean') for p in PLACES))
