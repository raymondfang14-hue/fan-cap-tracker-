"""Write data/olwin.json: ESPN team block win rates (PBWR = pass block win rate, RBWR = run block win rate).
ESPN publishes these from NFL Next Gen Stats tracking data. Plain Cap reads them as plain text from the free
NFL Lines table ("ESPN Block Win % Through Week N") and credits ESPN.
Usage: python3 data/build_olwin.py   (edit THRU, ASOF and ROWS below when refreshing)
Each row: team code, PBWR %, PBWR rank, RBWR %, RBWR rank."""
import json

ASOF, THRU, SRC = '2026-10-15', 5, 'ESPN Analytics (NFL Next Gen Stats tracking data), as tabulated by NFL Lines, through Week 5'
ROWS = [
    ('ARI', 30, 31, 72, 21), ('ATL', 53, 9, 73, 17), ('BAL', 48, 21, 74, 8), ('BUF', 59, 2, 77, 2),
    ('CAR', 44, 27, 71, 27), ('CHI', 56, 4, 74, 11), ('CIN', 46, 24, 77, 1), ('CLE', 47, 22, 71, 26),
    ('DAL', 50, 17, 69, 31), ('DEN', 47, 23, 73, 19), ('DET', 58, 3, 72, 22), ('GB', 26, 32, 73, 20),
    ('HOU', 53, 11, 71, 24), ('IND', 49, 19, 73, 18), ('JAX', 42, 28, 74, 14), ('KC', 52, 13, 76, 3),
    ('LV', 62, 1, 74, 13), ('LAC', 39, 30, 75, 6), ('LAR', 54, 6, 75, 7), ('MIA', 51, 15, 71, 28),
    ('MIN', 52, 14, 75, 5), ('NE', 52, 12, 74, 12), ('NO', 45, 26, 73, 16), ('NYG', 50, 16, 74, 15),
    ('NYJ', 54, 7, 70, 30), ('PHI', 48, 20, 71, 23), ('PIT', 53, 8, 74, 9), ('SF', 56, 5, 76, 4),
    ('SEA', 46, 25, 71, 25), ('TB', 50, 17, 74, 10), ('TEN', 42, 29, 70, 29), ('WAS', 53, 10, 67, 32),
]
assert len(ROWS) == 32 and len({r[0] for r in ROWS}) == 32
out = {'asOf': ASOF, 'thru': THRU, 'source': SRC,
       'teams': {t: {'pbwr': pb / 100, 'pbwrRk': pr, 'rbwr': rb / 100, 'rbwrRk': rr} for t, pb, pr, rb, rr in ROWS}}
json.dump(out, open('data/olwin.json', 'w'), separators=(',', ':'))
print('teams', len(out['teams']))
