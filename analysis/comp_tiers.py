"""
조합 간 라운드로빈 -> 티어.

조합을 서로 모두 붙여서 평균 승률을 낸다. 경제나 의사결정이 개입하지 않은
"보드 대 보드" 기준의 상대 강도라, 패치 전후로 무엇이 세졌는지 비교할 때 쓴다.

--comps 로 조합 JSON을 받을 수 있다. 형식:
    {"조합 이름": [{"name": "yasuo", "stars": 2, "items": []}, ...], ...}
생략하면 analysis/comps.py 의 조합을 2성으로 붙인다.

실행: python -m analysis.comp_tiers --n 20
"""
import argparse
import json
from collections import defaultdict

from analysis.battle import win_rate
from analysis.comps import COMPS, spec


def load_comps(path):
    if path:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {name: spec(comp, stars=2) for name, comp in COMPS.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--comps', default=None)
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--out', default=None, help='승률 매트릭스 JSON 저장 경로')
    args = ap.parse_args()

    comps = load_comps(args.comps)
    names = list(comps)
    matrix = defaultdict(dict)
    total = defaultdict(float)
    played = defaultdict(int)

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rate = win_rate(comps[a], comps[b], args.n)
            matrix[a][b] = round(rate, 3)
            # win_rate가 매 판 좌우를 바꿔가며 붙이니 진영 유리는 이미 상쇄돼 있다.
            # 반대 방향을 따로 한 번 더 돌릴 이유가 없어서 대칭으로 채운다.
            matrix[b][a] = round(1 - rate, 3)
            total[a] += rate
            total[b] += 1 - rate
            played[a] += 1
            played[b] += 1
        print(f'  {a} 완료', flush=True)

    # 조합 하나가 실제로 치르는 판은 N x (조합 수 - 1) 이다. 기본값 N=20이면
    # 승률이 비슷한 두 조합의 순위는 다시 돌릴 때마다 뒤집힌다. 큰 차이만 읽어야 한다.
    print(f'\n조합 티어 (전체 평균 승률, 매치업당 N={args.n})')
    for name in sorted(names, key=lambda x: total[x] / max(played[x], 1), reverse=True):
        print(f'  {total[name] / max(played[name], 1) * 100:5.1f}%   {name}')

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({a: matrix[a] for a in names}, f, ensure_ascii=False, indent=2)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
