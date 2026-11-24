"""실제보다 많은 탈락을 겹치지 않게 나눈 표(results/README 「체력 쪽 나눔 표」, 2026-11-24). 판은 안 돌리고 교과서 8자리 대조 기록만 읽는다. 판정 없음.

자리마다 세 갈래를 붙인다.
  덱: 4-1에 든 덱(deck15, 없으면 끝 덱)이 밸류덱(late)·느린 리롤(slow)·보통 덱(normal) 가운데 무엇인가(hra.spend_lesson.group).
  초반: 2-1·2-2를 모두 이겼나(못 이기면 L). 이긴 자리 가운데 4-1 전 대전에서 두 번 연달아 진 자리는 S, 아니면 W
        (meta/human_macro.early_mode와 meta/human_bot.update_mode를 기록으로 다시 짠 것). 패배는 대전 라운드에 체력이 준 것으로 본다.
  체력: 라운드를 처음 체력 40 미만으로 시작한 단계(3, 4, 5, 6 이상, 없음).
칸마다 「실제보다 많은 탈락」 = 칸의 자리 가운데 그 라운드 전에 끝난 수 − 실제 10.24 탈락률 × 칸의 자리 수. 칸을 모두 더하면 판 전체의 초과 탈락이다.
실행(저장소 맨 위에서, june을 PYTHONPATH에): python meta/inversion/hp_split.py [기록 ...]
"""
import json
import sys
from collections import Counter, defaultdict

from hra.spend_lesson import group
from meta.real_games import round_name, slot_round

DEFAULT = ['meta/inversion/late_none.json', 'meta/inversion/nine_none.json', 'meta/inversion/nine2_none.json', 'results/spend_lesson_none_cap30_s750_tb-era.json']
REAL_ALIVE = {'5-1': 7.714, '5-5': 6.486, '6-1': 5.143}  # results/real_games_set4.json groups['10.24']['alive']
CUT = {'5-1': 21, '5-5': 24, '6-1': 27}  # 이 칸을 시작하지 못하면 그 라운드 전에 끝난 것


def stage_k(slot):
    s, k = round_name(slot_round(slot)).split('-')
    return int(s), int(k)


def pvp(slot):
    s, k = stage_k(slot)
    return s >= 2 and k != 7


def tags(seat):
    c = seat['curve']
    hp = {x[0]: x[3] for x in c}
    lost = {t: hp[t + 1] < hp[t] for t in hp if t + 1 in hp and pvp(t)}
    if not (lost.get(3) is False and lost.get(4) is False):
        path = 'L'
    else:
        seq = [lost[t] for t in sorted(lost) if t <= 13]  # 4-1(칸 15) 전에 연패 2가 되려면 3-6(칸 13)까지의 대전
        path = 'S' if any(a and b for a, b in zip(seq, seq[1:])) else 'W'
    low = next((stage_k(x[0])[0] for x in c if x[3] < 40), None)
    first40 = 'none' if low is None else str(min(low, 6)) if low >= 3 else '2'
    return group(seat, 'deck15'), path, first40


def table(files):
    cells = defaultdict(Counter)
    games = 0
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        assert not d['errors'] and d['actions_per_turn'] == 30 and d['textbook'] == {'spend': 'era', 'lose_5': False}, f  # 팔 실행도 셀 수 있다
        games += len(d['rows'])
        for g in d['rows']:
            for seat in g:
                c = cells[tags(seat)]
                c['seats'] += 1
                for name, cut in CUT.items():
                    c[name] += seat['curve'][-1][0] < cut
    return games, cells


def excess(c, name):
    return c[name] - (1 - REAL_ALIVE[name] / 8) * c['seats']


def show(games, cells, title):
    tot = Counter()
    for c in cells.values():
        tot.update(c)
    print(f'\n== {title}: {games}판, 자리 {tot["seats"]}')
    ex = {n: excess(tot, n) for n in CUT}
    print('판당 초과 탈락', {n: round(ex[n] / games, 3) for n in CUT})
    for dim, name in ((0, '덱'), (1, '초반'), (2, '처음 40 미만 단계')):
        m = defaultdict(Counter)
        for k, c in cells.items():
            m[k[dim]].update(c)
        print(f'-- {name}')
        for k in sorted(m, key=lambda k: -excess(m[k], '5-5')):
            c = m[k]
            print(f'  {k:7s} 자리 {c["seats"] / tot["seats"]:6.1%} | 끝남 5-1 {c["5-1"] / c["seats"]:5.1%} 5-5 {c["5-5"] / c["seats"]:5.1%} 6-1 {c["6-1"] / c["seats"]:5.1%} | '
                  + ' '.join(f'초과 {n} {excess(c, n) / ex[n]:6.1%}' for n in CUT))
    print('-- 칸(덱, 초반, 처음 40 미만 단계), 5-5 초과가 큰 순')
    for k in sorted(cells, key=lambda k: -excess(cells[k], '5-5'))[:12]:
        c = cells[k]
        print(f'  {str(k):28s} 자리 {c["seats"] / tot["seats"]:6.1%} | ' + ' '.join(f'초과 {n} {excess(c, n) / ex[n]:6.1%}' for n in CUT))
    return tot


if __name__ == '__main__':
    files = sys.argv[1:] or DEFAULT
    for f in files:
        show(*table([f]), f.split('/')[-1])
    if len(files) > 1:
        show(*table(files), '모두 합침')
