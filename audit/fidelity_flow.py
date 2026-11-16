"""충실도 성적표(audit/fidelity.md) ③ 한 판의 흐름을 교과서 8명 실행 기록에서 센다. 새 판은 돌리지 않는다.

- 그때 글의 기준점 8개는 hra/save_lesson.py를 그대로 쓴다. 그 스크립트는 4-1 전에 탈락한 자리가 하나라도 있으면 멈추므로
  (유령 대전 때문에 수입을 되짚을 수 없다) 그런 자리가 있는 판만 빼고 넘긴다.
- 4-1 뒤 레벨 일정(그때 가이드: 4-1에 7, 5-1에 8은 거의 모두 한다): 다음 라운드를 시작할 때 살아 있던 자리 가운데 그 레벨에 닿은 몫.
- 참고 값: 1등 자리가 마지막 라운드를 시작할 때 레벨 9 이상인 몫. 끝난 보드의 레벨이 아니라서 hra/evaluate.py meta의 값보다 낮게 나온다.

    python -m audit.fidelity_flow results/spend_lesson_none_cap30_s750_tb-era.json
"""
import json
import sys

from hra.save_lesson import LAST, report, show

SCHEDULE = ((16, 7, '4-1에 레벨 7 (4-2 시작 레벨)'), (22, 8, '5-1에 레벨 8 (5-2 시작 레벨)'))


def level_at(seat, slot):
    return next((c[1] for c in seat['curve'] if c[0] == slot), None)


def main(path):
    run = json.load(open(path, encoding='utf-8'))
    kept = [g for g in run['rows'] if all(max(c[0] for c in s['curve']) >= LAST for s in g)]
    print(f'{path}: {len(run["rows"])}판 가운데 4-1 전에 탈락한 자리가 없는 {len(kept)}판으로 기준점을 센다')
    show([report({**run, 'rows': kept})])
    seats = [s for g in run['rows'] for s in g]
    for slot, level, label in SCHEDULE:
        alive = [lv for lv in (level_at(s, slot) for s in seats) if lv is not None]
        print(f'{label}: {sum(lv >= level for lv in alive) / len(alive):.1%} (살아 있던 자리 {len(alive)})')
    top = [s['curve'][-1][1] for s in seats if s['place'] == 1]
    print(f'참고: 1등 자리가 마지막 라운드를 시작할 때 레벨 9 이상 {sum(lv >= 9 for lv in top) / len(top):.1%} (1등 {len(top)}자리)')


if __name__ == '__main__':
    main(sys.argv[1])
