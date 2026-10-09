"""
봇의 플레이를 실제 10.24 플레이(meta/set4_play.md)와 같은 항목으로 잰다.

세 조건을 같은 시드로 돌린다. 기본 봇(덱을 정해 주지 않음), 덱 봇(meta.lobby의 정책과 아이템 나눠 주기),
사람 봇(meta/human_bot.py).
- 라운드마다 살아 있는 봇의 레벨, 골드, 체력. 「그 라운드에 올린 뒤」 레벨을 보려고 다음 칸 시작 때 값을 쓴다.
  사람 봇은 초반 전략(연승형·연패형)별로도 나눠 본다.
- 탈락하거나 끝날 때의 보드: 유닛 수, 비용별 별, 완성 아이템 수, 켜진 특성, 선택받은 자 특성, 아이템을 완성으로 쓴 비율.
- 5단계 시작 때 목표 덱 캐리가 아이템을 든 비율, 덱 계열별 비율과 평균 등수.
실제 쪽은 롤체지지 1등 보드 25개와 메타 트렌드(meta/lolchess_10.24_2020-11-28.json)다.

실행: python -m meta.play_stats --games 100 --jobs 7 --out results/play_stats_1024.json
      python -m meta.play_stats --games 400 --conditions human --knob tier_weight=0 --out ...
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from functools import partial
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meta import lobby
from set4 import cost_of

REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_10.24_2020-11-28.json')
CONDITIONS = {'default': '기본 봇', 'deck': '덱 봇', 'human': '사람 봇'}
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


def real_families():
    """롤체지지 메타 트렌드를 계열로 묶은 (계열, 27개 조합 안 몫, 평균 등수)."""
    rows = defaultdict(lambda: [0.0, 0.0])
    for t in json.load(open(REAL, encoding='utf-8'))['trends']:
        name = family({k.lower(): v for k, v in t['traits'].items()})[0]
        rows[name][0] += t['pick_rate']
        rows[name][1] += t['pick_rate'] * t['average_placement']
    return sorted(((f, s, w / s) for f, (s, w) in rows.items()), key=lambda r: -r[1])


def curve_table(curves, mode=None, style=None):
    """칸별 레벨·골드·체력. mode는 초반 전략('win'·'lose'), style은 느린 리롤 덱인가(True·False)로 거른다.
    가이드 레벨은 보통 덱 기준이라 보통 덱으로 판정한다(유저 결정 2026-10-09)."""
    at = defaultdict(list)
    for curve in curves:
        for slot, level, gold, hp, m, slow in curve:
            if (mode is None or m == mode) and (style is None or slow == style):
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
    worth = [(2 * b['completed_all'], 2 * b['completed_all'] + b['components_all']) for b in boards if 'completed_all' in b]
    return {'boards': len(boards), 'units': dict(sorted(Counter(min(len(b['units']), 10) for b in boards).items())),
            'nine_plus': sum(len(b['units']) >= 9 for b in boards) / len(boards),
            'two_star_4cost': two_plus[4], 'two_star_5cost': two_plus[5],
            'three_star_per_board': sum(v for (_, s), v in stars.items() if s == 3) / len(boards),
            'items_median': statistics.median(items),
            'item_use': (sum(a for a, _ in worth) / max(1, sum(b for _, b in worth))) if worth else None,
            'item_worth': statistics.mean(b for _, b in worth) if worth else None,
            'chosen_kinds': len({b['chosen'] for b in boards if b['chosen']}),
            'chosen_off_family': (sum(c not in f[1] for c, f in with_chosen) / len(with_chosen)) if with_chosen else None,
            'no_family': sum(f[0] == 'other' for f in fams) / len(boards),
            'families': Counter(f[0] for f in fams).most_common()}


def family_table(players):
    """(계열, 마지막 보드 몫, 평균 등수)."""
    rows = defaultdict(list)
    for p in players:
        rows[family(p['board']['traits'])[0]].append(p['place'])
    return sorted(((f, len(v) / len(players), statistics.mean(v)) for f, v in rows.items()), key=lambda r: -r[1])


def fmt(v, pct=True):
    """None은 '-', 실수는 pct면 백분율·아니면 소수 둘째 자리, 그 밖은 그대로."""
    if v is None:
        return '-'
    if isinstance(v, float):
        return f'{v * 100:.0f}%' if pct else f'{v:.2f}'
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=100)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--conditions', default='default,deck,human', help='쉼표로: default, deck, human')
    ap.add_argument('--knob', action='append', default=[], help='사람 봇 손잡이 값 바꾸기, 예: tier_weight=0')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    knobs = {k: float(v) for k, v in (kv.split('=') for kv in args.knob)}

    rng = random.Random(args.seed)
    games = [(args.seed * 100000 + g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(args.games)]
    os.environ['PYTHONHASHSEED'] = str(args.seed)  # meta.lobby와 같은 이유로 일꾼의 해시를 고정한다
    out = {'games': args.games, 'seed': args.seed, 'knobs': knobs, 'real_winners': board_summary(real_winners()),
           'real_families': real_families()}
    for key in args.conditions.split(','):
        label = CONDITIONS[key]
        start = time.perf_counter()
        with Pool(args.jobs) as workers:  # 조건마다 새 일꾼(덱 봇의 덱 목록 등록이 다른 조건에 새지 않게)
            results = workers.map(partial(lobby.play, bot=key, knobs=knobs), games, chunksize=1)
        players = [p for r in results for p in r['players']]
        curves = [r['curve'] for r in results]
        carry = [p['carry21'] for p in players if p['carry21'] is not None]
        modes = defaultdict(list)
        for p in players:
            modes[p['mode']].append(p['place'])
        out[label] = {'seconds': time.perf_counter() - start, 'curve': curve_table(curves),
                      'curve_win': curve_table(curves, 'win'), 'curve_lose': curve_table(curves, 'lose'),
                      'curve_normal': curve_table(curves, style=False), 'curve_slow': curve_table(curves, style=True),
                      'curve_normal_win': curve_table(curves, 'win', False),
                      'curve_normal_lose': curve_table(curves, 'lose', False),
                      'winners': board_summary([p['board'] for p in players if p['place'] == 1]),
                      'all': board_summary([p['board'] for p in players]),
                      'carry21': statistics.mean(carry) if carry else None,
                      'modes': {str(m): [len(v), statistics.mean(v)] for m, v in modes.items()},
                      'switches': statistics.mean(p['switches'] for p in players),
                      'families': family_table(players),
                      'winner_boards': [p['board'] for p in players if p['place'] == 1]}

    for label in [CONDITIONS[k] for k in args.conditions.split(',')]:
        o = out[label]
        print(f'\n[{label}] {args.games}판 {o["seconds"]:.0f}초, 캐리 아이템(5단계) {fmt(o["carry21"])}, '
              f'아이템 완성 비율(전체 보드) {fmt(o["all"]["item_use"])}, 받은 아이템(조각으로) {fmt(o["all"]["item_worth"], False)}, '
              f'덱 갈아타기 {o["switches"]:.2f}번/명')
        for tag, rows in (('전체', o['curve']), ('연승형', o['curve_win']), ('연패형', o['curve_lose']),
                          ('보통 덱', o['curve_normal']), ('보통 연승', o['curve_normal_win']),
                          ('보통 연패', o['curve_normal_lose']), ('느린 덱', o['curve_slow'])):
            for r in rows:
                print(f'  {tag:4} {r["when"]:7} 가이드 {r["guide"]:>4} | 레벨 {r["level"]:.2f} 7+ {fmt(r["lv7"])} '
                      f'8+ {fmt(r["lv8"])} 9 {fmt(r["lv9"])} 골드 {r["gold"]:.1f} 체력 {r["hp"]:.1f} (살아 있음 {r["alive"]})')
        print('  초반 전략별 (명, 평균 등수):', o['modes'])
        print('  계열 (몫, 평균 등수):', [(f, fmt(s), round(a, 2)) for f, s, a in o['families'][:8]])
    print('\n실제 메타 트렌드 계열 (몫, 평균 등수):', [(f, fmt(s), round(a, 2)) for f, s, a in out['real_families']])
    print('\n1등 보드')
    keys = [('boards', '보드 수', False), ('nine_plus', '9유닛 이상', True), ('two_star_4cost', '4코스트 2성 이상', True),
            ('two_star_5cost', '5코스트 2성 이상', True), ('three_star_per_board', '보드당 3성', False),
            ('items_median', '완성 아이템 가운데 값', False), ('chosen_kinds', '선택받은 자 특성 가짓수', False),
            ('chosen_off_family', '선택받은 자가 계열 특성이 아닌 비율', True), ('no_family', '큰 특성 없는 보드', True)]
    columns = [('실제 1등', out['real_winners'])] + [(CONDITIONS[k] + ' 1등', out[CONDITIONS[k]]['winners'])
                                                  for k in args.conditions.split(',')]
    for key, name, pct in keys:
        print(f'  {name}: ' + ' / '.join(f'{label}: {fmt(s[key], pct)}' for label, s in columns))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
