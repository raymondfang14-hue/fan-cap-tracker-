"""Weekly Search Console report: how every part of plainstatsnfl.com does in Google search, which searches to win next,
and which /players/<name> pages gained impressions.

The report opens with the whole site by section (player pages, comparisons, teams, draft, explainers, app pages, home), then
"Searches to win next": searches where the site already shows up at positions 4 to 20 with real impressions, each with the page
Google showed and that page's title today, ranked by the clicks within reach if it reached the top 3 (estimated from this site's
own click rate at the top 3 that week; left out when there is too little top-3 data to say). Then, as before, it compares the last 7 days that Search Console has data for (it runs about 3 days behind) with the 7 days before and writes
a Markdown report: totals with the click rate, the top searches that show a player page (with their change, click rate and
the page Google showed), searches seen often but rarely clicked (the ones titles and descriptions should answer), then per
page the biggest gainers in impressions, pages showing up for the first time and the biggest drops, each with its click
rate and its top search. A "Player vs. player searches" section lists searches like "hurts vs mckee", says whether a comparison
page (/players/<a>-vs-<b>) already exists and, when both names match a player, prints the line to add to data/compare_pairs.json
so the next build gives the pair its own page. It reads only our own site's Search Console numbers. Google leaves rare searches out of the
per-search numbers for privacy, so search totals come in below page totals.

Run by .github/workflows/search-console-weekly.yml (Monday mornings), which posts the report as a GitHub issue.
Needs:
  GSC_SERVICE_ACCOUNT  the JSON key of a Google Cloud service account that has the Search Console API enabled and has been
                       added as a user (Restricted is enough) on the plainstatsnfl.com property in Search Console.
  GSC_SITE             optional; the property, default "sc-domain:plainstatsnfl.com" (use "https://plainstatsnfl.com/"
                       for a URL-prefix property).

Usage: python3 -I tools/gsc_report.py [--out report.md] [--top 25]
       python3 -I tools/gsc_report.py --demo        (made-up numbers, to check the report layout without Google access)
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

API = 'https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query'
SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
LAG = 3   # days Search Console data trails today


def token():
    raw = os.environ.get('GSC_SERVICE_ACCOUNT', '').strip()
    if not raw:
        sys.exit('GSC_SERVICE_ACCOUNT is not set (see the top of tools/gsc_report.py).')
    from google.oauth2 import service_account          # pip install google-auth (the workflow does this)
    from google.auth.transport.requests import Request
    cred = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=[SCOPE])
    cred.refresh(Request())
    return cred.token


def query(tok, site, start, end, dims=('page',)):
    """Clicks, impressions and position across the whole site for start..end (inclusive), keyed by the dims values
    (one value: a string; several, e.g. ('query', 'page'): a tuple)."""
    url = API.format(site=urllib.parse.quote(site, safe=''))
    rows, at = {}, 0
    while True:
        body = {'startDate': start.isoformat(), 'endDate': end.isoformat(), 'dimensions': list(dims), 'rowLimit': 25000, 'startRow': at}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            got = json.load(r).get('rows', [])
        for x in got:
            k = x['keys'][0] if len(dims) == 1 else tuple(x['keys'])
            rows[k] = {'clicks': x['clicks'], 'imp': x['impressions'], 'pos': x['position']}
        if len(got) < 25000:
            return rows
        at += len(got)


NAMES = None


def name_of(url):
    """The player's name as the site spells it (Tanner McKee, Joe Milton III), from og-data/players.json;
    the address, title-cased, only for a page that file does not know."""
    global NAMES
    if NAMES is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'og-data', 'players.json')) as f:
                NAMES = {k: v.get('t') for k, v in json.load(f).get('cards', {}).items()}
        except (OSError, ValueError):
            NAMES = {}
    slug = urllib.parse.urlparse(url).path.rstrip('/').split('/')[-1].replace('.html', '')
    if '-vs-' in slug:   # a comparison page: "Josh Allen vs. Patrick Mahomes"
        return ' vs. '.join(NAMES.get(x) or x.replace('-', ' ').title() for x in slug.split('-vs-', 1))
    return NAMES.get(slug) or slug.replace('-', ' ').title()


ZERO = {'clicks': 0, 'imp': 0, 'pos': None}
MIN_IMP = 20      # "seen but rarely clicked": searches with at least this many impressions ...
LOW_CTR = 0.01    # ... and a click rate below this


def ctr(r):
    return r['clicks'] / r['imp'] if r['imp'] else None


def pct(x):
    return '–' if x is None else f'{x * 100:.1f}%'


def pos(r):
    return f"{r['pos']:.1f}" if r['pos'] else '–'


def cell(text):
    """A search as typed, safe inside a Markdown table cell."""
    return str(text).replace('|', '\\|').replace('\n', ' ')


def page_link(u):
    path = urllib.parse.urlparse(u).path or '/'
    label = name_of(u) if path.startswith('/players/') and path != '/players/' else path
    return f'[{label}](https://plainstatsnfl.com{path})'


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = ('/players', '/teams', '/draft', '/learn')


def section(u):
    """Which part of the site a page belongs to."""
    path = (urllib.parse.urlparse(u).path or '/').rstrip('/') or '/'
    if path == '/':
        return 'Home'
    if path.startswith('/players/'):
        return 'Player comparisons' if '-vs-' in path else 'Player pages'
    for pre, name in (('/teams', 'Team pages'), ('/draft', 'Draft prospects'), ('/learn', 'Stat explainers'), ('/players', 'Player pages')):
        if path == pre or path.startswith(pre + '/'):
            return name
    return 'App pages'


SECTIONS = ['Player pages', 'Player comparisons', 'Team pages', 'Draft prospects', 'Stat explainers', 'App pages', 'Home']


def is_player(u):
    return section(u) == 'Player pages' and (urllib.parse.urlparse(u).path or '').rstrip('/') != '/players'


def title_of(u):
    """The page's <title> in this checkout (static pages only; app pages share index.html and get their title in the browser)."""
    path = (urllib.parse.urlparse(u).path or '/').rstrip('/')
    if not path.startswith(STATIC):
        return 'app page'
    for f in (path.lstrip('/') + '.html', path.lstrip('/') + '/index.html'):
        try:
            with open(os.path.join(ROOT, f), encoding='utf-8') as fh:
                m = re.search(r'<title>(.*?)</title>', fh.read(4000), re.S)
            if m:
                return html_unescape(m.group(1))
        except OSError:
            pass
    return 'page not in this build'


def html_unescape(s):
    import html
    return html.unescape(s)


def top_by_page(pairs):
    """The search with the most impressions for each page, from {(query, page): row}."""
    best = {}
    for (q, u), r in pairs.items():
        if r['imp'] > best.get(u, ('', ZERO))[1]['imp']:
            best[u] = (q, r)
    return best


def top_page_by_query(pairs):
    """The page with the most impressions for each search, from {(query, page): row}."""
    best = {}
    for (q, u), r in pairs.items():
        if r['imp'] > best.get(q, ('', ZERO))[1]['imp']:
            best[q] = (u, r)
    return best


VS_RE = re.compile(r'\s+(?:vs\.?|versus|v\.?)\s+')


def _norm(s):
    s = unicodedata.normalize('NFKD', s)
    return re.sub(r"[^a-z ]", '', ''.join(c for c in s if not unicodedata.combining(c)).lower().replace('-', ' ')).strip()


def _players():
    """Skill players from data/nfl.json: full name and last name (normalized) -> gsis ids."""
    try:
        rows = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'nfl.json')))['players']
    except Exception:
        return {}, {}
    full, last = {}, {}
    for r in rows:
        if r[2] in ('QB', 'RB', 'FB', 'WR', 'TE') and r[19]:
            n = _norm(r[0])
            full.setdefault(n, set()).add(r[19])
            last.setdefault(n.split()[-1] if n.split()[-1] not in ('jr', 'sr', 'ii', 'iii', 'iv') else n.split()[-2], set()).add(r[19])
    return full, last


def vs_match(q, full, last):
    """(gid, gid) when both sides of an "a vs b" search name exactly one skill player each, else None."""
    sides = VS_RE.split(_norm(q).replace('stats', '').replace('fantasy', '').strip())
    if len(sides) != 2:
        return None
    out = []
    for side in sides:
        side = side.strip()
        hit = full.get(side) or last.get(side)
        if not hit or len(hit) != 1:
            return None
        out.append(next(iter(hit)))
    return tuple(out) if out[0] != out[1] else None


WIN_LO, WIN_HI = 4, 20     # "searches to win next": average position in this range ...
TOP3_MIN_IMP = 50          # ... with clicks within reach estimated only when the top 3 had at least this many impressions


def report(now_all, prev_all, qnow, qprev, pairs, start, end, top):
    now = {u: r for u, r in now_all.items() if is_player(u)}
    prev = {u: r for u, r in prev_all.items() if is_player(u)}
    pages = set(now) | set(prev)
    diff = []
    for u in pages:
        a, b = now.get(u, ZERO), prev.get(u, ZERO)
        diff.append((a['imp'] - b['imp'], u, a, b))
    up = sorted([d for d in diff if d[0] > 0 and d[3]['imp'] > 0], key=lambda d: -d[0])[:top]
    new = sorted([d for d in diff if d[3]['imp'] == 0 and d[2]['imp'] > 0], key=lambda d: -d[0])[:top]
    down = sorted([d for d in diff if d[0] < 0], key=lambda d: d[0])[:10]
    tot = lambda rows: {'clicks': sum(x['clicks'] for x in rows.values()), 'imp': sum(x['imp'] for x in rows.values())}
    t, p = tot(now), tot(prev)
    search_of, page_of = top_by_page(pairs), top_page_by_query(pairs)
    ta, pa = tot(now_all), tot(prev_all)
    out = [f'## PlainStats in Google search, {start:%b %-d} to {end:%b %-d}',
           '', f'Compared with the 7 days before. Search Console data runs about {LAG} days behind.', '',
           f"- Whole site: **{ta['imp']:,}** impressions (was {pa['imp']:,}, {ta['imp'] - pa['imp']:+,}), "
           f"**{ta['clicks']:,}** clicks (was {pa['clicks']:,}, {ta['clicks'] - pa['clicks']:+,}), click rate **{pct(ctr(ta))}** (was {pct(ctr(pa))})",
           f'- Searches that showed the site: **{len(qnow):,}** (was {len(qprev):,})', '',
           '### By section', '', '| Section | Pages seen | Impressions | Change | Clicks | Change | Click rate |', '|---|---:|---:|---:|---:|---:|---:|']
    for sec in SECTIONS:
        a = {u: r for u, r in now_all.items() if section(u) == sec}
        b = {u: r for u, r in prev_all.items() if section(u) == sec}
        if not a and not b:
            continue
        x, y = tot(a), tot(b)
        out.append(f"| {sec} | {len(a)} | {x['imp']:,} | {x['imp'] - y['imp']:+,} | {x['clicks']:,} | {x['clicks'] - y['clicks']:+,} | {pct(ctr(x))} (was {pct(ctr(y))}) |")
    out.append('')

    # Searches to win next: already on page one or two, not yet top 3, seen often enough to matter
    top3 = [r for r in qnow.values() if r['pos'] and r['pos'] <= 3]
    t3 = tot({i: r for i, r in enumerate(top3)})
    rate3 = ctr(t3) if t3['imp'] >= TOP3_MIN_IMP else None
    near = [(q, a) for q, a in qnow.items() if a['pos'] and WIN_LO <= a['pos'] <= WIN_HI and a['imp'] >= MIN_IMP]
    reach = lambda a: max(0, round(a['imp'] * rate3 - a['clicks'])) if rate3 is not None else None
    near.sort(key=lambda kv: (-(reach(kv[1]) or 0), -kv[1]['imp']))
    out.extend(['### Searches to win next', '',
                f'Searches where the site already shows up at positions {WIN_LO} to {WIN_HI} with {MIN_IMP}+ impressions. Moving up is cheaper than '
                'ranking for something new: check that the page and its title answer the search, then watch its position next week. '
                'Position change: + means it moved up since last week. '
                + (f'"Clicks within reach" assumes the top-3 click rate this site had this week ({pct(rate3)} on {t3["imp"]:,} impressions).'
                   if rate3 is not None else f'Too few top-3 impressions this week (under {TOP3_MIN_IMP}) to estimate clicks within reach, so they are ranked by impressions.'), ''])
    if not near:
        out.extend(['None this week.', ''])
    else:
        out.extend(['| Search | Impressions | Avg. position | Change | Clicks | Within reach | Page shown most | Its title today |',
                    '|---|---:|---:|---:|---:|---:|---|---|'])
        for q, a in near[:top]:
            b = qprev.get(q, ZERO)
            u = page_of.get(q, (None,))[0]
            mv = f"{b['pos'] - a['pos']:+.1f}" if b['pos'] else 'new'
            r = reach(a)
            out.append(f"| {cell(q)} | {a['imp']:,} | {pos(a)} | {mv} | {a['clicks']:,} | {'–' if r is None else f'+{r:,}'} | "
                       f"{page_link(u) if u else '–'} | {cell(title_of(u)) if u else '–'} |")
        out.append('')
    def searches(title, note, rows):
        out.extend([f'### {title}', '', note, ''])
        if not rows:
            out.extend(['None this week.', ''])
            return
        out.extend(['| Search | Impressions | Change | Clicks | Click rate | Avg. position | Page shown most |',
                    '|---|---:|---:|---:|---:|---:|---|'])
        for q, a in rows:
            b = qprev.get(q, ZERO)
            u = page_of.get(q, (None,))[0]
            out.append(f"| {cell(q)} | {a['imp']:,} | {a['imp'] - b['imp']:+,} | {a['clicks']:,} | {pct(ctr(a))} | "
                       f"{pos(a)} (was {pos(b)}) | {page_link(u) if u else '–'} |")
        out.append('')

    ranked = sorted(qnow.items(), key=lambda kv: (-kv[1]['imp'], -kv[1]['clicks']))
    searches('Top searches', 'The searches that showed the site most often. Google leaves rare searches out, '
             'so these add up to less than the page totals.', ranked[:top])
    searches('Seen but rarely clicked',
             f'Searches with {MIN_IMP}+ impressions and a click rate under {LOW_CTR:.0%}: what people wanted that the '
             'title and description did not promise.',
             [kv for kv in ranked if kv[1]['imp'] >= MIN_IMP and ctr(kv[1]) < LOW_CTR][:15])

    # "A vs B" searches: which already have a comparison page, and the line that would give the rest one
    vs = [kv for kv in ranked if VS_RE.search(' ' + kv[0] + ' ')][:20]
    out.extend(['### Player vs. player searches', '',
                'Searches like "hurts vs mckee". A pair gets its own page (/players/<a>-vs-<b>) once its line is in '
                '`data/compare_pairs.json` (`{"pairs": [...]}`) and the next build runs.', ''])
    if not vs:
        out.extend(['None this week.', ''])
    else:
        full, last = _players()
        out.extend(['| Search | Impressions | Clicks | Page shown most | Line for data/compare_pairs.json |', '|---|---:|---:|---|---|'])
        for q, a in vs:
            u = page_of.get(q, (None,))[0]
            has = bool(u and '-vs-' in u)
            m = None if has else vs_match(q, full, last)
            line = 'has a page' if has else ('`{"a": "%s", "b": "%s", "q": "%s"}`' % (m[0], m[1], q.replace('"', '')) if m else 'names did not match one player each: add by hand')
            out.append(f"| {cell(q)} | {a['imp']:,} | {a['clicks']:,} | {page_link(u) if u else '–'} | {line} |")
        out.append('')

    def table(title, rows):
        out.extend([f'### {title}', ''])
        if not rows:
            out.extend(['None this week.', ''])
            return
        out.extend(['| Player | Impressions | Change | Clicks | Click rate | Avg. position | Top search |',
                    '|---|---:|---:|---:|---:|---:|---|'])
        for d, u, a, b in rows:
            q = search_of.get(u)
            out.append(f"| {page_link(u)} | {a['imp']:,} | {d:+,} | {a['clicks']:,} | {pct(ctr(a))} (was {pct(ctr(b))}) | "
                       f"{pos(a)} (was {pos(b)}) | {cell(q[0]) + ' (' + format(q[1]['imp'], ',') + ')' if q else '–'} |")
        out.append('')

    out.extend([f'## Player pages, {start:%b %-d} to {end:%b %-d}', '',
                f'- Player pages with impressions: **{len(now)}** (was {len(prev)})',
                f"- Impressions: **{t['imp']:,}** (was {p['imp']:,}, {t['imp'] - p['imp']:+,})",
                f"- Clicks: **{t['clicks']:,}** (was {p['clicks']:,}, {t['clicks'] - p['clicks']:+,})",
                f'- Click rate: **{pct(ctr(t))}** (was {pct(ctr(p))})', ''])
    table('Biggest gains', up)
    table('New in search this week', new)
    table('Biggest drops', down)
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--demo', action='store_true')
    a = ap.parse_args()
    end = dt.date.today() - dt.timedelta(days=LAG)
    start, pend = end - dt.timedelta(days=6), end - dt.timedelta(days=7)
    pstart = pend - dt.timedelta(days=6)
    if a.demo:   # made-up numbers, layout check only
        u = 'https://plainstatsnfl.com/players/'
        prev = {u + 'example-one': {'clicks': 2, 'imp': 40, 'pos': 18.2}, u + 'example-two': {'clicks': 0, 'imp': 90, 'pos': 25.0}}
        now = {u + 'example-one': {'clicks': 9, 'imp': 310, 'pos': 9.4}, u + 'example-three': {'clicks': 1, 'imp': 55, 'pos': 30.1},
               u + 'example-two': {'clicks': 0, 'imp': 60, 'pos': 27.3},
               'https://plainstatsnfl.com/teams/eagles': {'clicks': 4, 'imp': 120, 'pos': 11.0},
               'https://plainstatsnfl.com/learn/epa': {'clicks': 6, 'imp': 80, 'pos': 2.4},
               'https://plainstatsnfl.com/usage-risers': {'clicks': 2, 'imp': 35, 'pos': 6.2}}
        pairs = {('example one stats', u + 'example-one'): {'clicks': 7, 'imp': 140, 'pos': 8.1},
                 ('example one contract', u + 'example-one'): {'clicks': 2, 'imp': 90, 'pos': 6.5},
                 ('example two', u + 'example-two'): {'clicks': 0, 'imp': 45, 'pos': 26.8},
                 ('example three injury', u + 'example-three'): {'clicks': 1, 'imp': 30, 'pos': 31.0},
                 ('jalen hurts vs tanner mckee', u + 'tanner-mckee'): {'clicks': 0, 'imp': 25, 'pos': 9.0},
                 ('mahomes vs allen', u + 'josh-allen-vs-patrick-mahomes'): {'clicks': 1, 'imp': 20, 'pos': 7.5},
                 ('what is epa nfl', 'https://plainstatsnfl.com/learn/epa'): {'clicks': 6, 'imp': 80, 'pos': 2.4},
                 ('eagles cap space', 'https://plainstatsnfl.com/teams/eagles'): {'clicks': 1, 'imp': 90, 'pos': 9.2},
                 ('nfl target share week 9', 'https://plainstatsnfl.com/usage-risers'): {'clicks': 0, 'imp': 35, 'pos': 6.2}}
        qnow = {q: r for (q, _), r in pairs.items()}
        qprev = {'example one contract': {'clicks': 2, 'imp': 30, 'pos': 17.9}, 'example two': {'clicks': 0, 'imp': 70, 'pos': 24.2}}
    else:
        site = os.environ.get('GSC_SITE') or 'sc-domain:plainstatsnfl.com'
        tok = token()
        now, prev = query(tok, site, start, end), query(tok, site, pstart, pend)
        qnow, qprev = query(tok, site, start, end, ('query',)), query(tok, site, pstart, pend, ('query',))
        pairs = query(tok, site, start, end, ('query', 'page'))
    md = report(now, prev, qnow, qprev, pairs, start, end, a.top)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(md + '\n')
    print(md)


if __name__ == '__main__':
    main()
