"""Build Plain Cap data/stats.json from nflverse weekly files.
Usage: python3 -I build_stats.py <dir with nflverse csvs> <season> <out.json> [last week]
(last week: optional; leave out to use every week in the files, give it to skip a week still being played)
Needs: stats_player_week_<S>.csv, snap_counts_<S>.csv, advstats_week_{def,pass,rush,rec}_<S>.csv, players.csv
from https://github.com/nflverse/nflverse-data/releases/download/<tag>/<file>
(tags: stats_player, snap_counts, pfr_advstats, players).

Players are matched across files by id, never by name: snap counts and advanced stats use the PFR id, box scores
use the gsis id, and players.csv links the two. Names differ between files (Greg / Gregory Rousseau), so name
matching split one player into two records and his card showed zero tackles. Name + team is only a fallback for
the few players players.csv cannot link. Each output row carries "gid" (gsis id), which the page matches on."""
import csv, json, re, sys, os, datetime
from collections import defaultdict
D, S, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
LAST = int(sys.argv[4]) if len(sys.argv) > 4 else 99
rd = lambda f: [r for r in csv.DictReader(open(os.path.join(D, f), encoding='utf-8')) if not r.get('week') or int(r['week']) <= LAST]
num = lambda v: float(v) if v not in ('', None, 'NA') else 0.0
SUF = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b')
def norm(n):
    n = n.lower().replace('.', '').replace("'", '').replace('-', ' ')
    n = SUF.sub('', n)
    return re.sub(r'\s+', ' ', n).strip()
TEAMFIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR'}
tf = lambda t: TEAMFIX.get(t, t)

snaps = rd(f'snap_counts_{S}.csv')
G2P, P2G = {}, {}   # gsis id <-> pfr id
if os.path.exists(os.path.join(D, 'players.csv')):
    for r in rd('players.csv'):
        if r.get('gsis_id') and r.get('pfr_id'): G2P[r['gsis_id']] = r['pfr_id']; P2G[r['pfr_id']] = r['gsis_id']
else:
    print('warning: players.csv missing; box scores fall back to name matching')
sp = rd(f'stats_player_week_{S}.csv')
weeks = sorted({int(r['week']) for r in sp if r['season_type'] == 'REG'})
thru = max(weeks) if weeks else 0

P = {}  # key: pfr id or synthetic
def get(key, name, team):
    if key not in P:
        P[key] = {'n': name, 't': team, 'wk': {}, 's': defaultdict(float)}
    p = P[key]; return p
team_games = defaultdict(set)
for r in snaps:
    if r['game_type'] != 'REG': continue
    t = tf(r['team']); w = int(r['week']); team_games[t].add(w)
    p = get(r['pfr_player_id'], r['player'], t)
    p['pos'] = r['position']
    o, d, s_ = num(r['offense_snaps']), num(r['defense_snaps']), num(r['st_snaps'])
    op, dp = num(r['offense_pct']), num(r['defense_pct'])
    p['wk'][w] = t
    p['s']['osn'] += o; p['s']['dsn'] += d; p['s']['ssn'] += s_
    if o: p['s']['opct_sum'] += op; p['s']['og'] += 1
    if d: p['s']['dpct_sum'] += dp; p['s']['dg'] += 1
    if o or d or s_: p['s']['g'] += 1
    if op >= .5 or dp >= .5: p['s']['gs'] += 1   # games as a primary player
# team snap totals per game (for offense, defense)
tsn = defaultdict(lambda: defaultdict(float))
for r in snaps:
    if r['game_type'] != 'REG': continue
    t = tf(r['team']); w = int(r['week'])
    for side, sn, pc in (('o', 'offense_snaps', 'offense_pct'), ('d', 'defense_snaps', 'defense_pct')):
        a, b = num(r[sn]), num(r[pc])
        if a and b: tsn[(t, w)][side] = max(tsn[(t, w)][side], round(a / b))

by_name_team = {}
for k, p in P.items():
    by_name_team.setdefault((norm(p['n']), p['t']), k)
    for t in set(p['wk'].values()): by_name_team.setdefault((norm(p['n']), t), k)
def find(name, team, create=True):
    k = by_name_team.get((norm(name), team))
    if k: return P[k]
    if not create: return None
    k = 'x:' + norm(name) + ':' + team
    by_name_team[(norm(name), team)] = k
    return get(k, name, team)

# box score stats
SUM = ['completions', 'attempts', 'passing_yards', 'passing_tds', 'passing_interceptions', 'sacks_suffered', 'passing_air_yards',
       'passing_yards_after_catch', 'passing_first_downs', 'passing_epa', 'passing_20', 'passing_40', 'carries', 'rushing_yards', 'rushing_tds',
       'rushing_fumbles_lost', 'rushing_first_downs', 'rushing_epa', 'rushing_10', 'rushing_20', 'receptions', 'targets', 'receiving_yards',
       'receiving_tds', 'receiving_fumbles_lost', 'receiving_air_yards', 'receiving_yards_after_catch', 'receiving_first_downs', 'receiving_epa',
       'receiving_20', 'receiving_40', 'def_tackles_solo', 'def_tackle_assists', 'def_tackles_with_assist', 'def_tackles_for_loss', 'def_fumbles_forced', 'def_sacks',
       'def_qb_hits', 'def_interceptions', 'def_pass_defended', 'def_tds', 'penalties', 'penalty_yards', 'fg_made', 'fg_att', 'fg_made_50_59', 'fg_made_60_',
       'fg_made_40_49', 'fg_missed_40_49', 'fg_missed_50_59', 'fg_missed_60_', 'pat_made', 'pat_att', 'pt_att', 'pt_yards', 'pt_inside_20', 'pt_touchback', 'pt_net_yards',
       'punt_return_yards', 'kickoff_return_yards', 'special_teams_tds', 'fantasy_points_ppr', 'sack_fumbles_lost']
for r in sp:
    if r['season_type'] != 'REG': continue
    t = tf(r['team']); pk = G2P.get(r['player_id'])
    p = P[pk] if pk in P else find(r['player_display_name'], t)
    if pk and pk not in P and p is not None: P.setdefault(pk, p)   # box score with no snap row: later files find him by id too
    p['gsis'] = r['player_id']; p.setdefault('pos', r['position'])
    p.setdefault('bwk', set()).add(int(r['week']))
    for c in SUM: p['s'][c] += num(r.get(c))
    if r.get('passing_cpoe') not in ('', 'NA', None) and num(r['attempts']) > 0:
        p['s']['cpoe_w'] += num(r['passing_cpoe']) * num(r['attempts']); p['s']['cpoe_n'] += num(r['attempts'])
    if r.get('fg_long'): p['s']['fg_long'] = max(p['s']['fg_long'], num(r['fg_long']))
    # team totals
for f, cols in (('def', ['def_targets', 'def_completions_allowed', 'def_yards_allowed', 'def_receiving_td_allowed', 'def_air_yards_completed', 'def_yards_after_catch',
                          'def_times_blitzed', 'def_times_hurried', 'def_times_hitqb', 'def_sacks', 'def_pressures', 'def_tackles_combined', 'def_missed_tackles', 'def_ints']),
                ('pass', ['passing_drops', 'passing_bad_throws', 'times_sacked', 'times_blitzed', 'times_hurried', 'times_hit', 'times_pressured']),
                ('rush', ['carries', 'rushing_yards_before_contact', 'rushing_yards_after_contact', 'rushing_broken_tackles', 'receiving_broken_tackles']),
                ('rec', ['receiving_broken_tackles', 'receiving_drop'])):
    for r in rd(f'advstats_week_{f}_{S}.csv'):
        if r['game_type'] != 'REG': continue
        t = tf(r['team']); k = r['pfr_player_id']
        p = P.get(k) or find(r['pfr_player_name'], t)
        for c in cols:
            if f == 'rush' and c == 'carries': p['s']['adv_car'] += num(r[c]); continue
            p['s'][f + ':' + c] += num(r[c])
        # passer-rating allowed: weight by targets
        if f == 'def' and num(r['def_targets']) > 0 and r['def_passer_rating_allowed'] not in ('', 'NA'):
            p['s']['pra_w'] += num(r['def_passer_rating_allowed']) * num(r['def_targets'])

# team context: targets, air yards, rush attempts, dropbacks, sacks allowed, ybc
TT = defaultdict(lambda: defaultdict(float))
for r in sp:
    if r['season_type'] != 'REG': continue
    t = tf(r['team'])
    for c in ('targets', 'receiving_air_yards', 'carries', 'attempts', 'sacks_suffered', 'passing_tds', 'rushing_yards'): TT[t][c] += num(r.get(c))
for p in P.values():
    p['s']['team_ybc'] = 0
for r in rd(f'advstats_week_rush_{S}.csv'):
    if r['game_type'] != 'REG': continue
    t = tf(r['team']); TT[t]['ybc'] += num(r['rushing_yards_before_contact']); TT[t]['adv_car'] += num(r['carries'])

def rnd(x, d=1):
    return round(x, d) if isinstance(x, float) else x
out = []
seen_rec = set()
for k, p in P.items():
    if id(p) in seen_rec: continue   # the same record can sit under two keys (id and name fallback)
    seen_rec.add(id(p))
    s = p['s']; team = p['t']
    # most recent team
    wk = p['wk']
    if wk: team = wk[max(wk)]
    tg = len(team_games[team]) or thru
    g = max(int(s['g']), len(p.get('bwk', ())))   # a week missing from the snap file still counts if he has a box score
    if g == 0: continue
    teamo = sum(tsn[(t, w)]['o'] for w, t in [(w, team) for w in team_games[team]]) or 1
    teamd = sum(tsn[(t, w)]['d'] for w, t in [(w, team) for w in team_games[team]]) or 1
    gid = p.get('gsis') or P2G.get(k, '')
    o = {'n': p['n'], 'k': norm(p['n']), 'gid': gid, 't': team, 'pp': p.get('pos', ''), 'g': g, 'gs': int(s['gs']), 'tg': tg}
    if s['osn']: o['osn'] = int(s['osn']); o['osh'] = rnd(s['osn'] / teamo, 3); o['opg'] = rnd(s['opct_sum'] / max(1, s['og']), 3)
    if s['dsn']: o['dsn'] = int(s['dsn']); o['dsh'] = rnd(s['dsn'] / teamd, 3); o['dpg'] = rnd(s['dpct_sum'] / max(1, s['dg']), 3)
    if s['ssn']: o['ssn'] = int(s['ssn'])
    m = {}
    a = s['attempts']
    if a:
        db = a + s['sacks_suffered']
        m.update(cmp=s['completions'], att=a, pyd=s['passing_yards'], ptd=s['passing_tds'], int=s['passing_interceptions'], sk=s['sacks_suffered'],
                 ypa=s['passing_yards'] / a, cmpp=s['completions'] / a, tdp=s['passing_tds'] / a, intp=s['passing_interceptions'] / a, skp=s['sacks_suffered'] / db,
                 adot=s['passing_air_yards'] / a, epa=(s['passing_epa'] + s['rushing_epa']) / (db + s['carries']), pepa=s['passing_epa'] / db,
                 p20=s['passing_20'], cpoe=(s['cpoe_w'] / s['cpoe_n'] if s['cpoe_n'] else 0),
                 bad=s['pass:passing_bad_throws'] / a, qprs=s['pass:times_pressured'] / db, ny=(s['passing_yards'] - 0) / db)
    if s['carries']:
        c = s['carries']; ac = s['adv_car'] or c
        m.update(car=c, ryd=s['rushing_yards'], rtd=s['rushing_tds'], ypc=s['rushing_yards'] / c, repa=s['rushing_epa'] / c, r10=s['rushing_10'], r20=s['rushing_20'],
                 yco=s['rush:rushing_yards_after_contact'] / ac, ybc=s['rush:rushing_yards_before_contact'] / ac, rbt=s['rush:rushing_broken_tackles'],
                 rsh=c / max(1, TT[team]['carries']), rfd=s['rushing_first_downs'])
    if s['targets']:
        tg_ = s['targets']; rc = s['receptions']
        m.update(tgt=tg_, rec=rc, ryds=s['receiving_yards'], rectd=s['receiving_tds'], cat=rc / tg_, ypr=(s['receiving_yards'] / rc if rc else 0), ypt=s['receiving_yards'] / tg_,
                 tsh=tg_ / max(1, TT[team]['targets']), ash=s['receiving_air_yards'] / max(1, TT[team]['receiving_air_yards']), radot=s['receiving_air_yards'] / tg_,
                 yac=(s['receiving_yards_after_catch'] / rc if rc else 0), drp=s['rec:receiving_drop'], drpp=s['rec:receiving_drop'] / tg_, rfd1=s['receiving_first_downs'],
                 xepa=s['receiving_epa'] / tg_, x20=s['receiving_20'], rbt2=s['rec:receiving_broken_tackles'])
    if s['carries'] or s['targets']:
        m['fum'] = s['rushing_fumbles_lost'] + s['receiving_fumbles_lost']
        m['scr'] = s['rushing_yards'] + s['receiving_yards']
        m['ppr'] = s['fantasy_points_ppr']
    tk = s['def_tackles_solo'] + s['def_tackle_assists'] + s['def_tackles_with_assist'] - s['def_tackles_with_assist']
    # defensive line: players who mostly play defense, plus defensive players who also take offensive snaps
    # (a linebacker used at fullback, 30+ defensive snaps, or a special-teamer, still shows his tackles); an offensive player's tackle after a turnover is left out
    defpos = p.get('pos', '') in ('DE', 'DT', 'NT', 'DL', 'LB', 'OLB', 'ILB', 'MLB', 'CB', 'DB', 'S', 'FS', 'SS', 'SAF')
    if (s['dsn'] or tk or s['def:def_targets']) and (s['dsn'] >= s['osn'] or defpos or s['dsn'] >= 30 or (tk and s['ssn'] > s['osn'])):
        tk = s['def_tackles_solo'] + s['def_tackle_assists']
        att_tk = s['def:def_tackles_combined'] + s['def:def_missed_tackles']
        m.update(tk=tk, solo=s['def_tackles_solo'], tfl=s['def_tackles_for_loss'], sck=s['def_sacks'], qbh=s['def_qb_hits'], ff=s['def_fumbles_forced'],
                 dint=s['def_interceptions'], pd=s['def_pass_defended'], prs=s['def:def_pressures'], hur=s['def:def_times_hurried'], blz=s['def:def_times_blitzed'],
                 mtk=s['def:def_missed_tackles'], mtp=(s['def:def_missed_tackles'] / att_tk if att_tk else 0),
                 dtg=s['def:def_targets'], dca=s['def:def_completions_allowed'], dya=s['def:def_yards_allowed'], dtd=s['def:def_receiving_td_allowed'],
                 pra=(s['pra_w'] / s['def:def_targets'] if s['def:def_targets'] else 0), dtd2=s['def_tds'])
    if s['fg_att'] or s['pat_att']:
        m.update(fgm=s['fg_made'], fga=s['fg_att'], fgp=(s['fg_made'] / s['fg_att'] if s['fg_att'] else 0), fg50=s['fg_made_50_59'] + s['fg_made_60_'],
                 fg40a=s['fg_made_40_49'] + s['fg_missed_40_49'] + s['fg_made_50_59'] + s['fg_missed_50_59'] + s['fg_made_60_'] + s['fg_missed_60_'],
                 fg40m=s['fg_made_40_49'] + s['fg_made_50_59'] + s['fg_made_60_'], lng=s['fg_long'], patm=s['pat_made'], pata=s['pat_att'])
    if s['pt_att']:
        n_ = s['pt_att']; m.update(pun=n_, pavg=s['pt_yards'] / n_, pnet=s['pt_net_yards'] / n_, pi20=s['pt_inside_20'], ptb=s['pt_touchback'], pi20p=s['pt_inside_20'] / n_)
    if s['penalties']: m['pen'] = s['penalties']
    if not o['gid']: del o['gid']
    o['m'] = {k2: rnd(v, 3) if isinstance(v, float) and abs(v) < 10 else rnd(v, 1) for k2, v in m.items() if v}
    out.append(o)
# team unit context for O-line
teams = {}
for t, v in TT.items():
    db = v['attempts'] + v['sacks_suffered']
    teams[t] = {'skp': round(v['sacks_suffered'] / db, 4) if db else 0, 'ybc': round(v['ybc'] / v['adv_car'], 2) if v['adv_car'] else 0,
                'ypc': round(v['rushing_yards'] / v['carries'], 2) if v['carries'] else 0, 'g': len(team_games[t])}
json.dump({'asOf': datetime.date.today().isoformat(), 'season': int(S), 'thru': thru, 'source': 'nflverse (nflverse-data releases: stats_player, snap_counts, pfr_advstats)',
           'teams': teams, 'players': out}, open(OUT, 'w'), separators=(',', ':'))
print('players', len(out), 'thru week', thru)
