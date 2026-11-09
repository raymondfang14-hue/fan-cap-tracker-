"""Weekly Search Console report: which /players/<name> pages gained impressions.

Compares the last 7 days that Search Console has data for (it runs about 3 days behind) with the 7 days before, per page,
and writes a Markdown report: the biggest gainers in impressions, pages showing up for the first time, and the biggest drops.
It reads only our own site's Search Console numbers.

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
import sys
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


def query(tok, site, start, end):
    """Clicks, impressions and position per /players/ page for start..end (inclusive)."""
    url = API.format(site=urllib.parse.quote(site, safe=''))
    rows, at = {}, 0
    while True:
        body = {'startDate': start.isoformat(), 'endDate': end.isoformat(), 'dimensions': ['page'], 'rowLimit': 25000, 'startRow': at,
                'dimensionFilterGroups': [{'filters': [{'dimension': 'page', 'operator': 'contains', 'expression': '/players/'}]}]}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            got = json.load(r).get('rows', [])
        for x in got:
            rows[x['keys'][0]] = {'clicks': x['clicks'], 'imp': x['impressions'], 'pos': x['position']}
        if len(got) < 25000:
            return rows
        at += len(got)


def name_of(url):
    slug = urllib.parse.urlparse(url).path.rstrip('/').split('/')[-1]
    return slug.replace('.html', '').replace('-', ' ').title()


def report(now, prev, start, end, top):
    pages = set(now) | set(prev)
    diff = []
    for u in pages:
        a, b = now.get(u, {'clicks': 0, 'imp': 0, 'pos': None}), prev.get(u, {'clicks': 0, 'imp': 0, 'pos': None})
        diff.append((a['imp'] - b['imp'], u, a, b))
    up = sorted([d for d in diff if d[0] > 0 and d[3]['imp'] > 0], key=lambda d: -d[0])[:top]
    new = sorted([d for d in diff if d[3]['imp'] == 0 and d[2]['imp'] > 0], key=lambda d: -d[0])[:top]
    down = sorted([d for d in diff if d[0] < 0], key=lambda d: d[0])[:10]
    ti, pi = sum(x['imp'] for x in now.values()), sum(x['imp'] for x in prev.values())
    tc, pc = sum(x['clicks'] for x in now.values()), sum(x['clicks'] for x in prev.values())
    pos = lambda r: f"{r['pos']:.1f}" if r['pos'] else '–'
    out = [f'## Player pages in Google search, {start:%b %-d} to {end:%b %-d}',
           '', f'Compared with the 7 days before. Search Console data runs about {LAG} days behind.', '',
           f'- Player pages with impressions: **{len(now)}** (was {len(prev)})',
           f'- Impressions: **{ti:,}** (was {pi:,}, {ti - pi:+,})',
           f'- Clicks: **{tc:,}** (was {pc:,}, {tc - pc:+,})', '']

    def table(title, rows):
        out.extend([f'### {title}', ''])
        if not rows:
            out.extend(['None this week.', ''])
            return
        out.extend(['| Player | Impressions | Change | Clicks | Avg. position |', '|---|---:|---:|---:|---:|'])
        for d, u, a, b in rows:
            path = urllib.parse.urlparse(u).path
            out.append(f"| [{name_of(u)}](https://plainstatsnfl.com{path}) | {a['imp']:,} | {d:+,} | {a['clicks']:,} | {pos(a)} (was {pos(b)}) |")
        out.append('')

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
               u + 'example-two': {'clicks': 0, 'imp': 60, 'pos': 27.3}}
    else:
        site = os.environ.get('GSC_SITE') or 'sc-domain:plainstatsnfl.com'
        tok = token()
        now, prev = query(tok, site, start, end), query(tok, site, pstart, pend)
    md = report(now, prev, start, end, a.top)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(md + '\n')
    print(md)


if __name__ == '__main__':
    main()
