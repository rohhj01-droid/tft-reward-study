"""
자기 대전 학습(hra/plan_ai_design.md 5절). 일꾼들이 8자리 모두 최신 신경망으로 판을 돌리고, 본체가 경험 더미에서 배운다.
따라 하기 자료를 더미 옆에 두고 값 손실과 여백 손실을 계속 건다(데운 신경망이 자기 대전 초반에 무너지지 않게).
save_every판마다 저장하고 AI 4 대 규칙 4 점검(중간 점검)을 한다. 같은 명령을 다시 돌리면 마지막 저장에서 이어 간다.

실행: python -m hra.selfplay --config both --aux-w 0.1 --seed 1 --games 10000 --jobs 6
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
import time
from collections import deque

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hra.evaluate import ab
from hra.plan_bot import pinned_pool, safe_play
from hra.plan_learn import KEYS, Replay, learn_step
from hra.plan_net import PlanNet, choose, flip_rate, load, save, weights
from meta.lobby import N_PLAYERS

BATCH, DEMO_BATCH, LR, SYNC, UPDATES_PER_GAME, CAPACITY = 256, 64, 2.5e-4, 1000, 8, 500_000
EPS_START, EPS_END = (0.03, 0.15, 0.15), (0.01, 0.05, 0.05)  # 덱, 레벨, 남길 골드(설계 5절)
PUBLISH_EVERY, KEEP_POLICIES = 25, 5  # 이 판 수마다 일꾼용 신경망을 새 파일로 쓰고, 마지막 몇 개만 남긴다
SEED_SELFPLAY, SEED_CHECK = 100000, 800000
_worker = {'path': None, 'net': None, 'w': None}


def eps_at(done, total):
    """학습한 판 수에 따른 갈래별 탐험 몫(시작에서 끝으로 곧게)."""
    t = min(done / max(total, 1), 1.0)
    return tuple(a + (b - a) * t for a, b in zip(EPS_START, EPS_END))


def margin_weight(done, until):
    """여백 손실 가중치. until(판 수)이 없으면 늘 1(설계 5절, 여섯 실행). 있으면 0판에서 1로 시작해 until판에서 0이 되고 그 뒤로 0
    (여백 떼기 시험: 규칙의 선택에 묶인 레벨·남길 골드를 자기 대전이 바꿀 수 있는지 본다)."""
    if until is None:
        return 1.0
    return max(0.0, 1.0 - done / until)


def margin_weights(done, until, keep_deck=False):
    """갈래(덱, 레벨, 남길 골드)별 여백 손실 가중치. keep_deck이면 덱 갈래는 늘 1이고 레벨·남길 골드만 margin_weight대로 줄인다
    (여백 떼기 시험 2차: 세 갈래를 다 떼자 덱 갈래가 500판 안에 무너졌다. results/README 「여백 떼기 시험」)."""
    m = margin_weight(done, until)
    return (1.0 if keep_deck else m, m, m)


def is_better(new, best):
    """중간 점검 등수 차가 지금까지의 최고보다 나은가. 처음이면 그렇다. 값이 없으면(nan) 아니다."""
    return new == new and (best is None or new > best)


def prune_policies(ck_dir, name, keep=KEEP_POLICIES):
    """일꾼용 정책 파일을 마지막 keep개만 남기고 지운다. 일꾼이 아직 읽는 파일은(Windows에선 지우지 못한다) 다음에 지운다."""
    for old in sorted(glob.glob(os.path.join(ck_dir, f'{name}_policy_v*.pt')), key=os.path.getmtime)[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass


def selfplay_game(job):
    """(시드, 일꾼용 신경망 경로, 탐험 몫) -> (경험 목록, 판 요약, 오류). 일꾼은 경로가 바뀔 때만 신경망을 다시 읽는다."""
    seed, path, eps = job
    if _worker['path'] != path:
        torch.set_num_threads(1)
        _worker['net'], _worker['w'], _ = load(path)
        _worker['path'] = path
    rng = random.Random(seed)
    planner = lambda s, m: choose(_worker['net'], s, m, _worker['w'], eps, rng)
    out, err = safe_play(seed, [planner] * N_PLAYERS)
    if out is None:
        return [], None, err
    summary = {'switches': [s['switches'] for s in out['seats']], 'decks': [s['deck'] for s in out['seats']]}
    return [t for s in out['seats'] for t in s['transitions']], summary, None


def train(config, aux_w, seed, games, jobs, save_every=500, eval_games=100, warm=None, demos=None, root='.', tag=None,
          margin_until=None, margin_keep_deck=False, econ_w=0.3):
    """자기 대전 학습. games는 이 이름으로 끝낼 총 판 수다(이어 하기면 남은 만큼만 돈다)."""
    name = tag or f'plan_{config}_s{seed}'
    ck_dir, res_dir = os.path.join(root, 'checkpoints'), os.path.join(root, 'results')
    os.makedirs(ck_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)
    ck_path, log_path = os.path.join(ck_dir, f'{name}.pt'), os.path.join(res_dir, f'{name}.json')
    latest, best_path = os.path.join(ck_dir, f'{name}_latest.pt'), os.path.join(ck_dir, f'{name}_best.pt')
    w = weights(config, aux_w, econ_w)
    torch.manual_seed(seed)
    torch.set_num_threads(1)  # 일꾼이 CPU를 다 쓸 때 스레드 둘은 서로 기다리느라 학습 한 걸음이 14배 느려졌다
    rng = np.random.default_rng(seed)
    net, target = PlanNet(), PlanNet()
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    done, best, updates, curve, resumed = 0, None, 0, [], False
    if os.path.exists(ck_path):  # 이어 하기(경험 더미는 저장하지 않으니 빈 더미에서 다시 배운다. 곡선에 표시한다)
        resumed = True
        ck = torch.load(ck_path, map_location='cpu', weights_only=True)
        net.load_state_dict(ck['net'])
        target.load_state_dict(ck['target'])
        opt.load_state_dict(ck['opt'])
        done, best, updates = ck['games'], ck['best'], ck['updates']
        if os.path.exists(log_path):
            curve = json.load(open(log_path, encoding='utf-8'))['curve']
    else:
        if warm:
            net.load_state_dict(load(warm)[0].state_dict())
        target.load_state_dict(net.state_dict())
    if done >= games:  # 이미 끝난 실행: 일꾼을 띄우거나 정책 파일을 쓰지 않는다
        return {'games': done, 'best': best}
    demo_replay = None
    if demos:
        arrays = np.load(demos)
        demo_replay = Replay.from_arrays({k: arrays[k] for k in KEYS})
    replay, version = Replay(CAPACITY), 0

    def publish():
        nonlocal version
        version += 1
        path = os.path.join(ck_dir, f'{name}_policy_v{done}_{version}.pt')
        save(net, path, w, config=config, aux_w=aux_w, seed=seed, games=done)
        prune_policies(ck_dir, name)
        return path

    policy = publish()
    with pinned_pool(jobs) as pool:
        while done < games:
            chunk, start, losses, switches, errors = min(save_every, games - done), time.time(), [], [], 0
            submitted, finished, inflight = 0, 0, deque()
            while finished < chunk:
                while len(inflight) < 2 * jobs and submitted < chunk:
                    k = done + submitted
                    inflight.append(pool.apply_async(
                        selfplay_game, ((SEED_SELFPLAY + seed * 1_000_000 + k, policy, eps_at(k, games)),)))
                    submitted += 1
                try:
                    transitions, summary, err = inflight.popleft().get()
                except Exception as e:  # 일꾼 쪽 예외(신경망 파일 읽기 등)도 그 판만 버린다
                    transitions, summary, err = [], None, f'{type(e).__name__}: {e}'
                finished += 1
                errors += err is not None
                if summary:
                    switches += summary['switches']
                for t in transitions:
                    replay.add(t)
                if len(replay) >= BATCH:
                    lam = margin_weights(done + finished, margin_until, margin_keep_deck)
                    for _ in range(UPDATES_PER_GAME):
                        demo = demo_replay.sample(DEMO_BATCH, rng) if demo_replay is not None else None
                        losses.append(learn_step(net, target, opt, w, batch=replay.sample(BATCH, rng), demo=demo, lam=lam))
                        updates += 1
                        if updates % SYNC == 0:
                            target.load_state_dict(net.state_dict())
                if finished % PUBLISH_EVERY == 0:
                    policy = publish()
            done += chunk
            save(net, latest, w, config=config, aux_w=aux_w, seed=seed, games=done)
            check = ab(latest, eval_games, pool=pool, seed0=SEED_CHECK)
            idx = rng.integers(0, len(replay), min(2000, len(replay))) if len(replay) else []
            flips = flip_rate(net, replay.s[idx], replay.m[idx], w) if len(replay) else 0.0
            if is_better(check['diff'], best):
                best = check['diff']
                save(net, best_path, w, config=config, aux_w=aux_w, seed=seed, games=done, diff=best)
            curve.append({'games': done, 'diff': check['diff'], 'se': check['se'], 'check_errors': len(check['errors']),
                          'flip': flips, 'switches': statistics.mean(switches) if switches else None,
                          'loss': statistics.mean(losses) if losses else None, 'errors': errors,
                          'minutes': (time.time() - start) / 60, 'resumed': resumed,
                          'margin': margin_weight(done, margin_until)})
            resumed = False
            tmp = ck_path + '.tmp'
            torch.save({'net': net.state_dict(), 'target': target.state_dict(), 'opt': opt.state_dict(),
                        'games': done, 'best': best, 'updates': updates}, tmp)
            os.replace(tmp, ck_path)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump({'config': config, 'aux_w': aux_w, 'seed': seed, 'margin_until': margin_until,
                           'margin_keep_deck': margin_keep_deck, 'econ_w': econ_w, 'curve': curve}, f,
                          ensure_ascii=False, indent=1)
            print(f'{done}판: 점검 등수 차 {check["diff"]:+.2f}±{check["se"]:.2f}, 뒤집는 비율 {flips:.2f}, '
                  f'갈아타기 {curve[-1]["switches"]}, 멈춘 판 {errors}, 여백 가중치 {curve[-1]["margin"]:.2f}', flush=True)
            policy = publish()
    return {'games': done, 'best': best}


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='both', choices=['none', 'synergy', 'units', 'both'])
    ap.add_argument('--aux-w', type=float, default=0.3, help='보조 갈래 가중치. 사전 시험에서 0.3을 골랐다(설계 4절)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--games', type=int, default=10000)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--save-every', type=int, default=500)
    ap.add_argument('--eval-games', type=int, default=100)
    ap.add_argument('--warm', default=None, help='데우기 신경망. 없으면 checkpoints/plan_warm_<설정>.pt가 있을 때 그것')
    ap.add_argument('--demos', default=None, help='따라 하기 자료. 없으면 checkpoints/plan_demos.npz가 있을 때 그것')
    ap.add_argument('--tag', default=None)
    ap.add_argument('--margin-until', type=int, default=None,
                    help='여백 손실 가중치를 이 판 수까지 1→0으로 줄여 끈다(여백 떼기 시험). 없으면 끝까지 1(설계 5절)')
    ap.add_argument('--margin-keep-deck', action='store_true',
                    help='덱 갈래는 여백 손실을 끝까지 1로 두고 레벨·남길 골드 갈래만 --margin-until대로 줄인다(여백 떼기 시험 2차)')
    ap.add_argument('--econ-w', type=float, default=0.3, help='이자 갈래 가중치(설계 4절 0.3). 0이면 이자 갈래를 끈다(이자 가설 대조)')
    return ap


def inputs(config, warm, demos, root='.'):
    """자기 대전에 넣을 (데우기 신경망 경로, 따라 하기 자료 경로, 경고 목록). 직접 준 파일이 없으면 FileNotFoundError,
    기본 경로(checkpoints/plan_warm_<설정>.pt, checkpoints/plan_demos.npz)에 없으면 None과 경고를 돌려준다
    (데우기 없음은 무작위 초기값에서 시작, 자료 없음은 여백 손실 없이 학습)."""
    out, warnings = [], []
    for label, given, default, effect in (
            ('데우기 신경망', warm, os.path.join(root, 'checkpoints', f'plan_warm_{config}.pt'), '무작위 초기값에서 시작한다'),
            ('따라 하기 자료', demos, os.path.join(root, 'checkpoints', 'plan_demos.npz'), '여백 손실 없이 배운다')):
        if given is not None:
            if not os.path.exists(given):
                raise FileNotFoundError(f'{label} {given}이 없다')
            out.append(given)
        elif os.path.exists(default):
            out.append(default)
        else:
            out.append(None)
            warnings.append(f'{label}이 {default}에 없어 {effect}')
    return out[0], out[1], warnings


def main():
    ap = parser()
    args = ap.parse_args()
    try:
        warm, demos, warnings = inputs(args.config, args.warm, args.demos)
    except FileNotFoundError as e:
        ap.error(str(e))
    for line in warnings:
        print('경고:', line, flush=True)
    result = train(args.config, args.aux_w, args.seed, args.games, args.jobs, args.save_every, args.eval_games,
                   warm, demos, tag=args.tag, margin_until=args.margin_until, margin_keep_deck=args.margin_keep_deck,
                   econ_w=args.econ_w)
    print(result)


if __name__ == '__main__':
    main()
