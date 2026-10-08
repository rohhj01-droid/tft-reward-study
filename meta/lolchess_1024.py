"""
롤체지지 10.24 통계 보관본(웨이백)에서 실제 플레이 자료를 꺼내 JSON으로 저장한다.

- 메타 트렌드(2020-11-28 07:11 UTC 보관본, 10.24 핫픽스 전): 지난 24시간 다이아 이상 판의 최종 보드 특성 조합 27개.
  조합마다 고른 비율, 판 수로 보이는 값(games_score), 승률, 4등 안, 평균 등수, 1~8등 비율, 자주 든 아이템.
  페이지에 박힌 window.__decks를 그대로 읽는다.
- 최근 1등 덱(2020-11-27 03:19 UTC 보관본): 1등 25명의 최종 보드(유닛, 별, 아이템, 특성, 선택받은 자 특성).
  소환사 이름, 지역, 판 번호는 저장하지 않는다.

실행: python -m meta.lolchess_1024  ->  meta/lolchess_10.24_2020-11-28.json
"""
import html
import json
import os
import re
import urllib.request

TRENDS = 'https://web.archive.org/web/20201128071110id_/https://lolchess.gg/decks'
WINNERS = 'https://web.archive.org/web/20201127031903id_/https://lolchess.gg/decks/matches'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_10.24_2020-11-28.json')


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode('utf-8', 'ignore')


def trends(page):
    start = page.index('window.__decks = ') + len('window.__decks = ')
    decks, _ = json.JSONDecoder().raw_decode(page[start:])
    return [{'key': d['key'], 'traits': {t['key']: int(t['num_units']) for t in d['traits']},
             'pick_rate': d['pick_rate'], 'games_score': d['games_score'], 'win_rate': d['win_rate'],
             'top4_rate': d['top_rate'], 'average_placement': d['average_placement'],
             'placements': [d['placements'][str(p)]['rate'] for p in range(1, 9)],
             # items는 그 챔피언이 그 조합에서 자주 든 아이템 3개(모든 유닛에 있다), recommended는 페이지에 보이던
             # 핵심 유닛의 추천 아이템(보드마다 8개)이다. 보드를 실제처럼 만들 때는 recommended를 쓴다.
             'units': [{'name': c['key'], 'items': c['items'],
                        'recommended': c['recommend_items'] if c['show_recommend_items'] else []}
                       for c in d['champions']]} for d in decks]


def winners(page):
    boards = []
    for block in page.split('<div class="deckItem">')[1:]:
        traits = re.findall(r'class="tft-hexagon-image([^"]*)">\s*<img[^>]*?alt="([^"]+)"', block)
        units = []
        for unit in block.split('<div class="unit">')[1:]:
            units.append({'name': re.search(r'tft-champion[^>]*>\s*<img[^>]*?alt="([^"]+)"', unit).group(1),
                          'stars': int(re.search(r'stars(\d)', unit).group(1)),
                          'items': [html.unescape(i) for i in re.findall(r'class="item"[^>]*?title="([^"]*)"', unit)]})
        boards.append({'traits': [alt for _, alt in traits],
                       'chosen_trait': next((alt.split(' ', 1)[1] for cls, alt in traits if 'chosen' in cls), None),
                       'units': units})
    return boards


if __name__ == '__main__':
    data = {'source': {'trends': TRENDS, 'trends_note': '지난 24시간 다이아 이상, 최종 보드 특성 조합별(10.24 핫픽스 전)',
                       'winners': WINNERS, 'winners_note': '최근 1등 25명의 최종 보드. 소환사 이름·지역·판 번호는 뺐다'},
            'trends': trends(fetch(TRENDS)), 'winners': winners(fetch(WINNERS))}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'메타 트렌드 {len(data["trends"])}개, 1등 보드 {len(data["winners"])}개 -> {OUT}')
