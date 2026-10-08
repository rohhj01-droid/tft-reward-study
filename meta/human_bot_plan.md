# 사람처럼 노는 봇 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10.24에서 사람(다이아 이상)처럼 플레이하는 봇(`HumanPolicy`)을 만들고, 8명 모두 이 봇일 때의 플레이를 실제
롤체지지 자료와 같은 항목으로 잰다.

**Architecture:** 덱 봇(`meta/lobby.py`의 `DeckPolicy`)을 단계 메서드로 나눈 뒤 `HumanPolicy`가 물려받아, 아이템
(`meta/human_items.py`), 초반 전략과 레벨·리롤(`meta/human_macro.py`), 덱 고르기(`meta/human_deck.py`)를 차례로 더한다.
판 실행은 `meta/lobby.py`의 `play()` 하나를 쓰고, 측정은 `meta/play_stats.py`가 기본 봇·덱 봇·사람 봇을 같은 시드로 돌린다.

**Tech Stack:** Python 3.11 가상환경, june 시뮬레이터(TFTMuZeroAgent 포크, `fix/set4-accuracy`), numpy. 새 의존성 없음.

**Spec:** [meta/human_bot_design.md](human_bot_design.md) (curt-2 `5562b1c` 뒤 2026-10-08 수정: 선택받은 자 바꾸기,
캐리와 안정의 뜻. 2026-10-09 수정: 자리 맞추기를 구석 배치로, 시뮬레이터 전투 한계). 실제 자료와 지금 봇 측정은
[meta/set4_play.md](set4_play.md), 시뮬레이터 전투가 실제와 얼마나 맞는지는 results/README 「롤체지지 10.24 최종 보드 대전」
아래 절들.

## Global Constraints

- june 저장소는 바꾸지 않는다. 새 코드는 모두 tft-reward-study에 둔다.
- 같은 시드면 같은 판이 나와야 한다(일꾼 프로세스의 `PYTHONHASHSEED` 고정은 `meta.lobby`·`meta.play_stats`의 main이 한다).
- 사람 봇 한 판에 걸리는 시간은 같은 조건의 기본 봇의 1.5배 안쪽이어야 한다.
- 새 의존성을 넣지 않는다(표준 라이브러리와 이미 깔린 numpy만).
- 문서와 주석은 한국어 쉬운 말로 쓴다. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`을 붙인다.
- 손잡이 값의 처음 값은 설계 6절 표를 그대로 쓴다(선택받은 자 덤 10, 아이템 하나 점수 3, 티어 비중 3, 겹침 감점 장당 1,
  제비뽑기 온도 3, 갈아타기 문턱 2단계 10%·3단계 30%·4단계부터 60%, 연승형 문턱 2, 연패형 전환 체력 50, 4-1 남길 골드 20,
  4-5 남길 골드 10, 이자 지킬 골드 50, 체력 기준 40·20, 조각 많음 4개 초과). 1단계 사기 기준(두루 들어가는 정도 6)은 이
  계획에서 정했다(유닛 58종의 가운데 값).
- 각 단계(0~3)가 끝나면 기준을 넘는지 보고, 못 넘으면 다음 작업으로 가지 말고 숫자를 유저에게 보고한다.

## Review Focus

- 아이템 칸이 소모품(복제기 등)으로만 차 있을 때: 아이템 판단은 아무것도 하지 않아야 한다(Task 3의 검사).
- 목표 덱 캐리가 보드에 두 장(1성과 2성) 있을 때: 아이템은 별이 높은 쪽에 가야 한다(Task 3의 검사).
- 보드에 모래 병사 같은 소환물이 있을 때: 아이템을 소환물에게 주면 안 된다(Task 3의 검사).
- 정찰할 다른 플레이어 중 이미 탈락한 플레이어가 있을 때: 그 플레이어의 유닛은 세지 않아야 한다(Task 6의 검사).
- 덱 점수가 모두 0 이하이거나 6단계 이후일 때: 덱 고르기가 오류 없이 하나를 골라야 한다(Task 6의 검사).

## 실행 환경

모든 명령은 tft-reward-study 폴더에서 아래를 먼저 해 둔 셸로 돌린다.

```bash
PY=.venv/Scripts/python.exe        # Python 3.11 가상환경
export PYTHONIOENCODING=utf-8
export PYTHONPATH="<june 경로>;<stubs 경로>;."
OUT=<임시 폴더>                      # 저장소 밖. 비교용 결과를 둔다
```

- `<june 경로>`: june 저장소(브랜치 `fix/set4-accuracy`).
- `<stubs 경로>`: `dotenv.py` 한 파일이 든 폴더. 내용은 `def load_dotenv(*a, **k): return False` 두 줄이다(venv에
  python-dotenv가 없어서 쓰는 흉내 모듈).
- 검사 실행: `"$PY" -m meta.test_lobby`, `"$PY" -m meta.test_human_bot`. 실패하면 오류로 끝난다.

## 파일 구조

| 파일 | 맡는 일 |
|---|---|
| `meta/lobby.py` (고침) | 판 실행 `play(game, bot, knobs)`, 덱 봇 `DeckPolicy`(단계 메서드로 나눔), 덱의 캐리 `carriers`, 기록 함수 |
| `meta/play_stats.py` (고침) | 세 조건(기본·덱·사람 봇)을 같은 시드로 돌려 실제 자료와 같은 항목으로 잰다 |
| `meta/human_bot.py` (새로) | `HumanPolicy`(단계 순서, 상태, 손잡이 값 `KNOBS`)와 `attach_human` |
| `meta/human_items.py` (새로) | 아이템 판단 `item_action` |
| `meta/human_macro.py` (새로) | 초반 전략 `early_mode`, 레벨·리롤 `plan`·`action`, `stable`·`carry3`·`stay_level` |
| `meta/human_deck.py` (새로) | 덱 점수 `score`, 고르기 `choose`, 정찰 `scout`, 1단계 사기 기준 `SPREAD` |
| `meta/test_lobby.py` (고침) | 캐리 검사 하나를 더한다 |
| `meta/test_human_bot.py` (새로) | 사람 봇 검사 |

---

### Task 1: 덱 봇을 단계 메서드로 나누고 `play()`에 봇 고르기 넣기 (동작은 그대로)

**Files:**
- Modify: `meta/lobby.py` (`DeckPolicy` 전체, `play()`의 `deck_bots` 인자, 새 함수 `carriers`)
- Modify: `meta/play_stats.py` (`partial(lobby.play, deck_bots=...)` 두 곳)
- Test: `meta/test_lobby.py`

**Interfaces:**
- Produces: `lobby.carriers(board) -> list[str]` (추천 아이템을 가장 많이 드는 유닛 이름들, 보드 파일에 적힌 순서),
  `DeckPolicy` 메서드 `set_board(board)`, `fill(player, shop, mask)`, `sell(player)`, `buy(player, shop, mask)`,
  `swap(player)`, `reposition(player, game_round)`, `macro(player, game_round)`. 각 메서드는 행동 문자열이나 `None`을 돌려준다.
  `DeckPolicy.board`(목표 덱 dict). `lobby.play(game, bot='deck', knobs=None)`에서 `bot`은 `'default'`, `'deck'`, `'human'`.

- [ ] **Step 1: 바꾸기 전 결과를 남긴다**

Run: `"$PY" -m meta.lobby --games 3 --jobs 3 --out "$OUT/before.json"`
Expected: 표가 찍히고 `저장: .../before.json`

- [ ] **Step 2: 캐리 검사를 쓴다**

`meta/test_lobby.py`의 `if __name__ == '__main__':` 바로 위에 넣는다.

```python
def carriers_are_units_with_most_recommended_items_test():
    """덱의 캐리는 추천 아이템을 가장 많이 드는 유닛들이다(설계 4절)."""
    from meta.lobby import carriers
    assert carriers({'items': {'jhin': ['a', 'b', 'c'], 'riven': ['d', 'e', 'f'], 'aatrox': ['g']}}) == ['jhin', 'riven']
    assert carriers({'items': {'riven': ['a', 'b', 'c'], 'jhin': ['d', 'e']}}) == ['riven']
```

- [ ] **Step 3: 실패를 확인한다**

Run: `"$PY" -m meta.test_lobby`
Expected: `ImportError: cannot import name 'carriers'`

- [ ] **Step 4: `carriers`를 넣고 `DeckPolicy`를 나눈다**

`meta/lobby.py`에서 `completion` 함수 바로 아래에 넣는다.

```python
def carriers(board):
    """덱의 캐리: 추천 아이템을 가장 많이 드는 유닛들(보드마다 1~2명)."""
    most = max(len(held) for held in board['items'].values())
    return [u for u, held in board['items'].items() if len(held) == most]
```

`class DeckPolicy`의 `__init__`과 `__call__`을 아래로 바꾼다(`macro`는 그대로 둔다).

```python
    def __init__(self, agent, board):
        self.agent = agent
        self.moves = {}  # 라운드별 자리 맞추기 횟수. 자리가 안 맞는 보드에서 같은 이동을 되풀이하지 않게 한다
        self.set_board(board)

    def set_board(self, board):
        """목표 덱을 정한다. 사람 봇은 덱을 갈아탈 때 다시 부른다."""
        self.board = board
        self.units = set(board['units'])
        self.trait = chosen_of(board)[1]
        self.slow = board['slow']

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        return (self.fill(player, shop, mask) or self.sell(player) or self.buy(player, shop, mask)
                or self.swap(player) or self.reposition(player, game_round) or self.macro(player, game_round))

    def fill(self, player, shop, mask):
        """보드 빈자리 채우기(기본 봇 규칙)."""
        placement = self.agent.max_unit_check(player, shop, mask)
        return None if placement == ' ' else placement

    def sell(self, player):
        """벤치가 꽉 차면 덱 밖 유닛부터 판다."""
        if not player.bench_full():
            return None
        for i, u in enumerate(player.bench):
            if u.name not in self.units:
                return '4_' + str(28 + i)
        return self.agent.sell_bench_full(player)

    def buy(self, player, shop, mask):
        """덱 유닛과 덱 특성의 선택받은 자를 산다."""
        for i, unit in enumerate(shop):
            if not mask[47 + i][0]:
                continue
            if unit.endswith('_c'):  # 선택받은 자 "이름_특성_c". 값은 1성의 세 배(pool_stats.buy_cost)
                name, trait = unit.split('_')[:2]
                if name in self.units and trait == self.trait and not player.chosen and 3 * COST[name] <= player.gold:
                    return '3_' + str(i)
            elif unit in self.units and COST[unit] <= player.gold:
                return '3_' + str(i)
        return None

    def swap(self, player):
        """벤치의 덱 유닛을 보드의 덱 밖 유닛과 바꾼다. 보드에 이미 있는 유닛의 사본은 올리지 않는다."""
        on_board = {u.name for row in player.board for u in row if u}
        for i, u in enumerate(player.bench):
            if u and u.name in self.units and u.name not in on_board:
                for x, row in enumerate(player.board):
                    for y, b in enumerate(row):
                        if b and b.name in BASE_CHAMPION_LIST and b.name not in self.units:
                            return f'5_{x_y_to_1d_coord(x, y)}_{28 + i}'
        return None

    def reposition(self, player, game_round):
        """앞줄·뒷줄 자리 맞추기(기본 봇 규칙). 한 라운드에 8번까지."""
        if self.moves.get(game_round, 0) >= 8:
            return None
        for x, row in enumerate(player.board):
            for y, b in enumerate(row):
                move = b and self.agent.check_unit_location(player, x, y, b.name)
                if move:
                    self.moves[game_round] = self.moves.get(game_round, 0) + 1
                    return move
        return None
```

`play()`를 `bot` 인자로 바꾼다. 네 군데다.
1. `def play(game, deck_bots=True):` 줄을 `def play(game, bot='deck', knobs=None):`로 바꾼다.
2. docstring 첫 문장 `한 판. game = (시드, 덱 번호 8개). deck_bots=False면 덱을 정해 주지 않은 기본 봇 그대로 돈다(meta.play_stats).`를
   `한 판. game = (시드, 덱 번호 8개). bot은 'default'(덱을 정해 주지 않은 기본 봇), 'deck'(덱 봇), 'human'(사람 봇).`으로 바꾼다.
3. 함수 안의 `if deck_bots:` 두 곳(`_register()` 앞, `attach` 반복 앞)을 `if bot == 'deck':`로 바꾼다.
4. `if deck_bots and game_round >= 11`을 `if bot == 'deck' and game_round >= 11`로 바꾼다.

`knobs`는 Task 2에서 사람 봇에 넘긴다. `meta/play_stats.py`의 조건 반복을 아래로 바꾼다.

```python
    for label, bot in (('기본 봇', 'default'), ('덱 봇', 'deck')):
        with Pool(args.jobs) as workers:  # 조건마다 새 일꾼(덱 봇의 덱 목록 등록이 기본 봇에 새지 않게)
            results = workers.map(partial(lobby.play, bot=bot), games, chunksize=1)
```

- [ ] **Step 5: 검사와 같은 결과를 확인한다**

Run: `"$PY" -m meta.test_lobby`
Expected: `PASS` 10줄

Run: `"$PY" -m meta.lobby --games 3 --jobs 3 --out "$OUT/after.json"`
Run: `"$PY" -c "import json,sys; r=lambda f: json.load(open(f,encoding='utf-8'))['rows']; print('같음' if r(sys.argv[1])==r(sys.argv[2]) else '다름')" "$OUT/before.json" "$OUT/after.json"`
Expected: `같음`

Run: `"$PY" -m meta.play_stats --games 2 --jobs 2`
Expected: 표가 찍히고 오류 없음

- [ ] **Step 6: 커밋한다**

```bash
git add meta/lobby.py meta/play_stats.py meta/test_lobby.py
git commit -m "meta: 덱 봇을 단계 메서드로 나누고 play()에 봇 고르기(동작 그대로)

사람 봇이 덱 봇의 단계를 물려받아 쓰도록 DeckPolicy를 fill·sell·buy·swap·reposition·macro로 나눴다. 덱의 캐리를
뜻하는 carriers를 lobby에 두었다. play(game, deck_bots)를 play(game, bot, knobs)로 바꿨다. 같은 시드 3판 결과가 그대로다.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 측정 늘리기와 사람 봇 뼈대 (0단계)

**Files:**
- Create: `meta/human_bot.py`
- Create: `meta/test_human_bot.py`
- Modify: `meta/lobby.py` (`play()` 전체, 새 함수 `carry_share`, `board_record`)
- Modify: `meta/play_stats.py` (파일 전체)

**Interfaces:**
- Consumes: Task 1의 `DeckPolicy`, `carriers`, `play(game, bot, knobs)`.
- Produces: `HumanPolicy.reposition(player, game_round) -> str | None`(구석 배치, 덱 봇의 것을 덮어씀),
  `human_bot.attach_human(player, others, rng, knobs=None, board=None) -> HumanPolicy`,
  `human_bot.KNOBS: dict`, `HumanPolicy(agent, board, others, rng, knobs)` 속성 `board`, `mode`(None·'win'·'lose'),
  `rebuilt`(bool), `switches`(int), `choose_decks`(bool, `board`를 안 주면 True).
  `play()`가 돌려주는 `players` 항목에 `carry21`, `mode`, `switches`를 더하고, `curve` 항목을
  `(칸, 레벨, 골드, 체력, 초반 전략)` 다섯 값으로 늘린다. `board_record`에 `completed_all`, `components_all`을 더한다.

- [ ] **Step 1: 사람 봇 검사를 쓴다**

`meta/test_human_bot.py`를 만든다.

```python
"""
사람 봇(meta/human_bot.py) 검사.

실행: python -m meta.test_human_bot
"""
import random
from types import SimpleNamespace as Unit

from Simulator.item_stats import item_builds
from meta.test_lobby import OPEN, SHARPSHOOTERS, deck_player

FULL = [[1] * 37 for _ in range(60)]  # 상점·아이템을 모두 허락하는 마스크(mask[47 + i][0], mask[37 + 칸][유닛 칸])


def attach_human_takes_over_from_round_one_test():
    """사람 봇은 1라운드부터 정책을 맡는다(덱 봇은 11라운드까지 기본 봇이었다)."""
    from meta.human_bot import attach_human
    p = deck_player(['jhin'])
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(1, ['garen', 'vayne', 'garen', 'garen', 'garen'], OPEN) == '3_1'
    assert policy.choose_decks is False and policy.switches == 0


def human_bot_puts_ranged_carry_in_back_corner_test():
    """자리 맞추기는 구석 배치다(analysis.battle.corner_positions): 원거리는 뒷줄 구석부터 아이템 많은 순, 근접은 앞줄
    가운데부터. 자리가 맞으면 아무것도 하지 않는다."""
    from Simulator.utils import x_y_to_1d_coord
    from meta.human_bot import attach_human
    p = deck_player(['garen', 'jinx'])  # 가렌 (0, 0), 징크스 (1, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) == f'5_{x_y_to_1d_coord(0, 0)}_{x_y_to_1d_coord(3, 3)}'  # 근접은 앞줄 가운데로
    p = deck_player(['jinx'])  # 원거리 하나가 이미 뒷줄 구석 (0, 0)
    policy = attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert policy.reposition(p, 12) is None


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.endswith('_test'):
            test()
            print('PASS', name)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `ModuleNotFoundError: No module named 'meta.human_bot'`

- [ ] **Step 3: 사람 봇 뼈대를 만든다**

`meta/human_bot.py`를 만든다.

```python
"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

지금(0단계)은 덱 봇(meta.lobby.DeckPolicy)과 같은 규칙을 1라운드부터 쓰고, 자리 맞추기만 구석 배치다. 아이템(1단계),
초반 전략과 레벨·리롤(2단계), 덱 고르기(3단계)를 차례로 더한다.
"""
from analysis.battle import corner_positions
from Simulator.utils import x_y_to_1d_coord
from meta.lobby import DeckPolicy

KNOBS = {}  # 손잡이 값(설계 6절). 단계마다 채운다


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

    def reposition(self, player, game_round):
        """자리 맞추기(설계 1절 7번): 원거리는 뒷줄 구석부터 아이템 많은 순, 근접은 앞줄 가운데부터
        (analysis.battle.corner_positions). 한 라운드에 8번까지. 자리가 다른 첫 유닛을 제자리로 옮긴다(그 칸에 유닛이
        있으면 맞바꾼다). 유닛 순서를 이름순으로 고정해서, 옮긴 뒤 아이템 수가 같은 유닛끼리 자리를 계속 바꾸지 않게 한다."""
        if self.moves.get(game_round, 0) >= 8:
            return None
        units = sorted(((x, y, u) for x, row in enumerate(player.board) for y, u in enumerate(row)
                        if u and u.name != 'sandguard'), key=lambda t: (t[2].name, -t[2].stars))
        for (x, y, _), (tx, ty) in zip(units, corner_positions([u for _, _, u in units])):
            target = player.board[tx][ty]
            if (x, y) != (tx, ty) and not (target and target.name == 'sandguard'):
                self.moves[game_round] = self.moves.get(game_round, 0) + 1
                return f'5_{x_y_to_1d_coord(x, y)}_{x_y_to_1d_coord(tx, ty)}'
        return None


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고(0~2단계), 주지 않으면 스스로 고른다(3단계)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
```

- [ ] **Step 4: 검사가 통과하는지 본다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `PASS attach_human_takes_over_from_round_one_test`, `PASS human_bot_puts_ranged_carry_in_back_corner_test`

- [ ] **Step 5: `play()`에 사람 봇과 새 기록을 넣는다**

`meta/lobby.py`의 `board_record`를 아래로 바꾸고, 그 아래에 `carry_share`를 넣는다.

```python
def board_record(player):
    """보드 기록: 레벨, 유닛(이름, 비용, 별, 완성 아이템 수), 켜진 특성 인원, 선택받은 자 특성, 들고 있는 아이템 수.
    completed_all·components_all은 보드·벤치 유닛과 아이템 칸 전부의 완성 아이템·조각 수다(주걱·소모품 제외)."""
    units = [u for row in player.board for u in row if u and u.name in BASE_CHAMPION_LIST]
    everyone = [u for row in player.board for u in row if u] + [u for u in player.bench if u]
    held = [i for u in everyone for i in u.items] + [i for i in player.item_bench if i]
    return {'level': player.level,
            'units': [[u.name, u.cost, u.stars, sum(i in item_builds for i in u.items)] for u in units],
            'traits': {t: n for t, n in player.team_composition.items() if player.team_tiers.get(t, 0) > 0},
            'chosen': player.chosen or None,
            'completed_all': sum(_worth(i) == 2 for i in held), 'components_all': sum(_worth(i) == 1 for i in held)}


def carry_share(player, board):
    """목표 덱 캐리 중 보드에서 완성 아이템을 하나 이상 든 비율(보드에 없는 캐리는 못 든 것으로 센다).
    목표 덱이 없으면 None."""
    if board is None:
        return None
    holding = {u.name for row in player.board for u in row if u and any(_worth(i) == 2 for i in u.items)}
    names = carriers(board)
    return sum(c in holding for c in names) / len(names)
```

`play()` 전체를 아래로 바꾼다.

```python
def play(game, bot='deck', knobs=None):
    """한 판. game = (시드, 덱 번호 8개). bot은 'default'(덱을 정해 주지 않은 기본 봇), 'deck'(덱 봇),
    'human'(사람 봇, meta/human_bot.py). knobs는 사람 봇 손잡이 값을 바꿀 때 쓴다(meta.play_stats --knob).
    돌려주는 값: {'curve': [(칸, 레벨, 골드, 체력, 초반 전략), ...] 살아 있는 봇이 그 칸에서 처음 움직일 때,
                 'players': [{'deck', 'place', 'complete', 'complete21', 'carry21', 'mode', 'switches', 'board'}, ...]}
    탈락 때 완성도(complete)는 일찍 죽은 덱일수록 낮게 나와 등수와 엉킨다. 그래서 5단계 시작(21번째 칸) 때 살아 있던
    봇의 완성도(complete21)와 캐리 아이템 비율(carry21)을 따로 잰다(그 전에 탈락하면 None). board는 탈락하거나 끝날
    때의 board_record다. 덱 번호는 덱 봇과 0~2단계 사람 봇의 목표 덱이다."""
    seed, decks = game
    sim_config.LOGMESSAGES = False  # 켜 두면 실행한 곳에 log.txt가 생긴다
    if bot == 'deck':
        _register()
    random.seed(seed)
    np.random.seed(seed)
    with quiet():
        env = parallel_env(TFTConfig(observation_class=ObservationToken,
                                     max_actions_per_round=config.ACTIONS_PER_TURN))
        obs, info = env.reset(options={'default_agent': [True] * N_PLAYERS})
        deck_of = dict(zip(info, decks))
        players = {a: info[a]['player'] for a in info}
        policies = {}
        if bot == 'deck':
            for a, deck in deck_of.items():
                players[a].default_agent.comp_number = FIRST_DECK + deck
                policies[a] = attach(players[a], BOARDS[deck])
        elif bot == 'human':
            from meta.human_bot import attach_human  # human_bot이 이 파일을 불러서, 여기서 늦게 부른다
            for i, (a, deck) in enumerate(deck_of.items()):
                others = [players[o] for o in players if o != a]
                policies[a] = attach_human(players[a], others, random.Random(seed * N_PLAYERS + i), knobs,
                                           board=BOARDS[deck])
        mode = lambda a: getattr(policies.get(a), 'mode', None)
        curve, seen, handed, placement, done, mid, carry, boards = [], set(), {}, {}, {}, {}, {}, {}
        rank, guard = N_PLAYERS, 0
        # 종료 신호를 놓치면 루프가 안 끝난다(fullgame/ab_test.py와 같은 상한). 상한에 걸린 판은 아래에서 등수를 메운다.
        while obs and guard < 5000:
            guard += 1
            alive = list(obs)
            actions = []
            for a in alive:
                game_round, p = info[a]['game_round'], players[a]
                if (a, game_round) not in seen:
                    seen.add((a, game_round))
                    curve.append((game_round, p.level, p.gold, p.health, mode(a)))
                if game_round >= 21 and a not in mid:
                    mid[a] = completion(p, BOARDS[deck_of[a]])
                    carry[a] = carry_share(p, getattr(policies.get(a), 'board', None))
                if bot == 'deck' and game_round >= 11 and handed.get(a) != game_round:
                    hand_out_items(p, BOARDS[deck_of[a]]['items'])
                    handed[a] = game_round
                actions.append(p.default_policy(game_round, info[a]['shop'], obs[a]['action_mask']))
            decoded = utils.decode_action(actions)
            obs, _, terminated, _, info = env.step({a: decoded[i] for i, a in enumerate(alive)})
            for a, ended in terminated.items():
                if ended and a not in placement:
                    placement[a], rank = rank, rank - 1
                    done[a], boards[a] = completion(players[a], BOARDS[deck_of[a]]), board_record(players[a])
    for a in deck_of:  # 끝까지 terminated가 안 온 플레이어
        if a not in placement:
            placement[a], rank = rank, rank - 1
            done[a], boards[a] = completion(players[a], BOARDS[deck_of[a]]), board_record(players[a])
    return {'curve': curve,
            'players': [{'deck': deck_of[a], 'place': placement[a], 'complete': done[a], 'complete21': mid.get(a),
                         'carry21': carry.get(a), 'mode': mode(a), 'switches': getattr(policies.get(a), 'switches', 0),
                         'board': boards[a]} for a in deck_of]}
```

- [ ] **Step 6: `play_stats`를 세 조건과 새 항목으로 바꾼다**

`meta/play_stats.py` 전체를 아래로 바꾼다.

```python
"""
봇의 플레이를 실제 10.24 플레이(meta/set4_play.md)와 같은 항목으로 잰다.

세 조건을 같은 시드로 돌린다. 기본 봇(덱을 정해 주지 않음), 덱 봇(meta.lobby의 정책과 아이템 나눠 주기),
사람 봇(meta/human_bot.py).
- 라운드마다 살아 있는 봇의 레벨, 골드, 체력. 「그 라운드에 올린 뒤」 레벨을 보려고 다음 칸 시작 때 값을 쓴다.
  사람 봇은 초반 전략(연승형·연패형)별로도 나눠 본다.
- 탈락하거나 끝날 때의 보드: 유닛 수, 비용별 별, 완성 아이템 수, 켜진 특성, 선택받은 자 특성, 아이템을 완성으로 쓴 비율.
- 5단계 시작 때 목표 덱 캐리가 아이템을 든 비율, 덱 계열별 비율과 평균 등수.
실제 쪽은 롤체지지 1등 보드 25개와 메타 트렌드(meta/lolchess_10.24_2020-11-28.json)다.

실행: python -m meta.play_stats --games 100 --jobs 7 --out results/play_stats_1024.json
      python -m meta.play_stats --games 400 --conditions human --knob tier_weight=0 --out ...
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from functools import partial
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meta import lobby
from set4 import cost_of

REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolchess_10.24_2020-11-28.json')
CONDITIONS = {'default': '기본 봇', 'deck': '덱 봇', 'human': '사람 봇'}
# (다음 칸 번호, 이름, 가이드의 표준 레벨). 칸 3 = 2-1이고 한 스테이지가 6칸이다(4-5는 18번째 칸).
CHECKPOINTS = [(4, '2-1 뒤', '4'), (11, '3-2 뒤', '6'), (16, '4-1 뒤', '7'), (19, '4-5 뒤', '7~8'),
               (22, '5-1 뒤', '8'), (28, '6-1 뒤', '8~9')]
# 덱 계열: 앞에서부터 처음 맞는 것(meta/set4_play.md의 분류와 같다). 두 번째 값은 그 계열로 볼 선택받은 자 특성.
FAMILIES = [('dusk', 4, {'dusk'}), ('ninja', 4, {'ninja', 'shade'}), ('duelist', 6, {'duelist'}),
            ('cultist', 6, {'cultist'}), ('warlord', 6, {'warlord'}), ('sharpshooter', 4, {'sharpshooter'}),
            ('divine', 4, {'divine'}), ('hunter', 3, {'hunter'}), ('elderwood', 3, {'elderwood'}),
            ('fortune', 3, {'fortune'}), ('mystic', 4, {'mystic'}), ('brawler', 4, {'brawler'})]
COMPONENTS = {'B.F. Sword', 'Chain Vest', "Giant's Belt", 'Needlessly Large Rod', 'Negatron Cloak', 'Recurve Bow',
              'Sparring Gloves', 'Spatula', 'Tear of the Goddess'}


def family(traits):
    return next(((name, chosen) for name, n, chosen in FAMILIES if traits.get(name, 0) >= n), ('other', set()))


def real_winners():
    """롤체지지 1등 보드를 board_record와 같은 모양으로 바꾼다. 레벨은 모르므로 유닛 수로 둔다."""
    boards = []
    for w in json.load(open(REAL, encoding='utf-8'))['winners']:
        units = []
        for u in w['units']:
            name = u['name'].lower().replace(' ', '').replace("'", '')
            units.append([name, cost_of(name), u['stars'], sum(i not in COMPONENTS for i in u['items'])])
        traits = {t.split(' ', 1)[1].lower(): int(t.split(' ', 1)[0]) for t in w['traits']}
        chosen = w['chosen_trait'].lower() if w['chosen_trait'] else None
        boards.append({'level': len(units), 'units': units, 'traits': traits, 'chosen': chosen})
    return boards


def real_families():
    """롤체지지 메타 트렌드를 계열로 묶은 (계열, 27개 조합 안 몫, 평균 등수)."""
    rows = defaultdict(lambda: [0.0, 0.0])
    for t in json.load(open(REAL, encoding='utf-8'))['trends']:
        name = family({k.lower(): v for k, v in t['traits'].items()})[0]
        rows[name][0] += t['pick_rate']
        rows[name][1] += t['pick_rate'] * t['average_placement']
    return sorted(((f, s, w / s) for f, (s, w) in rows.items()), key=lambda r: -r[1])


def curve_table(curves, mode=None):
    at = defaultdict(list)
    for curve in curves:
        for slot, level, gold, hp, m in curve:
            if mode is None or m == mode:
                at[slot].append((level, gold, hp))
    rows = []
    for slot, name, guide in CHECKPOINTS:
        v = at.get(slot)
        if v:
            share = lambda k: sum(lv >= k for lv, _, _ in v) / len(v)
            rows.append({'when': name, 'guide': guide, 'alive': len(v), 'level': statistics.mean(x[0] for x in v),
                         'lv7': share(7), 'lv8': share(8), 'lv9': share(9),
                         'gold': statistics.mean(x[1] for x in v), 'hp': statistics.mean(x[2] for x in v)})
    return rows


def board_summary(boards):
    stars = Counter((cost, star) for b in boards for _, cost, star, _ in b['units'])
    two_plus = {c: sum(v for (cost, s), v in stars.items() if cost == c and s >= 2) /
                max(1, sum(v for (cost, _), v in stars.items() if cost == c)) for c in (4, 5)}
    items = [sum(u[3] for u in b['units']) for b in boards]
    fams = [family(b['traits']) for b in boards]
    with_chosen = [(b['chosen'], f) for b, f in zip(boards, fams) if b['chosen'] and f[0] != 'other']
    worth = [(2 * b['completed_all'], 2 * b['completed_all'] + b['components_all']) for b in boards if 'completed_all' in b]
    return {'boards': len(boards), 'units': dict(sorted(Counter(min(len(b['units']), 10) for b in boards).items())),
            'nine_plus': sum(len(b['units']) >= 9 for b in boards) / len(boards),
            'two_star_4cost': two_plus[4], 'two_star_5cost': two_plus[5],
            'three_star_per_board': sum(v for (_, s), v in stars.items() if s == 3) / len(boards),
            'items_median': statistics.median(items),
            'item_use': (sum(a for a, _ in worth) / max(1, sum(b for _, b in worth))) if worth else None,
            'item_worth': statistics.mean(b for _, b in worth) if worth else None,
            'chosen_kinds': len({b['chosen'] for b in boards if b['chosen']}),
            'chosen_off_family': (sum(c not in f[1] for c, f in with_chosen) / len(with_chosen)) if with_chosen else None,
            'no_family': sum(f[0] == 'other' for f in fams) / len(boards),
            'families': Counter(f[0] for f in fams).most_common()}


def family_table(players):
    """(계열, 마지막 보드 몫, 평균 등수)."""
    rows = defaultdict(list)
    for p in players:
        rows[family(p['board']['traits'])[0]].append(p['place'])
    return sorted(((f, len(v) / len(players), statistics.mean(v)) for f, v in rows.items()), key=lambda r: -r[1])


def fmt(v, pct=True):
    """None은 '-', 실수는 pct면 백분율·아니면 소수 둘째 자리, 그 밖은 그대로."""
    if v is None:
        return '-'
    if isinstance(v, float):
        return f'{v * 100:.0f}%' if pct else f'{v:.2f}'
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=100)
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--conditions', default='default,deck,human', help='쉼표로: default, deck, human')
    ap.add_argument('--knob', action='append', default=[], help='사람 봇 손잡이 값 바꾸기, 예: tier_weight=0')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    knobs = {k: float(v) for k, v in (kv.split('=') for kv in args.knob)}

    rng = random.Random(args.seed)
    games = [(args.seed * 100000 + g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(args.games)]
    os.environ['PYTHONHASHSEED'] = str(args.seed)  # meta.lobby와 같은 이유로 일꾼의 해시를 고정한다
    out = {'games': args.games, 'seed': args.seed, 'knobs': knobs, 'real_winners': board_summary(real_winners()),
           'real_families': real_families()}
    for key in args.conditions.split(','):
        label = CONDITIONS[key]
        start = time.perf_counter()
        with Pool(args.jobs) as workers:  # 조건마다 새 일꾼(덱 봇의 덱 목록 등록이 다른 조건에 새지 않게)
            results = workers.map(partial(lobby.play, bot=key, knobs=knobs), games, chunksize=1)
        players = [p for r in results for p in r['players']]
        curves = [r['curve'] for r in results]
        carry = [p['carry21'] for p in players if p['carry21'] is not None]
        modes = defaultdict(list)
        for p in players:
            modes[p['mode']].append(p['place'])
        out[label] = {'seconds': time.perf_counter() - start, 'curve': curve_table(curves),
                      'curve_win': curve_table(curves, 'win'), 'curve_lose': curve_table(curves, 'lose'),
                      'winners': board_summary([p['board'] for p in players if p['place'] == 1]),
                      'all': board_summary([p['board'] for p in players]),
                      'carry21': statistics.mean(carry) if carry else None,
                      'modes': {str(m): [len(v), statistics.mean(v)] for m, v in modes.items()},
                      'switches': statistics.mean(p['switches'] for p in players),
                      'families': family_table(players),
                      'winner_boards': [p['board'] for p in players if p['place'] == 1]}

    for label in [CONDITIONS[k] for k in args.conditions.split(',')]:
        o = out[label]
        print(f'\n[{label}] {args.games}판 {o["seconds"]:.0f}초, 캐리 아이템(5단계) {fmt(o["carry21"])}, '
              f'아이템 완성 비율(전체 보드) {fmt(o["all"]["item_use"])}, 받은 아이템(조각으로) {fmt(o["all"]["item_worth"], False)}, '
              f'덱 갈아타기 {o["switches"]:.2f}번/명')
        for tag, rows in (('전체', o['curve']), ('연승형', o['curve_win']), ('연패형', o['curve_lose'])):
            for r in rows:
                print(f'  {tag:4} {r["when"]:7} 가이드 {r["guide"]:>4} | 레벨 {r["level"]:.2f} 7+ {fmt(r["lv7"])} '
                      f'8+ {fmt(r["lv8"])} 9 {fmt(r["lv9"])} 골드 {r["gold"]:.1f} 체력 {r["hp"]:.1f} (살아 있음 {r["alive"]})')
        print('  초반 전략별 (명, 평균 등수):', o['modes'])
        print('  계열 (몫, 평균 등수):', [(f, fmt(s), round(a, 2)) for f, s, a in o['families'][:8]])
    print('\n실제 메타 트렌드 계열 (몫, 평균 등수):', [(f, fmt(s), round(a, 2)) for f, s, a in out['real_families']])
    print('\n1등 보드')
    keys = [('boards', '보드 수', False), ('nine_plus', '9유닛 이상', True), ('two_star_4cost', '4코스트 2성 이상', True),
            ('two_star_5cost', '5코스트 2성 이상', True), ('three_star_per_board', '보드당 3성', False),
            ('items_median', '완성 아이템 가운데 값', False), ('chosen_kinds', '선택받은 자 특성 가짓수', False),
            ('chosen_off_family', '선택받은 자가 계열 특성이 아닌 비율', True), ('no_family', '큰 특성 없는 보드', True)]
    columns = [('실제 1등', out['real_winners'])] + [(CONDITIONS[k] + ' 1등', out[CONDITIONS[k]]['winners'])
                                                  for k in args.conditions.split(',')]
    for key, name, pct in keys:
        print(f'  {name}: ' + ' / '.join(f'{label}: {fmt(s[key], pct)}' for label, s in columns))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 7: 0단계 기준을 확인한다**

Run: `"$PY" -m meta.test_lobby && "$PY" -m meta.test_human_bot`
Expected: `PASS` 10줄, `PASS` 1줄

Run: `"$PY" -m meta.play_stats --games 20 --jobs 7 --out "$OUT/stage0_a.json"`
Run: `"$PY" -m meta.play_stats --games 20 --jobs 7 --out "$OUT/stage0_b.json"`
Run: `"$PY" -c "import json,sys; r=lambda f: json.load(open(f,encoding='utf-8'))['사람 봇']['winner_boards']; print('같음' if r(sys.argv[1])==r(sys.argv[2]) else '다름')" "$OUT/stage0_a.json" "$OUT/stage0_b.json"`
Expected:
- 두 실행 모두 오류 없이 표가 찍힌다(판이 끝까지 돈다).
- `같음`(같은 시드면 같은 판).
- 첫 줄의 `[사람 봇] 20판 N초`가 `[기본 봇] 20판 M초`의 1.5배 이하.
- 기준을 못 넘으면 Task 3으로 가지 말고 숫자를 유저에게 보고한다.

- [ ] **Step 8: 커밋한다**

```bash
git add meta/human_bot.py meta/test_human_bot.py meta/lobby.py meta/play_stats.py
git commit -m "meta: 사람 봇 뼈대(0단계)와 측정 늘리기

HumanPolicy를 덱 봇 규칙으로 1라운드부터 쓰게 붙였다(meta/human_bot.py). 자리 맞추기만 구석 배치(원거리는 뒷줄
구석부터 아이템 많은 순, analysis.battle.corner_positions)다. play()에 사람 봇 조건과 기록(5단계 캐리
아이템 비율, 초반 전략, 덱 갈아타기 수, 들고 있는 아이템 수)을 더하고, play_stats를 세 조건·조건 고르기·손잡이 값
바꾸기·걸린 시간·계열별 등수로 늘렸다. 0단계 기준(끝까지 돎, 같은 시드 같은 판, 시간 1.5배 안쪽)을 확인했다.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 아이템 판단 `meta/human_items.py`

**Files:**
- Create: `meta/human_items.py`
- Test: `meta/test_human_bot.py`

**Interfaces:**
- Consumes: `lobby.carriers(board)`.
- Produces: `human_items.item_action(player, board, mode, game_round, mask) -> str | None`. `board`는 목표 덱 dict 또는
  `None`, `mode`는 `'win'`/`'lose'`, 돌려주는 값은 `'6_<유닛 칸>_<아이템 칸>'` 또는 `None`. 유닛 칸은 보드 `x*4+y`.
  `human_items.DEFENSIVE: list[str]`.

- [ ] **Step 1: 아이템 검사를 쓴다**

`meta/test_human_bot.py`의 `if __name__ == '__main__':` 바로 위에 넣는다.

```python
def item_player(board_units, item_bench, bench_units=()):
    """보드 x칸 0줄에 유닛을 놓은 가짜 플레이어. x번째 유닛의 칸 번호는 4x다."""
    board = [[None] * 4 for _ in range(7)]
    for x, u in enumerate(board_units):
        board[x][0] = u
    return Unit(board=board, bench=list(bench_units) + [None] * (9 - len(bench_units)),
                item_bench=list(item_bench) + [None] * (10 - len(item_bench)))


GA = item_builds['guardian_angel']
NO_TANK_DECK = {'name': 'x', 'tier': 'B', 'slow': False, 'units': ['jhin', 'vayne'], 'items': {'jhin': ['infinity_edge']}}


def builds_carry_item_on_carrier_test():
    """목표 덱 추천 아이템의 두 조각이 다 있으면 캐리에게 첫 조각을 올린다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[]), Unit(name='garen', stars=1, items=[])], [GA[1], GA[0]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_0_1'


def finishes_started_item_test():
    """조각 하나를 든 유닛이 있고 합칠 조각이 아이템 칸에 있으면 마저 올린다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[GA[0]])], [GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_0_0'


def carry_item_goes_to_holder_when_carrier_absent_test():
    """캐리가 없으면 보드의 덱 밖 유닛 중 별이 가장 높은 유닛(맡아 둘 유닛)에게 만든다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='vayne', stars=1, items=[]), Unit(name='garen', stars=2, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def holds_components_without_holder_test():
    """캐리도 맡아 둘 유닛(덱 밖 유닛)도 없고 조각이 4개 이하면 들고 있는다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='vayne', stars=1, items=[]), Unit(name='teemo', stars=1, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'lose', 12, FULL) is None


def gives_completed_item_to_carrier_test():
    """아이템 칸의 완성 아이템(맡긴 유닛을 팔아 돌아온 것)은 캐리에게 준다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='jhin', stars=2, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def win_mode_slams_defensive_item_on_one_cost_frontliner_test():
    """연승형은 2~3단계에 앞줄 유닛이면 1코스트 2성에게도 방어 아이템을 만든다(유저 제안)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[])], list(item_builds['sunfire_cape']))
    assert item_action(p, NO_TANK_DECK, 'win', 5, FULL) == '6_0_0'


def lose_mode_holds_defensive_components_test():
    """연패형은 방어 아이템을 미리 만들지 않는다(조각 4개 이하)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='garen', stars=2, items=[])], list(item_builds['sunfire_cape']))
    assert item_action(p, NO_TANK_DECK, 'lose', 5, FULL) is None


def builds_something_with_more_than_four_components_test():
    """조각이 5개 이상이면 연패형이어도 하나를 만든다. 덱 아이템(무한의 대검)도 방어 아이템도 안 되는 조각들이라
    4번 규칙(아무 완성 아이템)을 탄다."""
    from meta.human_items import item_action
    comps = ['bf_sword', 'recurve_bow', 'needlessly_large_rod', 'tear_of_the_goddess', 'giants_belt']
    p = item_player([Unit(name='garen', stars=2, items=[])], comps)
    assert item_action(p, NO_TANK_DECK, 'lose', 12, FULL).startswith('6_0_')


def does_not_start_item_on_unit_holding_component_test():
    """조각을 든 유닛에는 새로 만들지 않는다. 캐리가 주걱 하나를 들고 있으면 맡아 둘 유닛에게 만든다."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=['spatula']), Unit(name='garen', stars=1, items=[])], [GA[0], GA[1]])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def ignores_consumables_test():
    """아이템 칸이 소모품으로만 차 있으면 아무것도 하지 않는다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=2, items=[])], ['champion_duplicator'] * 10)
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) is None


def gives_item_to_higher_star_copy_test():
    """캐리가 두 장(1성, 2성) 있으면 별이 높은 쪽에 준다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='jhin', stars=1, items=[]), Unit(name='jhin', stars=2, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) == '6_4_0'


def never_gives_items_to_summons_test():
    """모래 병사 같은 소환물에는 아이템을 주지 않는다(Review Focus)."""
    from meta.human_items import item_action
    p = item_player([Unit(name='sandguard', stars=1, items=[])], ['infinity_edge'])
    assert item_action(p, SHARPSHOOTERS, 'win', 12, FULL) is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `ModuleNotFoundError: No module named 'meta.human_items'`

- [ ] **Step 3: 아이템 판단을 만든다**

`meta/human_items.py`를 만든다.

```python
"""
사람 봇의 아이템 판단(meta/human_bot_design.md 5절). item_action은 행동 하나("6_유닛칸_아이템칸") 또는 None을 돌려준다.

위에서부터 처음 맞는 것 하나를 한다.
0. 만들다 만 아이템 마저 만들기: 보드 유닛의 마지막 아이템이 조각이고, 합쳐질 조각이 아이템 칸에 있으면 올린다.
   회전초밥 유닛이 조각을 들고 온 경우도 여기서 마무리한다. 덱 아이템, 방어 아이템이 되는 짝을 먼저 고른다.
1. 아이템 칸의 완성 아이템 주기(맡겨 둔 유닛을 팔아 돌아온 것 등): 덱 캐리 아이템이면 캐리, 방어 아이템이면 앞줄,
   그 밖은 별이 가장 높은 유닛.
2. 목표 덱 캐리 아이템 만들기: 두 조각이 다 있으면 캐리에게(없으면 맡아 둘 유닛에게) 첫 조각을 올린다.
   맡아 둘 유닛은 보드의 목표 덱 밖 유닛 중 별이 가장 높은 유닛이고, 없으면 만들지 않는다.
3. 방어 아이템(연승형, 2~3단계): 앞줄 유닛(1코스트 2성 포함)에게 첫 조각을 올린다.
4. 조각이 4개를 넘으면: 방어 아이템(전략·단계와 상관없이), 그다음 아무 완성 아이템 순서로 하나를 시작한다.
시뮬레이터는 조각 둘을 같은 유닛에 연달아 올리면 합친다. 그래서 첫 조각을 올린 다음 행동에서 0이 마저 올린다.
"""
from collections import Counter

from Simulator.default_agent_stats import FRONT_LINE_UNITS
from Simulator.item_stats import basic_items, item_builds, trait_items
from Simulator.stats import BASE_CHAMPION_LIST, round_stage
from Simulator.utils import x_y_to_1d_coord
from meta.lobby import carriers

DEFENSIVE = ['sunfire_cape', 'gargoyle_stoneplate', 'bramble_vest', 'dragons_claw', 'warmogs_armor']
# 만들지도 주지도 않는 것: 주걱과 주걱으로 만든 것(특성 아이템, 자연의 힘), 도적의 장갑(설계 5절)
SKIP = {'spatula', 'thieves_gloves', 'force_of_nature'} | set(trait_items.values())
PAIR = {tuple(sorted(parts)): item for item, parts in item_builds.items()
        if item not in SKIP and not SKIP & set(parts)}


def _board(player):
    """(유닛 칸, 유닛) 목록. 소환물(모래 병사 등)은 뺀다."""
    return [(x_y_to_1d_coord(x, y), u) for x, row in enumerate(player.board) for y, u in enumerate(row)
            if u and u.name in BASE_CHAMPION_LIST]


def _room(u):
    """완성 아이템을 더 받을 수 있는지."""
    return len(u.items) < 3 and 'thieves_gloves' not in u.items


def _open(u):
    """새로 만들기 시작할 수 있는지: 자리가 있고 조각 하나를 들고 있지 않다."""
    return _room(u) and not (u.items and u.items[-1] in basic_items)


def _best(cands):
    """별이 가장 높은 유닛의 칸. 후보가 없으면 None."""
    return max(cands, key=lambda cu: cu[1].stars)[0] if cands else None


def _held_completed(player):
    everyone = [u for row in player.board for u in row if u] + [u for u in player.bench if u]
    held = [it for u in everyone for it in u.items] + [it for it in player.item_bench if it]
    return Counter(it for it in held if it in item_builds and it not in SKIP)


def _recipient(player, board, item, starting):
    """아이템을 줄 유닛 칸. 캐리 아이템이면 캐리 → 맡아 둘 유닛, 방어 아이템이면 앞줄, 그 밖은 별이 높은 유닛."""
    fits = _open if starting else _room
    units = [(c, u) for c, u in _board(player) if fits(u)]
    names = carriers(board) if board else []
    if any(item in board['items'][n] for n in names):
        carrier = [(c, u) for c, u in units if u.name in names and item in board['items'][u.name]]
        if carrier:
            return _best(carrier)
        return _best([(c, u) for c, u in units if u.name not in board['units']])
    if item in DEFENSIVE:
        front = [(c, u) for c, u in units if u.name in FRONT_LINE_UNITS]
        if front:
            return _best(front)
    return _best(units)


def item_action(player, board, mode, game_round, mask):
    ok = lambda idx, coord: coord is not None and bool(mask[37 + idx][coord])
    comps = [(i, it) for i, it in enumerate(player.item_bench) if it in basic_items and it not in SKIP]
    deck_items = {it for held in board['items'].values() for it in held} if board else set()

    for coord, u in _board(player):  # 0. 만들다 만 아이템 마저 만들기
        if u.items and u.items[-1] in basic_items and len(u.items) <= 3:
            partners = [(idx, PAIR[key]) for idx, c in comps
                        if (key := tuple(sorted((u.items[-1], c)))) in PAIR]
            partners.sort(key=lambda p: (p[1] not in deck_items, p[1] not in DEFENSIVE))
            for idx, _ in partners:
                if ok(idx, coord):
                    return f'6_{coord}_{idx}'

    for idx, it in enumerate(player.item_bench):  # 1. 아이템 칸의 완성 아이템 주기
        if it in item_builds and it not in SKIP:
            coord = _recipient(player, board, it, starting=False)
            if ok(idx, coord):
                return f'6_{coord}_{idx}'

    slots = {}
    for idx, c in comps:
        slots.setdefault(c, []).append(idx)

    def start(item, coord):
        """item의 두 조각이 아이템 칸에 있으면 coord의 유닛에게 첫 조각을 올리는 행동."""
        a, b = item_builds[item]
        if len(slots.get(a, [])) >= 1 + (a == b) and slots.get(b) and ok(slots[a][0], coord):
            return f'6_{coord}_{slots[a][0]}'
        return None

    def defensive():
        coord = _best([(c, u) for c, u in _board(player) if u.name in FRONT_LINE_UNITS and _open(u)])
        if coord is None:
            return None
        return next((act for item in DEFENSIVE if (act := start(item, coord))), None)

    if board:  # 2. 목표 덱 캐리 아이템 만들기
        have = _held_completed(player)
        wanted = [it for n in carriers(board) for it in board['items'][n] if it not in SKIP]
        need = Counter(wanted)
        for item in wanted:
            if have[item] < need[item] and (act := start(item, _recipient(player, board, item, starting=True))):
                return act

    if mode == 'win' and round_stage(game_round) in (2, 3) and (act := defensive()):  # 3. 방어 아이템
        return act

    if len(comps) > 4:  # 4. 조각 4개 초과
        if act := defensive():
            return act
        for item in PAIR.values():
            if act := start(item, _recipient(player, board, item, starting=True)):
                return act
    return None
```

- [ ] **Step 4: 검사가 통과하는지 본다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `PASS` 13줄(뼈대 1 + 아이템 12)

- [ ] **Step 5: 커밋한다**

```bash
git add meta/human_items.py meta/test_human_bot.py
git commit -m "meta: 사람 봇의 아이템 판단(meta/human_items.py)

설계 5절의 규칙: 만들다 만 아이템 마저 만들기, 아이템 칸의 완성 아이템 주기, 목표 덱 캐리 아이템(없으면 맡아 둘 유닛),
연승형의 방어 아이템(1코스트 2성 앞줄 포함), 조각 4개 초과. 주걱·도적의 장갑·소모품·소환물은 건드리지 않는다.
검사 12개(Review Focus 셋 포함).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 아이템을 사람 봇에 붙이고 1단계 재기

**Files:**
- Modify: `meta/human_bot.py`
- Test: `meta/test_human_bot.py`

**Interfaces:**
- Consumes: `human_items.item_action`.
- Produces: `HumanPolicy.__call__`의 단계 순서 `fill → sell → buy → swap → items → reposition → macro`.
  이 작업에서는 `self.mode`를 `'win'`으로 둔다(초반 전략은 Task 5).

- [ ] **Step 1: 단계 순서 검사를 쓴다**

`meta/test_human_bot.py`의 `if __name__ == '__main__':` 바로 위에 넣는다.

```python
def human_policy_places_items_before_leveling_test():
    """살 것도 바꿀 것도 없으면 레벨·리롤보다 아이템을 먼저 한다."""
    import Simulator.champion as cm
    from meta.human_bot import attach_human
    p = deck_player(['jhin'], gold=50)
    p.item_bench[0], p.item_bench[1] = GA[0], GA[1]
    attach_human(p, [], random.Random(0), board=SHARPSHOOTERS)
    assert p.default_policy(12, ['garen'] * 5, FULL) == f'6_{0}_0'
```

- [ ] **Step 2: 실패를 확인한다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `FAIL`(AssertionError, 지금은 레벨 행동 `'1'`이 나온다)

- [ ] **Step 3: 아이템 단계를 넣는다**

`meta/human_bot.py`를 아래로 바꾼다.

```python
"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

행동할 때마다 할 일이 있는 첫 단계만 움직인다: 보드 채우기 → 벤치 정리 → 사기 → 교체 → 아이템 → 자리 맞추기 → 레벨·리롤.
지금(1단계)은 덱 봇 규칙에 아이템(meta/human_items.py)을 더했다. 초반 전략과 레벨·리롤(2단계), 덱 고르기(3단계)를
차례로 더한다.
"""
from meta.human_items import item_action
from meta.lobby import DeckPolicy

KNOBS = {}  # 손잡이 값(설계 6절). 단계마다 채운다


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, 'win', False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        return (self.fill(player, shop, mask) or self.sell(player) or self.buy(player, shop, mask)
                or self.swap(player) or item_action(player, self.board, self.mode, game_round, mask)
                or self.reposition(player, game_round) or self.macro(player, game_round))


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고(0~2단계), 주지 않으면 스스로 고른다(3단계)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
```

- [ ] **Step 4: 검사가 통과하는지 본다**

Run: `"$PY" -m meta.test_human_bot && "$PY" -m meta.test_lobby`
Expected: `PASS` 14줄, `PASS` 10줄

- [ ] **Step 5: 1단계 기준을 잰다**

Run: `"$PY" -m meta.play_stats --games 100 --jobs 7 --conditions default,human --out "$OUT/stage1.json"`
Expected(보고할 숫자):
- `[사람 봇]` 줄의 `아이템 완성 비율(전체 보드)`이 80% 이상.
- `캐리 아이템(5단계)`이 80% 이상.
- `받은 아이템(조각으로)` 값을 기본 봇과 함께 적는다. 1등 보드의 완성 아이템 가운데 값이 9에 크게 못 미치는데
  받은 아이템이 원래 18(조각 18개 = 완성 9개)보다 적으면 드롭 문제로 따로 보고한다.
- 한 기준이라도 못 넘으면 Task 5로 가지 말고 숫자를 유저에게 보고한다.

- [ ] **Step 6: 커밋한다**

```bash
git add meta/human_bot.py meta/test_human_bot.py
git commit -m "meta: 사람 봇에 아이템 단계를 붙이고 1단계 재기

HumanPolicy의 단계를 보드 채우기·벤치 정리·사기·교체·아이템·자리 맞추기·레벨·리롤 순서로 두었다. 1단계 측정:
(측정 숫자를 여기에 적는다: 아이템 완성 비율, 5단계 캐리 아이템 비율, 받은 아이템).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

커밋 메시지의 괄호 안은 Step 5에서 나온 실제 숫자로 바꿔 적는다.

---

### Task 5: 초반 전략과 레벨·리롤 `meta/human_macro.py` (2단계)

**Files:**
- Create: `meta/human_macro.py`
- Modify: `meta/human_bot.py`
- Test: `meta/test_human_bot.py`

**Interfaces:**
- Consumes: `lobby.carriers`, `HumanPolicy`(Task 4).
- Produces: `human_macro.early_mode(player, k) -> 'win'|'lose'`, `stay_level(board) -> int|None`,
  `stable(player, board) -> bool`, `carry3(player, board) -> bool`,
  `plan(slot, level, hp, mode, rebuilt, stay, done3, steady, k) -> (int, int|None)`,
  `action(gold, level, target, floor, exp_first) -> '1'|'2'|'0'`. `HumanPolicy.update_mode(player, game_round)`,
  `HumanPolicy.macro`를 덮어쓴다. `KNOBS`에 `win_threshold`, `lose_hp`, `keep`, `floor_41`, `floor_45`, `hp_low`,
  `hp_all_in`을 넣는다.

- [ ] **Step 1: 레벨·리롤 검사를 쓴다**

`meta/test_human_bot.py`의 `if __name__ == '__main__':` 바로 위에 넣는다.

```python
K = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20}


def plan_follows_design_curves_test():
    """설계 3·4절의 레벨 곡선과 남길 골드. 칸: 2-1 = 3, 2-5 = 6, 3-1 = 9, 3-2 = 10, 4-1 = 15, 4-5 = 18, 5-1 = 21."""
    from meta.human_macro import plan
    cases = [
        ((3, 3, 90, 'win', False, None, False, False), (4, 50)),     # 연승형 2-1에 4, 넘는 몫은 리롤
        ((6, 4, 90, 'win', False, None, False, False), (5, 50)),     # 연승형 2-5에 5
        ((9, 5, 90, 'win', False, None, False, False), (6, 50)),     # 연승형 3-1에 6
        ((6, 4, 90, 'lose', False, None, False, False), (4, None)),  # 연패형은 모으기만
        ((10, 4, 60, 'lose', True, None, False, False), (6, 20)),    # 연패형이 보드를 세운다
        ((15, 7, 60, 'win', False, None, False, False), (7, 20)),    # 4-1에 7, 안정이 아니면 20까지
        ((15, 7, 60, 'win', False, None, False, True), (7, 50)),     # 안정이면 50을 지킨다
        ((18, 8, 60, 'win', False, None, False, False), (8, 10)),    # 4-5에 8, 안정이 아니면 10까지
        ((9, 5, 90, 'win', False, 5, False, False), (5, 50)),        # 느린 리롤(1코스트 캐리)은 5에 머문다
        ((15, 6, 60, 'win', False, 7, False, False), (7, None)),     # 3코스트 캐리는 7까지 올리고 그다음 리롤
        ((12, 6, 60, 'win', False, 6, True, False), (8, 50)),        # 캐리가 3성이면 8로
        ((16, 7, 35, 'win', False, None, False, True), (7, 10)),     # 4단계 체력 40 아래면 10까지
        ((16, 7, 15, 'win', False, None, False, True), (7, 0)),      # 20 아래면 다 쓴다
    ]
    for args, expected in cases:
        assert plan(*args, K) == expected, (args, plan(*args, K), expected)


def action_spends_in_order_test():
    """목표 레벨까지 경험치 → 5단계 레벨 8에서 안정이면 50 넘는 몫을 경험치(9로) → 남길 골드까지 리롤."""
    from meta.human_macro import action
    assert action(30, 6, 7, 20, False) == '1'
    assert action(60, 8, 8, 50, True) == '1'
    assert action(53, 8, 8, 50, True) == '2'
    assert action(21, 7, 7, 20, False) == '0'
    assert action(80, 9, 8, 50, True) == '2'


def early_mode_and_board_state_test():
    """초반 세기(2성 수 + 완성 아이템 수)로 전략을 고르고, 안정과 캐리 3성을 본다."""
    from meta.human_macro import carry3, early_mode, stable
    strong = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='vayne', stars=2, items=[])], [])
    weak = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='vayne', stars=1, items=[])], [])
    assert early_mode(strong, K) == 'win' and early_mode(weak, K) == 'lose'
    half = item_player([Unit(name='jhin', stars=1, items=[]), Unit(name='riven', stars=2, items=[])], [])
    both = item_player([Unit(name='jhin', stars=2, items=[]), Unit(name='riven', stars=2, items=[])], [])
    assert not stable(half, SHARPSHOOTERS) and stable(both, SHARPSHOOTERS)
    brawlers = {'name': 'b', 'tier': 'A', 'slow': False, 'units': ['ashe', 'sett'],
                'items': {'ashe': ['a', 'b', 'c'], 'sett': ['d', 'e', 'f']}}
    assert stable(item_player([Unit(name='ashe', stars=2, items=[]), Unit(name='sett', stars=1, items=[])], []), brawlers)
    ninja = {'name': 'n', 'tier': 'S', 'slow': True, 'units': ['zed', 'akali'],
             'items': {'zed': ['a', 'b', 'c'], 'akali': ['d', 'e', 'f']}}
    assert carry3(item_player([Unit(name='zed', stars=3, items=[])], []), ninja)
    assert not carry3(item_player([Unit(name='akali', stars=3, items=[])], []), ninja)


def update_mode_switches_and_rebuilds_test():
    """연승형이 2~3단계에 두 번 연달아 지면 연패형으로, 연패형은 3-2나 체력 50 아래에서 보드를 세운다."""
    from meta.human_bot import HumanPolicy
    p = item_player([Unit(name='garen', stars=2, items=[]), Unit(name='vayne', stars=2, items=[])], [])
    p.loss_streak, p.health = 0, 90
    policy = HumanPolicy(None, SHARPSHOOTERS, [], random.Random(0))
    policy.update_mode(p, 3)
    assert policy.mode == 'win'
    p.loss_streak = 2
    policy.update_mode(p, 8)
    assert policy.mode == 'lose' and not policy.rebuilt
    policy.update_mode(p, 10)
    assert policy.rebuilt
```

- [ ] **Step 2: 실패를 확인한다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `ModuleNotFoundError: No module named 'meta.human_macro'`

- [ ] **Step 3: 레벨·리롤 판단을 만든다**

`meta/human_macro.py`를 만든다.

```python
"""
사람 봇의 초반 전략과 레벨·리롤(meta/human_bot_design.md 3·4절).

plan()이 이번 행동의 (목표 레벨, 남길 골드)를 정하고, action()이 행동 하나("1" 경험치, "2" 리롤, "0" 넘김)로 바꾼다.
칸 번호(game_round): 2-1 = 3, 2-5 = 6, 3-1 = 9, 3-2 = 10, 4-1 = 15, 4-5 = 18, 5-1 = 21.
"""
from Simulator.item_stats import item_builds
from Simulator.stats import COST, round_stage
from meta.lobby import carriers

STAY = {1: 5, 2: 6, 3: 7}  # 느린 리롤 캐리 비용 -> 머무는 레벨


def early_mode(player, k):
    """2-1의 초반 세기(보드 2성 유닛 수 + 보드 완성 아이템 수)로 연승형('win')·연패형('lose')을 고른다."""
    units = [u for row in player.board for u in row if u]
    strength = sum(u.stars >= 2 for u in units) + sum(it in item_builds for u in units for it in u.items)
    return 'win' if strength >= k['win_threshold'] else 'lose'


def stay_level(board):
    """느린 리롤 덱이 머무는 레벨(캐리 중 가장 싼 유닛의 비용으로). 보통 덱이나 목표 덱이 없으면 None."""
    return STAY[min(COST[c] for c in carriers(board))] if board and board['slow'] else None


def stable(player, board):
    """4코스트 이하 캐리가 모두 보드에 2성 이상으로 있는가. 캐리가 모두 5코스트면 보드에 있기만 하면 된다."""
    on = {}
    for row in player.board:
        for u in row:
            if u:
                on[u.name] = max(on.get(u.name, 0), u.stars)
    core = [c for c in carriers(board) if COST[c] <= 4]
    if not core:
        return all(c in on for c in carriers(board))
    return all(on.get(c, 0) >= 2 for c in core)


def carry3(player, board):
    """느린 리롤 덱의 가장 싼 캐리가 보드에 3성으로 있는가."""
    cheapest = min(carriers(board), key=lambda c: COST[c])
    return any(u and u.name == cheapest and u.stars >= 3 for row in player.board for u in row)


def plan(slot, level, hp, mode, rebuilt, stay, done3, steady, k):
    """(목표 레벨, 남길 골드). 남길 골드가 None이면 리롤하지 않는다.
    stay: 느린 리롤 머무는 레벨(보통 덱 None), done3: 느린 리롤 캐리가 3성, steady: 안정."""
    if slot < 3:
        return level, None
    if slot < 15:
        target = (6 if slot >= 9 else 5 if slot >= 6 else 4) if mode == 'win' else (6 if rebuilt else 4)
    else:
        target = 8 if slot >= 18 else 7
    banking = mode == 'lose' and not rebuilt and slot < 15
    if stay is not None and not done3:  # 느린 리롤: 머무는 레벨에서 50 넘는 몫으로 리롤
        if banking:
            return 4, None
        target = stay if rebuilt or slot >= 15 else min(target, stay)
        floor = k['keep'] if level >= target else None
    else:
        if stay is not None:
            target = max(target, 8)  # 캐리가 3성이면 8로 빠르게
        if banking:
            floor = None
        elif steady:
            floor = k['keep']
        elif slot >= 18 and level >= 8:
            floor = k['floor_45']
        elif slot >= 15 and level >= 7:
            floor = k['floor_41']
        elif mode == 'lose' and rebuilt:
            floor = k['floor_41']
        else:
            floor = k['keep']
    if round_stage(slot) >= 4 and hp < k['hp_all_in']:
        floor = 0
    elif round_stage(slot) >= 4 and hp < k['hp_low']:
        floor = k['floor_45'] if floor is None else min(floor, k['floor_45'])
    return target, floor


def action(gold, level, target, floor, exp_first):
    """목표 레벨까지 경험치 → 5단계 레벨 8에서 안정이면 50 넘는 몫을 경험치(9로) → 남길 골드까지 리롤."""
    if level < target and gold >= 4:
        return '1'
    if exp_first and level < 9 and gold >= 54:
        return '1'
    if floor is not None and gold >= floor + 2:
        return '2'
    return '0'
```

`meta/human_bot.py`를 아래로 바꾼다.

```python
"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

행동할 때마다 할 일이 있는 첫 단계만 움직인다: 보드 채우기 → 벤치 정리 → 사기 → 교체 → 아이템 → 자리 맞추기 → 레벨·리롤.
라운드의 첫 행동 때 초반 전략(연승형·연패형)을 정하거나 바꾼다. 아이템은 meta/human_items.py, 레벨·리롤은
meta/human_macro.py에 있다. 덱 고르기(3단계)는 다음에 더한다.
"""
from Simulator.stats import round_stage
from meta.human_items import item_action
from meta.human_macro import action, carry3, early_mode, plan, stable, stay_level
from meta.lobby import DeckPolicy

KNOBS = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20}


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        if game_round != self.last_round:
            self.last_round = game_round
            self.update_mode(player, game_round)
        return (self.fill(player, shop, mask) or self.sell(player) or self.buy(player, shop, mask)
                or self.swap(player) or item_action(player, self.board, self.mode or 'win', game_round, mask)
                or self.reposition(player, game_round) or self.macro(player, game_round))

    def update_mode(self, player, game_round):
        """2-1에 초반 전략을 고르고, 연승형이 2~3단계에 두 번 연달아 지면 연패형으로 바꾼다.
        연패형은 3-2가 되거나 체력이 손잡이 값(50) 아래로 내려가면 보드를 세운다(rebuilt)."""
        if game_round < 3:
            return
        if self.mode is None:
            self.mode = early_mode(player, self.knobs)
        if self.mode == 'win' and game_round < 15 and player.loss_streak >= 2:
            self.mode, self.rebuilt = 'lose', False
        if self.mode == 'lose' and not self.rebuilt and (game_round >= 10 or player.health < self.knobs['lose_hp']):
            self.rebuilt = True

    def macro(self, player, game_round):
        board = self.board
        stay = stay_level(board)
        done3 = stay is not None and carry3(player, board)
        steady = bool(board) and stable(player, board)
        target, floor = plan(game_round, player.level, player.health, self.mode or 'win', self.rebuilt, stay,
                             done3, steady, self.knobs)
        exp_first = round_stage(game_round) >= 5 and player.level == 8 and steady
        return action(player.gold, player.level, target, floor, exp_first)


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고(0~2단계), 주지 않으면 스스로 고른다(3단계)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
```

- [ ] **Step 4: 검사가 통과하는지 본다**

Run: `"$PY" -m meta.test_human_bot && "$PY" -m meta.test_lobby`
Expected: `PASS` 18줄, `PASS` 10줄

- [ ] **Step 5: 2단계 기준을 잰다**

Run: `"$PY" -m meta.play_stats --games 100 --jobs 7 --conditions default,human --out "$OUT/stage2.json"`
Expected(보고할 숫자, `[사람 봇]` 부분):
- `연승형` 줄의 평균 레벨이 2-1 뒤 4, 4-1 뒤 7, 4-5와 5-1 뒤 8과 각각 0.3 안쪽. 3-2 뒤는 연승형 6, 연패형 6(보드를
  세운 뒤)과 0.3 안쪽(연패형은 3-2 전까지 4인 게 맞다).
- `1등 보드`의 `9유닛 이상`이 61~91%(실제 76%와 15%p 안쪽).
- `5코스트 2성 이상`이 54~84%(실제 69%와 15%p 안쪽).
- `전체` 줄의 골드가 4-1 뒤와 4-5 뒤에 내려갔다가 5-1 뒤나 6-1 뒤에 다시 45 이상으로 오른다.
- `연패형` 줄의 3-2 뒤 골드가 50 이상(3-2 전에 50에 닿았다).
- `초반 전략별` 평균 등수 차이가 1 안쪽.
- 한 기준이라도 못 넘으면 Task 6으로 가지 말고 숫자를 유저에게 보고한다.

- [ ] **Step 6: 커밋한다**

```bash
git add meta/human_macro.py meta/human_bot.py meta/test_human_bot.py
git commit -m "meta: 사람 봇의 초반 전략과 레벨·리롤(meta/human_macro.py), 2단계 재기

설계 3·4절: 2-1에 초반 세기로 연승형·연패형, 연승형 두 연패면 연패형, 연패형은 3-2나 체력 50 아래에 보드 세우기.
4-1에 7(안정 아니면 20까지), 4-5에 8(10까지), 5단계 레벨 8 안정이면 50 넘는 몫으로 9, 느린 리롤은 캐리 비용별
5·6·7에서 50 넘는 몫으로 리롤하고 캐리 3성이면 8로, 체력 40·20 기준. 검사 4개. 2단계 측정: (숫자).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

커밋 메시지의 「(숫자)」는 Step 5에서 나온 실제 숫자(전략별 단계 레벨, 레벨 9, 5코스트 2성, 연패형 3-2 골드, 전략별
평균 등수)로 바꿔 적는다.

---

### Task 6: 덱 고르기 `meta/human_deck.py` (3단계)

**Files:**
- Create: `meta/human_deck.py`
- Modify: `meta/human_bot.py`, `meta/lobby.py` (`play()`의 사람 봇 분기에서 `board=` 빼기)
- Test: `meta/test_human_bot.py`

**Interfaces:**
- Consumes: `lobby.BOARDS`, `lobby.carriers`, `pit.chosen_of`, `HumanPolicy`(Task 5).
- Produces: `human_deck.copies(units) -> Counter`, `scout(others) -> Counter`, `buildable(board, completed, components) -> int`,
  `score(board, mine, chosen_trait, completed, components, others, k) -> float`,
  `choose(scores, current, stage, rng, k) -> int`, `SPREAD: Counter`. `HumanPolicy.pick_deck`, `sell_chosen`,
  `buy`(1단계 규칙과 짝 사기)를 더한다. `KNOBS`에 `chosen_bonus`, `item_point`, `tier_weight`, `contest`, `temperature`,
  `switch`, `early_spread`를 넣는다.

- [ ] **Step 1: 덱 고르기 검사를 쓴다**

`meta/test_human_bot.py`의 `if __name__ == '__main__':` 바로 위에 넣는다.

```python
D = dict(K, chosen_bonus=10, item_point=3, tier_weight=3, contest=1, temperature=3,
         switch={2: 0.1, 3: 0.3, 4: 0.6}, early_spread=6)


def score_follows_owned_units_and_chosen_test():
    """황혼 선택받은 자와 황혼 유닛을 들면 Chosen Dusks 점수가 Chosen Hunters보다 높다."""
    from collections import Counter
    from meta.human_deck import score
    from meta.lobby import BOARDS
    dusks = next(b for b in BOARDS if b['name'] == 'Chosen Dusks')
    hunters = next(b for b in BOARDS if b['name'] == 'Chosen Hunters')
    mine = Counter({'riven': 3, 'cassiopeia': 1, 'thresh': 3})
    assert score(dusks, mine, 'dusk', [], [], Counter(), D) > score(hunters, mine, 'dusk', [], [], Counter(), D)


def buildable_counts_completed_and_components_test():
    """들고 있는 완성 아이템과 조각으로 추천 아이템을 몇 개 만들 수 있는지 센다."""
    from meta.human_deck import buildable
    assert buildable(SHARPSHOOTERS, ['infinity_edge'], list(GA)) == 2
    assert buildable(SHARPSHOOTERS, [], [GA[0]]) == 0


def contest_lowers_score_test():
    """다른 플레이어가 핵심 유닛(캐리와 4·5코스트)을 들고 있으면 그 장수만큼 점수가 내려간다."""
    from collections import Counter
    from meta.human_deck import score
    from meta.lobby import BOARDS
    sharp = next(b for b in BOARDS if b['name'] == 'Chosen Sharpshooters')
    base = score(sharp, Counter(), None, [], [], Counter(), D)
    assert score(sharp, Counter(), None, [], [], Counter({'jhin': 9}), D) == base - 9


def choose_is_seeded_and_sticky_test():
    """처음엔 시드를 고정한 제비뽑기, 그다음엔 문턱을 넘어야 갈아탄다(2단계 10%, 4단계부터 60%)."""
    from meta.human_deck import choose
    scores = [1.0, 5.0, 3.0]
    assert choose(scores, None, 2, random.Random(7), D) == choose(scores, None, 2, random.Random(7), D)
    assert choose(scores, None, 2, random.Random(7), dict(D, temperature=0.01)) == 1
    assert choose([10.0, 15.0], 0, 4, random.Random(0), D) == 0
    assert choose([10.0, 17.0], 0, 4, random.Random(0), D) == 1
    assert choose([10.0, 12.0], 0, 2, random.Random(0), D) == 1


def choose_handles_non_positive_scores_and_late_stages_test():
    """점수가 모두 0 이하여도, 6단계여도 하나를 고른다(Review Focus)."""
    from meta.human_deck import choose
    assert choose([-5.0, -1.0, 0.0], None, 2, random.Random(0), D) in (0, 1, 2)
    assert choose([-5.0, 3.0], 0, 6, random.Random(0), D) == 1


def scout_ignores_eliminated_players_test():
    """탈락한 플레이어의 유닛은 정찰에서 세지 않는다(Review Focus)."""
    from meta.human_deck import scout
    alive = item_player([Unit(name='jhin', stars=2, items=[])], [])
    alive.health = 30
    dead = item_player([Unit(name='riven', stars=2, items=[])], [])
    dead.health = 0
    assert scout([alive, dead]) == {'jhin': 3}


def sells_chosen_of_other_trait_after_switch_test():
    """덱을 갈아타서 들고 있는 선택받은 자 특성이 목표 덱과 다르면 그 선택받은 자를 판다(벤치 칸은 28부터)."""
    from meta.human_bot import HumanPolicy
    from meta.lobby import BOARDS
    hunters = next(b for b in BOARDS if b['name'] == 'Chosen Hunters')
    bench = [Unit(name='vayne', stars=1, items=[], chosen=False), Unit(name='garen', stars=1, items=[], chosen=False),
             Unit(name='riven', stars=2, items=[], chosen='dusk')]
    p = item_player([], [], bench)
    p.chosen = 'dusk'
    policy = HumanPolicy(None, None, [], random.Random(0))
    policy.set_board(hunters)
    assert policy.sell_chosen(p) == '4_30'


def buys_pairs_and_widely_used_units_before_choosing_test():
    """목표 덱을 정하기 전에는 짝과 여러 후보 덱에 두루 들어가는 유닛을 산다."""
    from meta.human_bot import HumanPolicy
    from meta.human_deck import SPREAD
    p = item_player([Unit(name='jhin', stars=1, items=[], chosen=False)], [])
    p.gold, p.chosen = 10, False
    policy = HumanPolicy(None, None, [], random.Random(0))
    rare = min(SPREAD, key=SPREAD.get)
    assert policy.buy(p, [rare, 'jhin', rare, rare, rare], OPEN) == '3_1'
    assert SPREAD['shen'] >= 6 and policy.buy(p, [rare, 'shen', rare, rare, rare], OPEN) == '3_1'
```

- [ ] **Step 2: 실패를 확인한다**

Run: `"$PY" -m meta.test_human_bot`
Expected: `ModuleNotFoundError: No module named 'meta.human_deck'`

- [ ] **Step 3: 덱 고르기를 만든다**

`meta/human_deck.py`를 만든다.

```python
"""
사람 봇의 덱 고르기(meta/human_bot_design.md 2절).

후보는 tftactics 10.24 보드 27개(meta.lobby.BOARDS). 점수 = 유닛 점수(비용 × 사본 수) + 선택받은 자 덤
+ 아이템 점수 + 티어 점수 - 겹침 감점. 처음엔 점수가 높을수록 잘 뽑히는 제비뽑기로 고르고, 그 뒤로는 문턱을 넘어야
갈아탄다.
"""
import math
from collections import Counter

from Simulator.item_stats import basic_items, item_builds
from Simulator.stats import COST
from meta.lobby import BOARDS, carriers
from meta.pit import chosen_of

TIER_POINTS = {'S': 3, 'A': 2, 'B': 1}


def copies(units):
    """유닛 목록 -> {이름: 1성으로 친 장수}(1성 1, 2성 3, 3성 9)."""
    count = Counter()
    for u in units:
        count[u.name] += 3 ** (u.stars - 1)
    return count


def units_of(player):
    return [u for row in player.board for u in row if u] + [u for u in player.bench if u]


def scout(others):
    """살아 있는 다른 플레이어들이 들고 있는 유닛 장수."""
    return copies(u for o in others if o.health > 0 for u in units_of(o))


def buildable(board, completed, components):
    """들고 있는 완성 아이템과 조각으로 이 덱의 추천 아이템을 몇 개 만들 수 있는지(앞에서부터 센다)."""
    done, parts = Counter(completed), Counter(components)
    n = 0
    for held in board['items'].values():
        for item in held:
            if done[item]:
                done[item] -= 1
                n += 1
            elif item in item_builds and not Counter(item_builds[item]) - parts:
                parts -= Counter(item_builds[item])
                n += 1
    return n


def key_units(board):
    """핵심 유닛: 캐리와 4·5코스트."""
    return set(carriers(board)) | {u for u in board['units'] if COST[u] >= 4}


def score(board, mine, chosen_trait, completed, components, others, k):
    s = sum(COST[u] * min(mine.get(u, 0), 9) for u in set(board['units']))
    if chosen_trait and chosen_trait == chosen_of(board)[1]:
        s += k['chosen_bonus']
    s += k['item_point'] * buildable(board, completed, components)
    s += k['tier_weight'] * TIER_POINTS[board['tier']]
    s -= k['contest'] * sum(others.get(u, 0) for u in key_units(board))
    return s


def choose(scores, current, stage, rng, k):
    """current가 None이면 제비뽑기(확률은 exp((점수 - 최고점) / 온도)에 비례). 아니면 최고점이 지금 덱보다
    문턱(단계별 비율 × 지금 점수, 지금 점수가 1보다 작으면 1로) 넘게 높을 때만 갈아탄다."""
    if current is None:
        top = max(scores)
        weights = [math.exp((s - top) / k['temperature']) for s in scores]
        return rng.choices(range(len(scores)), weights=weights)[0]
    best = max(range(len(scores)), key=lambda i: scores[i])
    margin = k['switch'][min(max(stage, 2), 4)]
    return best if scores[best] - scores[current] > margin * max(scores[current], 1) else current


SPREAD = Counter()  # 1단계 사기 기준: 유닛마다 그 유닛이 든 후보 덱들의 티어 점수 합(가운데 값 6)
for _board in BOARDS:
    for _unit in set(_board['units']):
        SPREAD[_unit] += TIER_POINTS[_board['tier']]


def held_items(player):
    """(완성 아이템 목록, 조각 목록). 보드·벤치 유닛과 아이템 칸 전부. 주걱은 뺀다."""
    held = [it for u in units_of(player) for it in u.items] + [it for it in player.item_bench if it]
    return ([it for it in held if it in item_builds],
            [it for it in held if it in basic_items and it != 'spatula'])
```

`meta/human_bot.py`를 아래로 바꾼다.

```python
"""
사람처럼 노는 봇(meta/human_bot_design.md). 기본 봇 위에 얹는 정책 하나로, 1라운드부터 끝까지 맡는다.

행동할 때마다 할 일이 있는 첫 단계만 움직인다: 보드 채우기 → 벤치 정리 → 다른 특성 선택받은 자 팔기 → 사기 → 교체
→ 아이템 → 자리 맞추기 → 레벨·리롤. 라운드의 첫 행동 때 초반 전략을 정하거나 바꾸고, 2-1부터 목표 덱을 고르거나
갈아탄다. 아이템은 meta/human_items.py, 레벨·리롤은 meta/human_macro.py, 덱 고르기는 meta/human_deck.py에 있다.
"""
from Simulator.stats import COST, round_stage
from Simulator.utils import x_y_to_1d_coord
from meta.human_deck import SPREAD, choose, copies, held_items, score, scout, units_of
from meta.human_items import item_action
from meta.human_macro import action, carry3, early_mode, plan, stable, stay_level
from meta.lobby import BOARDS, DeckPolicy

KNOBS = {'win_threshold': 2, 'lose_hp': 50, 'keep': 50, 'floor_41': 20, 'floor_45': 10, 'hp_low': 40, 'hp_all_in': 20,
         'chosen_bonus': 10, 'item_point': 3, 'tier_weight': 3, 'contest': 1, 'temperature': 3,
         'switch': {2: 0.1, 3: 0.3, 4: 0.6}, 'early_spread': 6}


class HumanPolicy(DeckPolicy):
    def __init__(self, agent, board, others, rng, knobs=None):
        self.agent = agent
        self.others = others  # 다른 플레이어(정찰)
        self.rng = rng        # 이 플레이어의 난수(시드 고정)
        self.knobs = dict(KNOBS, **(knobs or {}))
        self.moves, self.mode, self.rebuilt, self.switches, self.last_round = {}, None, False, 0, None
        self.choose_decks = board is None
        self.set_board(board)

    def set_board(self, board):
        if board is None:
            self.board, self.units, self.trait, self.slow = None, set(), None, False
        else:
            super().set_board(board)

    def __call__(self, player, shop, game_round, mask):
        self.agent.current_round = game_round
        if game_round != self.last_round:
            self.last_round = game_round
            self.update_mode(player, game_round)
            if self.choose_decks and game_round >= 3:
                self.pick_deck(player, game_round)
        return (self.fill(player, shop, mask) or self.sell(player) or self.sell_chosen(player)
                or self.buy(player, shop, mask) or self.swap(player)
                or item_action(player, self.board, self.mode or 'win', game_round, mask)
                or self.reposition(player, game_round) or self.macro(player, game_round))

    def pick_deck(self, player, game_round):
        """라운드 첫 행동 때 후보 27개의 점수를 매겨 목표 덱을 고르거나 갈아탄다(설계 2절)."""
        completed, components = held_items(player)
        mine, others = copies(units_of(player)), scout(self.others)
        scores = [score(b, mine, player.chosen or None, completed, components, others, self.knobs) for b in BOARDS]
        current = BOARDS.index(self.board) if self.board else None
        new = choose(scores, current, round_stage(game_round), self.rng, self.knobs)
        if new != current:
            if current is not None:
                self.switches += 1
            self.set_board(BOARDS[new])

    def sell(self, player):
        if self.board is None:  # 목표 덱이 없으면 기본 봇 규칙(짝 아닌 1성부터)
            return self.agent.sell_bench_full(player) if player.bench_full() else None
        return super().sell(player)

    def sell_chosen(self, player):
        """덱을 갈아타서 들고 있는 선택받은 자 특성이 목표 덱과 다르면 판다. 시뮬레이터는 선택받은 자를 들고 있으면
        상점에 다른 선택받은 자를 내지 않는다(pool.sample)."""
        if not (self.choose_decks and self.board and player.chosen and player.chosen != self.trait):
            return None
        for x, row in enumerate(player.board):
            for y, u in enumerate(row):
                if u and u.chosen:
                    return f'4_{x_y_to_1d_coord(x, y)}'
        for i, u in enumerate(player.bench):
            if u and u.chosen:
                return f'4_{28 + i}'
        return None

    def buy(self, player, shop, mask):
        """목표 덱이 없으면 짝·두루 들어가는 유닛·처음 본 선택받은 자를, 있으면 덱 유닛·덱 특성 선택받은 자를 사고
        4-1 전까지는 보드 유닛의 짝도 산다."""
        if self.board is None:
            owned = {u.name for u in units_of(player)}
            for i, unit in enumerate(shop):
                if not mask[47 + i][0]:
                    continue
                if unit.endswith('_c'):
                    name = unit.split('_')[0]
                    if not player.chosen and COST[name] > 1 and 3 * COST[name] <= player.gold:
                        return '3_' + str(i)
                elif (unit in owned or SPREAD[unit] >= self.knobs['early_spread']) and COST[unit] <= player.gold:
                    return '3_' + str(i)
            return None
        act = super().buy(player, shop, mask)
        if act or (self.last_round or 0) >= 15:
            return act
        on_board = {u.name for row in player.board for u in row if u}
        for i, unit in enumerate(shop):
            if mask[47 + i][0] and not unit.endswith('_c') and unit in on_board and COST[unit] <= player.gold:
                return '3_' + str(i)
        return None

    def update_mode(self, player, game_round):
        """2-1에 초반 전략을 고르고, 연승형이 2~3단계에 두 번 연달아 지면 연패형으로 바꾼다.
        연패형은 3-2가 되거나 체력이 손잡이 값(50) 아래로 내려가면 보드를 세운다(rebuilt)."""
        if game_round < 3:
            return
        if self.mode is None:
            self.mode = early_mode(player, self.knobs)
        if self.mode == 'win' and game_round < 15 and player.loss_streak >= 2:
            self.mode, self.rebuilt = 'lose', False
        if self.mode == 'lose' and not self.rebuilt and (game_round >= 10 or player.health < self.knobs['lose_hp']):
            self.rebuilt = True

    def macro(self, player, game_round):
        board = self.board
        stay = stay_level(board)
        done3 = stay is not None and carry3(player, board)
        steady = bool(board) and stable(player, board)
        target, floor = plan(game_round, player.level, player.health, self.mode or 'win', self.rebuilt, stay,
                             done3, steady, self.knobs)
        exp_first = round_stage(game_round) >= 5 and player.level == 8 and steady
        return action(player.gold, player.level, target, floor, exp_first)


def attach_human(player, others, rng, knobs=None, board=None):
    """플레이어의 기본 봇에 HumanPolicy를 얹는다. 1라운드부터 이 정책이 맡는다.
    board를 주면 그 덱을 끝까지 쓰고, 주지 않으면 스스로 고른다(3단계부터 측정은 주지 않는다)."""
    policy = HumanPolicy(player.default_agent, board, others, rng, knobs)
    player.default_agent.policy = lambda p, shop, game_round, mask: policy(p, shop, game_round, mask)
    return policy
```

`meta/lobby.py`의 `play()`에서 사람 봇 분기의 `attach_human(...)` 호출을 아래로 바꾼다(목표 덱을 주지 않는다).

```python
                policies[a] = attach_human(players[a], others, random.Random(seed * N_PLAYERS + i), knobs)
```

`play()` docstring의 마지막 문장을 `덱 번호는 덱 봇의 목표 덱이다(사람 봇은 스스로 고른다).`로 바꾼다.

- [ ] **Step 4: 검사가 통과하는지 본다**

Run: `"$PY" -m meta.test_human_bot && "$PY" -m meta.test_lobby`
Expected: `PASS` 26줄, `PASS` 10줄

- [ ] **Step 5: 3단계 기준을 잰다**

Run: `"$PY" -m meta.play_stats --games 100 --jobs 7 --conditions default,human --out "$OUT/stage3.json"`
Expected(보고할 숫자, `[사람 봇]`과 `1등 보드`):
- `큰 특성 없는 보드`(사람 봇 1등)가 15% 이하.
- `선택받은 자가 계열 특성이 아닌 비율`(사람 봇 1등)이 40~65%.
- `계열` 목록의 첫 몫(마지막 보드에서 가장 많은 계열)이 35% 이하.
- 2단계 기준(레벨 곡선, 레벨 9, 5코스트 2성)이 덱 고르기를 넣은 뒤에도 유지되는지 함께 적는다.
- `덱 갈아타기` 평균 횟수와 0단계 대비 걸린 시간(1.5배 안쪽)을 적는다.
- 한 기준이라도 못 넘으면 Task 7로 가지 말고 숫자를 유저에게 보고한다.

- [ ] **Step 6: 커밋한다**

```bash
git add meta/human_deck.py meta/human_bot.py meta/lobby.py meta/test_human_bot.py
git commit -m "meta: 사람 봇의 덱 고르기(meta/human_deck.py), 3단계 재기

설계 2절: 후보 27개를 유닛(비용 × 사본 수)·선택받은 자 덤·아이템·티어·겹침(살아 있는 플레이어만)으로 점수 매겨
2-1부터 제비뽑기로 고르고, 단계별 문턱(10/30/60%)을 넘어야 갈아탄다. 갈아탄 뒤 특성이 다른 선택받은 자는 판다
(시뮬레이터가 들고 있는 동안 새 선택받은 자를 안 내서). 덱을 정하기 전엔 짝·두루 들어가는 유닛·처음 본 선택받은 자를
산다. 검사 8개(Review Focus 둘 포함). 3단계 측정: (숫자).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

커밋 메시지의 「(숫자)」는 Step 5에서 나온 실제 숫자(큰 특성 없는 1등 보드, 선택받은 자가 계열 특성이 아닌 비율,
가장 많은 계열의 몫, 덱 갈아타기 횟수)로 바꿔 적는다.

---

### Task 7: 4단계 메타 비교 (측정과 보고)

**Files:**
- Create: `results/human_meta_1024.json`, `results/human_meta_1024_tier0.json`
- Modify: `results/README.md` (맨 아래에 새 절), `meta/set4_play.md` (5절 추가)

**Interfaces:**
- Consumes: `meta.play_stats`의 `--conditions human`, `--knob tier_weight=0`.

- [ ] **Step 1: 사람 봇만 400판을 두 번 돌린다**

Run: `"$PY" -m meta.play_stats --games 400 --jobs 7 --conditions human --out results/human_meta_1024.json`
Run: `"$PY" -m meta.play_stats --games 400 --jobs 7 --conditions human --knob tier_weight=0 --out results/human_meta_1024_tier0.json`
Expected: 두 실행 모두 표가 찍히고 `저장:`으로 끝난다(각각 40분 안팎).

- [ ] **Step 2: 결과를 나란히 놓는다**

Run:
```bash
"$PY" - <<'EOF'
import json
for name in ('results/human_meta_1024.json', 'results/human_meta_1024_tier0.json'):
    d = json.load(open(name, encoding='utf-8'))
    o = d['사람 봇']
    print(name, '| 1등 계열', o['winners']['families'][:6])
    print('   마지막 보드 계열 (몫, 평균 등수):', [(f, round(s, 3), round(a, 2)) for f, s, a in o['families'][:10]])
print('실제 1등 계열:', d['real_winners']['families'])
print('실제 메타 트렌드 계열:', [(f, round(s, 3), round(a, 2)) for f, s, a in d['real_families']])
EOF
```
Expected: 계열별 몫과 평균 등수가 두 설정(티어 비중 3, 0)과 실제 두 자료(1등 보드, 메타 트렌드)로 찍힌다.

- [ ] **Step 3: 문서에 적는다**

`results/README.md` 맨 아래에 `## 10.24 사람 봇 메타 비교 (날짜)` 절을 더한다. 담을 것:
- 실행 명령 두 줄과 결과 파일 두 개, june 커밋.
- 1등 보드 표(실제 1등, 사람 봇 1등: 레벨 9, 5코스트 2성, 완성 아이템, 선택받은 자, 큰 특성 없는 보드).
- 계열 표: 계열 | 사람 봇 몫 | 사람 봇 평균 등수 | 티어 0 몫 | 티어 0 평균 등수 | 실제 메타 트렌드 몫 | 실제 평균 등수
  | 실제 1등 보드 수.
- 읽은 것: 1티어 덱 계열(황혼 dusk, 신성 divine)이 몫과 평균 등수에서 어디쯤인지, 티어 비중을 0으로 두면 무엇이 바뀌는지,
  실제와 다른 곳. 인과는 주장하지 않는다(떼어 잰 것만 원인으로 적는다).

`meta/set4_play.md`의 `## 출처` 바로 위에 `## 5. 사람 봇 결과` 절을 더하고, 위 표 두 개를 줄여 옮긴 뒤
results/README의 새 절로 이어지게 적는다.

- [ ] **Step 4: 커밋하고 올린다**

```bash
git add results/human_meta_1024.json results/human_meta_1024_tier0.json results/README.md meta/set4_play.md
git commit -m "results: 10.24 사람 봇 메타 비교(400판, 티어 비중 3과 0)

(읽은 것 요약을 여기에 적는다).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin curt-2
```

커밋 메시지의 괄호 안은 Step 3에서 results/README에 쓴 「읽은 것」을 두세 줄로 줄여 적는다.

올리기 전에 나가는 변경과 커밋 메시지에 개인 정보(이름, 학교 메일, 전화번호)와 로컬 경로가 없는지 훑는다.
