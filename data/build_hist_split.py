"""Split data/history.json (+ data/history_old.json) into small files the page loads on demand, in data/hist/.

Usage: python3 -I data/build_hist_split.py
build_history.py and build_history_old.py run this themselves when they finish, so the usual order is
build_history.py -> build_history_old.py (it reads history.json) and the split files are rewritten each time.

Why: the combined files were 1.2 MB and every phone had to download and parse them before a player's Stats tab
showed anything. The page now loads only what the screen needs.

Files written:
  hist/meta.json   {asOf, current, seasons, thru, oldFirst, oldLast, shards}      tiny, loaded first
  hist/s<YEAR>.json  one per season in history.json: {season, players: [[id, name, pos, line], ...]}
                     season totals only (no game logs). Used by Players > Season stats.
  hist/wk<YEAR>.json  this season's game log for every player, with snaps and the garbage-time part of each week's line (from
                     splits.json, built by build_splits.py): {season, thru, cut, players: [[id, name, pos, [[week, team, line, snaps, garbage], ...]], ...]}.
                     Used by the week range, minimum snaps and garbage-time filters on Players > Season stats.
  hist/p<NN>.json  NN = 00..shards-1. {players: [{id, n, pos, s: {year: line}, w?: [game log]}]}
                     Every season a player has (1999 on, including history_old.json) plus this season's game log.
                     Used by a player card's Stats tab: one shard of about 20 KB.

Players are keyed by nflverse gsis id and never by team, so a player traded mid-season is still one record. His season
line keeps t (the team he played most games for) and tt (every team that season, most games first); each game-log row
carries the team he played that game for. Shard = digits of the gsis id mod SHARDS; the page uses the same rule
(histShard in src.html). Change SHARDS in both places together."""
import json, os, re, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'hist')
SHARDS = 64
dump = lambda path, obj: json.dump(obj, open(path, 'w'), separators=(',', ':'))
shard = lambda pid: int(re.sub(r'\D', '', pid) or 0) % SHARDS

H = json.load(open(os.path.join(HERE, 'history.json')))
oldp = os.path.join(HERE, 'history_old.json')
O = json.load(open(oldp)) if os.path.exists(oldp) else {'players': [], 'seasons': [None, None]}

os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, '*.json')): os.remove(f)

# season files: totals only
for S in H['seasons']:
    rows = [[r['id'], r['n'], r['pos'], r['s'][str(S)]] for r in H['players'] if str(S) in r['s'] and r['s'][str(S)].get('g', 0) > 0]
    dump(os.path.join(OUT, f's{S}.json'), {'season': S, 'players': rows})

# week file: the current game log with snaps and garbage-time lines (splits.json is optional; without it snaps are 0)
sp_path = os.path.join(HERE, 'splits.json')
SP = json.load(open(sp_path)) if os.path.exists(sp_path) else {'players': {}, 'cut': None}
wrows = []
for r in H['players']:
    if not r.get('w'): continue
    sp = SP['players'].get(r['id'], {})
    wrows.append([r['id'], r['n'], r['pos'], [[w[0], w[2], w[3], sp.get(str(w[0]), [0, {}])[0], sp.get(str(w[0]), [0, {}])[1]] for w in r['w']]])
dump(os.path.join(OUT, f"wk{H['current']}.json"), {'season': H['current'], 'thru': H['thru'], 'cut': SP.get('cut'), 'snaps': bool(SP['players']), 'players': wrows})

# player shards: every season plus the current game log
merged = {}
for r in H['players']:
    merged[r['id']] = {'id': r['id'], 'n': r['n'], 'pos': r['pos'], 's': dict(r['s'])}
    if r.get('w'): merged[r['id']]['w'] = r['w']
for x in O['players']:
    m = merged.setdefault(x['id'], {'id': x['id'], 'n': x['n'], 'pos': x['pos'], 's': {}})
    for y, line in x['s'].items(): m['s'].setdefault(y, line)   # history.json wins where both have a season
buckets = [[] for _ in range(SHARDS)]
for pid, m in sorted(merged.items()): buckets[shard(pid)].append(m)
for i, b in enumerate(buckets): dump(os.path.join(OUT, 'p%02d.json' % i), {'players': b})

dump(os.path.join(OUT, 'meta.json'), {'asOf': datetime.date.today().isoformat(), 'current': H['current'], 'seasons': H['seasons'], 'thru': H['thru'],
     'oldFirst': O['seasons'][0], 'oldLast': O['seasons'][1], 'shards': SHARDS})
sizes = [os.path.getsize(os.path.join(OUT, 'p%02d.json' % i)) for i in range(SHARDS)]
print('hist split:', len(merged), 'players,', len(H['seasons']), 'season files, shards', SHARDS, 'max', max(sizes), 'bytes avg', sum(sizes) // SHARDS)
