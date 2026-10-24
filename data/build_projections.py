"""Build data/projections.json: standings, the PlainStats game model's picks and season projections, from nflverse results.

Usage: python3 -I data/build_projections.py <path to games.csv> [season] [sims]
Data: nflverse schedules/games.csv (CC BY 4.0) and team divisions from data/nfl.json. Betting lines in games.csv are NOT used.
Runs weekly (after Monday Night Football), so standings and projections move once a week; scores update daily in data/schedule.json.

The model
- Team strength is an Elo rating built from every game since 1999 (regular season and playoffs). After each game the winner takes
  points from the loser, more for a bigger margin and less when the favorite wins as expected. K = 20, home field = 40 Elo points
  (none at neutral sites), and each team moves 40% of the way back to average between seasons.
- Win chance = 1 / (1 + 10^(-diff/400)). Spread = diff / 25 points. Projected score: each team's points for and against this season
  (shrunk toward league average early on) set the total, and the Elo spread splits it.
- The rest of the season is simulated SIMS times. Ratings move inside each simulated season as results come in, so a hot or cold
  run carries forward. Division winners and wild cards use the main NFL tiebreakers in a simplified form (record, head-to-head,
  division record, conference record, strength of victory, then a coin flip). Then the playoffs are simulated: 7 seeds per
  conference, the top seed gets a bye, the higher seed hosts, the Super Bowl is neutral.
- Backtest: every regular-season game from BT_FROM to last season is predicted with the ratings as they stood before kickoff."""
import csv, json, math, os, random, sys, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1]
SEASON = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
SIMS = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
K, HFA, REG, MOVC, PTS_PER_ELO, BT_FROM = 20, 40, 0.4, 2.2, 25, 2012
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
tf = lambda t: FIX.get(t, t)
winp = lambda d: 1 / (1 + 10 ** (-d / 400))

TEAMS = {t['id']: t['div'] for t in json.load(open(os.path.join(HERE, 'nfl.json')))['teams']}
CONF = {t: d.split()[0] for t, d in TEAMS.items()}

allg = [g for g in csv.DictReader(open(PATH, encoding='utf-8'))]
for g in allg: g['home_team'], g['away_team'] = tf(g['home_team']), tf(g['away_team'])
allg.sort(key=lambda g: (int(g['season']), g['gameday'], g['gametime'], g['game_id']))
done = [g for g in allg if g['home_score'] not in ('', 'NA')]
cur = [g for g in allg if int(g['season']) == SEASON and g['game_type'] == 'REG']

# ---------- Elo through every final game ----------
elo, last, pre = {}, None, {}
bt_n = bt_c = bt_b = 0
for g in done:
    s = int(g['season'])
    if s != last:
        for t in elo: elo[t] = elo[t] * (1 - REG) + 1505 * REG
        last = s
    h, a = g['home_team'], g['away_team']
    eh, ea = elo.get(h, 1505), elo.get(a, 1505)
    d = eh + (0 if g['location'] == 'Neutral' else HFA) - ea
    p = winp(d)
    m = int(g['home_score']) - int(g['away_score'])
    res = 1 if m > 0 else 0 if m < 0 else .5
    if s == SEASON and g['game_type'] == 'REG': pre[g['game_id']] = d
    if BT_FROM <= s < SEASON and g['game_type'] == 'REG':
        bt_n += 1; bt_b += (p - res) ** 2; bt_c += .5 if res == .5 else (p > .5) == (res == 1)
    wd = d if m > 0 else -d
    mult = math.log(abs(m) + 1) * MOVC / (wd * 0.001 + MOVC) if m else 1
    delta = K * mult * (res - p)
    elo[h], elo[a] = eh + delta, ea - delta
if last != SEASON:   # season not started: carry ratings into it
    for t in elo: elo[t] = elo[t] * (1 - REG) + 1505 * REG
for t in TEAMS: elo.setdefault(t, 1505)

# ---------- standings from final games ----------
def blank(): return {'w': 0, 'l': 0, 't': 0, 'pf': 0, 'pa': 0, 'dw': 0, 'dl': 0, 'dt': 0, 'cw': 0, 'cl': 0, 'ct': 0,
                     'hw': 0, 'hl': 0, 'ht': 0, 'aw': 0, 'al': 0, 'at': 0, 'res': [], 'beat': []}
def tally(R, H2H, h, a, hs, as_):
    for t, o, f, ag, side in ((h, a, hs, as_, 'h'), (a, h, as_, hs, 'a')):
        r = R[t]; k = 'w' if f > ag else 'l' if f < ag else 't'
        r[k] += 1; r[side + k] += 1; r['pf'] += f; r['pa'] += ag; r['res'].append(k.upper())
        if TEAMS[t] == TEAMS[o]: r['d' + k] += 1
        if CONF[t] == CONF[o]: r['c' + k] += 1
        if k == 'w': r['beat'].append(o)
        H2H[(t, o)][0 if k == 'w' else 1 if k == 'l' else 2] += 1
R0, H0 = {t: blank() for t in TEAMS}, defaultdict(lambda: [0, 0, 0])
final_cur = [g for g in cur if g['home_score'] not in ('', 'NA')]
for g in final_cur: tally(R0, H0, g['home_team'], g['away_team'], int(g['home_score']), int(g['away_score']))
pct = lambda w, l, t: (w + t / 2) / (w + l + t) if w + l + t else 0

def rank(group, R, H2H, rnd):
    """Order tied teams: record, then head-to-head among the tied group, division record, conference record,
    strength of victory, then a coin flip (rnd)."""
    def key(t):
        r = R[t]; return pct(r['w'], r['l'], r['t'])
    out, group = [], sorted(group, key=key, reverse=True)
    i = 0
    while i < len(group):
        j = i
        while j + 1 < len(group) and abs(key(group[j + 1]) - key(group[i])) < 1e-9: j += 1
        tied = group[i:j + 1]
        if len(tied) > 1:
            def tb(t):
                hw = sum(H2H[(t, o)][0] + H2H[(t, o)][2] / 2 for o in tied if o != t)
                hg = sum(sum(H2H[(t, o)]) for o in tied if o != t)
                r = R[t]
                sov = sum(pct(R[o]['w'], R[o]['l'], R[o]['t']) for o in r['beat']) / max(1, len(r['beat']))
                return (hw / hg if hg else .5, pct(r['dw'], r['dl'], r['dt']), pct(r['cw'], r['cl'], r['ct']), sov, rnd(t))
            tied.sort(key=tb, reverse=True)
        out += tied; i = j + 1
    return out

def seeds(R, H2H, rnd):
    res = {}
    for c in ('AFC', 'NFC'):
        divs = sorted({d for t, d in TEAMS.items() if CONF[t] == c})
        winners = [rank([t for t in TEAMS if TEAMS[t] == d], R, H2H, rnd)[0] for d in divs]
        rest = [t for t in TEAMS if CONF[t] == c and t not in winners]
        res[c] = rank(winners, R, H2H, rnd) + rank(rest, R, H2H, rnd)[:3]
    return res

alpha = lambda t: -ord(t[0]) / 100   # deterministic last resort for "if the season ended today"
SEED_NOW = seeds(R0, H0, alpha)

# ---------- projected scores ----------
# Played games get the projection the model would have made before kickoff: the rating gap then (pre) and points for and
# against from the games before it only. Games still to play use today's ratings and this season's points so far.
def ppg_model(R):
    pf = sum(r['pf'] for r in R.values()); n = sum(r['w'] + r['l'] + r['t'] for r in R.values())
    avg = pf / n if n else 22.0
    def off(t): r = R[t]; g = r['w'] + r['l'] + r['t']; return (r['pf'] + 4 * avg) / (g + 4)
    def dfn(t): r = R[t]; g = r['w'] + r['l'] + r['t']; return (r['pa'] + 4 * avg) / (g + 4)
    return off, dfn
def proj(h, a, d, OFF, DEF):
    p = winp(d); spread = d / PTS_PER_ELO
    total = (OFF(h) + DEF(a)) / 2 + (OFF(a) + DEF(h)) / 2
    hs, as_ = round(total / 2 + spread / 2), round(total / 2 - spread / 2)
    if p > .5 and hs <= as_: hs = as_ + 1
    if p < .5 and as_ <= hs: as_ = hs + 1
    return [round(p, 3), hs, as_]

games, RUN, HRUN = {}, {t: blank() for t in TEAMS}, defaultdict(lambda: [0, 0, 0])
for g in final_cur:
    h, a = g['home_team'], g['away_team']
    games[g['game_id']] = proj(h, a, pre[g['game_id']], *ppg_model(RUN))
    tally(RUN, HRUN, h, a, int(g['home_score']), int(g['away_score']))
OFF, DEF = ppg_model(R0)
for g in cur:
    if g['game_id'] in games: continue
    h, a = g['home_team'], g['away_team']
    games[g['game_id']] = proj(h, a, elo[h] + (0 if g['location'] == 'Neutral' else HFA) - elo[a], OFF, DEF)
pk_w = pk_l = 0
for g in final_cur:
    p = games[g['game_id']][0]; m = int(g['home_score']) - int(g['away_score'])
    if m: pk_w, pk_l = (pk_w + 1, pk_l) if (p > .5) == (m > 0) else (pk_w, pk_l + 1)

# ---------- simulate ----------
left = [g for g in cur if g['home_score'] in ('', 'NA')]
acc = {t: defaultdict(float) for t in TEAMS}
random.seed(SEASON * 7 + len(final_cur))
for _ in range(SIMS):
    E = dict(elo)
    R = {t: dict(R0[t], res=[], beat=list(R0[t]['beat'])) for t in TEAMS}
    H2H = defaultdict(lambda: [0, 0, 0], {k: list(v) for k, v in H0.items()})
    for g in left:
        h, a = g['home_team'], g['away_team']
        p = winp(E[h] + (0 if g['location'] == 'Neutral' else HFA) - E[a])
        hw = random.random() < p
        tally(R, H2H, h, a, 1 if hw else 0, 0 if hw else 1)
        dl = K * ((1 if hw else 0) - p); E[h] += dl; E[a] -= dl
    coin = {t: random.random() for t in TEAMS}
    S = seeds(R, H2H, lambda t: coin[t])
    for t in TEAMS: acc[t]['w'] += R[t]['w']; acc[t]['l'] += R[t]['l']; acc[t]['t'] += R[t]['t']
    champs = {}
    for c, sd in S.items():
        for i, t in enumerate(sd):
            acc[t]['po'] += 1; acc[t]['s%d' % (i + 1)] += 1
            if i < 4: acc[t]['dv'] += 1
        play = lambda hi, lo: hi if random.random() < winp(E[hi] + HFA - E[lo]) else lo
        alive = [sd[0]] + [play(sd[1], sd[6]), play(sd[2], sd[5]), play(sd[3], sd[4])]
        alive.sort(key=sd.index)
        alive = [play(alive[0], alive[3]), play(alive[1], alive[2])]
        alive.sort(key=sd.index)
        champs[c] = play(alive[0], alive[1]); acc[champs[c]]['cf'] += 1
    a_, n_ = champs['AFC'], champs['NFC']
    acc[a_ if random.random() < winp(E[a_] - E[n_]) else n_]['sb'] += 1

order = sorted(TEAMS, key=lambda t: -elo[t])
teams = {}
for t in TEAMS:
    r, x = R0[t], acc[t]
    st = ''
    if r['res']:
        n = 0
        for v in reversed(r['res']):
            if v != r['res'][-1]: break
            n += 1
        st = r['res'][-1] + str(n)
    now = next((i + 1 for c in SEED_NOW for i, s in enumerate(SEED_NOW[c]) if s == t), 0)
    f = lambda k: round(100 * x[k] / SIMS, 1)
    teams[t] = {'elo': round(elo[t]), 'eloRk': order.index(t) + 1, **{k: r[k] for k in ('w', 'l', 't', 'pf', 'pa', 'dw', 'dl', 'dt', 'cw', 'cl', 'ct', 'hw', 'hl', 'ht', 'aw', 'al', 'at')},
                'strk': st, 'l5': ''.join(r['res'][-5:]), 'seed': now,
                'pw': round(x['w'] / SIMS, 1), 'pl': round(x['l'] / SIMS, 1), 'pt': round(x['t'] / SIMS, 1),
                'po': f('po'), 'dv': f('dv'), 'by': f('s1'), 'cf': f('cf'), 'sb': f('sb'), 'sd': [f('s%d' % i) for i in range(1, 8)]}
weeks = {int(g['week']) for g in cur}
thru = max([w for w in weeks if all(x['home_score'] not in ('', 'NA') for x in cur if int(x['week']) == w)] or [0])   # last week with every game final
out = {'asOf': datetime.date.today().isoformat(), 'season': SEASON, 'thru': thru, 'games_final': len(final_cur), 'sims': SIMS,
       'source': 'PlainStats Elo model on nflverse game results (schedules/games.csv). No betting lines.',
       'model': {'k': K, 'hfa': HFA, 'regress': REG, 'ptsPerElo': PTS_PER_ELO,
                 'backtest': {'from': BT_FROM, 'to': SEASON - 1, 'games': bt_n, 'acc': round(bt_c / bt_n, 3) if bt_n else None, 'brier': round(bt_b / bt_n, 4) if bt_n else None},
                 'picks': {'w': pk_w, 'l': pk_l}},
       'seedsNow': SEED_NOW, 'teams': teams, 'games': games}
json.dump(out, open(os.path.join(HERE, 'projections.json'), 'w'), separators=(',', ':'))
top = sorted(TEAMS, key=lambda t: -teams[t]['sb'])[:3]
print('projections: thru week', thru, '| picks', pk_w, '-', pk_l, '| backtest', out['model']['backtest'], '| SB favorites', [(t, teams[t]['sb']) for t in top])
