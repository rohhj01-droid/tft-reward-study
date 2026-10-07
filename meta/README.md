# 패치 10.24 메타 덱 목록

목표는 "AI가 10.24에서 사람처럼 플레이해서, 그 패치의 1티어 덱으로 실제로 1등을 하는가"를 보는 것이다.
그러려면 먼저 1티어 덱이 무엇인지 출처를 근거로 정해 둬야 한다. 이 폴더가 그 목록이다.

- `decks_1024.py`: 덱 정의(기준 보드, 아이템, 선택받은 자, 분류 기준)와 분류 함수 `classify()`
- `tftactics_10.24_2020-11-28.txt`: 기준 보드를 옮겨 온 원자료. 27개 조합 전부 들어 있다

확인: `python -m meta.decks_1024` (시뮬레이터 저장소가 PYTHONPATH에 있어야 한다)

## 어느 10.24인가

10.24 공식 패치 노트는 2020-11-23에 나왔다. 2020-12-01에 10.24b 핫픽스가 나와서
제드, 사교도(갈리오), 수호자 보호막, 요네, 루난의 허리케인을 약하게 했다.

시뮬레이터 기본값은 핫픽스 **뒤** 값이다. 직접 확인한 값: 제드 공격 속도 0.75, 제드 공격력 훔치기
25/30/35%, 요네 최대 마나 60, 수호자 보호막 150/225/350, 루난의 허리케인 공격력 배율 0.9.
june `Simulator/patch_manager.py`의 10.24 항목 주석도 "핫픽스 값과 같다"고 적고 있다.
그래서 티어는 핫픽스 뒤에 나온 티어표를 기준으로 삼았다.

## 1티어와 2티어

기준: **bunnymuffins 10.24b 티어표(2020-12-04 게시)의 S를 1티어, A를 2티어**로 삼았다.
내가 찾은 핫픽스 뒤 표 중 덱별 설명까지 글로 남은 것은 이것 하나다.

| 덱 | 10.24b bunnymuffins (핫픽스 뒤) | 10.24 bunnymuffins (핫픽스 전) | 10.24 tftactics (핫픽스 전) | 10.24 The Game Haus 1주차 (핫픽스 전) | 10.25 bunnymuffins 2주차 |
|---|---|---|---|---|---|
| **황혼** | **S** | S | S (Chosen Dusks) | A (Dusk Riven) | S |
| **신성 워윅** | **S** | S | S (Chosen Divines) | A (Warwick) | S |
| 제드 닌자 그림자 | A | S | S (Ninja Shades) | S (Zed) | S·A에 없음 |
| 달빛 다이애나 | A | A | B (Moonlight Assassins) | 상위권에 없음 | S·A에 없음 |
| 총사령관 | A | A | S (Chosen Warlords) | A (Warlords) | S·A에 없음 |

1티어가 둘뿐인 이유: 핫픽스 뒤 표의 S가 둘이다. 핫픽스 전 표들은 제드도 S였지만, 핫픽스가 제드를
직접 약하게 했고 핫픽스 뒤 표는 제드를 A로 내렸다. 다음 패치(10.25) 2주차 표에서도 S는 황혼과
신성 워윅 둘이다. 황혼과 신성 워윅이 이 시기 1티어라는 데는 출처 다섯 곳이 대체로 맞는다.
The Game Haus만 둘을 A에 뒀다.

tftactics 표는 S가 7개로 넓다. 그중 사교도(Chosen Cultists, Dusk Cultists)와 결투가(Chosen Duelists)는
핫픽스 뒤 bunnymuffins 표에서 각각 C와 B로 내려갔다. 사교도는 핫픽스에서 직접 약해졌다.

## 덱별 내용

기준 보드는 tftactics 표에서 그대로 옮겼다. 운영 방법과 선택받은 자는 bunnymuffins 10.24b 설명을 줄여 옮겼다.
특성 인원수는 `python -m meta.decks_1024`가 시뮬레이터 셈법으로 센 값이다. 선택받은 자는 빼고 셌고,
1명으로 켜지는 특성(닌자 1, 추방자 1 등)은 적지 않았다.

### 1티어: 황혼

- 보드(레벨 8): 베인, 쓰레쉬, 아트록스(Gargoyle Stoneplate), 카시오페아, 진(Infinity Edge, Last Whisper),
  리븐(Ionic Spark, Quicksilver, Sunfire Cape), 릴리아, 질리언
- 특성: 황혼 5, 사교도 3, 신비술사 2, 명사수 2, 선봉대 2
- 선택받은 자: 황혼, 신비술사, 명사수, 수호자 중 하나
- 운영: 초반에는 사교도로 연승하며 가장 센 보드를 쓴다. 3-2에 레벨 6, 또는 4-1에 레벨 7에서 보드가
  안정될 때까지 리롤하고, 4-5에 레벨 8에서 다시 리롤한다. 리븐은 황혼 6이면 방어 아이템만,
  황혼 4면 공격 아이템 하나를 섞는다. 베인이 3성이 되면 베인을 캐리로 써도 된다.
- 분류 기준: 황혼 4 이상 (bunnymuffins 덱 이름이 "4 or 6 Dusk"다)

### 1티어: 신성 워윅

- 보드(레벨 8): 잭스, 이렐리아, 럭스, 모르가나(Morellonomicon), 쉔, 워윅(Deathblade, Quicksilver,
  Runaan's Hurricane), 리 신, 요네(Guardian Angel, Hand of Justice)
- 특성: 신성 5, 숙련자 3, 결투가 2, 깨달은 자 2, 선지자 2
- 선택받은 자: 신성, 숙련자, 사냥꾼 중 하나
- 운영: 가장 센 보드로 버티다가 4-5에 레벨 8로 올려 리롤한다. 또는 4-1에 레벨 7에서 워윅 한 장만
  찾을 만큼(20골드쯤) 리롤한다. 워윅에게 Quicksilver와 아이템 2개를 준다.
- 분류 기준: 신성 4 이상이고 워윅이 보드에 있다

### 2티어: 제드 닌자 그림자

- 보드(레벨 7): 엘리스, 파이크, 제드(Guinsoo's Rageblade, Quicksilver, Rapid Firecannon), 이블린,
  아칼리(Locket of the Iron Solari, Zeke's Herald 2개), 케넨, 쉔
- 특성: 닌자 4, 사교도 3, 암살자 2, 그림자 2, 수호자 2
- 선택받은 자: 그림자
- 운영: 닌자가 잘 뜨는 판인지 본 뒤에 들어간다. 제드 3성을 노리면 레벨 6~7에서 천천히 리롤하고,
  아니면 레벨 8~9로 빨리 올려 5코스트 유닛을 넣는다.
- 분류 기준: 닌자 4 이상이고 제드가 보드에 있다
- 아칼리가 지원 아이템을 든 것은 tftactics 표 그대로다

### 2티어: 달빛 다이애나

- 보드(레벨 7): 리산드라, 다이애나(Dragon's Claw, Hand of Justice, Sunfire Cape), 파이크, 사일러스,
  아칼리(Blue Buff, Hextech Gunblade, Rapid Firecannon), 카타리나, 탈론
- 특성: 암살자 5, 달빛 3
- 선택받은 자: 달빛 (다이애나나 리산드라)
- 운영: 초반에 달빛 선택받은 자를 얻은 뒤에 이 덱으로 정한다. 다이애나와 리산드라를 천천히 리롤하고
  암살자 4~6을 붙인다.
- 분류 기준: 달빛 3 이상이고 다이애나가 보드에 있다
- 이 보드는 tftactics 표에서는 B티어 조합(Moonlight Assassins)이다. 다이애나 중심 보드가 그것뿐이라 썼다

### 2티어: 총사령관

- 보드(레벨 8): 가렌, 니달리, 자르반 4세, 파이크(Warlord's Banner), 바이, 카타리나(Guardian Angel,
  Hextech Gunblade, Quicksilver), 신 짜오(Bloodthirster, Titan's Resolve), 아지르
- 특성: 총사령관 8 (유닛 7 + Warlord's Banner 1), 수호자 2, 암살자 2. 총사령관 선택받은 자까지 넣으면 총사령관 9
- 선택받은 자: 총사령관
- 운영: 총사령관 선택받은 자로 초반에 연승하고, 레벨 8로 빨리 올린 뒤 레벨 9에서 5코스트 캐리를 쓴다.
  가렌이 방어 아이템을 든다.
- 분류 기준: 총사령관 6 이상. bunnymuffins는 총사령관 3으로 하는 판도 있다고 적었지만, 총사령관 3은
  가렌·니달리·자르반 4세만 있어도 켜져서 덱을 가르는 기준이 못 된다. 그래서 6으로 잡았다

## 분류 기준

게임이 끝났을 때 보드를 보고 정한다. 특성 인원수(선택받은 자와 상징 아이템 포함, 시뮬레이터가 세는
방식과 같다)가 기준 이상이어야 하고, 캐리가 정해진 덱은 그 캐리가 보드에 있어야 한다.

기준 인원수는 기준 보드보다 낮게 잡았다. 예를 들어 신성 워윅 기준 보드는 선택받은 자까지 신성 6인데
기준은 4다. 레벨이 낮거나 유닛이 하나 빠진 보드도 같은 덱으로 세려는 것이다. 황혼 4만 출처의 숫자다.
나머지 기준 인원수는 내가 정했다.

시뮬레이터에서 쓸 때는 `player.update_team_tiers()` 뒤에
`classify(보드 위 유닛 이름들, player.team_composition)`을 부르면 된다.

## 한계

1. 기준 보드는 핫픽스 전(2020-11-28) 자료다. 핫픽스 뒤 보드를 글자로 남긴 자료는 못 찾았다.
   bunnymuffins 10.24b 보드는 그림이었는데 그림 파일이 서버에서 지워져 있다. 다만 bunnymuffins
   10.24b의 1티어 설명이 tftactics 보드와 맞는다. 황혼은 "황혼 4·6에 사교도 3, 명사수 2, 진 아이템,
   리븐 방어 아이템"이고 워윅은 "Quicksilver와 아이템 2개"다.
2. 티어표는 사람이 매긴 판단이지 승률 통계가 아니다. 그 시기 덱별 1등 비율 통계는 찾지 못했다.
   그래서 이 덱들이 시뮬레이터 안에서도 실제로 센지 따로 쟀다(아래 「시뮬레이터에서 붙여 본 결과」).
3. 선택받은 자가 어느 유닛인지는 출처에 없다. 특성 후보만 적었다.
4. 느린 리롤 덱(제드, 달빛)은 tftactics 보드가 레벨 7 기준이라 7명이다.
5. 10.24b 표의 B·C 덱은 코드에 넣지 않았다. B는 결투가, 명사수, 사냥꾼, 아리 선봉대 신비술사,
   애쉬 싸움꾼·조율이고 C는 깨달은 자, 마법사 리롤, 사교도다. 비슷한 보드는 tftactics 원자료에 있다.

## 시뮬레이터에서 붙여 본 결과 (2026-10-07)

`python -m meta.pit --n 60 --jobs 5 --out results/pit_1024.json`. tftactics 보드 27개를 서로 모두 붙였다.
조건, 전체 표, 해석은 [results/README.md](../results/README.md)의 「10.24 메타 보드 대전」에 있다.

- 1티어 두 덱은 우리 덱 다섯 중 1·2위다. 신성 워윅은 나머지 넷을 95~100%로 이기고, 27개 중 3위다(평균 89.3%).
  황혼은 2티어 셋을 73~100%로 이기지만 신성 워윅에게는 5%이고, 27개 중 9위다(62.6%).
- 2티어 중 달빛 다이애나(18.9%)와 총사령관(15.2%)은 시뮬레이터에서 바닥권이다. 총사령관은 하네스가 연승을
  0으로 두는 탓이 크다(연승 5를 주면 황혼 상대 3% -> 43%).
- 티어표에서 B인 애쉬 사냥꾼이 시뮬레이터에서는 1위다(92.4%). 시뮬레이터가 티어표 순위를 그대로 재현하지는 않는다.

## 출처

- bunnymuffins, "TFT Tier List – Patch 10.24b Meta Snapshot", 2020-12-04 게시:
  https://bunnymuffins.lol/tft-tier-list-patch-1024b/
- bunnymuffins, "TFT Patch 10.24b UPDATE & Predictions", 2020-12-01 (핫픽스 내용):
  https://bunnymuffins.lol/tft-patch-10-24b-update-predictions/
- bunnymuffins, "TFT Tier List – Patch 10.24", 2020-11-27 게시:
  https://bunnymuffins.lol/tft-tier-list-patch-1024/
- tftactics.gg 팀 조합 티어표 Patch 10.24, 웨이백 보관본 2020-11-28:
  https://web.archive.org/web/20201128065028/https://tftactics.gg/tierlist/team-comps
- The Game Haus, "TFT Meta Snapshot/Tier List 10.24 Week One", 2020-11-30:
  https://thegamehaus.com/teamfight-tactics/tft-meta-snapshot-tier-list-10-24-week-one-zed-or-dead/2020/11/30/
- bunnymuffins, "TFT Tier List – Patch 10.25 Meta Snapshot Week 2": https://bunnymuffins.lol/?p=2810
- Riot, 10.24 공식 패치 노트, 2020-11-23:
  https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-10-24-notes/
