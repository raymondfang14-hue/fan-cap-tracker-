"""Write data/olwin.json: team offensive line measures PlainStats computes itself from nflverse play-by-play.

  pbwr  "Pass protection": share of the team's dropbacks with no sack and no QB hit (scrambles count as dropbacks).
  rbwr  "Run success": share of the team's designed runs (rush attempts that are not QB scrambles or kneels) that
        gain positive expected points (nflverse `success`).
Both are regular-season plays only, two-point tries and aborted snaps excluded. The keys keep their old names so the
page reads them unchanged; *Rk is the rank among 32 teams (1 = best).

Data: nflverse play-by-play (play_by_play_<season>.csv.gz from github.com/nflverse/nflverse-data releases, CC BY 4.0).
Usage: python3 -I data/build_olwin.py <path to play_by_play_<season>.csv.gz>
"""
import csv, gzip, json, sys, datetime

FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
db, hit, ru, ok, wk = {}, {}, {}, {}, 0
with gzip.open(sys.argv[1], 'rt') as f:
    for r in csv.DictReader(f):
        if r['season_type'] != 'REG' or r['two_point_attempt'] == '1' or r['aborted_play'] == '1' or not r['posteam']:
            continue
        t = FIX.get(r['posteam'], r['posteam']); wk = max(wk, int(r['week'] or 0))
        if r['qb_dropback'] == '1':
            db[t] = db.get(t, 0) + 1
            if r['sack'] == '1' or r['qb_hit'] == '1': hit[t] = hit.get(t, 0) + 1
        elif r['rush_attempt'] == '1' and r['qb_scramble'] != '1' and r['qb_kneel'] != '1':
            ru[t] = ru.get(t, 0) + 1
            if r['success'] == '1' or (r['epa'] and float(r['epa']) > 0): ok[t] = ok.get(t, 0) + 1
teams = {}
for t in db:
    teams[t] = {'pbwr': round(1 - hit.get(t, 0) / db[t], 3), 'rbwr': round(ok.get(t, 0) / max(1, ru.get(t, 0)), 3)}
for k in ('pbwr', 'rbwr'):
    for i, t in enumerate(sorted(teams, key=lambda t: -teams[t][k])): teams[t][k + 'Rk'] = i + 1
assert len(teams) == 32, len(teams)
out = {'asOf': datetime.date.today().isoformat(), 'thru': wk,
       'source': f'PlainStats, from nflverse play-by-play through Week {wk}: pass protection = dropbacks with no sack or QB hit; run success = designed runs with positive expected points',
       'teams': teams}
json.dump(out, open('data/olwin.json', 'w'), separators=(',', ':'))
print('teams', len(teams), 'thru week', wk, 'KC', teams['KC'])
