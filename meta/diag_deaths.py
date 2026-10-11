"""
실제 보드 대전의 한 보드가 상대별로 어떻게 지는지 본다(진단, 2026-10-12 명사수 6명 보드에 썼다).

판마다 그 보드 유닛이 죽은 시각과 그때 곁(1칸)에 있던 적, 유닛별로 준 피해, 지켜볼 유닛의 기본 공격·스킬 횟수와 첫 공격 시각을
센다. 대전 결과 파일의 보드와 설정을 그대로 쓴다(패치가 적혀 있으면 그 패치 값, 없으면 핫픽스 전 값, 구석 배치, 판마다 좌우를
바꾼다). 시뮬레이터 함수를 감싸서 세므로 결과는 대전 결과와 같은 조건이다.

실행: python -m meta.diag_deaths results/real_boards_1024.json 6sharpshooter jhin,jinx 20 4ninja-4shade-3cultist-2adept 6duelist-2adept
      (결과 파일, 볼 보드 이름 앞부분, 지켜볼 유닛, 상대마다 판 수, 상대 이름 앞부분...)
"""
import json
import statistics
import sys
from collections import Counter, defaultdict

import Simulator.champion as cm
from Simulator import champion_functions as cf
from analysis.battle import battle, to_units
from meta.real_boards import apply_sim_patch, prehotfix, spec


def main():
    src, board, watch, n, prefixes = sys.argv[1], sys.argv[2], sys.argv[3].split(','), int(sys.argv[4]), sys.argv[5:]
    result = json.load(open(src, encoding='utf-8'))
    apply_sim_patch(result['patch']) if result.get('patch') else prehotfix()
    boards = {b['key']: b for b in result['boards']}
    me = next(k for k in boards if k.startswith(board))
    mine = set(boards[me]['units'])
    st = {'team': None, 'deaths': [], 'damage': Counter(), 'attacks': Counter(), 'casts': Counter(),
          'first': defaultdict(list), 'seen': set()}
    die, add_damage, attack, cast = cf.die, cf.add_damage_dealt, cf.attack, cm.champion.cast

    def watched_die(c):
        if c.team == st['team'] and c.name in mine and not (c.will_revive[0][0] or c.will_revive[1][0]):
            near = [e.name for e in c.enemy_team() if e.health > 0 and abs(e.y - c.y) <= 1 and abs(e.x - c.x) <= 1]
            st['deaths'].append((cf.MILLIS() / 1000, c.name, near))
        return die(c)

    def watched_damage(c, damage, target):
        st['damage'][('me' if c.team == st['team'] else 'opp', c.name)] += damage
        return add_damage(c, damage, target)

    def watched_attack(c, target, bonus_dmg=0, item_attack=False, trait_attack='', *args, **kwargs):
        if c.team == st['team'] and c.name in watch and not item_attack and not trait_attack and (c.idle or bonus_dmg) and target:
            st['attacks'][c.name] += 1
            if id(c) not in st['seen']:
                st['seen'].add(id(c))
                st['first'][c.name].append(cf.MILLIS() / 1000)
        return attack(c, target, bonus_dmg, item_attack, trait_attack, *args, **kwargs)

    def watched_cast(self):
        if self.team == st['team'] and self.name in watch:
            st['casts'][self.name] += 1
        return cast(self)

    cf.die = cm.die = watched_die
    cf.add_damage_dealt = cm.add_damage_dealt = watched_damage
    cf.attack = cm.attack = watched_attack
    cm.champion.cast = watched_cast

    med = lambda xs: f'{statistics.median(xs):.1f}초' if xs else '-'
    for prefix in prefixes:
        opp = next(k for k in boards if k.startswith(prefix))
        wins, first_death, died, near = 0, Counter(), defaultdict(list), defaultdict(Counter)
        for k in ('damage', 'attacks', 'casts', 'first'):
            st[k].clear()
        for i in range(n):
            st['deaths'], st['seen'] = [], set()
            a, b = to_units(spec(boards[me], 2)), to_units(spec(boards[opp], 2))
            st['team'] = 'blue' if i % 2 == 0 else 'red'
            wins += battle(a, b, 'corner') == 1 if i % 2 == 0 else battle(b, a, 'corner') == 2
            if st['deaths']:
                first_death[st['deaths'][0][1]] += 1
            for t, name, around in st['deaths']:
                died[name].append(t)
                near[name].update(around)
        mine_total = sum(v for (s, _), v in st['damage'].items() if s == 'me') or 1
        opp_total = sum(v for (s, _), v in st['damage'].items() if s == 'opp') or 1
        print(f'=== vs {opp}  이긴 판 {wins}/{n}')
        for name in watch:
            print(f'  {name}: 죽은 판 {len(died[name])}/{n}, 죽은 시각 중앙값 {med(died[name])}, 판당 기본 공격 '
                  f'{st["attacks"][name] / n:.1f}, 판당 스킬 {st["casts"][name] / n:.1f}, 첫 공격 시각 중앙값 {med(st["first"][name])}, '
                  f'죽을 때 곁의 적 {dict(near[name].most_common(4))}')
        print(f'  가장 먼저 죽은 유닛: {dict(first_death.most_common(4))}')
        print('  이 보드 피해 몫: ' + ', '.join(f'{nm} {v / mine_total:.0%}' for (s, nm), v in st['damage'].most_common() if s == 'me'))
        print('  상대 보드 피해 몫: ' + ', '.join(f'{nm} {v / opp_total:.0%}' for (s, nm), v in st['damage'].most_common() if s == 'opp'))


if __name__ == '__main__':
    main()
