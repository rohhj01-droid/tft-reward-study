"""레벨 9 관문 규칙 후보 판정과 문턱 낮추기 다시 재기(results/README 「레벨 9 관문 규칙 후보와 문턱 낮추기 다시 재기: 미리 정한 판정」, 2026-11-19).
판은 안 돌리고 실행 기록만 읽는다.

팔 다섯(low30, carry1, stage6, fast, b_all)마다 맞대결(_ab: 팔 4자리 + 교과서 4자리)과 판 전체(_all: 여덟 자리 모두 팔)를 읽는다.
대조(nine_none)는 여덟 자리 모두 교과서이고, 모두 같은 시드 770000~770399다.
판정 1(등수, 다섯 팔 모두): 맞대결의 판별 차(교과서 자리 평균 − 팔 자리 평균)에서 대조의 판별 차를 뺀 값의 평균과 표준오차.
판정 2(실제 쪽으로):
  low30: 판 전체의 판별 「6-1 시작에 살아 있는 자리 수」 − 대조. 실제 10.24는 5.14.
  묶음 B 넷: 판 전체의 판별 「레벨 9로 끝난 자리 수」 − 대조. 실제 10.24는 8 × 23.57% = 1.89. 팔의 판당 값이 실제보다 크면 「실제를 넘었다」.
둘 다 표준오차의 2배를 문턱으로 쓴다.
low30의 다시 재기: 판정 1이 「내려간다」가 아니고 판정 2가 「실제 쪽으로 움직였다」면 「다시 재도 통한다」, 아니면 「다시 재면 보이지 않는다」.
묶음 B의 고른 팔: 판정 1이 「내려간다」가 아니고 판정 2가 「실제 쪽으로 움직였다」인 팔 가운데 레벨 9 자리가 가장 많이 는 팔.
모든 기록의 환경과 시드가 같은지 확인한다(다르면 셈을 멈춘다). 그 밖의 값은 판정 없이 함께 낸다.
실행(저장소 맨 위에서): python meta/inversion/nine_judge.py results/nine_lesson_share.json
셈 확인: 둘째 인자로 check를 주면 팔의 자리에 대조 기록을 넣는다(차가 모두 0.000, 「구별되지 않는다」, 고른 팔 없음).
"""
import hashlib
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from meta.real_games import bot_summary, slot_round  # noqa: E402

OUT = sys.argv[1]
CHECK = len(sys.argv) > 2 and sys.argv[2] == 'check'
INV = 'meta/inversion/'
ARMS = ('low30', 'carry1', 'stage6', 'fast', 'b_all')
SEED0, GAMES, ROUND_6_1 = 770000, 400, 33
record = {'check': CHECK, 'inputs': {}}
ENV = set()


def load(name, arm, everyone):
    raw = open(INV + name, 'rb').read()
    record['inputs'][name] = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw)
    assert d['seed0'] == SEED0 and d['games_asked'] == GAMES, name
    assert d['arm'] == arm and bool(d['everyone']) == everyone, name
    assert len(d['seeds']) == len(d['rows']), name
    ENV.add(json.dumps({'textbook': d['textbook'], 'actions_per_turn': d['actions_per_turn']}, sort_keys=True))
    return d


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def alive(d):
    """{판 시드: 6-1 시작에 살아 있는 자리 수}"""
    return {s: sum(slot_round(seat['curve'][-1][0]) >= ROUND_6_1 for seat in rows) for s, rows in zip(d['seeds'], d['rows'])}


def nines(d):
    """{판 시드: 레벨 9로 끝난 자리 수}(meta.real_games.bot_summary와 같이 마지막으로 시작한 라운드의 레벨)"""
    return {s: sum(seat['curve'][-1][1] >= 9 for seat in rows) for s, rows in zip(d['seeds'], d['rows'])}


def paired(a, b):
    """같은 시드끼리 a − b."""
    return mse([a[s] - b[s] for s in sorted(set(a) & set(b))])


def cell(m, se, up, down):
    return up if m >= 2 * se and m > 0 else down if m <= -2 * se and m < 0 else '구별되지 않는다'


def view(s):
    """판 전체 실행의 판정 밖 값."""
    return {'alive': s['alive'], 'level_9': s['level']['9'], 'level_9_per_game': round(8 * s['level']['9'], 3), 'mean_level': s['mean_level'],
            'ended_by_stage_5': round(sum(v['share'] for k, v in s['ended_in_stage'].items() if int(k) <= 5), 4),
            'level_9_by_place': {str(p): s['by_place'][str(p)]['level']['9'] for p in range(1, 9)}}


none = load('nine_none.json', None, False)
none_diff, base = dict(zip(none['seeds'], none['per_game'])), bot_summary(none)
real = json.load(open('results/real_games_set4.json', encoding='utf-8'))['groups']['10.24']
REAL_NINE = 8 * real['level']['9']
record['real_10.24'] = view(real)
record['textbook'] = view(base)
record['arms'] = {}
for arm in ARMS:
    ab = none if CHECK else load(f'nine_{arm}_ab.json', arm, False)
    every = none if CHECK else load(f'nine_{arm}_all.json', arm, True)
    place, place_se = paired(dict(zip(ab['seeds'], ab['per_game'])), none_diff)
    lobby = view(bot_summary(every))
    r = {'errors': [len(ab['errors']), len(every['errors'])], 'place': [place, place_se],
         'verdict_place': cell(place, place_se, '등수가 오른다', '등수가 내려간다'), 'lobby': lobby}
    if arm == 'low30':
        more, more_se = paired(alive(every), alive(none))
        r.update(alive_6_1=[more, more_se], verdict_real=cell(more, more_se, '실제 쪽으로 움직였다', '실제에서 멀어졌다'))
        r['again'] = '다시 재도 통한다' if r['verdict_place'] != '등수가 내려간다' and r['verdict_real'] == '실제 쪽으로 움직였다' else '다시 재면 보이지 않는다'
    else:
        more, more_se = paired(nines(every), nines(none))
        v = cell(more, more_se, '실제 쪽으로 움직였다', '실제에서 멀어졌다')
        r.update(level_9_seats=[more, more_se], verdict_real='실제를 넘었다' if v == '실제 쪽으로 움직였다' and lobby['level_9_per_game'] > REAL_NINE else v)
    record['arms'][arm] = r
assert len(ENV) == 1, f'환경이 기록마다 다르다: {ENV}'
record['environment'] = json.loads(next(iter(ENV)))
good = [a for a, r in record['arms'].items() if a != 'low30' and r['verdict_place'] != '등수가 내려간다' and r['verdict_real'] == '실제 쪽으로 움직였다']
record['picked'] = max(good, key=lambda a: record['arms'][a]['level_9_seats'][0]) if good else None
print(f'환경 {record["environment"]}, 판당 레벨 9 자리: 실제 {REAL_NINE:.3f}, 교과서 {8 * base["level"]["9"]:.3f}')
for arm, r in record['arms'].items():
    key, name = ('alive_6_1', '6-1 생존') if arm == 'low30' else ('level_9_seats', '레벨 9 자리')
    print(f'{arm:7s} 등수 {r["place"][0]:+.3f} ± {r["place"][1]:.3f} 「{r["verdict_place"]}」 | {name} {r[key][0]:+.3f} ± {r[key][1]:.3f} 「{r["verdict_real"]}」'
          f'{" → " + r["again"] if "again" in r else ""} | 레벨 9 {r["lobby"]["level_9"]:.1%} 1등 {r["lobby"]["level_9_by_place"]["1"]:.1%}')
print('고른 팔:', record['picked'])
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
