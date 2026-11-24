"""대전당 피해를 실제 판 기록과 견준다(판정 없음, 읽기만, 2026-11-24, results/README 「대전당 피해를 실제 판과 견주기: 미리 정한 읽기」).

실제 쪽: meta/real_games.py와 같은 Kaggle 판 기록의 10.24 판. 자리마다 등수, 끝난 라운드, 「플레이어에게 준 피해 합」만 쓴다.
         판 번호와 플레이어 식별 칸은 판을 묶는 데만 쓰고 결과에 남기지 않는다.
시뮬레이터 쪽: meta/inversion/board4.py를 BOARD4_ROUNDS=0,99로 돌린 교과서 여덟 자리 기록(대전마다 승패와 진 쪽 피해).

- 사람끼리 대전 수: 대전 라운드마다 살아 있는 자리 수 ÷ 2(내림). 실제는 끝난 라운드에서, 시뮬레이터는 대전 기록에서 센다.
- 준 피해: 실제는 기록의 값. 시뮬레이터는 사람끼리 대전에서 이긴 쪽이 준 피해(「유령 뺌」)와, 거기에 유령 대전에서 복사된 보드가
  이겨 준 피해를 복사된 자리 몫으로 더한 값(「유령 넣음」) 둘을 낸다. 실제 값이 유령 몫을 세는지 모르기 때문이다.
- 단계를 맞춘 비 = 실제 준 피해 합 ÷ (실제 단계별 대전 수 × 시뮬레이터 단계별 대전당 피해). 1이면 같은 단계의 대전이 평균 같은 크기로 끝난다.
- 구간은 판을 다시 뽑는 부트스트랩(실제 판과 시뮬레이터 판을 각각 200번)이다.

내려받은 파일을 읽으므로 표준 라이브러리만 쓰고 격리 실행한다(저장소 맨 위에서):
    python -I meta/inversion/dealt_read.py <csv> meta/inversion/dealt_rows.json results/dealt_read.json
    python -I meta/inversion/dealt_read.py <csv> --structure   (피해는 안 보고 판 수와 생존 수만 본다)
    python -I meta/inversion/dealt_read.py selfcheck
"""
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict

PATCH = '10.24'
STAGE_DAMAGE = [0, 0, 2, 3, 5, 8, 15]  # june Simulator/stats.py STAGE_DAMAGE(공식 10.24). 스테이지 8부터는 마지막 값
PER_UNIT = [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]  # june DAMAGE_PER_UNIT(살아남은 유닛 수 -> 피해)
FIRST_ROUND = 19  # meta/real_games.py와 같다. 1등이 4-1 전에 끝난 판은 다시 하기로 본다
ALIVE = {'5-1': 26, '5-5': 30, '6-1': 33, '6-5': 37, '7-1': 40}  # meta/real_games.py와 같다
VALID = (600, 1000)  # 실제 판당 준 피해 합이 이 밖이면 읽지 않는다
MIN_LATE = 30  # 시뮬레이터의 7단계 이후 대전이 이보다 적으면 6단계와 합친다
BOOT, BOOT_SEED = 200, 0


def real_stage(r):
    """실제 라운드 번호(1부터) -> (단계, 칸). 1단계는 네 칸, 2단계부터 일곱 칸이다."""
    if r <= 4:
        return 1, r
    s, k = divmod(r - 5, 7)
    return s + 2, k + 1


def real_pvp(r):
    s, k = real_stage(r)
    return s >= 2 and k in (1, 2, 3, 5, 6)


def slot_stage(slot):
    """시뮬레이터 칸 번호(회전초밥을 뺀 번호) -> 단계. june Simulator/stats.py round_stage와 같다."""
    return 1 if slot < 3 else 2 + (slot - 3) // 6


def base(stage):
    return STAGE_DAMAGE[min(stage, len(STAGE_DAMAGE)) - 1]


def real_lobby(seats):
    """실제 한 판. seats = [(등수, 끝난 라운드, 준 피해)] 여덟 자리."""
    fights, played = Counter(), Counter()
    for r in range(5, max(s[1] for s in seats) + 1):
        alive = [i for i, s in enumerate(seats) if s[1] >= r]
        if real_pvp(r) and len(alive) >= 2:
            fights[real_stage(r)[0]] += len(alive) // 2
            played.update(alive)
    return {'F': fights, 'D': Counter(), 'G': Counter(), 'total': sum(s[2] for s in seats),
            'seats': [(p, d, 0, played[i]) for i, (p, _, d) in enumerate(seats)], 'last': [s[1] for s in seats]}


def sim_lobby(rows, fights):
    """시뮬레이터 한 판. rows = 자리 기록(place, pnum), fights = board4.py의 대전 기록(판 끝까지)."""
    F, D, G, dealt, ghost, played = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for f in fights:
        st, (a, b) = slot_stage(f['round']), f['pnum']
        played[a] += 1
        if f['ghost']:
            if f['won'] == 2:  # 복사된 보드가 이겼다. 피해는 복사된 자리 몫으로 따로 센다
                G[st] += f['damage']
                ghost[b] += f['damage']
            continue
        played[b] += 1
        F[st] += 1
        if f['won']:
            D[st] += f['damage']
            dealt[f['pnum'][f['won'] - 1]] += f['damage']
    return {'F': F, 'D': D, 'G': G, 'total': sum(D.values()),
            'seats': [(r['place'], dealt[r['pnum']], ghost[r['pnum']], played[r['pnum']]) for r in rows]}


def capped(counter, top):
    out = Counter()
    for stage, v in counter.items():
        out[min(stage, top)] += v
    return out


def added(lobbies, key, top):
    out = Counter()
    for L in lobbies:
        out.update(capped(L[key], top))
    return out


def ratios(real, sim, top):
    """단계를 맞춘 비 (유령 뺌, 유령 넣음)."""
    F, D, G, R = [added(sim, k, top) for k in 'FDG'] + [added(real, 'F', top)]
    total = sum(L['total'] for L in real)
    return tuple(total / sum(R[s] * (D[s] + g * G[s]) / F[s] for s in R) for g in (0, 1))


def interval(values):
    v = sorted(values)
    return [round(v[int(0.025 * len(v))], 4), round(v[int(0.975 * len(v)) - 1], 4)]


def reading(valid, a, b):
    """a, b = [값, 아래 끝, 위 끝] (유령 뺌, 유령 넣음). 미리 정한 읽기."""
    if not valid:
        return '읽지 않는다(실제 판당 준 피해 합이 미리 정한 범위 밖이다)'
    if a[2] < 0.9 and b[2] < 0.9:
        return '시뮬레이터 판의 대전이 실제보다 크게 끝난다'
    if a[1] > 1.1 and b[1] > 1.1:
        return '시뮬레이터 판의 대전이 실제보다 팽팽하게 끝난다'
    if min(a[1], b[1]) >= 0.9 and max(a[2], b[2]) <= 1.1:
        return '판 전체로 보면 실제와 비슷한 크기로 끝난다'
    return '유령 대전 셈에 달렸거나 가르지 못한다'


def per_fight(F, total, top):
    """대전당 피해, 그 가운데 단계 기본 피해, 나머지(살아남은 유닛 몫). 비김은 드물어 기본 피해를 대전마다 센다."""
    n = sum(F.values())
    b = sum(v * base(s) for s, v in F.items())
    return {'damage': round(total / n, 3), 'base': round(b / n, 3), 'unit': round((total - b) / n, 3)}


def by_place(lobbies, ghost):
    out = {}
    all_d = sum(s[1] + ghost * s[2] for L in lobbies for s in L['seats'])
    for p in range(1, 9):
        seats = [s for L in lobbies for s in L['seats'] if s[0] == p]
        d, r = sum(s[1] + ghost * s[2] for s in seats), sum(s[3] for s in seats)
        out[str(p)] = {'dealt': round(d / len(seats), 2), 'rounds': round(r / len(seats), 2), 'per_round': round(d / r, 3), 'share': round(d / all_d, 4)}
    return out


def survivors(record, top):
    """시뮬레이터만: 단계마다 사람끼리 대전 수, 비김 몫, 이긴 쪽에 남은 유닛 수(피해에서 되짚는다)."""
    cells = defaultdict(Counter)
    for fights in record['fights']:
        for f in fights:
            if f['ghost']:
                continue
            st = slot_stage(f['round'])
            c = cells[min(st, top)]
            c['fights'] += 1
            if f['won']:
                left = PER_UNIT.index(f['damage'] - base(st))  # 표에 없으면 기본 피해나 유닛 피해 표가 기록과 다른 것이다
                c['decided'] += 1
                c['left'] += left
                c['damage'] += f['damage']
                c['left_%d' % min(left, 6)] += 1
    return {str(s): {'fights_per_game': round(c['fights'] / len(record['fights']), 2), 'draw': round(1 - c['decided'] / c['fights'], 4),
                     'damage': round(c['damage'] / c['decided'], 2), 'left': round(c['left'] / c['decided'], 3),
                     'left_share': {str(k): round(c['left_%d' % k] / c['decided'], 3) for k in range(1, 7)}}
            for s, c in sorted(cells.items()) if c['decided']}


def summary(real, sim, boot=BOOT):
    late = sum(v for L in sim for s, v in L['F'].items() if s >= 7)
    top = 7 if late >= MIN_LATE else 6
    rng = random.Random(BOOT_SEED)
    reps = [ratios(rng.choices(real, k=len(real)), rng.choices(sim, k=len(sim)), top) for _ in range(boot)]
    a, b = ([round(v, 4)] + interval([r[i] for r in reps]) for i, v in enumerate(ratios(real, sim, top)))
    rf, sf, sd, sg = added(real, 'F', top), added(sim, 'F', top), added(sim, 'D', top), added(sim, 'G', top)
    real_total = sum(L['total'] for L in real)
    valid = VALID[0] <= real_total / len(real) <= VALID[1]
    side = lambda F, total, n: {'games': n, 'fights_per_game': round(sum(F.values()) / n, 2), 'dealt_per_game': round(total / n, 1),
                                'fights_by_stage': {str(s): round(F[s] / n, 2) for s in sorted(F)}, 'per_fight': per_fight(F, total, top)}
    return {'top_stage': top, 'sim_fights_stage7_up': late, 'valid': valid, 'ratio': {'no_ghost': a, 'with_ghost': b}, 'reading': reading(valid, a, b),
            'real': {**side(rf, real_total, len(real)), 'by_place': by_place(real, 0)},
            'sim_no_ghost': {**side(sf, sum(sd.values()), len(sim)), 'by_place': by_place(sim, 0),
                             'per_fight_by_stage': {str(s): round(sd[s] / sf[s], 3) for s in sorted(sf)}},
            'sim_with_ghost': {**side(sf, sum(sd.values()) + sum(sg.values()), len(sim)), 'by_place': by_place(sim, 1),
                               'per_fight_by_stage': {str(s): round((sd[s] + sg[s]) / sf[s], 3) for s in sorted(sf)}}}


def read_real(path, patch=PATCH):
    """판 기록 -> (판 목록, 뺀 판 수). 판 번호와 플레이어 식별 칸은 이 함수 밖으로 나가지 않는다."""
    csv.field_size_limit(10 ** 7)
    games, repeated = defaultdict(dict), 0
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            if row['patch_version'] != patch:
                continue
            g = games[row['match_id']]
            repeated += row['puuid'] in g
            g[row['puuid']] = (int(float(row['placement'])), int(float(row['last_round'])), int(float(row['total_dmg_to_players'])))
    drop, lobbies = Counter(rows_repeated=repeated), []
    for g in games.values():
        seats = sorted(g.values())
        if [s[0] for s in seats] != list(range(1, 9)):
            drop['not_8_seats'] += 1
        elif seats[0][1] < FIRST_ROUND:
            drop['remake'] += 1
        else:
            lobbies.append(real_lobby(seats))
    return lobbies, dict(drop)


def structure(real):
    """피해를 보지 않는 점검: 생존 수(이미 올린 results/real_games_set4.json과 맞는지)와 끝난 라운드의 종류."""
    n = len(real)
    kinds = Counter()
    for L in real:
        first, second = sorted(L['last'], reverse=True)[:2]
        kinds['top_two_same_round'] += first == second
        for i, (p, *_) in enumerate(L['seats']):
            if p > 1:
                s, k = real_stage(L['last'][i])
                kinds['carousel' if s >= 2 and k == 4 else 'pve' if s == 1 or k == 7 else 'pvp'] += 1
    lost = 7 * n
    return {'games': n, 'alive': {name: round(sum(x >= r for L in real for x in L['last']) / n, 3) for name, r in ALIVE.items()},
            'top_two_same_round': round(kinds['top_two_same_round'] / n, 4),
            'ended_in': {k: round(kinds[k] / lost, 4) for k in ('pvp', 'pve', 'carousel')}}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def selfcheck():
    # 실제 판 세기: 2-1에 여섯이 끝나고 둘이 2-5까지 간다 -> 2-1에 4번, 2-2·2-3·2-5에 1번씩(2-4는 회전초밥)
    L = real_lobby([(1, 9, 30), (2, 9, 10), (3, 5, 0), (4, 5, 0), (5, 5, 0), (6, 5, 0), (7, 5, 0), (8, 5, 0)])
    assert L['F'] == {2: 7} and L['total'] == 40 and [s[3] for s in L['seats']] == [4, 4, 1, 1, 1, 1, 1, 1], L
    # 셋이 남으면 사람끼리 대전은 한 번이고(한 자리는 유령과 싸운다) 셋 모두 라운드를 치른다
    L = real_lobby([(1, 7, 0), (2, 7, 0), (3, 7, 0), (4, 5, 0), (5, 5, 0), (6, 5, 0), (7, 5, 0), (8, 5, 0)])
    assert L['F'] == {2: 6} and [s[3] for s in L['seats']][:3] == [3, 3, 3], L
    assert real_stage(26) == (5, 1) and real_stage(40) == (7, 1) and not real_pvp(8) and not real_pvp(11) and real_pvp(9)
    # 시뮬레이터 판 세기: 사람끼리 대전 둘(하나는 비김), 유령 대전 하나(복사된 0번 보드가 이김)
    rows = [{'place': 1, 'pnum': 0}, {'place': 2, 'pnum': 1}, {'place': 3, 'pnum': 2}]
    fights = [{'round': 3, 'ghost': False, 'pnum': [0, 1], 'won': 1, 'damage': 4},
              {'round': 9, 'ghost': True, 'pnum': [2, 0], 'won': 2, 'damage': 8},
              {'round': 9, 'ghost': False, 'pnum': [0, 1], 'won': 0, 'damage': 2}]
    S = sim_lobby(rows, fights)
    assert S['F'] == {2: 1, 3: 1} and S['D'] == {2: 4} and S['G'] == {3: 8} and S['seats'] == [(1, 4, 8, 2), (2, 0, 0, 2), (3, 0, 0, 1)], S
    assert survivors({'fights': [fights]}, 7)['2']['left'] == 2 and slot_stage(2) == 1 and slot_stage(3) == 2 and slot_stage(15) == 4
    # 읽기: 시뮬레이터와 같은 판이면 비가 1, 실제 피해가 0.8배면 「크게 끝난다」, 1.2배면 「팽팽하게」
    sim = [{'F': Counter({2: 20, 3: 20, 4: 20, 5: 15, 6: 8, 7: 2}), 'D': Counter({2: 90, 3: 170, 4: 190, 5: 180, 6: 124, 7: 46}),
            'G': Counter(), 'total': 800, 'seats': [(p, 100, 0, 30) for p in range(1, 9)]} for _ in range(40)]
    for scale, want in ((1.0, '판 전체로 보면 실제와 비슷한 크기로 끝난다'), (0.8, '시뮬레이터 판의 대전이 실제보다 크게 끝난다'),
                        (1.2, '시뮬레이터 판의 대전이 실제보다 팽팽하게 끝난다')):
        real = [{**x, 'total': x['total'] * scale, 'last': [40] * 8} for x in sim]
        out = summary(real, sim, boot=20)
        assert abs(out['ratio']['no_ghost'][0] - scale) < 1e-9 and out['reading'] == want, (scale, out['ratio'], out['reading'])
    # 실제 판이 더 길면(6단계 대전이 열 번 더) 같은 피해 합이라도 비가 1 아래다
    longer = [{**x, 'F': x['F'] + Counter({6: 10}), 'last': [40] * 8} for x in sim]
    assert summary(longer, sim, boot=20)['ratio']['no_ghost'][0] < 0.9
    assert reading(False, [1, 1, 1], [1, 1, 1]).startswith('읽지 않는다') and reading(True, [1.0, 0.95, 1.05], [0.85, 0.8, 0.88]).startswith('유령')
    print('selfcheck 통과')


def main(argv):
    if argv[:1] == ['selfcheck']:
        return selfcheck()
    real, drop = read_real(argv[0])
    shape = structure(real)
    print('실제 10.24 판', shape['games'], '뺀 것', drop, '\n생존', shape['alive'], '\n1·2등이 같은 라운드에 끝난 몫', shape['top_two_same_round'],
          '끝난 라운드 종류', shape['ended_in'])
    if argv[1] == '--structure':
        return
    record = json.load(open(argv[1], encoding='utf-8'))
    assert not record['errors'] and len(record['rows']) == record['games_asked'] and record['record'] == [0, 99], '기록이 판 끝까지가 아니거나 오류가 있다'
    sim = [sim_lobby(rows, fights) for rows, fights in zip(record['rows'], record['fights'])]
    out = {'source': {'name': 'TEAMFIGHT TACTICS: FATES Challenger EUW Rank Games', 'csv_sha256': sha256(argv[0]), 'patch': PATCH, 'dropped': drop},
           'sim_record': {'file': argv[1], 'sha256': sha256(argv[1]), 'seed0': record['seed0'], 'games': len(sim),
                          'actions_per_turn': record['actions_per_turn'], 'textbook': record['textbook']},
           'structure': shape, **summary(real, sim)}
    out['sim_survivors_by_stage'] = survivors(record, out['top_stage'])
    with open(argv[2], 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for key in ('real', 'sim_no_ghost', 'sim_with_ghost'):
        s = out[key]
        print(key, '판', s['games'], '대전', s['fights_per_game'], '준 피해', s['dealt_per_game'], s['per_fight'], '\n  단계별 대전', s['fights_by_stage'])
    print('비', out['ratio'], '\n읽기:', out['reading'], '\n저장:', argv[2])


if __name__ == '__main__':
    main(sys.argv[1:])
