"""The NFL's official transaction wire (nfl.com/transactions) as a list, checked against PlainStats' own files.

Run:  python3 -I tools/nfl_transactions.py [--since 2026-11-15] [--json out.json] [--all]
  --since  first date to include (default: 3 days before data/moves.json asOf)
  --json   also write every transaction to a file
  --all    also list practice squad, reserve list and waiver moves (left out of the report by default; there are hundreds)

What it does: reads the six league pages (trades, signings, terminations, waivers, reserve list, other) for each month in the
window, following their "next page" links, and prints three lists for the news sweep:
  1. Trades and releases the wire shows that data/moves.json has no item for (match: player name and kind).
  2. Players a team released or waived who are still on that team in data/nfl.json (the nflverse roster has not caught up yet;
     data/build_contracts.py takes them off once it does, so these are only a heads-up).
  3. Players signed to a 53-man roster who are not on that team in data/nfl.json.
The wire is a named official source (NFL.com) for the fact of a move: who, which teams, what kind, which day. It never gives
contract figures; those still need a named report. Names are matched loosely (case, punctuation, Jr./III) because the wire has
no gsis id; treat a match as a lead to confirm, never as a gid.
"""
import argparse, datetime as dt, html, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://www.nfl.com'
CATS = ['trades', 'terminations', 'signings', 'waivers', 'reserve-list', 'other']
FIX = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'SD': 'LAC', 'OAK': 'LV', 'STL': 'LAR'}
UA = 'Mozilla/5.0 (compatible; PlainStats data check)'


def get(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def text(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s)).split())


def norm(name):
    n = re.sub(r"[.'’,-]", '', name.lower())
    n = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', n)
    return ''.join(n.split())


def parse(page, cat, year):
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        tds = re.findall(r'<td>(.*?)</td>', tr, re.S)
        if len(tds) < 6:
            continue
        def club(td):
            m = re.search(r'logos/([A-Z]{2,3})"', td)
            return FIX.get(m.group(1), m.group(1)) if m else ''
        md = text(tds[2])
        try:
            m, d = (int(x) for x in md.split('/')[:2])
        except ValueError:
            continue
        slug = re.search(r'href="/players/([^/"]+)/?"', tds[3])
        out.append({'date': f'{year}-{m:02d}-{d:02d}', 'cat': cat, 'from': club(tds[0]), 'to': club(tds[1]),
                    'name': text(tds[3]), 'pos': text(tds[4]), 'type': text(tds[5]),
                    'url': f"{BASE}/players/{slug.group(1)}/" if slug else ''})
    nxt = re.search(r'href="([^"]*\?after=[^"]*)"', page)
    return out, (html.unescape(nxt.group(1)) if nxt else None)


def wire(since, today):
    rows, months = [], sorted({(d.year, d.month) for d in (since + dt.timedelta(n) for n in range((today - since).days + 1))})
    for y, m in months:
        for cat in CATS:
            url, pages = f'{BASE}/transactions/league/{cat}/{y}/{m}', 0
            while url and pages < 15:
                out, nxt = parse(get(url), cat, y)
                pages += 1
                rows += [r for r in out if r['date'] >= since.isoformat()]
                if not out or min(r['date'] for r in out) < since.isoformat():
                    break   # pages run newest first; stop once past the window
                url = BASE + nxt if nxt and nxt.startswith('/') else nxt
    seen, uniq = set(), []
    for r in rows:
        k = (r['date'], r['cat'], r['name'], r['from'], r['to'], r['type'])
        if k not in seen:
            seen.add(k); uniq.append(r)
    return sorted(uniq, key=lambda r: (r['date'], r['cat'], r['name']), reverse=True)


def minor(r):
    t = r['type'].lower()
    return r['cat'] in ('reserve-list', 'waivers') or 'practice squad' in t or 'futures' in t


def main(a):
    moves = json.load(open(os.path.join(ROOT, 'data', 'moves.json')))
    today = dt.date.today()
    since = dt.date.fromisoformat(a.since) if a.since else dt.date.fromisoformat(moves.get('asOf', today.isoformat())) - dt.timedelta(3)
    rows = wire(since, today)
    if a.json:
        json.dump(rows, open(a.json, 'w'), indent=1)

    roster, psq = {}, set()   # normalized name -> set of teams in data/nfl.json; practice squad players (provenance p)
    for p in json.load(open(os.path.join(ROOT, 'data', 'nfl.json')))['players']:
        roster.setdefault(norm(p[0]), set()).add(p[1])
        if p[15] == 'p':
            psq.add(norm(p[0]))
    # Any news item naming the player counts (a called-off trade is filed as League, not Trade).
    named = {}
    for it in moves['moves']:
        for n in it.get('players', []):
            named.setdefault(norm(n), []).append(it.get('iso', ''))
    covered = lambda r: any(d >= (dt.date.fromisoformat(r['date']) - dt.timedelta(3)).isoformat() for d in named.get(norm(r['name']), []))

    def is_release(r):
        return r['cat'] == 'terminations' or r['type'].lower().startswith(('released', 'waived', 'terminated'))

    missing = [r for r in rows if not covered(r) and (r['cat'] == 'trades'
               or (is_release(r) and not minor(r) and norm(r['name']) in roster and norm(r['name']) not in psq))]
    # A cut followed by a signing with the same team (usually to its practice squad) is not a departure. One line per player.
    later = lambda r: any(o['date'] >= r['date'] and o['cat'] == 'signings' and o['to'] == r['from'] and norm(o['name']) == norm(r['name']) for o in rows)
    stale, seen = [], set()
    for r in rows:
        if is_release(r) and r['from'] and r['from'] in roster.get(norm(r['name']), set()) and not later(r) and norm(r['name']) not in seen \
                and (a.all or norm(r['name']) not in psq):
            seen.add(norm(r['name'])); stale.append(r)
    new = [r for r in rows if r['cat'] == 'signings' and not minor(r) and r['to'] and r['to'] not in roster.get(norm(r['name']), set())]

    line = lambda r: f"| {r['date']} | {r['name']} | {r['pos'] or '–'} | {r['from'] or '–'} | {r['to'] or '–'} | {r['type']} |"
    head = ['| Date | Player | Pos | From | To | Move |', '| --- | --- | --- | --- | --- | --- |']
    print(f'## NFL transaction wire, {since:%b %-d} to {today:%b %-d}', '',
          f'{len(rows)} transactions on nfl.com/transactions ({sum(minor(r) for r in rows)} practice squad, reserve or waiver moves).', '', sep='\n')
    for title, lst, note in [
            ('Not in data/moves.json yet', missing, 'Trades, and releases of players on our rosters, with no news item. Find a named report for each before adding it.'),
            ('Released or waived, still on that team in data/nfl.json', stale, 'The nflverse roster has not caught up; build_contracts.py takes them off when it does. Practice squad players are left out (use --all).'),
            ('Signed to a roster, not on that team in data/nfl.json', new, 'New signings; the nflverse roster usually adds them within a day or two.')]:
        print(f'### {title} ({len(lst)})', '', note, '', sep='\n')
        print('\n'.join(head + [line(r) for r in lst[:60]]) if lst else 'None.', '', sep='\n')
        if len(lst) > 60:
            print(f'...and {len(lst) - 60} more (use --json for all).', '', sep='\n')
    if a.all:
        print('### Every transaction', '', '\n'.join(head + [line(r) for r in rows]), '', sep='\n')
    print('Source: NFL.com transaction wire (https://www.nfl.com/transactions/). It states the move, never contract figures.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--since')
    ap.add_argument('--json')
    ap.add_argument('--all', action='store_true')
    sys.exit(main(ap.parse_args()))
