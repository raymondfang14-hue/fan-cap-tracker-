"""Backtest the schedule adjustment in data/build_tiers.py (how LAMBDA was chosen).

For each week from 6 to 18 of each season given, fit on the games before that week and predict every offense's EPA per play
in that week's games. Prints the plays-weighted mean squared error for the raw ratings (no opponent adjustment) and the
schedule-adjusted ratings at several LAMBDA values, against a league-average-only guess. Higher % = better prediction.

Usage: python3 -I tools/backtest_tiers.py play_by_play_2024.csv.gz play_by_play_2025.csv.gz
Result on 2024 + 2025 (Nov 2026): best LAMBDA is 250 to 400 for both; adjusted 14.5-14.6%, raw 14.2-14.3%; LAMBDA 10 overfits.
(nflverse files: github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_<year>.csv.gz)
"""
import csv, gzip, sys

FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}


def load(path):
    games = {}
    with gzip.open(path, 'rt') as f:
        for r in csv.DictReader(f):
            if r['season_type'] != 'REG' or r['play_type'] not in ('pass', 'run') or not r['epa'] or not r['posteam'] or not r['defteam']:
                continue
            k = (int(r['week']), FIX.get(r['posteam'], r['posteam']), FIX.get(r['defteam'], r['defteam']))
            g = games.setdefault(k, [0, 0.0]); g[0] += 1; g[1] += float(r['epa'])
    return games


def fit(obs, lam, adjust, iters=1000):
    teams = {t for o, d, _, _ in obs for t in (o, d)}
    mu = sum(n * y for _, _, n, y in obs) / sum(n for _, _, n, _ in obs)
    a, b = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)
    for _ in range(iters if adjust else 1):
        top = {t: [0.0, 0.0] for t in teams}
        for o, d, n, y in obs:
            top[o][0] += n * (y - mu - (b[d] if adjust else 0)); top[o][1] += n
        na = {t: top[t][0] / (top[t][1] + lam) for t in teams}
        top = {t: [0.0, 0.0] for t in teams}
        for o, d, n, y in obs:
            top[d][0] += n * (y - mu - (na[o] if adjust else 0)); top[d][1] += n
        nb = {t: top[t][0] / (top[t][1] + lam) for t in teams}
        moved = max(max(abs(na[t] - a[t]), abs(nb[t] - b[t])) for t in teams)
        a, b = na, nb
        if moved < 1e-9:
            break
    return mu, a, b


LAMS = [10, 50, 100, 150, 250, 400, 700, 1500]
res = {}
for path in sys.argv[1:]:
    G = load(path)
    weeks = sorted({w for w, _, _ in G})
    for w in weeks:
        if w < 6 or w > 18:
            continue
        train = [(o, d, n, s / n) for (ww, o, d), (n, s) in G.items() if ww < w]
        test = [(o, d, n, s / n) for (ww, o, d), (n, s) in G.items() if ww == w]
        if not test:
            continue
        mu = sum(n * y for _, _, n, y in train) / sum(n for _, _, n, _ in train)
        base = sum(n * (y - mu) ** 2 for _, _, n, y in test)
        tn = sum(n for _, _, n, _ in test)
        res.setdefault('league avg only', [0, 0]); res['league avg only'][0] += base; res['league avg only'][1] += tn
        for adj in (False, True):
            for lam in LAMS:
                mu, a, b = fit(train, lam, adj)
                err = sum(n * (y - mu - a.get(o, 0) - b.get(d, 0)) ** 2 for o, d, n, y in test)
                k = f"{'adjusted' if adj else 'raw     '} lambda={lam}"
                res.setdefault(k, [0, 0]); res[k][0] += err; res[k][1] += tn
base = res['league avg only'][0] / res['league avg only'][1]
for k, (e, n) in res.items():
    print(f'{k:<24} weighted MSE {e / n:.5f}   vs league-average-only {100 * (1 - e / n / base):+.2f}%')
