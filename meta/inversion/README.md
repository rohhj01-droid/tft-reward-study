# 사람 봇 메타가 실제와 거꾸로인 까닭 떼어 재기 (2026-10-10)

results/README.md 「사람 봇 메타가 실제와 거꾸로인 까닭 떼어 재기」의 숫자를 낸 스크립트다. 모두 코드를 바꾸지 않고,
스크립트 안에서만 사람 봇 함수를 바꿔 끼워(몽키패치) 잰다. 결과 JSON은 스크립트 옆에 쓰고 git에는 올리지 않는다.

실행 환경(저장소 맨 위에서, Git Bash):

```bash
export PYTHONIOENCODING=utf-8 PYTHONPATH="<june 경로>;<stubs 경로>;meta/inversion;."
```

`PYTHONHASHSEED`는 스크립트가 일꾼에게 0으로 넘긴다. 한 프로세스로 한 판만 다시 돌릴 때는 `PYTHONHASHSEED=0`을 실행
전에 줘야 같은 판이 나온다(파이썬은 실행 중에 바꾼 해시 시드를 쓰지 않는다). `lobby.play`는 판 동안 표준 출력을 막으니
판 안에서 찍을 진단은 파일로 쓴다.

| 스크립트 | 하는 일 | 실행 |
|---|---|---|
| `diag_dusk.py` | 사람 봇 판을 돌려 목표 덱별 마지막 보드(유닛·별·아이템·선택받은 자·덱 겹침)를 모은다. `diag_dusk_rows.json`을 쓴다(아래 둘이 읽는다) | `python meta/inversion/diag_dusk.py 200` |
| `diag_curves.py`, `diag_curves2.py` | 덱별 단계 곡선(레벨·골드·체력·초반 전략). 2는 보드의 덱 유닛 수와 덱 특성 인원을 더 센다 | `python meta/inversion/diag_curves2.py 100` |
| `diag_iso4.py` | 4코스트 올리기: `DIAG_VARIANT=rolldown`(레벨 8부터 캐리 4코스트가 2성이 될 때까지 다 써서 리롤), `cap`(4코스트를 3장보다 안 삼), `both`, `base`(diag_dusk 결과로 요약만) | `DIAG_VARIANT=rolldown python meta/inversion/diag_iso4.py 200` |
| `diag_actions.py` | 롤다운 조건 라운드의 행동 수(한 라운드 15번), 리롤 수, 라운드 시작·끝 골드 | `DIAG_VARIANT=rolldown python meta/inversion/diag_actions.py 40` |
| `diag_iso5.py` | 가이드대로 황혼: `roll`(3-2에 레벨 6, 4-1에 레벨 7에서 캐리 2성까지 10골드 남기고 리롤), `guide`(+ 4-1 전 사교도 오프너, 연승형) | `DIAG_VARIANT=guide python meta/inversion/diag_iso5.py 200` |
| `diag_iso6.py` | 로비 구성: 봇마다 덱을 판 내내 고정해 `real`(실제 메타 트렌드 계열 몫) 또는 `bot`(봇이 스스로 고른 몫, diag_dusk 결과)대로 나눈다 | `DIAG_VARIANT=real python meta/inversion/diag_iso6.py 300` |
| `diag_iso7.py` | 느린 덱 대비책: 4-5까지 캐리 3성을 못 맞추면 보통 덱처럼 8로. `LOBBY=real`(diag_iso6의 실제 몫 로비)·`self`(봇이 덱을 고름), `FALLBACK=0`이면 대비책 없이 기준만 | `LOBBY=self FALLBACK=1 python meta/inversion/diag_iso7.py 200` |
| `find_crash.py` | diag_iso7(self) 판을 판마다 따로 돌려 오류 난 판 번호를 찾는다(바이 크래시를 찾을 때 썼다) | `python meta/inversion/find_crash.py 200` |

판 목록은 모두 `meta.play_stats`와 같은 시드 0의 앞 N판이다(diag_iso6은 판마다 덱을 그 몫으로 다시 뽑는다).
