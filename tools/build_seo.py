#!/usr/bin/env python3
"""Builds the crawlable PlainStats pages that search engines index.

Run:  python3 -I tools/build_seo.py        (from anywhere; paths are relative to this file)

Writes plain static HTML (no JavaScript, inline CSS, system fonts) into
  players/<name>.html            /players/patrick-mahomes
  teams/<team>/index.html        /teams/chiefs
  teams/<team>/cap.html          /teams/chiefs/cap
  teams/<team>/dead-money.html   /teams/chiefs/dead-money
  draft/<name>.html              /draft/jeremiah-smith
  learn/<term>.html              /learn/dead-money   (stat explainers; learn/index.html is their hub)
  players/index.html, teams/index.html, draft/index.html   (hub pages that link to everything)
and rewrites sitemap.xml (each URL dated by when its page text last changed, kept in data/lastmod.json). vercel.json has cleanUrls on, so the .html is dropped from the address.
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
import csv, datetime as dt, hashlib, html, json, pathlib, re, shutil, unicodedata, urllib.parse

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

# The page date is the newest data the pages are built from (contracts, season stats or scores), so the footers and the
# sitemap's lastmod move whenever any of them is refreshed.
def _asof():
    ds = [NFL.get('asOf') or '']
    for fn in ('stats.json', 'schedule.json', 'moves.json'):
        try:
            ds.append(json.load(open(DATA / fn)).get('asOf') or '')
        except Exception:
            pass
    return max(d for d in ds if re.match(r'\d{4}-\d{2}-\d{2}$', d or '')) if any(ds) else NFL['asOf']


ASOF = _asof()

# PlainScore (0 to 100) and its percentile bars, keyed by gsis id. The page computes these itself; tools/refresh_helpers.py plainscore
# exports them to data/plainscore.json so these pages print exactly what the app shows. Missing file = no PlainScore section.
try:
    PSCORE = json.loads((DATA / 'plainscore.json').read_text())
except Exception:
    PSCORE = {'week': None, 'players': {}}
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


# data/pageslugs.json: lets the app's Copy link button hand out the page address (rich preview card) instead of a #hash address.
PAGEMAP = {'p': {}, 'd': {}}


# Vercel Web Analytics (cookieless page counts). Only runs on the live domains; the file is 404 until it is switched on in the Vercel dashboard.
VA = "<script>if(/(^|\\.)plainstatsnfl\\.com$/.test(location.hostname)){window.va=window.va||function(){(window.vaq=window.vaq||[]).push(arguments)};var s=document.createElement('script');s.defer=true;s.src='/_vercel/insights/script.js';document.head.appendChild(s)}</script>"

# Google Analytics 4, same rules as the app (src.html): live domain only, nothing loads until the visitor clicks Accept,
# and the choice is shared through the same localStorage key (pc.consent) so a visitor is asked once across the whole site.
GA = ("<script>(function(){if(!/(^|\\.)plainstatsnfl\\.com$/.test(location.hostname))return;var ID='G-PLKGBKTLC3',K='pc.consent',c=null;"
      "try{c=JSON.parse(localStorage.getItem(K))}catch(e){}"
      "function load(){if(window.__ga)return;window.__ga=1;var s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtag/js?id='+ID;document.head.appendChild(s);"
      "window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments)};gtag('js',new Date());gtag('config',ID,{anonymize_ip:true})}"
      "function decide(v){try{localStorage.setItem(K,JSON.stringify(v))}catch(e){}var b=document.getElementById('consent');if(b)b.remove();if(v==='yes')load()}"
      "if(c==='yes')load();else if(c===null)document.addEventListener('DOMContentLoaded',function(){var b=document.createElement('div');b.className='consent';b.id='consent';b.setAttribute('role','dialog');b.setAttribute('aria-label','Cookie choices');"
      "b.innerHTML='<p>PlainStats uses cookies for visit counts. You can accept, or decline and still use everything. <a href=\"/privacy\">Details</a></p><div class=\"row\"><button type=\"button\" data-c=\"no\">Decline</button><button type=\"button\" data-c=\"yes\">Accept</button></div>';"
      "b.addEventListener('click',function(e){var t=e.target.closest('[data-c]');if(t)decide(t.dataset.c)});document.body.appendChild(b)});"
      # GA4 events, the same names as the app's psTrack (README, "Analytics events"); sent only once gtag exists, i.e. after Accept
      "function ev(n,p){if(window.gtag)gtag('event',n,p)}var at=location.pathname;"
      "document.addEventListener('submit',function(e){var f=e.target;if(f&&/beehiiv\\.com/.test(f.action||''))ev('sign_up',{method:'cap_sheet',from_page:at})},true);"
      "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a');if(!a)return;var h=a.getAttribute('href')||'';"
      "if(a.closest('.doors'))ev('door_click',{link_url:h,from_page:at});else if(a.classList.contains('xq'))ev('explainer_open',{term:h.split('/').pop(),from_page:at});"
      "else if(a.classList.contains('cta'))ev(/[?&]share=1/.test(h)?'share_card_open':'app_open',{link_url:h,from_page:at})},true)})();</script>")



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
    if p.prov == 'm' and 's' in p.ver and (p.base or 0) > 1_000_000:  # undrafted second-year players (these had pages as rookie-scale rows)
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
    f = dict(total=None, apy=None, gtd=None, fg=None, end=None, cap=None, sb=None, years=None, base=None)
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
    if p.prov == 'm' and ok(p, 's'):
        f['base'] = p.base  # undrafted player: this season's CBA minimum base salary, nothing else
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
    if f['base'] and not (f['total'] or f['apy'] or f['cap']):
        return (intro + f". He went undrafted, so the CBA sets his {SEASON_YEAR} base salary at the league minimum of at least {mon(f['base'])}."
                ' The length, signing bonus and guarantees of his deal are being verified.')
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
    elif f['base']:
        q.append((f'How much does {n} make?', f"{n} went undrafted, so his {SEASON_YEAR} base salary is the CBA league minimum of at least {mon(f['base'])}. The length, signing bonus and guarantees of his deal are being verified."))
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
    elif f['base']:
        card.update(n=mon(f['base']), l=f'{SEASON_YEAR} base salary (league minimum)', x='Undrafted · deal length being verified')
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
.scroll{overflow-x:auto}.note{color:var(--mu);font-size:.85rem}.cta{display:inline-block;background:var(--br);color:#fff;padding:10px 18px;border-radius:999px;text-decoration:none;font-weight:600;margin:8px 0}.cta.alt{background:transparent;color:var(--br);border:1px solid var(--br);margin-left:8px}
.faq h3{margin-top:1.1em}.faq p{margin:.2em 0}.chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}.chips a{display:block;background:var(--sf);border:1px solid var(--ln);border-radius:999px;padding:6px 12px;text-decoration:none;font-size:.9rem}
ul.list{columns:2 220px;list-style:none;padding:0;margin:0}ul.list li{padding:3px 0;break-inside:avoid}
ul.doors{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,160px),1fr));gap:10px;list-style:none;padding:0;margin:0}
ul.doors a{display:block;height:100%;background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:12px 14px;text-decoration:none;color:var(--fg)}
ul.doors b{display:block;color:var(--lk)}ul.doors span{display:block;color:var(--mu);font-size:.88rem;margin-top:2px}
.signup{background:var(--sf);border:1px solid var(--ln);border-radius:20px;padding:20px;margin:28px 0 8px}.signup h2{margin:0 0 .2em}.signup p{color:var(--mu);margin:0 0 12px}
.signup form{display:flex;gap:10px;flex-wrap:wrap}.signup input[type=email]{flex:1 1 220px;min-width:0;font:inherit;padding:10px 16px;border-radius:999px;border:1px solid var(--ln);background:var(--bg);color:var(--fg)}
.signup button{font:inherit;font-weight:600;border:0;border-radius:999px;padding:10px 18px;background:var(--br);color:#fff;cursor:pointer}.signup .cta{margin:0}
.psh{display:flex;gap:14px;align-items:center;padding:10px 0}.psh p{margin:0}.psn{flex:none;display:grid;place-items:center;width:64px;height:64px;border-radius:12px;font-size:1.9rem;font-weight:800;font-variant-numeric:tabular-nums;background:var(--bs);box-shadow:inset 0 -5px 0 var(--c)}
ul.pbars{list-style:none;padding:0 0 10px;margin:0;display:grid;gap:8px}ul.pbars li{display:grid;grid-template-columns:8.5rem minmax(0,1fr) 2rem 6.5rem;gap:10px;align-items:center;font-size:.9rem}
ul.pbars .tr{height:10px;border-radius:5px;background:var(--ln);overflow:hidden}ul.pbars .tr i{display:block;height:100%;border-radius:5px}ul.pbars b{text-align:right;font-variant-numeric:tabular-nums}ul.pbars .v{color:var(--mu);font-size:.85rem;text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:480px){ul.pbars li{grid-template-columns:7rem minmax(0,1fr) 2rem}ul.pbars .v{grid-column:1/-1;text-align:left;margin-top:-6px}}
a.xq{display:inline-grid;place-items:center;width:1.15em;height:1.15em;border-radius:50%;border:1px solid var(--ln);color:var(--mu);font-size:.72rem;font-weight:600;line-height:1;text-decoration:none;vertical-align:.1em}a.xq:hover{color:var(--lk);border-color:var(--lk)}
.card.ex{padding:14px 16px}ul.doors.wide{grid-template-columns:1fr}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media(max-width:480px){h1{font-size:1.5rem}.id img{width:56px;height:56px}}
footer{max-width:760px;margin:0 auto;padding:16px;color:var(--mu);font-size:.85rem;border-top:1px solid var(--ln)}footer a{color:var(--mu)}
.consent{position:fixed;z-index:60;left:12px;right:12px;bottom:12px;max-width:560px;margin-inline:auto;background:var(--sf);color:var(--fg);border:1px solid var(--ln);border-radius:18px;padding:16px 18px;box-shadow:0 8px 30px rgba(0,0,0,.18);display:grid;gap:12px;font-size:.88rem;line-height:1.45}
.consent p{margin:0;color:var(--mu)}.consent a{color:var(--lk)}.consent .row{display:flex;gap:10px;justify-content:flex-end}
.consent button{font:inherit;font-weight:600;border-radius:980px;padding:8px 16px;cursor:pointer;border:1px solid var(--ln);background:transparent;color:var(--fg)}.consent button[data-c=yes]{background:var(--br);border-color:var(--br);color:#fff}
@media(min-width:900px){.consent{left:20px;right:auto;bottom:20px;margin:0}}"""


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
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">{meta_robots}<meta property="og:type" content="article"><meta property="og:site_name" content="PlainStats"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{canon}"><meta property="og:image" content="{esc(img)}">{img_meta}<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{esc(img)}"><meta name="theme-color" content="#f5f5f7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)"><link rel="icon" href="/icon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="apple-touch-icon" href="/icon-180.png"><link rel="manifest" href="/manifest.json"><link rel="preconnect" href="https://a.espncdn.com"><style>{CSS}</style>{ld({'@context': 'https://schema.org', '@graph': graph})}{VA}{GA}</head><body><header class="top"><div><a class="logo" href="/">PlainStats</a><a href="/teams">Teams</a><a href="/players">Players</a><a href="/draft">Draft</a><a href="/learn">Explainers</a></div></header><main>{crumb_html}{body}</main><footer><p>PlainStats explains NFL contracts and stats in plain English. Contract figures come from named reports or are calculated from the CBA, and anything unconfirmed says so. Data as of {esc(ASOF)}. Spot a mistake? <a href="{fix_href(path)}"{FIX_ATTR}>Suggest a fix</a>.</p><p><a href="/">Open PlainStats</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p></footer></body></html>"""


# The Cap Sheet newsletter. Static pages carry no third-party script, so this is a plain HTML form that opens beehiiv's hosted
# subscribe page in a new tab (email prefilled). Fill in the publication's subscribe URL, e.g. https://<name>.beehiiv.com/subscribe.
# Left empty, the panel links to the signup on the app's home page instead (/?signup=1 scrolls to it).
CAP_SHEET_URL = 'https://raymonds-newsletter-e9eade.beehiiv.com/subscribe'
CAP_SHEET_PITCH = 'One short email a week: the contract moves that mattered and one chart. Free.'


def signup_html():
    if CAP_SHEET_URL:
        form = (f'<form method="get" action="{esc(CAP_SHEET_URL)}" target="_blank" rel="noopener"><label class="sr" for="cs-email">Email address</label>'
                '<input id="cs-email" name="email" type="email" required placeholder="you@email.com" autocomplete="email"><button type="submit">Subscribe</button></form>')
    else:
        form = '<a class="cta" href="/?signup=1">Sign up for The Cap Sheet</a>'
    return f'<section class="signup" aria-labelledby="h-capsheet"><h2 id="h-capsheet">The Cap Sheet</h2><p>{esc(CAP_SHEET_PITCH)}</p>{form}</section>'


def doors_html(items, heading='Keep exploring'):
    """Doorway links: tiles from a search page into the app tools that answer the next question."""
    return (f'<h2>{esc(heading)}</h2><ul class="doors">'
            + ''.join(f'<li><a href="{esc(u)}"><b>{esc(t)}</b><span>{esc(s)}</span></a></li>' for t, u, s in items) + '</ul>')


def player_doors(p, f, T):
    nick = T['name']
    pos = POSNAME.get(p.pos, p.pos)
    items = [('Compare players', '/compare', f'Put {p.name} side by side with any other player'),
             ('Trade checker', '/trade-checker', f'Test a trade with the {nick} and see if it fits the cap')]
    if f['end'] == SEASON_YEAR:
        items.append(('Free agency', '/free-agency', f'{p.name} is set to hit the market in {SEASON_YEAR + 1}. See who joins him'))
    else:
        items.append(('Best and worst contracts', '/best-worst-contracts', 'Which deals pay off and which ones hurt'))
    items += [('Season stats', '/stats', f'Every {SEASON_YEAR} stat leader, filter by team or position'),
              ('Player ratings', '/player-ratings', f'How {pos}s rank on the field this season'),
              ('Cap 101', '/cap-101', 'Cap hits, guarantees and dead money in plain English')]
    return doors_html(items)


def team_doors(t):
    nick = t['name']
    return doors_html([
        ('Cap lab', '/cap-lab', f'Where the {nick}\' money goes, next to the other 31 teams'),
        ('Roster builder', '/roster-builder', f'Build your own {nick} depth chart'),
        ('Trade checker', '/trade-checker', f'Test a trade with the {nick} and see if it fits the cap'),
        ('Team ratings', '/team-ratings', f'How the {nick} grade on offense, defense and special teams'),
        ('Cap room', '/cap-room', 'Cap space for all 32 teams, side by side'),
        ('Standings', '/standings', f'Where the {nick} stand in the {t["div"]}'),
        ('NFL news', '/news', 'Every move this season and what it means for the cap'),
    ])


def faq_html(faq):
    return '<section class="faq"><h2>Quick answers</h2>' + ''.join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in faq) + '</section>'


def facts_html(rows):
    rows = [(k, v) for k, v in rows if v not in (None, '')]
    if not rows:
        return ''
    return '<div class="card"><dl>' + ''.join(f'<div><dt>{esc(k)}</dt><dd>{v}</dd></div>' for k, v in rows) + '</dl></div>'


# ---------------------------------------------------------------- per-page dates (sitemap lastmod, JSON-LD dateModified)
# data/lastmod.json keeps, for every generated page, a hash of its text and the date that text last changed. A page's date moves
# only when what it says changes (lm_norm: title, description and main text), so a daily refresh or a script change that leaves
# a page's words alone leaves its date alone. Build input; kept out of the deployment (.vercelignore).
LM_FILE = DATA / 'lastmod.json'
LM_TOKEN = '@@LASTMOD@@'
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()
try:
    LM_OLD = json.loads(LM_FILE.read_text())
except Exception:
    LM_OLD = {}
LM = {}


def lm_norm(text):
    """What a reader sees: the title, the description and the <main> text. Scripts, styles, JSON-LD, og tags and the footer's
    "Data as of" date are left out, so a code-only change does not move the date. Also used on older builds by a one-off seed."""
    keep = [m.group(0) for m in re.finditer(r'<title>.*?</title>|<meta name="description"[^>]*>|<main>.*?</main>', text, re.S)]
    return '\n'.join(keep) if keep else text


def lm_track(path, text):
    """Record the page's hash; returns its date (kept when the text is unchanged, today otherwise)."""
    h = hashlib.sha1(lm_norm(text).encode('utf-8')).hexdigest()[:16]
    old = LM_OLD.get(path)
    LM[path] = [h, old[1] if old and old[0] == h else TODAY]
    return LM[path][1]


def page_path(rel):
    """players/x.html -> /players/x, teams/chiefs/index.html -> /teams/chiefs."""
    rel = re.sub(r'(^|/)index\.html$', '', rel)
    return '/' + re.sub(r'\.html$', '', rel)


def write(rel, text):
    out = ROOT / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text.replace(LM_TOKEN, lm_track(page_path(rel), text)), encoding='utf-8')


def player_name_link(p):
    return f'<a href="/players/{p.slug}">{esc(p.name)}</a>'


PAGE_BY_TEAM = {}
for p in PAGES:
    PAGE_BY_TEAM.setdefault(p.team, []).append(p)

# ---------------------------------------------------------------- PlainScore
PS_COLOR = lambda v: '#1565C0' if v >= 80 else '#2A78D6' if v >= 50 else '#9FB4CF' if v >= 25 else '#E0602C'   # same steps as pColor() in src.html


def plainscore(p, f):
    """This player's PlainScore from data/plainscore.json, or None. The pay bar stays only when contract_facts() confirms his yearly pay."""
    ps = PSCORE['players'].get(p.gid) if p.gid else None
    if not ps:
        return None
    bars = [b for b in ps['bars'] if b[3] != 'pay' or f['apy']]
    return dict(ps, bars=bars, pay=any(b[3] == 'pay' for b in bars))


def ps_rank_words(ps):
    return 'first' if ps.get('rk') == 1 else 'last' if ps.get('rk') == ps['n'] else f"better than {ps['s']}%"


def plainscore_sentence(p, ps):
    return (f"{p.name} has a PlainScore of {ps['s']} out of 100: he ranks {ps_rank_words(ps)} of the {ps['n']} qualified {ps['grp']} "
            f"on the field in {SEASON_YEAR}, through week {PSCORE['week']}.")


def plainscore_html(p, ps):
    if not ps:
        return ''
    bars = ''.join(f'<li><span>{esc(l)}</span><span class="tr" aria-hidden="true"><i style="width:{v}%;background:{PS_COLOR(v)}"></i></span><b>{v}</b><span class="v">{esc(val)}</span></li>'
                   for l, v, val, _k in ps['bars'])
    play = f" Play rating {ps['play']}." if ps.get('play') is not None else ''
    return (f'<h2>PlainScore</h2><div class="card"><div class="psh"><b class="psn" style="--c:{PS_COLOR(ps["s"])}" aria-label="PlainScore {ps["s"]} out of 100">{ps["s"]}</b>'
            f'<p>{esc(plainscore_sentence(p, ps))}{play}</p></div><ul class="pbars" aria-label="Percentiles behind his PlainScore">{bars}</ul></div>'
            f'<p class="note">Each bar is a percentile against the same {ps["n"]} {esc(ps["grp"])}: 90 means better than 90% of them.'
            f'{" Yearly pay is against everyone at his position." if ps["pay"] else ""} From nflverse box scores and play-by-play. <a href="/cap-101">How PlainScore works</a></p>')



# ---------------------------------------------------------------- player titles by search intent
# People search a player for one of four reasons, and the title and description lead with the one the page answers best:
#   contract  veteran with a reported deal ("trey hendrickson contract")
#   rookie    on a rookie-scale deal PlainStats calculated from the draft slot ("cyrus allen rookie contract")
#   salary    undrafted, CBA league-minimum base salary ("jalon daniels salary")
#   stats     qualified this season (has a PlainScore) and not on a big reported deal ("fernando mendoza stats"),
#             or has played but has no confirmed contract
# Contract figures still come only from contract_facts(), so an unconfirmed deal never reaches a title.
BIG_DEAL = 5_000_000  # a reported deal at or above this a year stays contract-first even when he is playing well


def page_intent(p, f, ps):
    reported = p.prov == 'r' and bool(f['total'] or f['apy'] or f['cap'])
    if ps and not (reported and (f['apy'] or 0) >= BIG_DEAL):
        return 'stats'
    if reported:
        return 'contract'
    if p.prov == 'f' and (f['total'] or f['apy'] or f['cap']):
        return 'rookie'
    if f['base'] and not (f['total'] or f['apy'] or f['cap']):
        return 'salary'
    if f['total'] or f['apy'] or f['cap']:
        return 'contract'
    return 'stats' if headline_stat(p) else 'contract'


def fit(head, parts, n=60):
    """head + ': ' + parts, dropping parts from the end until it fits in n characters (Google shows about 60)."""
    parts = [x for x in parts if x]
    while parts and len(head + ': ' + ', '.join(parts)) > n:
        parts.pop()
    t = head + (': ' + ', '.join(parts) if parts else '')
    return t + ' | PlainStats' if len(t) + 13 <= n else t


def pack(sentences, n=158):
    """Whole sentences, in order, while they fit in n characters; the first is clipped only if it alone is too long."""
    out = ''
    for x in [x for x in sentences if x]:
        if not out:
            out = clip(x, n)
        elif len(out) + 1 + len(x) <= n:
            out += ' ' + x
    return out


def deal_words(f):
    """'$112.0M through 2029' / '$4.5M deal' / '$14.0M a year' from confirmed figures only."""
    if f['total'] and f['end']:
        return f"{mon(f['total'])} through {f['end']}"
    if f['total']:
        return f"{mon(f['total'])} deal"
    if f['apy']:
        return f"{mon(f['apy'])} a year"
    return None


def deal_sentence(p, f, rookie=False, short=False):
    """The contract in one sentence, confirmed figures only. short: total, end and cap hit only."""
    kind = 'rookie contract' if rookie else 'contract'
    bits = []
    if f['years'] and f['total']:
        bits.append(f"{f['years']}-year, {mon(f['total'])}")
    elif f['total']:
        bits.append(mon(f['total']))
    if f['end']:
        bits.append(f"through {f['end']}")
    lead = f"{poss(p.name)} {kind}: " + ' '.join(bits) if bits else f"{poss(p.name)} {kind}"
    extra = []
    if f['apy'] and not (short and f['total']):
        extra.append(f"{mon(f['apy'])} a year")
    if f['gtd'] and f['total'] and not short:
        extra.append(f"{mon(f['gtd'])} guaranteed")
    if f['cap']:
        extra.append(f"{mon(f['cap'])} {SEASON_YEAR} cap hit")
    return lead + (', ' + ', '.join(extra) if extra else '') + '.'


def season_line(p):
    """'2,104 passing yards in 2026 through week 9' or None."""
    st = headline_stat(p)
    if not st:
        return None
    return f"{st[0]} {st[1]} in {SEASON_YEAR} through week {HIST.get('thru')}"


def player_meta(p, f, ps, intent, summary):
    """(title, description, h1) for a player page, led by its search intent."""
    n, T = p.name, TEAMS[p.team]
    role = POSNAME.get(p.pos, p.pos)
    who = f"{article(role).capitalize()} {role} for the {T['full']}."
    psw = f"PlainScore {ps['s']}" if ps else None
    calc = {'f': ' Calculated from the CBA rookie scale.', 'm': ' Calculated from the CBA league minimum.',
            'p': ' Practice squad pay set by the CBA.'}.get(p.prov, '')
    if intent == 'stats':
        st = headline_stat(p)
        stw = f"{st[0]} {st[1]}" if st else None
        parts = [psw, stw] if st and 'games played' in st[1] or st and 'game played' in st[1] else [stw, psw]
        title = fit(f"{n} {SEASON_YEAR} stats and contract", parts)
        line = season_line(p)
        if f['total'] or f['apy'] or f['cap']:
            deal = deal_sentence(p, f, rookie=p.prov == 'f', short=True) + calc  # one piece, so the note never shows without its figures
        elif f['base']:
            deal = f"League-minimum base salary of at least {mon(f['base'])}."
        else:
            deal = 'Contract being verified.'
        d = [f"{n}: {line}." if line else None,
             f"PlainScore {ps['s']}, {ps_rank_words(ps)} of {ps['n']} qualified {ps['grp']}." if ps else None,
             deal, who]
        return title, pack(d), f"{n}: {SEASON_YEAR} stats and contract"
    line = season_line(p)
    line = line[0].upper() + line[1:] + '.' if line else None
    if intent == 'rookie':
        title = fit(f"{n} rookie contract", [deal_words(f), f"{mon(f['cap'])} cap hit" if f['cap'] else None])
        return title, pack([deal_sentence(p, f, rookie=True, short=True), calc.strip(), who, line]), f"{poss(n)} rookie contract explained"
    if intent == 'salary':
        title = fit(f"{n} salary", [f"{mon(f['base'])} in {SEASON_YEAR} (league minimum)"])
        d = [f"{n} went undrafted, so his {SEASON_YEAR} base salary is the CBA league minimum of at least {mon(f['base'])}.", who,
             'Length, signing bonus and guarantees are being verified.', line]
        return title, pack(d), f"{poss(n)} salary explained"
    if f['total'] or f['apy'] or f['cap']:
        title = fit(f"{n} contract", [deal_words(f), f"{mon(f['cap'])} cap hit" if f['cap'] else None])
        d = [deal_sentence(p, f), calc.strip(), who, f"PlainScore {ps['s']} of 100 in {SEASON_YEAR}." if ps else line]
        return title, pack(d), f"{poss(n)} contract explained"
    return fit(f"{n} contract and {SEASON_YEAR} stats", []), clip(summary, 158), f"{poss(n)} contract explained"


# ---------------------------------------------------------------- player pages
URLS = []  # (path, priority, changefreq)


def build_player(p):
    T = TEAMS[p.team]
    f = contract_facts(p)
    summary = player_summary(p, f)
    faq = player_faq(p, f)
    ps = plainscore(p, f)
    if ps:
        faq.insert(1, (f"What is {poss(p.name)} PlainScore?", plainscore_sentence(p, ps) + ' PlainScore ranks his play rating against everyone at his position with enough snaps.'))
    path = f'/players/{p.slug}'
    has_deal = bool(f['total'] or f['apy'] or f['cap'] or f['base'])
    intent = page_intent(p, f, ps)
    title, desc, h1 = player_meta(p, f, ps, intent, summary)

    src_html = ''
    if p.prov == 'r' and p.srcI >= 0 and p.srcI < len(SOURCES):
        sname, surl = SOURCES[p.srcI]
        src_html = f'<p class="note">Source: <a href="{esc(surl)}" rel="nofollow noopener">{esc(sname)}</a>, a named report. Figures PlainStats has not confirmed are left out.</p>'
    elif p.prov == 'f':
        src_html = '<p class="note">Calculated by PlainStats from the draft slot and the CBA rookie scale (not a reported figure).</p>'
    elif p.prov == 'm' and f['base']:
        src_html = '<p class="note">Base salary from the CBA league-minimum salary table for his years in the league. Undrafted players can also get a small signing bonus and guarantees, which are not in any table, so they are left out until a named report confirms them.</p>'
    elif p.prov == 'm':
        src_html = '<p class="note">Calculated by PlainStats from the CBA league-minimum salary table.</p>'
    elif p.prov == 'p':
        src_html = '<p class="note">Practice squad pay set by the CBA.</p>'

    rows = [('Position', esc(POSNAME.get(p.pos, p.pos)).capitalize()), ('Team', f'<a href="/teams/{T["slug"]}">{esc(T["full"])}</a>')]
    if p.age:
        rows.append(('Age', esc(p.age)))
    if has_deal and f['base'] and not (f['total'] or f['apy'] or f['cap']):
        rows += [(f'{SEASON_YEAR} base salary', 'At least ' + mon(f['base']) + ' (league minimum)'), ('Length, bonus and guarantees', 'Being verified')]
    elif has_deal:
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
    spa = f'/player/{slugify(p.name)}-{p.team.lower()}'
    PAGEMAP['p'][f'p-{slugify(p.name)}-{p.team.lower()}'] = p.slug
    deal_html = facts_html(rows) + src_html
    # Stats-first pages put the season (PlainScore, stats) above the contract; the rest lead with the contract.
    main_html = (plainscore_html(p, ps) + stats_html + deal_html) if intent == 'stats' else (deal_html + plainscore_html(p, ps) + stats_html)
    body = (f'<div class="id">{img_html}<div><h1>{esc(h1)}</h1></div></div>'
            f'<p class="lede">{esc(summary)}</p>{main_html}'
            f'{faq_html(faq)}'
            f'<p><a class="cta" href="{esc(spa)}">See {esc(p.name)} in the PlainStats app</a><a class="cta alt" rel="nofollow" href="{esc(spa)}?share=1">Share</a></p>'
            f'<h2>More on the {esc(T["name"])}</h2><ul class="chips"><li><a href="/teams/{T["slug"]}">{esc(T["full"])} roster and contracts</a></li><li><a href="/teams/{T["slug"]}/cap">How much cap space do the {esc(T["name"])} have?</a></li><li><a href="/teams/{T["slug"]}/dead-money">{esc(T["name"])} dead money</a></li></ul>'
            f'{player_doors(p, f, T)}{signup_html()}')
    person = {'@type': 'Person', 'name': p.name, 'jobTitle': f"{POSNAME.get(p.pos, p.pos).capitalize()}, NFL",
              'url': SITE + path, 'memberOf': {'@type': 'SportsTeam', 'name': T['full'], 'sport': 'American football', 'url': f'{SITE}/teams/{T["slug"]}'}}
    if img:
        person['image'] = img
    graph = [person, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}, 'about': {'@type': 'Person', 'name': p.name}},
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
            f'<ul class="chips"><li><a href="/teams/{slug}/cap">How much cap space do the {esc(nick)} have?</a></li><li><a href="/teams/{slug}/dead-money">{esc(nick)} dead money</a></li><li><a href="/team/{tid.lower()}">Open the {esc(nick)} page in the app</a></li><li><a rel="nofollow" href="/team/{tid.lower()}?share=1">Share the {esc(nick)} as an image</a></li></ul>'
            f'{top_html}{faq_html(faq)}{roster_html}'
            f'<p class="note">Team cap figures are PlainStats\' latest team totals as of {esc(ASOF)}. Player contracts are being re-sourced one by one from named reports, so team totals can change.</p>'
            f'{team_doors(t)}{signup_html()}')
    team_ld = {'@type': 'SportsTeam', 'name': full, 'sport': 'American football', 'url': SITE + path, 'memberOf': {'@type': 'SportsOrganization', 'name': 'National Football League'}}
    if t.get('logo'):
        team_ld['logo'] = t['logo']
    if rec and rec[1].get('coach'):
        team_ld['coach'] = {'@type': 'Person', 'name': rec[1]['coach']}
    graph = [team_ld, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
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
            f'<ul class="chips"><li><a href="/teams/{slug}">{esc(full)} overview</a></li><li><a href="/teams/{slug}/dead-money">{esc(nick)} dead money</a></li><li><a href="/team/{tid.lower()}">Open in the app</a></li></ul>'
            f'{team_doors(t)}{signup_html()}')
    graph = [{'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'about': {'@type': 'SportsTeam', 'name': full, 'sport': 'American football'}, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Cap space', path)])]
    write(f'teams/{slug}/cap.html', shell(path, title, desc, body, graph, image=t.get('logo'), crumbs=[('PlainStats', '/'), ('Teams', '/teams'), (full, f'/teams/{slug}'), ('Cap space', path)], card=og_add('teams', f'{slug}-cap', **card_space)))
    URLS.append((path, '0.8', 'daily'))

    # --- dead money page
    path = f'/teams/{slug}/dead-money'
    title = f"{nick} dead money: {mon(t['dead'])} on the {SEASON_YEAR} cap | PlainStats"
    answer = f"The {full} have about {mon(t['dead'])} in dead money in {SEASON_YEAR}, {ordn(t['r_dead'])} most in the NFL, as of {ASOF}."
    desc = clip(answer + ' Dead money is cap space used by players a team cut or traded.', 158)
    dead_rows = ''.join(f'<tr><td>{esc(n)}</td><td class="r">{mon(v)}</td></tr>' for n, v in (t.get('topDead') or []))
    dead_tbl = f'<h2>Who the {esc(nick)} are still paying</h2><div class="card scroll"><table><thead><tr><th>Player</th>{th_x("Dead money", "dead-money", "r")}</tr></thead><tbody>{dead_rows}</tbody></table></div>' if dead_rows else ''
    faq = [
        (f'How much dead money do the {nick} have?', answer),
        ('What is dead money in the NFL?', 'Dead money is cap space used by players a team cut or traded. It is mostly bonus money that had not been counted yet when the player left.'),
        (f'Why do the {nick} have dead money?', f"Dead money builds up when a team releases or trades a player before his contract ends. The {nick} still owe bonus money and guaranteed salary tied to the players listed here."),
    ]
    body = (f'<h1>{esc(nick)} dead money</h1><p class="lede">{esc(answer)}</p>'
            f'{facts_html([("Dead money", mon(t["dead"])), ("Rank in the NFL", ordn(t["r_dead"]) + " most of 32"), ("Share of the cap", f"{t['dead'] / CAP * 100:.1f}%")])}'
            f'{dead_tbl}<p class="note">The five biggest dead-money charges are PlainStats\' latest team figures as of {esc(ASOF)} and can change as contracts are re-sourced.</p>{faq_html(faq)}'
            f'<ul class="chips"><li><a href="/teams/{slug}">{esc(full)} overview</a></li><li><a href="/teams/{slug}/cap">How much cap space do the {esc(nick)} have?</a></li><li><a href="/team/{tid.lower()}">Open in the app</a></li></ul>'
            f'{team_doors(t)}{signup_html()}')
    graph = [{'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'about': {'@type': 'SportsTeam', 'name': full, 'sport': 'American football'}, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
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
    PAGEMAP['d']['d-' + pr['id']] = pr['slug']
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
            f'<p><a class="cta" href="/prospect/{esc(pr["id"])}">See {esc(pr["name"])} in the PlainStats app</a><a class="cta alt" rel="nofollow" href="/prospect/{esc(pr["id"])}?share=1">Share</a></p><p><a href="/draft">All 2027 draft prospects</a></p>')
    person = {'@type': 'Person', 'name': pr['name'], 'jobTitle': f'College {role}', 'alumniOf': {'@type': 'CollegeOrUniversity', 'name': school}, 'url': SITE + path}
    if img:
        person['image'] = img
    graph = [person, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
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
            f'<div class="card scroll"><table><thead><tr><th>Team</th><th class="r">Cap space</th>{th_x("Dead money", "dead-money", "r")}<th>More</th></tr></thead><tbody>{rows}</tbody></table></div>{faq_html(faq)}')
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


# ---------------------------------------------------------------- stat explainers (/learn/<term>)
# One short page per term that shows up as a column header across the site. Table headers in the app (linkHeads() in src.html) and
# on these static pages (th_x) carry a small "?" link to the matching page. Live examples use the same data and wording rules as
# the rest of the site: team totals say so, and a contract figure appears only when the player's `ver` letters confirm it.
TIERS = json.loads((DATA / 'tiers.json').read_text())
LEARN = [  # slug, short name, column-header label
    ('epa', 'EPA', 'EPA'),
    ('success-rate', 'Success rate', 'success rate'),
    ('cap-hit', 'Cap hit', 'cap hit'),
    ('dead-money', 'Dead money', 'dead money'),
    ('guaranteed-money', 'Guaranteed money', 'guaranteed money'),
]
LEARN_NAME = {s: n for s, n, _ in LEARN}


def th_x(label, slug, cls=''):
    """A table header with a small link to its explainer page."""
    c = f' class="{cls}"' if cls else ''
    return f'<th{c}>{esc(label)} <a class="xq" href="/learn/{slug}" title="What is {esc(LEARN_NAME[slug].lower() if slug != "epa" else "EPA")}?" aria-label="What is {esc(LEARN_NAME[slug].lower() if slug != "epa" else "EPA")}?">?</a></th>'


def team_link(tid):
    t = TEAMS[tid]
    return f'<a href="/teams/{t["slug"]}">{esc(t["full"])}</a>'


def link_or_name(p):
    return player_name_link(p) if hasattr(p, 'slug') else esc(p.name)


def learn_list(rows):
    return '<div class="card"><dl>' + ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) + '</dl></div>'


def learn_content():
    thru = TIERS['thru']
    tt = {k: v for k, v in TIERS['teams'].items() if k in TEAMS}
    off = sorted(tt, key=lambda k: -tt[k]['off'])
    sr = sorted(tt, key=lambda k: -tt[k]['offSr'])
    avg_sr = sum(v['offSr'] for v in tt.values()) / len(tt)
    sgn = lambda v: f'{v:+.2f}'
    conf = [(p, contract_facts(p)) for p in PLAYERS]
    gtds = sorted([(p, f) for p, f in conf if f['gtd']], key=lambda x: -x[1]['gtd'])[:5]
    dead = by_dead[:5]
    league_dead = sum(t['dead'] or 0 for t in TEAMS.values())
    src_pbp = f'From nflverse play-by-play, regular season through Week {thru}.'
    pages = {}

    pages['epa'] = dict(
        q='What is EPA in football?',
        title='What is EPA in football? Expected points added, explained | PlainStats',
        answer='EPA, or expected points added, measures how much a single play changed a team\'s chances of scoring. Every down, distance and spot on the field is worth a certain number of points on average; EPA is the value after the play minus the value before it.',
        how=[
            'Start with expected points: from years of NFL games, a model knows how many points a team usually ends up with from, say, first and 10 at its own 25. A first and 10 near the other team\'s goal line is worth much more.',
            'Each play moves the team to a new situation with a new expected points value. The change is the play\'s EPA. A gain that keeps a drive alive is positive, a sack or a turnover is negative, and a touchdown adds whatever was left to get to seven.',
            'Yards alone miss context. A 3-yard run on third and 2 adds points because it moves the chains; the same 3 yards on third and 5 loses points because the drive stalls.',
            'Averaged over many plays, EPA per play is one of the best single numbers for how well an offense, or a quarterback, is playing. League average sits close to zero. For a defense the number is what it allows, so lower is better.',
        ],
        example=('Example', 'Third and 8 at midfield. A 12-yard completion gives a fresh set of downs in field-goal range: big positive EPA. An incompletion means a punt: negative EPA. An interception is worse still.'),
        now_h=f'Best offenses by EPA per play, through Week {thru}',
        now=[(team_link(k), sgn(tt[k]['off'])) for k in off[:5]],
        now_note=src_pbp + ' Garbage time is included.',
        where=[('Team tiers', '/team-tiers', 'Every team by offense and defense EPA per play'), ('Player ratings', '/player-ratings', 'EPA feeds the quarterback and skill-player ratings'), ('Season stats', '/stats', 'Season stats for every player')],
        faq=[('What is a good EPA per play?', 'League average is close to zero. An offense well above +0.10 per play is among the best in the league; one below -0.10 is struggling.'),
             ('Where does PlainStats get EPA?', 'From nflverse, an open data project whose play-by-play files include expected points for every NFL play.'),
             ('Is EPA better than yards?', 'For judging plays, usually. Yards ignore down, distance and field position; EPA counts them, so it rewards first downs and touchdowns and punishes sacks and turnovers.')],
        card=dict(n=sgn(tt[off[0]]['off']), l=f'EPA per play, {TEAMS[off[0]]["full"]}, best in the NFL'),
    )

    pages['success-rate'] = dict(
        q='What is success rate in football?',
        title='What is success rate in football? Explained in plain English | PlainStats',
        answer='Success rate is the share of plays that add expected points, that is, plays with positive EPA. It tells you how often an offense stays on schedule, not how big its best plays were.',
        how=[
            'Every play gets an EPA value. A play counts as a success when its EPA is above zero: it left the offense in a better spot to score than before.',
            'In practice that usually means a good chunk of the yards needed on first down, most of them on second down, and a conversion on third or fourth down.',
            'Success rate and EPA per play answer different questions. EPA per play rewards big plays; success rate rewards consistency. An offense that lives on long passes can post a fine EPA with a low success rate, and a grind-it-out offense can do the opposite.',
            'For a defense, the number is the share of plays it allows that are successes, so lower is better.',
        ],
        example=('Example', 'Ten plays: six gain enough to add expected points, four do not. That is a 60% success rate, however long the six gains were.'),
        now_h=f'Highest offensive success rate, through Week {thru}',
        now=[(team_link(k), f"{tt[k]['offSr'] * 100:.1f}%") for k in sr[:5]],
        now_note=f'League average this season: {avg_sr * 100:.1f}%. ' + src_pbp + ' A success is a play with positive EPA (nflverse <code>success</code>).',
        where=[('Team tiers', '/team-tiers', 'Offense and defense success rate for every team ("hit" columns)'), ('Player ratings', '/player-ratings', 'Team run success sits behind the offensive line ratings')],
        faq=[('What is a good success rate in the NFL?', f'This season the average offense succeeds on {avg_sr * 100:.1f}% of its plays. A few points above that is very good.'),
             ('How is success rate different from EPA?', 'EPA measures how much each play was worth. Success rate only counts whether it was worth something, so one huge play moves EPA a lot but success rate very little.')],
        card=dict(n=f"{tt[sr[0]]['offSr'] * 100:.1f}%", l=f'success rate, {TEAMS[sr[0]]["full"]}, best in the NFL'),
    )

    pages['cap-hit'] = dict(
        q='What is a cap hit in the NFL?',
        title='What is a cap hit in the NFL? Explained in plain English | PlainStats',
        answer=f'A cap hit is how much one player counts against his team\'s salary cap this season. Every team\'s cap hits, plus its dead money, have to fit under the {SEASON_YEAR} cap of {mon(CAP)}.',
        how=[
            'A cap hit adds up the player\'s base salary for the season, a share of his signing bonus, and any roster, workout or likely incentive bonuses for that year.',
            'The signing bonus is paid in cash up front but spread evenly over the contract for cap purposes, up to five seasons. That is why a cap hit is often very different from what the player is paid in cash this year.',
            'Teams move cap hits around on purpose. A restructure turns salary into a bonus so this year\'s cap hit drops and later years go up; void years stretch a bonus over seasons the player will never play.',
            'Cap hit is not the same as yearly pay. Headlines quote average per year (total value divided by years); the cap hit is the number the team actually counts this season.',
        ],
        example=('Example', 'A player signs for four years with a $20M signing bonus and a $5M base salary this season. The bonus counts $5M a year, so this season\'s cap hit is $5M + $5M = $10M, even though he was paid $25M in cash.'),
        now_h=f'Largest {SEASON_YEAR} cap hits PlainStats has confirmed so far',
        now=[],  # no confirmed-cap-hit list until more veteran deals are verified (it was led by rookie deals)
        now_note='Only cap hits confirmed by a named report or calculated from the CBA are listed. Contracts still being verified are left out, so this is not a full league ranking.',
        where=[('All contracts', '/contracts', 'Every player\'s cap hit, sortable'), ('Cap room', '/cap-room', 'What all those cap hits leave each team'), ('Cap 101', '/cap-101', 'Signing bonuses, restructures and void years')],
        faq=[('Is a cap hit the same as salary?', 'No. Base salary is one part of it. The cap hit also counts a share of the signing bonus and other bonuses for the season.'),
             (f'What is the {SEASON_YEAR} NFL salary cap?', f'{mon(CAP)} per team. It is a hard cap: a team\'s cap hits and dead money together cannot go over it.')],
        card=dict(n=mon(CAP, 0), l=f'{SEASON_YEAR} salary cap per team'),
    )

    pages['dead-money'] = dict(
        q='What is dead money in the NFL?',
        title='What is dead money in the NFL? Explained in plain English | PlainStats',
        answer='Dead money is salary cap space taken up by players who are no longer on the team. It is mostly signing bonus that had not been counted against the cap yet when the player was cut or traded, plus any salary the team still has to pay.',
        how=[
            'A signing bonus is paid up front but counted against the cap a slice at a time over the contract. If the player leaves early, the slices not yet counted do not disappear: they land on the old team\'s cap all at once. That is dead money.',
            'Guaranteed salary the team still owes counts too, because the team has to pay it whether or not he plays.',
            'Timing matters. Cut a player before June 1 and all of his leftover bonus counts this season. Cut him after June 1, or with a post-June 1 designation, and the hit splits between this season and next.',
            'In a trade, the old team keeps the bonus it already paid as dead money, and the new team takes on only his salary from then on.',
            'Void years are a common source: when a contract voids, whatever bonus was spread over those fake years lands as dead money.',
        ],
        example=('Example', 'A player gets a $20M signing bonus on a five-year deal: $4M a year on the cap. He is cut before June 1 after two seasons. The three seasons not yet counted, $12M, all hit the cap this season as dead money.'),
        now_h=f'Most dead money in {SEASON_YEAR}',
        now=[(team_link(t['id']), mon(t['dead'])) for t in dead],
        now_note=f'PlainStats\' latest team totals as of {esc(ASOF)}. Across the league, teams carry about {mon(league_dead, 0)} in dead money. Totals can change as contracts are re-sourced from named reports.',
        where=[('Teams', '/teams', 'Dead money for all 32 teams, with a page for each'), ('Cap lab', '/cap-lab', 'How dead money weighs on each team\'s cap health'), ('Cap 101', '/cap-101', 'Before or after June 1, restructures and void years')],
        faq=[('Why do NFL teams have dead money?', 'Because they cut or trade players before their contracts end. The bonus already paid, and any guaranteed salary still owed, keeps counting against the cap.'),
             ('Does dead money count against the salary cap?', 'Yes. Dead money uses cap space exactly like a current player\'s cap hit does.'),
             ('What is a post-June 1 cut?', 'A release after June 1, or one designated as post-June 1 before then. Only this season\'s share of the bonus counts now; the rest moves to next season.')],
        card=dict(n=mon(dead[0]['dead']), l=f'dead money, {dead[0]["full"]}, most in the NFL'),
    )

    pages['guaranteed-money'] = dict(
        q='What is guaranteed money in an NFL contract?',
        title='What is guaranteed money in an NFL contract? Explained | PlainStats',
        answer='Guaranteed money is the part of an NFL contract the player gets even if he is cut. Most NFL contracts are not fully guaranteed, so the guaranteed figure is usually a better guide to a deal\'s real size than the headline total.',
        how=[
            'Fully guaranteed at signing: money locked in the day he signs. It is paid even if he is cut for skill, gets hurt or the team changes its mind. The signing bonus is part of it.',
            'Guaranteed for injury only: paid if he is cut while hurt, but not if he is cut for performance.',
            'Rolling or vesting guarantees: salary that becomes fully guaranteed on a set date, often early in the new league year, if he is still on the roster. Teams decide before that date whether to keep him.',
            'Headlines usually add every kind together. That is why two deals with the same "guaranteed" number can be very different. PlainStats shows the share guaranteed and, where a report gives it, the amount locked at signing.',
        ],
        example=('Example', 'A four-year, $100M deal with $60M guaranteed might have $40M fully guaranteed at signing and $20M that only becomes guaranteed if he is on the roster next March. If he is cut before then, he keeps the $40M.'),
        now_h='Largest guarantees PlainStats has confirmed so far',
        now=[(f'{link_or_name(p)} <span class="note">{esc(p.pos)}, {esc(TEAMS[p.team]["name"]) if p.team in TEAMS else esc(p.team)}</span>', mon(f['gtd'])) for p, f in gtds],
        now_note='Only guarantees confirmed by a named report are listed. Contracts still being verified are left out, so this is not a full league ranking.',
        where=[('All contracts', '/contracts', 'Sort every deal by share guaranteed'), ('Best and worst contracts', '/best-worst-contracts', 'Which deals pay off'), ('Cap 101', '/cap-101', 'Guarantees, bonuses and dead money')],
        faq=[('Are NFL contracts guaranteed?', 'Only partly, for most players. The guaranteed part is paid if he is cut; the rest depends on him staying on the roster.'),
             ('How does guaranteed money relate to dead money?', 'Guaranteed money still owed when a player is cut or traded counts against the old team\'s cap as dead money.')],
        card=dict(n=mon(gtds[0][1]['gtd']) if gtds else mon(CAP, 0), l=(f'guaranteed, {gtds[0][0].name}' if gtds else f'{SEASON_YEAR} salary cap')),
    )
    return pages


def build_learn():
    pages = learn_content()
    hub_crumb = ('Stat explainers', '/learn')
    for slug, name, _ in LEARN:
        L = pages[slug]
        path = f'/learn/{slug}'
        desc = clip(L['answer'], 158)
        crumbs = [('PlainStats', '/'), hub_crumb, (name, path)]
        how = ''.join(f'<p>{esc(x)}</p>' for x in L['how'])
        now = learn_list(L['now']) if L['now'] else ''
        others = ''.join(f'<li><a href="/learn/{s}">{esc(n)}</a></li>' for s, n, _ in LEARN if s != slug)
        faq = [(L['q'], L['answer'])] + L['faq']
        body = (f'<h1>{esc(L["q"])}</h1><p class="lede">{esc(L["answer"])}</p>'
                f'<h2>How it works</h2>{how}'
                f'<div class="card ex"><b>{esc(L["example"][0])}.</b> {esc(L["example"][1])}</div>'
                + (f'<h2>{esc(L["now_h"])}</h2>{now}<p class="note">{L["now_note"]}</p>' if now else '')
                + f'{doors_html(L["where"], "Where you see it on PlainStats")}'
                f'{faq_html(L["faq"])}'
                f'<h2>More stat explainers</h2><ul class="chips">{others}<li><a href="/cap-101">Cap 101 glossary</a></li></ul>{signup_html()}')
        graph = [{'@type': 'Article', 'headline': L['q'], 'description': desc, 'url': SITE + path, 'dateModified': LM_TOKEN,
                  'author': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}, 'publisher': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'},
                  'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}},
                 {'@type': 'DefinedTerm', 'name': name, 'description': L['answer'], 'url': SITE + path, 'inDefinedTermSet': SITE + '/learn'},
                 faq_ld(faq), crumbs_ld(crumbs)]
        card = og_add('pages', f'learn-{slug}', m='brand', c=OG_BRAND, e='Stat explainer', t=L['q'], s='Explained in plain English', x='PlainStats', **L['card'])
        write(f'learn/{slug}.html', shell(path, L['title'], desc, body, graph, crumbs=crumbs, card=card))
        URLS.append((path, '0.7', 'weekly'))

    path = '/learn'
    title = 'NFL stats and contract terms explained in plain English | PlainStats'
    desc = 'Short, plain-English explainers for EPA, success rate, cap hit, dead money and guaranteed money, with this season\'s numbers.'
    items = ''.join(f'<li><a href="/learn/{s}"><b>{esc(pages[s]["q"])}</b><span>{esc(clip(pages[s]["answer"], 120))}</span></a></li>' for s, _, _ in LEARN)
    body = (f'<h1>Stat explainers</h1><p class="lede">The numbers in PlainStats tables, one short page each. Tap the small ? next to a column name anywhere on the site to land here.</p>'
            f'<ul class="doors wide">{items}</ul><p>Want the rest of the vocabulary, from franchise tags to void years? See <a href="/cap-101">Cap 101</a>.</p>{signup_html()}')
    graph = [{'@type': 'DefinedTermSet', 'name': 'PlainStats stat explainers', 'url': SITE + path, 'description': desc,
              'hasDefinedTerm': [{'@type': 'DefinedTerm', 'name': n, 'url': f'{SITE}/learn/{s}'} for s, n, _ in LEARN]},
             crumbs_ld([('PlainStats', '/'), ('Stat explainers', path)])]
    card = og_add('pages', 'learn', m='brand', c=OG_BRAND, e='PlainStats', t='Stat explainers', s='EPA, cap hits, dead money and more', n=str(len(LEARN)), l='short plain-English explainers', x='With this season\'s numbers')
    write('learn/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Stat explainers', path)], card=card))
    URLS.append((path, '0.7', 'weekly'))


def build_nav():
    teams = ''.join(f'<a href="/teams/{t["slug"]}">{esc(t["full"])}</a> ' for t in sorted(TEAMS.values(), key=lambda t: t['full']))
    (ROOT / 'tools' / 'seo-nav.html').write_text(
        '<nav aria-label="Browse PlainStats" style="max-width:1100px;margin:0 auto;padding:8px 20px 48px;color:var(--muted);font:.85rem/2 var(--body)">'
        '<strong style="color:var(--fg)">Browse:</strong> <a href="/teams">All teams</a> <a href="/players">Players</a> <a href="/draft">2027 Draft</a> <a href="/learn">Stat explainers</a><br>' + teams.replace('</a> <a', '</a> · <a') + '</nav>\n', encoding='utf-8')

# App pages (one URL per section of the single-page app; vercel.json sends them to index.html)
APP_URLS = [('/scores', '0.9', 'daily'), ('/standings', '0.9', 'weekly'), ('/projections', '0.8', 'weekly'), ('/news', '0.8', 'daily'),
            ('/player-ratings', '0.8', 'weekly'), ('/player-ratings/roles', '0.5', 'weekly'), ('/player-ratings/pay-vs-play', '0.6', 'weekly'), ('/player-ratings/rankings', '0.7', 'weekly'), ('/player-ratings/traits', '0.6', 'weekly'),
            ('/stats', '0.8', 'weekly'), ('/contracts', '0.9', 'daily'), ('/power-rankings', '0.8', 'weekly'),
            ('/mock-draft', '0.8', 'weekly'), ('/big-board', '0.7', 'weekly'), ('/free-agency', '0.8', 'weekly'), ('/free-agency/key-dates', '0.5', 'monthly'),
            ('/team-ratings', '0.7', 'weekly'), ('/team-tiers', '0.8', 'weekly'), ('/cap-room', '0.8', 'daily'), ('/awards', '0.6', 'weekly'), ('/best-worst-contracts', '0.6', 'weekly'),
            ('/rookie-contracts', '0.6', 'weekly'), ('/rookie-pay', '0.5', 'monthly'), ('/draft-guide', '0.4', 'monthly'), ('/cap-lab', '0.5', 'weekly'),
            ('/roster-builder', '0.6', 'weekly'), ('/trade-checker', '0.5', 'weekly'), ('/trade-deadline', '0.8', 'daily'), ('/compare', '0.5', 'weekly'), ('/cap-101', '0.6', 'monthly'),
            ('/about', '0.3', 'monthly')]
# One page per panel inside a section tab (SUBS in src.html)
APP_URLS += [(u, '0.5', 'weekly') for u in [
    '/team-ratings/best',
    '/team-ratings/traits',
    '/team-ratings/roster-ratings',
    '/team-tiers/offense-vs-defense',
    '/team-tiers/all-teams',
    '/awards/how-it-works',
    '/power-rankings/results-vs-roster',
    '/power-rankings/risers-and-fallers',
    '/power-rankings/how-it-works',
    '/standings/playoff-seeds',
    '/projections/playoff-odds',
    '/projections/all-teams',
    '/projections/how-it-works',
    '/contracts/position-market',
    '/contracts/all-players',
    '/best-worst-contracts/teams',
    '/best-worst-contracts/all',
    '/rookie-contracts/extension-watch',
    '/rookie-contracts/all',
    '/cap-lab/spending-heatmap',
    '/cap-lab/cap-health',
    '/cap-lab/doppelganger',
    '/free-agency/by-position',
    '/free-agency/by-team',
    '/free-agency/all',
    '/free-agency/franchise-tags',
    '/free-agency/news',
    '/big-board/class-depth',
    '/big-board/expert-splits',
    '/big-board/full',
    '/mock-draft/pick-owners',
    '/rookie-pay/savings',
    '/rookie-pay/rules']]


def build_sitemap():
    """Each generated page carries the date its own text last changed (data/lastmod.json). The home page and the app pages
    (APP_URLS, one index.html filled with live data) use the data date, since their numbers change with every refresh."""
    for f in ('privacy.html', 'terms.html'):
        lm_track(page_path(f), (ROOT / f).read_text(encoding='utf-8'))
    date = lambda path: LM[path][1] if path in LM else ASOF
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             f'  <url><loc>{SITE}/</loc><lastmod>{ASOF}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>']
    for path, pri, freq in sorted(URLS + APP_URLS, key=lambda u: (-float(u[1]), u[0])):
        lines.append(f'  <url><loc>{SITE}{esc(path)}</loc><lastmod>{date(path)}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
    for path in ('/privacy', '/terms'):
        lines.append(f'  <url><loc>{SITE}{path}</loc><lastmod>{date(path)}</lastmod><changefreq>yearly</changefreq><priority>0.2</priority></url>')
    lines.append('</urlset>')
    (ROOT / 'sitemap.xml').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    LM_FILE.write_text(json.dumps(LM, separators=(',', ':'), sort_keys=True) + '\n', encoding='utf-8')


def build_og_data():
    """og-data/<kind>.json: the text and image URLs api/og.js draws each card from. Never edit by hand."""
    out = ROOT / 'og-data'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    label = dt.date.fromisoformat(ASOF).strftime('%b %-d, %Y') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ASOF)) else str(ASOF)
    for kind, cards in OG.items():
        (out / f'{kind}.json').write_text(json.dumps({'asOf': label, 'cards': cards}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def main():
    for d in ('players', 'teams', 'draft', 'learn'):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    for p in PAGES:
        build_player(p)
    for t in TEAMS.values():
        build_team(t)
    for pr in PROS:
        build_prospect(pr)
    build_hubs()
    build_learn()
    build_sitemap()
    build_nav()
    build_og_data()
    (ROOT / 'data' / 'pageslugs.json').write_text(json.dumps(PAGEMAP, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    print(f'social cards {sum(len(c) for c in OG.values())}', end=' | ')
    print(f'players {len(PAGES)} of {len(PLAYERS)} | teams {len(TEAMS)} x3 | draft {len(PROS)} | sitemap urls {len(URLS) + 3}')


if __name__ == '__main__':
    main()
