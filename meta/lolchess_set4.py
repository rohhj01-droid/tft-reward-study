"""
롤체지지 Set 4 보관본(웨이백)에서 자료를 더 꺼내 JSON으로 저장한다. meta/lolchess_1024.py(10.24 메타 트렌드 27조합과
1등 보드 25개)에 더하는 것이다. 웨이백 CDX로 Set 4 기간(2020-09-16~2021-01-21)의 롤체지지 페이지를 훑어 찾았다
(2026-10-11). 챔피언별 페이지에는 통계가 없고, 프로필 페이지는 보관본이 없었다.

- 10.22 1등 보드: 2020-10-29 보관본 셋과 11-01 보관본의 최근 1등 25명씩(겹치는 보드는 하나로). 페이지가 베트남어·한국어판이라
  유닛은 초상 파일 이름, 특성은 아이콘 파일 이름, 아이템은 아이콘 → 영어 이름 표(영어판 페이지에서 만든다)로 읽는다.
- 메타 트렌드: 10.22(11-02)와 10.24의 다른 시각 둘(11-27 03:23, 22:38). 10.24 11-28 07:11은 lolchess_1024.py에 있다.
  같은 패치의 다른 시각끼리 견주면 지난 24시간 통계가 하루 사이 얼마나 흔들리는지 보인다.
- 아이템 트렌드(statistics/items): 챔피언마다 플래티넘 이상 4등 안 플레이어가 자주 든 아이템 5개와 비율. 10.22 둘, 10.24 하나.
- 롤체지지 추천 덱(meta, 2020-12-05, 10.24 핫픽스 뒤): 덱 16개의 유닛·아이템·비용.
소환사 이름, 지역, 판 번호는 저장하지 않는다.

실행: python -m meta.lolchess_set4 [--cache DIR]  ->  meta/lolchess_set4_more.json
--cache DIR을 주면 DIR/<보관 시각>.html이 있을 때 그 파일을 쓰고, 없으면 받아서 거기에 둔다.
"""
import argparse
import gzip
import html
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meta.decks_1024 import CHAMPION_TRAITS
from meta.lolchess_1024 import trends

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_set4_more.json')
MATCHES, DECKS, ITEMS_STAT = 'https://lolchess.gg/decks/matches', 'https://lolchess.gg/decks', 'https://lolchess.gg/statistics/items'
WINNERS_1022 = ['20201029024215', '20201029025324', '20201029025853', '20201101111305']
TRENDS = {'10.22': ['20201102075758'], '10.24': ['20201127032313', '20201127223836']}
ITEM_TRENDS = {'10.22': [('20201029223046', ITEMS_STAT), ('20201101014129', ITEMS_STAT)],
               '10.24': [('20201128172208', ITEMS_STAT + '?hl=en-US')]}
META_DECKS = ('20201205034241', 'https://lolchess.gg/meta')
# 아이템 아이콘 → 영어 이름 표를 만들 영어판 페이지
ENGLISH = [('20201128173743', 'https://lolchess.gg/items?hl=en-US'), ('20201101111305', MATCHES), ('20201127031903', MATCHES),
           ('20201128071110', DECKS)]
LABELS = ('UPDATED', 'HOT', 'NEW')


def fetch(ts, url, cache=None):
    path = cache and os.path.join(cache, ts + '.html')
    if path and os.path.exists(path):
        raw = open(path, 'rb').read()
    else:
        req = urllib.request.Request(f'https://web.archive.org/web/{ts}id_/{url}', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
        if path:
            open(path, 'wb').write(raw)
    if raw[:2] == b'\x1f\x8b':  # 보관본이 압축된 채로 오기도 한다
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', 'ignore')


PORTRAIT = re.compile(r'(?:champions/set4|img/champion)/(\w+)\.png')  # 롤체지지 초상 또는 롤 데이터 드래곤 초상(옛 템플릿 일부)


def unit_name(key):
    """초상 파일 이름(Leesin, Jarvaniv, 데이터 드래곤의 MonkeyKing) → 시뮬레이터 이름(leesin, jarvaniv, wukong)."""
    name = {'monkeyking': 'wukong'}.get(key.lower(), key.lower())
    assert name in CHAMPION_TRAITS, key
    return name


def trait_name(key):
    return 'the_boss' if key in ('theboss', 'the_boss') else key


def item_icons(pages):
    """영어판 페이지들의 아이템 <img>에서 아이콘 파일 이름 → 영어 이름."""
    names = {}
    for page in pages:
        for tag in re.findall(r'<img[^>]+>', page):
            src = re.search(r'/item/([^"/]+)\.png"', tag)
            title = re.search(r'(?:title|alt)="([^"]+)"', tag)
            if src and title and 'item' in tag:
                names.setdefault(src.group(1), html.unescape(title.group(1)))
    return names


def item_names(block, icons):
    out = []
    for tag in re.findall(r'<img[^>]*class="item"[^>]*>', block):
        src = re.search(r'/item/([^"/]+)\.png"', tag)
        title = re.search(r'title="([^"]*)"', tag)
        out.append(icons.get(src.group(1)) if src and src.group(1) in icons else html.unescape(title.group(1)))
    return out


def winners(page, icons):
    """최근 1등 보드. 두 템플릿(2020-10~11월 profile__match-history-v2, 11-27 tft-hexagon-image) 모두 읽는다."""
    boards = []
    for block in page.split('<div class="deckItem">')[1:]:
        traits, chosen = {}, None
        for hexa in re.findall(r'<div[^>]*class="tft-hexagon[^"]*"[^>]*>\s*<img[^>]*>', block):
            key = re.search(r'trait_icon_(.+?)_(?:darken|black|bronze|silver|gold|chromatic|platinum)\.png', hexa)
            count = re.search(r'alt="(\d+)', hexa)
            if not (key and count):
                continue
            traits[trait_name(key.group(1))] = int(count.group(1))
            if 'chosen' in hexa or 'chromatic' in hexa:
                chosen = trait_name(key.group(1))
        units = []
        for unit in block.split('<div class="unit">')[1:]:
            units.append({'name': unit_name(PORTRAIT.search(unit).group(1)),
                          'stars': int(re.search(r'stars(\d)\.png', unit).group(1)), 'items': item_names(unit, icons)})
        boards.append({'traits': traits, 'chosen_trait': chosen, 'units': units})
    return boards


def item_trends(page):
    """챔피언마다 (아이템, 비율) 5개. 표 머리의 패치 번호와 설명도 돌려준다."""
    text = lambda s: ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s)).split())
    head = re.search(r'v(1\d\.\d+) Item Trends (.*?) Champion Items', text(page))  # 표 머리: "v10.24 Item Trends Based on …"
    rows = {}
    for row in re.findall(r'<tr[^>]*>.*?</tr>', page, re.S):
        cells = re.findall(r'<td[^>]*>.*?</td>', row, re.S)
        if len(cells) < 2:
            continue
        name = re.sub(r'[^a-z]', '', text(cells[0]).lower())
        assert name in CHAMPION_TRAITS, text(cells[0])
        rows[name] = [[m.group(2), float(m.group(1))] for c in cells[1:]
                      for m in [re.match(r'([\d.]+)% (.+?) \+ [\d.]+%$', text(c))] if m]
    return {'patch': head.group(1) if head else None, 'note': head.group(2).strip() if head else None, 'champions': rows}


def meta_decks(page, icons):
    """롤체지지 추천 덱: 이름, 표시(UPDATED/HOT/NEW), 유닛, 유닛별 아이템, 비용."""
    decks = []
    for block in page.split('class="guide-meta__deck-box"')[1:]:
        words = html.unescape(re.sub(r'<[^>]+>', ' ', re.search(r'guide-meta__deck__column name[^>]*>(.*?)</div>', block, re.S).group(1))).split()
        label = next((w for w in words if w in LABELS), None)
        units, items = [], {}
        for box in re.findall(r'class="tft-champion-box">.*?</div>\s*</div>', block, re.S):
            name = unit_name(PORTRAIT.search(box).group(1))
            units.append(name)
            held = [icons.get(s, t) for s, t in re.findall(r'/item/([^"/]+)\.png"[^>]*?(?:title|alt)="([^"]+)"', box)]
            if held:
                items[name] = [html.unescape(h) for h in held]
        cost = re.search(r'guide-meta__deck__column cost.*?<span[^>]*>\s*(\d+)\s*</span>', block, re.S)
        decks.append({'name': ' '.join(w for w in words if w not in LABELS), 'label': label, 'units': units, 'items': items,
                      'cost': int(cost.group(1)) if cost else None,
                      'traits': [trait_name(k) for k in re.findall(r'trait_icon_(.+?)_(?:darken|black|bronze|silver|gold|chromatic|platinum)\.png', block)]})
    return decks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=None)
    args = ap.parse_args()
    if args.cache:
        os.makedirs(args.cache, exist_ok=True)
    icons = item_icons([fetch(ts, url, args.cache) for ts, url in ENGLISH])
    boards = {}
    for ts in WINNERS_1022:
        for b in winners(fetch(ts, MATCHES, args.cache), icons):
            key = json.dumps([b['chosen_trait'], [(u['name'], u['stars'], sorted(u['items'])) for u in b['units']]], sort_keys=True)
            boards.setdefault(key, dict(b, snapshots=[]))['snapshots'].append(ts)
    out = {'source': {'archive': 'https://web.archive.org/web/<보관 시각>/<주소>',
                      'winners_1022': {'url': MATCHES, 'snapshots': WINNERS_1022,
                                       'note': '최근 1등 25명씩, 겹치는 보드는 하나로. 소환사 이름·지역·판 번호는 뺐다. 10-29 셋은 베트남어·한국어판'},
                      'trends': {'url': DECKS, 'snapshots': TRENDS, 'note': '지난 24시간 다이아 이상 최종 보드 특성 조합별(lolchess_1024.py와 같은 모양)'},
                      'item_trends': {'url': ITEMS_STAT, 'snapshots': {p: [ts for ts, _ in v] for p, v in ITEM_TRENDS.items()}},
                      'meta_decks_1024b': {'url': META_DECKS[1], 'snapshot': META_DECKS[0], 'note': '롤체지지 추천 덱, 10.24 핫픽스 뒤'}},
           'winners_1022': list(boards.values()),
           'trends': {p: {ts: trends(fetch(ts, DECKS, args.cache)) for ts in v} for p, v in TRENDS.items()},
           'item_trends': {p: {ts: item_trends(fetch(ts, url, args.cache)) for ts, url in v} for p, v in ITEM_TRENDS.items()},
           'meta_decks_1024b': meta_decks(fetch(*META_DECKS, args.cache), icons)}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('1등 보드(10.22)', len(out['winners_1022']), '| 트렌드', {p: {ts: len(v) for ts, v in d.items()} for p, d in out['trends'].items()},
          '| 아이템 트렌드', {p: list(d) for p, d in out['item_trends'].items()}, '| 추천 덱', len(out['meta_decks_1024b']), '->', OUT)


if __name__ == '__main__':
    main()
