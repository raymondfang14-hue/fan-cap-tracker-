"""Print the facts sheet for the weekly tiers post: every number a caption or "why" line may quote.

Usage (repo root):  python3 -I .claude/skills/weekly-tiers-post/scripts/facts.py [path to tiers.json]

Reads data/tiers.json, data/projections.json (records, streaks) and data/schedule.json (this week's scores).
Ranks, tiers and the rank change in the file are SCHEDULE-ADJUSTED (data/build_tiers.py: net EPA per play compared with what
an average unit would have done against the same opponents). Per team in rank order the sheet prints: tier, rank, rank change,
record, streak, adjusted net / offense / defense, raw net, the raw rank (before adjustment), strength of schedule (average
adjusted net of the opponents faced, rank 1 = toughest so far), the league rank of each split (1 = best; defense ranks use EPA
allowed, lower is better) and the team's result in the latest week. Then risers, fallers, schedule extremes and the hook
candidates the data supports.

If the file has no schedule adjustment (built before Nov 2026) the sheet says so and prints the raw numbers; do not write
schedule claims in that case.
"""
import json
import sys

T = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'data/tiers.json'))
P = json.load(open('data/projections.json'))['teams']
S = json.load(open('data/schedule.json'))['games']
thru = T['thru']
teams = T['teams']
ADJ = bool(T.get('adjusted'))
NET, OFF, DEF = ('aNet', 'aOff', 'aDef') if ADJ else ('net', 'off', 'def')


def ranks(key, best_high):
    order = sorted(teams, key=lambda k: teams[k][key], reverse=best_high)
    return {k: i + 1 for i, k in enumerate(order)}


R = {'off': ranks(OFF, True), 'def': ranks(DEF, False)}
R.update({m: ranks(m, m in ('offPass', 'offRush', 'offSr')) for m in ('offPass', 'offRush', 'defPass', 'defRush', 'offSr', 'defSr')})
last = {}
for g in S:
    if g[1] == thru and g[6] is not None and g[7] is not None:
        a, h, sa, sh = g[4], g[5], g[6], g[7]
        ot = ' OT' if len(g) > 8 and g[8] else ''
        last[a] = f"{'W' if sa > sh else 'L'} {sa}-{sh} at {h}{ot}"
        last[h] = f"{'W' if sh > sa else 'L'} {sh}-{sa} vs {a}{ot}"


def rec(k):
    p = P[k]
    return f"{p['w']}-{p['l']}" + (f"-{p['t']}" if p['t'] else '')


print(f"PlainStats tiers facts, data through Week {thru} (asOf {T['asOf']}).")
if ADJ:
    print(f"SCHEDULE-ADJUSTED model (ridge, lambda {T['lambda']}): rank, tier, move, net/off/def below are adjusted for the opponents faced.")
    print('Raw numbers (before adjustment) are shown as rawNet / rawRank. Pass, run and hit-rate split ranks are RAW (not adjusted).')
else:
    print('WARNING: this tiers.json has NO schedule adjustment (raw numbers only). Do not write strength-of-schedule claims. Rebuild with data/build_tiers.py.')
print("Defense numbers are EPA ALLOWED (lower = better). Rank change = places gained (+) or lost (-) vs last week; last week's TIER is not stored.\n")
hdr = 'rk tier mv   team rec     strk  ' + ('adjNet adjOff adjDef rawNet rawRk sos(rk) ' if ADJ else 'net    off    def   ')
print(hdr + '| rank: off def oPass oRun dPass dRun oSR dSR | week result')
for k in sorted(teams, key=lambda k: teams[k]['rank']):
    t, p = teams[k], P[k]
    nums = (f"{t['aNet']:+.3f} {t['aOff']:+.3f} {t['aDef']:+.3f} {t['net']:+.3f} {t['rawRank']:>4} {t['sos']:+.3f}({t['sosRank']:>2}) " if ADJ
            else f"{t['net']:+.3f} {t['off']:+.3f} {t['def']:+.3f} ")
    print(f"{t['rank']:>2} T{t['tier']} {t['move']:+d}  {k:<4} {rec(k):<7} {p['strk']:<4}  {nums}| "
          f"{R['off'][k]:>2} {R['def'][k]:>2}  {R['offPass'][k]:>2}  {R['offRush'][k]:>2}  {R['defPass'][k]:>2}  {R['defRush'][k]:>2}  {R['offSr'][k]:>2} {R['defSr'][k]:>2} | {last.get(k, 'no game / bye')}")
print('\nBiggest risers:', ', '.join(f"{k} {teams[k]['move']:+d}" for k in sorted(teams, key=lambda k: -teams[k]['move'])[:6]))
print('Biggest fallers:', ', '.join(f"{k} {teams[k]['move']:+d}" for k in sorted(teams, key=lambda k: teams[k]['move'])[:6]))
if ADJ:
    by_sos = sorted(teams, key=lambda k: teams[k]['sosRank'])
    print('Toughest schedules so far:', ', '.join(f"{k} (#{teams[k]['sosRank']}, {teams[k]['sos']:+.3f})" for k in by_sos[:4]))
    print('Easiest schedules so far:', ', '.join(f"{k} (#{teams[k]['sosRank']}, {teams[k]['sos']:+.3f})" for k in by_sos[-4:]))
    print('Schedule moved them (raw rank -> adjusted rank, 3 or more places):')
    for k in sorted(teams, key=lambda k: teams[k]['rawRank'] - teams[k]['rank'], reverse=True):
        d = teams[k]['rawRank'] - teams[k]['rank']
        if abs(d) >= 3:
            print(f"  {k}: #{teams[k]['rawRank']} raw -> #{teams[k]['rank']} adjusted ({'up' if d > 0 else 'down'} {abs(d)}), schedule #{teams[k]['sosRank']} of 32 (1 = toughest)")
print('\nHook candidates (record vs rank):')
for k in sorted(teams, key=lambda k: teams[k]['rank']):
    p, t = P[k], teams[k]
    games = p['w'] + p['l'] + p['t']
    pct = (p['w'] + p['t'] / 2) / games if games else 0
    if pct >= .7 and t['rank'] > 5:
        print(f"  {k}: {rec(k)} but rank {t['rank']} (tier {t['tier']})")
    if pct <= .35 and t['rank'] <= 12:
        print(f"  {k}: {rec(k)} but rank {t['rank']} (tier {t['tier']})")
if ADJ:
    print('Schedule hooks: a top-5 team with an easy schedule (sos rank 25+), or a good team ranked lower than its record because of a hard one (sos rank 8 or better).')
    for k in sorted(teams, key=lambda k: teams[k]['rank']):
        t = teams[k]
        if t['rank'] <= 5 and t['sosRank'] >= 25:
            print(f"  {k}: rank {t['rank']} with the #{t['sosRank']} schedule of 32 (1 = toughest)")
        if t['sosRank'] <= 8 and t['rank'] <= 12 and t['rank'] < t['rawRank']:
            print(f"  {k}: rank {t['rank']} (raw #{t['rawRank']}), schedule #{t['sosRank']} of 32")
