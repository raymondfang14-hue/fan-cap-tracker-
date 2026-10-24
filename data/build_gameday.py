"""Build data/gameday.json: this week's games with the official injury report, stadium details and the model's pick
adjusted for injuries. The page adds live weather from the US National Weather Service when a game page opens.

Usage: python3 -I data/build_gameday.py <games.csv> <injuries_<season>.csv> [season]
Data: nflverse schedules/games.csv and injuries/injuries_<season>.csv (the NFL's official game-status and practice reports,
CC BY 4.0); snap shares from data/stats.json; the base pick from data/projections.json (run build_projections.py first).
Runs every day: injury reports come out Wednesday to Friday (Saturday for some games), so picks move during the week.

Injury adjustment
- Each listed player's chance of missing the game: Out 1, Doubtful 0.85, Questionable 0.3. Early in the week, before game
  statuses exist, his latest practice report stands in: did not practice 0.35, limited 0.1.
- His weight is POS_W[position] (the Elo points a full-time starter is worth; a starting quarterback is by far the most)
  times his share of his team's snaps this season, so a backup barely moves the pick and a player who has already missed
  most of the season counts little (his absence is already in the team's results).
- Team penalty = sum of chance x weight, capped at CAP. The rating gap moves by (away penalty - home penalty), and the
  win chance and projected score are recomputed from it. Betting lines are never used.

Weather (applied by the page, from api.weather.gov, US public domain) only for open-air US stadiums. Indoor and closed-roof
games and international sites get none."""
import csv, json, math, os, re, sys, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES, INJ = sys.argv[1], sys.argv[2]
SEASON = sys.argv[3] if len(sys.argv) > 3 else '2026'
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
tf = lambda t: FIX.get(t, t)
CHANCE = {'Out': 1.0, 'Doubtful': 0.85, 'Questionable': 0.3}
# Before Friday's game statuses come out, the latest practice report stands in: did not practice 0.35, limited 0.1.
PRACTICE = {'Did Not Participate In Practice': 0.35, 'Limited Participation in Practice': 0.1}
POS_W = {'QB': 75, 'RB': 5, 'FB': 2, 'WR': 9, 'TE': 6, 'T': 6, 'OT': 6, 'G': 5, 'OG': 5, 'C': 5, 'OL': 5, 'DE': 8, 'EDGE': 8, 'OLB': 6,
         'DT': 6, 'NT': 5, 'DL': 6, 'LB': 5, 'ILB': 5, 'MLB': 5, 'CB': 8, 'DB': 6, 'S': 5, 'FS': 5, 'SS': 5, 'SAF': 5, 'K': 4, 'P': 2, 'LS': 1}
CAP, PTS_PER_ELO = 150, 25
# Open-air (or retractable) US stadiums the weather service covers: stadium_id -> (lat, lon). Fixed domes are left out.
STADIUMS = {
    'SEA00': (47.5952, -122.3316), 'CAR00': (35.2258, -80.8528), 'CIN00': (39.0955, -84.5161), 'HOU00': (29.6847, -95.4107),
    'IND00': (39.7601, -86.1639), 'JAX00': (30.3239, -81.6373), 'PIT00': (40.4468, -80.0158), 'NAS00': (36.1665, -86.7713),
    'PHI00': (39.9008, -75.1675), 'NYC01': (40.8135, -74.0745), 'KAN00': (39.0489, -94.4839), 'BUF00': (42.7738, -78.7870),
    'ATL97': (33.7554, -84.4008), 'BAL00': (39.2780, -76.6227), 'CHI98': (41.8623, -87.6167), 'BOS00': (42.0909, -71.2643),
    'TAM00': (27.9759, -82.5033), 'DEN00': (39.7439, -105.0201), 'PHO00': (33.5276, -112.2626), 'DAL00': (32.7473, -97.0945),
    'SFO01': (37.4030, -121.9700), 'GNB00': (44.5013, -88.0622), 'CLE00': (41.5061, -81.6995), 'MIA00': (25.9580, -80.2389),
    'WAS00': (38.9078, -76.8645)}
INDOOR = {'DET00', 'VEG00', 'MIN01', 'NOR00', 'LAX01'}
RETRACT = {'HOU00', 'IND00', 'ATL97', 'PHO00', 'DAL00'}   # roofs usually closed; weather counts only if games.csv says open
winp = lambda d: 1 / (1 + 10 ** (-d / 400))
norm = lambda n: re.sub(r'\s+', ' ', re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', n.lower().replace('.', '').replace("'", '').replace('-', ' '))).strip()

P = json.load(open(os.path.join(HERE, 'projections.json')))
SD = json.load(open(os.path.join(HERE, 'stats.json')))
share = {}
for s in SD['players']:
    sh = max(s.get('osh', 0) or 0, s.get('dsh', 0) or 0)
    if s.get('pp') in ('K', 'P', 'LS') and s.get('g'): sh = min(1, s['g'] / max(1, s.get('tg', 1)))
    share[(s['k'], s['t'])] = max(sh, share.get((s['k'], s['t']), 0))

games = [g for g in csv.DictReader(open(GAMES, encoding='utf-8')) if g['season'] == SEASON and g['game_type'] == 'REG']
open_w = [int(g['week']) for g in games if g['home_score'] in ('', 'NA')]
WEEK = min(open_w) if open_w else max(int(g['week']) for g in games)
wk = [g for g in games if int(g['week']) == WEEK]

inj = {}
for r in csv.DictReader(open(INJ, encoding='utf-8')):
    if r['season'] != SEASON or r['game_type'] != 'REG' or int(r['week']) != WEEK: continue
    t = tf(r['team']); st = r['report_status'] or ''
    if not st and r['practice_status'] in ('', 'Full Participation in Practice'): continue
    sh = share.get((norm(r['full_name']), t), 0)
    w = POS_W.get(r['position'], 3) * sh
    hit = round((CHANCE.get(st, 0) if st else PRACTICE.get(r['practice_status'], 0)) * w, 1)
    injury = r['report_primary_injury'] or r['practice_primary_injury'] or ''
    inj.setdefault(t, []).append([r['full_name'], r['position'], st, injury, r['practice_status'].replace(' in Practice', '').replace(' In Practice', ''), r['gsis_id'], round(sh, 2), hit])
ORDER = {'Out': 0, 'Doubtful': 1, 'Questionable': 2, '': 3}
for t in inj: inj[t].sort(key=lambda x: (ORDER.get(x[2], 3), -x[7], x[0]))

ET, UTC = ZoneInfo('America/New_York'), datetime.timezone.utc
out = {}
for g in wk:
    gid, a, h = g['game_id'], tf(g['away_team']), tf(g['home_team'])
    base = P['games'].get(gid)
    if not base: continue
    pa = min(CAP, sum(x[7] for x in inj.get(a, []))); ph = min(CAP, sum(x[7] for x in inj.get(h, [])))
    p0 = min(max(base[0], 1e-4), 1 - 1e-4); d0 = 400 * math.log10(p0 / (1 - p0)); d = d0 - ph + pa
    total = base[1] + base[2]; p = winp(d); spread = d / PTS_PER_ELO
    hs, as_ = round(total / 2 + spread / 2), round(total / 2 - spread / 2)
    if p > .5 and hs <= as_: hs = as_ + 1
    if p < .5 and as_ <= hs: as_ = hs + 1
    sid, roof = g['stadium_id'], g['roof']
    indoor = sid in INDOOR or roof in ('dome', 'closed') or (sid in RETRACT and roof != 'open')
    kick = None
    if g['gametime']:
        kick = datetime.datetime.strptime(g['gameday'] + ' ' + g['gametime'], '%Y-%m-%d %H:%M').replace(tzinfo=ET).astimezone(UTC).strftime('%Y-%m-%dT%H:%MZ')
    rec = {'kick': kick, 'stadium': g['stadium'], 'roof': 'indoor' if indoor else ('outdoor' if sid in STADIUMS else 'unknown'),
           'pen': [round(pa, 1), round(ph, 1)], 'base': base, 'adj': [round(p, 3), hs, as_], 'inj': {a: inj.get(a, []), h: inj.get(h, [])}}
    if not indoor and sid in STADIUMS: rec['ll'] = STADIUMS[sid]
    out[gid] = rec
json.dump({'asOf': datetime.date.today().isoformat(), 'season': int(SEASON), 'week': WEEK,
           'source': 'NFL injury reports via nflverse (CC BY 4.0); PlainStats game model; weather from the US National Weather Service, added in the page.',
           'model': {'chance': CHANCE, 'practice': PRACTICE, 'posWeight': POS_W, 'cap': CAP}, 'games': out},
          open(os.path.join(HERE, 'gameday.json'), 'w'), separators=(',', ':'))
moved = sorted(out.items(), key=lambda kv: -abs(kv[1]['adj'][0] - kv[1]['base'][0]))[:3]
print('gameday: week', WEEK, '|', len(out), 'games |', sum(len(v) for v in inj.values()), 'injury rows | biggest moves',
      [(k, v['base'][0], v['adj'][0]) for k, v in moved])
