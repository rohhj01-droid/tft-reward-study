"""
패치 10.24 메타 덱. 1티어 2개, 2티어 3개.

시뮬레이터 기본값은 10.24b 핫픽스(2020-12-01) 뒤 값이다. 그래서 티어는 핫픽스 뒤에 나온
bunnymuffins 10.24b 티어표(2020-12-04)를 따른다. 그 표의 S가 1티어, A가 2티어다.
기준 보드와 아이템은 tftactics 10.24 팀 조합 표(웨이백 보관본 2020-11-28, 핫픽스 전)에서 옮겼다.
출처와 판단 근거는 meta/README.md에 있다.

실행: python -m meta.decks_1024   (이름과 분류 기준을 스스로 확인한다)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from set4 import CHAMPION_TRAITS
from Simulator.item_stats import trait_items

EMBLEM_TRAIT = {item: trait for trait, item in trait_items.items()}

# signature: 분류 기준. 끝난 보드의 특성 인원수가 모두 이 값 이상이어야 한다.
# carry:     분류 기준. 이 중 하나가 보드에 있어야 한다. 비어 있으면 따지지 않는다.
# chosen:    bunnymuffins 10.24b가 권하는 선택받은 자 특성. 어느 유닛인지는 출처에 없다.
# units, items: tftactics 기준 보드. 느린 리롤 덱(제드, 달빛)은 레벨 7 보드라 7명이다.
DECKS = {
    'dusk': {
        'tier': 1,
        'signature': {'dusk': 4},
        'carry': [],
        'chosen': ['dusk', 'mystic', 'sharpshooter', 'keeper'],
        'units': ['vayne', 'thresh', 'aatrox', 'cassiopeia', 'jhin', 'riven', 'lillia', 'zilean'],
        'items': {'aatrox': ['gargoyle_stoneplate'],
                  'jhin': ['infinity_edge', 'last_whisper'],
                  'riven': ['ionic_spark', 'quicksilver', 'sunfire_cape']},
    },
    'divine_warwick': {
        'tier': 1,
        'signature': {'divine': 4},
        'carry': ['warwick'],
        'chosen': ['divine', 'adept', 'hunter'],
        'units': ['jax', 'irelia', 'lux', 'morgana', 'shen', 'warwick', 'leesin', 'yone'],
        'items': {'morgana': ['morellonomicon'],
                  'warwick': ['deathblade', 'quicksilver', 'runaans_hurricane'],
                  'yone': ['guardian_angel', 'hand_of_justice']},
    },
    'zed_ninja_shade': {
        'tier': 2,
        'signature': {'ninja': 4},
        'carry': ['zed'],
        'chosen': ['shade'],
        'units': ['elise', 'pyke', 'zed', 'evelynn', 'akali', 'kennen', 'shen'],
        'items': {'zed': ['guinsoos_rageblade', 'quicksilver', 'rapid_firecannon'],
                  'akali': ['locket_of_the_iron_solari', 'zekes_herald', 'zekes_herald']},
    },
    'moonlight_diana': {
        'tier': 2,
        'signature': {'moonlight': 3},
        'carry': ['diana'],
        'chosen': ['moonlight'],
        'units': ['lissandra', 'diana', 'pyke', 'sylas', 'akali', 'katarina', 'talon'],
        'items': {'diana': ['dragons_claw', 'hand_of_justice', 'sunfire_cape'],
                  'akali': ['blue_buff', 'hextech_gunblade', 'rapid_firecannon']},
    },
    'warlords': {
        'tier': 2,
        'signature': {'warlord': 6},
        'carry': [],
        'chosen': ['warlord'],
        'units': ['garen', 'nidalee', 'jarvaniv', 'pyke', 'vi', 'katarina', 'xinzhao', 'azir'],
        'items': {'pyke': ['warlords_banner'],
                  'katarina': ['guardian_angel', 'hextech_gunblade', 'quicksilver'],
                  'xinzhao': ['bloodthirster', 'titans_resolve']},
    },
}


def trait_counts(units, items, chosen=None):
    """특성별 인원수. 시뮬레이터 player.update_team_tiers()와 같은 방식으로 센다.
    같은 유닛은 한 번만, 상징 아이템은 든 개수만큼, 선택받은 자 특성은 1을 더한다."""
    counts = {}
    for name in set(units):
        for trait in CHAMPION_TRAITS[name]:
            counts[trait] = counts.get(trait, 0) + 1
    for held in items.values():
        for item in held:
            if item in EMBLEM_TRAIT:
                counts[EMBLEM_TRAIT[item]] = counts.get(EMBLEM_TRAIT[item], 0) + 1
    if chosen:
        counts[chosen] = counts.get(chosen, 0) + 1
    return counts


def classify(units, counts):
    """끝난 보드가 어느 덱인지 덱 이름 목록으로 돌려준다. 해당 없으면 빈 목록.
    시뮬레이터 플레이어라면 update_team_tiers() 뒤의 player.team_composition을 counts로 넘긴다."""
    units = set(units)
    return [key for key, deck in DECKS.items()
            if all(counts.get(t, 0) >= n for t, n in deck['signature'].items())
            and (not deck['carry'] or units & set(deck['carry']))]


if __name__ == '__main__':
    from Simulator.origin_class_stats import origin_class
    from Simulator.item_stats import item_builds
    from set4 import TRAIT_BREAKS

    for key, deck in DECKS.items():
        for name in deck['units']:
            # set4.py 특성표가 시뮬레이터와 어긋나면 분류가 시뮬레이터 보드와 다르게 나온다
            assert sorted(CHAMPION_TRAITS[name]) == sorted(origin_class[name]), name
        assert set(deck['items']) <= set(deck['units']), key
        assert all(i in item_builds for held in deck['items'].values() for i in held), key
        assert all(t in TRAIT_BREAKS for t in [*deck['signature'], *deck['chosen']]), key
        counts = trait_counts(deck['units'], deck['items'])
        # 기준 보드는 선택받은 자 없이도 자기 덱 하나로만 분류돼야 한다
        assert classify(deck['units'], counts) == [key], key
        active = {t: c for t, c in counts.items() if c >= TRAIT_BREAKS[t][0]}
        print(f'{key:16} {deck["tier"]}티어  ' +
              ', '.join(f'{t} {c}' for t, c in sorted(active.items(), key=lambda x: -x[1])))

    # 10.24b에서 B티어인 tftactics "Chosen Duelists" 보드는 어느 덱으로도 안 잡혀야 한다
    duelists = ['fiora', 'yasuo', 'jax', 'kalista', 'janna', 'shen', 'leesin', 'yone']
    assert classify(duelists, trait_counts(duelists, {})) == []
    print('ok')
