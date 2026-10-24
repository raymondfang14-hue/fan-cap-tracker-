"""Build data/schedule.json (every game of the season with kickoff and score) from nflverse schedules.

Usage: python3 -I data/build_schedule.py <path to games.csv> [season]
Data: nflverse schedules/games.csv (github.com/nflverse/nflverse-data releases, CC BY 4.0). Kickoff times are US Eastern.
Runs every day so scores stay current. The model's picks and the standings come from data/projections.json (weekly).
Each game row: [game_id, week, gameday, gametime, away, home, away_score, home_score, overtime, neutral site name or ''].
Scores are null until the game is final. Betting lines in games.csv are not used."""
import csv, json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
SEASON = sys.argv[2] if len(sys.argv) > 2 else '2026'
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
tf = lambda t: FIX.get(t, t)
sc = lambda v: int(v) if v not in ('', 'NA', None) else None
rows = []
for g in csv.DictReader(open(sys.argv[1], encoding='utf-8')):
    if g['season'] != SEASON or g['game_type'] != 'REG': continue
    a, h = sc(g['away_score']), sc(g['home_score'])
    rows.append([g['game_id'], int(g['week']), g['gameday'], g['gametime'], tf(g['away_team']), tf(g['home_team']), a, h,
                 1 if g['overtime'] == '1' else 0, g['stadium'] if g['location'] == 'Neutral' else ''])
rows.sort(key=lambda r: (r[1], r[2], r[3], r[0]))
final = sum(1 for r in rows if r[7] is not None)
json.dump({'asOf': datetime.date.today().isoformat(), 'season': int(SEASON), 'weeks': max((r[1] for r in rows), default=18),
           'source': 'nflverse schedules (games.csv). Kickoff times are Eastern.', 'games': rows},
          open(os.path.join(HERE, 'schedule.json'), 'w'), separators=(',', ':'))
print('schedule:', len(rows), 'games,', final, 'final')
