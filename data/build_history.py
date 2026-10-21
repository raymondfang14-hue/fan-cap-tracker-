"""Build Plain Cap data/history.json (season-by-season stats and this season's game log) and
data/drafted.json (recent draft classes) from nflverse files.

Usage: python3 -I data/build_history.py <dir with nflverse csvs> <current season> [first season]
Needs in <dir>: stats_player_week_<S>.csv for every season from the first season (default: current - 3)
through the current one, and draft_picks.csv. Download with curl -sSL from
https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_<S>.csv and
https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv
Regular-season games only. Writes data/history.json and data/drafted.json next to this script."""
import csv, json, os, sys, datetime
from collections import defaultdict

D, CUR = sys.argv[1], int(sys.argv[2])
FIRST = int(sys.argv[3]) if len(sys.argv) > 3 else CUR - 3
HERE = os.path.dirname(os.path.abspath(__file__))
TEAMFIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR', 'LVR': 'LV', 'GNB': 'GB',
           'KAN': 'KC', 'NOR': 'NO', 'NWE': 'NE', 'SFO': 'SF', 'TAM': 'TB', 'RAM': 'LAR', 'SDG': 'LAC', 'CLT': 'IND',
           'CRD': 'ARI', 'HTX': 'HOU', 'OTI': 'TEN', 'RAV': 'BAL', 'RAI': 'LV', 'LAS': 'LV'}
tf = lambda t: TEAMFIX.get(t, t)
num = lambda v: float(v) if v not in ('', None, 'NA') else 0.0

# short key -> function of one csv row
F = {
    'cmp': lambda r: num(r['completions']), 'att': lambda r: num(r['attempts']), 'pyd': lambda r: num(r['passing_yards']),
    'ptd': lambda r: num(r['passing_tds']), 'int': lambda r: num(r['passing_interceptions']), 'sk': lambda r: num(r['sacks_suffered']),
    'car': lambda r: num(r['carries']), 'ryd': lambda r: num(r['rushing_yards']), 'rtd': lambda r: num(r['rushing_tds']),
    'tgt': lambda r: num(r['targets']), 'rec': lambda r: num(r['receptions']), 'reyd': lambda r: num(r['receiving_yards']),
    'retd': lambda r: num(r['receiving_tds']),
    'fl': lambda r: num(r['rushing_fumbles_lost']) + num(r['receiving_fumbles_lost']) + num(r['sack_fumbles_lost']),
    'tk': lambda r: num(r['def_tackles_solo']) + num(r['def_tackle_assists']), 'tfl': lambda r: num(r['def_tackles_for_loss']),
    'dsk': lambda r: num(r['def_sacks']), 'qbh': lambda r: num(r['def_qb_hits']), 'dint': lambda r: num(r['def_interceptions']),
    'pd': lambda r: num(r['def_pass_defended']), 'ff': lambda r: num(r['def_fumbles_forced']), 'dtd': lambda r: num(r['def_tds']),
    'fgm': lambda r: num(r['fg_made']), 'fga': lambda r: num(r['fg_att']), 'xpm': lambda r: num(r['pat_made']),
    'xpa': lambda r: num(r['pat_att']), 'pun': lambda r: num(r['pt_att']), 'puy': lambda r: num(r['pt_yards']),
    'pi20': lambda r: num(r['pt_inside_20']), 'fp': lambda r: num(r['fantasy_points_ppr']),
}
MAXK = {'fgl': lambda r: num(r['fg_long'])}
clean = lambda d: {k: (round(v, 1) if isinstance(v, float) and v != int(v) else int(v)) for k, v in d.items() if v}

players = {}
for S in range(FIRST, CUR + 1):
    path = os.path.join(D, f'stats_player_week_{S}.csv')
    if not os.path.exists(path):
        print('missing', path); continue
    rows = [r for r in csv.DictReader(open(path, encoding='utf-8')) if r['season_type'] == 'REG']
    for r in rows:
        pid = r['player_id']
        p = players.setdefault(pid, {'id': pid, 'n': r['player_display_name'] or r['player_name'], 'pos': r['position'], 'seasons': {}, 'wk': []})
        p['n'] = r['player_display_name'] or p['n']; p['pos'] = r['position'] or p['pos']
        s = p['seasons'].setdefault(S, {'teams': defaultdict(int), 'g': 0, 'v': defaultdict(float), 'fgl': 0})
        t = tf(r['team']); s['teams'][t] += 1; s['g'] += 1
        for k, f in F.items(): s['v'][k] += f(r)
        s['fgl'] = max(s['fgl'], MAXK['fgl'](r))
        if S == CUR:
            line = clean({k: f(r) for k, f in F.items()})
            p['wk'].append([int(r['week']), tf(r['opponent_team']), t, line])

out = []
for p in players.values():
    sea = {}
    for S, s in sorted(p['seasons'].items()):
        teams = sorted(s['teams'].items(), key=lambda x: -x[1])
        line = clean(dict(s['v'])); line['g'] = s['g']; line['t'] = teams[0][0]
        if len(teams) > 1: line['tt'] = [t for t, _ in teams]
        if s['fgl']: line['fgl'] = int(s['fgl'])
        sea[str(S)] = line
    rec = {'id': p['id'], 'n': p['n'], 'pos': p['pos'], 's': sea}
    if p['wk']: rec['w'] = sorted(p['wk'])
    out.append(rec)
out.sort(key=lambda r: r['n'])
thru = max([w[0] for r in out for w in r.get('w', [])] or [0])
hist = {'asOf': datetime.date.today().isoformat(), 'current': CUR, 'seasons': list(range(FIRST, CUR + 1)), 'thru': thru,
        'note': 'Regular season only. nflverse weekly player stats.', 'source': 'nflverse-data releases: stats_player', 'players': out}
json.dump(hist, open(os.path.join(HERE, 'history.json'), 'w'), separators=(',', ':'))

dr = []
for r in csv.DictReader(open(os.path.join(D, 'draft_picks.csv'), encoding='utf-8')):
    y = int(r['season'])
    if y < CUR - 5: continue
    dr.append([r['gsis_id'], r['pfr_player_name'], y, int(r['round']), int(r['pick']), tf(r['team']), r['position'], r['college']])
json.dump({'asOf': datetime.date.today().isoformat(), 'source': 'nflverse-data releases: draft_picks',
           'cols': ['gsis', 'name', 'season', 'round', 'pick', 'team', 'pos', 'college'], 'picks': dr},
          open(os.path.join(HERE, 'drafted.json'), 'w'), separators=(',', ':'))
print(len(out), 'players,', 'seasons', hist['seasons'], 'thru week', thru, '|', len(dr), 'draft picks',
      os.path.getsize(os.path.join(HERE, 'history.json')), 'bytes')
