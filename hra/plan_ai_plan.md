# 계획 AI 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 라운드마다 「어느 덱으로, 어느 레벨까지, 골드를 얼마 남기고 리롤할지」를 정하는 신경망을, 사람 봇을 실행기로 삼아 풀게임 8명 자기 대전으로 학습하고, CURT 성공 기준 셋과 AI 메타 대 실제 메타로 평가한다.

**Architecture:** 사람 봇(meta/human_bot.HumanPolicy)을 물려받은 PlanPolicy가 라운드 첫 호출마다 상태 153칸을 계획기에 넘겨 계획(덱 28, 레벨 3, 남길 골드 6)을 받고, 사기·팔기·배치·아이템은 사람 봇 규칙이 그 계획을 따라 여러 행동으로 실행한다. 경험은 보상 5갈래로 쌓고, 1학기 다중 보상 Q학습을 행동 갈래 셋으로 넓힌 신경망을 규칙 봇 따라 하기(DQfD 여백 손실)로 데운 뒤 일꾼 6개 자기 대전으로 다듬는다.

**Tech Stack:** Python 3.11 가상환경, torch 2.14(CPU), numpy 1.23.5, multiprocessing(윈도우 spawn), 시뮬레이터 june(fix/set4-accuracy 45e77c5).

**Spec:** hra/plan_ai_design.md (2026-10-12 승인)

## Global Constraints

- 저장소 tft-reward-study의 curt-2 브랜치에서 한다. 시뮬레이터 june은 45e77c5 그대로 쓰고 이 계획에서는 고치지 않는다.
- 1학기 학습 코드(hra/env.py, hra/env_battle.py, hra/model.py, hra/train.py, hra/train_battle.py, hra/sweep.py)는 그대로 둔다.
- 새 의존성을 넣지 않는다(torch, numpy, 표준 라이브러리만).
- 계획: 목표 덱 28가지(0 = 그대로, 1~27 = meta/lobby.BOARDS[번호 − 1]), 목표 레벨 3가지(지금 레벨 + 0~2), 남길 골드 6가지(FLOORS = (None, 50, 30, 20, 10, 0)).
- 상태 153칸 = 내 상태 8 + 내 보드 7 + 덱마다 5 × 27 + 상대 요약 2 + 덱 이력 1. 값은 나눈 뒤 0~2로 자른다. 공략 사이트 티어 점수는 넣지 않는다.
- 보상 갈래 순서는 (place, hp, econ, synergy, units). 가중치는 등수 1, 체력 1, 이자 0.3, 시너지·유닛 수는 0 또는 w(사전 시험으로 정함).
- 할인율 0.98, 여백 0.8, 경험 더미 50만, 일꾼 6, 판마다 학습 8걸음, 목표 신경망 1000걸음마다 맞춤.
- 탐험 몫은 덱 3%→1%, 레벨·남길 골드 15%→5%(학습 판 수에 따라 곧게 줄임).
- 커밋 접두어는 학습 코드 `hra:`, 결과 `results:`. 커밋 꼬리말은 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 문서와 주석은 쉬운 한국어로 쓴다. 개인 정보와 이 컴퓨터의 경로는 커밋하지 않는다(푸시 전에 바뀐 내용을 훑는다).
- 큰 산출물(따라 하기 자료 npz, 신경망 pt)은 checkpoints/에 둔다(.gitignore에 있다). 결과 요약 JSON만 results/에 커밋한다.
- 검사 함수 이름은 `_test`로 끝나고 모듈을 `python -m`으로 돌린다(저장소 방식).

## Review Focus

1. 같은 걸음에 여럿이 탈락하거나 판이 걸음 상한(5000)에 걸린 판: 등수 1~8이 하나씩 나가고, 기록하는 정책의 finish가 자리마다 한 번만 불린다(Task 4의 기록 판 검사와 finish 검사).
2. 탐험 중에도 가린 칸을 고르지 않는다. 2-1에 「그대로」를 고르면 덱 없이 판이 돈다(Task 5의 가림 검사).
3. 덱을 라운드마다 갈아타는 계획(최악의 탐험)에도 실행기가 멈추지 않고 판이 끝난다(Task 4의 덱 갈아타기 검사).
4. 시뮬레이터가 판 중간에 예외를 내면 그 판만 버리고 모으기·평가·자기 대전이 계속된다(Task 4의 safe_play 검사, Task 9·10의 오류 집계).
5. 컴퓨터가 꺼진 뒤 같은 명령을 다시 돌리면 마지막 저장에서 판 수를 이어 가고, 최고 저장본은 더 나은 점검 결과로만 바뀐다(Task 10의 이어 하기 검사와 is_better 검사).

---

## 파일 구조

| 파일 | 하는 일 | 과제 |
|---|---|---|
| hra/score_rank.py | 성공 기준 1: 완성 보드의 점수 넷과 대전 승률의 순위 상관. 특성 단계 세기(tiers_of) | 1 |
| hra/plan_state.py | 보상 갈래 이름, 계획 번호·가림·풀이, 규칙의 한 라운드를 계획 번호로 옮기기, 상태 153칸 | 2, 3 |
| hra/plan_bot.py | 실행기(PlanPolicy), 따라 하기 기록기(RuleRecorder), 경험 쌓기(Recorder), 판 돌리기(play, safe_play) | 4 |
| hra/plan_net.py | 신경망, 가중합 선택, 갈래별 탐험, 보조 갈래가 뒤집는 비율, 저장·불러오기 | 5 |
| hra/plan_learn.py | 경험 더미, 갈래별 Q 손실, 여백 손실, 한 걸음 학습 | 6 |
| hra/collect.py | 규칙 기록기 8명 판으로 따라 하기 자료 모으기 | 7 |
| hra/pretrain.py | 데우기, 떼어 둔 판의 일치율 | 8 |
| hra/evaluate.py | A/B, 행동 일치율, AI 메타 | 9 |
| hra/selfplay.py | 자기 대전 학습, 저장·점검·이어 하기 | 10 |
| hra/test_plan.py | 빠른 검사(판을 돌리지 않음) | 1~3, 5, 6, 8, 10 |
| hra/test_plan_game.py | 느린 검사(시뮬레이터 판을 돌림, 판 하나에 20초쯤) | 4, 7, 9, 10 |
| meta/human_bot.py | 레벨·리롤 판단을 「숫자 정하기(macro_plan)」와 「행동 고르기(macro)」로 나눔 | 4 |

## 검사 돌리는 법

저장소 루트에서 돌린다. PYTHONPATH에 june 저장소(fix/set4-accuracy), dotenv 대역 폴더(dotenv.py 한 파일: `def load_dotenv(*a, **k): return False`), `.`을 넣고, PYTHONIOENCODING=utf-8로 `.venv/Scripts/python.exe`를 쓴다. 아래 명령의 `$PY`는 이 설정으로 부르는 파이썬이다.

- 빠른 검사 전부: `$PY -m hra.test_plan`
- 빠른 검사 하나: `$PY -m hra.test_plan 검사이름_test`
- 느린 검사 전부: `$PY -m hra.test_plan_game` (판을 여러 개 돌려 몇 분 걸린다)
- 기존 검사 묶음(건드린 모듈의 회귀): `$PY -m meta.test_human_bot`, `$PY -m meta.test_lobby`, `$PY -m meta.test_real_boards`

두 검사 모듈의 끝에는 같은 실행부를 둔다. 인자로 이름을 주면 그 검사만 돈다.

```python
if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
```

---

### Task 1: 성공 기준 1 — 점수 순위 대 대전 승률 순위

**Files:**
- Create: `hra/score_rank.py`
- Create: `hra/test_plan.py`
- Modify: `results/pit_1024.json` (사람 봇 덱 27개 대전을 지금 시뮬레이터로 다시)
- Create: `results/score_rank_1024.json`
- Modify: `results/README.md` (새 절)

**Interfaces:**
- Consumes: `meta.decks_1024.trait_counts(units, items, chosen) -> dict`, `meta.pit.average(matrix) -> dict`, `meta.pit.chosen_of(board) -> (unit, trait) | None`, `meta.real_boards.spearman(x, y) -> float`, `set4.COST_STAR_VALUE`, `set4.TRAIT_BREAKS`, `set4.cost_of(name) -> int`
- Produces: `hra.score_rank.ROOT: str`, `tiers_of(counts: dict) -> int`, `board_scores(units, items, chosen) -> (int, int, int)`, `rho(x, y) -> float | None`, `SCORES: dict`

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`를 새로 만든다.

```python
"""
계획 AI 빠른 검사(판을 돌리지 않는다).

실행: python -m hra.test_plan
"""
import numpy as np


def board_scores_count_value_traits_units_test():
    """사람 봇 덱 Chosen Duelists(완성, 모두 2성): 보드 값 3+3+5+8+5+11+14+14 = 63(1학기 값표), 발동한 특성 단계 10, 유닛 8."""
    from hra.score_rank import board_scores
    from meta.lobby import BOARDS
    from meta.pit import chosen_of
    b = next(b for b in BOARDS if b['name'] == 'Chosen Duelists')
    assert board_scores(b['units'], b['items'], chosen_of(b)[1]) == (63, 10, 8)


def rho_skips_constant_lists_test():
    """8명 보드끼리는 유닛 수 점수가 모두 같아 순위 상관을 낼 수 없다. 그때는 None이다."""
    from hra.score_rank import rho
    assert rho([8, 8, 8], [0.1, 0.5, 0.3]) is None
    assert rho([1, 2, 3], [10, 20, 30]) == 1.0


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.score_rank'`

- [ ] **Step 3: 구현** — `hra/score_rank.py`

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: `PASS board_scores_count_value_traits_units_test`, `PASS rho_skips_constant_lists_test`

- [ ] **Step 5: 사람 봇 덱 대전 다시 돌리기** (30~60분, 뒤에서 돌린다)

Run: `$PY -m meta.pit --n 60 --jobs 7 --out results/pit_1024.json`
Expected: 「human 완료」「harness 완료」와 보드별 평균 승률 표가 나오고 파일이 바뀐다. 예전 결과는 git 이력에 있다.

- [ ] **Step 6: 분석 돌리기**

Run: `$PY -m hra.score_rank --out results/score_rank_1024.json`
Expected: `== decks`와 `== trends` 아래 점수 넷의 상관이 찍힌다. units의 win_eight는 `-`다.

- [ ] **Step 7: 신청서의 1학기 두 조합 다시 재기** (몇 분)

Run: `$PY -m analysis.synergy`
Expected: 1학기 조합 넷(analysis/comps.py)의 시너지 단계·board_value·승률 표. 신청서가 적은 두 조합은 「2~3코 (Warlord)」(1학기 41.2점, 승률 62%)와 「1~3코 Duelist/Divine」(34.9점, 83%)이다. 지금 시뮬레이터로 승률이 바뀔 수 있으니 새 숫자를 쓴다. 합친 점수(보드 값 ÷120 + 단계 수 ÷11, 네 조합 모두 8명이라 유닛 수 항은 같다)로 두 조합의 순서가 승률 순서와 맞는지 본다(신청서의 확인 절차).

- [ ] **Step 8: 문서** — `results/README.md` 끝에 「점수 순위 대 대전 승률 순위 (성공 기준 1, 날짜)」 절을 쓴다. 명령 셋, 파일, 두 묶음의 표(점수 넷 × 전체·8명, 트렌드는 실제 등수 열 포함), 1학기 두 조합의 다시 잰 표와 합친 점수의 순서, 읽은 것(시너지·유닛 수를 넣은 점수가 보드 값만보다 높은가, 8명끼리도 그런가, 두 조합의 순서가 바로잡히는가)을 적는다.

- [ ] **Step 9: 커밋**

```bash
git add hra/score_rank.py hra/test_plan.py results/pit_1024.json results/score_rank_1024.json results/README.md
git commit -m "hra: 성공 기준 1 — 완성 보드의 점수 넷(보드 값·시너지·유닛 수·합)과 대전 승률의 순위 상관" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 계획 번호, 가림, 규칙 정답 옮기기

**Files:**
- Create: `hra/plan_state.py`
- Modify: `hra/test_plan.py` (검사 다섯 추가)

**Interfaces:**
- Consumes: `meta.lobby.BOARDS: list[dict]`
- Produces: `hra.plan_state.HEADS = ('place', 'hp', 'econ', 'synergy', 'units')`, `FLOORS = (None, 50, 30, 20, 10, 0)`, `PLAN_SIZES = (28, 3, 6)`, `MASK_SIZE = 37`, `SLICES = ((0, 28), (28, 31), (31, 37))`, `masks(level: int, deck: dict | None) -> np.ndarray[37] bool`, `decode(plan, level, deck) -> (dict | None, int, int | None)`, `floor_index(floor) -> int`, `rule_label(old_deck, new_deck, level_start, best_target, min_floor) -> (int, int, int)`

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`의 실행부 위에 더한다.

```python
def plan_sizes_and_slices_test():
    from hra.plan_state import HEADS, MASK_SIZE, PLAN_SIZES, SLICES
    assert HEADS == ('place', 'hp', 'econ', 'synergy', 'units')
    assert PLAN_SIZES == (28, 3, 6) and MASK_SIZE == 37
    assert SLICES == ((0, 28), (28, 31), (31, 37))


def masks_hide_impossible_plans_test():
    """덱이 없으면(2-1) 「그대로」를 가리고, 덱이 있으면 지금 덱을 다시 고르는 칸을 가린다. 레벨은 9를 넘는 목표를 가린다."""
    from hra.plan_state import masks
    from meta.lobby import BOARDS
    m = masks(3, None)
    assert not m[0] and m[1:28].all() and m[28:31].all() and m[31:].all()
    m = masks(8, BOARDS[4])
    assert m[0] and not m[5] and m[28] and m[29] and not m[30]
    assert list(masks(9, BOARDS[0])[28:31]) == [True, False, False]


def decode_turns_numbers_into_a_plan_test():
    from hra.plan_state import decode
    from meta.lobby import BOARDS
    assert decode((0, 1, 3), 5, BOARDS[2]) == (BOARDS[2], 6, 20)
    assert decode((5, 0, 0), 4, None) == (BOARDS[4], 4, None)


def floor_index_picks_nearest_floor_test():
    from hra.plan_state import floor_index
    assert [floor_index(f) for f in (None, 50, 20, 10, 0, 35, 45, 60)] == [0, 1, 3, 4, 5, 2, 1, 1]


def rule_label_maps_one_round_of_rule_play_test():
    """규칙의 한 라운드 -> 계획 번호. 레벨은 올릴 단계 수(0~2, 9를 넘지 않게), 남길 골드는 가장 가까운 칸."""
    from hra.plan_state import rule_label
    from meta.lobby import BOARDS
    assert rule_label(None, BOARDS[3], 3, 4, None) == (4, 1, 0)      # 2-1 첫 덱, 레벨 4 목표, 리롤 없음
    assert rule_label(BOARDS[3], BOARDS[3], 6, 7, 20) == (0, 1, 3)   # 4-1: 그대로, 7로, 20 남기고
    assert rule_label(BOARDS[3], BOARDS[7], 5, 9, 0) == (8, 2, 5)    # 갈아타기, 두 단계로 자름, 다 쓰기
    assert rule_label(BOARDS[3], BOARDS[3], 8, 9, 50) == (0, 1, 1)   # 레벨 8은 한 단계까지만
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan plan_sizes_and_slices_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.plan_state'`

- [ ] **Step 3: 구현** — `hra/plan_state.py`

```python
"""
계획 AI의 계획 번호와 상태(hra/plan_ai_design.md 2·3절).

계획은 세 갈래다: 목표 덱(0 = 그대로, 1~27 = meta/lobby.BOARDS[번호 - 1]), 목표 레벨(지금 레벨에 0~2를 더한다),
리롤할 때 남길 골드(FLOORS[번호], None은 리롤 안 함). 가림 37칸은 덱 28 + 레벨 3 + 남길 골드 6이다.
"""
import numpy as np

from meta.lobby import BOARDS

HEADS = ('place', 'hp', 'econ', 'synergy', 'units')  # 보상 갈래(설계 4절)
FLOORS = (None, 50, 30, 20, 10, 0)
PLAN_SIZES = (len(BOARDS) + 1, 3, len(FLOORS))  # (28, 3, 6)
MASK_SIZE = sum(PLAN_SIZES)                      # 37
SLICES = ((0, PLAN_SIZES[0]), (PLAN_SIZES[0], PLAN_SIZES[0] + PLAN_SIZES[1]),
          (PLAN_SIZES[0] + PLAN_SIZES[1], MASK_SIZE))


def masks(level, deck):
    """못 하는 선택을 가린 37칸. 덱이 없으면(2-1) 「그대로」를, 덱이 있으면 지금 덱을 다시 고르는 칸을 가린다
    (「그대로」와 같다). 레벨은 9를 넘는 목표를 가린다."""
    m = np.ones(MASK_SIZE, dtype=bool)
    if deck is None:
        m[0] = False
    else:
        m[BOARDS.index(deck) + 1] = False
    m[PLAN_SIZES[0] + 1] = level <= 8
    m[PLAN_SIZES[0] + 2] = level <= 7
    return m


def decode(plan, level, deck):
    """계획 번호 (덱, 레벨, 남길 골드) -> (목표 덱, 목표 레벨, 남길 골드)."""
    d, lv, fl = plan
    return (deck if d == 0 else BOARDS[d - 1]), level + lv, FLOORS[fl]


def floor_index(floor):
    """남길 골드 -> 가장 가까운 칸 번호. None(리롤 안 함)은 0번."""
    if floor is None:
        return 0
    return min(range(1, len(FLOORS)), key=lambda i: abs(FLOORS[i] - floor))


def rule_label(old_deck, new_deck, level_start, best_target, min_floor):
    """규칙 봇이 한 라운드에 한 일 -> 계획 번호(따라 하기 정답). best_target은 그 라운드에 규칙이 낸 가장 높은 목표
    레벨, min_floor는 가장 낮은 남길 골드(리롤 판단이 없었으면 None)."""
    d = 0 if new_deck is old_deck else BOARDS.index(new_deck) + 1
    lv = min(max(best_target - level_start, 0), 2, 9 - level_start)
    return d, lv, floor_index(min_floor)
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: 일곱 검사 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/plan_state.py hra/test_plan.py
git commit -m "hra: 계획 AI 계획 번호·가림·규칙 정답 옮기기" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 상태 153칸

**Files:**
- Modify: `hra/plan_state.py` (state, board_units, active_tiers, STATE_SIZE)
- Modify: `hra/test_plan.py` (도우미 `_player`와 검사 하나)

**Interfaces:**
- Consumes: `hra.score_rank.tiers_of(counts) -> int`, `meta.human_five.trait_table(units) -> dict`, `meta.human_deck.copies/units_of/scout/buildable/key_units/held_items`, `meta.pit.chosen_of`, `Simulator.stats.BASE_CHAMPION_LIST/COST`, `set4.COST_STAR_VALUE`
- Produces: `hra.plan_state.STATE_SIZE = 153`, `board_units(player) -> list`, `active_tiers(units) -> int`, `state(player, others, deck, deck_age, game_round) -> np.ndarray[153] float32`. 칸 배치: 0~7 내 상태, 8~14 내 보드, 15 + 5i ~ 19 + 5i 덱 i(BOARDS[i]), 150~151 상대 요약, 152 덱 이력.

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`에 더한다.

```python
def _player(units, bench=(), index=0, **attrs):
    """시뮬레이터 플레이어. units는 보드(구석 배치), bench는 벤치, attrs는 골드·체력·레벨 같은 값."""
    from analysis.battle import build_player, to_units
    from Simulator.pool import pool
    p = build_player(pool(), index, to_units(list(units)), 'corner')
    for u in to_units(list(bench)):
        p.add_to_bench(u)
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


def state_counts_what_a_player_can_see_test():
    """2성 야스오(선택받은 결투가, 무한의 대검)·1성 피오라·3성 잭스가 보드에, 1성 칼리스타가 벤치에 있다. 살아 있는 상대
    다섯(체력 80·70·50·90·64, 레벨 6·6·5·7·6, 첫째가 2성 야스오를 든다), 죽은 상대 둘(2성 리 신을 든 쪽은 정찰에서 빠진다).
    목표 덱은 Chosen Duelists(4번), 고른 뒤 2라운드, 3-1(칸 9)."""
    from hra.plan_state import STATE_SIZE, state
    from meta.lobby import BOARDS
    me = _player([{'name': 'yasuo', 'stars': 2, 'items': ['infinity_edge'], 'chosen': 'duelist'},
                  {'name': 'fiora', 'stars': 1, 'items': []}, {'name': 'jax', 'stars': 3, 'items': []}],
                 bench=[{'name': 'kalista', 'stars': 1, 'items': []}],
                 gold=35, health=64, level=5, exp=10, win_streak=0, loss_streak=3)
    others = [_player([{'name': 'yasuo', 'stars': 2, 'items': []}], index=1, health=80, level=6)]
    others += [_player([{'name': 'garen', 'stars': 1, 'items': []}], index=i, health=h, level=lv)
               for i, h, lv in ((2, 70, 6), (3, 50, 5), (4, 90, 7), (5, 64, 6))]
    others += [_player([{'name': 'leesin', 'stars': 2, 'items': []}], index=6, health=0, level=9),
               _player([{'name': 'garen', 'stars': 1, 'items': []}], index=7, health=0, level=9)]
    x = state(me, others, BOARDS[4], 2, 9)
    assert x.shape == (STATE_SIZE,) == (153,) and x.dtype == np.float32
    # 내 상태: 칸/40, 체력/100, 골드/60, 레벨/9, 경험치 10/20, 연승/5, 연패/5, 살아 있는 상대/7
    # 내 보드: 보드 값 3+1+17=21 /120, 2성 1/9, 3성 1/9, 특성 단계(결투가 4 → 2, 추방자 1 → 1) 3/11, 유닛 3/9, 완성 1/10, 조각 0
    assert np.allclose(x[:15], [9 / 40, 0.64, 35 / 60, 5 / 9, 0.5, 0.0, 0.6, 5 / 7,
                                21 / 120, 1 / 9, 1 / 9, 3 / 11, 3 / 9, 0.1, 0.0]), x[:15]
    assert np.allclose(x[15:20], [0.0, 0.0, 0.0, 0.125, 0.0]), x[15:20]       # 0번 Chosen Dusks: 무한의 대검 하나 만들 수 있음
    assert np.allclose(x[35:40], [25 / 40, 0.3, 1.0, 0.0, 1.0]), x[35:40]     # 4번 Chosen Duelists: 몫 25, 남의 야스오 3장
    assert np.allclose(x[150:], [3 / 7, 6 / 9, 0.1]), x[150:]                 # 나보다 체력 많은 3명, 평균 레벨 6, 이력 2
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan state_counts_what_a_player_can_see_test`
Expected: FAIL — `ImportError: cannot import name 'STATE_SIZE'`

- [ ] **Step 3: 구현** — `hra/plan_state.py`의 import 묶음과 끝에 더한다.

import 묶음을 이렇게 바꾼다.

```python
import numpy as np

from set4 import COST_STAR_VALUE
from Simulator.stats import BASE_CHAMPION_LIST, COST
from hra.score_rank import tiers_of
from meta.human_deck import buildable, copies, held_items, key_units, scout, units_of
from meta.human_five import trait_table
from meta.lobby import BOARDS
from meta.pit import chosen_of
```

파일 끝에 더한다.

```python
STATE_SIZE = 8 + 7 + 5 * len(BOARDS) + 2 + 1  # 153


def board_units(player):
    """보드에 선 챔피언(아지르 모래 병사 같은 소환물 빼고)."""
    return [u for row in player.board for u in row if u and u.name in BASE_CHAMPION_LIST]


def active_tiers(units):
    """유닛들의 발동한 특성 단계 수. 선택받은 자 +1과 상징 아이템을 시뮬레이터처럼 센다(meta/human_five.trait_table)."""
    return tiers_of(trait_table(units))


def state(player, others, deck, deck_age, game_round):
    """153칸(설계 3절). deck은 지금 목표 덱(BOARDS의 원소 또는 None), deck_age는 그 덱을 고른 뒤 지난 라운드 수.
    실제 사람이 볼 수 있는 것만 넣고, 공략 사이트 티어 점수는 넣지 않는다. 덱마다의 앞 네 값은 규칙 봇 덱 점수
    (meta/human_deck.score)의 항과 같은 셈이다."""
    alive = [o for o in others if o.health > 0]
    units = board_units(player)
    stars = [u.stars for u in units]
    need = player.level_costs[player.level] if player.level < player.max_level else 0
    completed, components = held_items(player)
    mine, theirs = copies(units_of(player)), scout(others)
    x = [game_round / 40, player.health / 100, player.gold / 60, player.level / 9,
         player.exp / need if need else 1.0, player.win_streak / 5, player.loss_streak / 5, len(alive) / 7,
         sum(COST_STAR_VALUE[COST[u.name] - 1][u.stars - 1] for u in units) / 120,
         stars.count(2) / 9, stars.count(3) / 9, active_tiers(units) / 11, len(units) / 9,
         len(completed) / 10, len(components) / 10]
    for b in BOARDS:
        trait = (chosen_of(b) or (None, None))[1]
        x += [sum(COST[u] * min(mine.get(u, 0), 9) for u in set(b['units'])) / 40,
              sum(theirs.get(u, 0) for u in key_units(b)) / 10,
              float(bool(player.chosen) and player.chosen == trait),
              buildable(b, completed, components) / 8,
              float(b is deck)]
    x += [sum(o.health > player.health for o in alive) / 7,
          sum(o.level for o in alive) / len(alive) / 9 if alive else 0.0,
          deck_age / 20]
    return np.clip(np.array(x, dtype=np.float32), 0.0, 2.0)
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: 여덟 검사 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/plan_state.py hra/test_plan.py
git commit -m "hra: 계획 AI 상태 153칸(사람이 볼 수 있는 것만, 티어표 없음)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 실행기·기록기·판 돌리기

**Files:**
- Modify: `meta/human_bot.py` (macro를 macro_plan + macro로 나눔)
- Modify: `meta/test_human_bot.py` (검사 하나)
- Create: `hra/plan_bot.py`
- Create: `hra/test_plan_game.py`
- Modify: `hra/test_plan.py` (finish 검사 하나)

**Interfaces:**
- Consumes: Task 2·3의 `HEADS, MASK_SIZE, SLICES, STATE_SIZE, masks, decode, rule_label, state, board_units, active_tiers`; `meta.human_bot.HumanPolicy(agent, board, others, rng, knobs=None)`; `meta.human_macro.action(gold, level, target, floor, exp_first) -> str`; `meta.lobby.N_PLAYERS, board_record, finish_order`; `fullgame.board_stars.quiet`
- Produces:
  - `HumanPolicy.macro_plan(player, game_round) -> (target: int, floor: int | None, exp_first: bool)`
  - 경험 하나 = `(s: float32[153], m: bool[37], a: int64[3], r: float32[5], s2: float32[153], d: bool, m2: bool[37])`
  - `hra.plan_bot.legal(plan, mask) -> bool`, `Recorder`(start_recording, close, finish, transitions, rounds, tokens), `PlanPolicy(agent, others, rng, planner)`, `RuleRecorder(agent, others, rng)`, `make_policy(seat, player, others, rng)`
  - `play(seed, seats, trace=False) -> {'seats': [{'place', 'deck', 'switches', 'board', 'transitions', ('rounds', 'tokens')}], 'capped': bool}`. seats의 원소는 `'rule'`, `'record'`, 또는 계획기 `planner(s, m) -> (d, lv, fl)`.
  - `safe_play(seed, seats, trace=False) -> (dict | None, str | None)`

- [ ] **Step 1: 사람 봇 검사 쓰기** — `meta/test_human_bot.py`의 `macro_knobs_for_gold_after_stage_five_test` 아래에 더한다.

```python
def macro_plan_gives_the_numbers_behind_macro_test():
    """레벨·리롤 판단을 「숫자 정하기」와 「행동 고르기」로 나눴다(계획 AI 따라 하기 기록이 숫자를 쓴다, hra/plan_bot).
    5단계(칸 21) 레벨 8, 60골드: 목표 8, 남길 골드 50, 경험치 우선 켜짐. macro는 그 숫자로 고른 행동이다."""
    from meta.human_bot import HumanPolicy
    from meta.human_macro import action
    p = item_player([Unit(name='garen', stars=2, items=[])], [])
    p.level, p.gold, p.health = 8, 60, 50
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    policy.mode = 'win'
    plan = policy.macro_plan(p, 21)
    assert plan == (8, 50, True) and policy.macro(p, 21) == action(60, 8, *plan) == '1'
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m meta.test_human_bot`
Expected: FAIL — `AttributeError: 'HumanPolicy' object has no attribute 'macro_plan'`

- [ ] **Step 3: 사람 봇 나누기** — `meta/human_bot.py`의 `macro`를 아래 둘로 바꾼다(본문은 옮기기만 한다).

```python
    def macro_plan(self, player, game_round):
        """(목표 레벨, 남길 골드, 5단계 레벨 8의 경험치 우선). 계획 AI의 따라 하기 기록(hra/plan_bot)도 이 숫자를 쓴다."""
        board = self.board
        stay = stay_level(board)
        done3 = stay is not None and carry3(player, board)
        steady = bool(board) and stable(player, board)
        target, floor = plan(game_round, player.level, player.health, self.mode or 'win', self.rebuilt, stay,
                             done3, steady, self.knobs, rebuild_now=self.rebuilt_at == game_round)
        if player.level >= 9 and floor is not None and self.knobs['floor_9'] is not None:
            floor = min(floor, self.knobs['floor_9'])
        # 5단계 레벨 8이면 안정 여부와 상관없이 50 넘는 몫으로 9로 간다(유저 결정 2026-10-09). 9가 되면 넘는 몫은 리롤
        exp_first = bool(self.knobs['xp_to_9']) and round_stage(game_round) >= 5 and player.level == 8
        return target, floor, exp_first

    def macro(self, player, game_round):
        return action(player.gold, player.level, *self.macro_plan(player, game_round))
```

- [ ] **Step 4: 사람 봇 검사 통과**

Run: `$PY -m meta.test_human_bot`
Expected: 56개 모두 PASS(기존 55 + 새 1)

- [ ] **Step 5: 계획 AI 판 검사 쓰기** — `hra/test_plan_game.py`를 새로 만들고, `hra/test_plan.py`에 finish 검사를 더한다.

`hra/test_plan_game.py`:

```python
"""
계획 AI 판 검사(시뮬레이터 판을 실제로 돌려서 느리다, 판 하나에 20초쯤).

실행: python -m hra.test_plan_game
"""
import numpy as np

from hra.plan_bot import play, safe_play
from hra.plan_state import MASK_SIZE, SLICES, STATE_SIZE
from meta.lobby import BOARDS

DUELISTS = next(i for i, b in enumerate(BOARDS) if b['name'] == 'Chosen Duelists') + 1


def recorded_game_chains_round_experiences_test():
    """규칙 기록기 8명 한 판: 등수는 1~8이 하나씩 나가고, 자리마다 경험이 라운드마다 하나씩 이어진다(다음 상태 = 다음 경험의
    상태). 끝 표시는 마지막 하나뿐이고 등수 보상은 마지막 경험에만 1 - 2(등수-1)/7로 붙는다. 정답은 가리지 않은 칸이다."""
    out = play(11, ['record'] * 8)
    assert not out['capped']
    assert sorted(s['place'] for s in out['seats']) == list(range(1, 9))
    for seat in out['seats']:
        ts = seat['transitions']
        assert ts, seat['place']
        assert ts[0][2][0] != 0  # 2-1에 첫 덱을 고른다
        for k, (s, m, a, r, s2, d, m2) in enumerate(ts):
            assert s.shape == (STATE_SIZE,) and m.shape == (MASK_SIZE,) and r.shape == (5,)
            assert all(m[lo + i] for (lo, _), i in zip(SLICES, a))
            assert r[1] <= 0 and 0 <= r[2] <= 1 and r[3] >= 0 and r[4] >= 0
            last = k == len(ts) - 1
            assert d == last
            assert abs(r[0] - (1 - 2 * (seat['place'] - 1) / 7 if last else 0.0)) < 1e-6
            if not last:
                assert np.array_equal(s2, ts[k + 1][0]) and np.array_equal(m2, ts[k + 1][1])


def plan_seat_rolls_buys_and_keeps_its_deck_test():
    """계획 자리 하나(0번): 2-1~2-3에는 Chosen Duelists로 가서 골드를 다 써 리롤(남길 골드 0), 그 뒤로는 그대로·레벨 그대로·
    리롤 안 함. 다른 자리는 규칙 사람 봇. 앞 라운드들에는 리롤('2')과 사기('3_')가 섞여 나오고, 뒤 라운드에는 리롤이 없다.
    덱은 끝까지 Chosen Duelists이고 갈아탄 횟수는 0이다. 한 계획이 여러 행동으로 실행된다는 뜻이다."""
    def planner(s, m):
        if not m[0]:
            return DUELISTS, 0, 5
        return (0, 0, 5) if round(float(s[0]) * 40) <= 5 else (0, 0, 0)
    out = play(12, [planner] + ['rule'] * 7, trace=True)
    seat = out['seats'][0]
    assert seat['deck'] == 'Chosen Duelists' and seat['switches'] == 0
    early = [t for r, t in seat['tokens'] if 3 <= r <= 5]
    late = [t for r, t in seat['tokens'] if r > 5]
    assert '2' in early and any(t.startswith('3_') for t in early), early
    assert '2' not in late


def deck_hopping_planner_does_not_break_the_game_test():
    """최악의 탐험: 0번 자리가 라운드마다 다른 덱으로 갈아탄다. 판이 끝까지 돌고, 갈아탄 횟수가 판단 수 - 1이다."""
    calls = []

    def planner(s, m):
        calls.append(1)
        d = len(calls) % 27 + 1
        if not m[d]:
            d = d % 27 + 1
        return d, 0, 1
    out = play(14, [planner] + ['rule'] * 7)
    seat = out['seats'][0]
    assert not out['capped'] and seat['switches'] == len(calls) - 1 == len(seat['transitions']) - 1


def rule_recorder_labels_follow_rule_rolls_test():
    """규칙 기록기의 남길 골드 정답: 그 라운드에 리롤('2')이 있었으면 「리롤 안 함」(0번)이 아니다."""
    out = play(13, ['record'] + ['rule'] * 7, trace=True)
    seat = out['seats'][0]
    rolled = {r for r, t in seat['tokens'] if t == '2'}
    assert rolled
    for r, t in zip(seat['rounds'], seat['transitions']):
        if r in rolled:
            assert t[2][2] != 0, r


def safe_play_returns_the_error_instead_of_raising_test():
    """계획기가 판 중간(3-1)에 예외를 내면 safe_play는 판을 버리고 (None, 오류 문자열)을 돌려준다."""
    def planner(s, m):
        if round(float(s[0]) * 40) >= 9:
            raise RuntimeError('boom')
        return (1 if not m[0] else 0), 0, 1
    out, err = safe_play(15, [planner] + ['rule'] * 7)
    assert out is None and 'RuntimeError: boom' in err


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:] or [n for n in list(globals()) if n.endswith('_test')]:
        globals()[name]()
        print('PASS', name)
```

`hra/test_plan.py`의 실행부 위에 더한다.

```python
def finish_without_a_decision_does_nothing_test():
    """판단 없이 끝난 자리(2-1 전 탈락)는 경험이 없고, finish를 두 번 불러도 한 번만 닫는다."""
    from hra.plan_bot import Recorder
    r = Recorder()
    r.start_recording()
    r.current_plan = lambda player: None
    me = _player([{'name': 'garen', 'stars': 1, 'items': []}])
    r.finish(me, 8)
    r.finish(me, 8)
    assert r.transitions == [] and r.finished
```

- [ ] **Step 6: 실패 확인**

Run: `$PY -m hra.test_plan finish_without_a_decision_does_nothing_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.plan_bot'`

- [ ] **Step 7: 구현** — `hra/plan_bot.py`

```python
"""
계획 AI의 실행기, 따라 하기 기록기, 판 돌리기(hra/plan_ai_design.md 2·4절).

PlanPolicy  : 사람 봇(meta/human_bot.HumanPolicy)을 물려받아, 2-1부터 라운드마다 한 번 계획기에게 계획(덱, 레벨, 남길
              골드)을 받아 실행한다. 사기·팔기·바꾸기·배치·아이템은 사람 봇 규칙 그대로 계획의 목표 덱을 따르므로,
              한 계획이 그 라운드의 여러 행동(리롤, 사기, 팔기)으로 이뤄진다.
RuleRecorder: 규칙 사람 봇을 그대로 두고, 라운드마다 규칙이 한 일을 계획 번호(따라 하기 정답)로 적는다.
둘 다 라운드마다 경험 (상태, 가림, 계획, 보상 5갈래, 다음 상태, 끝, 다음 가림)을 쌓는다(Recorder).
play()      : 자리 8개에 정책을 붙여 한 판을 돌린다(meta/lobby.play와 같은 틀).
"""
import random
from math import floor

import numpy as np

import config
import Simulator.config as sim_config
from Simulator.observation.token.basic_observation import ObservationToken
from Simulator.player import Player
from Simulator.tft_simulator import TFTConfig, parallel_env
from fullgame.board_stars import quiet
from hra.plan_state import MASK_SIZE, SLICES, STATE_SIZE, active_tiers, board_units, decode, masks, rule_label, state
from meta.human_bot import HumanPolicy
from meta.human_macro import action
from meta.lobby import N_PLAYERS, board_record, finish_order

try:
    import utils
except ImportError:
    from Simulator import utils

FIRST_ROUND = 3   # 2-1. 그 전(1단계)은 규칙이 맡는다
MAX_STEPS = 5000  # meta/lobby.play와 같은 걸음 상한

# 이자 보상(설계 4절): 시뮬레이터는 라운드 시작 수입(Player.gold_income)에서 그때 골드로 이자를 준다. 준 이자를 남겨 둔다.
_gold_income = Player.gold_income


def _gold_income_recording(self, t_round):
    self.last_interest = min(floor(self.gold / 10), 5)
    return _gold_income(self, t_round)


Player.gold_income = _gold_income_recording


def legal(plan, mask):
    """계획 세 갈래가 모두 가리지 않은 칸인가."""
    return all(mask[lo + a] for (lo, _), a in zip(SLICES, plan))


class Recorder:
    """라운드마다 경험을 쌓는다. 라운드 r의 보상은 라운드 r+1의 첫 판단 때 센다(그때 보드가 라운드 r에 싸운 보드이고,
    라운드 r+1 시작 수입에서 라운드 r 끝 골드로 이자를 받는다). 물려받는 쪽이 current_plan(player)을 정한다."""

    def start_recording(self):
        self.transitions, self.rounds, self.tokens = [], [], []
        self.pending = None   # (상태, 가림, 계획 또는 None, 라운드 시작 체력, 라운드)
        self.finished = False

    def close(self, player, plan, next_state, next_mask, done, place=None):
        """미뤄 둔 판단 하나를 경험으로 닫는다. 정답이 가린 칸이면 버린다."""
        if self.pending is None:
            return
        s, m, _, hp0, game_round = self.pending
        self.pending = None
        if plan is None or not legal(plan, m):
            return
        units = board_units(player)
        r = np.array([0.0 if place is None else 1 - 2 * (place - 1) / (N_PLAYERS - 1),
                      -min((hp0 - max(player.health, 0)) / 20, 1.0),
                      0.0 if done else getattr(player, 'last_interest', 0) / 5,
                      active_tiers(units) / 11,
                      len(units) / 9], dtype=np.float32)
        self.transitions.append((s, m, np.array(plan, dtype=np.int64), r, next_state, done, next_mask))
        self.rounds.append(game_round)

    def finish(self, player, place):
        """탈락하거나 판이 끝났을 때 한 번. 마지막 판단에 등수 보상과 끝 표시를 붙인다."""
        if self.finished:
            return
        self.finished = True
        self.close(player, self.current_plan(player), np.zeros(STATE_SIZE, np.float32),
                   np.ones(MASK_SIZE, bool), True, place)


class PlanPolicy(Recorder, HumanPolicy):
    """계획기를 따르는 사람 봇. planner(상태, 가림) -> (덱, 레벨, 남길 골드) 번호."""

    def __init__(self, agent, others, rng, planner):
        HumanPolicy.__init__(self, agent, None, others, rng)
        self.planner = planner
        self.target, self.floor, self.deck_age, self.plan_round = None, None, 0, None
        self.start_recording()

    def __call__(self, player, shop, game_round, mask):
        if game_round >= FIRST_ROUND and game_round != self.plan_round:
            self.plan_round = game_round
            self.begin_round(player, game_round)
        token = HumanPolicy.__call__(self, player, shop, game_round, mask)
        self.tokens.append((game_round, token))
        return token

    def current_plan(self, player):
        return self.pending[2] if self.pending else None

    def begin_round(self, player, game_round):
        if self.board is not None:
            self.deck_age += 1
        s, m = state(player, self.others, self.board, self.deck_age, game_round), masks(player.level, self.board)
        self.close(player, self.current_plan(player), s, m, False)
        plan = tuple(int(i) for i in self.planner(s, m))
        assert legal(plan, m), (plan, game_round)
        deck, self.target, self.floor = decode(plan, player.level, self.board)
        if deck is not self.board:
            if self.board is not None:
                self.switches += 1
            self.set_board(deck)
            self.deck_age = 0
        self.pending = (s, m, plan, player.health, game_round)

    def pick_deck(self, player, game_round):
        """덱은 계획이 고른다(begin_round)."""

    def macro(self, player, game_round):
        if self.target is None:  # 2-1 전(1단계)은 규칙 그대로
            return HumanPolicy.macro(self, player, game_round)
        return action(player.gold, player.level, self.target, self.floor, False)


class RuleRecorder(Recorder, HumanPolicy):
    """규칙 사람 봇을 그대로 두고 라운드마다 한 일을 계획 번호로 적는다(따라 하기 자료, 설계 2절). 덱은 그 라운드 첫 행동의
    덱 고르기 결과, 레벨은 그 라운드에 규칙이 낸 가장 높은 목표 레벨 - 시작 레벨(0~2), 남길 골드는 그 라운드에 규칙이 낸
    가장 낮은 값(리롤 판단이 없었으면 리롤 안 함)이다. 상태는 덱 고르기 전에 센다(AI가 판단하는 자리와 같다)."""

    def __init__(self, agent, others, rng):
        HumanPolicy.__init__(self, agent, None, others, rng)
        self.deck_age, self.plan_round = 0, None
        self.old_deck, self.level_start, self.best_target, self.min_floor = None, 0, 0, None
        self.start_recording()

    def __call__(self, player, shop, game_round, mask):
        if game_round >= FIRST_ROUND and game_round != self.plan_round:
            self.plan_round = game_round
            self.begin_round(player, game_round)
        token = HumanPolicy.__call__(self, player, shop, game_round, mask)  # 라운드 첫 호출이면 여기서 규칙이 덱을 고른다
        self.tokens.append((game_round, token))
        return token

    def current_plan(self, player):
        if self.pending is None:
            return None
        return rule_label(self.old_deck, self.board, self.level_start, self.best_target, self.min_floor)

    def begin_round(self, player, game_round):
        if self.board is not None:
            self.deck_age += 1
        s, m = state(player, self.others, self.board, self.deck_age, game_round), masks(player.level, self.board)
        self.close(player, self.current_plan(player), s, m, False)
        self.old_deck, self.level_start, self.best_target, self.min_floor = self.board, player.level, player.level, None
        self.pending = (s, m, None, player.health, game_round)

    def set_board(self, board):
        if board is not getattr(self, 'board', None):
            self.deck_age = 0
        HumanPolicy.set_board(self, board)

    def macro(self, player, game_round):
        target, floor_, exp_first = self.macro_plan(player, game_round)
        if self.pending is not None:
            eff = 9 if exp_first and player.level < 9 and player.gold >= 54 else target
            self.best_target = max(self.best_target, eff)
            if floor_ is not None:
                self.min_floor = floor_ if self.min_floor is None else min(self.min_floor, floor_)
        return action(player.gold, player.level, target, floor_, exp_first)


def make_policy(seat, player, others, rng):
    """seat: 'rule'(규칙 사람 봇), 'record'(규칙 + 기록), 또는 계획기(부를 수 있는 것)."""
    if seat == 'rule':
        policy = HumanPolicy(player.default_agent, None, others, rng)
    elif seat == 'record':
        policy = RuleRecorder(player.default_agent, others, rng)
    else:
        policy = PlanPolicy(player.default_agent, others, rng, seat)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy


def play(seed, seats, trace=False):
    """한 판. seats는 자리 8개의 정책(make_policy). 돌려주는 값:
    {'seats': [{'place', 'deck', 'switches', 'board', 'transitions', ('rounds', 'tokens': trace일 때)}], 'capped'}.
    transitions는 기록하는 정책(계획기, 'record')만 채운다."""
    sim_config.LOGMESSAGES = False
    random.seed(seed)
    np.random.seed(seed)
    with quiet():
        env = parallel_env(TFTConfig(observation_class=ObservationToken,
                                     max_actions_per_round=config.ACTIONS_PER_TURN))
        obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
        agents = list(info)
        players = {a: info[a]['player'] for a in agents}
        policies = {a: make_policy(seats[i], players[a], [players[o] for o in agents if o != a],
                                   random.Random(seed * N_PLAYERS + i)) for i, a in enumerate(agents)}
        placement, start_hp, seen, ties, rank, steps = {}, {}, set(), random.Random(seed), N_PLAYERS, 0
        while obs and steps < MAX_STEPS:
            steps += 1
            alive = list(obs)
            actions = []
            for a in alive:
                game_round, p = info[a]['game_round'], players[a]
                if (a, game_round) not in seen:
                    seen.add((a, game_round))
                    start_hp[a] = p.health
                actions.append(p.default_policy(game_round, info[a]['shop'], obs[a]['action_mask']))
            decoded = utils.decode_action(actions)
            obs, _, terminated, _, info = env.step({a: decoded[i] for i, a in enumerate(alive)})
            ended = [a for a, e in terminated.items() if e and a not in placement]
            for a in finish_order(ended, players, start_hp, ties):
                placement[a], rank = rank, rank - 1
        for a in agents:  # 걸음 상한에 걸려 끝까지 terminated가 안 온 플레이어
            if a not in placement:
                placement[a], rank = rank, rank - 1
    out = []
    for a in agents:
        pol = policies[a]
        if isinstance(pol, Recorder):
            pol.finish(players[a], placement[a])
        row = {'place': placement[a], 'deck': pol.board['name'] if pol.board else None, 'switches': pol.switches,
               'board': board_record(players[a]), 'transitions': getattr(pol, 'transitions', [])}
        if trace:
            row['rounds'], row['tokens'] = getattr(pol, 'rounds', []), getattr(pol, 'tokens', [])
        out.append(row)
    return {'seats': out, 'capped': steps >= MAX_STEPS}


def safe_play(seed, seats, trace=False):
    """play()와 같지만 시뮬레이터나 계획기가 판 중간에 예외를 내면 그 판을 버리고 (None, 오류 문자열)을 돌려준다
    (설계 8절). 정상이면 (결과, None)."""
    try:
        return play(seed, seats, trace), None
    except Exception as e:  # 어느 예외든 그 판만 버리고 부른 쪽이 센다
        return None, f'{type(e).__name__}: {e}'
```

- [ ] **Step 8: 빠른 검사 통과**

Run: `$PY -m hra.test_plan`
Expected: 아홉 검사 모두 PASS

- [ ] **Step 9: 느린 검사 통과** (판 다섯, 2~3분)

Run: `$PY -m hra.test_plan_game`
Expected: 다섯 검사 모두 PASS. 실패하면 판 시드와 자리의 tokens를 찍어 원인을 찾는다(검사를 고치기 전에 실행기를 먼저 의심한다).

- [ ] **Step 10: 기존 묶음 회귀**

Run: `$PY -m meta.test_lobby` 그리고 `$PY -m meta.test_real_boards`
Expected: 16개, 14개 모두 PASS

- [ ] **Step 11: 커밋**

```bash
git add meta/human_bot.py meta/test_human_bot.py hra/plan_bot.py hra/test_plan_game.py hra/test_plan.py
git commit -m "hra: 계획 AI 실행기·따라 하기 기록기·판 돌리기(사람 봇 레벨·리롤 판단을 숫자와 행동으로 나눔)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 신경망

**Files:**
- Create: `hra/plan_net.py`
- Modify: `hra/test_plan.py` (검사 다섯)

**Interfaces:**
- Consumes: `hra.plan_state.HEADS, MASK_SIZE, SLICES, STATE_SIZE`
- Produces: `hra.plan_net.CONFIGS = ('none', 'synergy', 'units', 'both')`, `weights(config, aux_w) -> dict[str, float]`, `PlanNet(hidden=256)` (forward: (배치, 153) -> (배치, 5, 37)), `combined(q, w) -> Tensor(배치, 37)`, `masked_argmax(values, mask) -> LongTensor(배치, 3)`, `choose(net, state, mask, w, eps=(0, 0, 0), rng=random) -> tuple[int, int, int]`, `flip_rate(net, states, masks_, w) -> float`, `save(net, path, w, **meta)`, `load(path) -> (PlanNet, dict, dict)`

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`에 더한다.

```python
def plan_net_outputs_five_heads_by_37_cells_test():
    import torch
    from hra.plan_net import PlanNet
    assert tuple(PlanNet()(torch.zeros(4, 153)).shape) == (4, 5, 37)


def masked_choice_never_picks_a_hidden_cell_test():
    """가중합으로 고르든 무작위로 고르든(탐험 몫 100%) 가린 칸은 고르지 않는다. 2-1에 「그대로」를 고르면 덱 없이 판이 돈다."""
    import random
    import torch
    from hra.plan_net import PlanNet, choose, weights
    from hra.plan_state import masks
    from meta.lobby import BOARDS
    torch.manual_seed(0)
    net, w, rng = PlanNet(), weights('both', 0.1), random.Random(0)
    for level, deck in ((3, None), (8, BOARDS[4]), (9, BOARDS[0])):
        m = masks(level, deck)
        for eps in ((0, 0, 0), (1, 1, 1)):
            for _ in range(300):
                d, lv, fl = choose(net, np.zeros(153, np.float32), m, w, eps, rng)
                assert m[d] and m[28 + lv] and m[31 + fl], (level, eps, d, lv, fl)


def exploration_rate_is_per_branch_test():
    """덱 갈래만 탐험 몫 100%, 나머지 0%면 레벨·남길 골드는 늘 가중합 선택과 같고 덱은 여러 칸이 나온다."""
    import random
    import torch
    from hra.plan_net import PlanNet, choose, weights
    from hra.plan_state import masks
    torch.manual_seed(1)
    net, w, rng, m = PlanNet(), weights('none', 0.1), random.Random(1), masks(5, None)
    s = np.full(153, 0.3, np.float32)
    greedy = choose(net, s, m, w)
    picks = [choose(net, s, m, w, (1, 0, 0), rng) for _ in range(200)]
    assert all(p[1:] == greedy[1:] for p in picks) and len({p[0] for p in picks}) > 10


def weights_follow_config_test():
    from hra.plan_net import weights
    assert weights('none', 0.1) == {'place': 1.0, 'hp': 1.0, 'econ': 0.3, 'synergy': 0.0, 'units': 0.0}
    assert weights('both', 0.3)['synergy'] == weights('both', 0.3)['units'] == 0.3
    assert weights('units', 0.1)['synergy'] == 0.0 and weights('synergy', 0.1)['units'] == 0.0


def plan_net_save_load_and_flip_rate_test():
    """저장했다 불러온 신경망은 같은 값과 같은 선택을 낸다. 보조 갈래 가중치가 0이면 보조 갈래가 뒤집는 판단은 없다."""
    import os
    import tempfile
    import torch
    from hra.plan_net import PlanNet, flip_rate, load, save, weights
    from hra.plan_state import masks
    net, w = PlanNet(), weights('both', 0.1)
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(net, path, w, config='both', seed=1, games=0)
    net2, w2, meta = load(path)
    x = torch.rand(16, 153)
    assert torch.equal(net(x), net2(x)) and w2 == w and meta == {'config': 'both', 'seed': 1, 'games': 0}
    states = np.random.default_rng(0).random((50, 153)).astype(np.float32)
    ms = np.stack([masks(5, None)] * 50)
    assert flip_rate(net, states, ms, weights('none', 0.3)) == 0.0
    assert 0.0 <= flip_rate(net, states, ms, weights('both', 5.0)) <= 1.0
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan plan_net_outputs_five_heads_by_37_cells_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.plan_net'`

- [ ] **Step 3: 구현** — `hra/plan_net.py`

```python
"""
계획 AI 신경망(hra/plan_ai_design.md 5절).

상태 153칸 -> 공유 두 층(256) -> 보상 갈래 5 x 행동 칸 37(덱 28 + 레벨 3 + 남길 골드 6). 행동 갈래마다 다섯 갈래 값을
가중합하고, 가린 칸을 빼고 가장 큰 쪽을 고른다(1학기 hra/model.py를 행동 갈래로 넓힌 것). 갈래마다 따로 값을 배우니
판단마다 어느 보상 갈래가 밀었는지 꺼내 볼 수 있다.
"""
import os
import random

import torch
import torch.nn as nn

from hra.plan_state import HEADS, MASK_SIZE, SLICES, STATE_SIZE

CONFIGS = ('none', 'synergy', 'units', 'both')


def weights(config, aux_w):
    """설정 이름 -> 보상 가중치(설계 4절). 등수 1, 체력 1, 이자 0.3, 시너지·유닛 수는 켜면 aux_w."""
    assert config in CONFIGS, config
    return {'place': 1.0, 'hp': 1.0, 'econ': 0.3,
            'synergy': aux_w if config in ('synergy', 'both') else 0.0,
            'units': aux_w if config in ('units', 'both') else 0.0}


class PlanNet(nn.Module):
    def __init__(self, hidden=256):
        super().__init__()
        self.args = {'hidden': hidden}  # 불러올 때 같은 모양으로 다시 짓는다
        self.trunk = nn.Sequential(nn.Linear(STATE_SIZE, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.out = nn.Linear(hidden, len(HEADS) * MASK_SIZE)

    def forward(self, x):
        """(배치, 153) -> (배치, 5, 37)."""
        return self.out(self.trunk(x)).view(-1, len(HEADS), MASK_SIZE)


def combined(q, w):
    """(배치, 5, 37) -> 보상 가중합 (배치, 37)."""
    return sum(w[h] * q[:, i] for i, h in enumerate(HEADS))


def masked_argmax(values, mask):
    """(배치, 37) 값과 가림 -> 행동 갈래마다 가리지 않은 칸 중 가장 큰 번호 (배치, 3)."""
    v = values.masked_fill(~mask, float('-inf'))
    return torch.stack([v[:, lo:hi].argmax(1) for lo, hi in SLICES], 1)


def choose(net, state, mask, w, eps=(0.0, 0.0, 0.0), rng=random):
    """상태 하나 -> 계획 (덱, 레벨, 남길 골드). eps는 행동 갈래마다 무작위로 고를 몫이다. 무작위로 골라도 가린 칸은 안 고른다."""
    with torch.no_grad():
        q = net(torch.as_tensor(state, dtype=torch.float32).unsqueeze(0))
    plan = masked_argmax(combined(q, w), torch.as_tensor(mask, dtype=torch.bool).unsqueeze(0))[0].tolist()
    for i, (lo, hi) in enumerate(SLICES):
        if rng.random() < eps[i]:
            plan[i] = rng.choice([j for j in range(hi - lo) if mask[lo + j]])
    return tuple(plan)


def flip_rate(net, states, masks_, w):
    """보조 갈래(시너지·유닛 수)를 뺐을 때 계획이 바뀌는 판단의 몫(설계 4절 사전 시험, 5절 중간 점검)."""
    if not len(states):
        return 0.0
    with torch.no_grad():
        q = net(torch.as_tensor(states, dtype=torch.float32))
    m = torch.as_tensor(masks_, dtype=torch.bool)
    a = masked_argmax(combined(q, w), m)
    b = masked_argmax(combined(q, dict(w, synergy=0.0, units=0.0)), m)
    return float((a != b).any(1).float().mean())


def save(net, path, w, **meta):
    """신경망·보상 가중치·설명(meta, 기본형만)을 함께 저장한다. 다른 프로세스가 읽는 중에 덮지 않게 임시 파일에 쓰고 바꾼다."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    torch.save({'args': net.args, 'state_dict': net.state_dict(), 'weights': dict(w), 'meta': meta}, tmp)
    os.replace(tmp, path)


def load(path):
    ck = torch.load(path, map_location='cpu', weights_only=True)
    net = PlanNet(**ck['args'])
    net.load_state_dict(ck['state_dict'])
    net.eval()
    return net, ck['weights'], ck['meta']
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: 열네 검사 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/plan_net.py hra/test_plan.py
git commit -m "hra: 계획 AI 신경망(보상 갈래 5 x 행동 칸 37, 가림·갈래별 탐험·보조 갈래 뒤집는 비율)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 학습 바탕 — 경험 더미와 손실

**Files:**
- Create: `hra/plan_learn.py`
- Modify: `hra/test_plan.py` (검사 셋)

**Interfaces:**
- Consumes: `hra.plan_net.combined, masked_argmax, PlanNet`; `hra.plan_state.HEADS, MASK_SIZE, SLICES, STATE_SIZE`; Task 4의 경험 튜플 순서
- Produces: `hra.plan_learn.GAMMA = 0.98`, `MARGIN = 0.8`, `KEYS = ('s', 'm', 'a', 'r', 's2', 'd', 'm2')`, `Replay(capacity)` (`add(t)`, `sample(k, rng) -> dict[str, Tensor]`, `arrays() -> dict`, `from_arrays(arrays) -> Replay`, `len()`), `td_loss(net, target, batch, w) -> Tensor`, `margin_loss(net, batch, w) -> Tensor`, `learn_step(net, target, opt, w, batch=None, demo=None, lam=1.0) -> float`

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`에 더한다.

```python
def _bandit_transition(d, s, m):
    """판단 한 번에 끝나는 판의 경험: 덱 3번이면 등수 +1, 아니면 -1."""
    return (s, m, np.array([d, 0, 0]), np.array([1.0 if d == 3 else -1.0, 0, 0, 0, 0], np.float32),
            np.zeros(153, np.float32), True, np.ones(37, bool))


def replay_wraps_around_test():
    from hra.plan_learn import Replay
    r = Replay(3)
    s, m = np.zeros(153, np.float32), np.ones(37, bool)
    for d in range(5):
        r.add(_bandit_transition(d, s, m))
    assert len(r) == 3 and sorted(r.a[:, 0].tolist()) == [2, 3, 4]
    back = Replay.from_arrays(r.arrays())
    assert len(back) == 3 and np.array_equal(back.a, r.a)


def td_loss_learns_a_one_round_bandit_test():
    """무작위로 고른 경험 600개로 배우면 가중합 선택이 등수 +1을 주는 덱 3번이다."""
    import torch
    from hra.plan_learn import Replay, learn_step
    from hra.plan_net import PlanNet, choose, weights
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    s, m = np.full(153, 0.5, np.float32), np.ones(37, bool)
    m[0] = False
    replay = Replay(1000)
    for _ in range(600):
        replay.add(_bandit_transition(int(rng.integers(1, 28)), s, m))
    net, target, w = PlanNet(), PlanNet(), weights('none', 0.1)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ in range(400):
        learn_step(net, target, opt, w, batch=replay.sample(64, rng))
    assert choose(net, s, m, w)[0] == 3


def margin_loss_makes_demo_choices_win_test():
    """여백 손실로 상태 다섯 개의 정답 계획을 외운다(보상은 모두 0)."""
    import torch
    from hra.plan_learn import Replay, learn_step
    from hra.plan_net import PlanNet, choose, weights
    torch.manual_seed(2)
    rng = np.random.default_rng(2)
    states = rng.random((5, 153)).astype(np.float32)
    labels = [(4, 1, 2), (9, 0, 5), (17, 2, 0), (1, 1, 1), (26, 0, 3)]
    demos = Replay(10)
    for s, a in zip(states, labels):
        demos.add((s, np.ones(37, bool), np.array(a), np.zeros(5, np.float32), np.zeros(153, np.float32), True,
                   np.ones(37, bool)))
    net, target, w = PlanNet(), PlanNet(), weights('none', 0.1)
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ in range(300):
        learn_step(net, target, opt, w, demo=demos.sample(5, rng))
    assert [choose(net, s, np.ones(37, bool), w) for s in states] == labels
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan replay_wraps_around_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.plan_learn'`

- [ ] **Step 3: 구현** — `hra/plan_learn.py`

```python
"""
계획 AI 학습의 바탕(hra/plan_ai_design.md 5절): 경험 더미, 갈래별 Q 손실, 따라 하기 여백 손실, 한 걸음 학습.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from hra.plan_net import combined, masked_argmax
from hra.plan_state import HEADS, MASK_SIZE, SLICES, STATE_SIZE

GAMMA = 0.98
MARGIN = 0.8
KEYS = ('s', 'm', 'a', 'r', 's2', 'd', 'm2')  # hra/plan_bot.Recorder 경험의 순서


class Replay:
    """경험 더미(고리). 꽉 차면 가장 오래된 것부터 덮는다."""

    def __init__(self, capacity):
        self.cap, self.n, self.i = capacity, 0, 0
        self.s = np.zeros((capacity, STATE_SIZE), np.float32)
        self.m = np.zeros((capacity, MASK_SIZE), bool)
        self.a = np.zeros((capacity, 3), np.int64)
        self.r = np.zeros((capacity, len(HEADS)), np.float32)
        self.s2 = np.zeros((capacity, STATE_SIZE), np.float32)
        self.d = np.zeros(capacity, np.float32)
        self.m2 = np.zeros((capacity, MASK_SIZE), bool)

    def __len__(self):
        return self.n

    def add(self, t):
        """t = (상태, 가림, 계획, 보상, 다음 상태, 끝, 다음 가림)."""
        for key, value in zip(KEYS, t):
            getattr(self, key)[self.i] = value
        self.i = (self.i + 1) % self.cap
        self.n = min(self.n + 1, self.cap)

    def sample(self, k, rng):
        idx = rng.integers(0, self.n, k)
        return {key: torch.as_tensor(getattr(self, key)[idx]) for key in KEYS}

    def arrays(self):
        return {key: getattr(self, key)[:self.n] for key in KEYS}

    @classmethod
    def from_arrays(cls, arrays):
        n = len(arrays['s'])
        replay = cls(max(n, 1))
        for key in KEYS:
            getattr(replay, key)[:n] = arrays[key]
        replay.n, replay.i = n, n % replay.cap
        return replay


def _pick(q, a):
    """(배치, 5, 칸) 값에서 배치마다 고른 칸 -> (배치, 5)."""
    return q.gather(2, a.view(-1, 1, 1).expand(-1, q.shape[1], 1)).squeeze(2)


def td_loss(net, target, batch, w):
    """갈래별 Q 손실. 다음 행동은 지금 신경망의 가중합으로 고르고(가린 칸 빼고), 값은 갈래마다 목표 신경망의 자기 값으로
    부트스트랩한다(1학기 hra/train.py와 같은 방식을 행동 갈래 셋으로)."""
    q = net(batch['s'])
    with torch.no_grad():
        a2 = masked_argmax(combined(net(batch['s2']), w), batch['m2'])
        q2 = target(batch['s2'])
    keep = (1 - batch['d']).unsqueeze(1)
    loss = 0.0
    for i, (lo, hi) in enumerate(SLICES):
        y = batch['r'] + GAMMA * keep * _pick(q2[:, :, lo:hi], a2[:, i])
        loss = loss + F.smooth_l1_loss(_pick(q[:, :, lo:hi], batch['a'][:, i]), y)
    return loss / len(SLICES)


def margin_loss(net, batch, w):
    """따라 하기 여백 손실(DQfD): 행동 갈래마다 정답 칸의 가중합 값이 가리지 않은 다른 칸보다 MARGIN 이상 높아야 한다."""
    c = combined(net(batch['s']), w).masked_fill(~batch['m'], float('-inf'))
    loss = 0.0
    for i, (lo, hi) in enumerate(SLICES):
        v, a = c[:, lo:hi], batch['a'][:, i:i + 1]
        bonus = torch.full_like(v, MARGIN).scatter(1, a, 0.0)
        loss = loss + ((v + bonus).max(1).values - v.gather(1, a).squeeze(1)).mean()
    return loss / len(SLICES)


def learn_step(net, target, opt, w, batch=None, demo=None, lam=1.0):
    """한 걸음. batch는 자기 대전 경험(값 손실), demo는 따라 하기 경험(값 손실 + 여백 손실). 둘 중 하나는 있어야 한다."""
    loss = 0.0
    if batch is not None:
        loss = loss + td_loss(net, target, batch, w)
    if demo is not None:
        loss = loss + td_loss(net, target, demo, w) + lam * margin_loss(net, demo, w)
    opt.zero_grad()
    loss.backward()
    nn.utils.clip_grad_norm_(net.parameters(), 10.0)
    opt.step()
    return float(loss)
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: 열일곱 검사 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/plan_learn.py hra/test_plan.py
git commit -m "hra: 계획 AI 학습 바탕(경험 더미, 갈래별 Q 손실, 여백 손실)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 따라 하기 자료 모으기

**Files:**
- Create: `hra/collect.py`
- Modify: `hra/test_plan_game.py` (검사 하나)
- 산출물: `checkpoints/plan_demos.npz` (커밋 안 함)

**Interfaces:**
- Consumes: `hra.plan_bot.safe_play`, `hra.plan_learn.KEYS`, `meta.lobby.N_PLAYERS`
- Produces: `hra.collect.SEED_BASE = 900000`, `one_game(seed) -> (list[경험], str | None)`, `stack(transitions, games=None) -> dict` (KEYS별 배열, games를 주면 'game' 열), npz 파일(KEYS + 'game' + 'n_games')

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan_game.py`에 더한다.

```python
def one_recorded_game_stacks_into_arrays_test():
    """기록 판 하나를 모으면 KEYS별 배열이 같은 길이로 쌓이고 끝 표시는 자리 수(8)만큼이다. 판 번호 열이 붙는다."""
    from hra.collect import one_game, stack
    ts, err = one_game(901)
    assert err is None and ts
    data = stack(ts, games=[0] * len(ts))
    n = len(ts)
    assert data['s'].shape == (n, 153) and data['m'].shape == (n, 37) and data['a'].shape == (n, 3)
    assert data['r'].shape == (n, 5) and data['d'].sum() == 8 and (data['game'] == 0).all()
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan_game one_recorded_game_stacks_into_arrays_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.collect'`

- [ ] **Step 3: 구현** — `hra/collect.py`

```python
"""
따라 하기 자료 모으기(hra/plan_ai_design.md 5절): 규칙 사람 봇 8명이 모두 기록하는 판을 돌려 경험을 npz로 저장한다.
시뮬레이터가 판 중간에 멈춘 판은 건너뛰고 수를 적는다. 판 번호 열(game)은 데우기에서 판 단위로 떼어 내는 데 쓴다.

실행: python -m hra.collect --games 2000 --jobs 7 --out checkpoints/plan_demos.npz
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_bot import safe_play
from hra.plan_learn import KEYS
from meta.lobby import N_PLAYERS

SEED_BASE = 900000  # 자기 대전·평가와 겹치지 않는 시드 구간


def one_game(seed):
    """한 판의 경험 목록과 오류(없으면 None)."""
    out, err = safe_play(seed, ['record'] * N_PLAYERS)
    if out is None:
        return [], err
    return [t for seat in out['seats'] for t in seat['transitions']], None


def stack(transitions, games=None):
    """경험 목록 -> KEYS별 배열. games(경험마다 판 번호)를 주면 'game' 열을 붙인다."""
    data = {key: np.stack(col) for key, col in zip(KEYS, zip(*transitions))}
    if games is not None:
        data['game'] = np.array(games)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=2000)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=os.path.join('checkpoints', 'plan_demos.npz'))
    args = ap.parse_args()
    transitions, games, errors = [], [], []
    with Pool(args.jobs) as workers:
        seeds = range(SEED_BASE, SEED_BASE + args.games)
        for k, (ts, err) in enumerate(workers.imap(one_game, seeds)):
            transitions += ts
            games += [k] * len(ts)
            if err:
                errors.append(err)
            if (k + 1) % 100 == 0:
                print(f'{k + 1}판, 경험 {len(transitions)}개, 멈춘 판 {len(errors)}', flush=True)
    data = stack(transitions, games)
    data['n_games'] = np.array(args.games - len(errors))
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    np.savez_compressed(args.out, **data)
    print(f'저장: {args.out} (경험 {len(transitions)}개, 멈춘 판 {len(errors)}개)')
    for e in errors[:5]:
        print('  ', e)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan_game one_recorded_game_stacks_into_arrays_test`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/collect.py hra/test_plan_game.py
git commit -m "hra: 따라 하기 자료 모으기(규칙 기록기 8명 판, 판 번호 열)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 2천 판 모으기** (1~3시간, 충전기를 꽂고 뒤에서 돌린다)

Run: `$PY -m hra.collect --games 2000 --jobs 7`
Expected: 100판마다 진행이 찍히고 마지막에 `저장: checkpoints/plan_demos.npz (경험 N개, 멈춘 판 M개)`. N은 40만 안팎, M은 0에 가깝다. M이 판의 1%를 넘으면 멈춘 오류 다섯을 보고 june 버그로 다룬다(이 계획 밖, 유저에게 알림). 숫자는 장부에 적는다.

---

### Task 8: 데우기

**Files:**
- Create: `hra/pretrain.py`
- Modify: `hra/test_plan.py` (검사 둘)
- 산출물: `checkpoints/plan_warm_<설정>.pt` (커밋 안 함)

**Interfaces:**
- Consumes: `hra.plan_learn.KEYS, Replay, learn_step`; `hra.plan_net.PlanNet, combined, masked_argmax, save, weights`; Task 7의 npz
- Produces: `hra.pretrain.split_by_game(data, held=0.1, seed=0) -> (dict, dict)`, `agreement(net, data, w) -> {'deck', 'level', 'floor', 'all'}`, `pretrain(train, w, steps, seed=0, log_every=2000, test=None) -> (net, target, opt)`, CLI

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan.py`에 더한다.

```python
def _fake_demos(n, seed=0):
    """정답이 상태 첫 칸으로 정해지는 가짜 따라 하기 자료(덱 = 1 + 첫 칸을 27칸으로 나눈 번호, 레벨 0, 남길 골드 1)."""
    rng = np.random.default_rng(seed)
    s = rng.random((n, 153)).astype(np.float32)
    deck = 1 + (s[:, 0] * 27).astype(int).clip(0, 26)
    return {'s': s, 'm': np.ones((n, 37), bool), 'a': np.stack([deck, np.zeros(n, int), np.ones(n, int)], 1),
            'r': np.zeros((n, 5), np.float32), 's2': np.zeros((n, 153), np.float32), 'd': np.ones(n, bool),
            'm2': np.ones((n, 37), bool), 'game': np.arange(n) // 10}


def split_by_game_keeps_games_whole_test():
    """같은 판의 경험은 학습과 점검 중 한쪽에만 간다. 20판(판마다 10개) 중 10%인 2판을 떼어 둔다.
    상태 첫 칸은 경험마다 다른 무작위 값이라 그 값으로 경험의 판을 찾는다."""
    from hra.pretrain import split_by_game
    data = _fake_demos(200)
    game_of = {float(v): int(g) for v, g in zip(data['s'][:, 0], data['game'])}
    train, test = split_by_game(data, held=0.1, seed=0)
    test_games = {game_of[float(v)] for v in test['s'][:, 0]}
    train_games = {game_of[float(v)] for v in train['s'][:, 0]}
    assert len(test['s']) == 20 and len(train['s']) == 180
    assert len(test_games) == 2 and not test_games & train_games


def pretrain_learns_a_simple_rule_test():
    """가짜 자료 300개를 데우면 셋 다 맞는 비율이 0.9를 넘는다."""
    from hra.plan_net import weights
    from hra.pretrain import agreement, pretrain
    data = _fake_demos(300)
    w = weights('none', 0.1)
    net, _, _ = pretrain(data, w, steps=1500, seed=0)
    assert agreement(net, data, w)['all'] > 0.9
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan split_by_game_keeps_games_whole_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.pretrain'`

- [ ] **Step 3: 구현** — `hra/pretrain.py`

```python
"""
데우기(hra/plan_ai_design.md 5절): 따라 하기 자료로 신경망을 데운다. 규칙의 선택에 가장 높은 값을 주게 하면서(여백 손실)
그 판의 실제 보상으로 값도 배운다(시연에서 배우는 Q학습, DQfD). 판 단위로 10%를 떼어 일치율(성공 기준 3의 첫 숫자)을 잰다.

실행: python -m hra.pretrain --config both --aux-w 0.1 --steps 20000 --out checkpoints/plan_warm_both.pt
"""
import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_learn import KEYS, Replay, learn_step
from hra.plan_net import PlanNet, combined, masked_argmax, save, weights

BATCH, LR, SYNC = 256, 2.5e-4, 1000


def split_by_game(data, held=0.1, seed=0):
    """판 단위로 떼어 낸다(같은 판의 경험이 학습과 점검으로 갈라지지 않게). (학습, 점검)."""
    games = np.unique(data['game'])
    test = np.random.default_rng(seed).choice(games, max(1, int(len(games) * held)), replace=False)
    sel = np.isin(data['game'], test)
    return {k: data[k][~sel] for k in KEYS}, {k: data[k][sel] for k in KEYS}


def agreement(net, data, w):
    """갈래별로 신경망의 가중합 선택이 정답과 같은 비율, 그리고 셋 다 같은 비율."""
    with torch.no_grad():
        q = net(torch.as_tensor(data['s'], dtype=torch.float32))
    plan = masked_argmax(combined(q, w), torch.as_tensor(data['m'], dtype=torch.bool)).numpy()
    same = plan == np.asarray(data['a'])
    return {'deck': float(same[:, 0].mean()), 'level': float(same[:, 1].mean()),
            'floor': float(same[:, 2].mean()), 'all': float(same.all(1).mean())}


def pretrain(train, w, steps, seed=0, log_every=2000, test=None):
    """train(KEYS별 배열)으로 데운 (신경망, 목표 신경망, 옵티마이저)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    demos = Replay.from_arrays(train)
    net, target = PlanNet(), PlanNet()
    target.load_state_dict(net.state_dict())
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    for step in range(1, steps + 1):
        learn_step(net, target, opt, w, demo=demos.sample(BATCH, rng))
        if step % SYNC == 0:
            target.load_state_dict(net.state_dict())
        if test is not None and step % log_every == 0:
            print(f'{step}걸음 떼어 둔 판 일치율 {agreement(net, test, w)}', flush=True)
    return net, target, opt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demos', default=os.path.join('checkpoints', 'plan_demos.npz'))
    ap.add_argument('--config', default='both')
    ap.add_argument('--aux-w', type=float, default=0.1)
    ap.add_argument('--steps', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    data = dict(np.load(args.demos))
    train, test = split_by_game(data, seed=args.seed)
    w = weights(args.config, args.aux_w)
    net, _, _ = pretrain(train, w, args.steps, args.seed, test=test)
    result = agreement(net, test, w)
    print(f'떼어 둔 판 일치율: {result}')
    out = args.out or os.path.join('checkpoints', f'plan_warm_{args.config}.pt')
    save(net, out, w, config=args.config, aux_w=args.aux_w, seed=args.seed, games=0, steps=args.steps,
         agree_deck=result['deck'], agree_level=result['level'], agree_floor=result['floor'], agree_all=result['all'])
    print(f'저장: {out}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: 통과 확인**

Run: `$PY -m hra.test_plan`
Expected: 열아홉 검사 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/pretrain.py hra/test_plan.py
git commit -m "hra: 계획 AI 데우기(따라 하기 여백 손실 + 값 학습, 판 단위로 떼어 일치율)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 진짜 자료로 한 번** (몇 분)

Run: `$PY -m hra.pretrain --config none --steps 20000`
Expected: 2천 걸음마다 떼어 둔 판 일치율이 찍히고 오른다. 마지막 줄 `저장: checkpoints/plan_warm_none.pt`. 덱 일치율은 대부분이 「그대로」라 높게(0.9 안팎), 남길 골드·레벨은 그보다 낮게 나올 수 있다. 숫자를 장부에 적는다(성공 기준 3의 첫 숫자는 Task 11에서 풀게임 상태로 다시 잰다).

---

### Task 9: 평가 도구

**Files:**
- Create: `hra/evaluate.py`
- Modify: `hra/test_plan_game.py` (검사 둘)

**Interfaces:**
- Consumes: `hra.plan_bot.safe_play`; `hra.plan_net.choose, load`; `hra.score_rank.ROOT`; `meta.decks_1024.trait_counts`; `meta.lobby.BOARDS, N_PLAYERS`; `meta.pit.average, chosen_of`; `meta.play_stats.family, family_table, real_families`; `meta.real_boards.spearman`
- Produces: `hra.evaluate.SIX`, `greedy_planner(path)`, `ab(path, games, jobs=None, pool=None, seed0=SEED_AB) -> {'diff', 'se', 'games', 'errors', 'pass', 'per_game'}`, `agree(path, games, jobs=None) -> {'deck', 'level', 'floor', 'all', 'decisions', 'deck_disagreements', 'errors'}`, `meta(path, games, jobs=None) -> {'families', 'rho_real', 'rho_sim', 'families_compared', 'switches', 'winner_level9', 'winner_five_two_star', 'errors'}`, CLI(ab/agree/meta)

- [ ] **Step 1: 실패하는 검사 쓰기** — `hra/test_plan_game.py`에 더한다.

```python
def ab_rule_against_rule_runs_test():
    """배관 검사 판짜기: 규칙 대 규칙 두 판. 판마다 등수 차는 -4~4이고 결과에 판정이 있다."""
    from hra.evaluate import ab
    res = ab(None, games=2, jobs=1)
    assert res['games'] == 2 and all(-4 <= d <= 4 for d in res['per_game']) and 'pass' in res


def agree_and_meta_run_with_a_fresh_net_test():
    """학습 안 한 신경망으로도 행동 일치율과 AI 메타가 끝까지 나온다(덱을 엉뚱하게 갈아타도 판이 돈다)."""
    import os
    import tempfile
    from hra.evaluate import agree, meta
    from hra.plan_net import PlanNet, save, weights
    path = os.path.join(tempfile.mkdtemp(), 'net.pt')
    save(PlanNet(), path, weights('both', 0.1), config='both', seed=0, games=0)
    a = agree(path, games=1, jobs=1)
    assert a['decisions'] > 0 and 0 <= a['all'] <= 1
    m = meta(path, games=1, jobs=1)
    assert m['families'] and abs(sum(share for _, share, _ in m['families']) - 1) < 1e-9
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan_game ab_rule_against_rule_runs_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.evaluate'`

- [ ] **Step 3: 구현** — `hra/evaluate.py`

```python
"""
계획 AI 평가(hra/plan_ai_design.md 6절).

ab   : AI 4자리 대 규칙 사람 봇 4자리(자리는 판마다 섞음). --net이 없으면 규칙 대 규칙(배관 검사). 등수 차는 규칙 자리 평균
       등수 - AI 자리 평균 등수라 양수면 AI가 낫다. 판정(신청서): 차 >= 0 이고 차 > 표준오차의 2배.
agree: 규칙 기록기 8명 판의 상태에서 AI가 고른 계획과 규칙의 계획이 같은 비율(갈래별, 셋 다). 어긋난 덱 짝을 센다.
meta : AI 8명 판의 계열별 몫·평균 등수. 롤체지지 10.24(실제)와, 사람 봇 덱 27개 고정 보드 대전(시뮬레이터 순서)과 순위
       상관을 여섯 큰 계열로 낸다. --net이 없으면 규칙 사람 봇 8명(비교 기준).

실행: python -m hra.evaluate ab --net checkpoints/plan_both_s1_best.pt --games 400 --jobs 7 --out results/plan_eval_ab_both_s1.json
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.plan_bot import safe_play
from hra.plan_net import choose, load
from hra.score_rank import ROOT
from meta.decks_1024 import trait_counts
from meta.lobby import BOARDS, N_PLAYERS
from meta.pit import average, chosen_of
from meta.play_stats import family, family_table, real_families
from meta.real_boards import spearman

SIX = ('warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter')  # 사람 봇 메타 비교와 같은 여섯 큰 계열
SEED_AB, SEED_AGREE, SEED_META = 700000, 710000, 720000
_cache = {}


def greedy_planner(path):
    """저장한 신경망 -> 탐험 없는 계획기. 일꾼마다 마지막 하나만 붙들어 둔다(긴 학습에서 기억이 쌓이지 않게)."""
    if path not in _cache:
        _cache.clear()
        net, w, _ = load(path)
        _cache[path] = lambda s, m: choose(net, s, m, w)
    return _cache[path]


def ab_game(job):
    """(시드, 신경망 경로 또는 None) -> (시드, 규칙 평균 등수 - AI 평균 등수 또는 None, 오류)."""
    seed, path = job
    ai = set(random.Random(seed).sample(range(N_PLAYERS), N_PLAYERS // 2))
    planner = greedy_planner(path) if path else 'rule'
    out, err = safe_play(seed, [planner if i in ai else 'rule' for i in range(N_PLAYERS)])
    if out is None:
        return seed, None, err
    places = [s['place'] for s in out['seats']]
    return seed, (statistics.mean(places[i] for i in range(N_PLAYERS) if i not in ai)
                  - statistics.mean(places[i] for i in ai)), None


def ab(path, games, jobs=None, pool=None, seed0=SEED_AB):
    """A/B 결과. pool을 주면 그 일꾼들을 쓴다(자기 대전의 중간 점검)."""
    jobs_list = [(seed0 + k, path) for k in range(games)]
    if pool is not None:
        rows = list(pool.imap_unordered(ab_game, jobs_list))
    else:
        with Pool(jobs) as p:
            rows = list(p.imap_unordered(ab_game, jobs_list))
    diffs = [d for _, d, _ in rows if d is not None]
    errors = [e for _, _, e in rows if e]
    if not diffs:
        return {'diff': float('nan'), 'se': float('nan'), 'games': 0, 'errors': errors, 'pass': False, 'per_game': []}
    diff = statistics.mean(diffs)
    se = statistics.stdev(diffs) / len(diffs) ** 0.5 if len(diffs) > 1 else float('nan')
    return {'diff': diff, 'se': se, 'games': len(diffs), 'errors': errors,
            'pass': bool(diff >= 0 and diff > 2 * se), 'per_game': diffs}


def agree_game(job):
    seed, path = job
    out, err = safe_play(seed, ['record'] * N_PLAYERS)
    if out is None:
        return [], err
    planner = greedy_planner(path)
    return [(tuple(int(i) for i in a), planner(s, m)) for seat in out['seats'] for s, m, a, *_ in seat['transitions']], None


def agree(path, games, jobs=None):
    with Pool(jobs) as p:
        results = p.map(agree_game, [(SEED_AGREE + k, path) for k in range(games)])
    pairs = [row for rows, _ in results for row in rows]
    same = np.array([[x == y for x, y in zip(rule, ai)] for rule, ai in pairs])
    name = lambda d: 'keep' if d == 0 else BOARDS[d - 1]['name']
    wrong = Counter((rule[0], ai[0]) for rule, ai in pairs if rule[0] != ai[0])
    return {'deck': float(same[:, 0].mean()), 'level': float(same[:, 1].mean()), 'floor': float(same[:, 2].mean()),
            'all': float(same.all(1).mean()), 'decisions': len(pairs),
            'deck_disagreements': [[name(a), name(b), n] for (a, b), n in wrong.most_common(10)],
            'errors': [e for _, e in results if e]}


def meta_game(job):
    seed, path = job
    planner = greedy_planner(path) if path else 'rule'
    out, err = safe_play(seed, [planner] * N_PLAYERS)
    if out is None:
        return [], err
    return [{'place': s['place'], 'board': s['board'], 'deck': s['deck'], 'switches': s['switches']}
            for s in out['seats']], None


def deck_family(board):
    """사람 봇 덱의 계열(완성 보드의 특성으로, meta/play_stats.family)."""
    return family(trait_counts(board['units'], board['items'], (chosen_of(board) or (None, None))[1]))[0]


def sim_order():
    """시뮬레이터 순서: 계열마다 그 계열 덱들의 고정 보드 대전 평균 승률(results/pit_1024.json의 human)."""
    win = average(json.load(open(os.path.join(ROOT, 'results', 'pit_1024.json'), encoding='utf-8'))['human'])
    rows = defaultdict(list)
    for b in BOARDS:
        rows[deck_family(b)].append(win[b['name']])
    return {f: statistics.mean(v) for f, v in rows.items()}


def meta(path, games, jobs=None):
    with Pool(jobs) as p:
        results = p.map(meta_game, [(SEED_META + k, path) for k in range(games)])
    players = [row for rows, _ in results for row in rows]
    table = family_table(players)  # (계열, 몫, 평균 등수)
    mine = {f: place for f, _, place in table}
    real = {f: place for f, _, place in real_families()}
    sim = sim_order()
    common = [f for f in SIX if f in mine and f in real]
    common_sim = [f for f in SIX if f in mine and f in sim]
    winners = [p['board'] for p in players if p['place'] == 1]
    fives = [u for b in winners for u in b['units'] if u[1] == 5]
    return {'families': [[f, share, place] for f, share, place in table],
            'rho_real': spearman([-mine[f] for f in common], [-real[f] for f in common]) if len(common) > 2 else None,
            'rho_sim': spearman([-mine[f] for f in common_sim], [sim[f] for f in common_sim]) if len(common_sim) > 2 else None,
            'families_compared': common, 'switches': statistics.mean(p['switches'] for p in players),
            'winner_level9': sum(b['level'] >= 9 for b in winners) / len(winners) if winners else None,
            'winner_five_two_star': sum(u[2] >= 2 for u in fives) / len(fives) if fives else None,
            'errors': [e for _, e in results if e]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['ab', 'agree', 'meta'])
    ap.add_argument('--net', default=None, help='저장한 신경망. 없으면 규칙 사람 봇(ab는 규칙 대 규칙)')
    ap.add_argument('--games', type=int, default=400)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    if args.kind == 'agree' and not args.net:
        ap.error('agree에는 --net이 필요하다')
    run = {'ab': ab, 'agree': agree, 'meta': meta}[args.kind]
    result = run(args.net, args.games, args.jobs)
    shown = {k: v for k, v in result.items() if k != 'per_game'}
    print(json.dumps(shown, ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'kind': args.kind, 'net': args.net and os.path.basename(args.net), 'games': args.games, **result},
                      f, ensure_ascii=False, indent=1)
        print(f'저장: {args.out}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: 통과 확인** (판 넷, 2분쯤)

Run: `$PY -m hra.test_plan_game ab_rule_against_rule_runs_test agree_and_meta_run_with_a_fresh_net_test`
Expected: 둘 다 PASS

- [ ] **Step 5: 커밋**

```bash
git add hra/evaluate.py hra/test_plan_game.py
git commit -m "hra: 계획 AI 평가 도구(A/B, 행동 일치율, AI 메타 대 실제·시뮬레이터 순서)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 자기 대전 학습

**Files:**
- Create: `hra/selfplay.py`
- Modify: `hra/test_plan.py` (검사 둘), `hra/test_plan_game.py` (검사 하나)

**Interfaces:**
- Consumes: `hra.evaluate.ab`; `hra.plan_bot.safe_play`; `hra.plan_learn.KEYS, Replay, learn_step`; `hra.plan_net.PlanNet, choose, flip_rate, load, save, weights`; `meta.lobby.N_PLAYERS`
- Produces: `hra.selfplay.eps_at(done, total) -> tuple`, `is_better(new, best) -> bool`, `selfplay_game(job) -> (list[경험], dict | None, str | None)`, `train(config, aux_w, seed, games, jobs, save_every=500, eval_games=100, warm=None, demos=None, root='.', tag=None) -> {'games', 'best'}`. 파일: `<root>/checkpoints/<이름>.pt`(이어 하기용 전체 상태), `<이름>_latest.pt`·`<이름>_best.pt`(평가용 신경망), `<이름>_policy_v<번호>.pt`(일꾼용, 마지막 5개만 남김), `<root>/results/<이름>.json`(곡선). 이름은 tag 또는 `plan_<설정>_s<시드>`.

- [ ] **Step 1: 실패하는 검사 쓰기**

`hra/test_plan.py`에 더한다.

```python
def eps_shrinks_per_branch_test():
    """탐험 몫은 덱 3%→1%, 레벨·남길 골드 15%→5%로 학습 판 수에 따라 곧게 준다."""
    from hra.selfplay import eps_at
    assert np.allclose(eps_at(0, 100), (0.03, 0.15, 0.15))
    assert np.allclose(eps_at(50, 100), (0.02, 0.10, 0.10))
    assert np.allclose(eps_at(200, 100), (0.01, 0.05, 0.05))


def best_checkpoint_only_moves_up_test():
    """최고 저장본은 처음이거나 더 나은 점검 결과로만 바뀐다. 점검이 모두 실패해 값이 없으면(nan) 안 바뀐다."""
    from hra.selfplay import is_better
    assert is_better(0.1, None) and is_better(0.3, 0.2)
    assert not is_better(0.1, 0.2) and not is_better(float('nan'), 0.2) and not is_better(float('nan'), None)
```

`hra/test_plan_game.py`에 더한다.

```python
def selfplay_runs_saves_and_resumes_test():
    """아주 작은 자기 대전: 2판 학습, 2판마다 저장과 점검(점검 1판). 같은 설정으로 3판까지 다시 부르면 이어서 1판만 더 돌고
    곡선이 한 줄 는다(컴퓨터가 꺼진 뒤 같은 명령으로 이어 가기)."""
    import json
    import os
    import tempfile
    from hra.selfplay import train
    root = tempfile.mkdtemp()
    first = train('both', 0.1, seed=5, games=2, jobs=1, save_every=2, eval_games=1, root=root)
    log = json.load(open(os.path.join(root, 'results', 'plan_both_s5.json'), encoding='utf-8'))
    assert first['games'] == 2 and [c['games'] for c in log['curve']] == [2]
    second = train('both', 0.1, seed=5, games=3, jobs=1, save_every=2, eval_games=1, root=root)
    log = json.load(open(os.path.join(root, 'results', 'plan_both_s5.json'), encoding='utf-8'))
    assert second['games'] == 3 and [c['games'] for c in log['curve']] == [2, 3]
    assert os.path.exists(os.path.join(root, 'checkpoints', 'plan_both_s5_best.pt'))
```

- [ ] **Step 2: 실패 확인**

Run: `$PY -m hra.test_plan eps_shrinks_per_branch_test`
Expected: FAIL — `ModuleNotFoundError: No module named 'hra.selfplay'`

- [ ] **Step 3: 구현** — `hra/selfplay.py`

```python
"""
자기 대전 학습(hra/plan_ai_design.md 5절). 일꾼들이 8자리 모두 최신 신경망으로 판을 돌리고, 본체가 경험 더미에서 배운다.
따라 하기 자료를 더미 옆에 두고 값 손실과 여백 손실을 계속 건다(데운 신경망이 자기 대전 초반에 무너지지 않게).
save_every판마다 저장하고 AI 4 대 규칙 4 점검(중간 점검)을 한다. 같은 명령을 다시 돌리면 마지막 저장에서 이어 간다.

실행: python -m hra.selfplay --config both --aux-w 0.1 --seed 1 --games 10000 --jobs 6
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
import time
from collections import deque
from multiprocessing import Pool

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.evaluate import ab
from hra.plan_bot import safe_play
from hra.plan_learn import KEYS, Replay, learn_step
from hra.plan_net import PlanNet, choose, flip_rate, load, save, weights
from meta.lobby import N_PLAYERS

BATCH, DEMO_BATCH, LR, SYNC, UPDATES_PER_GAME, CAPACITY = 256, 64, 2.5e-4, 1000, 8, 500_000
EPS_START, EPS_END = (0.03, 0.15, 0.15), (0.01, 0.05, 0.05)  # 덱, 레벨, 남길 골드(설계 5절)
PUBLISH_EVERY, KEEP_POLICIES = 25, 5  # 이 판 수마다 일꾼용 신경망을 새 파일로 쓰고, 마지막 몇 개만 남긴다
SEED_SELFPLAY, SEED_CHECK = 100000, 800000
_worker = {'path': None, 'net': None, 'w': None}


def eps_at(done, total):
    """학습한 판 수에 따른 갈래별 탐험 몫(시작에서 끝으로 곧게)."""
    t = min(done / max(total, 1), 1.0)
    return tuple(a + (b - a) * t for a, b in zip(EPS_START, EPS_END))


def is_better(new, best):
    """중간 점검 등수 차가 지금까지의 최고보다 나은가. 처음이면 그렇다. 값이 없으면(nan) 아니다."""
    return new == new and (best is None or new > best)


def selfplay_game(job):
    """(시드, 일꾼용 신경망 경로, 탐험 몫) -> (경험 목록, 판 요약, 오류). 일꾼은 경로가 바뀔 때만 신경망을 다시 읽는다."""
    seed, path, eps = job
    if _worker['path'] != path:
        torch.set_num_threads(1)
        _worker['net'], _worker['w'], _ = load(path)
        _worker['path'] = path
    rng = random.Random(seed)
    planner = lambda s, m: choose(_worker['net'], s, m, _worker['w'], eps, rng)
    out, err = safe_play(seed, [planner] * N_PLAYERS)
    if out is None:
        return [], None, err
    summary = {'switches': [s['switches'] for s in out['seats']], 'decks': [s['deck'] for s in out['seats']]}
    return [t for s in out['seats'] for t in s['transitions']], summary, None


def train(config, aux_w, seed, games, jobs, save_every=500, eval_games=100, warm=None, demos=None, root='.', tag=None):
    """자기 대전 학습. games는 이 이름으로 끝낼 총 판 수다(이어 하기면 남은 만큼만 돈다)."""
    name = tag or f'plan_{config}_s{seed}'
    ck_dir, res_dir = os.path.join(root, 'checkpoints'), os.path.join(root, 'results')
    os.makedirs(ck_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)
    ck_path, log_path = os.path.join(ck_dir, f'{name}.pt'), os.path.join(res_dir, f'{name}.json')
    latest, best_path = os.path.join(ck_dir, f'{name}_latest.pt'), os.path.join(ck_dir, f'{name}_best.pt')
    w = weights(config, aux_w)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    rng = np.random.default_rng(seed)
    net, target = PlanNet(), PlanNet()
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    done, best, updates, curve = 0, None, 0, []
    if os.path.exists(ck_path):  # 이어 하기
        ck = torch.load(ck_path, map_location='cpu', weights_only=True)
        net.load_state_dict(ck['net'])
        target.load_state_dict(ck['target'])
        opt.load_state_dict(ck['opt'])
        done, best, updates = ck['games'], ck['best'], ck['updates']
        if os.path.exists(log_path):
            curve = json.load(open(log_path, encoding='utf-8'))['curve']
    else:
        if warm:
            net.load_state_dict(load(warm)[0].state_dict())
        target.load_state_dict(net.state_dict())
    demo_replay = None
    if demos:
        arrays = np.load(demos)
        demo_replay = Replay.from_arrays({k: arrays[k] for k in KEYS})
    replay, version = Replay(CAPACITY), 0

    def publish():
        nonlocal version
        version += 1
        path = os.path.join(ck_dir, f'{name}_policy_v{done}_{version}.pt')
        save(net, path, w, config=config, aux_w=aux_w, seed=seed, games=done)
        for old in sorted(glob.glob(os.path.join(ck_dir, f'{name}_policy_v*.pt')), key=os.path.getmtime)[:-KEEP_POLICIES]:
            os.remove(old)
        return path

    policy = publish()
    with Pool(jobs) as pool:
        while done < games:
            chunk, start, losses, switches, errors = min(save_every, games - done), time.time(), [], [], 0
            submitted, finished, inflight = 0, 0, deque()
            while finished < chunk:
                while len(inflight) < 2 * jobs and submitted < chunk:
                    k = done + submitted
                    inflight.append(pool.apply_async(
                        selfplay_game, ((SEED_SELFPLAY + seed * 1_000_000 + k, policy, eps_at(k, games)),)))
                    submitted += 1
                try:
                    transitions, summary, err = inflight.popleft().get()
                except Exception as e:  # 일꾼 쪽 예외(신경망 파일 읽기 등)도 그 판만 버린다
                    transitions, summary, err = [], None, f'{type(e).__name__}: {e}'
                finished += 1
                errors += err is not None
                if summary:
                    switches += summary['switches']
                for t in transitions:
                    replay.add(t)
                if len(replay) >= BATCH:
                    for _ in range(UPDATES_PER_GAME):
                        demo = demo_replay.sample(DEMO_BATCH, rng) if demo_replay is not None else None
                        losses.append(learn_step(net, target, opt, w, batch=replay.sample(BATCH, rng), demo=demo))
                        updates += 1
                        if updates % SYNC == 0:
                            target.load_state_dict(net.state_dict())
                if finished % PUBLISH_EVERY == 0:
                    policy = publish()
            done += chunk
            save(net, latest, w, config=config, aux_w=aux_w, seed=seed, games=done)
            check = ab(latest, eval_games, pool=pool, seed0=SEED_CHECK)
            idx = rng.integers(0, len(replay), min(2000, len(replay))) if len(replay) else []
            flips = flip_rate(net, replay.s[idx], replay.m[idx], w) if len(replay) else 0.0
            if is_better(check['diff'], best):
                best = check['diff']
                save(net, best_path, w, config=config, aux_w=aux_w, seed=seed, games=done, diff=best)
            curve.append({'games': done, 'diff': check['diff'], 'se': check['se'], 'check_errors': len(check['errors']),
                          'flip': flips, 'switches': statistics.mean(switches) if switches else None,
                          'loss': statistics.mean(losses) if losses else None, 'errors': errors,
                          'minutes': (time.time() - start) / 60})
            tmp = ck_path + '.tmp'
            torch.save({'net': net.state_dict(), 'target': target.state_dict(), 'opt': opt.state_dict(),
                        'games': done, 'best': best, 'updates': updates}, tmp)
            os.replace(tmp, ck_path)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump({'config': config, 'aux_w': aux_w, 'seed': seed, 'curve': curve}, f, ensure_ascii=False, indent=1)
            print(f'{done}판: 점검 등수 차 {check["diff"]:+.2f}±{check["se"]:.2f}, 뒤집는 비율 {flips:.2f}, '
                  f'갈아타기 {curve[-1]["switches"]}, 멈춘 판 {errors}', flush=True)
            policy = publish()
    return {'games': done, 'best': best}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='both', choices=['none', 'synergy', 'units', 'both'])
    ap.add_argument('--aux-w', type=float, default=0.1)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--games', type=int, default=10000)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--save-every', type=int, default=500)
    ap.add_argument('--eval-games', type=int, default=100)
    ap.add_argument('--warm', default=None, help='없으면 checkpoints/plan_warm_<설정>.pt가 있을 때 그것')
    ap.add_argument('--demos', default=os.path.join('checkpoints', 'plan_demos.npz'))
    ap.add_argument('--tag', default=None)
    args = ap.parse_args()
    warm = args.warm or os.path.join('checkpoints', f'plan_warm_{args.config}.pt')
    result = train(args.config, args.aux_w, args.seed, args.games, args.jobs, args.save_every, args.eval_games,
                   warm if os.path.exists(warm) else None, args.demos if os.path.exists(args.demos) else None,
                   tag=args.tag)
    print(result)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: 빠른 검사 통과**

Run: `$PY -m hra.test_plan`
Expected: 스물한 검사 모두 PASS

- [ ] **Step 5: 느린 검사 통과** (판 다섯쯤, 2~3분)

Run: `$PY -m hra.test_plan_game selfplay_runs_saves_and_resumes_test`
Expected: PASS

- [ ] **Step 6: 느린 검사 전부와 기존 묶음**

Run: `$PY -m hra.test_plan_game` 그리고 `$PY -m meta.test_human_bot`, `$PY -m meta.test_lobby`, `$PY -m meta.test_real_boards`
Expected: 모두 PASS

- [ ] **Step 7: 커밋**

```bash
git add hra/selfplay.py hra/test_plan.py hra/test_plan_game.py
git commit -m "hra: 계획 AI 자기 대전 학습(일꾼 6, 따라 하기 여백 손실 유지, 저장·중간 점검·이어 하기)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: 배관 검사 둘과 보조 가중치 사전 시험

긴 실행은 충전기를 꽂고 뒤에서 돌린다. 각 단계의 숫자를 장부에 적는다.

**Files:**
- Create: `results/plan_eval_ab_rule_vs_rule.json`, `results/plan_eval_ab_warm_none.json`, `results/plan_eval_agree_warm_none.json`, `results/plan_pre_w0.1.json`, `results/plan_pre_w0.3.json`
- Modify: `results/README.md` (새 절), `hra/plan_ai_design.md` (4절에 고른 w 한 줄)

- [ ] **Step 1: 배관 검사 1 — 규칙 대 규칙** (16분쯤)

Run: `$PY -m hra.evaluate ab --games 400 --jobs 7 --out results/plan_eval_ab_rule_vs_rule.json`
Expected: `|diff| <= 2 × se`(자리 치우침 없음). 넘으면 ab_game의 자리 고르기와 시드를 먼저 확인하고, 원인을 장부에 적는다.

- [ ] **Step 2: 데우기 셋** (각 몇 분)

Run:
- `$PY -m hra.pretrain --config both --aux-w 0.1 --out checkpoints/plan_warm_both_w0.1.pt`
- `$PY -m hra.pretrain --config both --aux-w 0.3 --out checkpoints/plan_warm_both_w0.3.pt`
- (Task 8에서 만든 `checkpoints/plan_warm_none.pt`를 그대로 쓴다)
Expected: 저장 줄과 떼어 둔 판 일치율.

- [ ] **Step 3: 배관 검사 2 — 데우기만 한 AI 대 규칙, 행동 일치율 첫 숫자** (25분쯤)

Run:
- `$PY -m hra.evaluate ab --net checkpoints/plan_warm_none.pt --games 400 --jobs 7 --out results/plan_eval_ab_warm_none.json`
- `$PY -m hra.evaluate agree --net checkpoints/plan_warm_none.pt --games 50 --jobs 7 --out results/plan_eval_agree_warm_none.json`
Expected: 등수 차가 0 근처(|diff| < 0.3). 크게 음수면 연결(상태 함수, 계획 풀이, 실행기)을 의심하고 agree의 어긋난 덱 짝부터 본다. 일치율은 성공 기준 3의 데운 직후 숫자다.

- [ ] **Step 4: 보조 가중치 사전 시험** (각 2천 판, 1.5~2시간씩)

Run:
- `$PY -m hra.selfplay --config both --aux-w 0.1 --seed 1 --games 2000 --warm checkpoints/plan_warm_both_w0.1.pt --tag plan_pre_w0.1`
- `$PY -m hra.selfplay --config both --aux-w 0.3 --seed 1 --games 2000 --warm checkpoints/plan_warm_both_w0.3.pt --tag plan_pre_w0.3`
Expected: 500판마다 점검 줄이 찍히고 results/plan_pre_w0.1.json, results/plan_pre_w0.3.json이 생긴다.

- [ ] **Step 5: w 고르기** — 두 실행의 마지막 점검 줄의 뒤집는 비율(flip)을 견준다. 고르는 규칙: 뒤집는 비율이 20%에 더 가까운 쪽(보조 갈래가 판단에 닿되 중심 갈래를 덮지 않는 정도). 둘의 뒤집는 비율 차가 5%p 안이면 중간 점검 등수 차가 더 높은 쪽, 그것도 표준오차 안이면 0.1(덜 끼어드는 쪽). 장부에 `Task 11: Ruling: 보조 가중치 w = <값> — <두 비율과 등수 차> — 틀리면 본 학습의 보조 갈래 효과를 과소·과대 평가한다`를 적고, 설계 문서 4절의 「보조 가중치 w는 본 실험 전에 정한다」 줄 끝에 고른 값과 날짜를 덧붙인다.

- [ ] **Step 6: 문서** — `results/README.md`에 「계획 AI 배관 검사와 보조 가중치 사전 시험 (날짜)」 절: 명령, 파일, 규칙 대 규칙 A/B, 데운 직후 A/B와 일치율(갈래별, 셋 다, 어긋난 덱 짝 다섯), 사전 시험 두 곡선 표(판 수, 점검 등수 차, 뒤집는 비율, 갈아타기), 고른 w와 까닭.

- [ ] **Step 7: 커밋**

```bash
git add results/plan_eval_ab_rule_vs_rule.json results/plan_eval_ab_warm_none.json results/plan_eval_agree_warm_none.json results/plan_pre_w0.1.json results/plan_pre_w0.3.json results/README.md hra/plan_ai_design.md
git commit -m "results: 계획 AI 배관 검사 둘과 보조 가중치 사전 시험" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: 본 학습과 평가

「둘 다 끔」과 「둘 다 켬」 시드 3개씩, 학습 한 번 1만 판(8시간쯤). 아래에서 `W`는 Task 11에서 고른 보조 가중치다. 실행이 끊기면 같은 명령을 다시 돌린다(이어 하기).

**Files:**
- Create: `results/plan_none_s{1,2,3}.json`, `results/plan_both_s{1,2,3}.json`(곡선), `results/plan_eval_{ab,meta,agree}_{none,both}_s{1,2,3}.json`, `results/plan_eval_meta_rule.json`
- Modify: `results/README.md` (새 절), `meta/set4_play.md` (6절 끝에 한 줄)

- [ ] **Step 1: 데우기 둘**

Run:
- `$PY -m hra.pretrain --config none --aux-w W --out checkpoints/plan_warm_none.pt`
- `$PY -m hra.pretrain --config both --aux-w W --out checkpoints/plan_warm_both.pt`
Expected: 저장 줄.

- [ ] **Step 2: 학습 여섯** (차례로, 기계로 이틀쯤)

Run (설정 c ∈ {none, both}, 시드 s ∈ {1, 2, 3}):
`$PY -m hra.selfplay --config c --aux-w W --seed s --games 10000`
Expected: 실행마다 results/plan_<c>_s<s>.json 곡선과 checkpoints/plan_<c>_s<s>_best.pt. 멈춘 판(errors)이 판의 1%를 넘으면 그 오류를 모아 유저에게 알린다.

- [ ] **Step 3: 평가** (실행마다 A/B 400판, 메타 400판, 일치율 50판 — 실행 하나에 40분쯤)

Run (각 실행의 최고 저장본으로):
- `$PY -m hra.evaluate ab --net checkpoints/plan_<c>_s<s>_best.pt --games 400 --out results/plan_eval_ab_<c>_s<s>.json`
- `$PY -m hra.evaluate meta --net checkpoints/plan_<c>_s<s>_best.pt --games 400 --out results/plan_eval_meta_<c>_s<s>.json`
- `$PY -m hra.evaluate agree --net checkpoints/plan_<c>_s<s>_best.pt --games 50 --out results/plan_eval_agree_<c>_s<s>.json`
그리고 비교 기준 한 번: `$PY -m hra.evaluate meta --games 400 --out results/plan_eval_meta_rule.json`
Expected: 파일 열아홉.

- [ ] **Step 4: 정리** — `results/README.md`에 「계획 AI 본 학습 (날짜)」 절을 쓴다.
  - 학습 곡선 표: 설정마다 시드 3개의 500판 점검 등수 차 평균과 흔들림.
  - 성공 기준 2: 실행마다 A/B 등수 차 ± 표준오차와 판정, 설정별 평균.
  - 성공 기준 3: 데운 직후(Task 11)와 학습 뒤의 갈래별 일치율, 어긋난 덱 짝.
  - AI 메타: 계열별 몫과 평균 등수(설정별), rho_real과 rho_sim, 규칙 사람 봇 기준(plan_eval_meta_rule)과 비교, 황혼의 자리, 1등 레벨 9 비율, 1등 5코스트 2성 비율(실제 76%, 69%).
  - 보조 갈래의 답: 두 설정의 학습 속도·A/B·메타 상관 차가 시드 흔들림보다 큰지.
  - 설계 1절 「답할 수 없는 것」대로, AI 메타가 실제와 다를 때 rho_sim으로 학습기 몫과 시뮬레이터 몫을 가른다.
  `meta/set4_play.md` 6절 끝에 한 줄로 연결한다.

- [ ] **Step 5: 커밋과 올리기** — 푸시 전에 바뀐 내용에서 개인 정보와 이 컴퓨터의 경로를 훑는다.

```bash
git add results/plan_*.json results/README.md meta/set4_play.md
git commit -m "results: 계획 AI 본 학습 — 둘 다 끔·둘 다 켬 시드 3개씩, A/B·행동 일치율·AI 메타" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin curt-2
```

---

### Task 13: (시간이 남으면) 시너지만·유닛 수만

Task 12와 같은 명령을 설정 c ∈ {synergy, units}, 시드 s ∈ {1, 2, 3}으로 돌린다(데우기는 `--config synergy`, `--config units`로 한 번씩). 결과를 Task 12 절의 표에 열로 더하고, 같은 방식으로 커밋한다. 12월 첫 주까지 끝나지 않으면 하지 않고, 하지 않은 까닭을 README에 한 줄 적는다.
