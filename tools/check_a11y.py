"""Accessibility check for PlainStats: runs axe-core (the standard open-source accessibility rules) on every view that
tools/check_pages.py opens, at phone and desktop size, in light and dark mode, and lists what fails.

Run:  python3 -I tools/check_a11y.py [--url https://plainstatsnfl.com] [--views /,/team/kc] [--impact serious] [--json out.json]
  --impact   lowest level to report: minor, moderate, serious (default) or critical
  --views    comma-separated paths instead of the full list in check_pages.py
  --json     also write every result (rule, impact, view, mode, selector) to a file
Needs: pip install playwright (the sandbox has Chromium already) and axe-core, fetched once from npm into ~/.cache/plainstats/.
Report only: exits 1 when anything at or above --impact fails, so it can gate a push later, but nothing calls it yet.
"""
import argparse, asyncio, glob, importlib.util, json, os, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXE_VERSION = '4.10.2'
CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'plainstats', f'axe-core-{AXE_VERSION}')
LEVELS = ['minor', 'moderate', 'serious', 'critical']
MODES = [(390, 844, 'phone', 'light'), (390, 844, 'phone', 'dark'), (1280, 900, 'desktop', 'light'), (1280, 900, 'desktop', 'dark')]


def check_pages():
    """The view list and local server from check_pages.py, so both checks always open the same pages."""
    spec = importlib.util.spec_from_file_location('check_pages', os.path.join(ROOT, 'tools', 'check_pages.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def axe_source():
    path = os.path.join(CACHE, 'package', 'axe.min.js')
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        tgz = subprocess.run(['npm', 'pack', f'axe-core@{AXE_VERSION}', '--silent'], cwd=CACHE, check=True,
                             capture_output=True, text=True).stdout.strip().splitlines()[-1]
        with tarfile.open(os.path.join(CACHE, tgz)) as t:
            t.extract('package/axe.min.js', CACHE)
    return open(path).read()


async def main(args):
    from playwright.async_api import async_playwright
    cp = check_pages()
    views = args.views.split(',') if args.views else cp.VIEWS
    base = (args.url or cp.serve()).rstrip('/')
    axe = axe_source()
    floor = LEVELS.index(args.impact)
    found = []   # one entry per (rule, view, mode)
    async with async_playwright() as p:
        # PW_CHROMIUM: a browser already on the machine; in a Claude cloud session the preinstalled one is used when the pip
        # playwright wants a different build than /opt/pw-browsers holds
        exe = os.environ.get('PW_CHROMIUM') or next(iter(sorted(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux*/chrome'))), None)
        browser = await p.chromium.launch(executable_path=exe)

        async def run_mode(w, h, size, scheme):
            page = await browser.new_page(viewport={'width': w, 'height': h}, color_scheme=scheme)
            if not args.url:   # same as check_pages.py: only this repo's files
                await page.route(lambda u: not u.startswith(base), lambda route: route.abort())
            for v in views:
                try:
                    # same wait as check_pages.py: load, then networkidle only briefly (/scores keeps polling, so it never goes idle)
                    await page.goto(base + v, wait_until='load', timeout=60000)
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(800)
                    await page.add_script_tag(content=axe)
                    res = await page.evaluate("""() => axe.run(document, {resultTypes: ['violations']})
                        .then(r => r.violations.map(x => ({id: x.id, impact: x.impact, help: x.help, url: x.helpUrl,
                            nodes: x.nodes.length, sample: x.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
                except Exception as e:
                    found.append({'id': 'check-failed', 'impact': 'critical', 'help': str(e).splitlines()[0], 'url': '',
                                  'nodes': 0, 'sample': [], 'view': v, 'mode': f'{size}/{scheme}'})
                    continue
                for r in res:
                    if LEVELS.index(r['impact'] or 'minor') >= floor:
                        found.append(dict(r, view=v, mode=f'{size}/{scheme}'))
            await page.close()

        await asyncio.gather(*(run_mode(*m) for m in MODES))
        await browser.close()

    # Group by rule so one site-wide problem (say, a low-contrast label) reads as one line, not 200.
    rules = {}
    for f in found:
        r = rules.setdefault(f['id'], {'impact': f['impact'], 'help': f['help'], 'url': f['url'], 'views': set(), 'modes': set(),
                                       'nodes': 0, 'sample': f['sample']})
        r['views'].add(f['view']); r['modes'].add(f['mode']); r['nodes'] += f['nodes']
    order = sorted(rules.items(), key=lambda kv: (-LEVELS.index(kv[1]['impact'] or 'minor'), -len(kv[1]['views'])))
    for rid, r in order:
        print(f"{r['impact'].upper():9} {rid}: {r['help']}")
        print(f"          {len(r['views'])} views, {r['nodes']} elements, modes: {', '.join(sorted(r['modes']))}")
        print(f"          views: {', '.join(sorted(r['views'])[:8])}{' ...' if len(r['views']) > 8 else ''}")
        if r['sample']:
            print(f"          e.g. {' | '.join(r['sample'])}")
        if r['url']:
            print(f"          {r['url']}")
    print(f'{len(views)} views x {len(MODES)} modes checked, {len(rules)} rules failing at {args.impact} or above')
    if args.json:
        json.dump(found, open(args.json, 'w'), indent=1)
    return 1 if rules else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', help='check a live URL instead of this repo')
    ap.add_argument('--views', help='comma-separated paths (default: every view in check_pages.py)')
    ap.add_argument('--impact', default='serious', choices=LEVELS)
    ap.add_argument('--json', help='write every result to this file')
    sys.exit(asyncio.run(main(ap.parse_args())))
