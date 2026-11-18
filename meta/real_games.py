"""
실제 Set 4 판 기록을 세어 규칙 봇의 후반 운영을 맞출 목표 숫자를 낸다(2026-11-18, 판정 없음).

판 기록은 Kaggle 「TEAMFIGHT TACTICS: FATES Challenger EUW Rank Games」(CC0, 유럽 서부 챌린저 상위 1000명이 낀 93,616판, 패치 10.19~11.1)다.
https://www.kaggle.com/datasets/mariuszmackowski/teamfight-tactics-fates-challenger-euw-rank-games
저장소에는 넣지 않고 집계만 올린다. 판 번호와 플레이어 식별 칸은 결과에 남기지 않는다.

- 묶음: 전체, 10.23~10.25, 10.24. 1등이 4-1 전에 끝난 판(다시 하기)은 뺀다.
- 등수마다: 끝날 때 레벨, 끝난 라운드, 남은 골드, 게임 시간, 보드(유닛 수, 4·5코스트의 별). 판마다: 라운드 시작에 살아 있던 자리 수.
- 계열은 meta/play_stats.family와 같은 규칙으로 끝 보드의 특성에서 정한다.
- 한계: 유닛 칸이 이름을 열쇠로 한 사전이라 같은 유닛 두 장은 한 장으로 남는다. 등수는 챌린저가 낀 판의 값이고 라운드별 체력은 기록에 없다.
- 봇 쪽은 교과서 8명 실행 기록의 마지막 라운드 시작 때 레벨로 같은 표를 낸다(끝날 때 레벨보다 조금 낮게 잡힌다).

내려받은 파일을 읽으므로 표준 라이브러리만 쓰고 격리 실행한다(저장소 맨 위에서):
python -I meta/real_games.py <csv> --bot results/spend_lesson_none_cap30_s750_tb-era.json --meta results/plan_eval_meta_rule_cap30_era.json --out results/real_games_set4.json
"""
import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict

FIVE = {'Azir', 'Ezreal', 'Kayn', 'LeeSin', 'Lillia', 'Sett', 'Yone', 'Zilean'}
FOUR = {'Aatrox', 'Ahri', 'Ashe', 'Cassiopeia', 'Jhin', 'Morgana', 'Riven', 'Sejuani', 'Shen', 'Talon', 'Warwick'}
FAMILIES = [('dusk', 4), ('ninja', 4), ('duelist', 6), ('cultist', 6), ('warlord', 6), ('sharpshooter', 4), ('divine', 4),
            ('hunter', 3), ('elderwood', 3), ('fortune', 3), ('mystic', 4), ('brawler', 4)]  # meta/play_stats.FAMILIES와 같다
SIX = ('warlord', 'cultist', 'divine', 'ninja', 'dusk', 'sharpshooter')  # hra/evaluate.SIX와 같다
ALIVE = {'5-1': 26, '5-5': 30, '6-1': 33, '6-5': 37, '7-1': 40}
FIRST_ROUND = 19  # 4-1. 1등이 이보다 먼저 끝난 판은 다시 하기로 본다
GROUPS = {'all': None, '10.23-10.25': {'10.23', '10.24', '10.25'}, '10.24': {'10.24'}}
UNIT = re.compile(r"'(\w+)': \{'items': \[[^\]]*\], 'stars': (\d)\}")
TRAIT = re.compile(r"'(\w+)': (\d+)")


def round_name(r):
    """라운드 번호(1부터) -> '6-1'. 1단계는 네 칸, 2단계부터 일곱 칸이다."""
    if r <= 4:
        return f'1-{r}'
    stage, k = divmod(r - 5, 7)
    return f'{stage + 2}-{k + 1}'


def slot_round(slot):
    """봇의 칸 번호(회전초밥을 뺀 번호, 3 = 2-1) -> 라운드 번호."""
    if slot < 3:
        return slot + 2
    stage, k = divmod(slot - 3, 6)
    return 5 + 7 * stage + (0, 1, 2, 4, 5, 6)[k]


def parse_units(text):
    return [(name, int(stars)) for name, stars in UNIT.findall(text)]


def parse_traits(text):
    return {name.lower(): int(n) for name, n in TRAIT.findall(text)}


def family(traits):
    return next((name for name, n in FAMILIES if traits.get(name, 0) >= n), 'other')


def quantile(counts, p):
    """Counter(값 -> 수)에서 누적 몫이 p에 처음 닿는 값(낮은 쪽)."""
    need, seen = p * sum(counts.values()), 0
    for value in sorted(counts):
        seen += counts[value]
        if seen >= need:
            return value


def mean(counts):
    return sum(v * n for v, n in counts.items()) / sum(counts.values())


def level_shares(counts):
    n = sum(counts.values())
    return {'<=6': round(sum(c for lv, c in counts.items() if lv <= 6) / n, 4),
            **{str(lv): round(counts[lv] / n, 4) for lv in (7, 8, 9)}}


class Tally:
    """자리를 하나씩 더하고 표로 묶는다. 자리: place, level, round, gold, seconds(없으면 None), units, traits(보드가 없으면 None)."""

    def __init__(self):
        self.level, self.rounds, self.gold, self.seconds = [defaultdict(Counter) for _ in range(4)]
        self.board = defaultdict(Counter)
        self.all_level, self.alive, self.stage, self.stage9, self.place_level = Counter(), Counter(), Counter(), Counter(), defaultdict(list)
        self.families = defaultdict(lambda: defaultdict(list))
        self.seats = 0

    def add(self, s):
        p, lv, r = s['place'], s['level'], s['round']
        self.seats += 1
        self.level[p][lv] += 1
        self.rounds[p][r] += 1
        self.all_level[lv] += 1
        self.place_level[lv].append(p)
        self.alive.update(name for name, first in ALIVE.items() if r >= first)
        stage = min(7, 1 if r <= 4 else (r - 5) // 7 + 2)
        self.stage[stage] += 1
        self.stage9[stage] += lv >= 9
        if s.get('gold') is not None:
            self.gold[p][s['gold']] += 1
            self.seconds[p][int(s['seconds'])] += 1
        if s.get('units') is not None:
            b = self.board[p]
            b['boards'] += 1
            b['units'] += len(s['units'])
            for name, stars in s['units']:
                b['three'] += stars >= 3
                for key, group in (('five', FIVE), ('four', FOUR)):
                    if name in group:
                        b[key] += 1
                        b[key + '_two'] += stars >= 2
            f = family(s['traits'])
            self.families[f]['all'].append(p)
            if lv in (8, 9):
                self.families[f][str(lv)].append(p)

    def place_row(self, p):
        row = {'level': level_shares(self.level[p]), 'mean_level': round(mean(self.level[p]), 3),
               'last_round': {k: round_name(quantile(self.rounds[p], q)) for k, q in (('q1', .25), ('median', .5), ('q3', .75))},
               'ended_7_1_or_later': round(sum(c for r, c in self.rounds[p].items() if r >= 40) / sum(self.rounds[p].values()), 4)}
        if self.gold[p]:
            row['gold_left'] = {'mean': round(mean(self.gold[p]), 2), 'median': quantile(self.gold[p], .5)}
            row['minutes_median'] = round(quantile(self.seconds[p], .5) / 60, 1)
        b = self.board[p]
        if b['boards']:
            row.update(units_per_board=round(b['units'] / b['boards'], 3), five_per_board=round(b['five'] / b['boards'], 3),
                       five_two_star_per_board=round(b['five_two'] / b['boards'], 3), three_star_per_board=round(b['three'] / b['boards'], 3),
                       five_two_star_share=round(b['five_two'] / max(1, b['five']), 4),
                       four_two_star_share=round(b['four_two'] / max(1, b['four']), 4))
        return row

    def summary(self):
        games = self.seats / 8
        out = {'games': int(games), 'seats': self.seats, 'level': level_shares(self.all_level), 'mean_level': round(mean(self.all_level), 3),
               'by_place': {str(p): self.place_row(p) for p in range(1, 9)},
               'alive': {name: round(self.alive[name] / games, 3) for name in ALIVE},
               'ended_in_stage': {str(st): {'share': round(self.stage[st] / self.seats, 4), 'level_9': round(self.stage9[st] / self.stage[st], 4)}
                                  for st in sorted(self.stage)},
               'mean_place_by_level': {str(lv): round(statistics.mean(v), 3) for lv, v in sorted(self.place_level.items()) if lv >= 7}}
        if self.families:
            sizes = {'all': self.seats, '8': self.all_level[8], '9': self.all_level[9]}
            out['families'] = {f: {k: {'seats': len(v), 'share': round(len(v) / sizes[k], 4), 'mean_place': round(statistics.mean(v), 3)}
                                   for k, v in rows.items()} for f, rows in sorted(self.families.items())}
        return out


def tally_csv(path):
    """판 기록 -> 묶음별 표. 첫 번째로 훑어 다시 하기 판을 찾고, 두 번째로 센다. 판 번호는 이 함수 밖으로 나가지 않는다."""
    csv.field_size_limit(10 ** 7)
    with open(path, encoding='utf-8', newline='') as f:
        drop = {row['match_id'] for row in csv.DictReader(f) if int(float(row['placement'])) == 1 and int(float(row['last_round'])) < FIRST_ROUND}
    tallies = {name: Tally() for name in GROUPS}
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            if row['match_id'] in drop:
                continue
            seat = {'place': int(float(row['placement'])), 'level': int(float(row['level'])), 'round': int(float(row['last_round'])),
                    'gold': int(float(row['gold_left'])), 'seconds': float(row['time_in_game']),
                    'units': parse_units(row['units']), 'traits': parse_traits(row['traits'])}
            for name, patches in GROUPS.items():
                if patches is None or row['patch_version'] in patches:
                    tallies[name].add(seat)
    return {'dropped_games': len(drop), 'groups': {name: t.summary() for name, t in tallies.items()}}


def bot_summary(record):
    """교과서 8명 실행 기록(hra/spend_lesson 결과의 rows) -> 같은 표. 레벨은 마지막 라운드를 시작할 때의 값이다."""
    t = Tally()
    for game in record['rows']:
        for seat in game:
            slot, level = seat['curve'][-1][:2]
            t.add({'place': seat['place'], 'level': level, 'round': slot_round(slot)})
    return t.summary()


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0] * len(x)
    for k, i in enumerate(order):
        r[i] = k
    return r


def family_order(real, bot_rows):
    """여섯 큰 계열의 평균 등수(끝 보드로 센 모든 자리)와 순위 상관."""
    mine = {f: place for f, _, place in bot_rows}
    names = [f for f in SIX if f in real and f in mine]
    return {'real': {f: real[f]['all']['mean_place'] for f in names}, 'bot': {f: round(mine[f], 3) for f in names},
            'rho': round(statistics.correlation(ranks([real[f]['all']['mean_place'] for f in names]), ranks([mine[f] for f in names])), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--bot', required=True, help='교과서 8명 실행 기록')
    ap.add_argument('--meta', required=True, help='교과서 8명의 계열 표(hra.evaluate meta 결과)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    with open(args.csv, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    out = {'source': {'name': 'TEAMFIGHT TACTICS: FATES Challenger EUW Rank Games', 'license': 'CC0',
                      'url': 'https://www.kaggle.com/datasets/mariuszmackowski/teamfight-tactics-fates-challenger-euw-rank-games',
                      'csv_sha256': digest}, **tally_csv(args.csv)}
    with open(args.bot, encoding='utf-8') as f:
        record = json.load(f)
    with open(args.meta, encoding='utf-8') as f:
        meta = json.load(f)
    out['bot'] = {'record': args.bot, 'actions_per_turn': record['actions_per_turn'], 'textbook': record['textbook'], **bot_summary(record)}
    out['family_order'] = {name: family_order(out['groups'][name]['families'], meta['families']) for name in ('10.24', '10.23-10.25')}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'저장: {args.out}')


if __name__ == '__main__':
    main()
