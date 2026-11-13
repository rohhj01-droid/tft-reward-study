"""「4-1 전에만 계획 칸에 가둔 규칙 레벨」 탐침(2026-11-13, 레벨 손해 단계 가르기 (마)): probe_level.py(레벨만 탐침)와 같은 판(같은
시드·같은 자리 뽑기)을 돌리되, 레벨을 규칙으로 바꾸는 때를 2·3단계(4-1 전)로 줄인다. 4-1부터는 본래 탐침처럼 계획기가 라운드 시작에
고른 목표 레벨과 남길 골드를 쓴다. 남길 골드는 내내 계획기의 값이다. 덱 고르기와 갈아타기는 계획 AI가 한다.
2·3단계 레벨 몫 = 본래 탐침 − 이 탐침, 4단계부터 레벨 몫 = 이 탐침 − 레벨만 탐침이고, 둘의 합이 레벨 몫(본래 − 레벨만)이다(results/README
「학습 몫 가르기 반대 순서와 레벨 손해 단계 가르기」).

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_early.py --net checkpoints/plan_dense_both_s2_latest.pt --label early_plan_dense_both_s2_latest --games 400 --jobs 2 --out meta/inversion/probe_rows_early_plan_dense_both_s2_latest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hra.plan_bot import PlanPolicy
from meta.human_macro import action
from probe_level import level_macro  # 읽히면 PlanPolicy.macro를 레벨만 탐침 것으로 바꾸지만, 아래에서 다시 바꾼다

LATE_ROUND = 15  # 4-1(2-1이 3, 5-1이 21)


def early_macro(self, player, game_round):
    if game_round >= LATE_ROUND:  # 4-1부터는 본래 탐침(PlanPolicy.macro)과 같다
        return action(player.gold, player.level, self.target, self.floor, False)
    return level_macro(self, player, game_round)


PlanPolicy.macro = early_macro  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다
import probe_heads  # noqa: E402

if __name__ == '__main__':
    probe_heads.main()
