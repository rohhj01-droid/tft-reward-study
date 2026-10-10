"""
롤체지지 보관본 파서(meta/lolchess_set4.py) 검사.

실행: python -m meta.test_lolchess
"""

# 2020-10~11월 템플릿(10.22 보관본, 한국어판). 특성은 아이콘 파일 이름, 유닛은 초상 파일 이름, 아이템은 아이콘 → 영어 이름 표로 읽는다.
OLD = '''<div class="deckItem"><div class="profile__match-history-v2__item placement-1" data-match-id="x" data-match-url="https://lolchess.gg/profile/kr/x">
<div class="traits">
<div
    class="tft-hexagon tft-hexagon--24 tft-hexagon--grade-3 tft-hexagon-chosen">
    <img src="//cdn.lolchess.gg/images/assets/tft/traits/4.0/trait_icon_mystic_darken.png" data-toggle="tooltip"
         title="6 신비술사 (선택받은 자)" alt="6 신비술사"></div>
<div class="tft-hexagon tft-hexagon--24 tft-hexagon--grade-2"><img src="//cdn.lolchess.gg/images/assets/tft/traits/4.0/trait_icon_vanguard_darken.png" title="4 선봉대" alt="4 선봉대"></div>
</div>
<div class="unit"><img src="//cdn.lolchess.gg/images/tft/stars/cost2_stars2.png" class="stars"><div class="tft-champion cost-2"><img src="//cdn.lolchess.gg/images/tft/champions/set4/Janna.png" alt="잔나"></div>
<ul class="items"><img src="//cdn.lolchess.gg/images/tft/item/ChaliceOfPower2.png" class="item" title="힘의 성배"><img src="//ddragon.leagueoflegends.com/cdn/10.20.1/img/item/3190.png" class="item" title="강철의 솔라리 펜던트"></ul></div>
<div class="unit"><img src="//cdn.lolchess.gg/images/tft/stars/cost4_stars1.png" class="stars"><div class="tft-champion cost-4"><img src="//cdn.lolchess.gg/images/tft/champions/set4/Sejuani.png" alt="세주아니"></div><ul class="items"></ul></div>
<div class="unit"><img src="//cdn.lolchess.gg/images/tft/stars/cost1_stars3.png" class="stars"><div class="tft-champion cost-1"><img src="//ddragon.leagueoflegends.com/cdn/10.20.1/img/champion/MonkeyKing.png" alt="Wukong"></div><ul class="items"></ul></div>
</div></div>'''

# 2020-11-27 템플릿(10.24 보관본, 영어판). 선택받은 자는 --chromatic 클래스다.
NEW = '''<div class="deckItem"><div class="traits">
<div class="tft-hexagon-image tft-hexagon-image--black tft-hexagon-image--chromatic"><img src="//cdn.lolchess.gg/images/assets/tft/traits/4.0/trait_icon_dusk_black.png" title="6 Dusk" alt="6 Dusk"></div>
</div>
<div class="unit"><img src="//cdn.lolchess.gg/images/tft/stars/cost1_stars3.png" class="stars"><div class="tft-champion cost-1"><img src="//cdn.lolchess.gg/images/tft/champions/set4/Vayne.png" alt="Vayne"></div>
<ul class="items"><img src="//ddragon.leagueoflegends.com/cdn/10.22.1/img/item/3124.png" class="item" title="Guinsoo&#039;s Rageblade"></ul></div>
</div>'''

ITEM_MAP = {'ChaliceOfPower2': 'Chalice of Power', '3190': 'Locket of the Iron Solari', '3124': "Guinsoo's Rageblade"}


def winners_parse_both_templates_test():
    """두 템플릿에서 유닛(시뮬레이터 이름)·별·아이템(영어)·특성 인원·선택받은 자 특성이 같은 모양으로 나온다. 옛 템플릿은
    일부 초상을 롤 데이터 드래곤 그림(LeeSin, MonkeyKing=오공)으로 그린다."""
    from meta.lolchess_set4 import winners
    old = winners(OLD, ITEM_MAP)
    assert len(old) == 1
    b = old[0]
    assert b['units'] == [{'name': 'janna', 'stars': 2, 'items': ['Chalice of Power', 'Locket of the Iron Solari']},
                          {'name': 'sejuani', 'stars': 1, 'items': []}, {'name': 'wukong', 'stars': 3, 'items': []}], b['units']
    assert b['traits'] == {'mystic': 6, 'vanguard': 4} and b['chosen_trait'] == 'mystic', b
    new = winners(NEW, ITEM_MAP)[0]
    assert new['units'] == [{'name': 'vayne', 'stars': 3, 'items': ["Guinsoo's Rageblade"]}]
    assert new['traits'] == {'dusk': 6} and new['chosen_trait'] == 'dusk', new


ITEM_TRENDS = '''<ul><li><a href="https://lolchess.gg/statistics/items">Item Trends</a></li></ul>
<div class="statistics-items"><h5>v10.24 <span>Item Trends</span></h5><p>Based on use of TOP 4 players above Platinum Tier</p>
<table><tr><th>Champion</th><th>Items</th></tr>
<tr><td><span>Lee Sin</span></td><td><span>20.5%</span> <img class="item" title="Blue Buff"> <b>Blue Buff</b> + 20.5%</td>
<td><span>7%</span> <img class="item" title="Redemption"> <b>Redemption</b> + 7%</td></tr></table></div>'''

META_DECK = '''<div class="guide-meta__deck-box"><div class="guide-meta__deck__column name mr-3"><span>9 Warlord</span> <em>UPDATED</em></div>
<div class="guide-meta__deck__column traits"><div class="tft-hexagon-image"><img src="//cdn.lolchess.gg/images/assets/tft/traits/4.0/trait_icon_warlord_gold.png"></div></div>
<div class="guide-meta__deck__column champions mr-2">
<div class="tft-champion-box"><div class="tft-champion cost-1"><img src="//cdn.lolchess.gg/images/tft/champions/set4/Garen.png" alt="Garen"><span class="cost">$1</span></div><div class="tft-items"></div></div>
<div class="tft-champion-box"><div class="tft-champion cost-5"><img src="//cdn.lolchess.gg/images/tft/champions/set4/Sett.png" alt="Sett"><span class="cost">$5</span></div>
<div class="tft-items"><img src="//cdn.lolchess.gg/images/tft/item/WarlordsBanner.png" alt="Warlord&#039;s Banner"></div></div></div>
<div class="guide-meta__deck__column cost mr-2" data-toggle="tooltip" title="Minimum gold"><img src="x.png" alt="Gold"><span class="d-block">66</span></div></div>'''


def item_trends_and_meta_decks_parse_test():
    """아이템 트렌드는 패치·설명·챔피언(시뮬레이터 이름)별 (아이템, 비율)을, 추천 덱은 이름·표시·유닛·아이템·비용을 읽는다."""
    from meta.lolchess_set4 import item_trends, meta_decks
    t = item_trends(ITEM_TRENDS)
    assert t['patch'] == '10.24' and t['note'] == 'Based on use of TOP 4 players above Platinum Tier', t
    assert t['champions'] == {'leesin': [['Blue Buff', 20.5], ['Redemption', 7.0]]}, t['champions']
    d = meta_decks(META_DECK, {})[0]
    assert d['name'] == '9 Warlord' and d['label'] == 'UPDATED' and d['cost'] == 66, d
    assert d['units'] == ['garen', 'sett'] and d['items'] == {'sett': ["Warlord's Banner"]} and d['traits'] == ['warlord'], d


def winners_never_keep_player_identifiers_test():
    """판 번호와 프로필 주소(소환사 이름)는 결과에 들어가지 않는다."""
    import json
    from meta.lolchess_set4 import winners
    dumped = json.dumps(winners(OLD, ITEM_MAP), ensure_ascii=False)
    assert 'profile' not in dumped and 'match' not in dumped, dumped


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
