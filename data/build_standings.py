"""Update records in data/season.json (w, l, t, pf, pa, strk per team) from nflverse game results.
Coaches, 2025 records, rookies, comeback and prevRanks are left as they are.
Data: nflverse schedules (games.csv from github.com/nflverse/nflverse-data releases, CC BY 4.0).
Usage: python3 -I data/build_standings.py <path to games.csv> [season]"""
import csv, json, sys, datetime
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
for t, r in rec.items():
    st = ''
    if r['res']:
        last = r['res'][-1]; n = 0
        for x in reversed(r['res']):
            if x != last: break
            n += 1
        st = f'{last}{n}'
    s['teams'][t].update({'w': r['w'], 'l': r['l'], 't': r['t'], 'pf': r['pf'], 'pa': r['pa'], 'strk': st})
s['asOf'] = datetime.date.today().isoformat()
s['source'] = 'Records: nflverse game results. Coaches: team announcements and Wikipedia.'
json.dump(s, open('data/season.json', 'w'), separators=(',', ':'))
print('games', len(games), {t: (r['w'], r['l'], r['t']) for t, r in list(rec.items())[:4]})
