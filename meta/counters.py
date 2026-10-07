"""
출처가 적은 상성이 시뮬레이터 대전 결과에서도 보이는지 본다.

bunnymuffins 10.24b가 덱마다 적은 상성(Counters) 중 보드로 가를 수 있는 것만 골랐다. 덱 A의 상성 묶음 C에 대해
「A가 C를 상대로 낸 평균 승률」과 「A가 나머지를 상대로 낸 평균 승률」을 비교한다. 앞쪽이 확실히 낮아야
상성이 재현된 것이다. 배치로 상대하는 상성(뒷줄 모으기, 흩어 놓기)은 보드만으로 가를 수 없어 뺐다.

실행: python -m meta.counters results/pit_1024.json
"""
import json
import sys

from set4 import CHAMPION_TRAITS, cost_of
from Simulator.stats import RANGE
from meta.pit import load_boards, chosen_of
from meta.decks_1024 import trait_counts


def carry(board):
    """아이템을 가장 많이 든 유닛(같으면 비싼 쪽)."""
    return max(board['units'], key=lambda u: (len(board['items'].get(u, [])), cost_of(u)))


def holds(board, item):
    return any(item in held for held in board['items'].values())


def traits(board):
    pick = chosen_of(board)
    return trait_counts(board['units'], board['items'], pick[1] if pick else None)


# 상성 묶음: 보드 -> 해당 여부
GROUPS = {
    '진이 캐리': lambda b: len(b['items'].get('jhin', [])) >= 2,
    '뒷줄 캐리(캐리 사거리 3 이상)': lambda b: RANGE[carry(b)] >= 3,
    '암살자 2 이상': lambda b: traits(b).get('assassin', 0) >= 2,
    '선지자 2 이상': lambda b: traits(b).get('dazzler', 0) >= 2,
    '거인 학살자 보유': lambda b: holds(b, 'giant_slayer'),
    '베이가 캐리': lambda b: carry(b) == 'veigar',
    '신비술사 2 이상(마법 저항)': lambda b: traits(b).get('mystic', 0) >= 2,
    '아트록스 포함': lambda b: 'aatrox' in b['units'],
}

# (덱 보드, 출처 상성 설명, 상성 묶음 이름)
CLAIMS = [
    ('Chosen Dusks', '황혼: Jhin is good against Riven', '진이 캐리'),
    ('Chosen Divines', '신성 워윅: Backline Carries', '뒷줄 캐리(캐리 사거리 3 이상)'),
    ('Moonlight Assassins', '달빛 다이애나: High damage such as Jhin', '진이 캐리'),
    ('Chosen Duelists', '결투가: Dazzler', '선지자 2 이상'),
    ('Chosen Sharpshooters', '명사수: Talon/Zed or other Assassins', '암살자 2 이상'),
    ('Chosen Sharpshooters', '명사수: Dazzler', '선지자 2 이상'),
    ('Chosen Sharpshooters', '명사수: Aatrox if no Quicksilver', '아트록스 포함'),
    ('Chosen Hunters', '사냥꾼: Assassins', '암살자 2 이상'),
    ('Chosen Hunters', '사냥꾼: Dazzler', '선지자 2 이상'),
    ('Chosen Brawlers', '애쉬 싸움꾼: Giant Slayer', '거인 학살자 보유'),
    ('Chosen Brawlers', '애쉬 싸움꾼: Veigar', '베이가 캐리'),
    ('Chosen Elderwood', '애쉬 조율: Giant Slayer', '거인 학살자 보유'),
    ('Chosen Elderwood', '애쉬 조율: Veigar', '베이가 캐리'),
    ('Enlightened Mages', '마법사 리롤: Magic Resistance', '신비술사 2 이상(마법 저항)'),
]


def main(path):
    data = json.load(open(path, encoding='utf-8'))
    boards = {b['name']: b for b in load_boards()}
    for setting in ('human', 'harness'):
        m = data[setting]
        print(f'\n[{setting}] 덱이 상성 묶음을 만났을 때와 나머지를 만났을 때의 평균 승률 (매치업당 {data["n"]}판)')
        for deck, claim, group in CLAIMS:
            test = GROUPS[group]
            vs = [m[deck][o] for o in m[deck] if test(boards[o])]
            rest = [m[deck][o] for o in m[deck] if not test(boards[o])]
            a = sum(vs) / len(vs) * 100
            r = sum(rest) / len(rest) * 100
            verdict = '재현' if a <= r - 10 else ('반대' if a >= r + 10 else '차이 작음')
            print(f'  {claim:42} 상성 {len(vs):2}개 {a:5.1f}%  나머지 {len(rest):2}개 {r:5.1f}%  -> {verdict}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'results/pit_1024.json')
