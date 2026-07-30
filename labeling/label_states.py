"""
게임 상태 -> LLM 매크로 행동 라벨.

상태 텍스트를 넣고 "최선의 매크로 행동 + 근거"를 JSON으로 받는다.
OpenAI 호환 엔드포인트를 쓰므로 base_url 만 바꾸면 다른 제공자로도 돌아간다.

실행:
    export UPSTAGE_API_KEY=...
    python -m labeling.label_states states.json --out labels.json

라벨 분포가 한쪽으로 쏠리는 문제는 labeling/README.md 참고.
"""
import argparse
import json
import os
import sys
from collections import Counter

from openai import OpenAI

MODEL = 'solar-pro2'
BASE_URL = 'https://api.upstage.ai/v1'
VALID_ACTIONS = {'level_up', 'roll_down', 'save_econ', 'hold'}

SYSTEM = """너는 전략적 자동전투(TFT Set 4) 최상위 코치다.
주어진 게임 상태에서, 최종 등수를 최대화하기 위한 '단 하나의 최선의 매크로 행동'을 판단한다.

핵심 원칙 (반드시 종합 고려):
1. 체력 관리 최우선 - 체력 50 이하면 당장 보드를 강하게 만들어 출혈을 막아라.
2. 강한 보드 = 유닛 수(레벨) + 별 + 아이템 + 시너지. 레벨업만 하고 템/별이 비면 약하다.
3. 레벨업의 가치는 4~5코스트 고밸류 유닛과 시너지를 여는 데 있다. 안정적이면 레벨을 올려라.
4. 저코스트 핵심 캐리 + 체력 여유 -> 리롤(별 올리기)도 강력한 대안.
5. 이자(골드/10, 최대 5)를 활용한 경제 운영도 중요하다.

반드시 아래 JSON 형식으로만 답하라 (다른 텍스트 금지):
{
  "primary_action": "level_up | roll_down | save_econ | hold 중 하나",
  "target_level": 정수(목표 레벨, 유지면 현재 레벨),
  "commit_comp": "밀어야 할 조합 방향(문자열)",
  "priority_units": ["우선 확보/강화할 핵심 유닛", ...],
  "health_judgment": "안전 | 주의 | 위험",
  "reasoning": "한국어 2~4문장, 구체적 근거"
}"""


def extract_json(text):
    start, end = text.find('{'), text.rfind('}')
    return json.loads(text[start:end + 1])


def label_one(client, state_text):
    kwargs = dict(model=MODEL,
                  messages=[{'role': 'system', 'content': SYSTEM},
                            {'role': 'user', 'content': state_text +
                             '\n\n위 상태에서 최선의 매크로 행동을 JSON으로 판단하라.'}],
                  temperature=0.3, max_tokens=1000)
    try:
        resp = client.chat.completions.create(response_format={'type': 'json_object'}, **kwargs)
    except Exception:
        resp = client.chat.completions.create(**kwargs)  # json_object 미지원 폴백
    data = extract_json(resp.choices[0].message.content)
    if data.get('primary_action') not in VALID_ACTIONS:
        data['primary_action'] = 'hold'
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('states', help='sample_states.py 산출물')
    ap.add_argument('--out', default='labels.json')
    ap.add_argument('--limit', type=int, default=None)
    args = ap.parse_args()

    key = os.environ.get('UPSTAGE_API_KEY')
    if not key:
        sys.exit('UPSTAGE_API_KEY 환경변수가 필요하다.')

    with open(args.states, encoding='utf-8') as f:
        states = json.load(f)
    if args.limit:
        states = states[:args.limit]

    client = OpenAI(api_key=key, base_url=BASE_URL)
    out = []
    for i, entry in enumerate(states):
        try:
            label = label_one(client, entry['state_text'])
            out.append({'id': entry['id'], 'label': label})
            print(f"[{i + 1}/{len(states)}] {label['primary_action']} "
                  f"-> lv{label.get('target_level')} | {label.get('commit_comp')}", flush=True)
        except Exception as e:
            print(f'[{i + 1}] 에러: {e}')

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    dist = Counter(item['label']['primary_action'] for item in out)
    print(f'\n{len(out)}개 라벨 저장 -> {args.out}')
    print('행동 분포:', dict(dist))
    if out:
        top = dist.most_common(1)[0]
        print(f'최다 행동 비율: {100 * top[1] / len(out):.0f}% ({top[0]})')
        print('한 행동이 80%를 넘으면 그 라벨로는 상태를 구분하는 정책을 학습할 수 없다.')


if __name__ == '__main__':
    main()
