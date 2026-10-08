"""
실제 10.24 최종 보드끼리 시뮬레이터에서 붙인다.

롤체지지 메타 트렌드(핫픽스 전, 다이아 이상) 조합 27개를 보드로 만들어 서로 모두 붙이고(라운드로빈),
보드마다 나머지 26개 상대 평균 승률을 실제 평균 등수와 순위로 비교한다.
순위가 맞으면 전투는 믿을 만하고, 봇이 실제와 다른 건 운영(플레이) 탓이다. 안 맞으면 전투부터 고친다.

보드 만들기 (meta/lolchess_10.24_2020-11-28.json의 trends)
  유닛: 그 조합에 적힌 유닛 그대로(8~9명).
  아이템: 페이지에 보이던 추천 아이템(보드마다 8개).
  선택받은 자: 조합 이름에 적힌 특성 수가 유닛만으로 센 수보다 큰 특성. 유닛은 그 특성의 1~4코스트 중
              아이템이 많은 쪽, 같으면 비싼 쪽, 그래도 같으면 먼저 적힌 쪽(meta/pit.chosen_of와 같은 규칙).
  상징 아이템: 그 차이가 2면(전쟁군주 9, 결투가 8) 상징이 하나 더 있는 것이다. 그 특성이 없고 아이템이 3개보다
              적은 첫 유닛이 든다.
  별: 모두 2성. 비교용으로 5코스트만 1성.
  배치: 근접 앞줄, 원거리 뒷줄(analysis/battle.range_positions).
  수치: 자료가 10.24 중간 패치(12/1) 전이라 그 전 값으로 되돌린다(prehotfix). 비교용으로 지금 값(핫픽스 뒤).
  케인 형태는 고르지 않는다(meta/pit과 같다). 실제로는 최종 보드의 케인은 거의 다 형태가 있다.

실행: python -m meta.real_boards --n 60 --jobs 7 --out results/real_boards_1024.json
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import CHAMPION_TRAITS, TRAIT_BREAKS, cost_of
from Simulator.item_stats import item_builds, trait_items
from meta.pit import average, round_robin

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_10.24_2020-11-28.json')
SIM_ITEM = {k.replace('_', ''): k for k in item_builds}     # 'LocketoftheIronSolari' -> locket_of_the_iron_solari
SIM_TRAIT = {k.replace('_', ''): k for k in TRAIT_BREAKS}   # 'TheBoss' -> the_boss

# (이름, 5코스트 별, 핫픽스 전 값으로 되돌리나)
VARIANTS = [('main', 2, True), ('five_cost_1star', 1, True), ('post_hotfix', 2, False)]
LABEL = {'main': '2성', 'five_cost_1star': '5코 1성', 'post_hotfix': '핫픽스 뒤'}


def prehotfix():
    """10.24 중간 패치(12/1, 공식 노트 Mid-Patch Updates)를 되돌린다. 일꾼 프로세스마다 부른다."""
    import Simulator.config as config
    from Simulator import item_stats, origin_class_stats, stats
    config.GALIO_MULTIPLIER = 0.12
    stats.HEALTH['galio'] = [0, 1000, 1650, 2250]
    stats.AD['galio'] = [0, 85, 180, 320]
    origin_class_stats.shield['keeper'] = [0, 175, 250, 350]
    origin_class_stats.length['keeper'] = [0, 8000, 10000, 14000]
    stats.AS['zed'] = 0.8
    stats.ACTIVE_STOLEN_AD['zed'] = [0, 0.30, 0.35, 0.40]
    stats.MAXMANA['yone'] = 50
    stats.ABILITY_ARMOR_MR_DECREASE['yone'] = 0.10  # 남는 비율로 적는다. 90% 깎기 = 0.10
    item_stats.damage['runaans_hurricane'] = 1.0


def load_trends(path=SRC):
    boards = []
    for t in json.load(open(path, encoding='utf-8'))['trends']:
        units = [u['name'].lower() for u in t['units']]
        assert all(u in CHAMPION_TRAITS for u in units), (t['key'], units)
        items = {u: [SIM_ITEM[i.lower()] for i in raw['recommended']]
                 for u, raw in zip(units, t['units']) if raw['recommended']}

        traits = {SIM_TRAIT[k.lower()]: n for k, n in t['traits'].items()}
        counts = Counter(tr for u in units for tr in CHAMPION_TRAITS[u])
        gaps = {tr: n - counts[tr] for tr, n in traits.items() if n != counts[tr]}
        # 선택받은 자는 하나뿐이다. 특성이 둘 이상 남거나 모자라면 유닛 목록이 보드와 다른 것이다.
        assert len(gaps) == 1 and list(gaps.values())[0] in (1, 2), (t['key'], gaps)
        (trait, gap), = gaps.items()

        order = {u: i for i, u in enumerate(units)}
        pool = [u for u in units if trait in CHAMPION_TRAITS[u] and cost_of(u) < 5]
        chosen = min(pool, key=lambda u: (-len(items.get(u, [])), -cost_of(u), order[u]))
        emblem = None
        if gap == 2:
            emblem = next(u for u in units if trait not in CHAMPION_TRAITS[u] and len(items.get(u, [])) < 3)
            items.setdefault(emblem, []).append(trait_items[trait])

        boards.append({'key': t['key'], 'traits': traits, 'units': units, 'items': items, 'chosen': [chosen, trait],
                       'emblem': emblem, 'pick_rate': t['pick_rate'], 'games_score': t['games_score'],
                       'place': t['average_placement'], 'top4': t['top4_rate'], 'win': t['win_rate']})
    return boards


def spec(board, five_cost_stars):
    out = []
    for name in board['units']:
        unit = {'name': name, 'stars': five_cost_stars if cost_of(name) == 5 else 2,
                'items': board['items'].get(name, [])}
        if name == board['chosen'][0]:
            unit['chosen'] = board['chosen'][1]
        out.append(unit)
    return out


def ranks(values):
    """작은 값이 0번. 같은 값은 평균 순위."""
    s = sorted(values)
    return [s.index(v) + (s.count(v) - 1) / 2 for v in values]


def spearman(x, y):
    return statistics.correlation(ranks(x), ranks(y))


def perm_p(x, y, k=10000):
    """순서를 섞었을 때 순위 상관이 이만큼 이상 나올 비율(한쪽). 작을수록 우연이 아니다."""
    rx, ry = ranks(x), ranks(y)
    rho = statistics.correlation(rx, ry)
    rng = random.Random(0)
    hits = 0
    for _ in range(k):
        rng.shuffle(ry)
        hits += statistics.correlation(rx, ry) >= rho - 1e-12
    return (hits + 1) / (k + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=60, help='매치업당 판 수')
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=None, help='결과 JSON 저장 경로')
    args = ap.parse_args()

    boards = load_trends()
    print('보드 만들기 (선택받은 자, 상징 아이템을 든 유닛)')
    for b in boards:
        print(f'  {b["key"][:58]:58} {len(b["units"])}명  {b["chosen"][0]}({b["chosen"][1]})'
              + (f'  상징 {b["emblem"]}' if b['emblem'] else ''))

    matrices = {}
    for name, five, pre in VARIANTS:
        matrices[name] = round_robin({b['key']: spec(b, five) for b in boards}, args.n, 'range', args.jobs,
                                     init=prehotfix if pre else None)
        print(f'{LABEL[name]} 완료', flush=True)
    avg = {name: average(m) for name, m in matrices.items()}

    # 상대 26개 x N판이라 평균 승률의 표준오차는 N=60에서 1.3%p 안팎이다.
    print(f'\n보드별 (실제 평균 등수 순, 시뮬레이터는 상대 {len(boards) - 1}개 평균 승률, 매치업당 N={args.n})')
    print(f'{"조합":58} {"유닛":>4} {"고른 비율":>8} {"평균 등수":>8}' + ''.join(f' {LABEL[v]:>8}' for v, _, _ in VARIANTS))
    for b in sorted(boards, key=lambda b: b['place']):
        print(f'{b["key"][:58]:58} {len(b["units"]):4d} {b["pick_rate"] * 100:7.1f}% {b["place"]:8.2f}'
              + ''.join(f' {avg[v][b["key"]] * 100:7.1f}%' for v, _, _ in VARIANTS))

    # 실제는 등수가 낮을수록 좋으니 부호를 뒤집는다. 상관이 양수면 시뮬레이터가 실제와 같은 쪽으로 줄 세운 것이다.
    subsets = [('전체', boards),
               ('유닛 8명 보드만', [b for b in boards if len(b['units']) == 8]),
               ('유닛 9명 보드만', [b for b in boards if len(b['units']) == 9]),
               ('닌자 그림자 빼고', [b for b in boards if '4ninja' not in b['key']])]
    summary = {}
    print('\n실제 평균 등수와의 순위 상관 (괄호는 섞어서 이만큼 나올 확률)')
    for label, group in subsets:
        real = [-b['place'] for b in group]
        cols = {v: spearman(real, [avg[v][b['key']] for b in group]) for v, _, _ in VARIANTS}
        p = perm_p(real, [avg['main'][b['key']] for b in group])
        # 비교 기준: 전투 없이 유닛 수나 코스트 합만으로 줄 세웠을 때. 유닛 수가 다 같은 묶음에서는 못 잰다.
        sizes = [len(b['units']) for b in group]
        base_units = spearman(real, sizes) if len(set(sizes)) > 1 else None
        base_cost = spearman(real, [sum(cost_of(u) for u in b['units']) for b in group])
        summary[label] = {'n': len(group), **cols, 'main_p': p, 'units': base_units, 'cost': base_cost}
        print(f'  {label:12} ({len(group):2d}개)  ' + '  '.join(f'{LABEL[v]} {cols[v]:+.2f}' for v, _, _ in VARIANTS)
              + f'  (2성 p={p:.3f})  기준: 유닛 수 ' + (f'{base_units:+.2f}' if base_units is not None else '  - ')
              + f', 코스트 합 {base_cost:+.2f}')

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'n': args.n, 'boards': boards, 'average': avg, 'summary': summary, **matrices},
                      f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
