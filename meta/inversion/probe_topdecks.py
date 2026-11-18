"""좋은 덱만 고르는 규칙 봇 기준선 탐침(2026-11-18, results/README 「가르친 AI와 좋은 덱만 고르는 규칙 봇 견주기」): probe_heads.py와 같은
판(같은 시드·같은 자리 뽑기)을 돌리되 AI 자리에 덱 후보를 줄인 규칙 봇(hra.deck_baseline.topdecks)을 앉힌다. 덱 후보는 같은 환경에서 잰
덱별 위험 표의 상위 셋이다. 기록의 'ai' 자리가 기준선 자리이고, 기록기가 아니라서 라운드 기록(curve)은 비어 있다. --net은
probe_heads.main이 가중치를 읽어 기록 머리에 적는 데만 쓰이고 판에는 쓰이지 않는다.

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH, 위험 표를 먼저 만든다):
    python meta/inversion/probe_topdecks.py --net checkpoints/plan_warm_both_teach.pt --label topdecks_teach --games 400 --jobs 4 --out meta/inversion/probe_rows_topdecks_teach.json
"""
import functools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_heads  # noqa: E402
from hra.deck_baseline import topdecks  # noqa: E402

RISK = 'results/deck_risk_rule_teach.json'  # hra.deck_baseline risk의 결과


@functools.lru_cache
def top3(path):
    with open(path, encoding='utf-8') as f:
        return tuple(json.load(f)['top3'])


def top_planner(path, overrides):
    """AI 자리에 덱 후보를 위험 표의 상위 셋으로 줄인 규칙 봇을 앉힌다(신경망은 읽지 않는다)."""
    return topdecks(top3(RISK))


probe_heads.planner_for = top_planner  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다

if __name__ == '__main__':
    probe_heads.main()
