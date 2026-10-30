"""data/splits.json: per-week snap counts and garbage-time stat lines, for the filters on Players > Season stats.

Usage: python3 -I data/build_splits.py <dir with nflverse csvs> <current season>
Needs in <dir>: play_by_play_<S>.csv.gz, snap_counts_<S>.csv and players.csv. Download with curl -sSL from
https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_<S>.csv.gz
https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_<S>.csv
https://github.com/nflverse/nflverse-data/releases/download/players/players.csv
Then run `python3 -I data/build_hist_split.py`, which merges this file into data/hist/wk<S>.json (the file the page loads).

Garbage time: a regular-season pass, run or sack where the offense's win probability (nflverse `wp`, before the snap)
is under 5% or over 95%. Same cut-off as rbsdm.com. Only the offensive box score is split this way (passing, rushing,
receiving, sacks taken, fumbles lost), because that is what the play-by-play credits to one player. Kneel-downs, spikes
and two-point tries are left alone. Snaps are offense + defense snaps from the PFR snap counts (kickers and punters:
special teams snaps).

Output: {season, cut: [low, high], players: {gsis: {week: [snaps, garbageLine]}}}; garbageLine uses the same short keys as
history.json and includes fp (PPR points from those plays)."""
import csv, gzip, json, os, sys, datetime
from collections import defaultdict

D, CUR = sys.argv[1], int(sys.argv[2])
HERE = os.path.dirname(os.path.abspath(__file__))
LOW, HIGH = 0.05, 0.95
num = lambda v: float(v) if v not in ('', None, 'NA') else 0.0
clean = lambda d: {k: (round(v, 1) if v != int(v) else int(v)) for k, v in d.items() if v}

PFR = {}
for r in csv.DictReader(open(os.path.join(D, 'players.csv'), encoding='utf-8')):
    if r['pfr_id'] and r['gsis_id']: PFR[r['pfr_id']] = r['gsis_id']

out = defaultdict(dict)   # gsis -> week -> [snaps, garbage line]
snaps = defaultdict(lambda: defaultdict(float))
for r in csv.DictReader(open(os.path.join(D, f'snap_counts_{CUR}.csv'), encoding='utf-8')):
    gid = PFR.get(r['pfr_player_id'])
    if r['game_type'] != 'REG' or not gid: continue
    n = num(r['offense_snaps']) + num(r['defense_snaps']) or num(r['st_snaps'])
    snaps[gid][int(r['week'])] += n

gb = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # gsis -> week -> key -> value
nplays = ngarb = 0
with gzip.open(os.path.join(D, f'play_by_play_{CUR}.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        if r['season_type'] != 'REG' or r['wp'] in ('', 'NA'): continue
        if num(r['qb_kneel']) or num(r['qb_spike']) or num(r['two_point_attempt']): continue
        sack, pas, rush = num(r['sack']), num(r['pass_attempt']), num(r['rush_attempt'])
        if not (sack or pas or rush): continue
        nplays += 1
        wp = float(r['wp'])
        if LOW <= wp <= HIGH: continue
        ngarb += 1
        wk, yds = int(r['week']), num(r['yards_gained'])
        def add(pid, key, v):
            if pid and v: gb[pid][wk][key] += v
        if sack:
            add(r['passer_player_id'], 'sk', 1)
        elif pas:
            q, rc = r['passer_player_id'], r['receiver_player_id']
            comp = num(r['complete_pass'])
            add(q, 'att', 1); add(q, 'cmp', comp); add(q, 'pyd', yds if comp else 0)
            add(q, 'ptd', num(r['pass_touchdown'])); add(q, 'int', num(r['interception']))
            add(rc, 'tgt', 1); add(rc, 'rec', comp); add(rc, 'reyd', yds if comp else 0); add(rc, 'retd', num(r['pass_touchdown']))
        elif rush:
            c = r['rusher_player_id']
            add(c, 'car', 1); add(c, 'ryd', yds); add(c, 'rtd', num(r['rush_touchdown']))
        if num(r['fumble_lost']): add(r['fumbled_1_player_id'], 'fl', 1)

def fpts(d):
    return (d.get('pyd', 0) * .04 + d.get('ptd', 0) * 4 - d.get('int', 0) * 2 + d.get('ryd', 0) * .1 + d.get('rtd', 0) * 6
            + d.get('reyd', 0) * .1 + d.get('retd', 0) * 6 + d.get('rec', 0) - d.get('fl', 0) * 2)

for gid in set(snaps) | set(gb):
    for wk in set(snaps[gid]) | set(gb[gid]):
        g = dict(gb[gid][wk]) if gid in gb and wk in gb[gid] else {}
        if g: g['fp'] = fpts(g)
        out[gid][str(wk)] = [int(snaps[gid].get(wk, 0)), clean(g)]

json.dump({'asOf': datetime.date.today().isoformat(), 'season': CUR, 'cut': [LOW, HIGH],
           'source': 'nflverse-data releases: pbp, snap_counts, players', 'players': out},
          open(os.path.join(HERE, 'splits.json'), 'w'), separators=(',', ':'))
print('splits:', len(out), 'players,', nplays, 'offensive plays,', ngarb, 'in garbage time (%.1f%%)' % (100 * ngarb / max(1, nplays)))
