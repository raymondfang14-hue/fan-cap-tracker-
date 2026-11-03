"""Backtest the schedule-adjusted scoring margin in data/build_standings.py (how SRS_LAMBDA and SRS_HFA were chosen).

For each week from 6 to 18 of each season given, fit on the regular-season games before that week and predict every
game's home margin that week. Prints the mean squared error for the plain average-margin rating (no opponent adjustment) and
for the schedule-adjusted rating (SRS, ridge) at several prior strengths, with and without home field.
Only scores and the neutral-site flag are read from games.csv; the betting columns are never used.

Usage: python3 -I tools/backtest_margin.py <games.csv> 2024 2025
(games.csv: github.com/nflverse/nflverse-data/releases/download/schedules/games.csv)
Result on 2024 + 2025, weeks 6-18 (Nov 2026): best is lambda 4 with 1.5 points of home field, RMSE 12.87 vs 13.15 for the plain average
margin (4% lower mean squared error). Every lambda from 1 to 8 beat the plain average; lambda 16 is too stiff.
"""
import csv, sys

FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}


def srs(games, lam, hfa, plain=False):
    """games: (home, away, home margin, neutral). Returns team ratings in points per game."""
    teams = {t for h, a, _, _ in games for t in (h, a)}
    r = dict.fromkeys(teams, 0.0)
    for _ in range(1 if plain else 500):
        num, den = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)
        for h, a, m, neutral in games:
            m = m - (0 if neutral else hfa)
            num[h] += m + (0 if plain else r[a]); den[h] += 1
            num[a] += -m + (0 if plain else r[h]); den[a] += 1
        new = {t: num[t] / (den[t] + lam) for t in teams}
        moved = max(abs(new[t] - r[t]) for t in teams)
        r = new
        if moved < 1e-9:
            break
    return r


rows = list(csv.DictReader(open(sys.argv[1])))
res = {}
for season in sys.argv[2:]:
    G = [(g['season'], int(g['week']), FIX.get(g['home_team'], g['home_team']), FIX.get(g['away_team'], g['away_team']),
          int(g['home_score']) - int(g['away_score']), g['location'] != 'Home')
         for g in rows if g['season'] == season and g['game_type'] == 'REG' and g['home_score'] != '']
    for w in range(6, 19):
        train = [(h, a, m, n) for _, ww, h, a, m, n in G if ww < w]
        test = [(h, a, m, n) for _, ww, h, a, m, n in G if ww == w]
        if not test:
            continue
        for hfa in (0.0, 1.5, 2.5):
            for name, lam, plain in [('plain average margin', 0, True)] + [(f'adjusted lambda={l}', l, False) for l in (0.5, 1, 2, 4, 8, 16)]:
                r = srs(train, lam, hfa, plain)
                err = sum((m - (0 if nt else hfa) - (r.get(h, 0) - r.get(a, 0))) ** 2 for h, a, m, nt in test)
                k = (hfa, name)
                res.setdefault(k, [0.0, 0]); res[k][0] += err; res[k][1] += len(test)
print('home field (pts)  rating                      MSE      RMSE')
for (hfa, name), (e, n) in sorted(res.items(), key=lambda kv: (kv[0][0], kv[1][0] / kv[1][1])):
    print(f'{hfa:>6}            {name:<24} {e / n:7.2f}  {(e / n) ** .5:6.3f}')
