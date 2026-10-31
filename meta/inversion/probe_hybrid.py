"""「AI 덱 + 규칙 레벨·골드」 탐침(2026-10-31, 진행 보상 실험 다음): probe_heads.py와 같은 판(hra.evaluate ab와 같은 시드·자리 뽑기)을
돌리되 AI 자리의 레벨·리롤 결정(macro)만 규칙 사람 봇 것으로 바꾼다. 덱 고르기와 갈아타기는 계획 AI가 한다. 본래 탐침과의 A/B 차가
계획 AI의 레벨·남길 골드 몫이다(계획 틀이 규칙보다 거친 몫, 예를 들어 5단계 레벨 8의 경험치 우선이 없는 것도 섞인다). 이 탐침의 AI
자리 「계획 갈래」 표는 실행되지 않은 계획이라 읽지 않는다.

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_hybrid.py --net checkpoints/plan_dense_both_s1_latest.pt --label hybrid_plan_dense_both_s1_latest --games 400 --jobs 2 --out meta/inversion/probe_rows_hybrid_plan_dense_both_s1_latest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hra.plan_bot import PlanPolicy
from meta.human_bot import HumanPolicy

PlanPolicy.macro = HumanPolicy.macro  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다
import probe_heads

if __name__ == '__main__':
    probe_heads.main()
