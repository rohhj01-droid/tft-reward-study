"""
board_value 만으로는 설명되지 않는 부분이 있는가.

코스트 구성이 다른 조합 네 개를 같은 정책(slow-roll)으로 24라운드 굴린 뒤,
같은 상대 보드와 붙여서 board_value 와 승률을 함께 잰다.

board_value 가 승패를 다 설명한다면 두 값의 순위가 같아야 한다.
어긋난다면 board_value 가 놓치고 있는 요인(시너지 등)이 있다는 뜻이다.

실행: python -m analysis.synergy
"""
import statistics

from analysis.comps import COMPS, BENCHMARK
from hra.env_battle import BattleEconEnv
from set4 import synergy_score

N = 200


def run(comp, n=N):
    """slow-roll 정책으로 n판. (평균 board_value, 승률)"""
    env = BattleEconEnv(comp=comp, opponent=BENCHMARK)
    wins = 0
    scores = []
    for _ in range(n):
        env.reset()
        done = False
        win = 0
        while not done:
            # SAVE(0)만 골라도 패시브 경험치로 레벨은 알아서 오른다. 그래서 이 조건문은
            # "6레벨에 머문다"가 아니라 "6레벨 될 때까지 모았다가 리롤"이 된다.
            action = 3 if env.level >= 6 else 0
            _, reward, done = env.step(action)
            win = reward['win']
        # 무승부는 패로 센다. env_battle이 A승일 때만 win 보상을 준다.
        wins += (win > 0)
        scores.append(env.board_value())
    return statistics.mean(scores), 100 * wins / n


def main():
    print(f'조합별 성능 (slow-roll, N={N}, 상대는 6유닛 2성 고정)')
    print(f"{'조합':>18}{'시너지':>8}{'board_value':>14}{'승률':>9}")
    for name, comp in COMPS.items():
        score = synergy_score([n for n, _ in comp])
        board, wr = run(comp)
        print(f'{name:>18}{score:>8}{board:>14.1f}{wr:>8.0f}%')

    print()
    print('board_value 가 더 낮은데 승률이 더 높은 조합이 나오면,')
    print('board_value 만 최적화하는 학습기는 그 조합을 선택하지 않는다.')


if __name__ == '__main__':
    main()
