"""Builds data/draft.json for the Plain Cap Draft page (#draft).

Inputs, all edited by hand or by the daily refresh task:
  P        one row per prospect (below). w = WalterFootball big-board rank, b = NFL Draft Buzz
           big-board rank, a = NFL Draft Buzz "AVG RANK" across outlets. Use None when he is not on
           that board. tid/pid are his cfbstats.com team and player ids (player page
           https://cfbstats.com/2026/player/<tid>/<pid>/index.html); pid is None for offensive
           linemen and anyone cfbstats lists without a player page.
  data/draft_stats.txt
           one line per prospect: "<key> {json}" with his 2026 season totals from his cfbstats page
           (g games, pc/pa/py/ptd/pint passing, ra/ry/rtd rushing, rec/rey/retd receiving,
           tk tackles, tfl, sk sacks, int, pbu, qbh QB hurries, ff forced fumbles). Omit zero values.
  data/draft_espn.txt
           one line per prospect: "<key> <ESPN athlete id>" for his headshot
           (https://a.espncdn.com/i/headshots/college-football/players/full/<id>.png). Find the id with
           https://site.web.api.espn.com/apis/common/v3/search?query=<First%20Last>&limit=10&mode=prefix&type=player
           and take the NCAA Football result on his school. SCHOOLS rows end with the school's ESPN team id
           (logo https://a.espncdn.com/i/teamlogos/ncaa/500/<id>.png; same search with type=team).
  ASOF, STATS_THRU, BOARD_DATES
           dates (YYYY-MM-DD): today, the "through" date printed on cfbstats pages, and the
           update date of each board.

Rules: never invent a rank or a stat. A prospect stays on the list while at least one board ranks
him. School codes must be keys of SCHOOLS (add the school with its colors if a new one appears).
Group (grp) is one of QB RB WR TE OT IOL EDGE DT LB CB S. Run: python3 -I data/build_draft.py
The page computes the consensus order, grades, roles, traits, the mock and rookie pay itself.
Boards: WalterFootball 2027 big board and NFL Draft Buzz big board. College stats: cfbstats.com.
Rookie scale: 2026 first-round slot values (Pro Football Network / Spotrac)."""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'draft.json'
ASOF = '2026-10-21'
STATS_THRU = '2026-10-17'
BOARD_DATES = {'w': '2026-10-14', 'b': '2026-10-21'}

# key: (name, group, school code, class, height, weight, walter rank, buzz rank, buzz avg, cfbstats team id, cfbstats player id)
P = [
 ('jsmith', 'Jeremiah Smith', 'WR', 'OSU', 'JR', '6-4', 222, 1, 1, 1.1, 518, 50312218),
 ('lmoore', 'Leonard Moore', 'CB', 'ND', 'JR', '6-2', 197, 2, 18, 4.2, 513, 50309847),
 ('simmons', 'Colin Simmons', 'EDGE', 'TEX', 'JR', '6-3', 246, 3, 2, 4.8, 703, 50312306),
 ('ccoleman', 'Cam Coleman', 'WR', 'TEX', 'JR', '6-3', 204, 4, 6, 7.1, 703, 50310429),
 ('becker', 'Charlie Becker', 'WR', 'IND', 'JR', '6-4', 208, 5, 35, 18.9, 306, 50304327),
 ('carr', 'CJ Carr', 'QB', 'ND', 'JR', '6-2', 215, 6, 24, 27.1, 513, 50310480),
 ('goosby', 'Trevor Goosby', 'OT', 'TEX', 'SR', '6-7', 325, 7, 11, 12.1, 703, None),
 ('baugh', 'Jadan Baugh', 'RB', 'UF', 'JR', '6-1', 225, 8, 36, 22.9, 235, 50309802),
 ('stewart', 'Dylan Stewart', 'EDGE', 'SC', 'JR', '6-5', 250, 9, 5, 4.8, 648, 50310495),
 ('manning', 'Arch Manning', 'QB', 'TEX', 'SR', '6-4', 222, 10, 19, 10.5, 703, 2001506),
 ('erobinson', 'Ellis Robinson IV', 'CB', 'UGA', 'JR', '6-0', 180, 11, 12, 19.9, 257, 50310449),
 ('duff', 'KJ Duff', 'WR', 'RUT', 'JR', '6-6', 225, 12, 38, 36.4, 587, 50312274),
 ('tgreen', "Trey'Dez Green", 'TE', 'LSU', 'JR', '6-7', 242, 13, 22, 21.6, 365, 50312143),
 ('mensah', 'Darian Mensah', 'QB', 'MIA', 'JR', '6-3', 205, 14, 3, 19.8, 415, 2000040),
 ('dmoore', 'Dante Moore', 'QB', 'ORE', 'SR', '6-3', 220, 15, 7, 9.0, 529, 2000295),
 ('tjohnson', 'Tae Johnson', 'S', 'ND', 'JR', '6-2', 200, 16, 33, 24.9, 513, 50310479),
 ('gilliam', 'Xavier Gilliam', 'DT', 'TENN', 'JR', '6-2', 305, 17, None, None, 694, 50303952),
 ('echoles', 'Will Echoles', 'DT', 'MISS', 'JR', '6-3', 315, 18, 13, 13.4, 433, 50311247),
 ('lacy', 'Kewan Lacy', 'RB', 'MISS', 'JR', '5-11', 205, 19, 46, 31.8, 433, 50312188),
 ('pierre', 'Yhonzae Pierre', 'EDGE', 'BAMA', 'SR', '6-4', 251, 20, 15, 19.7, 8, 2000235),
 ('kjones', 'Kelley Jones', 'CB', 'MSST', 'SR', '6-4', 205, 21, 49, 36.7, 430, 2000009),
 ('rcw', 'Ryan Coleman-Williams', 'WR', 'BAMA', 'JR', '6-0', 184, 22, None, None, 8, 50312040),
 ('bolden', 'KJ Bolden', 'S', 'UGA', 'JR', '6-0', 195, 23, 16, 20.5, 257, 50311183),
 ('hampton', 'Ashton Hampton', 'CB', 'CLEM', 'JR', '6-2', 205, 24, None, None, 147, 50312065),
 ('heldt', 'Will Heldt', 'EDGE', 'CLEM', 'SR', '6-6', 260, 25, 50, 38.1, 147, 2000036),
 ('berry', 'Zeke Berry', 'CB', 'MICH', 'SR', '5-11', 188, 26, None, None, 418, 1180019),
 ('balexander', 'Bear Alexander', 'DT', 'ORE', 'SR', '6-3', 316, 27, None, None, 529, 1174428),
 ('mcdonald', 'Jelani McDonald', 'S', 'TEX', 'SR', '6-2', 201, 28, 48, 61.7, 703, 2002969),
 ('gjohnson', 'Greg Johnson', 'IOL', 'MINN', 'SR', '6-6', 325, 29, None, None, 428, None),
 ('rharris', 'Reed Harris', 'WR', 'ASU', 'SR', '6-5', 220, 30, None, None, 28, 2000413),
 ('kjackson', 'Kenyatta Jackson Jr.', 'EDGE', 'OSU', 'SR', '6-6', 263, 31, None, None, 518, 1177851),
 ('jamjohnson', 'Jamari Johnson', 'TE', 'ORE', 'SR', '6-5', 255, 32, 44, 23.0, 529, 2002973),
 ('marsh', 'Nick Marsh', 'WR', 'IND', 'JR', '6-3', 210, 33, 37, 35.5, 306, 50312177),
 ('chambliss', 'Trinidad Chambliss', 'QB', 'MISS', 'SR', '6-0', 210, 34, 45, 28.8, 433, 1136057),
 ('sbrown', 'Sammy Brown', 'LB', 'CLEM', 'JR', '6-2', 235, 35, 31, 36.3, 147, 50304691),
 ('seaton', 'Jordan Seaton', 'OT', 'LSU', 'JR', '6-5', 311, 36, 27, 12.3, 365, None),
 ('traore', 'Boubacar Traore', 'EDGE', 'ND', 'SR', '6-5', 253, 37, None, None, 513, 2001485),
 ('mestemaker', 'Drew Mestemaker', 'QB', 'OKST', 'SO', '6-3', 215, 38, 4, 27.4, 521, 50259623),
 ('reynolds', 'Luke Reynolds', 'TE', 'VT', 'JR', '6-4', 250, 39, None, None, 742, 50310486),
 ('benefield', 'Ty Benefield', 'S', 'LSU', 'SR', '6-3', 216, 40, None, None, 365, 2000753),
 ('drobinson', 'Duce Robinson', 'WR', 'FSU', 'SR', '6-6', 230, 41, 41, 62.8, 234, 1208932),
 ('leavitt', 'Sam Leavitt', 'QB', 'LSU', 'JR', '6-2', 207, 42, None, None, 365, 2000773),
 ('dwilson', 'Damon Wilson II', 'EDGE', 'MIA', 'SR', '6-4', 250, 43, 34, 52.5, 415, 2002195),
 ('swain', 'Vicari Swain', 'CB', 'SC', 'SR', '6-0', 193, 44, None, None, 648, 2001556),
 ('viliamu', 'Kyngstonn Viliamu-Asa', 'LB', 'ND', 'JR', '6-3', 234, 45, 14, 36.1, 513, 50311235),
 ('moten', 'Ahmad Moten Sr.', 'DT', 'MIA', 'SR', '6-3', 300, 46, None, None, 415, 1179981),
 ('washington', "A'Mauri Washington", 'DT', 'ORE', 'SR', '6-3', 325, 47, 23, 25.5, 529, 2000799),
 ('sellers', 'LaNorris Sellers', 'QB', 'SC', 'SR', '6-3', 238, 48, None, None, 648, 2002443),
 ('montgomery', 'Luke Montgomery', 'IOL', 'OSU', 'SR', '6-5', 313, 49, None, None, 518, None),
 ('uiagalelei', 'Matayo Uiagalelei', 'EDGE', 'ORE', 'SR', '6-5', 265, 50, 8, 36.8, 529, 2002224),
 ('lauck', 'Trevor Lauck', 'OT', 'IOWA', 'SR', '6-5', 314, 51, 28, 28.4, 312, None),
 ('thompkins', 'Devan Thompkins', 'DT', 'BAMA', 'SR', '6-5', 300, 52, None, None, 8, 1180295),
 ('craver', 'Mario Craver', 'WR', 'TAMU', 'JR', '5-9', 180, 53, None, None, 697, 50309831),
 ('dstone', 'David Stone', 'DT', 'OU', 'JR', '6-3', 315, 54, 21, 19.8, 522, 50312233),
 ('daley', 'John Henry Daley', 'EDGE', 'MICH', 'SR', '6-5', 252, 55, 43, 58.9, 418, 1207835),
 ('rawls', "Ja'Bril Rawls", 'CB', 'FSU', 'SR', '6-1', 178, 56, None, None, 234, 2000814),
 ('mascoe', 'Bo Mascoe', 'CB', 'TEX', 'SR', '5-11', 199, 57, None, None, 703, 2000233),
 ('hubbard', 'Bray Hubbard', 'S', 'BAMA', 'SR', '6-2', 215, 58, None, None, 8, 2000357),
 ('brahmer', 'Benjamin Brahmer', 'TE', 'PSU', 'SR', '6-7', 250, 59, None, None, 539, 2001490),
 ('beers', 'Rocky Beers', 'TE', 'OU', 'SR', '6-5', 240, 60, None, None, 522, 1133813),
 # On NFL Draft Buzz's top 50 but outside WalterFootball's top 60
 ('csmith', 'Carter Smith', 'OT', 'IND', 'SR', '6-5', 310, None, 9, 46.2, 306, None),
 ('cgreen', 'Cayden Green', 'OT', 'MIZ', 'SR', '6-5', 324, None, 10, 32.1, 434, None),
 ('sayin', 'Julian Sayin', 'QB', 'OSU', 'JR', '6-1', 214, None, 17, 25.6, 518, 50310418),
 ('maiava', 'Jayden Maiava', 'QB', 'USC', 'SR', '6-4', 230, None, 20, 45.2, 657, 1177721),
 ('jscott', 'Justin Scott', 'DT', 'MIA', 'JR', '6-4', 303, None, 25, 28.0, 415, 50312162),
 ('holmes', 'A.J. Holmes Jr.', 'DT', 'TTU', 'SR', '6-3', 300, None, 26, 57.1, 700, 1177461),
 ('ccole', 'Chris Cole', 'LB', 'UGA', 'JR', '6-3', 235, None, 29, 30.9, 257, 50311181),
 ('hardy', 'Ahmad Hardy', 'RB', 'MIZ', 'JR', '5-10', 210, None, 30, 34.6, 434, None),
 ('perkins', 'Suntarine Perkins', 'LB', 'MISS', 'SR', '6-1', 220, None, 32, 75.6, 433, 2001013),
 ('zbrown', 'Zabien Brown', 'CB', 'BAMA', 'JR', '6-2', 196, None, 39, 38.9, 8, 50310416),
 ('lubin', 'Clev Lubin', 'EDGE', 'LOU', 'SR', '6-3', 260, None, 40, 51.5, 367, 1178133),
 ('siereveld', 'Austin Siereveld', 'OT', 'OSU', 'SR', '6-5', 327, None, 42, 46.5, 518, None),
 ('pieper', 'Kade Pieper', 'IOL', 'IOWA', 'SR', '6-3', 298, None, 47, 34.6, 312, None),
]

SCHOOLS = {
 'OSU': ['Ohio State', '#BB0000', '#666666', 194], 'TEX': ['Texas', '#BF5700', '#FFFFFF', 251], 'ND': ['Notre Dame', '#0C2340', '#C99700', 87],
 'IND': ['Indiana', '#990000', '#EEEDEB', 84], 'SC': ['South Carolina', '#73000A', '#000000', 2579], 'UGA': ['Georgia', '#BA0C2F', '#000000', 61],
 'MIA': ['Miami', '#005030', '#F47321', 2390], 'ORE': ['Oregon', '#154733', '#FEE123', 2483], 'RUT': ['Rutgers', '#CC0033', '#5F6A72', 164],
 'LSU': ['LSU', '#461D7C', '#FDD023', 99], 'MISS': ['Ole Miss', '#14213D', '#CE1126', 145], 'TENN': ['Tennessee', '#FF8200', '#FFFFFF', 2633],
 'BAMA': ['Alabama', '#9E1B32', '#828A8F', 333], 'MSST': ['Mississippi State', '#660000', '#FFFFFF', 344], 'CLEM': ['Clemson', '#F56600', '#522D80', 228],
 'MICH': ['Michigan', '#00274C', '#FFCB05', 130], 'MINN': ['Minnesota', '#7A0019', '#FFCC33', 135], 'ASU': ['Arizona State', '#8C1D40', '#FFC627', 9],
 'FSU': ['Florida State', '#782F40', '#CEB888', 52], 'UF': ['Florida', '#0021A5', '#FA4616', 57], 'VT': ['Virginia Tech', '#630031', '#CF4420', 259],
 'OKST': ['Oklahoma State', '#FF7300', '#000000', 197], 'OU': ['Oklahoma', '#841617', '#FDF9D8', 201], 'IOWA': ['Iowa', '#000000', '#FFCD00', 2294],
 'MIZ': ['Missouri', '#000000', '#F1B82D', 142], 'TTU': ['Texas Tech', '#CC0000', '#000000', 2641], 'LOU': ['Louisville', '#AD0000', '#000000', 97],
 'TAMU': ['Texas A&M', '#500000', '#FFFFFF', 245], 'PSU': ['Penn State', '#041E42', '#FFFFFF', 213], 'USC': ['USC', '#990000', '#FFC72C', 30],
}

KEYS = ['g', 'pc', 'pa', 'py', 'ptd', 'pint', 'ra', 'ry', 'rtd', 'rec', 'rey', 'retd', 'tk', 'tfl', 'sk', 'int', 'pbu', 'qbh', 'ff']
stats = {}
for line in (HERE / 'draft_stats.txt').read_text().splitlines():
    if not line.strip():
        continue
    k, js = line.split(' ', 1)
    d = json.loads(js)
    stats[k] = {x: d[x] for x in KEYS if d.get(x)}

# 2026 first-round slot values, four-year totals (Pro Football Network, citing Spotrac). Pick 33 from the same article.
SLOT26 = [54565500, 52103630, 50537014, 48746540, 45613238, 40018084, 35541950, 31065822, 30841760, 29611072,
          27708728, 25023034, 24351620, 23232590, 22785000, 21442128, 20994516, 20435008, 20099288, 19987396,
          19875486, 19651672, 19427870, 18980258, 18756456, 18532620, 18308844, 18196940, 17298970, 16823440,
          16425104, 16168614]

assert all(r[3] in SCHOOLS for r in P), [r[0] for r in P if r[3] not in SCHOOLS]
assert len({r[0] for r in P}) == len(P), 'duplicate key'
espn = {}
for line in (HERE / 'draft_espn.txt').read_text().splitlines():
    if line.strip():
        k, v = line.split()
        espn[k] = int(v)
out = []
missing = []
for (k, n, grp, sch, cls, ht, wt, w, b, a, tid, pid) in P:
    st = stats.get(k)
    if pid and not st:
        missing.append(k)
    r = {'id': k, 'name': n, 'grp': grp, 'sch': sch, 'cls': cls, 'ht': ht, 'wt': wt, 'w': w, 'b': b, 'a': a}
    if st:
        r['st'] = st
    if k in espn:
        r['espn'] = espn[k]
    if pid:
        r['src'] = f'https://cfbstats.com/2026/player/{tid}/{pid}/index.html'
    out.append(r)

doc = {
 'asOf': ASOF,
 'statsThru': STATS_THRU,
 'draft': {'year': 2027, 'dates': 'April 29 to May 1, 2027', 'place': 'Washington, D.C.'},
 'boards': [
   {'id': 'w', 'name': 'WalterFootball', 'updated': BOARD_DATES['w'], 'url': 'https://walterfootball.com/nfldraftbigboard2027.php'},
   {'id': 'b', 'name': 'NFL Draft Buzz', 'updated': BOARD_DATES['b'], 'url': 'https://www.nfldraftbuzz.com/buzzbigboard'},
 ],
 'schools': SCHOOLS,
 'slot26': SLOT26,
 'slot26r2first': 12937488,
 'traded': [
   {'orig': 'IND', 'own': 'NYJ', 'note': 'Sauce Gardner trade'},
   {'orig': 'LAR', 'own': 'CLE', 'note': 'Myles Garrett trade'},
   {'orig': 'DAL', 'own': 'NYJ', 'swap': 'GB', 'note': 'Quinnen Williams trade: the Jets get the earlier of the Cowboys\' own pick and the Packers\' pick Dallas holds'},
   {'orig': 'GB', 'own': 'DAL', 'swap': 'DAL', 'note': 'Micah Parsons trade'},
 ],
 'sources': [
   ['WalterFootball 2027 big board', 'https://walterfootball.com/nfldraftbigboard2027.php'],
   ['NFL Draft Buzz big board', 'https://www.nfldraftbuzz.com/buzzbigboard'],
   ['cfbstats: 2026 college stats', 'https://cfbstats.com/2026/team/index.html'],
   ['Pro Football Network: 2026 rookie scale', 'https://www.profootballnetwork.com/nfl-draft-rookie-scale-contracts-april-23-2026/'],
   ['Wikipedia: 2027 NFL draft traded picks', 'https://en.wikipedia.org/wiki/2027_NFL_draft'],
 ],
 'prospects': out,
}
OUT.write_text(json.dumps(doc, separators=(',', ':')))
print(len(out), 'prospects;', 'missing stats:', missing, 'missing espn:', [r['id'] for r in out if 'espn' not in r], '->', OUT, OUT.stat().st_size, 'bytes')
