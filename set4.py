"""
TFT Set 4 게임 상수.

시뮬레이터(Simulator/pool_stats.py, Simulator/player.py)에서 확인한 값을 옮긴 것.
경제 환경(hra/env.py)을 시뮬레이터 없이도 돌릴 수 있도록 분리해 두었다.
"""

# 레벨별 코스트 등장 확률(누적). 인덱스 = 플레이어 레벨.
# 예) LEVEL_ODDS[6] = [0.25, 0.65, 0.95, 1, 10]
#     -> 1코 25%, 2코 40%, 3코 30%, 4코 5%, 5코 0%
# 마지막 원소의 10은 "그 위로는 안 나온다"는 의미의 sentinel(시뮬레이터 원본 표기 유지).
LEVEL_ODDS = [
    [1,    10,    10,    10,   10],
    [1,    10,    10,    10,   10],
    [1,    10,    10,    10,   10],
    [0.75, 1,     10,    10,   10],
    [0.55, 0.85,  1,     10,   10],
    [0.45, 0.775, 0.975, 1,    10],
    [0.25, 0.65,  0.95,  1,    10],
    [0.2,  0.5,   0.85,  0.99, 1],
    [0.15, 0.35,  0.7,   0.95, 1],
    [0.1,  0.25,  0.55,  0.85, 1],
    [0.05, 0.15,  0.35,  0.75, 1],
    [0.01, 0.03,  0.15,  0.65, 1],
]

# COST_STAR_VALUE[코스트-1][별-1] = 해당 유닛의 보드 가치
# 별이 하나 오를 때마다 대략 3배씩 증가한다.
COST_STAR_VALUE = [
    [1, 3, 9],
    [2, 5, 17],
    [3, 8, 26],
    [4, 11, 35],
    [5, 14, 44],
]

# 코스트별 유닛 1종당 풀에 존재하는 매수
POOL_SIZE = [29, 22, 18, 12, 10]

# 코스트별 유닛 종류 수
UNIQUE_PER_COST = [13, 13, 13, 11, 8]

# 레벨 L -> L+1 에 필요한 경험치 (Simulator.player.level_costs)
LEVEL_XP = {1: 2, 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 56, 8: 80}

# 라운드당 자동 지급 경험치
PASSIVE_XP = 2

# 최대 이자 (골드 50 이상에서 +5)
MAX_INTEREST = 5

ONE_COST_UNITS = ['diana', 'elise', 'fiora', 'garen', 'lissandra', 'maokai', 'nami',
                  'nidalee', 'tahmkench', 'twistedfate', 'vayne', 'wukong', 'yasuo']
TWO_COST_UNITS = ['annie', 'aphelios', 'hecarim', 'janna', 'jarvaniv', 'jax', 'lulu',
                  'pyke', 'sylas', 'teemo', 'thresh', 'vi', 'zed']
THREE_COST_UNITS = ['akali', 'evelynn', 'irelia', 'jinx', 'kalista', 'katarina', 'kennen',
                    'kindred', 'lux', 'nunu', 'veigar', 'yuumi', 'xinzhao']
FOUR_COST_UNITS = ['aatrox', 'ahri', 'ashe', 'cassiopeia', 'jhin', 'morgana', 'riven',
                   'sejuani', 'shen', 'talon', 'warwick']
FIVE_COST_UNITS = ['azir', 'ezreal', 'kayn', 'leesin', 'lillia', 'sett', 'yone', 'zilean']

# 트레잇별 발동 인원수. 시너지 분석(analysis/synergy.py)에서 사용.
TRAIT_BREAKS = {
    'cultist': [3, 6, 9], 'divine': [2, 4, 6, 8], 'dusk': [2, 4, 6],
    'elderwood': [3, 6, 9], 'enlightened': [2, 4, 6], 'exile': [1, 2],
    'fortune': [3, 6], 'moonlight': [3, 5], 'ninja': [1, 4],
    'spirit': [2, 4], 'warlord': [3, 6, 9], 'adept': [2, 3, 4],
    'assassin': [2, 4, 6], 'brawler': [2, 4, 6, 8], 'dazzler': [2, 4],
    'duelist': [2, 4, 6, 8], 'hunter': [2, 3, 4, 5], 'keeper': [2, 4, 6],
    'mage': [3, 6, 9], 'mystic': [2, 4, 6], 'sharpshooter': [2, 4, 6],
    'vanguard': [2, 4, 6, 8], 'shade': [2, 3, 4],
    'the_boss': [1], 'emperor': [1], 'tormented': [1],
}


# 챔피언 -> 트레잇. Simulator/origin_class_stats.py 의 origin_class 에서 옮긴 것.
CHAMPION_TRAITS = {
    'aatrox': ['cultist', 'vanguard'],       'ahri': ['spirit', 'mage'],
    'akali': ['ninja', 'assassin'],          'annie': ['fortune', 'mage'],
    'aphelios': ['moonlight', 'hunter'],     'ashe': ['elderwood', 'hunter'],
    'azir': ['warlord', 'keeper', 'emperor'], 'cassiopeia': ['dusk', 'mystic'],
    'diana': ['moonlight', 'assassin'],      'elise': ['cultist', 'keeper'],
    'evelynn': ['cultist', 'shade'],         'ezreal': ['elderwood', 'dazzler'],
    'fiora': ['enlightened', 'duelist'],     'garen': ['warlord', 'vanguard'],
    'hecarim': ['elderwood', 'vanguard'],    'irelia': ['enlightened', 'divine', 'adept'],
    'janna': ['enlightened', 'mystic'],      'jarvaniv': ['warlord', 'keeper'],
    'jax': ['divine', 'duelist'],            'jhin': ['cultist', 'sharpshooter'],
    'jinx': ['fortune', 'sharpshooter'],     'kalista': ['cultist', 'duelist'],
    'katarina': ['warlord', 'fortune', 'assassin'], 'kayn': ['tormented', 'shade'],
    'kennen': ['ninja', 'keeper'],           'kindred': ['spirit', 'hunter'],
    'leesin': ['divine', 'duelist'],         'lillia': ['dusk', 'mage'],
    'lissandra': ['moonlight', 'dazzler'],   'lulu': ['elderwood', 'mage'],
    'lux': ['divine', 'dazzler'],            'maokai': ['elderwood', 'brawler'],
    'morgana': ['enlightened', 'dazzler'],   'nami': ['enlightened', 'mage'],
    'nidalee': ['warlord', 'sharpshooter'],  'nunu': ['elderwood', 'brawler'],
    'pyke': ['cultist', 'assassin'],         'riven': ['dusk', 'keeper'],
    'sejuani': ['fortune', 'vanguard'],      'sett': ['the_boss', 'brawler'],
    'shen': ['ninja', 'mystic', 'adept'],    'sylas': ['moonlight', 'brawler'],
    'tahmkench': ['fortune', 'brawler'],     'talon': ['enlightened', 'assassin'],
    'teemo': ['spirit', 'sharpshooter'],     'thresh': ['dusk', 'vanguard'],
    'twistedfate': ['cultist', 'mage'],      'vayne': ['dusk', 'sharpshooter'],
    'veigar': ['elderwood', 'mage'],         'vi': ['warlord', 'brawler'],
    'warwick': ['divine', 'hunter', 'brawler'], 'wukong': ['divine', 'vanguard'],
    'xinzhao': ['warlord', 'duelist'],       'yasuo': ['exile', 'duelist'],
    'yone': ['exile', 'adept'],              'yuumi': ['spirit', 'mystic'],
    'zed': ['ninja', 'shade'],               'zilean': ['cultist', 'mystic'],
}


def synergy_score(names):
    """발동한 트레잇 단계의 총 개수. 조합이 얼마나 맞물려 있는지의 거친 지표."""
    counts = {}
    for name in names:
        for trait in CHAMPION_TRAITS.get(name, []):
            counts[trait] = counts.get(trait, 0) + 1
    return sum(sum(1 for b in TRAIT_BREAKS.get(t, []) if c >= b)
               for t, c in counts.items())


def cost_of(name):
    """유닛 이름 -> 코스트. 모르는 이름이면 None."""
    for i, group in enumerate([ONE_COST_UNITS, TWO_COST_UNITS, THREE_COST_UNITS,
                               FOUR_COST_UNITS, FIVE_COST_UNITS]):
        if name in group:
            return i + 1
    return None
