"""Build data/nfl.json player contracts from PlainStats' own sources, and record where every row comes from.

Usage:  python3 -I data/build_contracts.py <folder with roster_<season>.csv and draft_picks.csv from nflverse>

Sources, in order of priority (each player row ends with a provenance code, a source index and the fields it verifies):
  r  REPORTED  data/ledger.csv: one row per deal, taken from a named news report or team announcement, with its URL.
               Fields the report states replace the old figures; fields it leaves blank are kept and listed as unverified.
  f  FORMULA   rookie contracts for the 2023-2026 draft classes, computed from the draft slot with the rookie scale in
               data/cba.json (anchored to real signings) and the CBA minimum salaries. Undrafted rookies get the minimum.
  m  MINIMUM   veterans on one-year league-minimum deals, valued with the CBA minimum salary table.
  p  PRACTICE  practice squad players, valued at the 2026 practice squad weekly pay times 18 weeks.
  u  UNVERIFIED  older figures not yet re-sourced. The scheduled refresh replaces these with ledger rows over time.

Team rosters, draft slots, credited seasons and ages come from nflverse (data licensed CC BY 4.0).
The script never invents a contract: a player with no ledger row who is not covered by a formula keeps his row as 'u'.
"""
import csv, json, math, re, sys, unicodedata, datetime

NV = sys.argv[1].rstrip('/') + '/'
SEASON = 2026
D = json.load(open('data/nfl.json'))
CBA = json.load(open('data/cba.json'))
TEAMFIX = {'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR', 'WSH': 'WAS', 'ARZ': 'ARI',
           'KAN': 'KC', 'GNB': 'GB', 'NWE': 'NE', 'NOR': 'NO', 'TAM': 'TB', 'SFO': 'SF'}
tfix = lambda t: TEAMFIX.get(t, t)

def nn(n):
    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', n)
    return re.sub(r'[^a-z]', '', n)

# ---------- CBA helpers (data/rookie_scale.py) ----------
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from rookie_scale import minsal, rookie_deal, PS, RS

# ---------- inputs ----------
ro = {}
for r in csv.DictReader(open(NV + f'roster_{SEASON}.csv')):
    k = r['gsis_id']
    if k not in ro or int(r['week']) > int(ro[k]['week']): ro[k] = r
ROST = [r for r in ro.values() if r['status'] in ('ACT', 'RES', 'DEV', 'INA', 'EXE')]
byKey = {}
for r in ROST: byKey.setdefault((nn(r['full_name']), tfix(r['team'])), r)
byName = {}
for r in ROST: byName.setdefault(nn(r['full_name']), []).append(r)

picks, probowl, dteam, pfr = {}, {}, {}, {}
for r in csv.DictReader(open(NV + 'draft_picks.csv')):
    if r['gsis_id']:
        picks[r['gsis_id']] = (int(r['season']), int(r['pick']), int(r['round']))
        probowl[r['gsis_id']] = int(r['probowls'] or 0); dteam[r['gsis_id']] = tfix(r['team']); pfr[r['gsis_id']] = r['pfr_player_id']

# Proven performance escalator (CBA Article 7): fourth-year raise for round 2-7 picks who played a lot.
# Snap shares per season from nflverse snap counts (share of his team's offensive or defensive snaps over the season).
SNAP = {}
def load_snaps(y):
    try: rows = list(csv.DictReader(open(NV + f'snap_counts_{y}.csv')))
    except FileNotFoundError: return
    team_off, team_def, pl = {}, {}, {}
    for r in rows:
        if r['game_type'] != 'REG': continue
        g = (r['team'], r['game_id'])
        o, d = float(r['offense_snaps'] or 0), float(r['defense_snaps'] or 0)
        op, dp = float(r['offense_pct'] or 0), float(r['defense_pct'] or 0)
        if op > 0: team_off[g] = max(team_off.get(g, 0), o / op)
        if dp > 0: team_def[g] = max(team_def.get(g, 0), d / dp)
        a = pl.setdefault((r['pfr_player_id'], r['team']), [0, 0]); a[0] += o; a[1] += d
    tot_o, tot_d = {}, {}
    for (t, _), v in team_off.items(): tot_o[t] = tot_o.get(t, 0) + v
    for (t, _), v in team_def.items(): tot_d[t] = tot_d.get(t, 0) + v
    for (pid, t), (o, d) in pl.items():
        sh = max(o / tot_o[t] if tot_o.get(t) else 0, d / tot_d[t] if tot_d.get(t) else 0)
        SNAP[(pid, y)] = max(SNAP.get((pid, y), 0), sh)
for y in (SEASON - 3, SEASON - 2, SEASON - 1): load_snaps(y)
TEND = CBA['rfaTenders']['2026']
def ppe_salary(gid, cls, rnd):
    if cls != SEASON - 3 or rnd < 2 or not SNAP: return 0
    sh = [SNAP.get((pfr.get(gid), cls + k), 0) for k in range(3)]
    if probowl.get(gid, 0) >= 1: return TEND['second']
    if all(x >= 0.55 for x in sh): return TEND['original'] + 250000
    need = 0.60 if rnd == 2 else 0.35
    if sum(sh) / 3 >= need or sum(x >= need for x in sh) >= 2: return TEND['original']
    return 0

ledger = list(csv.DictReader(open('data/ledger.csv')))
L = {(nn(x['name']), x['team']): x for x in ledger}

opt = CBA['fifthYearOptions2023']
OPT_EX = {nn(k): v for k, v in opt['exercised'].items()}
EXTENDED = {nn(k) for k in opt['extended']}

def age_of(r):
    try:
        b = datetime.date.fromisoformat(r['birth_date'])
        return SEASON - b.year - (1 if (9, 1) < (b.month, b.day) else 0)
    except Exception: return None

def pos_of(r):
    p, dp = r['position'], r['depth_chart_position']
    if p == 'OL': return {'T': 'LT', 'G': 'LG', 'C': 'C'}.get(dp, 'LG')
    if p == 'DL': return 'EDGE' if dp == 'DE' else 'IDL'
    if p == 'LB':
        try: w = int(r['weight'])
        except Exception: w = 240
        return 'EDGE' if dp == 'OLB' and w >= 245 else 'LB'
    if p == 'DB': return 'CB' if dp in ('CB', 'DB') else 'S'
    if p == 'RB' and dp == 'FB': return 'FB'
    return p

SRC = []
YC = {}
def src_id(name, url):
    for i, s in enumerate(SRC):
        if s[1] == url: return i
    SRC.append([name, url]); return len(SRC) - 1
CBA_SRC = src_id('PlainStats rookie scale and CBA minimum salaries (data/cba.json)', 'data/cba.json')

# row layout: name, team, pos, age, total, apy, gtd, fullyGtd, endYear, voidFlag, capHit2026, base, bonus, deadPre, deadPost,
#             prov, srcIndex, verifiedFields, reportedSigningBonus
def blank(name, team, pos, age):
    return [name, team, pos, age, None, None, None, None, None, 0, None, None, None, None, None]

def apply_rookie(row, deal, cls, pick, name, gid=None, team=None, rnd=None):
    k = SEASON - cls  # contract year index this season
    if gid:
        esc = ppe_salary(gid, cls, rnd or 9)
        if esc > deal['base'][SEASON]:
            deal['cap'][SEASON] += esc - deal['base'][SEASON]; deal['total'] += esc - deal['base'][SEASON]; deal['base'][SEASON] = esc
        if team and dteam.get(gid) and dteam[gid] != team:
            # traded or re-signed elsewhere: the signing bonus stays with his first team, so only salary counts here
            deal['cap'][SEASON] = deal['base'][SEASON]; deal['traded'] = True
    end = deal['end']
    ex = OPT_EX.get(nn(name), False) if cls == 2023 and deal['r1'] else False
    if ex is not False: end = cls + 4
    rem_bonus = round(deal['bonus'] * (4 - k) / 4)
    gtd_full = deal['r1']  # first-round deals are fully guaranteed in practice
    gtd = deal['total'] if gtd_full else deal['bonus']
    rem_base = sum(v for y, v in deal['base'].items() if y >= SEASON)
    pr = 0 if deal.get('traded') else round(deal['bonus'] / 4)
    sched = {}
    for y in range(SEASON, deal['end'] + 1):
        b = deal['base'][y]; o = pr if y == SEASON or not deal.get('traded') else 0
        o = pr if not deal.get('traded') else 0
        sched[str(y)] = [b, o, b + o]
    if ex: sched[str(cls + 4)] = [ex, 0, ex]
    YC[row[0] + '|' + (team or row[1])] = sched
    rem_bonus = 0 if deal.get('traded') else rem_bonus
    row[4:15] = [deal['total'], round(deal['total'] / 4), gtd, gtd, end, 0, deal['cap'][SEASON], deal['base'][SEASON],
                 pr, rem_bonus + (rem_base if gtd_full else 0), pr + (deal['base'][SEASON] if gtd_full else 0)]

def minimum_row(row, cs):
    vsb = CBA['vetSalaryBenefit']
    cap = minsal(vsb['countsAsCredited'], SEASON) if cs >= vsb['minCredited'] else minsal(cs, SEASON)
    sal = minsal(cs, SEASON)
    row[4:15] = [sal, sal, 0, 0, SEASON, 0, cap, sal, 0, 0, 0]

count = {'r': 0, 'f': 0, 'm': 0, 'p': 0, 'u': 0}
out = []
seen = set()
for p in D['players']:
    row = list(p[:15]) + [None] * (15 - len(p[:15]))
    name, team = row[0], row[1]
    key = (nn(name), team)
    r = byKey.get(key) or (byName.get(nn(name), [None])[0] if len(byName.get(nn(name), [])) == 1 else None)
    if r: seen.add(r['gsis_id'])
    prov, sid, ver, sb = 'u', -1, '', None
    lg = L.get(key)
    if lg:
        prov, sid = 'r', src_id(lg['source'], lg['url'])
        F = [('total', 4, 't'), ('apy', 5, 'a'), ('gtd', 6, 'g'), ('fully_gtd', 7, 'f'), ('end', 8, 'e'), ('cap2026', 10, 'c'), ('bonus', 12, 'b')]
        for col, i, ch in F:
            v = (lg.get(col) or '').strip()
            if v:
                v = int(float(v))
                if col == 'bonus': sb = v; ver += ch; continue  # total signing bonus is shown as reported, not as this year's share
                row[i] = v; ver += ch
        if lg['pos']: row[2] = row[2] or lg['pos']
    elif r and r['gsis_id'] in picks and picks[r['gsis_id']][0] >= SEASON - 3:
        cls, pk, rnd = picks[r['gsis_id']]
        deal = rookie_deal(pk, cls)
        # a player whose old row pays far more than the scale has likely been extended: leave him for the ledger
        if nn(name) not in EXTENDED:
            if not (row[5] and row[5] > 2.2 * deal['total'] / 4 and row[5] > 5e6):
                apply_rookie(row, deal, cls, pk, name, r['gsis_id'], team, rnd)
                prov, sid, ver = 'f', CBA_SRC, 'tagfecb'
    elif r and r['status'] == 'DEV':
        exp = int(r['years_exp'] or 0)
        wk = PS['weeklyVet'] if exp > 2 else PS['weekly']
        cap = wk * PS['weeks']
        row[4:15] = [cap, cap, 0, 0, SEASON, 0, cap, cap, 0, 0, 0]
        prov, sid, ver = 'p', src_id(CBA['practiceSquad']['src'][0], CBA['practiceSquad']['src'][1]), 'tagfecb'
    elif r and not r['draft_number'] and int(r['rookie_year'] or 0) >= SEASON - 1:
        minimum_row(row, int(r['years_exp'] or 0)); prov, sid, ver = 'f', CBA_SRC, 'tagfecb'
    elif r and row[10] and row[4] and row[4] <= 1.6e6:
        exp = int(r['years_exp'] or 0)
        vsb = CBA['vetSalaryBenefit']
        expect = minsal(vsb['countsAsCredited'], SEASON) if exp >= vsb['minCredited'] else minsal(exp, SEASON)
        if abs(row[10] - expect) <= 0.25 * expect:
            minimum_row(row, exp); prov, sid, ver = 'm', src_id(CBA['minSalary']['src'][0], CBA['minSalary']['src'][1]), 'tagfecb'
    if r:
        a = age_of(r)
        if a: row[3] = a
    count[prov] += 1
    out.append(row + [prov, sid, ver, sb])

# rostered draft picks and undrafted rookies missing from the old list
added = 0
for r in ROST:
    if r['gsis_id'] in seen or r['status'] == 'DEV': continue
    t = tfix(r['team'])
    row = blank(r['full_name'], t, pos_of(r), age_of(r))
    if r['gsis_id'] in picks and picks[r['gsis_id']][0] >= SEASON - 3:
        cls, pk, rnd = picks[r['gsis_id']]
        apply_rookie(row, rookie_deal(pk, cls), cls, pk, r['full_name'], r['gsis_id'], t, rnd)
    elif not r['draft_number'] and int(r['rookie_year'] or 0) >= SEASON - 1:
        minimum_row(row, int(r['years_exp'] or 0))
    else: continue
    out.append(row + ['f', CBA_SRC, 'tagfecb', None]); count['f'] += 1; added += 1

D['players'] = out
D['sources'] = SRC
D['prov'] = {'asOf': datetime.date.today().isoformat(), 'counts': count, 'added': added,
             'legend': {'r': 'Reported in a named news report or team announcement', 'f': 'Calculated with the rookie scale and CBA minimum salaries',
                        'm': 'League-minimum deal, valued with the CBA minimum salary table', 'p': 'Practice squad pay set by the CBA',
                        'u': 'Older figure not yet re-verified'}}
json.dump(D, open('data/nfl.json', 'w'), separators=(',', ':'))
json.dump({'asOf': D['prov']['asOf'], 'note': 'Year-by-year cap hits PlainStats calculates itself: rookie contracts from the rookie scale and CBA minimums (data/cba.json), plus exercised fifth-year options. Each row: [base salary, bonus counted, cap hit].', 'contracts': YC},
          open('data/years_calc.json', 'w'), separators=(',', ':'))
print('rows', len(out), count, 'added', added, 'sources', len(SRC))
