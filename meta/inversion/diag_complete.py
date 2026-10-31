"""완성 여부로 가른 덱별 등수(results/README 「2학기 정리」 1번 표, 2026-10-31). 판을 돌리지 않고 같은 200판의 diag_flex·diag_chosen
기록을 자리끼리 붙여 센다(두 기록은 자리 순서가 같다).

완성 = 끝 레벨 8 이상, 끝 보드에 4코스트가 1장 이상이고 그중 절반 이상이 2성 이상, 덱의 선택받은 자를 들고 끝남. 4코스트가 없는 Chosen Warlords는
「캐리 전부 2성·레벨 8 이상」(선택받은 자 조건 없음)으로 센다. 아래 둘째 표는 모든 덱을 그 캐리 정의 하나로 센 것이다.

실행(저장소 맨 위에서):
    python meta/inversion/diag_complete.py meta/inversion/diag_flex_rows_syn.json meta/inversion/diag_chosen_rows_syn.json
"""
import json
import statistics
import sys

DECKS = ['Chosen Dusks', 'Dusk Cultists', 'Chosen Divines', 'Chosen Cultists', 'Chosen Warlords']


def by_carry(r):
    return r['level'] >= 8 and r['carry2'] == 1.0


def by_four(r):
    return r['level'] >= 8 and r['four'] > 0 and r['four2'] * 2 >= r['four'] and r['deck_chosen']


def table(title, rows, done):
    print(f'\n### {title}\n| 덱 | 자리 | 완성 비율 | 완성 등수 | 미완성 등수 | 전체 등수 |\n|---|---|---|---|---|---|')
    for d in DECKS:
        rs = [r for r in rows if r['deck'] == d]
        yes = [r['place'] for r in rs if done(r)]
        no = [r['place'] for r in rs if not done(r)]
        print(f'| {d} | {len(rs)} | {len(yes) / len(rs):.0%} | {statistics.mean(yes):.2f} | {statistics.mean(no):.2f} | '
              f'{statistics.mean(r["place"] for r in rs):.2f} |')


if __name__ == '__main__':
    flex = json.load(open(sys.argv[1], encoding='utf-8'))
    chosen = json.load(open(sys.argv[2], encoding='utf-8'))
    assert len(flex) == len(chosen) and all(a['deck'] == b['deck'] and a['place'] == b['place'] for a, b in zip(flex, chosen)), \
        '두 기록의 자리 순서가 다르다(같은 판 목록이 아니다)'
    rows = [dict(a, deck_chosen=b['end_deck_chosen']) for a, b in zip(flex, chosen)]
    table('덱별 정의(총사령관만 캐리 정의)', rows, lambda r: by_carry(r) if r['deck'] == 'Chosen Warlords' else by_four(r))
    table('모든 덱을 「캐리 전부 2성·레벨 8 이상」으로', rows, by_carry)
