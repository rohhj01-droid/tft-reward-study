"""
봇의 플레이를 실제 10.24 플레이(meta/set4_play.md)와 같은 항목으로 잰다.

두 조건을 같은 시드로 돌린다. 기본 봇(덱을 정해 주지 않음)과 덱을 따라가는 봇(meta.lobby의 정책과 아이템 나눠 주기).
- 라운드마다 살아 있는 봇의 레벨, 골드, 체력. 「그 라운드에 올린 뒤」 레벨을 보려고 다음 칸 시작 때 값을 쓴다.
- 탈락하거나 끝날 때의 보드: 유닛 수, 비용별 별, 완성 아이템 수, 켜진 특성, 선택받은 자 특성.
실제 쪽은 롤체지지 1등 보드 25개(meta/lolchess_10.24_2020-11-28.json)다.

실행: python -m meta.play_stats --games 100 --jobs 7 --out results/play_stats_1024.json
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from functools import partial
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meta import lobby
from set4 import cost_of

REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_10.24_2020-11-28.json')
# (다음 칸 번호, 이름, 가이드의 표준 레벨). 칸 3 = 2-1이고 한 스테이지가 6칸이다(4-5는 18번째 칸).
CHECKPOINTS = [(4, '2-1 뒤', '4'), (11, '3-2 뒤', '6'), (16, '4-1 뒤', '7'), (19, '4-5 뒤', '7~8'),
               (22, '5-1 뒤', '8'), (28, '6-1 뒤', '8~9')]
# 덱 계열: 앞에서부터 처음 맞는 것(meta/set4_play.md의 분류와 같다). 두 번째 값은 그 계열로 볼 선택받은 자 특성.
FAMILIES = [('dusk', 4, {'dusk'}), ('ninja', 4, {'ninja', 'shade'}), ('duelist', 6, {'duelist'}),
            ('cultist', 6, {'cultist'}), ('warlord', 6, {'warlord'}), ('sharpshooter', 4, {'sharpshooter'}),
            ('divine', 4, {'divine'}), ('hunter', 3, {'hunter'}), ('elderwood', 3, {'elderwood'}),
            ('fortune', 3, {'fortune'}), ('mystic', 4, {'mystic'}), ('brawler', 4, {'brawler'})]
COMPONENTS = {'B.F. Sword', 'Chain Vest', "Giant's Belt", 'Needlessly Large Rod', 'Negatron Cloak', 'Recurve Bow',
              'Sparring Gloves', 'Spatula', 'Tear of the Goddess'}


def family(traits):
    return next(((name, chosen) for name, n, chosen in FAMILIES if traits.get(name, 0) >= n), ('other', set()))


def real_winners():
    """롤체지지 1등 보드를 board_record와 같은 모양으로 바꾼다. 레벨은 모르므로 유닛 수로 둔다."""
    boards = []
    for w in json.load(open(REAL, encoding='utf-8'))['winners']:
        units = []
        for u in w['units']:
            name = u['name'].lower().replace(' ', '').replace("'", '')
            units.append([name, cost_of(name), u['stars'], sum(i not in COMPONENTS for i in u['items'])])
        traits = {t.split(' ', 1)[1].lower(): int(t.split(' ', 1)[0]) for t in w['traits']}
        chosen = w['chosen_trait'].lower() if w['chosen_trait'] else None
        boards.append({'level': len(units), 'units': units, 'traits': traits, 'chosen': chosen})
    return boards


def curve_table(curves):
    at = defaultdict(list)
    for curve in curves:
        for slot, level, gold, hp in curve:
            at[slot].append((level, gold, hp))
    rows = []
    for slot, name, guide in CHECKPOINTS:
        v = at.get(slot)
        if v:
            share = lambda k: sum(lv >= k for lv, _, _ in v) / len(v)
            rows.append({'when': name, 'guide': guide, 'alive': len(v), 'level': statistics.mean(x[0] for x in v),
                         'lv7': share(7), 'lv8': share(8), 'lv9': share(9),
                         'gold': statistics.mean(x[1] for x in v), 'hp': statistics.mean(x[2] for x in v)})
    return rows


def board_summary(boards):
    stars = Counter((cost, star) for b in boards for _, cost, star, _ in b['units'])
    two_plus = {c: sum(v for (cost, s), v in stars.items() if cost == c and s >= 2) /
                max(1, sum(v for (cost, _), v in stars.items() if cost == c)) for c in (4, 5)}
    items = [sum(u[3] for u in b['units']) for b in boards]
    fams = [family(b['traits']) for b in boards]
    with_chosen = [(b['chosen'], f) for b, f in zip(boards, fams) if b['chosen'] and f[0] != 'other']
    return {'boards': len(boards), 'units': dict(sorted(Counter(min(len(b['units']), 10) for b in boards).items())),
            'nine_plus': sum(len(b['units']) >= 9 for b in boards) / len(boards),
            'two_star_4cost': two_plus[4], 'two_star_5cost': two_plus[5],
            'three_star_per_board': sum(v for (_, s), v in stars.items() if s == 3) / len(boards),
            'items_median': statistics.median(items), 'items_min': min(items), 'items_max': max(items),
            'chosen_kinds': len({b['chosen'] for b in boards if b['chosen']}),
            'chosen_off_family': (sum(c not in f[1] for c, f in with_chosen) / len(with_chosen)) if with_chosen else None,
            'families': Counter(f[0] for f in fams).most_common()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=100)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    games = [(args.seed * 100000 + g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(args.games)]
    os.environ['PYTHONHASHSEED'] = str(args.seed)  # meta.lobby와 같은 이유로 일꾼의 해시를 고정한다
    out = {'games': args.games, 'seed': args.seed}
    real = real_winners()
    summary = {'실제 1등': board_summary(real)}
    for label, deck_bots in (('기본 봇', False), ('덱 봇', True)):
        with Pool(args.jobs) as workers:  # 조건마다 새 일꾼(덱 봇의 덱 목록 등록이 기본 봇에 새지 않게)
            results = workers.map(partial(lobby.play, deck_bots=deck_bots), games, chunksize=1)
        winners = [p['board'] for r in results for p in r['players'] if p['place'] == 1]
        out[label] = {'curve': curve_table([r['curve'] for r in results]), 'winners': board_summary(winners),
                      'winner_boards': winners}
        summary[label + ' 1등'] = out[label]['winners']

    print(f'\n단계별 레벨·골드·체력 (살아 있는 봇, {args.games}판씩)')
    print(f'{"":10}{"가이드":>6} | {"기본 봇 레벨":>10} {"7+":>5} {"8+":>5} {"9":>5} {"골드":>5} {"체력":>5} | '
          f'{"덱 봇 레벨":>9} {"7+":>5} {"8+":>5} {"9":>5} {"골드":>5} {"체력":>5}')
    for a, b in zip(out['기본 봇']['curve'], out['덱 봇']['curve']):
        cells = lambda r: (f'{r["level"]:10.2f} {r["lv7"] * 100:4.0f}% {r["lv8"] * 100:4.0f}% {r["lv9"] * 100:4.0f}% '
                           f'{r["gold"]:5.1f} {r["hp"]:5.1f}')
        print(f'{a["when"]:10}{a["guide"]:>6} | {cells(a)} | {cells(b)}')

    print('\n1등 보드')
    keys = [('boards', '보드 수'), ('units', '유닛 수 분포'), ('nine_plus', '9유닛 이상'), ('two_star_4cost', '4코스트 2성 이상'),
            ('two_star_5cost', '5코스트 2성 이상'), ('three_star_per_board', '보드당 3성'), ('items_median', '완성 아이템 가운데 값'),
            ('chosen_kinds', '선택받은 자 특성 가짓수'), ('chosen_off_family', '선택받은 자가 계열 특성이 아닌 비율'),
            ('families', '계열')]
    for key, name in keys:
        cells = []
        for label, s in summary.items():
            v = s[key]
            cells.append(f'{label}: ' + (f'{v * 100:.0f}%' if isinstance(v, float) and key not in ('items_median', 'three_star_per_board')
                                         else f'{v:.2f}' if isinstance(v, float) else str(v[:6] if key == 'families' else v)))
        print(f'  {name}: ' + ' / '.join(cells))
    if args.out:
        out['real_winners'] = summary['실제 1등']
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
