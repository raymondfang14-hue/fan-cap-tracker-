"""Write data/pff_ol.json: individual offensive linemen figures that PFF states in its free, public in-season pages.
Source for this run: PFF, "2026 NFL offensive line rankings" (Oct 21, 2026, after Week 6).
Only figures the article attaches to a named lineman are kept. Grouped-only claims ("three starters ...") and
figures shared by two players are left out. Scopes: wk6 = stated as Week 6; game = the lineman's latest game as
recapped in the Week 6 rankings; season = season to date.
Usage: python3 data/build_pff_ol.py   (replace ROWS when refreshing)"""
import json

ASOF, WEEK = '2026-10-21', 6
SRC = 'PFF public in-season offensive line rankings, after Week 6'
G, W, S = 'game', 'wk6', 'season'
ROWS = [
    ('DET', 'Penei Sewell', 'recent', ['overall grade above 90.0 in two of his last three games']),
    ('DET', 'Blake Miller', S, ['9 pressures on 166 pass-blocking snaps', '0 sacks allowed in his first four NFL games']),
    ('SF', 'Trent Williams', W, ['0 pressures allowed']),
    ('SF', 'Colton McKivitz', W, ['0 pressures allowed']),
    ('IND', 'Bernhard Raimann', G, ['pass-block and run-block grades both above 75.0']),
    ('IND', 'Quenton Nelson', G, ['pass-block and run-block grades both above 75.0']),
    ('IND', 'Tanor Bortolini', S, ['grade under 50.0 in 3 of 6 games']),
    ('BUF', 'Alec Anderson', W, ['pass-block grade 74.5']),
    ("BUF", "O'Cyrus Torrence", W, ['pass-block grade 74.5']),
    ('BUF', 'Dion Dawkins', G, ['0 pressures on 38 pass-blocking snaps']),
    ('DEN', 'Garett Bolles', G, ['0 pressures on 33 pass plays', 'pass-block grade above 85.0']),
    ('DEN', 'Quinn Meinerz', G, ['0 pressures on 33 pass plays', 'pass-block grade above 85.0']),
    ('DEN', 'Ben Powers', G, ['pass-block grade of 55.0 or lower']),
    ('DEN', 'Luke Wattenberg', G, ['pass-block grade of 55.0 or lower']),
    ('DEN', 'Mike McGlinchey', G, ['pass-block grade of 55.0 or lower']),
    ('CHI', 'Theo Benedet', G, ['0 pressures allowed']),
    ('CHI', 'Darnell Wright', G, ['0 pressures allowed']),
    ('TB', 'Ben Bredeson', G, ['pass-block grade under 40.0, his second such game this season']),
    ('TB', 'Tristan Wirfs', G, ['5 pressures on 53 pass-blocking snaps, a career high for one game']),
    ('SEA', 'Abraham Lucas', G, ['7 pressures and 2 sacks allowed']),
    ('ATL', 'Jake Matthews', G, ['1 pressure on 44 pass-blocking snaps']),
    ('ATL', 'Jawaan Taylor', G, ['6 pressures allowed']),
    ('CIN', 'Ted Karras', G, ['pass-block grade 59.2']),
    ('CIN', 'Dalton Risner', S, ['run-block grade 80.7, third among right guards']),
    ('LAR', 'David Quessenberry', W, ['pass-block grade 84.8', 'run-block grade 78.7']),
    ('LAR', 'Kevin Dotson', S, ['16 pressures on 286 pass-blocking snaps']),
    ('DAL', 'Tyler Guyton', G, ['7 pressures allowed']),
    ('DAL', 'Terence Steele', G, ['6 pressures allowed']),
    ('MIN', 'Ryan Van Demark', G, ['grade under 60.0']),
    ('MIN', 'Joe Huber', G, ['grade under 60.0']),
    ('LV', 'Tyler Linderbaum', G, ['pass-block grade 29.8', '2 pressures, both QB hits']),
    ('NYG', 'Francis Mauigoa', W, ['pass-block grade 33.0']),
    ('PHI', 'Jake Majors', G, ['4 pressures allowed, second straight week']),
    ('PHI', 'Willie Lampkin', G, ['0 pressures allowed']),
    ('KC', 'Kingsley Suamataia', G, ['run-block grade 90.3', '0 pressures on 27 pass-blocking snaps']),
    ('KC', 'Trey Smith', G, ['run-block grade 91.0', '0 pressures on 36 pass-blocking snaps']),
    ('WAS', 'Josh Conerly Jr.', W, ['6 pressures on 51 pass-blocking snaps, most on the team']),
    ('NO', 'Asim Richards', S, ['grade under 60.0 in 3 of 4 games']),
    ('CLE', 'Zion Johnson', S, ['69.7 overall grade through 6 games', '6 pressures on 238 pass-blocking snaps']),
    ('CLE', 'Spencer Fano', G, ['2 pressures on 39 pass-blocking snaps']),
    ('TEN', 'Atonio Mafi', G, ['2 pressures on 24 pass-blocking snaps', 'pass-block grade under 70.0']),
    ('CAR', 'Taylor Moton', G, ['pass-block grade 63.5', '2 pressures on 46 pass-blocking snaps']),
    ('CAR', 'Robert Hunt', G, ['0 pressures allowed']),
    ('NE', 'Caleb Lomu', G, ['0 pressures on 30 pass-blocking snaps in relief']),
    ('JAX', 'Emmanuel Pregnon', S, ['no game yet with a grade of 60.0 or better']),
    ('JAX', 'Robert Hainsey', S, ['season-high grade of 61.7 in his latest game']),
    ('HOU', 'Trent Brown', G, ['grade above 70.0, the only Texans starter to do so']),
    ('HOU', 'Keylan Rutledge', G, ['2 pressures allowed']),
    ('HOU', 'Evan Brown', G, ['0 pressures allowed']),
    ('HOU', 'Ed Ingram', G, ['0 pressures allowed']),
    ('ARI', 'Jayden Williams', G, ['2 pressures on 36 pass-blocking snaps', '0 QB hits']),
    ('LAC', 'Travis Burke', G, ['3 pressures on 49 pass-blocking snaps', 'pass-block grade above 70.0']),
    ('LAC', 'Jake Slaughter', G, ['pass-block grade above 70.0']),
    ('LAC', 'Alex Harkey', G, ['pass-block grade 36.2']),
]
LABEL = {W: 'Week 6', G: 'Latest game', S: 'Season', 'recent': 'Last three games'}
assert len({(t, n) for t, n, _, _ in ROWS}) == len(ROWS)
out = {'asOf': ASOF, 'week': WEEK, 'source': SRC, 'labels': LABEL,
       'rows': [{'t': t, 'n': n, 'sc': sc, 'bits': b} for t, n, sc, b in ROWS]}
json.dump(out, open('data/pff_ol.json', 'w'), separators=(',', ':'))
print('rows', len(out['rows']))
