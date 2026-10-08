"""
챔피언 스킬 시전 시간(10.24 게임 파일)을 받아 audit/cast_time_10.24.json으로 저장한다.

CommunityDragon의 10.24 챔피언 파일(game/data/characters/<이름>/<이름>.bin.json)에서 주 스킬
(CharacterRecords/Root의 spellNames 첫 번째)의 mSpell.mCastTime을 꺼낸다. 값이 없으면 null로 둔다(게임 기본값을 따르는
스킬이거나, 진·제드·베인처럼 마나 스킬이 아닌 패시브다). 시뮬레이터에는 시전 시간이 없다(audit/README 「전투 공통 규칙」).

실행: python audit/cast_time.py
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://raw.communitydragon.org/10.24/game/data/characters/{0}/{0}.bin.json'


def cast_time(name):
    # 파이썬 기본 요청 머리글은 403으로 막힌다
    request = urllib.request.Request(URL.format(name), headers={'User-Agent': 'tft-reward-study audit'})
    with urllib.request.urlopen(request, timeout=60) as r:
        data = json.load(r)
    root = next(v for k, v in data.items() if k.endswith('CharacterRecords/Root'))
    spell = root['spellNames'][0]
    return spell, next(v for k, v in data.items() if k.endswith('/Spells/' + spell))['mSpell'].get('mCastTime')


if __name__ == '__main__':
    champions = json.load(open(os.path.join(HERE, 'cdragon_10.24_set4.json'), encoding='utf-8'))
    out = {'_source': URL.format('<이름>') + ' 의 주 스킬 mSpell.mCastTime(초). null은 파일에 값이 없는 것'}
    for key, champ in champions.items():
        spell, seconds = cast_time(champ['apiName'].lower())
        out[key] = {'spell': spell, 'cast_time': None if seconds is None else round(seconds, 3)}
    with open(os.path.join(HERE, 'cast_time_10.24.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'{len(out) - 1}명 -> audit/cast_time_10.24.json')
