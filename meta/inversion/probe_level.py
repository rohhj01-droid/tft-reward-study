"""「AI 덱·AI 남길 골드 + 계획 칸에 가둔 규칙 레벨」 탐침(2026-11-10, 학습 몫 가르기): probe_frame.py(틀 탐침)와 같은 판(같은
시드·같은 자리 뽑기)을 돌리되, AI 자리의 레벨만 틀 탐침과 같은 식으로 규칙의 목표를 계획 칸에 넣어 그 라운드 첫 판단을 지키고, 남길
골드는 계획기가 라운드 시작에 고른 값을 쓴다(계획 AI처럼 경험치 우선 없이 실행). 덱 고르기와 갈아타기는 계획 AI가 한다.
레벨 몫 = 본래 탐침 − 이 탐침, 남길 골드 몫 = 이 탐침 − 틀 탐침이고, 둘의 합이 학습 몫(본래 − 틀)이다(results/README 「학습 몫
가르기」). AI 자리 「계획 갈래」 표의 레벨 단계는 실행되지 않은 신경망 계획이다(남길 골드는 실행된 값).

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_level.py --net checkpoints/plan_dense_both_s2_latest.pt --label level_plan_dense_both_s2_latest --games 400 --jobs 2 --out meta/inversion/probe_rows_level_plan_dense_both_s2_latest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hra.plan_bot import PlanPolicy
from meta.human_bot import HumanPolicy
from meta.human_macro import action
from probe_frame import frame_plan  # 읽히면 PlanPolicy.macro를 틀 탐침 것으로 바꾸지만, 아래에서 다시 바꾼다


def level_macro(self, player, game_round):
    if self.target is None:  # 2-1 전(1단계)은 규칙 그대로
        return HumanPolicy.macro(self, player, game_round)
    if getattr(self, 'held_round', None) != game_round:
        self.held_round = game_round
        self.held = frame_plan(player.level, player.gold, *self.macro_plan(player, game_round))[0]
    return action(player.gold, player.level, self.held, self.floor, False)


PlanPolicy.macro = level_macro  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다
import probe_heads  # noqa: E402

if __name__ == '__main__':
    probe_heads.main()
