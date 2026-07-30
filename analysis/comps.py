"""
분석에 쓰는 조합 정의.

코스트 구성이 서로 다른 조합을 골라, "어떤 코스트대의 조합이 주어진 골드로
실제로 완성 가능한가"를 비교할 수 있게 했다.

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

# 비교 기준이 되는 상대 보드. 6유닛 2성.
BENCHMARK = [{'name': n, 'stars': 2, 'items': []}
             for n in ['yasuo', 'fiora', 'wukong', 'garen', 'jax', 'xinzhao']]


def spec(comp, stars, size=None):
    """(이름, 코스트) 리스트 -> 전투용 보드 스펙."""
    units = comp[:size] if size else comp
    return [{'name': n, 'stars': stars, 'items': []} for n, _ in units]
