"""Build data/depth.json: each team's listed depth chart (offense, defense, special teams) from nflverse.

Usage: python3 -I data/build_depth.py <path to depth_charts_<season>.csv> [season]
Data: nflverse depth_charts/depth_charts_<season>.csv (github.com/nflverse/nflverse-data releases, CC BY 4.0). The file holds
every snapshot of the season; only the newest snapshot is used. Runs every day.
Output: {asOf, season, snap, source, teams: {TEAM: {O: {pos: [[gid, name], ...]}, D: {...}, S: {...}}}}
- Players are listed in depth order (first string first) under each position slot (QB, LT, LDE, MLB, PK ...).
- The defensive base (4-3 or 3-4) is whatever the team lists; names differ by base, so slots follow the file.
- gid is the gsis id (match players by it, never by name); it is '' when the file has none.
- This is the team's listed chart, not snap counts. The page's lineups come from snaps; use this for who is listed first."""
import csv, json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
SEASON = sys.argv[2] if len(sys.argv) > 2 else '2026'
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
tf = lambda t: FIX.get(t, t)
SIDE = {'3WR 1TE': 'O', 'Base 4-3 D': 'D', 'Base 3-4 D': 'D', 'Special Teams': 'S'}

rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
snap = max(r['dt'] for r in rows)
teams = {}
for r in rows:
    if r['dt'] != snap: continue
    side = SIDE.get(r['pos_grp'])
    if not side or not r['player_name']: continue
    slot = teams.setdefault(tf(r['team']), {'O': {}, 'D': {}, 'S': {}})[side].setdefault(r['pos_abb'], [])
    slot.append((int(r['pos_rank'] or 99), int(r['pos_slot'] or 0), r['gsis_id'], r['player_name']))
out = {}
for t, sides in sorted(teams.items()):
    out[t] = {s: {pos: [[g, n] for _, _, g, n in sorted(v)] for pos, v in sides[s].items()} for s in 'ODS'}
if len(out) != 32:
    sys.exit(f'depth: expected 32 teams, got {len(out)}')
json.dump({'asOf': datetime.date.today().isoformat(), 'season': int(SEASON), 'snap': snap,
           'source': 'nflverse depth_charts (newest snapshot). Listed depth order, not snap counts.', 'teams': out},
          open(os.path.join(HERE, 'depth.json'), 'w'), separators=(',', ':'))
print('depth:', len(out), 'teams, snapshot', snap, ',', sum(len(v) for s in out.values() for side in s.values() for v in side.values()), 'listed players')
