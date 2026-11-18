"""5단계 돈과 생존 규칙 후보 판정(results/README 「5단계 돈과 생존 규칙 후보: 미리 정한 판정」, 2026-11-18). 판은 안 돌리고 실행 기록만 읽는다.

팔 넷(stop, keep30, low30, combo)마다 두 실행을 읽는다. 맞대결(_ab: 팔 4자리 + 교과서 4자리)과 판 전체(_all: 여덟 자리 모두 팔)다. 대조(late_none)는
여덟 자리 모두 교과서이고, 같은 시드 760000~760399다.
판정 1(등수): 맞대결의 판별 차(교과서 자리 평균 − 팔 자리 평균)에서 대조의 판별 차를 뺀 값의 평균과 표준오차.
판정 2(실제 쪽으로): 판 전체 실행의 판별 「6-1 시작에 살아 있는 자리 수」에서 대조의 값을 뺀 평균과 표준오차. 실제 10.24는 5.14, 위로 움직이면 실제 쪽이다.
둘 다 표준오차의 2배를 문턱으로 쓴다. 고른 팔: 판정 1이 「내려간다」가 아니고 판정 2가 「실제 쪽으로 움직였다」인 팔 가운데 살아 있는 자리가 가장 많이 는 팔.
모든 기록의 환경과 시드가 같은지 확인한다(다르면 셈을 멈춘다). 레벨 9 비율과 그 밖의 값은 판정 없이 함께 낸다.
실행(저장소 맨 위에서): python meta/inversion/late_judge.py results/late_lesson_share.json
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
ARMS = ('stop', 'keep30', 'low30', 'combo')
SEED0, GAMES, ROUND_6_1 = 760000, 400, 33
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


def paired(a, b):
    """같은 시드끼리 a − b."""
    return mse([a[s] - b[s] for s in sorted(set(a) & set(b))])


def cell(m, se, up, down):
    return up if m >= 2 * se and m > 0 else down if m <= -2 * se and m < 0 else '구별되지 않는다'


def view(s):
    """판 전체 실행의 판정 밖 값."""
    return {'alive': s['alive'], 'level_9': s['level']['9'], 'mean_level': s['mean_level'], 'ended_stage_4_5': round(sum(v['share'] for k, v in s['ended_in_stage'].items() if int(k) <= 5), 4),
            'level_9_by_place': {p: s['by_place'][p]['level']['9'] for p in ('1', '2', '3', '4')}}


none = load('late_none.json', None, False)
none_diff, none_alive, base = dict(zip(none['seeds'], none['per_game'])), alive(none), bot_summary(none)
real = json.load(open('results/real_games_set4.json', encoding='utf-8'))['groups']['10.24']
record['real_10.24'] = view(real)
record['textbook'] = view(base)
record['arms'] = {}
for arm in ARMS:
    ab = none if CHECK else load(f'late_{arm}_ab.json', arm, False)
    every = none if CHECK else load(f'late_{arm}_all.json', arm, True)
    place, place_se = paired(dict(zip(ab['seeds'], ab['per_game'])), none_diff)
    more, more_se = paired(alive(every), none_alive)
    record['arms'][arm] = {'errors': [len(ab['errors']), len(every['errors'])], 'place': [place, place_se], 'alive_6_1': [more, more_se],
                           'verdict_place': cell(place, place_se, '등수가 오른다', '등수가 내려간다'),
                           'verdict_real': cell(more, more_se, '실제 쪽으로 움직였다', '실제에서 멀어졌다'), 'lobby': view(bot_summary(every))}
assert len(ENV) == 1, f'환경이 기록마다 다르다: {ENV}'
record['environment'] = json.loads(next(iter(ENV)))
good = [a for a, r in record['arms'].items() if r['verdict_place'] != '등수가 내려간다' and r['verdict_real'] == '실제 쪽으로 움직였다']
record['picked'] = max(good, key=lambda a: record['arms'][a]['alive_6_1'][0]) if good else None
print(f'환경 {record["environment"]}, 6-1 생존: 실제 {real["alive"]["6-1"]}, 교과서 {base["alive"]["6-1"]}')
for arm, r in record['arms'].items():
    print(f'{arm:7s} 등수 {r["place"][0]:+.3f} ± {r["place"][1]:.3f} 「{r["verdict_place"]}」 | 6-1 생존 {r["alive_6_1"][0]:+.3f} ± {r["alive_6_1"][1]:.3f} 「{r["verdict_real"]}」 | '
          f'레벨 9 {r["lobby"]["level_9"]:.1%} 1등 {r["lobby"]["level_9_by_place"]["1"]:.1%}')
print('고른 팔:', record['picked'])
json.dump(record, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
