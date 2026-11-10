"""「AI 덱 + 계획 칸에 가둔 규칙 레벨·골드」 탐침(2026-11-10, 계획 틀 몫 재기): probe_hybrid.py와 같은 판(같은 시드·같은 자리 뽑기)을
돌리되, AI 자리의 레벨·리롤을 규칙 그대로 두지 않고 계획 틀에 가둔다. 2-1부터 라운드마다 첫 레벨·리롤 판단 때 규칙이 셈한 (목표 레벨,
남길 골드, 경험치 우선)을 따라 하기 정답과 같은 식(RuleRecorder·rule_label)으로 계획 칸(레벨 그대로/+1/+2, 남길 골드 6칸)에 넣고 그
라운드 내내 지킨다(계획 AI처럼 라운드마다 한 번, 경험치 우선 없이 실행). 덱 고르기와 갈아타기는 계획 AI가 한다.
틀 몫 = 이 탐침 − 하이브리드 탐침, 학습 몫 = 본래 탐침 − 이 탐침(results/README 「계획 틀 몫」). AI 자리 「계획 갈래」 표는 실행되지
않은 신경망 계획이라 읽지 않는다.

실행(저장소 맨 위에서, probe_heads.py와 같은 PYTHONPATH):
    python meta/inversion/probe_frame.py --net checkpoints/plan_dense_both_s2_latest.pt --label frame_plan_dense_both_s2_latest --games 400 --jobs 2 --out meta/inversion/probe_rows_frame_plan_dense_both_s2_latest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hra.plan_bot import PlanPolicy
from hra.plan_state import FLOORS, rule_label
from meta.human_bot import HumanPolicy
from meta.human_macro import action


def frame_plan(level, gold, target, floor, exp_first):
    """규칙의 (목표 레벨, 남길 골드, 경험치 우선) -> 계획 틀의 (목표 레벨, 남길 골드)."""
    eff = 9 if exp_first and level < 9 and gold >= 54 else target  # RuleRecorder.macro와 같다
    _, lv, fi = rule_label(None, None, level, eff, floor)
    return level + lv, FLOORS[fi]


def frame_macro(self, player, game_round):
    if self.target is None:  # 2-1 전(1단계)은 규칙 그대로
        return HumanPolicy.macro(self, player, game_round)
    if getattr(self, 'held_round', None) != game_round:
        self.held_round = game_round
        self.held = frame_plan(player.level, player.gold, *self.macro_plan(player, game_round))
    return action(player.gold, player.level, *self.held, False)


PlanPolicy.macro = frame_macro  # 모듈 맨 위에서 바꿔야 윈도우 일꾼(spawn)도 이 파일을 다시 읽으며 같이 바뀐다
import probe_heads  # noqa: E402

if __name__ == '__main__':
    probe_heads.main()
