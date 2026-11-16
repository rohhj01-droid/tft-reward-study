"""「여덟 자리 모두 규칙」 대조 탐침(2026-11-16, 돈 쓰는 때까지 가르친 AI 판정의 대조 실행): probe_heads.py와 같은 판(같은 시드·같은
자리 뽑기)을 돌리되 AI 자리에도 규칙 사람 봇(기록기)을 앉힌다. 기록의 'ai' 자리는 「AI가 앉았을 자리의 규칙 봇」이다. 이 판들의
「규칙 평균 등수 − 'ai' 자리 평균 등수」는 자리 뽑기와 판 운만으로 생기는 차이고, 본래 탐침의 A/B에서 판마다 뺀다(results/README
「돈 쓰는 때까지 가르친 AI」). --net은 probe_heads.main이 가중치를 읽어 기록 머리에 적는 데만 쓰이고 판에는 쓰이지 않는다.

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_rule.py --net checkpoints/plan_warm_both_era.pt --label rule8 --games 400 --jobs 2 --out meta/inversion/probe_rows_rule8.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_heads  # noqa: E402


def rule_planner(path, overrides):
    """AI 자리에도 규칙 기록기를 앉힌다(신경망은 읽지 않는다)."""
    return 'record'


probe_heads.planner_for = rule_planner  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다

if __name__ == '__main__':
    probe_heads.main()
