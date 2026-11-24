"""3단계 체력 규칙(hp3) 판정(results/README 「3단계 체력 규칙: 미리 정한 판정」, 2026-11-24). 판은 안 돌리고 실행 기록만 읽는다.

대조(hp3_none: 여덟 자리 모두 교과서), 맞대결(hp3_hp3_ab: 팔 4자리 + 교과서 4자리), 판 전체(hp3_hp3_all: 여덟 자리 모두 팔)를
같은 시드 790000~790399에서 읽는다.
판정 1(등수): 맞대결의 판별 차(교과서 자리 평균 − 팔 자리 평균)에서 같은 시드 대조의 차를 뺀 값의 평균과 표준오차.
판정 2(5-5 생존): 판 전체의 판별 「5-5를 시작한 자리 수」 − 대조.
둘 다 표준오차의 2배를 문턱으로 쓴다. 판정 1이 「등수가 내려간다」가 아니고 판정 2가 「실제 쪽으로 움직였다」면 「교과서 후보」,
아니면 「교과서 후보 아님」. 그 밖의 값(5-1·6-1·6-5·7-1 생존, 레벨 9)은 판정 없이 함께 낸다. 초과 탈락 나눔은 meta/inversion/hp_split.py를 따로 돌린다.
오류로 버린 판이 있으면 세 실행 모두에 있는 시드끼리만 짝짓는다.
실행(저장소 맨 위에서, june을 PYTHONPATH에): python meta/inversion/hp3_judge.py results/hp3_share.json
셈 확인: 둘째 인자로 check를 주면 팔 자리에 대조 기록을 넣는다(차가 모두 0.000, 「교과서 후보 아님」).
"""
import hashlib
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from meta.real_games import bot_summary  # noqa: E402

SEED0, GAMES = 790000, 400
ENV = {'actions_per_turn': 30, 'textbook': {'spend': 'era', 'lose_5': False}}  # 미리 정한 환경(june fbc238d는 실행 기록으로 본다)
SLOT = {'5-1': 21, '5-5': 24, '6-1': 27, '6-5': 30, '7-1': 33}  # 칸 번호


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def alive(d, slot):
    """{판 시드: 그 칸을 시작한 자리 수}"""
    return {s: sum(seat['curve'][-1][0] >= slot for seat in rows) for s, rows in zip(d['seeds'], d['rows'])}


def nines(d):
    return {s: sum(seat['curve'][-1][1] >= 9 for seat in rows) for s, rows in zip(d['seeds'], d['rows'])}


def paired(a, b):
    """같은 시드끼리 a − b."""
    return mse([a[s] - b[s] for s in sorted(set(a) & set(b))])


def cell(m, se, up, down):
    return up if m >= 2 * se and m > 0 else down if m <= -2 * se and m < 0 else '구별되지 않는다'


def main(inv, out, check):
    record, env = {'check': check, 'inputs': {}}, set()

    def load(name, arm, everyone):
        raw = open(os.path.join(inv, name), 'rb').read()
        record['inputs'][name] = hashlib.sha256(raw).hexdigest()
        d = json.loads(raw)
        assert d['seed0'] == SEED0 and d['games_asked'] == GAMES, name
        assert d['arm'] == arm and bool(d['everyone']) == everyone, name
        assert len(d['seeds']) == len(d['rows']), name
        env.add(json.dumps({'textbook': d['textbook'], 'actions_per_turn': d['actions_per_turn']}, sort_keys=True))
        return d

    none = load('hp3_none.json', None, False)
    ab = none if check else load('hp3_hp3_ab.json', 'hp3', False)
    every = none if check else load('hp3_hp3_all.json', 'hp3', True)
    assert len(env) == 1, f'환경이 기록마다 다르다: {env}'
    assert json.loads(next(iter(env))) == ENV, f'미리 정한 환경이 아니다: {env}'
    place = paired(dict(zip(ab['seeds'], ab['per_game'])), dict(zip(none['seeds'], none['per_game'])))
    more = paired(alive(every, SLOT['5-5']), alive(none, SLOT['5-5']))
    record.update(environment=json.loads(next(iter(env))), errors=[len(none['errors']), len(ab['errors']), len(every['errors'])],
                  place=list(place), verdict_place=cell(*place, '등수가 오른다', '등수가 내려간다'),
                  alive_5_5=list(more), verdict_real=cell(*more, '실제 쪽으로 움직였다', '실제에서 멀어졌다'))
    record['candidate'] = ('교과서 후보' if record['verdict_place'] != '등수가 내려간다' and record['verdict_real'] == '실제 쪽으로 움직였다'
                           else '교과서 후보 아님')
    record['alive_change'] = {k: list(paired(alive(every, v), alive(none, v))) for k, v in SLOT.items()}  # 판정 밖
    record['level_9_change'] = list(paired(nines(every), nines(none)))  # 판정 밖
    record['textbook'], record['lobby'] = bot_summary(none), bot_summary(every)
    json.dump(record, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return record


if __name__ == '__main__':
    r = main('meta/inversion', sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == 'check')
    print(f'환경 {r["environment"]}, 오류 {r["errors"]}')
    print(f'hp3 등수 {r["place"][0]:+.4f} ± {r["place"][1]:.4f} 「{r["verdict_place"]}」 | 5-5 생존 {r["alive_5_5"][0]:+.4f} ± {r["alive_5_5"][1]:.4f} '
          f'「{r["verdict_real"]}」 → {r["candidate"]}')
    print('판정 밖 생존 변화', {k: f'{v[0]:+.3f} ± {v[1]:.3f}' for k, v in r['alive_change'].items()}, f'레벨 9 {r["level_9_change"][0]:+.3f} ± {r["level_9_change"][1]:.3f}')
