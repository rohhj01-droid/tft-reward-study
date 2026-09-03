"""
분석에 쓰는 조합 정의.

코스트 구성이 서로 다른 조합을 골라, "어떤 코스트대의 조합이 주어진 골드로
실제로 완성 가능한가"를 비교할 수 있게 했다.

조합은 손으로 골랐다. 티어 리스트에서 가져온 게 아니라서 절대 승률은 의미가 없다.
조합 사이의 상대 비교로만 읽는다.

LLM으로 생성/검증한 조합 세트(designed_comps.json)는 라벨링 파이프라인 산출물이라
저장소에 포함하지 않았다. analysis 스크립트는 --comps 로 그런 JSON을 받을 수도 있다.
"""

COMPS = {
    # 1코스트만으로 채운 조합. 시너지를 고려하지 않고 코스트만 맞춘 대조군.
    'low_incoherent': [('yasuo', 1), ('fiora', 1), ('wukong', 1), ('garen', 1),
                       ('vayne', 1), ('nidalee', 1), ('twistedfate', 1), ('diana', 1)],

    # 1~3코 중심이면서 Duelist / Divine 시너지가 맞물리는 조합.
    'low_coherent': [('yasuo', 1), ('fiora', 1), ('jax', 2), ('xinzhao', 3),
                     ('kalista', 3), ('wukong', 1), ('irelia', 3), ('garen', 1)],

    # 2~3코 중심. Warlord 계열.
    'mid': [('jax', 2), ('hecarim', 2), ('vi', 2), ('pyke', 2),
            ('kalista', 3), ('katarina', 3), ('irelia', 3), ('xinzhao', 3)],

    # 4~5코 고밸류. 레벨을 올려야 열리지만 별을 올리기는 어렵다.
    'high': [('jhin', 4), ('ashe', 4), ('warwick', 4), ('morgana', 4),
             ('azir', 5), ('leesin', 5), ('kayn', 5), ('sett', 5)],
}

# 모든 조합이 상대하는 고정 보드. 중반에 흔히 보이는 6유닛 2성 수준으로 잡았다.
# 여기가 너무 세거나 약하면 조합 승률이 전부 0% / 100%로 몰려서 비교가 안 된다.
BENCHMARK = [{'name': n, 'stars': 2, 'items': []}
             for n in ['yasuo', 'fiora', 'wukong', 'garen', 'jax', 'xinzhao']]


def spec(comp, stars, size=None):
    # size로 앞에서부터 잘라 "적은 유닛 고성 vs 많은 유닛 저성"을 만든다.
    units = comp[:size] if size else comp
    return [{'name': n, 'stars': stars, 'items': []} for n, _ in units]
