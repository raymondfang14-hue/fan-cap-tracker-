"""Build data/injuries.json: every player's official injury-report history this season, by gsis id.

Usage: python3 -I data/build_injuries.py <path to injuries_<season>.csv> [season]
Data: nflverse injuries/injuries_<season>.csv (the NFL's official game-status and practice reports, CC BY 4.0). Runs every day.
Output: {asOf, season, thru, source, players: {gid: [[week, team, status, injury, practice], ...]}}
- status: 'O' Out, 'D' Doubtful, 'Q' Questionable, '' none listed. practice: 'D' did not practice, 'L' limited, 'F' full, ''.
- injury: the primary injury on the game report, or on the practice report when no game report exists.
- Only weeks where the player was listed with a game status or missed or limited practice are kept. A full-practice row with
  no status is dropped, so a player's list is his actual injury history. Weeks are sorted. Match players by gid, never name.
- Not used for the game-page picks (build_gameday.py reads the CSV itself)."""
import csv, json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
SEASON = sys.argv[2] if len(sys.argv) > 2 else '2026'
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
tf = lambda t: FIX.get(t, t)
STATUS = {'Out': 'O', 'Doubtful': 'D', 'Questionable': 'Q'}
PRACTICE = {'Did Not Participate In Practice': 'D', 'Limited Participation in Practice': 'L', 'Full Participation in Practice': 'F'}

players, thru = {}, 0
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8')):
    if r['season'] != SEASON or r['game_type'] != 'REG' or not r['gsis_id']: continue
    st, pr = STATUS.get(r['report_status'], ''), PRACTICE.get(r['practice_status'], '')
    wk = int(r['week'])
    thru = max(thru, wk)
    if not st and pr in ('', 'F'): continue
    inj = (r['report_primary_injury'] or r['practice_primary_injury']).strip()
    if inj.lower().startswith('not injury related'): inj = 'Not injury related'
    players.setdefault(r['gsis_id'], []).append([wk, tf(r['team']), st, inj, pr])
for rows in players.values(): rows.sort(key=lambda x: x[0])
json.dump({'asOf': datetime.date.today().isoformat(), 'season': int(SEASON), 'thru': thru,
           'source': 'nflverse injuries (the NFL official injury report).', 'players': players},
          open(os.path.join(HERE, 'injuries.json'), 'w'), separators=(',', ':'))
print('injuries:', len(players), 'players listed through week', thru)
