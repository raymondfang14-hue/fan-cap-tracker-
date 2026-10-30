"""Write data/tiers.json: the Weekly Team Tiers page (/team-tiers), computed from nflverse play-by-play.

  off / def   EPA per play on offense, and EPA per play allowed on defense (lower = better defense).
  offPass, offRush, defPass, defRush   the same split into dropbacks (sacks and scrambles included) and designed runs.
  offSr / defSr   success rate: share of plays that gain positive expected points (nflverse `success`).
  net         off - def, the one number the tiers are cut from.
  tier        1 (best) to 5, by how many standard deviations a team's net EPA/play sits from the league average.
  q           quadrant on the chart: both / off / def / none.
  move        places gained (+) or lost (-) in the net EPA ranking since the week before.

Plays counted: regular season, passes and runs with a recorded EPA, up to the last week in which every game is final
(read from data/schedule.json, so a week still being played is left out). Kneels, spikes, punts, kicks and
two-point tries have no pass/run EPA and drop out. Garbage time is not filtered.

Data: nflverse play-by-play (play_by_play_<season>.csv.gz from github.com/nflverse/nflverse-data releases, CC BY 4.0).
Usage: python3 -I data/build_tiers.py <path to play_by_play_<season>.csv.gz> [data/schedule.json]
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


def measure(upto):
    """Per-team measures from every counted play in weeks 1..upto."""
    a = {}
    for w, o, d, ps, epa, ok in plays:
        if w > upto:
            continue
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
    return out


def ranks(m):
    return {t: i + 1 for i, t in enumerate(sorted(m, key=lambda t: -m[t]['net']))}


cur = measure(thru)
assert len(cur) == 32, len(cur)
rk = ranks(cur)
prev = ranks(measure(thru - 1)) if thru > 1 else {}
nets = [m['net'] for m in cur.values()]
mu = sum(nets) / 32
sd = math.sqrt(sum((x - mu) ** 2 for x in nets) / 32)
mo, md = sum(m['off'] for m in cur.values()) / 32, sum(m['def'] for m in cur.values()) / 32


def tier(z):
    return 1 if z >= 1 else 2 if z >= .35 else 3 if z > -.35 else 4 if z > -1 else 5


teams = {}
for t, m in cur.items():
    good_o, good_d = m['off'] >= mo, m['def'] <= md
    teams[t] = {**{k: (v if k == 'plays' else round(v, 4)) for k, v in m.items()},
                'rank': rk[t], 'tier': tier((m['net'] - mu) / sd) if sd else 3,
                'q': 'both' if good_o and good_d else 'off' if good_o else 'def' if good_d else 'none',
                'move': (prev[t] - rk[t]) if prev else 0}
out = {'asOf': datetime.date.today().isoformat(), 'thru': thru,
       'avg': {'off': round(mo, 4), 'def': round(md, 4)},
       'tiers': [[1, 'Tier 1', 'Best in the league'], [2, 'Tier 2', 'Good'], [3, 'Tier 3', 'Middle of the pack'], [4, 'Tier 4', 'Struggling'], [5, 'Tier 5', 'Bottom of the league']],
       'source': f'PlainStats, from nflverse play-by-play through Week {thru}: expected points added (EPA) per pass or run play, regular season, garbage time included',
       'teams': teams}
json.dump(out, open('data/tiers.json', 'w'), separators=(',', ':'))
top = sorted(teams, key=lambda t: teams[t]['rank'])
print('thru week', thru, 'plays', len(plays), 'tiers', [sum(1 for t in teams.values() if t['tier'] == i) for i in range(1, 6)])
print('top 5', [(t, teams[t]['off'], teams[t]['def']) for t in top[:5]])
