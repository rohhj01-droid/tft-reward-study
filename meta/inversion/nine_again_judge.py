"""레벨 9 관문 셋을 함께(b_all) 새 시드 다시 재기 판정(results/README 「레벨 9 관문 셋을 함께 새 시드로 다시 재기: 미리 정한 판정」, 2026-11-23).
판은 안 돌리고 실행 기록만 읽는다.

대조(nine2_none: 여덟 자리 모두 교과서), 맞대결(nine2_b_all_ab: 팔 4자리 + 교과서 4자리), 판 전체(nine2_b_all_all: 여덟 자리 모두 팔)를
같은 시드 780000~780399에서 읽는다. 셈은 meta/inversion/nine_judge.py의 묶음 B 셈과 같다.
판정 1(등수): 맞대결의 판별 차(교과서 자리 평균 − 팔 자리 평균)에서 같은 시드 대조의 차를 뺀 값의 평균과 표준오차.
판정 2(레벨 9): 판 전체의 판별 「레벨 9로 끝난 자리 수」(마지막으로 시작한 라운드의 레벨) − 대조.
둘 다 표준오차의 2배를 문턱으로 쓴다. 판정 1이 「등수가 내려간다」가 아니고 판정 2가 「실제 쪽으로 움직였다」면 「다시 재도 통한다」,
아니면 「다시 재면 보이지 않는다」. 그 밖의 값은 판정 없이 함께 낸다.
실행(저장소 맨 위에서): python meta/inversion/nine_again_judge.py results/nine_again_share.json
셈 확인: 둘째 인자로 check를 주면 팔 자리에 대조 기록을 넣는다(차가 모두 0.000, 「다시 재면 보이지 않는다」).
"""
import hashlib
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from meta.real_games import bot_summary, slot_round  # noqa: E402

SEED0, GAMES, ROUND_6_1 = 780000, 400, 33
ENV = {'actions_per_turn': 30, 'textbook': {'spend': 'era', 'lose_5': False}}  # 미리 정한 환경(june fbc238d는 실행 기록으로 본다)


def mse(x):
    return statistics.mean(x), statistics.stdev(x) / len(x) ** 0.5


def nines(d):
    """{판 시드: 레벨 9로 끝난 자리 수}(마지막으로 시작한 라운드의 레벨)"""
    return {s: sum(seat['curve'][-1][1] >= 9 for seat in rows) for s, rows in zip(d['seeds'], d['rows'])}


def paired(a, b):
    """같은 시드끼리 a − b."""
    return mse([a[s] - b[s] for s in sorted(set(a) & set(b))])


def cell(m, se, up, down):
    return up if m >= 2 * se and m > 0 else down if m <= -2 * se and m < 0 else '구별되지 않는다'


def view(d):
    """판 전체 실행의 판정 밖 값. 판당 레벨 9 자리와 5단계까지 끝난 비율은 원본 기록에서 바로 센다."""
    s = bot_summary(d)
    seats = [seat for rows in d['rows'] for seat in rows]
    return {'alive': s['alive'], 'level_9': s['level']['9'], 'level_9_per_game': statistics.mean(nines(d).values()),
            'mean_level': s['mean_level'], 'ended_by_stage_5': sum(slot_round(seat['curve'][-1][0]) < ROUND_6_1 for seat in seats) / len(seats),
            'level_9_by_place': {str(p): s['by_place'][str(p)]['level']['9'] for p in range(1, 9)}}


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

    none = load('nine2_none.json', None, False)
    ab = none if check else load('nine2_b_all_ab.json', 'b_all', False)
    every = none if check else load('nine2_b_all_all.json', 'b_all', True)
    assert len(env) == 1, f'환경이 기록마다 다르다: {env}'
    assert json.loads(next(iter(env))) == ENV, f'미리 정한 환경이 아니다: {env}'
    place = paired(dict(zip(ab['seeds'], ab['per_game'])), dict(zip(none['seeds'], none['per_game'])))
    more = paired(nines(every), nines(none))
    record.update(environment=json.loads(next(iter(env))), errors=[len(none['errors']), len(ab['errors']), len(every['errors'])],
                  place=list(place), verdict_place=cell(*place, '등수가 오른다', '등수가 내려간다'),
                  level_9_seats=list(more), verdict_real=cell(*more, '실제 쪽으로 움직였다', '실제에서 멀어졌다'))
    record['again'] = ('다시 재도 통한다' if record['verdict_place'] != '등수가 내려간다' and record['verdict_real'] == '실제 쪽으로 움직였다'
                       else '다시 재면 보이지 않는다')
    record['textbook'], record['lobby'] = view(none), view(every)
    json.dump(record, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return record


if __name__ == '__main__':
    r = main('meta/inversion', sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == 'check')
    print(f'환경 {r["environment"]}, 오류 {r["errors"]}')
    print(f'b_all 등수 {r["place"][0]:+.4f} ± {r["place"][1]:.4f} 「{r["verdict_place"]}」 | 레벨 9 자리 {r["level_9_seats"][0]:+.4f} ± {r["level_9_seats"][1]:.4f} '
          f'「{r["verdict_real"]}」 → {r["again"]} | 판당 레벨 9 교과서 {r["textbook"]["level_9_per_game"]:.4f}, 팔 {r["lobby"]["level_9_per_game"]:.4f}')
