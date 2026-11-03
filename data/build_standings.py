"""Update records in data/season.json (w, l, t, pf, pa, strk per team) and the schedule-adjusted scoring margin from nflverse game results.
  srs  scoring margin per game adjusted for the opponents played and for home field (points; 0 = average team, positive = better).
  sos  strength of schedule: the average srs of the opponents faced so far (points; positive = tougher than average).
SRS is a ridge regression on every game's home margin (home rating - away rating + home field); SRS_LAMBDA games of prior pull each
rating toward 0, and SRS_HFA points of home field apply unless the game is at a neutral site. Both were picked by
tools/backtest_margin.py (2024 and 2025: 4% lower prediction error than the plain average margin). Only scores and the
neutral-site flag are read from games.csv, never the betting columns.
Coaches, 2025 records, rookies, comeback and prevRanks are left as they are.
Data: nflverse schedules (games.csv from github.com/nflverse/nflverse-data releases, CC BY 4.0).
Usage: python3 -I data/build_standings.py <path to games.csv> [season]"""
import csv, json, sys, datetime
SRS_LAMBDA, SRS_HFA = 4, 1.5
SEASON = sys.argv[2] if len(sys.argv) > 2 else '2026'
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
s = json.load(open('data/season.json'))
rec = {t: {'w': 0, 'l': 0, 't': 0, 'pf': 0, 'pa': 0, 'res': []} for t in s['teams']}
games = [g for g in csv.DictReader(open(sys.argv[1])) if g['season'] == SEASON and g['game_type'] == 'REG' and g['home_score'] != '']
games.sort(key=lambda g: (g['gameday'], g['gametime']))
for g in games:
    for side, opp in (('home', 'away'), ('away', 'home')):
        t = FIX.get(g[side + '_team'], g[side + '_team'])
        if t not in rec: continue
        a, b = int(g[side + '_score']), int(g[opp + '_score'])
        r = rec[t]; r['pf'] += a; r['pa'] += b
        k = 'w' if a > b else 'l' if a < b else 't'; r[k] += 1; r['res'].append(k.upper())
# schedule-adjusted margin (SRS) and strength of schedule
ob = [(FIX.get(g['home_team'], g['home_team']), FIX.get(g['away_team'], g['away_team']), int(g['home_score']) - int(g['away_score']), g['location'] != 'Home') for g in games]
ob = [x for x in ob if x[0] in rec and x[1] in rec]
rating = dict.fromkeys(rec, 0.0)
for _ in range(500):
    num, den = dict.fromkeys(rec, 0.0), dict.fromkeys(rec, 0.0)
    for h, a, m, neutral in ob:
        m -= 0 if neutral else SRS_HFA
        num[h] += m + rating[a]; den[h] += 1
        num[a] += -m + rating[h]; den[a] += 1
    new = {t: num[t] / (den[t] + SRS_LAMBDA) for t in rec}
    moved = max(abs(new[t] - rating[t]) for t in rec)
    rating = new
    if moved < 1e-9:
        break
opps = {t: [] for t in rec}
for h, a, _, _ in ob:
    opps[h].append(a); opps[a].append(h)
for t, r in rec.items():
    st = ''
    if r['res']:
        last = r['res'][-1]; n = 0
        for x in reversed(r['res']):
            if x != last: break
            n += 1
        st = f'{last}{n}'
    s['teams'][t].update({'w': r['w'], 'l': r['l'], 't': r['t'], 'pf': r['pf'], 'pa': r['pa'], 'strk': st})
    if opps[t]:
        s['teams'][t].update({'srs': round(rating[t], 2), 'sos': round(sum(rating[o] for o in opps[t]) / len(opps[t]), 2)})
s['asOf'] = datetime.date.today().isoformat()
s['source'] = 'Records: nflverse game results. Coaches: team announcements and Wikipedia.'
json.dump(s, open('data/season.json', 'w'), separators=(',', ':'))
top = sorted(rec, key=lambda t: -rating[t])
print('srs top', [(t, round(rating[t], 1)) for t in top[:5]], 'toughest schedule', sorted(rec, key=lambda t: -sum(rating[o] for o in opps[t]) / max(1, len(opps[t])))[:3])
print('games', len(games), {t: (r['w'], r['l'], r['t']) for t, r in list(rec.items())[:4]})
