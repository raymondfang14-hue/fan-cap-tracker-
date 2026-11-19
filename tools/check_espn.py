"""Cross-check PlainStats' injury report and depth charts (both from nflverse) against ESPN's public NFL API.

Run:  python3 -I tools/check_espn.py <nflverse players.csv> [--out report.md] [--json out.json]
Needs network access to site.api.espn.com and sports.core.api.espn.com (GitHub Actions has it; the Claude sandbox does not).
players.csv (nflverse players/players.csv) maps ESPN athlete ids to gsis ids, so players are matched by gid, never by name.

What it compares, and only reports (nothing here changes the site; ESPN data is never shown on PlainStats):
  Injuries: this week's game status in data/gameday.json (the NFL's official report via nflverse) against ESPN's injury list.
    Flags a player ESPN lists as Out or Doubtful whom our report has no status for, and the other way round. Early in the week
    (before the Wednesday report) ESPN's list is its own estimate, so differences then are expected.
  Depth charts: the listed starter in data/depth.json against ESPN's depth chart at QB, RB, TE, the five line spots, K and P,
    and the top three receivers as a set. A different QB1 is the big one: it usually means an injury or benching that our
    newest nflverse snapshot has not caught yet.
Exit code: 0 with a report (differences are information, not failures); 2 when ESPN could not be read at all.
"""
import argparse, csv, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
CORE = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl'
FIX = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX'}
UA = 'Mozilla/5.0 (compatible; PlainStats data check)'
# ESPN depth chart position keys -> data/depth.json side and position
SPOTS = {'qb': ('O', 'QB'), 'rb': ('O', 'RB'), 'te': ('O', 'TE'), 'lt': ('O', 'LT'), 'lg': ('O', 'LG'), 'c': ('O', 'C'),
         'rg': ('O', 'RG'), 'rt': ('O', 'RT'), 'pk': ('S', 'K'), 'k': ('S', 'K'), 'p': ('S', 'P')}


DEADLINE = time.time() + 8 * 60   # the whole check stops asking ESPN after 8 minutes and reports what it has


def get(url):
    for attempt in range(2):
        if time.time() > DEADLINE:
            raise TimeoutError('time limit reached')
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20) as r:
                return json.load(r)
        except Exception:
            if attempt == 1:
                raise
            time.sleep(2)


def espn_ids(path):
    out = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        e, g = (r.get('espn_id') or '').split('.')[0], r.get('gsis_id') or ''
        if e and g:
            out[e] = g
    return out


def walk(o):
    """Every dict inside a JSON value (ESPN nests the same records at different depths in different endpoints)."""
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def aid(x):
    """ESPN athlete id from an athlete object (its id, or the id inside its $ref, profile link or headshot link) or a $ref."""
    if isinstance(x, dict):
        if x.get('id'):
            return str(x['id'])
        x = json.dumps(x)   # the injury list gives no id field, only links: .../player/_/id/<id>/..., .../full/<id>.png
    m = re.search(r'/athletes/(\d+)|/id/(\d+)|/players/full/(\d+)\.png', x or '')
    return next(g for g in m.groups() if g) if m else ''


def espn_injuries(by_name):
    """{espn athlete id: (team, name, status)} from ESPN's league injury list. by_name: team display name -> our code."""
    data, out = get(SITE + '/injuries'), {}
    for grp in data.get('injuries', []):
        team = FIX.get(grp.get('abbreviation', ''), grp.get('abbreviation', '')) or by_name.get(grp.get('displayName', ''), '')
        for rec in walk(grp):
            ath = rec.get('athlete')
            if not isinstance(ath, dict) or 'status' not in rec:
                continue
            t = ((ath.get('team') or {}).get('abbreviation')) or team
            st = rec['status'] if isinstance(rec['status'], str) else (rec['status'] or {}).get('name', '')
            i = aid(ath)
            if i:
                out[i] = (FIX.get(t, t), ath.get('displayName', ''), st)
    return out


def espn_teams():
    data = get(SITE + '/teams')
    out, names = {}, {}
    for t in walk(data):
        if t.get('abbreviation') and t.get('id') and t.get('displayName'):
            code = FIX.get(t['abbreviation'], t['abbreviation'])
            out[code] = str(t['id']); names[t['displayName']] = code
    return out, names


def espn_depth(team_id, season):
    """{position key: [espn athlete ids in order]} for one team."""
    data, out = get(f'{CORE}/seasons/{season}/teams/{team_id}/depthcharts?limit=20'), {}
    for item in data.get('items', []):
        for key, pos in (item.get('positions') or {}).items():
            aths = sorted(pos.get('athletes', []), key=lambda a: a.get('slot', a.get('rank', 99)))
            ids = [aid(a.get('athlete')) for a in aths]
            out.setdefault(key.lower(), [i for i in ids if i])
    return out


def main(a):
    e2g = espn_ids(a.players)
    gday = json.load(open(os.path.join(ROOT, 'data', 'gameday.json')))
    depth = json.load(open(os.path.join(ROOT, 'data', 'depth.json')))
    season = str(depth.get('season') or gday.get('season') or '2026')
    names = {}
    for p in json.load(open(os.path.join(ROOT, 'data', 'nfl.json')))['players']:
        if p[19]:
            names[p[19]] = (p[0], p[1])
    lines, found = [f"## ESPN cross-check, week {gday.get('week')}", '',
                    f"Our injury report: data/gameday.json (as of {gday.get('asOf')}). Our depth charts: data/depth.json "
                    f"(nflverse snapshot {depth.get('snap')}). ESPN is only compared against, never shown on the site.", ''], {}
    ok = 0

    # Injuries: only teams playing this week
    ours = {}
    for g in gday.get('games', {}).values():
        for team, rows in (g.get('inj') or {}).items():
            for r in rows:
                if len(r) > 5 and r[5]:
                    ours[r[5]] = (team, r[0], r[2] or '', r[4] or '')
    week_teams = {t for g in gday.get('games', {}).values() for t in (g.get('inj') or {})}
    # Only teams whose official report already gives game statuses (Out, Doubtful...). Before that (practice reports only, or
    # no report yet) ESPN's list is its own estimate and every difference is just timing.
    final = {t for g in gday.get('games', {}).values() for t, rows in (g.get('inj') or {}).items() if any(len(r) > 2 and r[2] for r in rows)}
    try:
        teams, by_name = espn_teams()
    except Exception as ex:
        teams, by_name = {}, {}
        lines += [f'ESPN team list could not be read ({ex}).', '']
    try:
        inj = espn_injuries(by_name); ok += 1
        diff = []
        for e, (team, name, st) in inj.items():
            g = e2g.get(e)
            if team not in final or not g:
                continue
            o = ours.get(g)
            # Injured reserve, PUP and suspensions are not on the weekly injury report at all, so only game statuses compare
            if st.lower() in ('out', 'doubtful') and (not o or not o[2]):
                diff.append((team, names.get(g, (name,))[0], st, (o[3] or 'listed, no game status') if o else 'not on our report'))
        for g, (team, name, st, prac) in ours.items():
            if team in final and st.lower() in ('out', 'doubtful') and g not in {e2g.get(e) for e in inj}:
                diff.append((team, name, 'not on ESPN list', st))
        found['injuries'] = diff
        wk = [e for e, v in inj.items() if v[0] in week_teams]
        lines += [f'### Injuries: {len(diff)} differences', '',
                  f'ESPN lists {len(inj)} injured players, {len(wk)} on teams playing this week ({sum(1 for e in wk if e2g.get(e))} matched to a gsis id); '
                  f'our report has {len(ours)}. Compared: Out and Doubtful, for the {len(final)} teams whose official report has game statuses '
                  f'({", ".join(sorted(final)) or "none yet"}). Injured reserve is never on the weekly report, so it is not compared.', '']
        lines += (['| Team | Player | ESPN | Ours |', '| --- | --- | --- | --- |'] +
                  [f'| {t} | {n} | {s} | {o} |' for t, n, s, o in sorted(diff)] if diff else ['None.']) + ['']
    except Exception as ex:
        lines += [f'### Injuries: ESPN could not be read ({ex})', '']

    # Depth charts
    try:
        if not teams:
            raise RuntimeError('no team list')
        ok += 1
        diff, skipped = [], []
        for team in sorted(depth.get('teams', {})):
            if team not in teams:
                continue
            try:
                ed = espn_depth(teams[team], season)
            except Exception as ex:
                skipped.append(f'{team} ({ex})'); continue
            ourt = depth['teams'][team]
            for key, (side, pos) in SPOTS.items():
                es, os_ = ed.get(key), (ourt.get(side) or {}).get(pos)
                if not es or not os_:
                    continue
                eg = e2g.get(es[0])
                if eg and eg != os_[0][0]:
                    diff.append((team, pos, names.get(eg, (eg,))[0], os_[0][1], 1 if pos == 'QB' else 2))
            ew = {e2g.get(i) for k in ('wr', 'lwr', 'rwr', 'swr', 'wr1', 'wr2', 'wr3') for i in (ed.get(k) or [])[:1]} - {None}
            ow = {r[0] for r in ((ourt.get('O') or {}).get('WR') or [])[:3]}
            if len(ew) >= 3 and ew - ow:
                diff.append((team, 'WR top 3', ', '.join(sorted(names.get(g, (g,))[0] for g in ew - ow)), 'not in our top 3', 3))
            time.sleep(0.3)
        found['depth'] = diff
        qb = [d for d in diff if d[4] == 1]
        read = sum(1 for t in depth.get('teams', {}) if t in teams) - len(skipped)
        lines += [f'### Depth charts: {len(diff)} differences ({len(qb)} at quarterback), {read} of 32 teams compared', '',
                  'Listed starters that differ. Teams list depth charts differently, so a few line and receiver differences are normal; a '
                  'different QB1 usually means an injury or benching.', '']
        lines += (['| Team | Spot | ESPN starter | Our starter |', '| --- | --- | --- | --- |'] +
                  [f'| {t} | {p} | {e} | {o} |' for t, p, e, o, _ in sorted(diff, key=lambda d: (d[4], d[0]))] if diff else ['None.']) + ['']
        if skipped:
            lines += [f'Not read from ESPN: {len(skipped)} teams: ' + '; '.join(skipped[:8]) + ('...' if len(skipped) > 8 else ''), '']
    except Exception as ex:
        lines += [f'### Depth charts: ESPN could not be read ({ex})', '']

    lines.append('Sources: our files are nflverse (CC BY 4.0); the comparison uses ESPN\'s public site API.')
    report = '\n'.join(lines)
    print(report)
    if a.out:
        open(a.out, 'w').write(report + '\n')
    if a.json:
        json.dump(found, open(a.json, 'w'), indent=1)
    return 0 if ok else 2


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('players')
    ap.add_argument('--out')
    ap.add_argument('--json')
    sys.exit(main(ap.parse_args()))
