"""Write data/tiers.json: the Weekly Team Tiers page (/team-tiers), computed from nflverse play-by-play.

  off / def   EPA per play on offense, and EPA per play allowed on defense (lower = better defense).
  offPass, offRush, defPass, defRush   the same split into dropbacks (sacks and scrambles included) and designed runs.
  offSr / defSr   success rate: share of plays that gain positive expected points (nflverse `success`).
  net         off - def, raw (not adjusted for the opponents a team has played).
  aOff / aDef / aNet   the same three numbers adjusted for schedule: what the team's offense and defense did per play
              compared with what an average offense or defense would have done against the same opponents (see adjust()).
  sos         strength of schedule: the average aNet of the opponents faced so far (positive = tougher than average);
              sosRank 1 = toughest schedule so far.
  rank / tier / move / q   all follow the schedule-adjusted aNet. rawRank is the rank by raw net.
              tier is 1 (best) to 5, by how many standard deviations a team's aNet sits from the league average.
              q is the chart quadrant (both / off / def / none), move is places gained (+) or lost (-) since the week before.

Plays counted: regular season, passes and runs with a recorded EPA, up to the last week in which every game is final
(read from data/schedule.json, so a week still being played is left out). Kneels, spikes, punts, kicks and
two-point tries have no pass/run EPA and drop out. Garbage time is not filtered.

Data: nflverse play-by-play (play_by_play_<season>.csv.gz from github.com/nflverse/nflverse-data releases, CC BY 4.0).
Schedule adjustment (added Nov 2026): every game gives two observations, the offense's EPA per play against that defense and
the defense's EPA allowed per play against that offense. A ridge regression y = mu + offense effect + defense effect, weighted
by plays, solves for all 32 offenses and defenses at once, so a team that beat up weak defenses is not credited as much as a
team that did it against strong ones. LAMBDA plays of prior pull every effect toward the league average, which stops a
few games from producing extreme ratings. LAMBDA = 300 was picked by backtesting on the 2024 and 2025 seasons (fit on the games
before each week from Week 6 on, predict that week's EPA per play): every value from 250 to 400 predicted best, and a small
LAMBDA overfits. At that setting the adjusted ratings predicted slightly better than the unadjusted ones (a gain of about
0.3 points of explained variance, so schedule matters, but less than the shrinkage). Home field is not modelled and garbage
time is not filtered (as in the raw numbers).

Usage: python3 -I data/build_tiers.py <path to play_by_play_<season>.csv.gz> [data/schedule.json] [output, default data/tiers.json]
"""
import csv, gzip, json, sys, datetime, math

FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
sched = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'data/schedule.json'))
by_week = {}
for g in sched['games']:
    by_week.setdefault(g[1], []).append(g[6] is not None and g[7] is not None)
done = [w for w in sorted(by_week) if all(by_week[w])]
thru = max(done) if done else 0
assert thru >= 1, 'no completed week in the schedule'

LAMBDA = 300   # prior weight, in plays (about 60% of a game), that shrinks each team's adjusted offense and defense toward average
OUT = sys.argv[3] if len(sys.argv) > 3 else 'data/tiers.json'
plays = []   # (week, off team, def team, is pass, epa, success)
with gzip.open(sys.argv[1], 'rt') as f:
    for r in csv.DictReader(f):
        if r['season_type'] != 'REG' or r['play_type'] not in ('pass', 'run') or not r['epa'] or not r['posteam'] or not r['defteam']:
            continue
        w = int(r['week'] or 0)
        if w > thru:
            continue
        plays.append((w, FIX.get(r['posteam'], r['posteam']), FIX.get(r['defteam'], r['defteam']), r['play_type'] == 'pass',
                      float(r['epa']), r['success'] == '1'))


def adjust(games):
    """Schedule-adjusted offense and defense for every team.

    games: {(week, offense team, defense team): [plays, total EPA]}. Returns {team: (aOff, aDef, [opponent by week])} where aOff
    is the team's EPA per play against an average defense and aDef the EPA per play it allows to an average offense."""
    obs = [(o, d, n, s / n) for (w, o, d), (n, s) in games.items()]
    teams = {t for o, d, _, _ in obs for t in (o, d)}
    mu = sum(n * y for _, _, n, y in obs) / sum(n for _, _, n, _ in obs)
    a, b = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)   # offense effect, defense effect (EPA allowed; higher is worse)
    for _ in range(1000):
        top = {t: [0.0, 0.0] for t in teams}
        for o, d, n, y in obs:
            top[o][0] += n * (y - mu - b[d]); top[o][1] += n
        new_a = {t: top[t][0] / (top[t][1] + LAMBDA) for t in teams}
        top = {t: [0.0, 0.0] for t in teams}
        for o, d, n, y in obs:
            top[d][0] += n * (y - mu - new_a[o]); top[d][1] += n
        new_b = {t: top[t][0] / (top[t][1] + LAMBDA) for t in teams}
        moved = max(max(abs(new_a[t] - a[t]), abs(new_b[t] - b[t])) for t in teams)
        a, b = new_a, new_b
        if moved < 1e-10:
            break
    opp = {t: {} for t in teams}
    for (w, o, d) in games:
        opp[o][w] = d; opp[d][w] = o
    return {t: (mu + a[t], mu + b[t], [opp[t][w] for w in sorted(opp[t])]) for t in teams}


def measure(upto):
    """Per-team measures from every counted play in weeks 1..upto."""
    a, games = {}, {}
    for w, o, d, ps, epa, ok in plays:
        if w > upto:
            continue
        g = games.setdefault((w, o, d), [0, 0.0]); g[0] += 1; g[1] += epa
        for side, t in (('o', o), ('d', d)):
            m = a.setdefault(t, {})
            for k in (side, side + ('P' if ps else 'R')):
                n = m.setdefault(k, [0, 0.0, 0])
                n[0] += 1; n[1] += epa; n[2] += ok
    out = {}
    for t, m in a.items():
        epa = lambda k: m[k][1] / m[k][0]
        sr = lambda k: m[k][2] / m[k][0]
        out[t] = {'plays': m['o'][0], 'off': epa('o'), 'def': epa('d'), 'offPass': epa('oP'), 'offRush': epa('oR'),
                  'defPass': epa('dP'), 'defRush': epa('dR'), 'offSr': sr('o'), 'defSr': sr('d')}
        out[t]['net'] = out[t]['off'] - out[t]['def']
    adj = adjust(games)
    for t, (ao, ad, _) in adj.items():
        out[t]['aOff'], out[t]['aDef'], out[t]['aNet'] = ao, ad, ao - ad
    for t, (_, _, opps) in adj.items():
        out[t]['sos'] = sum(out[o]['aNet'] for o in opps) / len(opps)
    return out


def ranks(m, key='aNet'):
    return {t: i + 1 for i, t in enumerate(sorted(m, key=lambda t: -m[t][key]))}


cur = measure(thru)
assert len(cur) == 32, len(cur)
rk, raw_rk = ranks(cur), ranks(cur, 'net')
prev = ranks(measure(thru - 1)) if thru > 1 else {}
sos_rk = {t: i + 1 for i, t in enumerate(sorted(cur, key=lambda t: -cur[t]['sos']))}
nets = [m['aNet'] for m in cur.values()]
mu = sum(nets) / 32
sd = math.sqrt(sum((x - mu) ** 2 for x in nets) / 32)
mo, md = sum(m['off'] for m in cur.values()) / 32, sum(m['def'] for m in cur.values()) / 32
amo, amd = sum(m['aOff'] for m in cur.values()) / 32, sum(m['aDef'] for m in cur.values()) / 32


def tier(z):
    return 1 if z >= 1 else 2 if z >= .35 else 3 if z > -.35 else 4 if z > -1 else 5


teams = {}
for t, m in cur.items():
    good_o, good_d = m['aOff'] >= amo, m['aDef'] <= amd
    teams[t] = {**{k: (v if k == 'plays' else round(v, 4)) for k, v in m.items()},
                'rank': rk[t], 'rawRank': raw_rk[t], 'sosRank': sos_rk[t], 'tier': tier((m['aNet'] - mu) / sd) if sd else 3,
                'q': 'both' if good_o and good_d else 'off' if good_o else 'def' if good_d else 'none',
                'move': (prev[t] - rk[t]) if prev else 0}
out = {'asOf': datetime.date.today().isoformat(), 'thru': thru,
       'avg': {'off': round(mo, 4), 'def': round(md, 4), 'aOff': round(amo, 4), 'aDef': round(amd, 4)},
       'adjusted': True, 'lambda': LAMBDA,
       'tiers': [[1, 'Tier 1', 'Best in the league'], [2, 'Tier 2', 'Good'], [3, 'Tier 3', 'Middle of the pack'], [4, 'Tier 4', 'Struggling'], [5, 'Tier 5', 'Bottom of the league']],
       'source': f'PlainStats, from nflverse play-by-play through Week {thru}: expected points added (EPA) per pass or run play, regular season, garbage time included. Ranks and tiers use net EPA adjusted for the opponents each team has played',
       'teams': teams}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
top = sorted(teams, key=lambda t: teams[t]['rank'])
print('thru week', thru, 'plays', len(plays), 'tiers', [sum(1 for t in teams.values() if t['tier'] == i) for i in range(1, 6)])
print('top 5', [(t, teams[t]['aOff'], teams[t]['aDef']) for t in top[:5]])
print('toughest schedules', [(t, teams[t]['sos']) for t in sorted(teams, key=lambda t: teams[t]['sosRank'])[:5]])
