"""Smoke test for PlainStats: opens every main view at phone and desktop size, in light and dark mode,
and fails if a page throws a JavaScript error, a data file fails to load, or the page scrolls sideways.

Run:  python3 -I tools/check_pages.py [--shots DIR] [--url https://plainstatsnfl.com]
Needs: pip install playwright && python3 -m playwright install chromium
Without --url it serves this repo locally, so it tests what you are about to push.
"""
import argparse, asyncio, functools, http.server, json, os, re, sys, threading

VIEWS = ['/', '/news', '/team-ratings', '/team/kc', '/contracts', '/power-rankings', '/awards', '/big-board', '/scores', '/standings',
         '/projections', '/roster-builder', '/#offseason', '/trade-checker', '/compare', '/cap-101', '/stats', '/player/patrick-mahomes-kc']
SHARE_VIEWS = ['/team-ratings', '/contracts', '/power-rankings', '/big-board']   # views whose charts and tables must each get a "Share this" button
SIZES = [(390, 844, 'phone'), (1280, 900, 'desktop')]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def serve():
    # Same routing as Vercel: clean .html URLs, and the rewrites in vercel.json send app paths to index.html.
    pats = []
    for r in json.load(open(os.path.join(ROOT, 'vercel.json'))).get('rewrites', []):
        p = re.sub(r':\w+\(([^)]+)\)', r'(\1)', r['source'])
        pats.append(re.compile('^' + re.sub(r':\w+', '[^/]+', p) + '$'))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def translate_path(self, path):
            q = path.split('?')[0].split('#')[0]
            f = os.path.join(ROOT, q.lstrip('/'))
            if q != '/' and not os.path.exists(f):
                if os.path.exists(f + '.html'):
                    return f + '.html'
                if any(p.match(q) for p in pats):
                    return os.path.join(ROOT, 'index.html')
            return super().translate_path(path)
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{s.server_address[1]}'


async def main(args):
    from playwright.async_api import async_playwright
    base = (args.url or serve()).rstrip('/')
    problems = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get('PW_CHROMIUM') or None)   # PW_CHROMIUM: a browser already on the machine
        for w, h, size in SIZES:
            for scheme in ('light', 'dark'):
                page = await browser.new_page(viewport={'width': w, 'height': h}, color_scheme=scheme)
                page.on('pageerror', lambda e, s=size, c=scheme: problems.append(f'{s}/{c}: JS error: {e}'))
                page.on('response', lambda r, s=size, c=scheme: r.status >= 400 and '/data/' in r.url
                        and problems.append(f'{s}/{c}: {r.status} loading {r.url}'))
                for v in VIEWS:
                    await page.goto(base + v, wait_until='load')
                    try:  # some pages keep polling (scores, weather), so networkidle can never come
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(600)
                    wide = await page.evaluate('document.documentElement.scrollWidth - innerWidth')
                    if wide > 1:
                        problems.append(f'{size}/{scheme} {v}: page scrolls sideways by {wide}px')
                    if v in SHARE_VIEWS:
                        try:  # the buttons appear after the data loads and a short debounce, so wait for one instead of guessing
                            await page.wait_for_function("[...document.querySelectorAll('.ps-share')].some(b => b.offsetParent)", timeout=6000)
                        except Exception:
                            problems.append(f'{size}/{scheme} {v}: no visible "Share this" button on any chart or table')
                    if v == '/stats':  # the Season stats table must fill with player rows
                        try:
                            await page.wait_for_function("document.querySelectorAll('#hs-table tbody tr').length > 5", timeout=6000)
                        except Exception:
                            problems.append(f'{size}/{scheme} #stats: the Season stats table has no rows')
                    if args.shots:
                        os.makedirs(args.shots, exist_ok=True)
                        await page.screenshot(path=os.path.join(args.shots, f"{v.strip('/#').replace('/', '_') or 'home'}-{size}-{scheme}.png"))
                await page.close()
        await browser.close()
    for line in problems:
        print('FAIL', line)
    print(f'{len(VIEWS)} pages x {len(SIZES) * 2} modes checked, {len(problems)} problems')
    return 1 if problems else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', help='folder to save screenshots in')
    ap.add_argument('--url', help='test a live URL instead of this repo')
    sys.exit(asyncio.run(main(ap.parse_args())))
