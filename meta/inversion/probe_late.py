"""「4-1부터만 계획 칸에 가둔 규칙 레벨·골드」 탐침(2026-11-16, 기초의 남은 학습 몫 단계 가르기): probe_frame.py(틀 탐침)와 같은
판(같은 시드·같은 자리 뽑기)을 돌리되, 레벨·남길 골드를 규칙으로 바꾸는 때를 4-1부터로 줄인다. 4-1 전(2·3단계)에는 본래 탐침처럼
계획기가 라운드 시작에 고른 목표 레벨과 남길 골드를 쓴다. 덱 고르기와 갈아타기는 계획 AI가 한다.
4-1부터의 몫 = 본래 탐침 − 이 탐침, 4-1 전 몫 = 이 탐침 − 틀 탐침이고, 둘의 합이 학습 몫(본래 − 틀)이다(results/README 「기초의 남은
학습 몫 단계 가르기」). AI 자리 「계획 갈래」 표는 4-1부터 실행되지 않은 신경망 계획이라 읽지 않는다.

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_late.py --net checkpoints/plan_dense_basics_s2_latest.pt --label late_plan_dense_basics_s2_latest --games 400 --jobs 2 --out meta/inversion/probe_rows_late_plan_dense_basics_s2_latest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hra.plan_bot import PlanPolicy
from meta.human_macro import action
from probe_frame import frame_macro  # 읽히면 PlanPolicy.macro를 틀 탐침 것으로 바꾸지만, 아래에서 다시 바꾼다

LATE_ROUND = 15  # 4-1(2-1이 3, 5-1이 21)


def late_macro(self, player, game_round):
    if game_round < LATE_ROUND and self.target is not None:  # 2-1부터 4-1 전까지는 본래 탐침(PlanPolicy.macro)과 같다
        return action(player.gold, player.level, self.target, self.floor, False)
    return frame_macro(self, player, game_round)  # 2-1 전(1단계)은 규칙 그대로, 4-1부터는 틀 탐침


PlanPolicy.macro = late_macro  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다
import probe_heads  # noqa: E402

if __name__ == '__main__':
    probe_heads.main()
