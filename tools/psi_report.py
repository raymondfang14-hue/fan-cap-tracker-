"""Weekly PageSpeed Insights (Lighthouse) report for plainstatsnfl.com: speed, accessibility, best practices and SEO scores,
Core Web Vitals, and the biggest fixes Google suggests, for the pages people land on most.

Run:  python3 -I tools/psi_report.py [--out report.md] [--prev last_report.md] [--base https://plainstatsnfl.com]
Needs: PSI_API_KEY in the environment (a free Google Cloud API key with the PageSpeed Insights API enabled). Without one,
Google answers most requests with 429 (too many requests), and the report says so.
Run by .github/workflows/pagespeed-weekly.yml, which posts the report as a GitHub issue labelled "pagespeed".
Lab scores come from one Lighthouse run in Google's data center (a mid-range phone on a slow 4G connection for "mobile"), so
they move a few points week to week; the field data (real Chrome users, last 28 days) only shows once a page has enough visits.
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

PAGES = ['/', '/players/patrick-mahomes', '/teams/kc', '/team-tiers', '/power-rankings', '/contracts', '/scores', '/weekly',
         '/learn/epa']
CATS = ['performance', 'accessibility', 'best-practices', 'seo']
API = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'


def run(url, strategy, key):
    q = [('url', url), ('strategy', strategy)] + [('category', c) for c in CATS] + ([('key', key)] if key else [])
    for attempt in range(3):
        try:
            with urllib.request.urlopen(API + '?' + urllib.parse.urlencode(q), timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(20 * (attempt + 1)); continue
            return {'error': f'HTTP {e.code}' + (' (too many requests: add the PSI_API_KEY secret)' if e.code == 429 else '')}
        except Exception as e:
            if attempt == 2:
                return {'error': str(e)}
            time.sleep(10)


def summarize(d):
    if 'error' in d:
        return {'error': d['error']}
    lh = d.get('lighthouseResult', {})
    cats = {c: round((lh.get('categories', {}).get(c, {}).get('score') or 0) * 100) for c in CATS}
    au = lh.get('audits', {})
    num = lambda k: au.get(k, {}).get('displayValue', '–')
    field = d.get('loadingExperience', {}).get('metrics', {})
    fv = lambda k: field.get(k, {}).get('category', '').lower().replace('_', ' ') or None
    opps = sorted([(a.get('details', {}).get('overallSavingsMs') or 0, a.get('title', ''))
                   for a in au.values() if a.get('details', {}).get('type') == 'opportunity' and (a.get('score') or 1) < 0.9],
                  reverse=True)[:3]
    return {'cats': cats, 'lcp': num('largest-contentful-paint'), 'cls': num('cumulative-layout-shift'),
            'tbt': num('total-blocking-time'), 'field_lcp': fv('LARGEST_CONTENTFUL_PAINT_MS'), 'field_inp': fv('INTERACTION_TO_NEXT_PAINT'),
            'field_cls': fv('CUMULATIVE_LAYOUT_SHIFT_SCORE'), 'opps': [f'{t} (about {ms / 1000:.1f}s)' for ms, t in opps if ms >= 100]}


def main(a):
    key = os.environ.get('PSI_API_KEY', '')
    prev = {}
    if a.prev and os.path.exists(a.prev):
        m = re.search(r'<!-- psi-data (.*?) -->', open(a.prev).read(), re.S)
        prev = json.loads(m.group(1)) if m else {}
    res = {}
    for p in PAGES:
        for s in ('mobile', 'desktop') if p == '/' else ('mobile',):
            res[f'{s} {p}'] = summarize(run(a.base.rstrip('/') + p, s, key))
            time.sleep(1 if key else 8)
    ch = lambda k, c: '' if not prev.get(k, {}).get('cats') else f" ({res[k]['cats'][c] - prev[k]['cats'][c]:+d})"
    out = ['## PageSpeed Insights, plainstatsnfl.com', '',
           'Lighthouse lab scores out of 100 (change from last week in brackets). Mobile is a mid-range phone on slow 4G.', '',
           '| Page | Speed | Accessibility | Best practices | SEO | LCP | CLS | TBT |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for k, r in res.items():
        if 'error' in r:
            out.append(f'| {k} | {r["error"]} | | | | | | |'); continue
        c = r['cats']
        out.append(f"| {k} | {c['performance']}{ch(k, 'performance')} | {c['accessibility']}{ch(k, 'accessibility')} | "
                   f"{c['best-practices']}{ch(k, 'best-practices')} | {c['seo']}{ch(k, 'seo')} | {r['lcp']} | {r['cls']} | {r['tbt']} |")
    field = [(k, r) for k, r in res.items() if 'error' not in r and r['field_lcp']]
    out += ['', '### Real visitors (Chrome field data, last 28 days)', '']
    out += ([f"- {k}: LCP {r['field_lcp']}, INP {r['field_inp'] or '–'}, CLS {r['field_cls'] or '–'}" for k, r in field]
            or ['Not enough Chrome visits yet for field data on these pages.'])
    out += ['', '### Biggest suggested fixes', '']
    fixes = [f"- {k}: " + '; '.join(r['opps']) for k, r in res.items() if 'error' not in r and r['opps']]
    out += fixes or ['None over 0.1s.']
    errs = sum('error' in r for r in res.values())
    if errs:
        out += ['', f'{errs} of {len(res)} pages could not be measured.' + ('' if key else ' No PSI_API_KEY is set (see the top of tools/psi_report.py).')]
    out += ['', f"<!-- psi-data {json.dumps({k: r for k, r in res.items() if 'error' not in r})} -->"]
    report = '\n'.join(out)
    print(report)
    if a.out:
        open(a.out, 'w').write(report + '\n')
    return 1 if errs == len(res) else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--prev')
    ap.add_argument('--base', default='https://plainstatsnfl.com')
    sys.exit(main(ap.parse_args()))
