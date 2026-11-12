"""Write data/usage.json: the Weekly usage risers page (/usage-risers), from nflverse weekly box scores.

For every running back, wide receiver, tight end and fullback with a target or a carry this season, one row per game:
his targets and carries, and his team's targets and carries in that game (summed over every player on the team, quarterbacks
included, from the same file). The page divides the two to get target share and carry share, and compares a week's share with
his share over his earlier games this season (pooled: his targets over his teams' targets in those games).

  players   [gid, name, pos, [[week, team, targets, carries, ppr points], ...]]   (ppr: nflverse fantasy_points_ppr)
  teams     {team: {week: [team targets, team carries]}}
  thru      the last week in the file (up to the week given on the command line)
  done      the last week in which every game in data/schedule.json is final (the page opens on it)
  open      teams whose game in week `thru` is not final yet (the page says so when it shows that week)

Only games with a box-score row count, so a game in which a player recorded no stat at all is not in his "before" average.
Data: nflverse stats_player_week_<season>.csv (github.com/nflverse/nflverse-data releases, CC BY 4.0). No betting data,
no Pro Football Reference or Next Gen Stats data.
Usage: python3 -I data/build_usage.py <folder with stats_player_week_<season>.csv> <season> [last week]
"""
import csv, json, sys, datetime, os

FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
POS = {'RB', 'WR', 'TE', 'FB'}
folder, season = sys.argv[1], int(sys.argv[2])
last = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 99
num = lambda v: float(v) if v not in ('', 'NA', None) else 0.0

team = {}      # (team, week) -> [targets, carries]
rows = {}      # gid -> {'n','pos','g': {week: [team, tgt, car, ppr]}}
check = []     # (gid, week, nflverse target_share) for the self-check below
with open(os.path.join(folder, f'stats_player_week_{season}.csv'), newline='') as f:
    for r in csv.DictReader(f):
        if r['season_type'] != 'REG' or int(r['season']) != season:
            continue
        w = int(r['week'])
        if w > last:
            continue
        t = FIX.get(r['team'], r['team'])
        tg, ca = num(r['targets']), num(r['carries'])
        tt = team.setdefault((t, w), [0, 0])
        tt[0] += tg; tt[1] += ca
        if r['position'] not in POS or not r['player_id']:
            continue
        p = rows.setdefault(r['player_id'], {'n': r['player_display_name'] or r['player_name'], 'pos': r['position'], 'g': {}})
        p['g'][w] = [t, int(tg), int(ca), round(num(r['fantasy_points_ppr']), 1)]
        if r['target_share'] not in ('', 'NA'):
            check.append((r['player_id'], w, t, float(r['target_share'])))

# our target share must match nflverse's own column wherever it gives one
bad = [(g, w, s) for g, w, t, s in check if team[(t, w)][0] and abs(rows[g]['g'][w][1] / team[(t, w)][0] - s) > .011]
assert len(bad) <= max(3, len(check) // 200), f'target share disagrees with nflverse on {len(bad)} of {len(check)} rows, e.g. {bad[:3]}'

players = [[gid, p['n'], p['pos'], [[w, *p['g'][w]] for w in sorted(p['g'])]]
           for gid, p in sorted(rows.items(), key=lambda kv: kv[1]['n'])
           if any(g[1] or g[2] for g in p['g'].values())]
teams = {}
for (t, w), (a, b) in sorted(team.items()):
    teams.setdefault(t, {})[str(w)] = [int(a), int(b)]
weeks = sorted({w for _, w in team})
assert weeks, 'no regular-season weeks in the file'
thru = weeks[-1]

# which weeks are complete, from the schedule (a week still being played shows as "so far")
sched = json.load(open('data/schedule.json'))
final = {}
open_teams = []
for g in sched['games']:
    ok = g[6] is not None and g[7] is not None
    final.setdefault(g[1], []).append(ok)
    if g[1] == thru and not ok:
        open_teams += [g[4], g[5]]
done = max([w for w in weeks if all(final.get(w, [False]))] or [thru])

out = {'asOf': datetime.date.today().isoformat(), 'season': season, 'thru': thru, 'done': done, 'open': sorted(open_teams),
       'source': f'PlainStats, from nflverse weekly box scores (stats_player_week {season}, CC BY 4.0), regular season through Week {thru}',
       'teams': teams, 'players': players}
json.dump(out, open('data/usage.json', 'w'), separators=(',', ':'))
print(f'usage: weeks {weeks[0]}-{thru} (all final through {done}), {len(players)} players, {len(teams)} teams,'
      f' target share checked on {len(check)} rows ({len(bad)} off)')
