"""
성공 기준 1: 점수 순위가 대전 승률 순위에 가까워지는가(hra/plan_ai_design.md 1·6절).

덱 두 묶음의 완성 보드(모두 2성)마다 점수 넷을 매기고, 시뮬레이터 고정 보드 대전 승률과 순위 상관을 낸다.
- 사람 봇 덱 27개(meta/lobby.BOARDS): 승률은 results/pit_1024.json의 human 설정 평균.
- 롤체지지 10.24 트렌드 27조합: 승률은 results/real_boards_1024.json의 main 평균. 실제 평균 등수와도 낸다.
점수: 보드 값(1학기 hra/env.py board_value와 같은 값표 set4.COST_STAR_VALUE, 2성), 발동한 특성 단계 수, 유닛 수,
셋을 합친 것(보드 값 ÷120 + 단계 수 ÷11 + 유닛 수 ÷9). 유닛 수가 7~9로 섞여 전체 상관은 유닛 수가 지배하므로 8명 보드끼리도 낸다.

실행: python -m hra.score_rank --out results/score_rank_1024.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import COST_STAR_VALUE, TRAIT_BREAKS, cost_of
from meta.decks_1024 import trait_counts
from meta.lobby import BOARDS
from meta.pit import average, chosen_of
from meta.real_boards import spearman

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES = {
    'board_value': lambda bv, tiers, n: bv,
    'synergy': lambda bv, tiers, n: tiers,
    'units': lambda bv, tiers, n: n,
    'combined': lambda bv, tiers, n: bv / 120 + tiers / 11 + n / 9,
}


def tiers_of(counts):
    """특성별 인원 -> 발동한 단계 수(특성마다 넘은 문턱 수의 합)."""
    return sum(sum(1 for b in TRAIT_BREAKS.get(t, []) if c >= b) for t, c in counts.items())


def board_scores(units, items, chosen):
    """완성 보드(모두 2성)의 (보드 값, 발동한 특성 단계 수, 유닛 수)."""
    bv = sum(COST_STAR_VALUE[cost_of(u) - 1][1] for u in units)
    return bv, tiers_of(trait_counts(units, items, chosen)), len(units)


def rho(x, y):
    """순위 상관. 한쪽 값이 모두 같으면 낼 수 없어 None."""
    return None if len(set(x)) < 2 or len(set(y)) < 2 else spearman(x, y)


def deck_rows():
    """사람 봇 덱 27개: (이름, 점수 재료, 대전 승률, None)."""
    pit = json.load(open(os.path.join(ROOT, 'results', 'pit_1024.json'), encoding='utf-8'))
    win = average(pit['human'])
    return [(b['name'], board_scores(b['units'], b['items'], (chosen_of(b) or (None, None))[1]), win[b['name']], None)
            for b in BOARDS]


def trend_rows():
    """롤체지지 트렌드 27조합: (조합, 점수 재료, 대전 승률, 실제 평균 등수)."""
    rb = json.load(open(os.path.join(ROOT, 'results', 'real_boards_1024.json'), encoding='utf-8'))
    win = rb['average']['main']
    return [(b['key'], board_scores(b['units'], b['items'], b['chosen'][1]), win[b['key']], b['place'])
            for b in rb['boards']]


def correlations(rows):
    """점수마다 순위 상관: 대전 승률과(전체, 8명끼리), 실제 등수와(있으면, 높은 순위가 좋도록 등수에 음수)."""
    eight = [i for i, r in enumerate(rows) if r[1][2] == 8]
    out = {}
    for name, f in SCORES.items():
        s = [f(*r[1]) for r in rows]
        out[name] = {'win_all': rho(s, [r[2] for r in rows]),
                     'win_eight': rho([s[i] for i in eight], [rows[i][2] for i in eight])}
        if rows[0][3] is not None:
            out[name]['real_all'] = rho(s, [-r[3] for r in rows])
            out[name]['real_eight'] = rho([s[i] for i in eight], [-rows[i][3] for i in eight])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    result = {'decks': correlations(deck_rows()), 'trends': correlations(trend_rows())}
    for group, table in result.items():
        print(f'== {group}')
        for name, cols in table.items():
            print(f'  {name:12} ' + '  '.join(f'{k} {"-" if v is None else f"{v:+.2f}"}' for k, v in cols.items()))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f'저장: {args.out}')


if __name__ == '__main__':
    main()
