"""Build Plain Cap data/history_old.json: season TOTALS (no game logs) before the seasons in data/history.json,
only for players on a current roster (data/nfl.json). Loaded by the page only when a player's Stats tab opens.

Usage: python3 -I data/build_history_old.py <dir with stats_player_reg_<S>.csv> [first season, default 1999]
Needs in <dir>: stats_player_reg_<S>.csv (or reg_<S>.csv) for every season from the first season up to the season
before data/history.json starts. Download with curl -sSL from
https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_<S>.csv
Snap counts: also needs snap_counts_<S>.csv for 2013 on and players.csv in <dir>. A season with no box-score row (offensive
linemen, special teamers) is filled with games and team from the snap counts, so every season he played shows up.
Roster matching: a roster player with a gsis id in data/nfl.json (row index 19) uses it directly; otherwise a roster player is matched to nflverse by the gsis id already in data/history.json (name + team),
otherwise by an exact normalized name + position group that is unique in the old data. Run it again whenever a
player joins a team (the daily refresh does) so new signings pick up earlier seasons. When a new season starts,
history.json moves its window forward (build_history.py drops last season's weekly game log by itself, since
only the current season keeps one); pass the new cut-off by running with the same folder plus the newly finished season."""
import csv, json, os, re, sys, datetime
D = sys.argv[1]
FIRST = int(sys.argv[2]) if len(sys.argv) > 2 else 1999
HERE = os.path.dirname(os.path.abspath(__file__))
H = json.load(open(os.path.join(HERE, 'history.json')))
LAST = H['seasons'][0] - 1
TEAMFIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR', 'LVR': 'LV'}
tf = lambda t: TEAMFIX.get(t, t)
num = lambda v: float(v) if v not in ('', None, 'NA') else 0.0
SUF = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b')
nk = lambda n: re.sub(r'\s+', ' ', SUF.sub('', re.sub(r"[.,'’]", '', n.lower()).replace('-', ' '))).strip()
HG = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'HB': 'RB', 'WR': 'WR', 'TE': 'TE', 'T': 'OL', 'G': 'OL', 'C': 'OL', 'OT': 'OL', 'OG': 'OL', 'OL': 'OL', 'LT': 'OL', 'LG': 'OL', 'RG': 'OL', 'RT': 'OL',
      'DE': 'DL', 'DT': 'DL', 'NT': 'DL', 'DL': 'DL', 'EDGE': 'DL', 'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB', 'LB': 'LB', 'CB': 'DB', 'DB': 'DB', 'S': 'DB', 'FS': 'DB', 'SS': 'DB', 'SAF': 'DB', 'K': 'K', 'PK': 'K', 'P': 'P'}
hg = lambda p: HG.get(p, 'X')
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
clean = lambda d: {k: (round(v, 1) if isinstance(v, float) and v != int(v) else int(v)) for k, v in d.items() if v}

# 1) roster -> gsis id via history.json, else mark for name matching
roster = json.load(open(os.path.join(HERE, 'nfl.json')))['players']
hk, hn = {}, {}
for r in H['players']:
    k = nk(r['n']); hn.setdefault(k, []).append(r)
    for l in r['s'].values():
        for t in [l['t']] + l.get('tt', []): hk.setdefault(k + '|' + t, r)
want = {}          # gsis id -> current team
byname = {}        # normalized name -> [(group, team)] for roster players with no id yet
for row in roster:
    name, team, pos = row[0], row[1], row[2]
    k = nk(name); r = hk.get(k + '|' + team)
    if len(row) > 19 and row[19]: want[row[19]] = team; continue
    if r and (hg(r['pos']) == hg(pos) or hg(pos) == 'X' or hg(r['pos']) == 'X'): want[r['id']] = team
    else: byname.setdefault(k, []).append((hg(pos), team))

# 2) read old seasons
players = {}
for S in range(FIRST, LAST + 1):
    path = next((p for p in (os.path.join(D, f'stats_player_reg_{S}.csv'), os.path.join(D, f'reg_{S}.csv')) if os.path.exists(p)), None)
    if not path: print('missing season', S); continue
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r['season_type'] != 'REG': continue
        line = clean({k: f(r) for k, f in F.items()}); line['g'] = int(num(r['games'])); line['t'] = tf(r['recent_team'])
        fgl = num(r['fg_long'])
        if fgl: line['fgl'] = int(fgl)
        p = players.setdefault(r['player_id'], {'id': r['player_id'], 'n': r['player_display_name'] or r['player_name'], 'pos': r['position'], 's': {}})
        p['pos'] = r['position'] or p['pos']; p['s'][str(S)] = line
# 2b) games from snap counts (2013 on) fill seasons with no box-score row
PFR = {}
if os.path.exists(os.path.join(D, 'players.csv')):
    for r in csv.DictReader(open(os.path.join(D, 'players.csv'), encoding='utf-8')):
        if r['pfr_id'] and r['gsis_id']: PFR[r['pfr_id']] = (r['gsis_id'], r['display_name'], r['position'])
SG = {}   # gsis -> season -> team -> game ids
for S in range(max(FIRST, 2013), LAST + 1):
    path = os.path.join(D, f'snap_counts_{S}.csv')
    if not os.path.exists(path): print('missing snap counts', S); continue
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r['game_type'] != 'REG' or r['pfr_player_id'] not in PFR: continue
        if num(r['offense_snaps']) + num(r['defense_snaps']) + num(r['st_snaps']) <= 0: continue
        gid = PFR[r['pfr_player_id']][0]
        if gid in want: SG.setdefault(gid, {}).setdefault(S, {}).setdefault(tf(r['team']), set()).add(r['game_id'])
for gid, byS in SG.items():
    p = players.get(gid)
    if p is None: _, nm, ps = next(v for v in PFR.values() if v[0] == gid); p = players[gid] = {'id': gid, 'n': nm, 'pos': ps, 's': {}}
    for S, byT in byS.items():
        n = sum(len(v) for v in byT.values()); ln = p['s'].get(str(S))
        if ln is None: p['s'][str(S)] = {'g': n, 't': max(byT, key=lambda t: len(byT[t]))}
        elif n > ln.get('g', 0): ln['g'] = n
# 3) name matching for roster players without an id
nm = {}
for p in players.values(): nm.setdefault(nk(p['n']), []).append(p)
matched_name = 0; unmatched = []
for k, lst in byname.items():
    for grp, team in lst:
        c = [p for p in nm.get(k, []) if hg(p['pos']) == grp]
        if len(c) == 1 and c[0]['id'] not in want: want[c[0]['id']] = team; matched_name += 1
        elif not c and k not in hn: unmatched.append(k)
out = []
for pid, team in want.items():
    p = players.get(pid)
    if p and p['s']: out.append({'id': p['id'], 'n': p['n'], 'pos': p['pos'], 'ct': team, 's': p['s']})
out.sort(key=lambda r: r['n'])
json.dump({'asOf': datetime.date.today().isoformat(), 'seasons': [FIRST, LAST], 'note': 'Regular-season totals only, current NFL rosters. nflverse stats_player_reg.',
           'players': out}, open(os.path.join(HERE, 'history_old.json'), 'w'), separators=(',', ':'))
print(len(out), 'players with seasons', FIRST, '-', LAST, '| matched by name only:', matched_name, '|', os.path.getsize(os.path.join(HERE, 'history_old.json')), 'bytes')
