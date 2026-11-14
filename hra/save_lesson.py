"""
「돈 모으기」 수업 점검(2026-11-14). 새 판은 돌리지 않는다.

양쪽 모두 교과서(규칙 사람 봇)인 대조 실행(hra/spend_lesson.py의 팔 none)의 자리별 기록 [칸, 레벨, 골드, 체력]을 읽어, 교과서의
2~3단계 골드·레벨이 2020년 10.24 무렵 글의 기준점과 맞는지 센다. 기준점과 판정은 results/README.md 「돈 모으기」 수업 점검에
숫자를 세기 전에 적었다. 기록의 골드는 라운드를 시작할 때 수입을 받은 뒤 값이다. 이기고 진 것은 대전 라운드에서 체력이 줄었는지로
알고, 거기서 연속 골드와 이자가 붙기 직전 골드를 되짚는다(walk). 4-1(15번째 칸) 뒤는 유령 대전이 생겨 되짚지 않는다.

시뮬레이터의 수입 규칙(june Simulator/player.py의 gold_income·won_round): 1-3·1-4·2-1을 시작할 때 4·3·4골드, 2-2부터 5골드.
이자는 직전 골드 10마다 1(최대 5). 연승·연패 2~3이면 +1, 4면 +2, 5 이상이면 +3. 대전을 이기면 그 자리에서 +1. 크립 라운드는
연속을 잇지도 끊지도 않는다.

실행: python -m hra.save_lesson results/spend_lesson_none.json results/spend_lesson_none_cap30.json --out results/save_lesson.json
"""
import argparse
import json
import statistics

PVE = (1, 2, 8, 14)         # 1-3, 1-4, 2-7 크립, 3-7 늑대
START = {1: 4, 2: 3, 3: 4}  # 이 칸을 시작할 때 수입(연속 골드가 없다)
LAST = 15                   # 4-1
STAGE = {3: '2-1', 4: '2-2', 5: '2-3', 6: '2-5', 7: '2-6', 8: '2-7', 9: '3-1', 10: '3-2', 11: '3-3', 12: '3-5', 13: '3-6',
         14: '3-7', 15: '4-1'}
EARLY = {'win': '끝까지 연승형', 'switch': '연승형이었다가 연패형', 'lose': '처음부터 연패형'}
STATE = {'win': '연승 3 이상', 'lose': '연패 3 이상', 'mixed': '그 밖(퐁당)'}
PATHS = {'전승': [True] * 10, '전패': [False] * 10, '번갈아(이기고 시작)': [True, False] * 5}


def interest(gold):
    return min(gold // 10, 5)


def streak_gold(n):
    return 0 if n < 2 else 1 if n < 4 else 2 if n == 4 else 3


def before_interest(total):
    """「이자가 붙기 직전 골드 + 이자」가 total인 직전 골드. 골드가 1 늘면 그 합도 1 이상 늘어 답은 많아야 하나고, 없으면 None."""
    return next((g for g in range(max(total - 5, 0), total + 1) if g + interest(g) == total), None)


def walk(curve):
    """자리 곡선에서 4-1까지 수입마다 되짚은 값. slot은 수입을 받은 칸, before는 이자가 붙기 직전 골드(앞 라운드를 이겨 받은 1골드
    포함), streak는 연속 골드, won은 앞 라운드를 이겼는가(크립 라운드면 None), wins·losses는 그때의 연승·연패 수다.
    수입이 규칙과 안 맞으면 before와 interest가 None이다."""
    rows, wins, losses = [], 0, 0
    for prev, cur in zip(curve, curve[1:]):
        slot = cur[0]
        if slot > LAST:
            break
        won = None
        if prev[0] >= 3 and prev[0] not in PVE:
            won = cur[3] >= prev[3]  # 지거나 비기면 체력이 적어도 1 깎인다
            wins, losses = (wins + 1, 0) if won else (0, losses + 1)
        bonus = 0 if slot in START else streak_gold(max(wins, losses))
        before = before_interest(cur[2] - (START[slot] if slot in START else 5 + bonus))
        rows.append({'slot': slot, 'before': before, 'interest': None if before is None else interest(before), 'streak': bonus,
                     'won': won, 'wins': wins, 'losses': losses})
    return rows


def early(rows):
    """교과서의 초반 전략을 되짚는다(meta/human_bot.update_mode). 2-3(5번째 칸)을 시작할 때 2연승이면 연승형이고, 그 뒤 4-1 전의
    라운드를 시작할 때 2연패를 보면 연패형으로 바뀐다. 'win' 끝까지 연승형, 'switch' 연승형이었다가 연패형, 'lose' 처음부터 연패형."""
    if next(r for r in rows if r['slot'] == 5)['wins'] < 2:
        return 'lose'
    return 'switch' if any(r['losses'] >= 2 for r in rows if 5 < r['slot'] < LAST) else 'win'


def ceiling(pattern, gold=10):
    """한 푼도 안 쓸 때의 칸별 시작 골드. 2-1(3번째 칸)을 gold로 시작하고, pattern은 대전 라운드 10개(2-1 ~ 3-6)를 이겼는가다.
    크립이 주는 골드는 뺀다."""
    out, wins, losses, results = {3: gold}, 0, 0, iter(pattern)
    for slot in range(3, LAST):
        if slot not in PVE:
            won = next(results)
            wins, losses = (wins + 1, 0) if won else (0, losses + 1)
            gold += won
        gold += interest(gold) + 5 + streak_gold(max(wins, losses))
        out[slot + 1] = gold
    return out


def verdict(share):
    """미리 정한 문턱: 맞춘 자리가 80% 이상, 50% 이상, 그 아래."""
    return '맞춘다' if share >= 0.8 else '절반 넘게 맞춘다' if share >= 0.5 else '못 맞춘다'


def seat(row):
    """자리 기록 하나 -> 칸별 (레벨, 골드, 체력) at, 칸별 되짚은 수입 inc, 초반 전략 early, 끝 등수 place."""
    rows = walk(row['curve'])
    return {'at': {c[0]: c[1:] for c in row['curve']}, 'inc': {r['slot']: r for r in rows}, 'early': early(rows),
            'place': row['place']}


MARKS = (  # (번호, 그때 글의 기준점, 자리에서 읽는 값, 맞춘 것으로 치는 아래 끝, 위 끝)
    (1, '2-1을 10골드로 시작', lambda s: s['at'][3][1], 10, None),
    (2, '2단계 회전초밥 전 10골드', lambda s: s['inc'][6]['before'], 10, None),
    (3, '2-7 크립 뒤 20~40골드', lambda s: s['at'][9][1], 20, 40),
    (4, '3-7 늑대 앞 50골드 이상', lambda s: s['at'][14][1], 50, None),
    (5, '4-1에 50골드', lambda s: s['at'][15][1], 50, None),
    (6, '레벨 4는 2-1이나 2-2', lambda s: s['at'][5][0], 4, None),
    (7, '레벨 5는 2-5', lambda s: s['at'][7][0], 5, None),
    (8, '레벨 6은 3-1이나 3-2', lambda s: s['at'][11][0], 6, None),
)


def checks(games):
    """판마다 자리(seat) 목록 -> 기준점 번호별 맞춘 몫 met, 판 사이 표준오차 se, 범위 아래·위 몫 below·above, 값의 평균과
    가운데·10%·90% 자리 값, 자리가 있는 판 수 games."""
    out = {}
    for no, name, read, lo, hi in MARKS:
        per_game = [[read(s) for s in g] for g in games if g]
        vals = sorted(v for g in per_game for v in g)
        ok = lambda v: v >= lo and (hi is None or v <= hi)
        shares = [statistics.mean(ok(v) for v in g) for g in per_game]
        out[no] = {'name': name, 'met': statistics.mean(ok(v) for v in vals),
                   'se': statistics.stdev(shares) / len(shares) ** 0.5 if len(shares) > 1 else None,
                   'below': statistics.mean(v < lo for v in vals), 'above': statistics.mean(hi is not None and v > hi for v in vals),
                   'mean': statistics.mean(vals), 'median': statistics.median(vals), 'p10': vals[len(vals) // 10],
                   'p90': vals[len(vals) * 9 // 10], 'games': len(per_game)}
    return out


def income(s):
    """2-2부터 4-1까지 수입 12번(기본 60골드)에서 받은 이자(2단계·3단계), 못 받은 이자, 연속 골드, 승리 골드와,
    그동안 쓴 돈(유닛·경험치·리롤을 합친 값에서 크립이 준 골드를 뺀 값)."""
    inc = [s['inc'][t] for t in range(4, LAST + 1)]
    got = lambda rows: sum(5 + r['interest'] + r['streak'] + (r['won'] is True) for r in rows)
    out = {'interest2': sum(r['interest'] for r in inc[:6]), 'interest3': sum(r['interest'] for r in inc[6:]),
           'streak': sum(r['streak'] for r in inc), 'wins': sum(r['won'] is True for r in inc)}
    out['missed'] = 5 * len(inc) - out['interest2'] - out['interest3']
    out['got2'] = got(inc[:6])                                  # 2단계(2-2 ~ 3-1 시작)에 들어온 돈
    out['spent2'] = s['at'][3][1] + out['got2'] - s['at'][9][1]  # 2단계(2-1 ~ 2-7 라운드)에 쓴 돈
    out['spent'] = s['at'][3][1] + got(inc) - s['at'][LAST][1]
    return out


def state(row):
    return 'win' if row['wins'] >= 3 else 'lose' if row['losses'] >= 3 else 'mixed'


def after(seats):
    """결과를 본 뒤에 더 센 것(미리 적지 않았다): 4-1을 시작할 때의 골드·체력과 끝 등수의 관계."""
    gold = [s['at'][LAST][1] for s in seats]
    hp = [s['at'][LAST][2] for s in seats]
    place = [s['place'] for s in seats]

    def bands(vals, cuts):
        out = []
        for lo, hi in zip(cuts, cuts[1:] + (10 ** 9,)):
            mine = [k for k, v in enumerate(vals) if lo <= v < hi]
            out.append({'from': lo, 'seats': len(mine), **{n: statistics.mean(x[k] for k in mine) if mine else None
                                                          for n, x in (('gold', gold), ('hp', hp), ('place', place))}})
        return out
    return {'gold_sd': statistics.pstdev(gold), 'hp_sd': statistics.pstdev(hp),
            'gold_place_corr': statistics.correlation(gold, place), 'hp_place_corr': statistics.correlation(hp, place),
            'by_gold': bands(gold, (0, 60, 67)), 'by_hp': bands(hp, (0, 45, 65, 85))}


def first_difference(a, b):
    """같은 시드로 돈 두 실행의 자리별 곡선이 4-1까지에서 처음 달라지는 칸 -> 자리 수. 4-1까지 같으면 None."""
    out = {}
    for x, y in zip((s for g in a for s in g), (s for g in b for s in g)):
        slot = next((p[0] for p, q in zip(x['curve'], y['curve']) if p != q and p[0] <= LAST), None)
        out[slot] = out.get(slot, 0) + 1
    return out


def _mean(seats, read):
    return statistics.mean(read(s) for s in seats) if seats else None


def _group(seats, total):
    """묶음 하나의 자리 수와 몫, 4-1을 시작할 때 골드·체력, 끝 등수, 4등 안 비율."""
    return {'seats': len(seats), 'share': len(seats) / total, 'gold41': _mean(seats, lambda s: s['at'][LAST][1]),
            'hp41': _mean(seats, lambda s: s['at'][LAST][2]), 'place': _mean(seats, lambda s: s['place']),
            'top4': _mean(seats, lambda s: s['place'] <= 4)}


def report(res):
    """대조 실행 결과 하나 -> 판정 표와 함께 적는 표들."""
    games = [[seat(r) for r in g] for g in res['rows']]
    seats = [s for g in games for s in g]
    assert all(LAST in s['at'] for s in seats), '4-1 전에 탈락한 자리가 있으면 유령 대전 때문에 되짚을 수 없다'
    out = {'cap': res['actions_per_turn'], 'games': len(games), 'seats': len(seats),
           'unexplained': sum(r['before'] is None for s in seats for r in s['inc'].values()), 'marks': checks(games)}
    for m in out['marks'].values():
        m['verdict'] = verdict(m['met'])
    out['path'] = {STAGE[t]: {'gold': _mean(seats, lambda s: s['at'][t][1]),
                              'gold_median': statistics.median(s['at'][t][1] for s in seats),
                              'level': _mean(seats, lambda s: s['at'][t][0]), 'hp': _mean(seats, lambda s: s['at'][t][2]),
                              **{'ceiling_' + n: ceiling(p)[t] for n, p in PATHS.items()}} for t in STAGE}
    out['early'] = {}
    for key in EARLY:
        part = [[s for s in g if s['early'] == key] for g in games]
        mine = [s for g in part for s in g]
        out['early'][key] = {**_group(mine, len(seats)), 'marks': {no: m['met'] for no, m in checks(part).items()},
                             'gold': {STAGE[t]: _mean(mine, lambda s: s['at'][t][1]) for t in (9, 10, 11, 14)},
                             'hp31': _mean(mine, lambda s: s['at'][9][2]),
                             'income': {k: _mean(mine, lambda s: income(s)[k]) for k in income(mine[0])}}
    out['income'] = {k: _mean(seats, lambda s: income(s)[k]) for k in income(seats[0])}
    out['states'] = {}
    for t in (10, 12, LAST):
        cells = {}
        for key in STATE:
            mine = [s for s in seats if state(s['inc'][t]) == key]
            cells[key] = {'seats': len(mine), 'share': len(mine) / len(seats), 'gold': _mean(mine, lambda s: s['at'][t][1]),
                          'gold_median': statistics.median(s['at'][t][1] for s in mine) if mine else None,
                          'level': _mean(mine, lambda s: s['at'][t][0]), 'hp': _mean(mine, lambda s: s['at'][t][2]),
                          'place': _mean(mine, lambda s: s['place']), 'top4': _mean(mine, lambda s: s['place'] <= 4)}
        out['states'][STAGE[t]] = cells
    out['after'] = after(seats)
    return out


def show(reports):
    """README에 옮길 표를 찍는다. 첫 결과가 주 조건이다."""
    main = reports[0]
    pct = lambda x: f'{100 * x:.1f}%'
    print('되짚기가 규칙과 안 맞는 수입: ' + ', '.join(f"상한 {r['cap']} {r['unexplained']}개" for r in reports))
    print('\n| 번호 | 기준점 | ' + ' | '.join(f"상한 {r['cap']}: 맞춘 자리 | 값의 가운데 (10%~90% 자리) | 판정" for r in reports) + ' |')
    print('|---|---|' + '---|---|---|' * len(reports))
    for no, name, *_ in MARKS:
        cells = []
        for r in reports:
            m = r['marks'][no]
            band = f" (아래 {pct(m['below'])}, 위 {pct(m['above'])})" if no == 3 else ''
            cells.append(f"{pct(m['met'])} ± {100 * m['se']:.1f}%p{band} | {m['median']:g} ({m['p10']}~{m['p90']}) | {m['verdict']}")
        print(f'| {no} | {name} | ' + ' | '.join(cells) + ' |')
    print('\n| 라운드 시작 | ' + ' | '.join(f"상한 {r['cap']}: 골드 평균 (가운데) | 레벨 | 체력" for r in reports)
          + ' | 안 쓸 때의 천장: ' + ' | '.join(PATHS) + ' |')
    print('|---|' + '---|---|---|' * len(reports) + '---|' * len(PATHS))
    for name, p in main['path'].items():
        cells = [f"{r['path'][name]['gold']:.1f} ({r['path'][name]['gold_median']:g}) | {r['path'][name]['level']:.2f} | "
                 f"{r['path'][name]['hp']:.1f}" for r in reports]
        print(f'| {name} | ' + ' | '.join(cells) + ' | ' + ' | '.join(str(p['ceiling_' + n]) for n in PATHS) + ' |')
    for r in reports:
        print(f"\n상한 {r['cap']}: 초반 전략별")
        print('| 초반 전략 | 자리 (몫) | 3번: 크립 뒤 20~40 | 7번: 2-5에 레벨 5 | 8번: 3-2까지 레벨 6 | 골드 3-1 / 3-2 / 3-3 / 3-7 / 4-1 | 체력 3-1 / 4-1 '
              '| 받은 이자 2단계 + 3단계 (못 받은 몫) | 연속 골드 | 승리 골드 | 쓴 돈 2단계 / 2~3단계 | 끝 등수 | 4등 안 |')
        print('|---|' + '---|' * 12)
        rows = [(EARLY[k], e) for k, e in r['early'].items()]
        whole = {**_group_of(r), 'marks': {no: m['met'] for no, m in r['marks'].items()},
                 'gold': {n: r['path'][n]['gold'] for n in ('3-1', '3-2', '3-3', '3-7')}, 'hp31': r['path']['3-1']['hp'],
                 'income': r['income']}
        for name, e in rows + [('전체', whole)]:
            i = e['income']
            print(f"| {name} | {e['seats']} ({pct(e['share'])}) | {pct(e['marks'][3])} | {pct(e['marks'][7])} | {pct(e['marks'][8])} | "
                  f"{e['gold']['3-1']:.1f} / {e['gold']['3-2']:.1f} / {e['gold']['3-3']:.1f} / {e['gold']['3-7']:.1f} / {e['gold41']:.1f} | "
                  f"{e['hp31']:.1f} / {e['hp41']:.1f} | {i['interest2']:.1f} + {i['interest3']:.1f} ({i['missed']:.1f}) | "
                  f"{i['streak']:.1f} | {i['wins']:.1f} | {i['spent2']:.1f} / {i['spent']:.1f} | {e['place']:.2f} | {pct(e['top4'])} |")
        print(f"\n상한 {r['cap']}: 연속 상태별")
        print('| 라운드 시작 | 상태 | 자리 (몫) | 골드 평균 (가운데) | 레벨 | 체력 | 끝 등수 | 4등 안 |\n|---|---|---|---|---|---|---|---|')
        for name, cells in r['states'].items():
            for key, c in cells.items():
                print(f"| {name} | {STATE[key]} | {c['seats']} ({pct(c['share'])}) | {c['gold']:.1f} ({c['gold_median']:g}) | "
                      f"{c['level']:.2f} | {c['hp']:.1f} | {c['place']:.2f} | {pct(c['top4'])} |")
        x = r['after']
        print(f"\n상한 {r['cap']}: 결과를 본 뒤에 더 센 것. 4-1 시작 골드의 표준편차 {x['gold_sd']:.1f}, 체력 {x['hp_sd']:.1f}. "
              f"끝 등수와의 상관은 골드 {x['gold_place_corr']:+.3f}, 체력 {x['hp_place_corr']:+.3f}")
        for label, key in (('4-1 골드', 'by_gold'), ('4-1 체력', 'by_hp')):
            print(f'| {label} | 자리 | 골드 | 체력 | 끝 등수 |\n|---|---|---|---|---|')
            for lo, hi in zip(x[key], x[key][1:] + [None]):
                name = f"{lo['from']} 이상" if hi is None else f"{lo['from']}~{hi['from'] - 1}"
                print(f"| {name} | {lo['seats']} | {lo['gold']:.1f} | {lo['hp']:.1f} | {lo['place']:.2f} |")
        if 'first_difference' in r:
            print(f"\n상한 {reports[0]['cap']}·{r['cap']}의 기록이 처음 달라지는 라운드 시작(자리 수): {r['first_difference']}")


def _group_of(r):
    """전체 줄: 초반 전략 묶음을 자리 수로 가중해 합친다."""
    e = list(r['early'].values())
    w = lambda k: sum(x[k] * x['seats'] for x in e) / r['seats']
    return {'seats': r['seats'], 'share': 1.0, 'gold41': w('gold41'), 'hp41': w('hp41'), 'place': w('place'), 'top4': w('top4')}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='+', help='대조 실행 결과 파일. 첫 파일이 주 조건이다')
    ap.add_argument('--out')
    a = ap.parse_args()
    runs = [json.load(open(p, encoding='utf-8')) for p in a.results]
    reports = [report(r) for r in runs]
    for r, run in zip(reports[1:], runs[1:]):  # 같은 시드의 다른 조건이 주 조건과 어디서 갈리는가
        diff = first_difference(runs[0]['rows'], run['rows'])
        r['first_difference'] = {STAGE.get(k, '4-1까지 같음'): diff[k] for k in sorted(diff, key=lambda k: k or 99)}
    show(reports)
    if a.out:
        json.dump(reports, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
