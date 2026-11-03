"""Print the facts sheet for the weekly tiers post: every number a caption or "why" line may quote.

Usage (repo root):  python3 -I .claude/skills/weekly-tiers-post/scripts/facts.py

Reads data/tiers.json, data/projections.json (records, streaks) and data/schedule.json (this week's scores).
Prints, per team in rank order: tier, rank, rank change, record, streak, net/off/def EPA per play, the league rank of
each split (1 = best; defense ranks use EPA allowed, lower is better), and the team's result in the latest week.
Then the hook candidates the data supports (best teams by record that sit outside the top 5, record-vs-rank gaps).
"""
import json

T = json.load(open('data/tiers.json'))
P = json.load(open('data/projections.json'))['teams']
S = json.load(open('data/schedule.json'))['games']
thru = T['thru']
teams = T['teams']


def ranks(key, best_high):
    order = sorted(teams, key=lambda k: teams[k][key], reverse=best_high)
    return {k: i + 1 for i, k in enumerate(order)}


R = {m: ranks(m, m in ('off', 'offPass', 'offRush', 'offSr')) for m in
     ('off', 'def', 'offPass', 'offRush', 'defPass', 'defRush', 'offSr', 'defSr')}
last = {}
for g in S:
    if g[1] == thru and g[6] is not None and g[7] is not None:
        a, h, sa, sh = g[4], g[5], g[6], g[7]
        ot = ' OT' if len(g) > 8 and g[8] else ''
        last[a] = f"{'W' if sa > sh else 'L'} {sa}-{sh} at {h}{ot}"
        last[h] = f"{'W' if sh > sa else 'L'} {sh}-{sa} vs {a}{ot}"
print(f"PlainStats tiers facts, data through Week {thru} (asOf {T['asOf']}). Defense numbers are EPA ALLOWED (lower = better).")
print('Quote only these numbers. Rank change = places gained (+) or lost (-) in net EPA rank vs last week; last week\'s TIER is not stored.\n')
print('rk tier mv   team rec    strk  net    off    def   | rank: off def oPass oRun dPass dRun oSR dSR | week result')
for k in sorted(teams, key=lambda k: teams[k]['rank']):
    t, p = teams[k], P[k]
    print(f"{t['rank']:>2} T{t['tier']} {t['move']:+d}  {k:<4} {p['w']}-{p['l']}{('-' + str(p['t'])) if p['t'] else ''}  {p['strk']:<4} {t['net']:+.3f} {t['off']:+.3f} {t['def']:+.3f} | "
          f"{R['off'][k]:>2} {R['def'][k]:>2}  {R['offPass'][k]:>2}  {R['offRush'][k]:>2}  {R['defPass'][k]:>2}  {R['defRush'][k]:>2}  {R['offSr'][k]:>2} {R['defSr'][k]:>2} | {last.get(k, 'no game / bye')}")
print('\nBiggest risers:', ', '.join(f"{k} {teams[k]['move']:+d}" for k in sorted(teams, key=lambda k: -teams[k]['move'])[:6]))
print('Biggest fallers:', ', '.join(f"{k} {teams[k]['move']:+d}" for k in sorted(teams, key=lambda k: teams[k]['move'])[:6]))
print('\nHook candidates (record vs net-EPA rank):')
for k in sorted(teams, key=lambda k: teams[k]['rank']):
    p, t = P[k], teams[k]
    games = p['w'] + p['l'] + p['t']
    pct = (p['w'] + p['t'] / 2) / games if games else 0
    if pct >= .7 and t['rank'] > 5:
        print(f"  {k}: {p['w']}-{p['l']} but rank {t['rank']} (tier {t['tier']})")
    if pct <= .35 and t['rank'] <= 12:
        print(f"  {k}: {p['w']}-{p['l']} but rank {t['rank']} (tier {t['tier']})")
