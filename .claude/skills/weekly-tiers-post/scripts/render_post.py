"""Render a PlainStats social post from a content file: the weekly team-tiers carousel, or a player post.

  python3 -I render_post.py --content WORK/content.json --photos WORK/photos --out WORK/out
         [--format ig|tt|both] [--story] [--reel] [--tiers path/to/tiers.json]

Formats: ig = Instagram carousel 1080x1350; tt = 1080x1920 slides for TikTok photo posts, Instagram Reels and Stories (bottom
350 px and right 110 px kept clear for the app's caption and buttons). --story adds OUT/story/story.png: one 1080x1920
Instagram Story frame with a clear area for the link sticker (content.json "story"). --reel turns the tt slides into
OUT/reel/reel.mp4 (silent H.264, 1080x1920, 30 fps, crossfades; add a sound in the app). --reel implies tt.

Data comes from the repo root; only the words in content.json are hand-written:
- tier, movers rows: data/tiers.json, data/projections.json (records), data/espn_assets.json (names, logos). Ranks, tiers
  and net EPA are SCHEDULE-ADJUSTED (aNet / sosRank, data/build_tiers.py); a tiers.json without the adjustment renders raw
  numbers and prints a WARNING.
- player, players slides: data/plainscore.json (exported from src.html plainScore(); never computed here) and
  data/nfl.json (name, team, by gsis id). Pay shows only when plainscore.json carries a "pay" bar, which it does only for a
  confirmed contract (CLAUDE.md data rules); otherwise the slide says "Contract being verified".

Cover accent (cover.line2 colour): the featured team's colour from ACCENT, never a fixed brand blue. Order: cover.line2_color
if given, else ACCENT[cover.team], else ACCENT of the first team in cover.pills. Player and players slides use the same
accent for their tag, score and bars.

content.json:
{
  "url":  "plainstatsnfl.com/team-tiers",                      # page every slide footer and the end slide name
  "foot": "Schedule-adjusted net EPA/play · thru Week 10",     # optional right side of the footer
  "cover":  {"photo": "cover", "team": "JAX", "label": "...", "line1": "...", "line2": "...", "sub": "optional third line",
             "pills": ["JAX", "BUF", {"text": "Purdy 98"}], "swipe": "Swipe for every team, and why →"},
  "slides": [
    {"type": "tier", "tier": 1, "photo": "t1", "title": "Best in the league", "hook": "...", "why": {"JAX": "...", ...}},
    {"type": "movers", "photo": "mv", "title": "Risers & fallers", "hook": "...", "up": ["PIT", "CHI"], "down": ["SEA", "BAL"],
     "why": {"PIT": "..."}, "also": "Also up: ... Also down: ..."},
    {"type": "player", "photo": "p1", "gid": "00-0037834", "tag": "PlainScore", "title": "...", "hook": "...", "note": "..."},
    {"type": "players", "photo": "p2", "tag": "...", "title": "...", "hook": "...", "gids": ["00-...", ...],
     "star": "00-0037834", "pos": true, "why": {"00-...": "optional sub line"}},
    {"type": "cta", "photo": "cta", "title": "Tiers update<br>every Tuesday.", "text": "...", "source": "..."}
  ],
  "story": {"photo": "cover", "kicker": "...", "title": "...", "text": "...", "sticker": "Tap the link"},
  "crop": {"t1": {"ig": ["cover", "50% 0%"], "tt": ["auto 128%", "50% 100%"], "story": [...]}}   # optional per photo and format
}
Missing url/foot/cta text fall back to the team-tiers wording, so old tiers content files still render the same.
A tier slide lists every team of that tier (override with "teams": [...]). Rows with up to 5 teams get two-line reasons
(about 100 characters), 6 to 7 teams two shorter lines (about 100), 8 or more one line (about 48 characters).
"""
import argparse, glob, html, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
E = html.escape
TCOL = {1: '#34d399', 2: '#60a5fa', 3: '#a3a3b2', 4: '#fbbf24', 5: '#f87171'}

# One accent per team, picked from the team's colours and lightened where needed so it reads on the dark slide (#0b0d12).
ACCENT = {
    'ARI': '#E8475F', 'ATL': '#F0474F', 'BAL': '#9B7BE0', 'BUF': '#4C8DF6', 'CAR': '#2FB4E8', 'CHI': '#F26B2B',
    'CIN': '#FB4F14', 'CLE': '#FF6A2A', 'DAL': '#A9B4C2', 'DEN': '#FB6A2C', 'DET': '#3FA7E8', 'GB': '#FFB612',
    'HOU': '#E8475F', 'IND': '#5B8FE8', 'JAX': '#D7A22A', 'KC': '#F0384F', 'LAC': '#3DB6F2', 'LAR': '#FFD100',
    'LV': '#C4CBD3', 'MIA': '#22B8C4', 'MIN': '#FFC62F', 'NE': '#E8475F', 'NO': '#D3BC8D', 'NYG': '#5B8FE8',
    'NYJ': '#3DBE7A', 'PHI': '#3AA59B', 'PIT': '#FFB612', 'SEA': '#69BE28', 'SF': '#D4B26A', 'TB': '#F0474F',
    'TEN': '#4B92DB', 'WAS': '#FFB612',
}
POS = {'quarterbacks': 'QB', 'running backs': 'RB', 'wide receivers': 'WR', 'tight ends': 'TE', 'left tackles': 'LT',
       'left guards': 'LG', 'centers': 'C', 'right guards': 'RG', 'right tackles': 'RT', 'edge rushers': 'EDGE',
       'def. tackles': 'DT', 'linebackers': 'LB', 'cornerbacks': 'CB', 'safeties': 'S', 'kickers': 'K', 'punters': 'P'}

# row sizes: (row height, logo tile, name px, reason px, rank px, net px, show "net EPA/play" label)
FORMATS = {
    'ig': dict(w=1080, h=1350, pad='0 64px 52px 64px', pill_top=52, credit_bottom=20, dots=True,
               big=(116, 80, 32, 24, 42, 34, True), mid=(104, 70, 30, 23, 40, 32, False), tiny=(68, 50, 26, 22, 32, 28, False),
               movers=(112, 76, 31, 24, 42, 32, False), cover_px=96, cta_px=104),
    'tt': dict(w=1080, h=1920, pad='0 110px 350px 64px', pill_top=150, credit_bottom=296, dots=False,
               big=(132, 84, 34, 26, 44, 36, True), mid=(104, 70, 30, 24, 40, 32, False), tiny=(72, 52, 27, 23, 32, 28, False),
               movers=(126, 80, 32, 25, 42, 34, False), cover_px=92, cta_px=104),
}
# Instagram Story: top 250 px (progress bar, account name) and bottom 250 px (reply bar) stay clear; the link sticker goes
# in the empty band the frame leaves above the reply bar.
STORY = dict(w=1080, h=1920, pad='0 64px 250px 64px', pill_top=150, credit_bottom=200, dots=False)
LIMITS = {'big': 105, 'mid': 105, 'tiny': 50, 'movers': 90, 'players': 70}

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
.row.star{border:2px solid var(--a);background:rgba(12,15,21,.72)}
.rk{font-weight:800;width:46px;text-align:center;color:#9aa0ae;flex:none}
.av{flex:none;border-radius:26%;background:#f2f3f6;width:var(--av);height:var(--av);display:flex;align-items:center;justify-content:center}
.lgo{width:80%;height:80%;object-fit:contain}
.mid{flex:1;min-width:0}.nm{font-weight:800;display:flex;align-items:center;gap:10px;white-space:nowrap}
.rec{color:#aab0be;font-weight:600;font-size:.8em}.why{color:#d3d7e2;line-height:1.26;margin-top:3px}
.net{text-align:right;flex:none;width:100px}.net b{display:block;font-weight:800}.net i{font-style:normal;font-size:17px;color:#9aa0ae}
.mv{font-size:.62em;font-weight:800;padding:2px 10px;border-radius:99px;background:rgba(255,255,255,.12);color:#c9cdd8}
.mv.up{background:#10382a;color:#34d399}.mv.dn{background:#41181a;color:#f87171}
.foot{display:flex;justify-content:space-between;gap:20px;font-size:21px;color:#9aa0ae;margin-top:16px;margin-bottom:26px}.foot b{color:#f5f5f7;font-weight:800}
.sec{font-weight:800;font-size:26px;margin:14px 0 8px;display:flex;align-items:center;gap:10px}
.score{display:flex;align-items:center;gap:26px;margin:4px 0 22px}
.score .n{font-weight:800;font-size:150px;line-height:.9;letter-spacing:-6px;color:var(--a)}
.score .s{font-size:30px;color:#e3e6ee;line-height:1.3}.score .s b{display:block;font-size:40px;color:#f5f5f7;font-weight:800}
.bars{display:flex;flex-direction:column;gap:12px;background:rgba(12,15,21,.58);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.07);border-radius:24px;padding:24px 26px}
.bar{display:grid;grid-template-columns:290px 1fr 60px 200px;align-items:center;gap:16px;font-size:27px}
.bar .tr{height:16px;border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden}.bar .tr i{display:block;height:100%;border-radius:99px}
.bar b{font-weight:800;text-align:right}.bar span.v{color:#aab0be;text-align:right;white-space:nowrap}
.note{font-size:21px;color:#9aa0ae;line-height:1.4;margin-top:14px}
"""


def jl(f):
    return json.load(open(ROOT / 'data' / f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', required=True); ap.add_argument('--photos', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--format', default='both', choices=['ig', 'tt', 'both'])
    ap.add_argument('--story', action='store_true', help='also render OUT/story/story.png from content.json "story"')
    ap.add_argument('--reel', action='store_true', help='also make OUT/reel/reel.mp4 from the 1080x1920 slides (needs ffmpeg)')
    ap.add_argument('--sec', type=float, default=3.0, help='seconds per slide in the reel (default 3)')
    ap.add_argument('--tiers', help='tiers.json to use instead of data/tiers.json (e.g. a preview built with data/build_tiers.py ... <out>)')
    ap.add_argument('--logos', help='folder of <TEAM>.png logos (default: <out>/../logos, fetched when missing)')
    a = ap.parse_args()
    C = json.load(open(a.content)); photos_dir = Path(a.photos).resolve(); out = Path(a.out).resolve()
    meta = json.load(open(photos_dir / 'photos.json'))
    tiers = json.load(open(a.tiers)) if a.tiers else jl('tiers.json')
    P = jl('projections.json')['teams']; N = {k: v['name'] for k, v in jl('espn_assets.json')['teams'].items()}
    T = tiers['teams']; thru = tiers['thru']
    ADJ = bool(tiers.get('adjusted')); NETK = 'aNet' if ADJ else 'net'
    types = {s['type'] for s in C['slides']}
    TIERS_POST = bool(types & {'tier', 'movers'})
    if types & {'player', 'players'}:
        PS = jl('plainscore.json'); PSP = PS['players']
        PN = {r[19]: (r[0], r[1]) for r in jl('nfl.json')['players'] if len(r) > 19 and r[19]}
    logos = Path(a.logos).resolve() if a.logos else out.parent / 'logos'
    if len(list(logos.glob('*.png'))) < 32:
        os.makedirs(logos, exist_ok=True)
        subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('photos.py')), 'logos', '--dir', str(logos)], check=True, cwd=ROOT)
    tier_names = {t[0]: t[2] for t in tiers['tiers']}
    order = sorted(T, key=lambda k: T[k]['rank'])
    warn = []
    if TIERS_POST and not ADJ:
        warn.append('data/tiers.json has no schedule adjustment (no "adjusted" flag): slides show RAW net EPA. Rebuild it with data/build_tiers.py before publishing.')

    cov = C['cover']
    team_pills = [p for p in cov.get('pills', []) if isinstance(p, str)]
    accent_team = cov.get('team') or (team_pills[0] if team_pills else None)
    ACC = cov.get('line2_color') or ACCENT.get(accent_team)
    if not ACC:
        warn.append('cover: no "team" (or team pill) to take the accent colour from; using white. Set cover.team or cover.line2_color.')
        ACC = '#f5f5f7'
    URL = C.get('url', 'plainstatsnfl.com/team-tiers')
    FOOT_R = C.get('foot') or (f'{"Schedule-adjusted net EPA/play" if ADJ else "Net EPA/play"} · thru Week {thru}' if TIERS_POST
                              else f'PlainScore · thru Week {PS["week"]}')

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

    def logo(k):
        return f'<div class="av"><img class="lgo" src="file://{logos / (k + ".png")}"></div>'

    def row(k, size, why):
        rh, av, nm, wy, rk, nt, lab = size; t, p = T[k], P[k]
        sub = ('<i>sched #%d</i>' % t['sosRank'] if ADJ else '<i>net EPA/play</i>') if lab else ''   # strength-of-schedule rank, 1 = toughest
        return (f'<div class="row" style="--rh:{rh}px;--av:{av}px"><div class="rk" style="font-size:{rk}px">{t["rank"]}</div>'
                f'{logo(k)}<div class="mid">'
                f'<div class="nm" style="font-size:{nm}px">{E(N[k])} <span class="rec">{p["w"]}-{p["l"]}{("-" + str(p["t"])) if p["t"] else ""}</span> {badge(t["move"])}</div>'
                f'<div class="why" style="font-size:{wy}px">{E(why)}</div></div>'
                f'<div class="net"><b style="font-size:{nt}px">{sgn(t[NETK])}</b>{sub}</div></div>')

    def check_why(k, why, kind, where):
        if not why:
            warn.append(f'{where}: no "why" for {k}')
        elif len(why) > LIMITS[kind]:
            warn.append(f'{where}: why for {k} is {len(why)} chars (limit {LIMITS[kind]} for {kind} rows)')

    # ---- player helpers (all numbers from data/plainscore.json)
    def ps(gid, where):
        if gid not in PSP:
            sys.exit(f'{where}: {gid} has no PlainScore in data/plainscore.json (not qualified, or export is stale)')
        return PSP[gid]

    def pay(v):
        b = next((b for b in v['bars'] if b[3] == 'pay'), None)
        return b[2] if b else None

    def prow(gid, size, star, show_pos, why):
        rh, av, nm, wy, rk, nt, _ = size; v = ps(gid, 'players'); name, team = PN[gid]
        pos = POS.get(v['grp'], '')
        rank = f'#{v["rk"]}' + (f' {pos}' if show_pos else '')
        sub = why or ' · '.join(x for x in [f'#{v["rk"]} of {v["n"]} {v["grp"]}', pay(v) or 'Contract being verified'] if x)
        return (f'<div class="row{" star" if star else ""}" style="--rh:{rh}px;--av:{av}px;--a:{ACC}">'
                f'<div class="rk" style="font-size:{rk if not show_pos else rk - 12}px;width:{46 if not show_pos else 92}px;{"color:" + ACC if star else ""}">{E(rank)}</div>'
                f'{logo(team)}<div class="mid"><div class="nm" style="font-size:{nm}px">{E(name)} <span class="rec">{E(team)}</span></div>'
                f'<div class="why" style="font-size:{wy}px">{E(sub)}</div></div>'
                f'<div class="net"><b style="font-size:{nt + 6}px;{"color:" + ACC if star else ""}">{v["s"]}</b><i>PlainScore</i></div></div>')

    def foot():
        return f'<div class="foot"><span><b>PlainStats</b> · {E(URL)}</span><span>{E(FOOT_R)}</span></div>'

    G = 'linear-gradient(to bottom,rgba(11,13,18,.05) 0%,rgba(11,13,18,.20) 25%,rgba(11,13,18,.62) 45%,rgba(11,13,18,.9) 70%,#0b0d12 100%)'

    def head(label, color, title, hook, tsz=76, hsz=29):
        return (f'<span class=tag style="--c:{color}">{label}</span><h1 style="font-size:{tsz}px;margin-top:12px">{title}</h1>'
                f'<div class=hook style="font-size:{hsz}px;margin:10px 0 18px">{hook}</div>')

    def pill(p):
        return (f'<span class=tag style="--c:#fff">{E(N[p].split()[-1])} #{T[p]["rank"]}</span>' if isinstance(p, str)
                else f'<span class=tag style="--c:#fff">{E(p["text"])}</span>')

    # ---- slide bodies per format: list of (slug, photo slot, dynamic shade?, shade css, body html)
    def bodies(fm):
        F = FORMATS[fm]; res = []
        c = cov
        res.append(('cover', c['photo'], False,
                    'linear-gradient(to bottom,rgba(11,13,18,.10) 0%,rgba(11,13,18,.30) 38%,rgba(11,13,18,.80) 58%,rgba(11,13,18,.95) 78%,#0b0d12 100%)',
                    f'<div style="margin-bottom:20px"><div style="font-size:30px;color:#d3d7e2">{E(c["label"])}</div>'
                    f'<h1 style="font-size:{F["cover_px"]}px;letter-spacing:-3px;margin-top:14px">{E(c["line1"])}</h1>'
                    f'<h1 style="font-size:{F["cover_px"]}px;letter-spacing:-3px;margin-top:16px;color:{ACC}">{E(c["line2"])}</h1>'
                    + (f'<div style="font-size:40px;font-weight:800;margin-top:20px;color:#e3e6ee">{E(c["sub"])}</div>' if c.get('sub') else '')
                    + (f'<div style="display:flex;gap:14px;margin-top:30px;font-size:28px">{"".join(pill(p) for p in c["pills"])}</div>' if c.get('pills') else '')
                    + f'<div style="margin:30px 0 30px;font-size:30px;color:#d3d7e2">{E(c.get("swipe", "Swipe for every team, and why →"))}</div></div>'))
        for s in C['slides']:
            if s['type'] == 'tier':
                t = s['tier']; teams = s.get('teams') or [k for k in order if T[k]['tier'] == t]
                kind = 'big' if len(teams) <= 5 else 'mid' if len(teams) <= 7 else 'tiny'
                gap = {'big': 10, 'mid': 8, 'tiny': 7}[kind]
                for k in teams: check_why(k, s['why'].get(k), kind, f'tier {t}')
                body = (head(f'Tier {t}', TCOL[t], s.get('title') or tier_names[t], s['hook']) + f'<div class=rows style="--gap:{gap}px">'
                        + ''.join(row(k, F[kind], s['why'].get(k, '')) for k in teams) + '</div>' + foot())
                res.append((f'tier{t}', s['photo'], True, G, body))
            elif s['type'] == 'movers':
                for k in s['up'] + s['down']: check_why(k, s['why'].get(k), 'movers', 'movers')
                sec = lambda col, txt: f'<div class=sec style="color:{col}">{txt}</div>'
                body = (head('Week %s movement' % thru, TCOL[1], s.get('title', 'Risers &amp; fallers'), s['hook'], 72, 28)
                        + sec(TCOL[1], '▲ Risers') + '<div class=rows style="--gap:8px">' + ''.join(row(k, F['movers'], s['why'].get(k, '')) for k in s['up']) + '</div>'
                        + sec(TCOL[5], '▼ Fallers') + '<div class=rows style="--gap:8px">' + ''.join(row(k, F['movers'], s['why'].get(k, '')) for k in s['down']) + '</div>'
                        + (f'<div style="font-size:22px;color:#c9cdd8;margin-top:14px;line-height:1.35">{E(s["also"])}</div>' if s.get('also') else '') + foot())
                res.append(('movers', s['photo'], True, G, body))
            elif s['type'] == 'player':
                v = ps(s['gid'], 'player'); name, team = PN[s['gid']]
                bars = ''.join(
                    f'<div class=bar><span>{E(b[0])}</span><span class=tr><i style="width:{b[1]}%;background:{"#9aa0ae" if b[3] == "pay" else ACC}"></i></span>'
                    f'<b>{b[1]}</b><span class=v>{E(b[2])}</span></div>' for b in v['bars'])
                verdict = 'first' if v['rk'] == 1 else 'last' if v['rk'] == v['n'] else f'#{v["rk"]}'
                body = (head(E(s.get('tag', 'PlainScore')), ACC, E(s.get('title', name)), E(s.get('hook', '')), 76, 29)
                        + f'<div class=score style="--a:{ACC}"><div class=n>{v["s"]}</div><div class=s><b>{E(name)}</b>'
                          f'Ranks {verdict} of {v["n"]} qualified {E(v["grp"])}<br>{E(team)} · thru Week {PS["week"]}</div></div>'
                        + f'<div class=bars>{bars}</div>'
                        + f'<div class=note>{E(s.get("note") or "Percentile among qualified " + v["grp"] + " (0 to 100). " + ("Pay is against his position; higher = paid more." if pay(v) else "Contract being verified, so no pay bar."))}</div>'
                        + foot())
                res.append((s.get('slug', 'player'), s['photo'], True, G, body))
            elif s['type'] == 'players':
                gids = s['gids']; size = F['movers'] if len(gids) <= 5 else F['mid']
                for gd in gids:
                    w = s.get('why', {}).get(gd)
                    if w and len(w) > LIMITS['players']:
                        warn.append(f'players: why for {gd} is {len(w)} chars (limit {LIMITS["players"]})')
                body = (head(E(s.get('tag', 'PlainScore')), ACC, E(s['title']), E(s.get('hook', '')), 72, 28)
                        + '<div class=rows style="--gap:9px">'
                        + ''.join(prow(gd, size, gd == s.get('star'), s.get('pos', False), s.get('why', {}).get(gd)) for gd in gids)
                        + '</div>' + (f'<div class=note>{E(s["note"])}</div>' if s.get('note') else '') + foot())
                res.append((s.get('slug', 'players'), s['photo'], True, G, body))
            elif s['type'] == 'cta':
                title = s.get('title', 'Tiers update<br>every Tuesday.')
                text = s.get('text', 'Every team\'s offense, defense, pass and run splits in one filterable table, plus contracts and cap for all 32 teams.')
                src = s.get('source') or ('Source: nflverse play-by-play (CC BY 4.0), regular season through Week %s, garbage time included. '
                                          'EPA = expected points added per pass or run play; lower is better on defense. %s' % (
                                              thru, 'Ranks use net EPA adjusted for the opponents each team has played; sched = strength of schedule so far (1 = toughest).' if ADJ else ''))
                body = (f'<h1 style="font-size:{F["cta_px"]}px;letter-spacing:-3px">{title}</h1>'
                        f'<div style="font-size:36px;margin-top:22px;color:#e3e6ee;line-height:1.3">{E(text)}</div>'
                        f'<div style="margin-top:34px;background:#0071e3;border-radius:30px;padding:30px 40px;font-size:{44 if len(URL) <= 30 else 38}px;font-weight:800;align-self:flex-start">{E(URL)}</div>'
                        f'<div style="margin:34px 0 30px;font-size:21px;color:#9aa0ae;line-height:1.4">{E(src)}</div>')
                res.append(('cta', s['photo'], False,
                            'linear-gradient(to bottom,rgba(11,13,18,.05) 0%,rgba(11,13,18,.3) 40%,rgba(11,13,18,.85) 62%,#0b0d12 100%)', body))
        return res

    def story_body():
        s = C['story']
        return ('story', s['photo'], False,
                'linear-gradient(to bottom,rgba(11,13,18,.05) 0%,rgba(11,13,18,.25) 30%,rgba(11,13,18,.85) 52%,#0b0d12 72%)',
                f'<div style="font-size:30px;color:#d3d7e2">{E(s.get("kicker", ""))}</div>'
                f'<h1 style="font-size:96px;letter-spacing:-3px;margin-top:14px">{E(s["title"])}</h1>'
                + (f'<h1 style="font-size:96px;letter-spacing:-3px;margin-top:12px;color:{ACC}">{E(s["line2"])}</h1>' if s.get('line2') else '')
                + f'<div style="font-size:34px;margin-top:22px;color:#e3e6ee;line-height:1.3">{E(s.get("text", ""))}</div>'
                f'<div style="margin-top:40px;font-size:34px;font-weight:800;color:{ACC}">{E(s.get("sticker", "Tap the link"))} ↓</div>'
                # empty band for the link sticker, above the reply bar
                f'<div style="height:300px"></div>'
                f'<div style="font-size:22px;color:#9aa0ae;margin-bottom:16px"><b style="color:#f5f5f7">PlainStats</b> · {E(URL)}</div>')

    def page(fm, i, total, slug, slot, shade, body):
        F = STORY if fm == 'story' else FORMATS[fm]
        css = (CSS.replace('@@FONTS@@', str(ROOT / 'assets' / 'fonts')).replace('@@W@@', str(F['w'])).replace('@@H@@', str(F['h']))
               .replace('@@PILL@@', str(F['pill_top'])).replace('@@DOTS@@', 'flex' if F['dots'] else 'none').replace('@@PAD@@', F['pad'])
               .replace('@@CREDB@@', str(F['credit_bottom'])).replace('@@CREDR@@', '64' if fm in ('ig', 'story') else '110'))
        f = photos_dir / (slot + '.jpg')
        if not f.exists():
            warn.append(f'photo file missing: {f}')
        crop = C.get('crop', {}).get(slot, {})
        size, pos = (crop.get(fm) or (crop.get('tt') if fm == 'story' else None) or ['cover', '50% 15%'])
        dots = ''.join(f'<i style="background:{"#f5f5f7" if j == i else "rgba(255,255,255,.35)"}"></i>' for j in range(1, total + 1))
        return (f'<html><head><meta charset=utf-8><style>{css}</style></head><body>'
                f'<div class=photo style="background-image:url(\'file://{f}\');background-size:{size};background-position:{pos}"></div>'
                f'<div class=shade style="background:{shade}"></div><div class=pill>PlainStats</div><div class=dots>{dots}</div>'
                f'<div class=credit>{E(credit(slot))}</div><div class=wrap>{body}</div></body></html>')

    def shoot(pg, fm, d, i, total, slug, slot, dyn, shade, body):
        hp = d / f'{i:02d}_{slug}.html'; hp.write_text(page(fm, i, total, slug, slot, shade, body))
        pg.goto('file://' + str(hp)); pg.wait_for_timeout(300)
        if dyn:   # fade the photo out from where the content starts, so the player stays visible above it
            pg.evaluate("""()=>{const top=document.querySelector('.wrap > *').getBoundingClientRect().top;
              document.querySelector('.shade').style.background=`linear-gradient(to bottom,rgba(11,13,18,.05) 0px,rgba(11,13,18,.22) ${Math.max(0,top-150)}px,rgba(11,13,18,.74) ${top+5}px,rgba(11,13,18,.92) ${top+200}px,#0b0d12 ${top+520}px)`}""")
        bad = pg.evaluate("""()=>[...document.querySelectorAll('.row')].filter(r=>{const rb=r.getBoundingClientRect();
          return r.querySelector('.why').getBoundingClientRect().bottom>rb.bottom-2||r.querySelector('.nm').scrollWidth>r.querySelector('.mid').clientWidth+1}).length""")
        if bad: warn.append(f'{fm} {slug}: {bad} row(s) overflow; shorten the reasons')
        top = pg.evaluate("()=>{const e=document.querySelector('.wrap > *');return e?e.getBoundingClientRect().top:999}")
        if top < (FORMATS[fm]['pill_top'] + 60 if fm in FORMATS else 250):
            warn.append(f'{fm} {slug}: content runs into the top bar ({int(top)} px from the top); cut words')
        png = hp.with_suffix('.png'); pg.screenshot(path=str(png)); hp.unlink()
        return png

    from playwright.sync_api import sync_playwright
    from PIL import Image
    chromium = os.environ.get('PLAYWRIGHT_CHROMIUM') or ('/opt/pw-browsers/chromium' if os.path.exists('/opt/pw-browsers/chromium') else None)
    formats = ['ig', 'tt'] if a.format == 'both' else [a.format]
    if a.reel and 'tt' not in formats:
        formats.append('tt')
    tt_files = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium, args=['--no-sandbox']) if chromium else p.chromium.launch()
        for fm in formats:
            F = FORMATS[fm]; d = out / fm; d.mkdir(parents=True, exist_ok=True)
            for old in glob.glob(str(d / '*')): os.remove(old)
            sl = bodies(fm); pg = b.new_page(viewport={'width': F['w'], 'height': F['h']}); files = []
            for i, (slug, slot, dyn, shade, body) in enumerate(sl, 1):
                files.append(shoot(pg, fm, d, i, len(sl), slug, slot, dyn, shade, body))
            if fm == 'tt':
                tt_files = files
            tw = 360; th = int(tw * F['h'] / F['w']); cols = 4; rows = (len(files) + cols - 1) // cols
            sheet = Image.new('RGB', (tw * cols, th * rows))
            for i, f in enumerate(files): sheet.paste(Image.open(f).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
            sheet.save(d / 'contact.png'); print(f'{fm}: {len(files)} slides -> {d}')
        if a.story:
            if 'story' not in C:
                warn.append('--story given but content.json has no "story"')
            else:
                d = out / 'story'; d.mkdir(parents=True, exist_ok=True)
                pg = b.new_page(viewport={'width': STORY['w'], 'height': STORY['h']})
                slug, slot, dyn, shade, body = story_body()
                png = shoot(pg, 'story', d, 1, 1, slug, slot, dyn, shade, body)
                png.rename(d / 'story.png'); print(f'story: {d / "story.png"}')
        b.close()

    if a.reel:
        ff = shutil.which('ffmpeg')
        if not ff:
            warn.append('--reel: ffmpeg not found, no reel made')
        else:
            d = out / 'reel'; d.mkdir(parents=True, exist_ok=True)
            n, sec, xf = len(tt_files), a.sec, 0.5
            cmd = [ff, '-y', '-loglevel', 'error']
            for f in tt_files:
                cmd += ['-loop', '1', '-t', str(sec + xf), '-i', str(f)]
            # crossfade chain: [0][1]xfade -> [v1], [v1][2]xfade -> [v2] ...
            fl, last = [], '0:v'
            for i in range(1, n):
                o = f'v{i}'
                fl.append(f'[{last}][{i}:v]xfade=transition=fade:duration={xf}:offset={i * sec:.2f}[{o}]'); last = o
            fl.append(f'[{last}]format=yuv420p,fps=30[out]')
            cmd += ['-filter_complex', ';'.join(fl), '-map', '[out]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                    '-movflags', '+faststart', str(d / 'reel.mp4')]
            subprocess.run(cmd, check=True)
            print(f'reel: {d / "reel.mp4"} ({n} slides, about {n * sec + xf:.0f} s, silent)')

    for w in warn: print('WARNING:', w)
    if not warn: print('no warnings')


if __name__ == '__main__':
    main()
