"""크래시 찾기: diag_iso7(LOBBY=self, 느린 덱 대비책)과 같은 판을 판마다 따로 돌려, 오류가 난 판 번호와 마지막 오류 줄을 모은다."""
import os, random, sys, traceback
os.environ.setdefault('LOBBY', 'self')
import diag_iso7 as iso
from meta import lobby

def safe(game):
    try:
        iso.base.run(game)
        return None
    except Exception as e:
        return game[0], type(e).__name__, str(e), traceback.format_exc().strip().splitlines()[-6:]

if __name__ == '__main__':
    from multiprocessing import Pool
    n = int(sys.argv[1])
    rng = random.Random(0)
    games = [(g, rng.sample(range(len(lobby.BOARDS)), lobby.N_PLAYERS)) for g in range(n)]
    with Pool(7) as pool:
        bad = [b for b in pool.map(safe, games, chunksize=1) if b]
    print('오류 난 판', len(bad), '/', n)
    for g, kind, msg, tb in bad:
        print(g, kind, msg)
        print('   ' + '\n   '.join(tb))
