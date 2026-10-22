"""Write data/market.json: the inputs behind the Free agency page's "Est. next deal" column and the Best & worst tab.
The price ladder (APY at selected ranks of each position) is computed from PlainStats' own contract table, data/nfl.json,
so no outside ranking is copied. Age curves: RB, WR and TE shapes follow 4for4's published production-by-age study; the
other positions are PlainStats judgment. Cap growth: the 2026 cap is $301.2M (NFL.com); later years use the site's
projection in data/freeagency.json.
Slots = how many starter-level jobs the league has at the position; a player's play-rating percentile among
qualified players is mapped onto ranks 1..slots of the ladder.
Usage: python3 data/build_market.py"""
import json

# The ladder is built from PlainStats' own contract table (data/nfl.json): every player's average per year (APY),
# ranked within his position group. Run build_contracts.py first.
GROUP = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE', 'LT': 'LT', 'RT': 'RT', 'LG': 'G', 'RG': 'G', 'C': 'C',
         'IDL': 'DT', 'DT': 'DT', 'EDGE': 'EDGE', 'LB': 'LB', 'CB': 'CB', 'S': 'S', 'K': 'K', 'P': 'P'}
RANKS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40, 45, 50, 60, 70, 80]
_nfl = json.load(open('data/nfl.json'))
_u = sum(1 for r in _nfl['players'] if len(r) > 15 and r[15] == 'u')
if _u > 0.2 * len(_nfl['players']):
    print(f'skipped: {_u} of {len(_nfl["players"])} contracts are still unverified, so a price ladder built now would be wrong. data/market.json is unchanged.')
    raise SystemExit(0)
_apy = {}
for r in _nfl['players']:
    g = GROUP.get(r[2])
    if g and r[5]: _apy.setdefault(g, []).append(r[5] / 1e6)
LADDER = {}
for g, v in _apy.items():
    v.sort(reverse=True)
    LADDER[g] = [[k, round(v[k - 1], 2)] for k in RANKS if k <= len(v)]
SLOTS = {'QB': 32, 'RB': 32, 'WR': 64, 'TE': 32, 'LT': 32, 'RT': 32, 'G': 64, 'C': 32, 'DT': 64, 'EDGE': 64, 'LB': 40, 'CB': 64, 'S': 64, 'K': 32, 'P': 32}
# value kept at each age relative to prime: [first age, factor] steps; the factor holds until the next step
AGE = {
 'QB':  [[0,1],[35,.93],[36,.86],[37,.78],[38,.7]],
 'RB':  [[0,1],[29,.95],[30,.88],[31,.78],[32,.68],[33,.55],[34,.45]],
 'WR':  [[0,1],[29,.95],[30,.9],[31,.85],[32,.78],[33,.7],[34,.6]],
 'TE':  [[0,1],[31,.92],[32,.85],[33,.78],[34,.7]],
 'OL':  [[0,1],[33,.92],[34,.85],[35,.75]],
 'EDGE':[[0,1],[32,.93],[33,.85],[34,.75]],
 'DT':  [[0,1],[32,.93],[33,.85],[34,.75]],
 'LB':  [[0,1],[30,.93],[31,.86],[32,.78],[33,.68]],
 'CB':  [[0,1],[29,.94],[30,.88],[31,.8],[32,.72],[33,.62]],
 'S':   [[0,1],[30,.94],[31,.88],[32,.8],[33,.7]],
 'K':   [[0,1],[37,.9]], 'P': [[0,1],[37,.9]],
}
SRC = {
 'PlainStats contract table (data/nfl.json): APY by position, ranked': 'data/nfl.json',
 '4for4, production curves by age (RB, WR and TE shapes)': 'https://www.4for4.com/2025/preseason/production-curves-positional-breakouts-prime-years-and-falloffs-age',
 'NFL.com: 2026 salary cap set at $301.2 million': 'https://www.nfl.com/_amp/nfl-announces-2026-salary-cap-set-at-301-2-million-per-team',
}
import datetime
out = {'asOf': datetime.date.today().isoformat(), 'unit': 'USD millions', 'cap2026': 301.2, 'sources': SRC, 'slots': SLOTS, 'ladder': LADDER, 'age': AGE,
       'ageSourced': ['RB', 'WR', 'TE'], 'shrinkPerYear': 0.08, 'shrinkFloor': 0.6}
for k, v in LADDER.items():
    assert [r for r, _ in v] == sorted(r for r, _ in v), k
json.dump(out, open('data/market.json', 'w'), separators=(',', ':'))
print('positions', len(LADDER))
