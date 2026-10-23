#!/usr/bin/env python3
"""Builds the crawlable PlainStats pages that search engines index.

Run:  python3 -I tools/build_seo.py        (from anywhere; paths are relative to this file)

Writes plain static HTML (no JavaScript, inline CSS, system fonts) into
  players/<name>.html            /players/patrick-mahomes
  teams/<team>/index.html        /teams/chiefs
  teams/<team>/cap.html          /teams/chiefs/cap
  teams/<team>/dead-money.html   /teams/chiefs/dead-money
  draft/<name>.html              /draft/jeremiah-smith
  players/index.html, teams/index.html, draft/index.html   (hub pages that link to everything)
and rewrites sitemap.xml. vercel.json has cleanUrls on, so the .html is dropped from the address.
It also writes og-data/<kind>.json (players, teams, draft, pages): the text behind each page's social card. Every page's og:image is
/api/og?k=<kind>&s=<slug>&v=<asOf>, which api/og.js draws on demand (the sandbox can't reach ESPN's image CDN, Vercel can).

Data rules (CLAUDE.md) are enforced here, not just in the page:
  * A contract figure appears only if the player's `ver` letters in data/nfl.json confirm it
    (t total, a yearly average, g guarantees, f fully guaranteed, e final season, c 2026 cap hit, b signing bonus).
  * Players with no confirmed or calculated contract say "Contract being verified". No guessing.
  * Reported deals name their source and link to it. Calculated deals say PlainStats calculated them.
  * Every page's JSON-LD (Person / SportsTeam / FAQPage / BreadcrumbList) repeats only text that is visible on the page.

Re-run after every data refresh (build.sh does it too), then commit the generated folders and sitemap.xml.
"""
import csv, datetime as dt, html, json, pathlib, re, shutil, unicodedata, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SITE = 'https://www.plainstatsnfl.com'
EMAIL = 'info@plainstatsnfl.com'
# The hosted fix form lives in src.html (const FIX_FORM = '...'); empty means the pages fall back to a mailto link.
_ff = re.search(r"const FIX_FORM = '([^']*)'", (ROOT / 'src.html').read_text(encoding='utf-8'))
FIX_FORM = _ff.group(1) if _ff else ''

FIX_ATTR = ' target="_blank" rel="noopener"' if FIX_FORM else ''

def fix_href(path):
    if FIX_FORM:
        return html.escape(FIX_FORM.replace('{page}', urllib.parse.quote(SITE + path, safe='')).replace('{about}', urllib.parse.quote(path, safe='')).replace('{kind}', ''), quote=True)
    return f'mailto:{EMAIL}?subject=Suggest%20a%20fix%3A%20{html.escape(path)}'

NFL = json.loads((DATA / 'nfl.json').read_text())
SEASON = json.loads((DATA / 'season.json').read_text())
HIST = json.loads((DATA / 'history.json').read_text())
DRAFT = json.loads((DATA / 'draft.json').read_text())
ASSETS = json.loads((DATA / 'espn_assets.json').read_text())
FA = json.loads((DATA / 'freeagency.json').read_text())
LEDGER = {}
with open(DATA / 'ledger.csv', newline='') as fh:
    for row in csv.DictReader(fh):
        LEDGER[(row['name'], row['team'])] = row

ASOF = NFL['asOf']
CAP = NFL['cap']
SEASON_YEAR = NFL['season']
SOURCES = NFL['sources']

# ---------------------------------------------------------------- social cards (Open Graph)
# Every page points og:image at /api/og?k=<kind>&s=<slug>&v=<asOf>. api/og.js looks the slug up in og-data/<kind>.json,
# written at the end of main(), and draws the card (face or logo, name, one key number). The card text comes only from
# this script, so it follows the same data rules as the page: a contract figure shows only when `ver` confirms it.
# Team colors are read from the page itself (src.html COLORS) so the cards never drift from the site.
_m = re.search(r"const COLORS = \{([^}]*)\}", (ROOT / 'src.html').read_text(encoding='utf-8'))
TEAM_COLOR = dict(re.findall(r"(\w+): '(#[0-9A-Fa-f]{6})'", _m.group(1))) if _m else {}
OG = {'players': {}, 'teams': {}, 'draft': {}, 'pages': {}}
OG_BRAND = '#0D47A1'


def og_url(kind, slug):
    return f"{SITE}/api/og?k={kind}&s={slug}&v={ASOF}"


def og_add(kind, slug, **card):
    """Store one card (empty fields dropped to keep the files small) and return its image URL."""
    OG[kind][slug] = {k: v for k, v in card.items() if v not in (None, '')}
    return og_url(kind, slug)


POSNAME = {'QB': 'quarterback', 'RB': 'running back', 'FB': 'fullback', 'WR': 'wide receiver', 'TE': 'tight end',
           'LT': 'left tackle', 'LG': 'left guard', 'C': 'center', 'RG': 'right guard', 'RT': 'right tackle',
           'IDL': 'interior defensive lineman', 'EDGE': 'edge rusher', 'LB': 'linebacker', 'CB': 'cornerback',
           'S': 'safety', 'K': 'kicker', 'P': 'punter', 'LS': 'long snapper'}
CLASSNAME = {'FR': 'freshman', 'SO': 'sophomore', 'JR': 'junior', 'SR': 'senior', 'GR': 'graduate'}
GRPNAME = {'QB': 'quarterback', 'RB': 'running back', 'WR': 'wide receiver', 'TE': 'tight end', 'OT': 'offensive tackle',
           'IOL': 'interior offensive lineman', 'EDGE': 'edge rusher', 'DT': 'defensive tackle', 'LB': 'linebacker',
           'CB': 'cornerback', 'S': 'safety'}


def slugify(s):
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[.'’]", '', s)
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def esc(s):
    return html.escape(str(s), quote=True)


def mon(n, d=1):
    if n is None:
        return None
    a = abs(n)
    s = '-' if n < 0 else ''
    if a >= 1e9:
        return f'{s}${a / 1e9:.2f}B'
    if a >= 1e6:
        return f'{s}${a / 1e6:.{d}f}M'
    if a >= 1e3:
        return f'{s}${round(a / 1e3)}K'
    return f'{s}${round(a)}'


def ordn(n):
    if 10 <= n % 100 <= 20:
        return f'{n}th'
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def clip(s, n):
    s = ' '.join(s.split())
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(' ', 1)[0].rstrip(',;:')
    return cut + '…'


# ---------------------------------------------------------------- teams
TEAMS = {}
for t in NFL['teams']:
    full = ASSETS['teams'].get(t['id'], {}).get('name') or f"{t['city']} {t['name']}"
    TEAMS[t['id']] = dict(t, full=full, slug=slugify(t['name']), logo=ASSETS['teams'].get(t['id'], {}).get('logo'))
by_space = sorted(TEAMS.values(), key=lambda t: -t['space'])
by_dead = sorted(TEAMS.values(), key=lambda t: -t['dead'])
for i, t in enumerate(by_space):
    t['r_space'] = i + 1
for i, t in enumerate(by_dead):
    t['r_dead'] = i + 1

# ---------------------------------------------------------------- players
HISTBY = {p['id']: p for p in HIST['players']}


def headshot(name, team):
    return ASSETS['players'].get(team + '|' + re.sub(r'[^a-z]', '', name.lower()))


class Pl:
    pass


PLAYERS = []
for i, r in enumerate(NFL['players']):
    p = Pl()
    (p.name, p.team, p.pos, p.age, p.total, p.apy, p.gtd, p.fg, p.end, p.voidy, p.cap, p.base, p.bonus,
     p.dpre, p.dpost, p.prov, p.srcI, p.ver, p.sb, p.gid) = r
    p.ver = p.ver or ''
    p.hist = HISTBY.get(p.gid)
    p.s26 = (p.hist or {}).get('s', {}).get(str(SEASON_YEAR))
    PLAYERS.append(p)

# Which players get a page. Substantive only: a reported deal, a rookie-scale deal above the minimum,
# or any 2026 stats. The rest are minimum-salary or unverified players with nothing to say yet.
def substantive(p):
    if p.prov == 'r':
        return True
    if p.s26 and p.s26.get('g'):
        return True
    if p.prov == 'f' and (p.cap or 0) > 1_000_000:
        return True
    return False


PAGES = [p for p in PLAYERS if substantive(p)]
seen = {}
for p in PAGES:
    seen.setdefault(slugify(p.name), []).append(p)
for sl, group in seen.items():
    for p in group:
        p.slug = sl if len(group) == 1 else f'{sl}-{p.pos.lower()}'
slug_seen = {}
for p in PAGES:
    if p.slug in slug_seen:  # same name and position: add the team
        p.slug += '-' + p.team.lower()
        slug_seen[p.slug] = p
    slug_seen[p.slug] = p


def ok(p, letter):
    return letter in p.ver


def contract_facts(p):
    """Confirmed contract fields only. Returns dict of confirmed values (None when not confirmed)."""
    f = dict(total=None, apy=None, gtd=None, fg=None, end=None, cap=None, sb=None, years=None)
    if p.prov == 'u':
        return f
    if ok(p, 't'):
        f['total'] = p.total
    if ok(p, 'a'):
        f['apy'] = p.apy
    if p.prov in ('r', 'f'):
        if ok(p, 'g'):
            f['gtd'] = p.gtd
        if ok(p, 'f'):
            f['fg'] = p.fg
    if ok(p, 'e'):
        f['end'] = p.end
    if ok(p, 'c'):
        f['cap'] = p.cap
    if p.prov == 'r' and ok(p, 'b') and p.sb:
        f['sb'] = p.sb
    led = LEDGER.get((p.name, p.team))
    if p.prov == 'r' and led and led.get('years'):
        try:
            f['years'] = int(led['years'])
        except ValueError:
            pass
    return f


def stat_lines(s):
    """Plain-English stat bullets from a nflverse season dict. Only keys that are present."""
    out = []
    g = lambda k: s.get(k)
    if g('att') is not None and g('cmp') is not None:
        out.append(('Passing', f"{g('cmp')} of {g('att')} for {g('pyd', ) or 0:,} yards" + (f", {pl(g('ptd'), 'touchdown')}" if g('ptd') else '') + (f", {pl(g('int'), 'interception')}" if g('int') else '')))
    if g('car'):
        out.append(('Rushing', f"{pl(g('car'), 'carry').replace('carrys', 'carries')} for {g('ryd') or 0:,} yards" + (f", {pl(g('rtd'), 'touchdown')}" if g('rtd') else '')))
    if g('rec') is not None and (g('rec') or g('tgt')):
        out.append(('Receiving', f"{g('rec')} {'catch' if g('rec') == 1 else 'catches'}" + (f" on {pl(g('tgt'), 'target')}" if g('tgt') else '') + f" for {g('reyd') or 0:,} yards" + (f", {pl(g('retd'), 'touchdown')}" if g('retd') else '')))
    d = []
    if g('tk'):
        d.append(pl(g('tk'), 'tackle'))
    if g('tfl'):
        d.append(pl(g('tfl'), 'tackle') + ' for loss')
    if g('dsk'):
        d.append(pl(g('dsk'), 'sack'))
    if g('qbh'):
        d.append(pl(g('qbh'), 'QB hit'))
    if g('pd'):
        d.append(f"{g('pd')} {'pass' if g('pd') == 1 else 'passes'} defended")
    if g('dint'):
        d.append(pl(g('dint'), 'interception'))
    if g('ff'):
        d.append(pl(g('ff'), 'forced fumble'))
    if d:
        out.append(('Defense', ', '.join(d)))
    if g('fga'):
        out.append(('Kicking', f"{g('fgm') or 0} of {g('fga')} field goals" + (f", {g('xpm') or 0} of {g('xpa')} extra points" if g('xpa') else '')))
    if g('pun'):
        out.append(('Punting', f"{g('pun')} punts for {g('puy') or 0:,} yards"))
    return out


def article(word):
    w = word.lower()
    return 'an' if w[:1] in 'aeiou' or re.match(r'(8|11|18)(\D|$)', w) else 'a'


def poss(name):
    return name + ("'" if name.endswith('s') else "'s")


def pl(n, word):
    """1 touchdown, 2 touchdowns."""
    return f"{n:g} {word}" if n == 1 else f"{n:g} {word}s"


def player_summary(p, f):
    T = TEAMS[p.team]
    role = POSNAME.get(p.pos, p.pos)
    intro = f"{p.name} is {article(role)} {role} for the {T['full']}"
    if p.prov == 'u' or not (f['total'] or f['apy'] or f['cap']):
        return intro + '. PlainStats shows a contract only once a named report confirms it, so this contract is being verified.'
    deal = ''
    if f['years'] and f['total']:
        deal = f"{f['years']}-year, {mon(f['total'])} contract"
    elif f['total']:
        deal = f"{mon(f['total'])} contract"
    elif f['apy']:
        deal = f"contract worth {mon(f['apy'])} a year"
    out = intro
    if deal:
        out += f", with {article(deal)} {deal}"
        if f['end']:
            out += f" that runs through {f['end']}"
        if f['apy'] and f['total']:
            out += f", averaging {mon(f['apy'])} a year"
        out += '.'
    else:
        out += '.'
    if f['gtd'] and f['total']:
        out += f" {mon(f['gtd'])} of it is guaranteed."
    if f['cap']:
        out += f" His {SEASON_YEAR} cap hit is {mon(f['cap'])}."
    if p.prov == 'f':
        out += ' PlainStats calculated these figures from the draft slot and the CBA rookie scale.'
    elif p.prov == 'm':
        out += ' PlainStats calculated this from the CBA league-minimum salary.'
    elif p.prov == 'p':
        out += ' This is practice squad pay set by the CBA.'
    return out


def player_faq(p, f):
    T = TEAMS[p.team]
    n = p.name
    q = []
    unver = 'PlainStats shows contract figures only after a named report confirms them, and this one is still being verified.'
    calc = ' PlainStats calculated this from the CBA rookie scale.' if p.prov == 'f' else ''
    if f['total'] or f['apy']:
        a = f"{n} has a {mon(f['total'])} contract" if f['total'] else f"{n} earns about {mon(f['apy'])} a year"
        if f['apy'] and f['total']:
            a += f", which averages {mon(f['apy'])} a year"
        a += '.' + calc
        q.append((f'How much does {n} make?', a))
    else:
        q.append((f'How much does {n} make?', f"{unver}"))
    if f['end'] or f['years']:
        a = f"{poss(n)} contract"
        if f['years']:
            a += f" is {f['years']} year{'' if f['years'] == 1 else 's'}"
            a += f" and runs through {f['end']}." if f['end'] else '.'
        else:
            a += f" runs through the {f['end']} season."
        q.append((f"How long is {poss(n)} contract?", a))
    if f['gtd'] is not None and f['total']:
        a = f"{mon(f['gtd'])} of the {mon(f['total'])} is guaranteed."
        if f['fg']:
            a += f" {mon(f['fg'])} was fully guaranteed at signing."
        if p.prov == 'f':
            a += ' These are PlainStats calculations.'
        q.append((f"How much of {poss(n)} contract is guaranteed?", a))
    if f['cap']:
        q.append((f"What is {poss(n)} {SEASON_YEAR} cap hit?", f"{n} counts {mon(f['cap'])} against the {T['name']}' {SEASON_YEAR} cap."))
    q.append((f'What team does {n} play for?', f"{n} plays {POSNAME.get(p.pos, p.pos)} for the {T['full']}."))
    return q


def headline_stat(p):
    """One season number for the card when no contract figure is confirmed. (value, label) or None. Only keys that are present."""
    s = p.s26 or {}
    if not s.get('g'):
        return None
    pick = {'QB': ('pyd', 'passing yards'), 'RB': ('ryd', 'rushing yards'), 'FB': ('ryd', 'rushing yards'), 'WR': ('reyd', 'receiving yards'),
            'TE': ('reyd', 'receiving yards'), 'EDGE': ('dsk', 'sacks'), 'IDL': ('dsk', 'sacks'), 'LB': ('tk', 'tackles'), 'CB': ('tk', 'tackles'),
            'S': ('tk', 'tackles'), 'K': ('fgm', 'field goals made'), 'P': ('pun', 'punts')}.get(p.pos)
    if pick and s.get(pick[0]):
        v = s[pick[0]]
        return (f'{v:,}' if isinstance(v, int) else f'{v:g}'), pick[1]
    return str(s['g']), ('game played' if s['g'] == 1 else 'games played')


def player_card(p, f, T, has_deal):
    """Card text for a player page. Contract numbers come from contract_facts() only, so unconfirmed deals never appear."""
    card = dict(m='face', c=TEAM_COLOR.get(p.team, OG_BRAND), i=headshot(p.name, p.team), g=T.get('logo'), t=p.name,
                s=f"{p.pos} · {T['full']}", e='NFL contract explained')
    if f['apy']:
        card.update(n=mon(f['apy']), l='per year')
        if f['total'] and f['end']:
            card['x'] = f"{mon(f['total'])} total through {f['end']}"
        elif f['total']:
            card['x'] = f"{mon(f['total'])} total"
        elif f['cap']:
            card['x'] = f"{SEASON_YEAR} cap hit {mon(f['cap'])}"
    elif f['total']:
        card.update(n=mon(f['total']), l='total contract', x=(f"Runs through {f['end']}" if f['end'] else None))
    elif f['cap']:
        card.update(n=mon(f['cap']), l=f'{SEASON_YEAR} cap hit')
    else:
        # No confirmed contract: lead with a real season number and say the contract is still being verified.
        st = headline_stat(p)
        if st:
            card.update(n=st[0], l=f'{st[1]} in {SEASON_YEAR}', x='Contract being verified')
        else:
            card.update(n='Contract being verified')
    return card


# ---------------------------------------------------------------- html shell
CSS =""":root{color-scheme:light dark;--bg:#f5f5f7;--sf:#fff;--fg:#1d1d1f;--mu:#636368;--ln:#e1e1e6;--br:#0071e3;--lk:#0066cc;--bs:#e8f1fc}
@media(prefers-color-scheme:dark){:root{--bg:#000;--sf:#161617;--fg:#f5f5f7;--mu:#a1a1a6;--ln:#2c2c2f;--br:#2997ff;--lk:#2997ff;--bs:#0c2541}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif;-webkit-text-size-adjust:100%}
a{color:var(--lk)}header.top{background:var(--sf);border-bottom:1px solid var(--ln)}
header.top div{max-width:760px;margin:0 auto;padding:12px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header.top a.logo{font-weight:700;color:var(--fg);text-decoration:none;margin-right:auto;letter-spacing:-.01em}
header.top a{font-size:.9rem;text-decoration:none}
main{max-width:760px;margin:0 auto;padding:20px 16px 40px}
nav.crumbs{font-size:.85rem;color:var(--mu);margin-bottom:12px}nav.crumbs a{color:var(--mu)}
h1{font-size:1.9rem;line-height:1.15;letter-spacing:-.02em;margin:.2em 0 .4em}h2{font-size:1.2rem;letter-spacing:-.01em;margin:1.6em 0 .5em}h3{font-size:1rem;margin:1em 0 .2em}
.lede{font-size:1.08rem;margin:0 0 1em}.id{display:flex;gap:14px;align-items:center;margin-bottom:6px}.id img{border-radius:12px;background:var(--ln);object-fit:cover}
.card{background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:6px 16px;margin:12px 0}
.card dl{margin:0}.card dl>div{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--ln)}.card dl>div:last-child{border:0}
.card dt{color:var(--mu)}.card dd{margin:0;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:.92rem;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--ln)}td.r,th.r{text-align:right}
.scroll{overflow-x:auto}.note{color:var(--mu);font-size:.85rem}.cta{display:inline-block;background:var(--br);color:#fff;padding:10px 18px;border-radius:999px;text-decoration:none;font-weight:600;margin:8px 0}
.faq h3{margin-top:1.1em}.faq p{margin:.2em 0}.chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}.chips a{display:block;background:var(--sf);border:1px solid var(--ln);border-radius:999px;padding:6px 12px;text-decoration:none;font-size:.9rem}
ul.list{columns:2 220px;list-style:none;padding:0;margin:0}ul.list li{padding:3px 0;break-inside:avoid}
@media(max-width:480px){h1{font-size:1.5rem}.id img{width:56px;height:56px}}
footer{max-width:760px;margin:0 auto;padding:16px;color:var(--mu);font-size:.85rem;border-top:1px solid var(--ln)}footer a{color:var(--mu)}"""


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + '</script>'


def faq_ld(faq):
    return {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]}


def crumbs_ld(items):
    return {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + u} for i, (n, u) in enumerate(items)]}


def shell(path, title, desc, body, graph, robots=None, image=None, crumbs=(), card=None):
    canon = SITE + path
    img = card or image or SITE + '/og-image.png'
    # A generated card is always 1200x630; say so (and describe it) so X, Discord and iMessage render it without a resize pass.
    alt = esc(clip(title.replace(' | PlainStats', ''), 110) + ' (PlainStats)')
    img_meta = (f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{alt}">'
                f'<meta name="twitter:image:alt" content="{alt}">') if card else ''
    crumb_html = ''
    if crumbs:
        crumb_html = '<nav class="crumbs" aria-label="Breadcrumb">' + ' › '.join(
            f'<a href="{esc(u)}">{esc(n)}</a>' for n, u in crumbs[:-1]) + (' › ' if len(crumbs) > 1 else '') + esc(crumbs[-1][0]) + '</nav>'
    meta_robots = f'<meta name="robots" content="{robots}">' if robots else ''
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">{meta_robots}<meta property="og:type" content="article"><meta property="og:site_name" content="PlainStats"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{canon}"><meta property="og:image" content="{esc(img)}">{img_meta}<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{esc(img)}"><meta name="theme-color" content="#f5f5f7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)"><link rel="icon" href="/icon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="apple-touch-icon" href="/icon-180.png"><link rel="manifest" href="/manifest.json"><link rel="preconnect" href="https://a.espncdn.com"><style>{CSS}</style>{ld({'@context': 'https://schema.org', '@graph': graph})}</head><body><header class="top"><div><a class="logo" href="/">PlainStats</a><a href="/teams">Teams</a><a href="/players">Players</a><a href="/draft">Draft</a></div></header><main>{crumb_html}{body}</main><footer><p>PlainStats explains NFL contracts and stats in plain English. Contract figures come from named reports or are calculated from the CBA, and anything unconfirmed says so. Data as of {esc(ASOF)}. Spot a mistake? <a href="{fix_href(path)}"{FIX_ATTR}>Suggest a fix</a>.</p><p><a href="/">Open PlainStats</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p></footer></body></html>"""


def faq_html(faq):
    return '<section class="faq"><h2>Quick answers</h2>' + ''.join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in faq) + '</section>'


def facts_html(rows):
    rows = [(k, v) for k, v in rows if v not in (None, '')]
    if not rows:
        return ''
    return '<div class="card"><dl>' + ''.join(f'<div><dt>{esc(k)}</dt><dd>{v}</dd></div>' for k, v in rows) + '</dl></div>'


def write(rel, text):
    out = ROOT / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')


def player_name_link(p):
    return f'<a href="/players/{p.slug}">{esc(p.name)}</a>'


PAGE_BY_TEAM = {}
for p in PAGES:
    PAGE_BY_TEAM.setdefault(p.team, []).append(p)

# ---------------------------------------------------------------- player pages
URLS = []  # (path, priority, changefreq)


def build_player(p):
    T = TEAMS[p.team]
    f = contract_facts(p)
    summary = player_summary(p, f)
    faq = player_faq(p, f)
    path = f'/players/{p.slug}'
    has_deal = bool(f['total'] or f['apy'] or f['cap'])
    if f['total'] and f['end']:
        title = f"{p.name} contract explained: {mon(f['total'])} through {f['end']}"
    elif f['total']:
        title = f"{p.name} contract explained: {mon(f['total'])} deal"
    elif f['cap']:
        title = f"{p.name} contract explained: {mon(f['cap'])} cap hit in 2026"
    else:
        title = f"{p.name} contract and 2026 stats explained"
    if len(title) <= 50:
        title += ' | PlainStats'
    desc = summary if len(summary) + 26 > 158 else summary + ' Plain-English breakdown.'
    desc = clip(desc, 158)

    src_html = ''
    if p.prov == 'r' and p.srcI >= 0 and p.srcI < len(SOURCES):
        sname, surl = SOURCES[p.srcI]
        src_html = f'<p class="note">Source: <a href="{esc(surl)}" rel="nofollow noopener">{esc(sname)}</a>, a named report. Figures PlainStats has not confirmed are left out.</p>'
    elif p.prov == 'f':
        src_html = '<p class="note">Calculated by PlainStats from the draft slot and the CBA rookie scale (not a reported figure).</p>'
    elif p.prov == 'm':
        src_html = '<p class="note">Calculated by PlainStats from the CBA league-minimum salary table.</p>'
    elif p.prov == 'p':
        src_html = '<p class="note">Practice squad pay set by the CBA.</p>'

    rows = [('Position', esc(POSNAME.get(p.pos, p.pos)).capitalize()), ('Team', f'<a href="/teams/{T["slug"]}">{esc(T["full"])}</a>')]
    if p.age:
        rows.append(('Age', esc(p.age)))
    if has_deal:
        if f['years']:
            rows.append(('Contract length', f"{f['years']} year{'' if f['years'] == 1 else 's'}"))
        rows += [('Total value', mon(f['total'])), ('Average per year', mon(f['apy'])), ('Guaranteed', mon(f['gtd'])),
                 ('Fully guaranteed at signing', mon(f['fg'])), ('Signing bonus', mon(f['sb'])),
                 ('Runs through', f['end']), (f'{SEASON_YEAR} cap hit', mon(f['cap']))]
    else:
        rows.append(('Contract', 'Contract being verified'))

    stats_html = ''
    if p.s26 and p.s26.get('g'):
        lines = stat_lines(p.s26)
        line_html = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in lines)
        stats_html = f'<h2>{SEASON_YEAR} stats</h2><div class="card"><dl><div><dt>Games</dt><dd>{p.s26["g"]}</dd></div>{line_html}</dl></div><p class="note">Regular season through week {HIST.get("thru")}. Source: nflverse.</p>'

    img = headshot(p.name, p.team)
    img_html = f'<img src="{esc(img)}" alt="{esc(p.name)}" width="72" height="72" loading="lazy" decoding="async" onerror="this.remove()">' if img else ''
    spa = f'/#p-{slugify(p.name)}-{p.team.lower()}'
    body = (f'<div class="id">{img_html}<div><h1>{esc(poss(p.name))} contract explained</h1></div></div>'
            f'<p class="lede">{esc(summary)}</p>{facts_html(rows)}{src_html}{stats_html}'
            f'{faq_html(faq)}'
            f'<p><a class="cta" href="{esc(spa)}">See {esc(p.name)} in the PlainStats app</a></p>'
            f'<h2>More on the {esc(T["name"])}</h2><ul class="chips"><li><a href="/teams/{T["slug"]}">{esc(T["full"])} roster and contracts</a></li><li><a href="/teams/{T["slug"]}/cap">How much cap space do the {esc(T["name"])} have?</a></li><li><a href="/teams/{T["slug"]}/dead-money">{esc(T["name"])} dead money</a></li></ul>')
    person = {'@type': 'Person', 'name': p.name, 'jobTitle': f"{POSNAME.get(p.pos, p.pos).capitalize()}, NFL",
              'url': SITE + path, 'memberOf': {'@type': 'SportsTeam', 'name': T['full'], 'sport': 'American football', 'url': f'{SITE}/teams/{T["slug"]}'}}
    if img:
        person['image'] = img
    graph = [person, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': ASOF, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}, 'about': {'@type': 'Person', 'name': p.name}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Players', '/players'), (p.name, path)])]
    crumbs = [('PlainStats', '/'), ('Players', '/players'), (p.name, path)]
    thin = not has_deal
    card = og_add('players', p.slug, **player_card(p, f, T, has_deal))
    write(f'players{"/" + p.slug}.html', shell(path, title, desc, body, graph, robots='noindex,follow' if thin else None, image=img, crumbs=crumbs, card=card))
    if not thin:
        URLS.append((path, '0.7' if p.prov == 'r' else '0.5', 'weekly'))


# ---------------------------------------------------------------- team pages
def team_reported_deals(team_id, n=8):
    """Deals confirmed by a named report, biggest yearly average first. Rookie and minimum deals are not ranked here."""
    rows = []
    for p in PLAYERS:
        if p.team == team_id and p.prov == 'r':
            f = contract_facts(p)
            if f['total'] or f['apy']:
                rows.append((p, f))
    rows.sort(key=lambda x: -(x[1]['apy'] or 0))
    return rows[:n]


def reported_table(rows, heading):
    if not rows:
        return ''
    tr = ''.join(f'<tr><td>{player_name_link(p) if hasattr(p, "slug") else esc(p.name)}</td><td>{esc(p.pos)}</td><td class="r">{mon(f["total"]) or "–"}</td><td class="r">{mon(f["apy"]) or "–"}</td></tr>' for p, f in rows)
    return (f'<h2>{heading}</h2><div class="card scroll"><table><thead><tr><th>Player</th><th>Pos</th><th class="r">Total</th><th class="r">Per year</th></tr></thead><tbody>{tr}</tbody></table></div>'
            '<p class="note">Only deals confirmed by a named report are listed. Contracts still being verified are left out, so this is not the full cap table.</p>')


def record_line(t):
    s = SEASON['teams'].get(t['id'])
    if not s:
        return None
    rec = f"{s['w']}-{s['l']}" + (f"-{s['t']}" if s.get('t') else '')
    return rec, s


def build_team(t):
    tid = t['id']
    slug = t['slug']
    full = t['full']
    nick = t['name']
    rec = record_line(t)
    top = team_reported_deals(tid)
    roster = sorted(PAGE_BY_TEAM.get(tid, []), key=lambda p: (-(contract_facts(p)['cap'] or 0), p.name))
    space_txt = mon(t['space'])
    rank_txt = ordn(t['r_space'])
    bits = [f"The {full} have about {space_txt} of {SEASON_YEAR} salary cap space, {rank_txt} most of 32 teams, as of {ASOF}."]
    if t['dead'] is not None:
        bits.append(f"They carry {mon(t['dead'])} in dead money, {ordn(t['r_dead'])} most in the league.")
    if rec:
        bits.append(f"This season they are {rec[0]}" + (f" under head coach {rec[1]['coach']}." if rec[1].get('coach') else '.'))
    summary = ' '.join(bits)
    # Team cards: logo on the team color, one big number. Overview and cap pages lead with cap space, dead-money page with dead money.
    sub = t['div'] + (f" · {rec[0]}" if rec else '')
    og_base = dict(m='logo', c=TEAM_COLOR.get(tid, OG_BRAND), i=t.get('logo'), t=full, s=sub)
    card_space = dict(og_base, e='Team cap space', n=space_txt, l=f'of cap space · {rank_txt} most in the NFL', x=f"Dead money {mon(t['dead'])}")
    card_dead = dict(og_base, e='Team dead money', n=mon(t['dead']), l=f"in dead money · {ordn(t['r_dead'])} most in the NFL", x=f'Cap space {space_txt}')

    # --- overview page
    faq = [
        (f'How much cap space do the {nick} have?', f"The {full} have about {space_txt} of {SEASON_YEAR} cap space as of {ASOF}, {rank_txt} most among the 32 teams. The league cap is {mon(CAP)}."),
        (f'How much dead money do the {nick} have?', f"The {nick} carry about {mon(t['dead'])} in dead money this season, {ordn(t['r_dead'])} most in the NFL. Dead money is cap space used by players a team already cut or traded."),
        (f'Who is the {nick} head coach?', f"{rec[1]['coach']} is the {nick} head coach, in the job since {rec[1]['since']}.") if rec and rec[1].get('coach') else None,
    ]
    faq = [x for x in faq if x]
    top_html = reported_table(top, f'{esc(nick)} contracts confirmed by named reports')
    roster_html = ''
    if roster:
        roster_html = f'<h2>{esc(nick)} players on PlainStats</h2><ul class="list">' + ''.join(f'<li>{player_name_link(p)} <span class="note">{esc(p.pos)}</span></li>' for p in roster) + '</ul>'
    facts = [(f'{SEASON_YEAR} cap space', space_txt), ('Dead money', mon(t['dead'])), ('League cap', mon(CAP)), ('Division', esc(t['div']))]
    if rec:
        facts.insert(0, ('Record', esc(rec[0])))
        if rec[1].get('coach'):
            facts.append(('Head coach', esc(rec[1]['coach'])))
    logo = f'<img src="{esc(t["logo"])}" alt="{esc(full)} logo" width="64" height="64" loading="lazy" decoding="async" onerror="this.remove()">' if t.get('logo') else ''
    path = f'/teams/{slug}'
    title = f"{full}: cap space, contracts and roster | PlainStats"
    desc = clip(summary, 158)
    body = (f'<div class="id">{logo}<h1>{esc(full)} cap space, contracts and roster</h1></div><p class="lede">{esc(summary)}</p>{facts_html(facts)}'
            f'<ul class="chips"><li><a href="/teams/{slug}/cap">How much cap space do the {esc(nick)} have?</a></li><li><a href="/teams/{slug}/dead-money">{esc(nick)} dead money</a></li><li><a href="/#team-{tid}">Open the {esc(nick)} page in the app</a></li></ul>'
            f'{top_html}{faq_html(faq)}{roster_html}'
            f'<p class="note">Team cap figures are PlainStats\' latest team totals as of {esc(ASOF)}. Player contracts are being re-sourced one by one from named reports, so team totals can change.</p>')
    team_ld = {'@type': 'SportsTeam', 'name': full, 'sport': 'American football', 'url': SITE + path, 'memberOf': {'@type': 'SportsOrganization', 'name': 'National Football League'}}
    if t.get('logo'):
        team_ld['logo'] = t['logo']
    if rec and rec[1].get('coach'):
        team_ld['coach'] = {'@type': 'Person', 'name': rec[1]['coach']}
    graph = [team_ld, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': ASOF, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', '/teams'), (full, path)])]
    write(f'teams/{slug}/index.html', shell(path, title, desc, body, graph, image=t.get('logo'), crumbs=[('PlainStats', '/'), ('Teams', '/teams'), (full, path)], card=og_add('teams', slug, **card_space)))
    URLS.append((path, '0.8', 'daily'))

    # --- cap space page
    path = f'/teams/{slug}/cap'
    title = f"How much cap space do the {nick} have? {space_txt} in {SEASON_YEAR} | PlainStats"
    answer = f"The {full} have about {space_txt} of cap space for the {SEASON_YEAR} season, {rank_txt} most among the 32 NFL teams, as of {ASOF}."
    desc = clip(answer + f" The league cap is {mon(CAP)}. See what is eating it.", 158)
    faq = [
        (f'How much cap space do the {nick} have?', answer),
        (f'What is the {SEASON_YEAR} NFL salary cap?', f"The {SEASON_YEAR} NFL salary cap is {mon(CAP)} per team."),
        (f'What is cap space?', 'Cap space is the room a team has left under the salary cap after counting every contract on its books, including dead money from players who already left.'),
        (f'How much of the {nick} cap is dead money?', f"About {mon(t['dead'])} of the {nick}' cap is dead money, which is {t['dead'] / CAP * 100:.1f}% of the league cap."),
    ]
    proj = FA.get('capByYear', {})
    facts = [('Cap space now', space_txt), ('Rank in the NFL', f"{rank_txt} most of 32"), ('League cap', mon(CAP)), ('Dead money', mon(t['dead'])),
             ('Offense contracts', mon(t['off'])), ('Defense contracts', mon(t['defn'])), ('Special teams contracts', mon(t['st'])), ('Injured reserve', mon(t['ir']))]
    top2 = reported_table(top, f'{esc(nick)} contracts confirmed by named reports')
    body = (f'<h1>How much cap space do the {esc(nick)} have?</h1><p class="lede">{esc(answer)}</p>{facts_html(facts)}'
            f'<p class="note">Team totals are PlainStats\' latest figures as of {esc(ASOF)}; individual contracts are being re-sourced from named reports, so these can shift.</p>{top2}{faq_html(faq)}'
            f'<ul class="chips"><li><a href="/teams/{slug}">{esc(full)} overview</a></li><li><a href="/teams/{slug}/dead-money">{esc(nick)} dead money</a></li><li><a href="/#team-{tid}">Open in the app</a></li></ul>')
    graph = [{'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': ASOF, 'about': {'@type': 'SportsTeam', 'name': full, 'sport': 'American football'}, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Cap space', path)])]
    write(f'teams/{slug}/cap.html', shell(path, title, desc, body, graph, image=t.get('logo'), crumbs=[('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Cap space', path)], card=og_add('teams', f'{slug}-cap', **card_space)))
    URLS.append((path, '0.8', 'daily'))

    # --- dead money page
    path = f'/teams/{slug}/dead-money'
    title = f"{nick} dead money: {mon(t['dead'])} on the {SEASON_YEAR} cap | PlainStats"
    answer = f"The {full} have about {mon(t['dead'])} in dead money in {SEASON_YEAR}, {ordn(t['r_dead'])} most in the NFL, as of {ASOF}."
    desc = clip(answer + ' Dead money is cap space used by players a team cut or traded.', 158)
    dead_rows = ''.join(f'<tr><td>{esc(n)}</td><td class="r">{mon(v)}</td></tr>' for n, v in (t.get('topDead') or []))
    dead_tbl = f'<h2>Who the {esc(nick)} are still paying</h2><div class="card scroll"><table><thead><tr><th>Player</th><th class="r">Dead money</th></tr></thead><tbody>{dead_rows}</tbody></table></div>' if dead_rows else ''
    faq = [
        (f'How much dead money do the {nick} have?', answer),
        ('What is dead money in the NFL?', 'Dead money is cap space used by players a team cut or traded. It is mostly bonus money that had not been counted yet when the player left.'),
        (f'Why do the {nick} have dead money?', f"Dead money builds up when a team releases or trades a player before his contract ends. The {nick} still owe bonus money and guaranteed salary tied to the players listed here."),
    ]
    body = (f'<h1>{esc(nick)} dead money</h1><p class="lede">{esc(answer)}</p>'
            f'{facts_html([("Dead money", mon(t["dead"])), ("Rank in the NFL", ordn(t["r_dead"]) + " most of 32"), ("Share of the cap", f"{t['dead'] / CAP * 100:.1f}%")])}'
            f'{dead_tbl}<p class="note">The five biggest dead-money charges are PlainStats\' latest team figures as of {esc(ASOF)} and can change as contracts are re-sourced.</p>{faq_html(faq)}'
            f'<ul class="chips"><li><a href="/teams/{slug}">{esc(full)} overview</a></li><li><a href="/teams/{slug}/cap">How much cap space do the {esc(nick)} have?</a></li><li><a href="/#team-{tid}">Open in the app</a></li></ul>')
    graph = [{'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': ASOF, 'about': {'@type': 'SportsTeam', 'name': full, 'sport': 'American football'}, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Dead money', path)])]
    write(f'teams/{slug}/dead-money.html', shell(path, title, desc, body, graph, image=t.get('logo'), crumbs=[('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Dead money', path)], card=og_add('teams', f'{slug}-dead-money', **card_dead)))
    URLS.append((path, '0.7', 'daily'))


# ---------------------------------------------------------------- draft pages
SCHOOLS = DRAFT['schools']
BOARDS = {b['id']: b for b in DRAFT['boards']}
PROS = DRAFT['prospects']
for pr in PROS:
    pr['slug'] = slugify(pr['name'])
_sl = {}
for pr in PROS:
    if pr['slug'] in _sl:
        pr['slug'] += '-' + pr['sch'].lower()
    _sl[pr['slug']] = pr


def college_stats(st):
    out = []
    g = st.get
    if g('pa'):
        out.append(('Passing', f"{g('pc', 0)} of {g('pa')} for {g('py', 0):,} yards, {pl(g('ptd', 0), 'touchdown')}, {pl(g('pint', 0), 'interception')}"))
    if g('ra'):
        out.append(('Rushing', f"{g('ra')} {'carry' if g('ra') == 1 else 'carries'} for {g('ry', 0):,} yards, {pl(g('rtd', 0), 'touchdown')}"))
    if g('rec'):
        out.append(('Receiving', f"{g('rec')} {'catch' if g('rec') == 1 else 'catches'} for {g('rey', 0):,} yards, {pl(g('retd', 0), 'touchdown')}"))
    d = []
    for k, one, many in (('tk', 'tackle', 'tackles'), ('tfl', 'tackle for loss', 'tackles for loss'), ('sk', 'sack', 'sacks'), ('qbh', 'QB hurry', 'QB hurries'), ('int', 'interception', 'interceptions'), ('pbu', 'pass breakup', 'pass breakups'), ('ff', 'forced fumble', 'forced fumbles')):
        if g(k):
            d.append(f"{g(k):g} {one if g(k) == 1 else many}")
    if d:
        out.append(('Defense', ', '.join(d)))
    return out


def build_prospect(pr):
    school = SCHOOLS.get(pr['sch'], [pr['sch']])[0]
    role = GRPNAME.get(pr['grp'], pr['grp'])
    cls = CLASSNAME.get(pr.get('cls'), '')
    path = f'/draft/{pr["slug"]}'
    ranks = []
    if pr.get('w'):
        ranks.append(f"No. {pr['w']} on the WalterFootball big board")
    if pr.get('b'):
        ranks.append(f"No. {pr['b']} on the NFL Draft Buzz big board")
    lead = f"{cls} {role}".strip()
    summary = f"{pr['name']} is {article(lead)} {lead} at {school} in the 2027 NFL Draft class" + (f", ranked {' and '.join(ranks)}." if ranks else '.')
    title = f"{pr['name']} 2027 NFL Draft profile: stats and big board rank | PlainStats"
    desc = clip(summary + ' College stats, size and where he fits.', 158)
    faq = []
    if ranks:
        faq.append((f"Where is {pr['name']} ranked in the 2027 NFL Draft?", f"{pr['name']} is {' and '.join(ranks)}. Boards update through the season."))
    faq.append((f"What position does {pr['name']} play?", f"{pr['name']} plays {role} at {school}."))
    st = college_stats(pr.get('st') or {})
    if st:
        faq.append((f"What are {poss(pr['name'])} 2026 college stats?", ' '.join(f'{k}: {v}.' for k, v in st)))
    facts = [('Position', esc(role).capitalize()), ('School', esc(school)), ('Class', esc(pr.get('cls'))), ('Height', esc(pr.get('ht'))),
             ('Weight', f"{pr['wt']} lb" if pr.get('wt') else None),
             ('WalterFootball rank', f"{pr['w']}" if pr.get('w') else None), ('NFL Draft Buzz rank', f"{pr['b']}" if pr.get('b') else None),
             ('Draft Buzz average rank', f"{pr['a']:g}" if pr.get('a') else None)]
    stat_html = ''
    if st:
        stat_html = f'<h2>2026 college stats</h2><div class="card"><dl>' + ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in st) + f'</dl></div><p class="note">Through {esc(DRAFT.get("statsThru"))}. Source: cfbstats.com.</p>'
    img = f'https://a.espncdn.com/i/headshots/college-football/players/full/{pr["espn"]}.png' if pr.get('espn') else None
    img_html = f'<img src="{esc(img)}" alt="{esc(pr["name"])}" width="72" height="72" loading="lazy" decoding="async" onerror="this.remove()">' if img else ''
    body = (f'<div class="id">{img_html}<h1>{esc(pr["name"])}: 2027 NFL Draft profile</h1></div><p class="lede">{esc(summary)}</p>{facts_html(facts)}{stat_html}{faq_html(faq)}'
            f'<p class="note">Ranks are from WalterFootball (updated {esc(BOARDS.get("w", {}).get("updated", ""))}) and NFL Draft Buzz (updated {esc(BOARDS.get("b", {}).get("updated", ""))}).</p>'
            f'<p><a class="cta" href="/#d-{esc(pr["id"])}">See {esc(pr["name"])} in the PlainStats app</a></p><p><a href="/draft">All 2027 draft prospects</a></p>')
    person = {'@type': 'Person', 'name': pr['name'], 'jobTitle': f'College {role}', 'alumniOf': {'@type': 'CollegeOrUniversity', 'name': school}, 'url': SITE + path}
    if img:
        person['image'] = img
    graph = [person, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': DRAFT.get('asOf', ASOF), 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Draft', '/draft'), (pr['name'], path)])]
    # Card: college headshot on the school color, school logo in the corner, big board rank as the key number.
    sch = SCHOOLS.get(pr['sch'], [pr['sch']])
    sch_color = sch[1] if len(sch) > 1 and re.fullmatch(r'#[0-9A-Fa-f]{6}', str(sch[1])) else OG_BRAND
    sch_logo = f'https://a.espncdn.com/i/teamlogos/ncaa/500/{sch[3]}.png' if len(sch) > 3 and sch[3] else None
    card = dict(m='face', c=sch_color, i=img, g=sch_logo, t=pr['name'], s=f"{pr['grp']} · {school}", e='2027 NFL Draft prospect')
    if pr.get('b'):
        card.update(n=f"#{pr['b']}", l='on the NFL Draft Buzz big board', x=(f"#{pr['w']} on WalterFootball" if pr.get('w') else None))
    elif pr.get('w'):
        card.update(n=f"#{pr['w']}", l='on the WalterFootball big board')
    else:
        card.update(n='2027 class', l='NFL Draft prospect')
    write(f'draft/{pr["slug"]}.html', shell(path, title, desc, body, graph, image=img, crumbs=[('PlainStats', '/'), ('Draft', '/draft'), (pr['name'], path)], card=og_add('draft', pr['slug'], **card)))
    URLS.append((path, '0.5', 'weekly'))


# ---------------------------------------------------------------- hubs
def build_hubs():
    # teams hub
    path = '/teams'
    title = 'NFL team cap space, contracts and dead money | PlainStats'
    desc = 'Cap space, dead money and contracts for all 32 NFL teams, explained in plain English.'
    rows = ''.join(f'<tr><td><a href="/teams/{t["slug"]}">{esc(t["full"])}</a></td><td class="r">{mon(t["space"])}</td><td class="r">{mon(t["dead"])}</td><td><a href="/teams/{t["slug"]}/cap">cap</a> · <a href="/teams/{t["slug"]}/dead-money">dead money</a></td></tr>' for t in sorted(TEAMS.values(), key=lambda t: t['full']))
    faq = [('How much cap space does each NFL team have?', f"Each team's cap space is listed here as of {ASOF}. The {SEASON_YEAR} league cap is {mon(CAP)}."), ('Which NFL team has the most cap space?', f"The {by_space[0]['full']} have the most cap space at about {mon(by_space[0]['space'])}, as of {ASOF}.")]
    body = (f'<h1>NFL teams: cap space and dead money</h1><p class="lede">All 32 teams, as of {esc(ASOF)}. Tap a team for its roster, cap space and dead money.</p>'
            f'<div class="card scroll"><table><thead><tr><th>Team</th><th class="r">Cap space</th><th class="r">Dead money</th><th>More</th></tr></thead><tbody>{rows}</tbody></table></div>{faq_html(faq)}')
    graph = [{'@type': 'CollectionPage', 'name': title, 'url': SITE + path, 'description': desc, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}}, faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', path)])]
    card = og_add('pages', 'teams', m='brand', c=OG_BRAND, e='PlainStats', t='All 32 NFL teams', s='Cap space and dead money', n=mon(CAP, 0), l=f'{SEASON_YEAR} salary cap per team',
                  x='Explained in plain English')
    write('teams/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Teams', path)], card=card))
    URLS.append((path, '0.9', 'daily'))

    # players hub
    path = '/players'
    title = 'NFL player contracts explained in plain English | PlainStats'
    desc = f'Contracts, cap hits and {SEASON_YEAR} stats for NFL players, explained in plain English, by team.'
    blocks = ''
    for t in sorted(TEAMS.values(), key=lambda t: t['full']):
        ps = sorted(PAGE_BY_TEAM.get(t['id'], []), key=lambda p: p.name)
        if ps:
            blocks += f'<h2><a href="/teams/{t["slug"]}">{esc(t["full"])}</a></h2><ul class="list">' + ''.join(f'<li>{player_name_link(p)} <span class="note">{esc(p.pos)}</span></li>' for p in ps) + '</ul>'
    body = f'<h1>NFL player contracts explained</h1><p class="lede">{len(PAGES)} players with a confirmed contract or {SEASON_YEAR} stats, grouped by team. Contracts still being verified are not shown until a named report confirms them.</p>{blocks}'
    graph = [{'@type': 'CollectionPage', 'name': title, 'url': SITE + path, 'description': desc, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}}, crumbs_ld([('PlainStats', '/'), ('Players', path)])]
    card = og_add('pages', 'players', m='brand', c=OG_BRAND, e='PlainStats', t='NFL player contracts', s='Explained in plain English', n=f'{len(PAGES):,}', l=f'players with a contract or {SEASON_YEAR} stats',
                  x='Browse every team')
    write('players/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Players', path)], card=card))
    URLS.append((path, '0.9', 'daily'))

    # draft hub
    path = '/draft'
    title = '2027 NFL Draft prospects: big board, stats and profiles | PlainStats'
    desc = f"{len(PROS)} 2027 NFL Draft prospects with college stats, size and big board ranks from WalterFootball and NFL Draft Buzz."
    order = sorted(PROS, key=lambda p: (p.get('a') or 999, p.get('b') or 999, p['name']))
    rows = ''.join(f'<tr><td><a href="/draft/{p["slug"]}">{esc(p["name"])}</a></td><td>{esc(p["grp"])}</td><td>{esc(SCHOOLS.get(p["sch"], [p["sch"]])[0])}</td><td class="r">{p.get("w") or "–"}</td><td class="r">{p.get("b") or "–"}</td></tr>' for p in order)
    faq = [('Who is the top prospect in the 2027 NFL Draft?', f"{order[0]['name']}, a {GRPNAME.get(order[0]['grp'], order[0]['grp'])} at {SCHOOLS.get(order[0]['sch'], [order[0]['sch']])[0]}, has the best average rank on the NFL Draft Buzz board as of {DRAFT.get('asOf')}."),
           ('When is the 2027 NFL Draft?', f"The 2027 NFL Draft is {DRAFT['draft']['dates']} in {DRAFT['draft']['place']}.")]
    body = (f'<h1>2027 NFL Draft prospects</h1><p class="lede">Sorted by NFL Draft Buzz average rank. Board ranks from WalterFootball and NFL Draft Buzz; college stats from cfbstats.com.</p>'
            f'<div class="card scroll"><table><thead><tr><th>Prospect</th><th>Pos</th><th>School</th><th class="r">WF</th><th class="r">Buzz</th></tr></thead><tbody>{rows}</tbody></table></div>{faq_html(faq)}')
    graph = [{'@type': 'CollectionPage', 'name': title, 'url': SITE + path, 'description': desc, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}}, faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Draft', path)])]
    card = og_add('pages', 'draft', m='brand', c=OG_BRAND, e='PlainStats', t='2027 NFL Draft', s='Big board, stats and profiles', n=f'{len(PROS):,}', l='prospects in the 2027 class',
                  x='WalterFootball and NFL Draft Buzz ranks')
    write('draft/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Draft', path)], card=card))
    URLS.append((path, '0.8', 'daily'))


def build_nav():
    teams = ''.join(f'<a href="/teams/{t["slug"]}">{esc(t["full"])}</a> ' for t in sorted(TEAMS.values(), key=lambda t: t['full']))
    (ROOT / 'tools' / 'seo-nav.html').write_text(
        '<nav aria-label="Browse PlainStats" style="max-width:1100px;margin:0 auto;padding:8px 20px 48px;color:var(--muted);font:.85rem/2 var(--body)">'
        '<strong style="color:var(--fg)">Browse:</strong> <a href="/teams">All teams</a> <a href="/players">Players</a> <a href="/draft">2027 Draft</a><br>' + teams.replace('</a> <a', '</a> · <a') + '</nav>\n', encoding='utf-8')


def build_sitemap():
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             f'  <url><loc>{SITE}/</loc><lastmod>{ASOF}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>']
    for path, pri, freq in sorted(URLS, key=lambda u: (-float(u[1]), u[0])):
        lines.append(f'  <url><loc>{SITE}{esc(path)}</loc><lastmod>{ASOF}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
    for path in ('/privacy', '/terms'):
        lines.append(f'  <url><loc>{SITE}{path}</loc><lastmod>{ASOF}</lastmod><changefreq>yearly</changefreq><priority>0.2</priority></url>')
    lines.append('</urlset>')
    (ROOT / 'sitemap.xml').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_og_data():
    """og-data/<kind>.json: the text and image URLs api/og.js draws each card from. Never edit by hand."""
    out = ROOT / 'og-data'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    label = dt.date.fromisoformat(ASOF).strftime('%b %-d, %Y') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ASOF)) else str(ASOF)
    for kind, cards in OG.items():
        (out / f'{kind}.json').write_text(json.dumps({'asOf': label, 'cards': cards}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def main():
    for d in ('players', 'teams', 'draft'):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    for p in PAGES:
        build_player(p)
    for t in TEAMS.values():
        build_team(t)
    for pr in PROS:
        build_prospect(pr)
    build_hubs()
    build_sitemap()
    build_nav()
    build_og_data()
    print(f'social cards {sum(len(c) for c in OG.values())}', end=' | ')
    print(f'players {len(PAGES)} of {len(PLAYERS)} | teams {len(TEAMS)} x3 | draft {len(PROS)} | sitemap urls {len(URLS) + 3}')


if __name__ == '__main__':
    main()
