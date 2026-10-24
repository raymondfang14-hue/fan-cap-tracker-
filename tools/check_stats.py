"""Audit the season stats behind every player card's On the field tab.

Run:  python3 -I tools/check_stats.py <folder with nflverse stats_player_week_<S>.csv> [season] [last week]

Sums the raw nflverse box scores per player (by gsis id) and checks, for every player in data/nfl.json:
  - data/nfl.json has one row per gsis id (no player listed twice under two spellings)
  - a player with box-score stats has a data/stats.json row with the same gid (the page attaches stats by gid)
  - that row's totals match the raw sums: tackles, sacks, TFL, QB hits, forced fumbles, interceptions, passes defended
    for defensive players; passing, rushing, receiving for offensive players; field goals for kickers
  - games played are not lower than the weeks he has a box score
An offensive player's tackle after a turnover is not shown on his card by design, so it is not counted as a mismatch.
Exits 1 if anything is wrong.
"""
import csv, json, os, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NV = sys.argv[1]
S = sys.argv[2] if len(sys.argv) > 2 else '2026'
LAST = int(sys.argv[3]) if len(sys.argv) > 3 else json.load(open(os.path.join(ROOT, 'data/stats.json'))).get('thru', 99)
num = lambda v: float(v) if v not in ('', None, 'NA') else 0.0

DEF = {'tk': ('def_tackles_solo', 'def_tackle_assists'), 'sck': ('def_sacks',), 'tfl': ('def_tackles_for_loss',), 'qbh': ('def_qb_hits',),
       'ff': ('def_fumbles_forced',), 'dint': ('def_interceptions',), 'pd': ('def_pass_defended',)}
OFF = {'att': ('attempts',), 'cmp': ('completions',), 'pyd': ('passing_yards',), 'ptd': ('passing_tds',), 'int': ('passing_interceptions',),
       'car': ('carries',), 'ryd': ('rushing_yards',), 'rtd': ('rushing_tds',), 'tgt': ('targets',), 'rec': ('receptions',),
       'ryds': ('receiving_yards',), 'rectd': ('receiving_tds',)}
KICK = {'fgm': ('fg_made',), 'fga': ('fg_att',)}
OFFPOS = {'QB', 'RB', 'FB', 'WR', 'TE', 'LT', 'LG', 'C', 'RG', 'RT', 'OL', 'T', 'G'}

raw, weeks = defaultdict(lambda: defaultdict(float)), defaultdict(set)
cols = {c for d in (DEF, OFF, KICK) for v in d.values() for c in v}
for r in csv.DictReader(open(os.path.join(NV, f'stats_player_week_{S}.csv'), encoding='utf-8')):
    if r['season_type'] != 'REG' or int(r['week']) > LAST: continue
    g = r['player_id']; weeks[g].add(int(r['week']))
    for c in cols: raw[g][c] += num(r.get(c))

D = json.load(open(os.path.join(ROOT, 'data/nfl.json')))['players']
SD = json.load(open(os.path.join(ROOT, 'data/stats.json')))
byG = {s['gid']: s for s in SD['players'] if s.get('gid')}
problems = []

dup = [g for g, n in Counter(p[19] for p in D if p[19]).items() if n > 1]
for g in dup: problems.append(f'listed twice: {[p[0] for p in D if p[19] == g]} ({g})')

checked = 0
for p in D:
    name, team, pos, g = p[0], p[1], p[2], p[19]
    if not g or g not in raw or not any(raw[g].values()): continue
    s = byG.get(g)
    if not s: problems.append(f'{name} ({team}): has {S} box scores but no stats row with gid {g}'); continue
    checked += 1
    m = s.get('m') or {}
    groups = [KICK] + ([OFF] if pos in OFFPOS else [DEF])
    for grp in groups:
        for k, src in grp.items():
            want = sum(raw[g][c] for c in src); have = m.get(k, 0)
            if abs(have - want) > 0.01: problems.append(f'{name} ({team}, {pos}): {k} shows {have:g}, box scores say {want:g}')
    if s.get('g', 0) < len(weeks[g]): problems.append(f"{name} ({team}): {s.get('g')} games shown, box scores in {len(weeks[g])} weeks")

for line in problems[:200]: print('FAIL', line)
print(f'{checked} player cards checked against nflverse box scores through week {LAST}, {len(problems)} problems')
sys.exit(1 if problems else 0)
