"""Render the weekly team-tiers carousel (Instagram 1080x1350 and/or TikTok 1080x1920) from a content file.

  python3 -I render_post.py --content WORK/content.json --photos WORK/photos --out WORK/out [--format ig|tt|both]

Reads data/tiers.json, data/projections.json and data/espn_assets.json from the repo root (record, rank, rank change, net EPA
and logos come from the data; only the words in content.json are hand-written). Needs the python `playwright` package and
Chromium. Writes OUT/<format>/NN_<slug>.png plus OUT/<format>/contact.png. Prints WARNINGS (missing "why", too long, missing
photo credit); fix every warning before sharing the images.

content.json (see SKILL.md for the full recipe):
{
  "cover":  {"photo": "cover_JAX", "label": "Week 8 NFL Team Tiers ...", "line1": "...", "line2": "...", "line2_color": "#00D1E6",
             "pills": ["JAX", "BUF", "MIN"]},
  "slides": [
    {"type": "tier", "tier": 1, "photo": "t1", "title": "Best in the league", "hook": "...", "why": {"JAX": "...", ...}},
    {"type": "movers", "photo": "mv", "title": "Risers & fallers", "hook": "...", "up": ["PIT", "CHI"], "down": ["SEA", "BAL"],
     "why": {"PIT": "..."}, "also": "Also up: ... Also down: ..."},
    {"type": "cta", "photo": "cta"}
  ],
  "crop": {"t1": {"ig": ["cover", "50% 0%"], "tt": ["auto 128%", "50% 100%"]}}     # optional per photo and format
}
A tier slide lists every team of that tier (override with "teams": [...]). Rows with up to 5 teams get two-line reasons
(about 100 characters), 6 to 7 teams two shorter lines (about 100), 8 or more one line (about 48 characters).
"""
import argparse, glob, html, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
E = html.escape
TCOL = {1: '#34d399', 2: '#60a5fa', 3: '#a3a3b2', 4: '#fbbf24', 5: '#f87171'}

# row sizes: (row height, logo tile, name px, reason px, rank px, net px, show "net EPA/play" label)
FORMATS = {
    'ig': dict(w=1080, h=1350, pad='0 64px 52px 64px', pill_top=52, credit_bottom=20, dots=True,
               big=(116, 80, 32, 24, 42, 34, True), mid=(104, 70, 30, 23, 40, 32, False), tiny=(68, 50, 26, 22, 32, 28, False),
               movers=(112, 76, 31, 24, 42, 32, False), cover_px=96, cta_px=104),
    'tt': dict(w=1080, h=1920, pad='0 110px 350px 64px', pill_top=150, credit_bottom=296, dots=False,
               big=(132, 84, 34, 26, 44, 36, True), mid=(104, 70, 30, 24, 40, 32, False), tiny=(72, 52, 27, 23, 32, 28, False),
               movers=(126, 80, 32, 25, 42, 34, False), cover_px=92, cta_px=104),
}
LIMITS = {'big': 105, 'mid': 105, 'tiny': 50, 'movers': 90}

CSS = """
@font-face{font-family:Inter;font-weight:600;src:url('file://@@FONTS@@/Inter-SemiBold.otf')}
@font-face{font-family:Inter;font-weight:800;src:url('file://@@FONTS@@/Inter-ExtraBold.otf')}
*{box-sizing:border-box;margin:0;padding:0}
body{width:@@W@@px;height:@@H@@px;background:#0b0d12;color:#f5f5f7;font-family:Inter,system-ui,sans-serif;font-weight:600;position:relative;overflow:hidden}
.photo{position:absolute;inset:0;background-repeat:no-repeat}.shade{position:absolute;inset:0}
.pill{position:absolute;left:64px;top:@@PILL@@px;background:#fff;color:#0b0d12;font-weight:800;font-size:30px;padding:10px 24px;border-radius:99px;z-index:3}
.dots{position:absolute;right:64px;top:72px;display:@@DOTS@@;gap:11px;z-index:3}.dots i{width:13px;height:13px;border-radius:50%;display:block}
.credit{position:absolute;left:64px;right:@@CREDR@@px;bottom:@@CREDB@@px;font-size:18px;color:rgba(255,255,255,.55);z-index:3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wrap{position:absolute;inset:0;padding:@@PAD@@;display:flex;flex-direction:column;justify-content:flex-end;z-index:2}
h1{font-weight:800;letter-spacing:-2px;line-height:1.0}
.tag{display:inline-block;align-self:flex-start;font-weight:800;font-size:26px;padding:6px 18px;border-radius:99px;background:var(--c);color:#06111F}
.hook{color:#e3e6ee;line-height:1.25}
.rows{display:flex;flex-direction:column;gap:var(--gap)}
.row{height:var(--rh);background:rgba(12,15,21,.58);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-radius:24px;padding:0 24px;display:flex;align-items:center;gap:18px;border:1px solid rgba(255,255,255,.07)}
.rk{font-weight:800;width:46px;text-align:center;color:#9aa0ae;flex:none}
.av{flex:none;border-radius:26%;background:#f2f3f6;width:var(--av);height:var(--av);display:flex;align-items:center;justify-content:center}
.lgo{width:80%;height:80%;object-fit:contain}
.mid{flex:1;min-width:0}.nm{font-weight:800;display:flex;align-items:center;gap:10px;white-space:nowrap}
.rec{color:#aab0be;font-weight:600;font-size:.8em}.why{color:#d3d7e2;line-height:1.26;margin-top:3px}
.net{text-align:right;flex:none;width:100px}.net b{display:block;font-weight:800}.net i{font-style:normal;font-size:17px;color:#9aa0ae}
.mv{font-size:.62em;font-weight:800;padding:2px 10px;border-radius:99px;background:rgba(255,255,255,.12);color:#c9cdd8}
.mv.up{background:#10382a;color:#34d399}.mv.dn{background:#41181a;color:#f87171}
.foot{display:flex;justify-content:space-between;font-size:21px;color:#9aa0ae;margin-top:16px;margin-bottom:26px}.foot b{color:#f5f5f7;font-weight:800}
.sec{font-weight:800;font-size:26px;margin:14px 0 8px;display:flex;align-items:center;gap:10px}
"""


def load():
    d = lambda f: json.load(open(ROOT / 'data' / f))
    tiers, proj, assets = d('tiers.json'), d('projections.json'), d('espn_assets.json')
    return tiers, proj['teams'], {k: v['name'] for k, v in assets['teams'].items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', required=True); ap.add_argument('--photos', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--format', default='both', choices=['ig', 'tt', 'both'])
    ap.add_argument('--logos', help='folder of <TEAM>.png logos (default: <out>/../logos, fetched when missing)')
    a = ap.parse_args()
    C = json.load(open(a.content)); photos_dir = Path(a.photos).resolve(); out = Path(a.out).resolve()
    meta = json.load(open(photos_dir / 'photos.json'))
    tiers, P, N = load(); T = tiers['teams']; thru = tiers['thru']
    logos = Path(a.logos).resolve() if a.logos else out.parent / 'logos'
    if len(list(logos.glob('*.png'))) < 32:
        os.makedirs(logos, exist_ok=True)
        import subprocess
        subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('photos.py')), 'logos', '--dir', str(logos)], check=True, cwd=ROOT)
    tier_names = {t[0]: t[2] for t in tiers['tiers']}
    order = sorted(T, key=lambda k: T[k]['rank'])
    warn = []

    def credit(slot):
        m = meta.get(slot)
        if not m:
            warn.append(f'no credit for photo {slot} in photos.json'); return ''
        t = re.sub(r'^File:', '', m['title']); t = re.sub(r'\.\w+$', '', t); t = re.sub(r'\s*\(\d{6,}\)', '', t)[:44]
        who = re.sub(r'\s+', ' ', m['artist'] or 'Wikimedia Commons')[:34]
        return f'"{t}" by {who}, {m["lic"]}' if m['lic'].startswith('CC BY') else f'Photo: {who} · {m["lic"]}'

    def sgn(x):
        r = round(x, 2); return '0.00' if r == 0 else f'{r:+.2f}'

    def badge(m):
        return f'<span class="mv up">▲ {m}</span>' if m > 0 else f'<span class="mv dn">▼ {-m}</span>' if m < 0 else '<span class="mv">—</span>'

    def row(k, size, why):
        rh, av, nm, wy, rk, nt, lab = size; t, p = T[k], P[k]
        return (f'<div class="row" style="--rh:{rh}px;--av:{av}px"><div class="rk" style="font-size:{rk}px">{t["rank"]}</div>'
                f'<div class="av"><img class="lgo" src="file://{logos / (k + ".png")}"></div><div class="mid">'
                f'<div class="nm" style="font-size:{nm}px">{E(N[k])} <span class="rec">{p["w"]}-{p["l"]}{("-" + str(p["t"])) if p["t"] else ""}</span> {badge(t["move"])}</div>'
                f'<div class="why" style="font-size:{wy}px">{E(why)}</div></div>'
                f'<div class="net"><b style="font-size:{nt}px">{sgn(t["net"])}</b>{"<i>net EPA/play</i>" if lab else ""}</div></div>')

    def check_why(k, why, kind, where):
        if not why:
            warn.append(f'{where}: no "why" for {k}')
        elif len(why) > LIMITS[kind]:
            warn.append(f'{where}: why for {k} is {len(why)} chars (limit {LIMITS[kind]} for {kind} rows)')

    foot = f'<div class="foot"><span><b>PlainStats</b> · plainstatsnfl.com/team-tiers</span><span>Net EPA/play, thru Week {thru}</span></div>'
    G = 'linear-gradient(to bottom,rgba(11,13,18,.05) 0%,rgba(11,13,18,.20) 25%,rgba(11,13,18,.62) 45%,rgba(11,13,18,.9) 70%,#0b0d12 100%)'

    def head(label, color, title, hook, tsz=76, hsz=29):
        return (f'<span class=tag style="--c:{color}">{label}</span><h1 style="font-size:{tsz}px;margin-top:12px">{title}</h1>'
                f'<div class=hook style="font-size:{hsz}px;margin:10px 0 18px">{hook}</div>')

    # ---- slide bodies per format: list of (slug, photo slot, dynamic shade?, shade css, body html)
    def bodies(fm):
        F = FORMATS[fm]; res = []
        c = C['cover']
        pills = ''.join(f'<span class=tag style="--c:#fff">{E(N[k].split()[-1])} #{T[k]["rank"]}</span>' for k in c['pills'])
        res.append(('cover', c['photo'], False,
                    'linear-gradient(to bottom,rgba(11,13,18,.10) 0%,rgba(11,13,18,.30) 38%,rgba(11,13,18,.80) 58%,rgba(11,13,18,.95) 78%,#0b0d12 100%)',
                    f'<div style="margin-bottom:20px"><div style="font-size:30px;color:#d3d7e2">{E(c["label"])}</div>'
                    f'<h1 style="font-size:{F["cover_px"]}px;letter-spacing:-3px;margin-top:14px">{E(c["line1"])}</h1>'
                    f'<h1 style="font-size:{F["cover_px"]}px;letter-spacing:-3px;margin-top:16px;color:{c.get("line2_color", "#00D1E6")}">{E(c["line2"])}</h1>'
                    f'<div style="display:flex;gap:14px;margin-top:30px;font-size:28px">{pills}</div>'
                    f'<div style="margin:30px 0 30px;font-size:30px;color:#d3d7e2">Swipe for every team, and why →</div></div>'))
        for s in C['slides']:
            if s['type'] == 'tier':
                t = s['tier']; teams = s.get('teams') or [k for k in order if T[k]['tier'] == t]
                kind = 'big' if len(teams) <= 5 else 'mid' if len(teams) <= 7 else 'tiny'
                gap = {'big': 10, 'mid': 8, 'tiny': 7}[kind]
                for k in teams: check_why(k, s['why'].get(k), kind, f'tier {t}')
                body = (head(f'Tier {t}', TCOL[t], s.get('title') or tier_names[t], s['hook']) + f'<div class=rows style="--gap:{gap}px">'
                        + ''.join(row(k, F[kind], s['why'].get(k, '')) for k in teams) + '</div>' + foot)
                res.append((f'tier{t}', s['photo'], True, G, body))
            elif s['type'] == 'movers':
                for k in s['up'] + s['down']: check_why(k, s['why'].get(k), 'movers', 'movers')
                sec = lambda col, txt: f'<div class=sec style="color:{col}">{txt}</div>'
                body = (head('Week %s movement' % thru, TCOL[1], s.get('title', 'Risers &amp; fallers'), s['hook'], 72, 28)
                        + sec(TCOL[1], '▲ Risers') + '<div class=rows style="--gap:8px">' + ''.join(row(k, F['movers'], s['why'].get(k, '')) for k in s['up']) + '</div>'
                        + sec(TCOL[5], '▼ Fallers') + '<div class=rows style="--gap:8px">' + ''.join(row(k, F['movers'], s['why'].get(k, '')) for k in s['down']) + '</div>'
                        + (f'<div style="font-size:22px;color:#c9cdd8;margin-top:14px;line-height:1.35">{E(s["also"])}</div>' if s.get('also') else '') + foot)
                res.append(('movers', s['photo'], True, G, body))
            elif s['type'] == 'cta':
                body = (f'<h1 style="font-size:{F["cta_px"]}px;letter-spacing:-3px">Tiers update<br>every Tuesday.</h1>'
                        '<div style="font-size:36px;margin-top:22px;color:#e3e6ee;line-height:1.3">Every team\'s offense, defense, pass and run splits in one filterable table, plus contracts and cap for all 32 teams.</div>'
                        '<div style="margin-top:34px;background:#0071e3;border-radius:30px;padding:30px 40px;font-size:44px;font-weight:800;align-self:flex-start">plainstatsnfl.com/team-tiers</div>'
                        '<div style="margin:34px 0 30px;font-size:21px;color:#9aa0ae;line-height:1.4">Source: nflverse play-by-play (CC BY 4.0), regular season through Week %s, garbage time included. '
                        'EPA = expected points added per pass or run play; lower is better on defense.</div>' % thru)
                res.append(('cta', s['photo'], False,
                            'linear-gradient(to bottom,rgba(11,13,18,.05) 0%,rgba(11,13,18,.3) 40%,rgba(11,13,18,.85) 62%,#0b0d12 100%)', body))
        return res

    def page(fm, i, total, slug, slot, shade, body):
        F = FORMATS[fm]
        css = (CSS.replace('@@FONTS@@', str(ROOT / 'assets' / 'fonts')).replace('@@W@@', str(F['w'])).replace('@@H@@', str(F['h']))
               .replace('@@PILL@@', str(F['pill_top'])).replace('@@DOTS@@', 'flex' if F['dots'] else 'none').replace('@@PAD@@', F['pad'])
               .replace('@@CREDB@@', str(F['credit_bottom'])).replace('@@CREDR@@', '64' if fm == 'ig' else '110'))
        f = photos_dir / (slot + '.jpg')
        if not f.exists():
            warn.append(f'photo file missing: {f}')
        size, pos = (C.get('crop', {}).get(slot, {}).get(fm) or ['cover', '50% 15%'])
        dots = ''.join(f'<i style="background:{"#f5f5f7" if j == i else "rgba(255,255,255,.35)"}"></i>' for j in range(1, total + 1))
        return (f'<html><head><meta charset=utf-8><style>{css}</style></head><body>'
                f'<div class=photo style="background-image:url(\'file://{f}\');background-size:{size};background-position:{pos}"></div>'
                f'<div class=shade style="background:{shade}"></div><div class=pill>PlainStats</div><div class=dots>{dots}</div>'
                f'<div class=credit>{E(credit(slot))}</div><div class=wrap>{body}</div></body></html>')

    from playwright.sync_api import sync_playwright
    chromium = os.environ.get('PLAYWRIGHT_CHROMIUM') or ('/opt/pw-browsers/chromium' if os.path.exists('/opt/pw-browsers/chromium') else None)
    formats = ['ig', 'tt'] if a.format == 'both' else [a.format]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium, args=['--no-sandbox']) if chromium else p.chromium.launch()
        for fm in formats:
            F = FORMATS[fm]; d = out / fm; d.mkdir(parents=True, exist_ok=True)
            for old in glob.glob(str(d / '*')): os.remove(old)
            sl = bodies(fm); pg = b.new_page(viewport={'width': F['w'], 'height': F['h']}); files = []
            for i, (slug, slot, dyn, shade, body) in enumerate(sl, 1):
                hp = d / f'{i:02d}_{slug}.html'; hp.write_text(page(fm, i, len(sl), slug, slot, shade, body))
                pg.goto('file://' + str(hp)); pg.wait_for_timeout(300)
                if dyn:   # fade the photo out from where the content starts, so the player stays visible above it
                    pg.evaluate("""()=>{const top=document.querySelector('.wrap > *').getBoundingClientRect().top;
                      document.querySelector('.shade').style.background=`linear-gradient(to bottom,rgba(11,13,18,.05) 0px,rgba(11,13,18,.22) ${Math.max(0,top-150)}px,rgba(11,13,18,.74) ${top+5}px,rgba(11,13,18,.92) ${top+200}px,#0b0d12 ${top+520}px)`}""")
                bad = pg.evaluate("""()=>[...document.querySelectorAll('.row')].filter(r=>{const rb=r.getBoundingClientRect();
                  return r.querySelector('.why').getBoundingClientRect().bottom>rb.bottom-2||r.querySelector('.nm').scrollWidth>r.querySelector('.mid').clientWidth+1}).length""")
                if bad: warn.append(f'{fm} {slug}: {bad} row(s) overflow; shorten the reasons')
                png = hp.with_suffix('.png'); pg.screenshot(path=str(png)); files.append(png); hp.unlink()
            from PIL import Image
            tw = 360; th = int(tw * F['h'] / F['w']); cols = 4; rows = (len(files) + cols - 1) // cols
            sheet = Image.new('RGB', (tw * cols, th * rows))
            for i, f in enumerate(files): sheet.paste(Image.open(f).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
            sheet.save(d / 'contact.png'); print(f'{fm}: {len(files)} slides -> {d}')
        b.close()
    for w in warn: print('WARNING:', w)
    if not warn: print('no warnings')


if __name__ == '__main__':
    main()
