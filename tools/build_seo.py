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
import csv, datetime as dt, hashlib, html, itertools, json, pathlib, re, shutil, unicodedata, urllib.parse

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


def _load(fn, empty):
    try:
        return json.loads((DATA / fn).read_text())
    except Exception:
        return empty


# "Latest" box on player pages: the news feed (moves.json, matched by `gids`), this week's official injury report
# (injuries.json) and the last game's line (history.json game log + schedule.json for date, opponent and score).
MOVES = _load('moves.json', {'moves': []})
INJ = _load('injuries.json', {'players': {}})
SCHED = _load('schedule.json', {'games': []})
NEWS_DAYS = 30  # a news item shows on the player's page for this many days
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
      "if(a.closest('.doors'))ev('door_click',{link_url:h,from_page:at});else if(a.closest('.pnews'))ev('player_news_click',{link_url:h,from_page:at});else if(a.classList.contains('xq'))ev('explainer_open',{term:h.split('/').pop(),from_page:at});else if(h=='/weekly'||h.indexOf('/weekly/')==0)ev('weekly_open',{link_url:h,from_page:at});"
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


# Just released (Growth Playbook, Nov 23 audit, finding 3): searches for a player spike in the days after a cut, and the
# nflverse roster drops him within a day, which used to take his page away exactly then. For RELEASE_DAYS after a `Release`
# item in moves.json names him as the one let go, his page leads with the move (title, first line, FAQ) and stays
# indexable. A player the roster no longer lists comes back from data/off_roster.json (the row build_contracts.py parked,
# contract and all) as p.gone: he gets his page but stays off team pages, the players hub and comparisons. A player claimed
# or signed by another team since, or back on the same team's game-day roster, gets his normal page.
RELEASE_DAYS = 7
_REL_VERB = re.compile(r'\b(release[sd]?|waive[sd]?|cut[s]?|part(?:s|ed)? ways with)\s+(.*?)(?=,|;| and [a-z]| as | after | at | to | following |$)')


def released_names(head):
    """The names a Release headline says were let go: the words after each release verb, up to the next clause.
    "Colts waive QB Daniel Jones and turn to Anthony Richardson" -> Daniel Jones only."""
    return [(m.group(1), m.group(2)) for m in _REL_VERB.finditer(head or '')]


def _rel_team(m, nick_head):
    """The team in the item's `teams` whose nickname leads the headline (the team that let him go), else the first."""
    for t in m.get('teams') or []:
        if t in TEAMS and nick_head.startswith(TEAMS[t]['name']):
            return t
    return (m.get('teams') or [None])[0]


_parked = {}
for _r in _load('off_roster.json', {'rows': []}).get('rows', []):
    if len(_r) > 19 and _r[19]:
        _parked.setdefault(_r[19], []).append(_r)
_on = {p.gid: p for p in PLAYERS if p.gid}
_cut = (dt.date.fromisoformat(ASOF) - dt.timedelta(days=RELEASE_DAYS - 1)).isoformat()
RELEASED = {}  # gid -> dict(m=news item, team=team that let him go, verb='released' | 'waived')
for _m in sorted(MOVES.get('moves', []), key=lambda m: m.get('iso') or ''):  # oldest first, so the newest release wins
    if _m.get('kind') != 'Release' or (_m.get('iso') or '') < _cut or (_m.get('iso') or '') > ASOF:
        continue
    for _verb, _clause in released_names(_m.get('head')):
        for _nm, _g in zip(_m.get('players') or [], _m.get('gids') or []):
            if not _g or not re.search(r'(^|\s)' + re.escape(_nm) + r'(\s|$)', _clause):
                continue
            _t = _rel_team(_m, _m.get('head') or '')
            RELEASED[_g] = dict(m=_m, team=_t, verb='waived' if _verb.startswith('waive') else 'released')
for _g, _rel in list(RELEASED.items()):
    p = _on.get(_g)
    if p:
        if p.team != _rel['team']:  # claimed or signed elsewhere since: his normal page tells that story
            del RELEASED[_g]
        continue
    row = next((r for r in _parked.get(_g, []) if r[1] == _rel['team']), None)
    if not row or row[1] not in TEAMS:
        del RELEASED[_g]
        continue
    p = Pl()
    (p.name, p.team, p.pos, p.age, p.total, p.apy, p.gtd, p.fg, p.end, p.voidy, p.cap, p.base, p.bonus,
     p.dpre, p.dpost, p.prov, p.srcI, p.ver, p.sb, p.gid) = row[:20]
    p.ver = p.ver or ''
    p.hist = HISTBY.get(p.gid)
    p.s26 = (p.hist or {}).get('s', {}).get(str(SEASON_YEAR))
    p.gone = True
    _on[_g] = p
GONE = [_on[g] for g in RELEASED if getattr(_on[g], 'gone', False)]
for p in PLAYERS:
    p.gone = False

PAGES = [p for p in PLAYERS if substantive(p) or p.gid in RELEASED] + GONE
# Player pages Google showed 20+ times in a week (Monday Search Console reports); they skip the thin rule in build_player().
SEARCH_SEEN = set(_load('search_seen.json', {'slugs': []}).get('slugs', []))
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


def pay_questions(p, f):
    """The pay questions people search ("how much does X make", "how long is X's contract", guarantees), answered from
    confirmed figures only. Pages that lead with the contract print these as headings right under the title."""
    T = TEAMS[p.team]
    n = p.name
    q = []
    unver = 'PlainStats shows contract figures only after a named report confirms them, and this one is still being verified.'
    calc = {'f': ' PlainStats calculated this from the draft slot and the CBA rookie scale.',
            'm': ' PlainStats calculated this from the CBA league-minimum salary.', 'p': ' This is practice squad pay set by the CBA.'}.get(p.prov, '')
    kind = 'rookie contract' if p.prov == 'f' else 'contract'
    if f['total'] or f['apy']:
        deal = (f"{f['years']}-year, {mon(f['total'])} {kind}" if f['years'] and f['total'] else
                f"{mon(f['total'])} {kind}" if f['total'] else None)
        if p.prov == 'p' and f['apy']:
            a, calc = f"{n} is on the {T['full']} practice squad, where the CBA sets his {SEASON_YEAR} pay at {mon(f['apy'])}.", ''
        elif f['apy'] and f['total'] and f['apy'] == f['total'] and not f['years']:
            a = f"{n} makes {mon(f['apy'])} in {SEASON_YEAR}, on a one-year {kind} with the {T['full']}."
        elif f['apy'] and deal:
            a = f"{n} makes {mon(f['apy'])} a year on average, on {article(deal)} {deal} with the {T['full']}."
        elif f['apy']:
            a = f"{n} makes {mon(f['apy'])} a year on average with the {T['full']}."
        else:
            a = f"{n} has {article(deal)} {deal} with the {T['full']}."
        q.append((f'How much does {n} make?', a + calc))
    elif f['cap']:
        q.append((f'How much does {n} make?', f"{n} counts {mon(f['cap'])} against the {T['name']}' {SEASON_YEAR} cap. The total value of his {kind} is being verified."))
    elif f['base']:
        q.append((f'How much does {n} make?', f"{n} went undrafted, so his {SEASON_YEAR} base salary is the CBA league minimum of at least {mon(f['base'])}. The length, signing bonus and guarantees of his deal are being verified."))
    else:
        q.append((f'How much does {n} make?', f"{unver}"))
    if f['end'] or f['years']:
        a = f"{poss(n)} {kind}"
        if f['years']:
            a += f" is {f['years']} year{'' if f['years'] == 1 else 's'}"
            a += f" and runs through the {f['end']} season." if f['end'] else '.'
        else:
            a += f" runs through the {f['end']} season."
        if f['end'] and p.prov not in ('f', 'p'):  # rookie deals can grow a fifth-year option; practice squad deals are not free agency
            a += f" Unless it is extended, {int(f['end']) + 1} is the first year he could become a free agent."
        q.append((f"How long is {poss(n)} contract?", a))
    if f['gtd'] is not None and f['total']:
        a = f"{mon(f['gtd'])} of the {mon(f['total'])} is guaranteed."
        if f['fg']:
            a += f" {mon(f['fg'])} was fully guaranteed at signing."
        if p.prov == 'f':
            a += ' These are PlainStats calculations.'
        q.append((f"How much of {poss(n)} contract is guaranteed?", a))
    return q


def player_faq(p, f):
    T = TEAMS[p.team]
    n = p.name
    q = pay_questions(p, f)
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
CSS =""":root{color-scheme:light dark;--bg:#f5f5f7;--sf:#fff;--fg:#1d1d1f;--mu:#636368;--ln:#e1e1e6;--br:#0071e3;--lk:#0066cc;--bs:#e8f1fc;--bt:#0071e3}
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
.scroll{overflow-x:auto}.nw{white-space:nowrap}.note{color:var(--mu);font-size:.85rem}.cta{display:inline-block;background:var(--bt);color:#fff;padding:10px 18px;border-radius:999px;text-decoration:none;font-weight:600;margin:8px 0}.cta.alt{background:transparent;color:var(--lk);border:1px solid var(--lk);margin-left:8px}
.pay h2{font-size:1.08rem;margin:1em 0 .2em}.pay p{margin:0 0 .6em;font-size:1.05rem}.faq h3{margin-top:1.1em}.faq p{margin:.2em 0}.chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}.chips a{display:block;background:var(--sf);border:1px solid var(--ln);border-radius:999px;padding:6px 12px;text-decoration:none;font-size:.9rem}
ul.list{columns:2 220px;list-style:none;padding:0;margin:0}ul.list li{padding:3px 0;break-inside:avoid}
ul.doors{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,160px),1fr));gap:10px;list-style:none;padding:0;margin:0}
ul.doors a{display:block;height:100%;background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:12px 14px;text-decoration:none;color:var(--fg)}
ul.doors b{display:block;color:var(--lk)}ul.doors span{display:block;color:var(--mu);font-size:.88rem;margin-top:2px}
.signup{background:var(--sf);border:1px solid var(--ln);border-radius:20px;padding:20px;margin:28px 0 8px}.signup h2{margin:0 0 .2em}.signup p{color:var(--mu);margin:0 0 12px}
.signup form{display:flex;gap:10px;flex-wrap:wrap}.signup input[type=email]{flex:1 1 220px;min-width:0;font:inherit;padding:10px 16px;border-radius:999px;border:1px solid var(--ln);background:var(--bg);color:var(--fg)}
.signup button{font:inherit;font-weight:600;border:0;border-radius:999px;padding:10px 18px;background:var(--bt);color:#fff;cursor:pointer}.signup .cta{margin:0}
.psh{display:flex;gap:14px;align-items:center;padding:10px 0}.psh p{margin:0}.psn{flex:none;display:grid;place-items:center;width:64px;height:64px;border-radius:12px;font-size:1.9rem;font-weight:800;font-variant-numeric:tabular-nums;background:var(--bs);box-shadow:inset 0 -5px 0 var(--c)}
ul.pbars{list-style:none;padding:0 0 10px;margin:0;display:grid;gap:8px}ul.pbars li{display:grid;grid-template-columns:8.5rem minmax(0,1fr) 2rem 6.5rem;gap:10px;align-items:center;font-size:.9rem}
ul.pbars .tr{height:10px;border-radius:5px;background:var(--ln);overflow:hidden}ul.pbars .tr i{display:block;height:100%;border-radius:5px}ul.pbars b{text-align:right;font-variant-numeric:tabular-nums}ul.pbars .v{color:var(--mu);font-size:.85rem;text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:480px){ul.pbars li{grid-template-columns:7rem minmax(0,1fr) 2rem}ul.pbars .v{grid-column:1/-1;text-align:left;margin-top:-6px}}
a.xq{display:inline-grid;place-items:center;width:1.15em;height:1.15em;border-radius:50%;border:1px solid var(--ln);color:var(--mu);font-size:.72rem;font-weight:600;line-height:1;text-decoration:none;vertical-align:.1em}a.xq:hover{color:var(--lk);border-color:var(--lk)}
.card.ex{padding:14px 16px}.pnews>div{padding:12px 0;border-bottom:1px solid var(--ln)}.pnews>div:last-child{border:0}.pnews h3{margin:0 0 2px;font-size:.85rem;font-weight:600;color:var(--mu)}.pnews p{margin:0}ul.doors.wide{grid-template-columns:1fr}
td .sub{display:block;color:var(--mu);font-size:.8rem;font-weight:400}.up{color:#1a7f37}.dn{color:#c62828}
@media(prefers-color-scheme:dark){.up{color:#4ac26b}.dn{color:#ff6b6b}}
.wknav{display:flex;justify-content:space-between;gap:12px;margin:12px 0;font-size:.92rem}
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
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">{meta_robots}<meta property="og:type" content="article"><meta property="og:site_name" content="PlainStats"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{canon}"><meta property="og:image" content="{esc(img)}">{img_meta}<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{esc(img)}"><meta name="theme-color" content="#f5f5f7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)"><link rel="icon" href="/icon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="apple-touch-icon" href="/icon-180.png"><link rel="manifest" href="/manifest.json"><link rel="preconnect" href="https://a.espncdn.com"><style>{CSS}</style>{ld({'@context': 'https://schema.org', '@graph': graph})}{GA}</head><body><header class="top"><div><a class="logo" href="/">PlainStats</a><a href="/teams">Teams</a><a href="/players">Players</a><a href="/draft">Draft</a><a href="/learn">Explainers</a></div></header><main>{crumb_html}{body}</main><footer><p>PlainStats is NFL analytics in plain English: player ratings, stats and contracts. Contract figures come from named reports or are calculated from the CBA, and anything unconfirmed says so. Data as of {esc(ASOF)}. Spot a mistake? <a href="{fix_href(path)}"{FIX_ATTR}>Suggest a fix</a>.</p><p><a href="/">Open PlainStats</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p></footer></body></html>"""


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
    if not p.gone:  # a released player the roster no longer lists is not under his old team in the hub
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
    if ps.get('rk'):
        play = f" That is {ordn(ps['rk'])} of {ps['n']}." + play
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


def page_intent(p, f, ps):
    # A contract a named report confirms always leads: nearly every search that shows these pages is "<name> contract"
    # or a pay question ("how much does <name> make"), and the confirmed deal is what other sites are slower to explain.
    if p.prov == 'r' and bool(f['total'] or f['apy'] or f['cap']):
        return 'contract'
    if ps:
        return 'stats'
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


def brand(core, n=65):
    """core + ' | PlainStats' when that still fits in n characters, else core alone (titles over about 65 get cut in search results)."""
    return core + ' | PlainStats' if len(core) + 13 <= n else core


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


# ---------------------------------------------------------------- latest: news, injury report, last game
NEWS_BY = {}
for _m in MOVES.get('moves', []):
    for _g in set(_m.get('gids') or []):
        if _g:
            NEWS_BY.setdefault(_g, []).append(_m)
for _v in NEWS_BY.values():
    _v.sort(key=lambda m: m.get('iso') or '', reverse=True)
GAME_AT = {}  # (week, team) -> schedule row, finished games only
for _g in SCHED.get('games', []):
    if _g[6] is not None and _g[7] is not None:
        GAME_AT[(_g[1], _g[4])] = GAME_AT[(_g[1], _g[5])] = _g
INJ_STATUS = {'O': 'Out', 'D': 'Doubtful', 'Q': 'Questionable'}
INJ_PRACTICE = {'D': 'did not practice', 'L': 'limited in practice', 'F': 'full practice'}


def player_news(p, n=2):
    """News items naming this player (by gsis id), newest first, from the last NEWS_DAYS days of the feed."""
    if not p.gid:
        return []
    ref = dt.date.fromisoformat(MOVES.get('asOf') or ASOF)
    cut = (ref - dt.timedelta(days=NEWS_DAYS)).isoformat()
    return [m for m in NEWS_BY.get(p.gid, []) if (m.get('iso') or '') >= cut][:n]


def injury_now(p):
    """'Questionable (ankle), limited in practice' from the latest week's official report, or None if he is not on it."""
    rows = (INJ.get('players') or {}).get(p.gid) or []
    if not rows or rows[-1][0] != INJ.get('thru'):
        return None
    wk, tm, stt, inj, pr = rows[-1]
    bits = [INJ_STATUS.get(stt) or ('Listed' if not pr else INJ_PRACTICE.get(pr, 'listed').capitalize())]
    if inj and inj != 'Not injury related':
        bits[0] += f' ({inj.lower()})'
    elif inj:
        bits[0] += ' (not injury related)'
    if stt and pr in INJ_PRACTICE:
        bits.append(INJ_PRACTICE[pr])
    return wk, ', '.join(bits)


def last_game(p):
    """(label, text) for his newest game in the nflverse weekly stats this season, or None. "Last played" when his team has played since."""
    w = [x for x in (p.hist or {}).get('w') or [] if x[0] <= (HIST.get('thru') or 99)]
    if not w:
        return None
    wk, opp, tm, st = w[-1]
    g = GAME_AT.get((wk, tm))
    team_last = max((k[0] for k in GAME_AT if k[1] == p.team and k[0] <= (HIST.get('thru') or 99)), default=wk)
    label = f'Last game, week {wk}' if wk >= team_last else f'Last played, week {wk}'
    o = TEAMS.get(opp, {}).get('name', opp)
    if g:
        home = g[5] == tm
        us, them = (g[7], g[6]) if home else (g[6], g[7])
        res = 'Won' if us > them else 'Lost' if us < them else 'Tied'
        d = dt.date.fromisoformat(g[2])
        label += f' ({d.strftime("%b")} {d.day})'
        head = f"{res} {us}-{them} {'vs.' if home else 'at'} the {o}"
    else:
        head = f'Against the {o}'
    if tm != p.team:
        head += f" (for the {TEAMS.get(tm, {}).get('name', tm)})"
    lines = stat_lines(st)
    body = '; '.join(f'{k.lower()} {v}' for k, v in lines) if lines else 'no box-score stats'
    return label, f'{head}: {body}.'


def back_since(p, m):
    """A release item reads wrong once he is back: ' He has since returned...' when he has played for this team after that news day."""
    if m.get('kind') != 'Release':
        return ''
    for wk, _opp, tm, _st in reversed((p.hist or {}).get('w') or []):
        g = GAME_AT.get((wk, tm))
        if tm == p.team and g and g[2] > (m.get('iso') or '9999'):
            return f" Since then he has been back with the {TEAMS[p.team]['name']}: he was on their game-day roster in week {wk}."
    return ''


def release_of(p):
    """RELEASED entry when his page should lead with a release this week, else None (back on the team's game-day roster since)."""
    rel = RELEASED.get(p.gid) if p.gid else None
    if not rel or back_since(p, rel['m']):
        return None
    return rel


def latest_html(p, skip=None):
    """The 'Latest' box under the lede: In the news, this week's injury report, last game. Empty when there is nothing to say."""
    rows = []
    for m in player_news(p, 3 if skip else 2):
        if m is skip:  # already the first line of the page
            continue
        src = f' <a href="{esc(m["url"])}" rel="nofollow noopener">{esc(m.get("source") or "Source")}</a>' if m.get('url') else ''
        rows.append(('In the news, ' + esc(m.get('date') or m.get('iso')), f'<b>{esc(m["head"])}.</b> {esc(m.get("plain") or "")}{src}{esc(back_since(p, m))}'))
    inj = injury_now(p)
    if inj:
        rows.append((f'Injury report, week {inj[0]}', esc(inj[1]) + '.'))
    lg = last_game(p)
    if lg:
        rows.append((esc(lg[0]), esc(lg[1])))
    if not rows:
        return ''
    body = ''.join(f'<div><h3>{k}</h3><p>{v}</p></div>' for k, v in rows)
    return (f'<h2>Latest on {esc(p.name)}</h2><div class="card pnews">{body}</div>'
            f'<p class="note">News from the PlainStats news feed, injury status from the NFL\'s official report, game stats from nflverse.</p>')


# ---------------------------------------------------------------- game log (player pages)
# One row per game this season from the nflverse weekly box scores (history.json 'w'), with his share of the team's targets,
# carries and snaps from data/usage.json where it has them. Columns depend on the position; a column nobody filled is dropped.
_USAGE_RAW = _load('usage.json', {'players': [], 'teams': {}})
GAME_SHARE = {}  # gid -> {week: (target share, carry share, snap share)}
for _gid, _n, _pos, _games in _USAGE_RAW.get('players', []):
    for _g in _games:
        _tt = _USAGE_RAW.get('teams', {}).get(_g[1], {}).get(str(_g[0]), [0, 0, 0])
        _sn = _g[5] if len(_g) > 5 else None
        GAME_SHARE.setdefault(_gid, {})[_g[0]] = (_g[2] / _tt[0] if _tt[0] else None, _g[3] / _tt[1] if _tt[1] else None,
                                                  min(1, _sn / _tt[2]) if _sn is not None and len(_tt) > 2 and _tt[2] else None)
_pct = lambda v: '–' if v is None else f'{round(v * 100)}%'
_n0 = lambda st, k: st.get(k) or 0
LOG_COLS = {
    'pass': [('Cmp-Att', lambda st, sh: f"{_n0(st, 'cmp')}-{_n0(st, 'att')}" if st.get('att') else ''), ('Pass yds', lambda st, sh: st.get('pyd')), ('TD', lambda st, sh: st.get('ptd')),
             ('Int', lambda st, sh: st.get('int')), ('Rush yds', lambda st, sh: st.get('ryd'))],
    'run': [('Carries', lambda st, sh: st.get('car')), ('Rush yds', lambda st, sh: st.get('ryd')), ('Catches', lambda st, sh: st.get('rec')), ('Rec yds', lambda st, sh: st.get('reyd')),
            ('TD', lambda st, sh: (_n0(st, 'rtd') + _n0(st, 'retd')) or None), ('Carry share', lambda st, sh: _pct(sh[1]) if sh and sh[1] is not None else ''),
            ('Snap share', lambda st, sh: _pct(sh[2]) if sh and sh[2] is not None else '')],
    'catch': [('Targets', lambda st, sh: st.get('tgt')), ('Catches', lambda st, sh: st.get('rec')), ('Rec yds', lambda st, sh: st.get('reyd')), ('TD', lambda st, sh: st.get('retd')),
              ('Target share', lambda st, sh: _pct(sh[0]) if sh and sh[0] is not None else ''), ('Snap share', lambda st, sh: _pct(sh[2]) if sh and sh[2] is not None else '')],
    'def': [('Tackles', lambda st, sh: st.get('tk')), ('For loss', lambda st, sh: st.get('tfl')), ('Sacks', lambda st, sh: st.get('dsk')), ('QB hits', lambda st, sh: st.get('qbh')),
            ('Passes defended', lambda st, sh: st.get('pd')), ('Int', lambda st, sh: st.get('dint'))],
    'kick': [('Field goals', lambda st, sh: f"{_n0(st, 'fgm')} of {st['fga']}" if st.get('fga') else ''), ('Extra points', lambda st, sh: f"{_n0(st, 'xpm')} of {st['xpa']}" if st.get('xpa') else '')],
    'punt': [('Punts', lambda st, sh: st.get('pun')), ('Punt yds', lambda st, sh: st.get('puy'))],
}
LOG_GROUP = {'QB': 'pass', 'RB': 'run', 'FB': 'run', 'WR': 'catch', 'TE': 'catch', 'EDGE': 'def', 'IDL': 'def', 'LB': 'def', 'CB': 'def', 'S': 'def', 'K': 'kick', 'P': 'punt'}


def game_result(wk, tm):
    """('vs. the Giants' | 'at the Giants', 'W 24-17' | '') for a team's game in a week, from the schedule."""
    g = GAME_AT.get((wk, tm))
    if not g:
        return None
    home = g[5] == tm
    opp = g[4] if home else g[5]
    us, them = (g[7], g[6]) if home else (g[6], g[7])
    return f"{'vs.' if home else 'at'} {TEAMS.get(opp, {}).get('name', opp)}", f"{'W' if us > them else 'L' if us < them else 'T'} {us}-{them}", g


def game_path(g):
    return f'/game/{SEASON_YEAR}-{g[1]:02d}-{g[4].lower()}-{g[5].lower()}'


def usage_trend(p, weeks):
    """One sentence on his share of the work in his last three games against the games before, or ''. Needs five games with a share."""
    grp = LOG_GROUP.get(p.pos)
    i, word = {'catch': (0, 'targets'), 'run': (1, 'carries')}.get(grp, (None, None))
    sh = GAME_SHARE.get(p.gid, {})
    vals = [sh[w][i] for w in weeks if i is not None and w in sh and sh[w][i] is not None]
    if len(vals) < 5:
        return ''
    late, early = sum(vals[-3:]) / 3, sum(vals[:-3]) / len(vals[:-3])
    d = round(late * 100) - round(early * 100)
    how = 'about the same as' if abs(d) < 3 else f"{'up' if d > 0 else 'down'} from"
    return (f"Over his last three games {p.name} has had {round(late * 100)}% of his team's {word}, {how} {round(early * 100)}% in his games before that.")


def gamelog_html(p):
    w = [x for x in (p.hist or {}).get('w') or [] if x[0] <= (HIST.get('thru') or 99)]
    cols = LOG_COLS.get(LOG_GROUP.get(p.pos))
    if not w or not cols:
        return ''
    sh = GAME_SHARE.get(p.gid, {})
    cells = [[fn(st, sh.get(wk)) for _l, fn in cols] for wk, _o, _t, st in w]
    keep = [j for j in range(len(cols)) if any(c[j] not in (None, '', 0) for c in cells)]
    if not keep:
        return ''
    show = lambda v: '–' if v in (None, '') else (f'{v:,}' if isinstance(v, int) else f'{v:g}' if isinstance(v, float) else esc(v))
    tr = ''
    for (wk, opp, tm, _st), c in zip(w, cells):
        r = game_result(wk, tm)
        where = esc(r[0]) if r else esc(TEAMS.get(opp, {}).get('name', opp))
        res = f'<a href="{game_path(r[2])}">{esc(r[1])}</a>' if r else '–'
        tr += f'<tr><td>{wk}</td><td class="nw">{where}</td><td class="nw">{res}</td>' + ''.join(f'<td class="r">{show(c[j])}</td>' for j in keep) + '</tr>'
    th = ''.join(f'<th class="r">{esc(cols[j][0])}</th>' for j in keep)
    shares = any(cols[j][0].endswith('share') for j in keep)
    trend = usage_trend(p, [x[0] for x in w])
    return (f'<h2>{esc(p.name)} game log, {SEASON_YEAR}</h2><div class="card scroll"><table><thead><tr><th>Week</th><th>Opponent</th><th>Result</th>{th}</tr></thead><tbody>{tr}</tbody></table></div>'
            + (f'<p>{esc(trend)} <a href="/usage-risers">This week\'s usage risers</a></p>' if trend else '')
            + f'<p class="note">Every game he has a box score for, through week {HIST.get("thru")}. Source: nflverse.'
            + (' Shares are his part of the team\'s targets, carries or snaps in that game.' if shares else '') + '</p>')


# ---------------------------------------------------------------- player pages
URLS = []  # (path, priority, changefreq)


def released_page(p, f, rel):
    """(title, description, h1, first line HTML, FAQ) for a page that leads with this week's release (RELEASED).
    The words come from the news item (moves.json, a named report); contract figures only from contract_facts()."""
    m, T, n = rel['m'], TEAMS[p.team], p.name
    verb, date = rel['verb'], m.get('date') or m.get('iso')
    vb = 'waive' if verb == 'waived' else 'release'
    role = POSNAME.get(p.pos, p.pos)
    plain = m.get('plain') or ''
    src = m.get('source') or 'a named report'
    first = f"The {T['full']} {verb} {n}, {article(role)} {role}, on {date}."
    title = brand(f"{n} {verb} by the {T['name']} on {date}")
    line = season_line(p)
    desc = pack([first, re.split(r'(?<=[.!?])\s+(?=[A-Z])', plain)[0], line and line[0].upper() + line[1:] + '.'])  # the report's first sentence only, so it reads in order
    link = f' <a href="{esc(m["url"])}" rel="nofollow noopener">{esc(src)}</a>' if m.get('url') else ''
    lede = f'<p class="lede"><b>{esc(first)}</b> {esc(plain)}{link}</p>'
    where = ('He is no longer on their roster in the nflverse roster data.' if p.gone else
             'He was still listed on their roster in the latest nflverse roster data.')
    faq = [(f"Why did the {T['name']} {vb} {n}?", plain or f"{src} reported the move on {date} and gave no reason."),
           (f"Is {n} still on the {T['name']}?", f"The {T['full']} {verb} him on {date}, {src} reported. {where}")]
    if f['total'] or f['apy'] or f['cap']:
        calc = {'f': ' PlainStats calculated it from the draft slot and the CBA rookie scale.', 'm': ' PlainStats calculated it from the CBA league minimum.',
                'p': ' Practice squad pay is set by the CBA.'}.get(p.prov, '')
        faq.append((f"What was {poss(n)} contract?", deal_sentence(p, f, rookie=p.prov == 'f') + f" He was on it when the {T['name']} {verb} him." + calc))
    else:
        faq.append((f"What was {poss(n)} contract?", 'PlainStats shows contract figures only after a named report confirms them, and this one is still being verified.'))
    return title, desc, f"{n} {verb} by the {T['name']}", lede, faq


def build_player(p):
    T = TEAMS[p.team]
    f = contract_facts(p)
    summary = player_summary(p, f)
    faq = player_faq(p, f)
    pay_q = pay_questions(p, f)
    ps = plainscore(p, f)
    if ps:
        faq.insert(1, (f"What is {poss(p.name)} PlainScore?", plainscore_sentence(p, ps) + ' PlainScore ranks his play rating against everyone at his position with enough snaps.'))
    path = f'/players/{p.slug}'
    has_deal = bool(f['total'] or f['apy'] or f['cap'] or f['base'])
    rel = release_of(p)
    intent = 'released' if rel else page_intent(p, f, ps)
    if rel:  # the week's news leads: title, first line and FAQ (released_page)
        title, desc, h1, rel_lede, faq = released_page(p, f, rel)
        if ps:
            faq.insert(1, (f"What is {poss(p.name)} PlainScore?", plainscore_sentence(p, ps) + ' PlainScore ranks his play rating against everyone at his position with enough snaps.'))
    else:
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

    rows = [('Position', esc(POSNAME.get(p.pos, p.pos)).capitalize()), ('Last team' if rel else 'Team', f'<a href="/teams/{T["slug"]}">{esc(T["full"])}</a>')]
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
    if not p.gone:  # the app has no sheet for a player off every roster
        PAGEMAP['p'][f'p-{slugify(p.name)}-{p.team.lower()}'] = p.slug
    deal_html = facts_html(rows) + src_html
    if rel and (f['total'] or f['apy'] or f['cap']):
        deal_html += f'<p class="note">The contract he was on when the {esc(T["name"])} {rel["verb"]} him.</p>'
    # Stats-first pages put the season (PlainScore, stats) above the contract; the rest lead with the contract.
    stats_html += gamelog_html(p)
    main_html = (plainscore_html(p, ps) + stats_html + deal_html) if intent in ('stats', 'released') else (deal_html + plainscore_html(p, ps) + stats_html)
    # Pages that lead with a confirmed contract open with the pay questions people search, each a heading with a
    # one-sentence answer, in place of the summary (which says the same). They are left out of the "Quick answers" at
    # the bottom so the numbers are not repeated, and stay in the FAQ JSON-LD because they are on the page.
    pay_first = intent in ('contract', 'rookie', 'salary') and has_deal
    if rel:
        top_html, rest = rel_lede, faq
    elif pay_first:
        top_html = '<section class="pay">' + ''.join(f'<h2>{esc(q)}</h2><p>{esc(a)}</p>' for q, a in pay_q) + '</section>'
        shown = {q for q, _ in pay_q}
        rest = [x for x in faq if x[0] not in shown]
    else:
        top_html, rest = f'<p class="lede">{esc(summary)}</p>', faq
    body = (f'<div class="id">{img_html}<div><h1>{esc(h1)}</h1></div></div>'
            f'{top_html}{latest_html(p, rel and rel["m"])}{main_html}'
            f'{faq_html(rest) if rest else ""}'
            + ('<p><a class="cta" href="/news">See every move this week in the PlainStats app</a></p>' if p.gone else
               f'<p><a class="cta" href="{esc(spa)}">See {esc(p.name)} in the PlainStats app</a><a class="cta alt" rel="nofollow" href="{esc(spa)}?share=1">Share</a></p>') +
            f'{vs_links_html(p)}'
            f'<h2>More on the {esc(T["name"])}</h2><ul class="chips"><li><a href="/teams/{T["slug"]}">{esc(T["full"])} roster and contracts</a></li><li><a href="/teams/{T["slug"]}/cap">How much cap space do the {esc(T["name"])} have?</a></li><li><a href="/teams/{T["slug"]}/dead-money">{esc(T["name"])} dead money</a></li></ul>'
            f'{player_doors(p, f, T)}{signup_html()}')
    person = {'@type': 'Person', 'name': p.name, 'jobTitle': f"{POSNAME.get(p.pos, p.pos).capitalize()}, NFL",
              'url': SITE + path, 'memberOf': {'@type': 'SportsTeam', 'name': T['full'], 'sport': 'American football', 'url': f'{SITE}/teams/{T["slug"]}'}}
    if rel:  # let go: not a member of that team any more
        del person['memberOf']
    if img:
        person['image'] = img
    graph = [person, {'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}, 'about': {'@type': 'Person', 'name': p.name}},
             faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Players', '/players'), (p.name, path)])]
    crumbs = [('PlainStats', '/'), ('Players', '/players'), (p.name, path)]
    # Google is shown a page only when it says something another site does not: a PlainScore (he has played enough to be
    # rated) or a contract a named report confirms. Rookie-scale, minimum-salary and unverified pages without a PlainScore
    # still exist and are linked, but carry noindex and stay out of the sitemap. Exception (owner, Nov 23, 2026): a page
    # Google showed 20+ times in a week (data/search_seen.json) stays indexable, if its contract figure is confirmed.
    reported = p.prov == 'r' and bool(f['total'] or f['apy'] or f['cap'])
    # A release this week (RELEASED, owner, Nov 23, 2026) is news other pages are slow to cover: indexable for RELEASE_DAYS.
    thin = not rel and (not has_deal or not (ps or reported or p.slug in SEARCH_SEEN))
    card_kw = player_card(p, f, T, has_deal)
    if rel:
        card_kw['e'] = f"{rel['verb'].capitalize()} {rel['m'].get('date') or ''}".strip()
    card = og_add('players', p.slug, **card_kw)
    write(f'players{"/" + p.slug}.html', shell(path, title, desc, body, graph, robots='noindex,follow' if thin else None, image=img, crumbs=crumbs, card=card))
    if not thin:
        URLS.append((path, '0.7' if p.prov == 'r' or rel else '0.5', 'daily' if rel else 'weekly'))


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


POS_ORDER = {k: i for i, k in enumerate(['QB', 'RB', 'FB', 'WR', 'TE', 'LT', 'LG', 'C', 'RG', 'RT', 'EDGE', 'IDL', 'LB', 'CB', 'S', 'K', 'P', 'LS'])}


def contract_cell(p, f):
    """Roster table: yearly pay only when contract_facts() confirms it, and where it comes from; otherwise what kind of deal, or being verified."""
    if p.prov == 'r' and (f['apy'] or f['total']):
        return f"{mon(f['apy'])} a year" if f['apy'] else f"{mon(f['total'])} total"
    if p.prov == 'f' and f['apy']:
        return f"Rookie deal, {mon(f['apy'])} a year"
    if p.prov == 'm':
        return 'League minimum'
    if p.prov == 'p':
        return 'Practice squad'
    return 'Being verified'


def team_roster_html(tid, nick):
    """Every player on the team: position, age, PlainScore, one season number and his contract status."""
    rows = []
    for p in PLAYERS:
        if p.team != tid:
            continue
        f = contract_facts(p)
        ps = plainscore(p, f)
        rows.append((POS_ORDER.get(p.pos, 99), -(ps['s'] if ps else -1), p.name, p, f, ps))
    if not rows:
        return ''
    rows.sort(key=lambda r: r[:3])
    tr = ''
    for _o, _s, _n, p, f, ps in rows:
        hs = headline_stat(p)
        score = f'<b style="color:{PS_COLOR(ps["s"])}">{ps["s"]}</b>' if ps else '–'
        tr += (f'<tr><td>{player_name_link(p) if hasattr(p, "slug") else esc(p.name)}</td><td>{esc(p.pos)}</td><td class="r">{esc(p.age) if p.age else "–"}</td>'
               f'<td class="r">{score}</td><td>{esc(hs[0] + " " + hs[1]) if hs else "–"}</td><td>{esc(contract_cell(p, f))}</td></tr>')
    rated = sum(1 for r in rows if r[5])
    return (f'<h2>{esc(nick)} roster, {SEASON_YEAR}</h2><div class="card scroll"><table><thead><tr><th>Player</th><th>Pos</th><th class="r">Age</th><th class="r">PlainScore</th><th>{SEASON_YEAR}</th><th>Contract</th></tr></thead><tbody>{tr}</tbody></table></div>'
            f'<p class="note">{len(rows)} players, {rated} with a PlainScore: a 0 to 100 rank of his play against everyone at his position with enough snaps, through week {PSCORE["week"]} (<a href="/cap-101">how it works</a>). '
            'Yearly pay is shown only when a named report confirms it or it follows from the CBA rookie scale; the rest say what kind of deal it is or that it is being verified. Stats from nflverse.</p>')


def wk_tiers_link():
    """Link from a team page to the static weekly tiers page for the week data/tiers.json covers, once it is saved."""
    w = TIERS.get('thru')
    return f' · <a href="/weekly/team-tiers-week-{w}">Week {w} tiers, saved</a>' if w and (DATA / 'weekly' / f'tiers-{w}.json').exists() else ''


def team_form(t):
    """(sentence, html) on where the team sits in the weekly tiers (data/tiers.json: EPA per play on offense and defense), or (None, '')."""
    all_t = TIERS.get('teams') or {}
    x = all_t.get(t['id'])
    if not x:
        return None, ''
    off_r = sorted(all_t, key=lambda k: -all_t[k]['off']).index(t['id']) + 1
    def_r = sorted(all_t, key=lambda k: all_t[k]['def']).index(t['id']) + 1
    tier = next((n for i, n, _d in TIERS.get('tiers', []) if i == x['tier']), f"Tier {x['tier']}")
    tdesc = next((d for i, _n, d in TIERS.get('tiers', []) if i == x['tier']), '')
    n = len(all_t)
    sent = (f"Through week {TIERS.get('thru')} the {t['name']} rank {ordn(x['rank'])} of {n} teams by net EPA per play, which puts them in {tier}"
            f"{' (' + tdesc.lower() + ')' if tdesc else ''}. The offense ranks {ordn(off_r)} and the defense {ordn(def_r)}.")
    facts = [('Net EPA per play', f"{x['net']:+.3f} ({ordn(x['rank'])})"), ('Offense EPA per play', f"{x['off']:+.3f} ({ordn(off_r)})"),
             ('Defense EPA per play allowed', f"{x['def']:+.3f} ({ordn(def_r)} best)"),
             ('Offense success rate', f"{x['offSr'] * 100:.1f}%"), ('Success rate allowed', f"{x['defSr'] * 100:.1f}%")]
    html = (f'<h2>How good are the {esc(t["name"])} this season?</h2><p>{esc(sent)}</p>{facts_html(facts)}'
            f'<p class="note">EPA (expected points added) per play measures how much each play helped the team score; for a defense, lower is better. '
            f'<a href="/learn/epa">What is EPA?</a> · <a href="/learn/success-rate">What is success rate?</a> · <a href="/team-tiers">All 32 teams in this week\'s tiers</a>{wk_tiers_link()}. From nflverse play-by-play.</p>')
    return sent, html


def kickoff(hhmm):
    try:
        h, m = map(int, hhmm.split(':'))
    except ValueError:
        return ''
    return f"{(h - 1) % 12 + 1}:{m:02d} {'PM' if h >= 12 else 'AM'} ET"


def team_schedule(t):
    """(next-game sentence or None, html): every game this season with the result or the kickoff time."""
    games = sorted((g for g in SCHED.get('games', []) if t['id'] in (g[4], g[5])), key=lambda g: g[1])
    if not games:
        return None, ''
    tr, nxt = '', None
    for g in games:
        home = g[5] == t['id']
        opp = TEAMS.get(g[4] if home else g[5], {})
        d = dt.date.fromisoformat(g[2])
        where = f"{'vs.' if home else 'at'} " + (f'<a href="/teams/{opp["slug"]}">{esc(opp["name"])}</a>' if opp else esc(g[4] if home else g[5]))
        if g[6] is not None and g[7] is not None:
            us, them = (g[7], g[6]) if home else (g[6], g[7])
            res = f'<a href="{game_path(g)}">{"W" if us > them else "L" if us < them else "T"} {us}-{them}</a>'
        else:
            res = f'<a href="{game_path(g)}">{esc(kickoff(g[3]) or "To be played")}</a>'
            if not nxt:
                nxt = (f"The {t['name']} play {'the ' + opp.get('name', '') + ' at home' if home else 'at the ' + opp.get('name', '')} on {d.strftime('%A, %b')} {d.day} "
                       f"(week {g[1]})" + (f", {kickoff(g[3])}" if kickoff(g[3]) else '') + '.')
        tr += f'<tr><td>{g[1]}</td><td class="nw">{d.strftime("%b")} {d.day}</td><td class="nw">{where}</td><td class="nw">{res}</td></tr>'
    html = (f'<h2>{esc(t["name"])} schedule and results, {SEASON_YEAR}</h2>' + (f'<p>{esc(nxt)}</p>' if nxt else '')
            + f'<div class="card scroll"><table><thead><tr><th>Week</th><th>Date</th><th>Opponent</th><th>Result or kickoff</th></tr></thead><tbody>{tr}</tbody></table></div>'
            '<p class="note">Each result opens the game page, with the PlainStats model\'s pick and the injury report. Kickoff times are Eastern. From the nflverse schedule.</p>')
    return nxt, html


def team_injuries_html(t):
    """This week's official injury report for the team's players, or '' when nobody is listed."""
    rows = []
    for p in PLAYERS:
        if p.team == t['id'] and p.gid:
            inj = injury_now(p)
            if inj:
                rows.append((POS_ORDER.get(p.pos, 99), p, inj))
    if not rows:
        wk = INJ.get('thru')
        if not wk:
            return ''
        played = any(t['id'] in (g[4], g[5]) for g in SCHED.get('games', []) if g[1] == wk)
        why = (f"No {t['name']} players were on the official injury report for week {wk}." if played else
               f"The {t['name']} had a bye in week {wk}, so they were not on that week's official injury report.")
        return (f'<h2>{esc(t["name"])} injury report, week {wk}</h2><p>{esc(why)}</p>'
                '<p class="note">From the NFL\'s official injury report, through nflverse.</p>')
    rows.sort(key=lambda r: (r[0], r[1].name))
    li = ''.join(f'<li>{player_name_link(p) if hasattr(p, "slug") else esc(p.name)} <span class="note">{esc(p.pos)}</span>: {esc(inj[1])}</li>' for _o, p, inj in rows)
    return (f'<h2>{esc(t["name"])} injury report, week {rows[0][2][0]}</h2><ul class="list">{li}</ul>'
            '<p class="note">From the NFL\'s official injury report, through nflverse.</p>')


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
    form_sent, form_html = team_form(t)
    next_sent, sched_html = team_schedule(t)
    if rec:
        faq.insert(0, (f"What is the {nick}' record?" if nick.endswith('s') else f"What is the {nick}'s record?",
                       f"The {full} are {rec[0]} in {SEASON_YEAR}, with {rec[1]['pf']} points scored and {rec[1]['pa']} allowed."))
    if next_sent:
        faq.insert(1 if rec else 0, (f'Who do the {nick} play next?', next_sent))
    if form_sent:
        faq.append((f'How good are the {nick} this season?', form_sent))
    top_html = reported_table(top, f'{esc(nick)} contracts confirmed by named reports')
    roster_html = team_roster_html(tid, nick)
    facts = [(f'{SEASON_YEAR} cap space', space_txt), ('Dead money', mon(t['dead'])), ('League cap', mon(CAP)), ('Division', esc(t['div']))]
    if rec:
        facts.insert(0, ('Record', esc(rec[0])))
        facts.insert(1, ('Points for and against', f"{rec[1]['pf']} to {rec[1]['pa']}"))
        if rec[1].get('coach'):
            facts.append(('Head coach', esc(rec[1]['coach'])))
    logo = f'<img src="{esc(t["logo"])}" alt="{esc(full)} logo" width="64" height="64" loading="lazy" decoding="async" onerror="this.remove()">' if t.get('logo') else ''
    path = f'/teams/{slug}'
    title = brand(f"{full}: cap space, contracts and roster")
    desc = clip(summary, 158)
    body = (f'<div class="id">{logo}<h1>{esc(full)} cap space, contracts and roster</h1></div><p class="lede">{esc(summary)}</p>{facts_html(facts)}'
            f'<ul class="chips"><li><a href="/teams/{slug}/cap">How much cap space do the {esc(nick)} have?</a></li><li><a href="/teams/{slug}/dead-money">{esc(nick)} dead money</a></li><li><a href="/team/{tid.lower()}">Open the {esc(nick)} page in the app</a></li><li><a rel="nofollow" href="/team/{tid.lower()}?share=1">Share the {esc(nick)} as an image</a></li></ul>'
            f'{form_html}{sched_html}{team_injuries_html(t)}{roster_html}{top_html}{faq_html(faq)}'
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
    title = brand(f"How much cap space do the {nick} have? {space_txt} in {SEASON_YEAR}")
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
    title = brand(f"{nick} dead money: {mon(t['dead'])} on the {SEASON_YEAR} cap")
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
    core = f"{pr['name']} 2027 NFL Draft profile: stats and big board rank"
    title = brand(core if len(core) <= 65 else f"{pr['name']} 2027 NFL Draft profile and stats")
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
    title = brand('NFL team cap space, contracts and dead money')
    desc = 'Cap space, dead money and contracts for all 32 NFL teams, explained in plain English.'
    _rec = lambda t: (record_line(t) or ['–'])[0]
    _tier = lambda t: (lambda x: f"{ordn(x['rank'])}, Tier {x['tier']}" if x else '–')((TIERS.get('teams') or {}).get(t['id']))
    rows = ''.join(f'<tr><td><a href="/teams/{t["slug"]}">{esc(t["full"])}</a></td><td class="r">{esc(_rec(t))}</td><td class="r">{esc(_tier(t))}</td><td class="r">{mon(t["space"])}</td><td class="r">{mon(t["dead"])}</td><td><a href="/teams/{t["slug"]}/cap">cap</a> · <a href="/teams/{t["slug"]}/dead-money">dead money</a></td></tr>' for t in sorted(TEAMS.values(), key=lambda t: t['full']))
    faq = [('How much cap space does each NFL team have?', f"Each team's cap space is listed here as of {ASOF}. The {SEASON_YEAR} league cap is {mon(CAP)}."), ('Which NFL team has the most cap space?', f"The {by_space[0]['full']} have the most cap space at about {mon(by_space[0]['space'])}, as of {ASOF}.")]
    body = (f'<h1>NFL teams: cap space and dead money</h1><p class="lede">All 32 teams, as of {esc(ASOF)}: record, rank by net EPA per play through week {TIERS.get("thru")}, cap space and dead money. Tap a team for its roster, schedule, injury report and contracts.</p>'
            f'<div class="card scroll"><table><thead><tr><th>Team</th><th class="r">Record</th>{th_x("EPA rank", "epa", "r")}<th class="r">Cap space</th>{th_x("Dead money", "dead-money", "r")}<th>More</th></tr></thead><tbody>{rows}</tbody></table></div>{faq_html(faq)}')
    graph = [{'@type': 'CollectionPage', 'name': title, 'url': SITE + path, 'description': desc, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}}, faq_ld(faq), crumbs_ld([('PlainStats', '/'), ('Teams', path)])]
    card = og_add('pages', 'teams', m='brand', c=OG_BRAND, e='PlainStats', t='All 32 NFL teams', s='Cap space and dead money', n=mon(CAP, 0), l=f'{SEASON_YEAR} salary cap per team',
                  x='Explained in plain English')
    write('teams/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Teams', path)], card=card))
    URLS.append((path, '0.9', 'daily'))

    # players hub
    path = '/players'
    title = brand('NFL player stats and contracts, explained in plain English')
    desc = f'{SEASON_YEAR} stats and contracts for NFL players, explained in plain English, by team, with head-to-head player comparisons.'
    blocks = ''
    for t in sorted(TEAMS.values(), key=lambda t: t['full']):
        ps = sorted(PAGE_BY_TEAM.get(t['id'], []), key=lambda p: p.name)
        if ps:
            blocks += f'<h2><a href="/teams/{t["slug"]}">{esc(t["full"])}</a></h2><ul class="list">' + ''.join(f'<li>{player_name_link(p)} <span class="note">{esc(p.pos)}</span></li>' for p in ps) + '</ul>'
    vs = ''
    for g in ('QB', 'RB', 'WR', 'TE'):
        L = sorted((x for x in VS_PAGES if VS_GROUP[x[1].pos] == g), key=lambda x: (x[1].name, x[2].name))
        if L:
            vs += f'<h3>{esc(VS_WORD[g].capitalize())}s</h3><ul class="list">' + ''.join(f'<li><a href="/players/{s}">{esc(a.name)} vs. {esc(b.name)}</a></li>' for s, a, b in L) + '</ul>'
    if vs:
        vs = f'<h2 id="comparisons">Player comparisons</h2><p>{len(VS_PAGES)} head-to-head pages with this season\'s numbers side by side.</p>{vs}'
    body = f'<h1>NFL player stats and contracts</h1><p class="lede">{sum(not p.gone for p in PAGES)} players with a confirmed contract or {SEASON_YEAR} stats, grouped by team. Contracts still being verified are not shown until a named report confirms them. <a href="#comparisons">Player comparisons</a> are at the bottom.</p>{blocks}{vs}'
    graph = [{'@type': 'CollectionPage', 'name': title, 'url': SITE + path, 'description': desc, 'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'}}, crumbs_ld([('PlainStats', '/'), ('Players', path)])]
    card = og_add('pages', 'players', m='brand', c=OG_BRAND, e='PlainStats', t='NFL player stats and contracts', s='Explained in plain English', n=f'{sum(not p.gone for p in PAGES):,}', l=f'players with a contract or {SEASON_YEAR} stats',
                  x='Browse every team')
    write('players/index.html', shell(path, title, desc, body, graph, crumbs=[('PlainStats', '/'), ('Players', path)], card=card))
    URLS.append((path, '0.9', 'daily'))

    # draft hub
    path = '/draft'
    title = brand('2027 NFL Draft prospects: big board, stats and profiles')
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
        title=brand('What is EPA in football? Expected points added, explained'),
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
        title=brand('What is success rate in football? Explained in plain English'),
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
        title=brand('What is a cap hit in the NFL? Explained in plain English'),
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
        title=brand('What is dead money in the NFL? Explained in plain English'),
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
        title=brand('What is guaranteed money in an NFL contract? Explained'),
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
    title = brand('NFL stats and contract terms explained in plain English')
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


# ---------------------------------------------------------------- static weekly pages (/weekly/...)
# One plain-HTML page per finished week for the three weekly app views, so the table is in the HTML Google reads (the app draws
# them with script): /weekly/usage-risers-week-<n>, /weekly/team-tiers-week-<n>, /weekly/power-rankings-week-<n>, and the /weekly
# hub. Built from the snapshots in data/weekly/ (tools/refresh_helpers.py weekly: usage and power rankings exported from the
# built page itself, tiers copied from data/tiers.json), so the numbers match the app's. Power rankings and tiers keep no history
# in the data, so their pages start with the first week saved. No contract figures on these pages.
WEEKLY_DIR = DATA / 'weekly'
WK_KINDS = [  # kind, file prefix, page name, app path
    ('usage', 'usage-risers', 'Usage risers', '/usage-risers'),
    ('tiers', 'team-tiers', 'Team tiers', '/team-tiers'),
    ('power', 'power-rankings', 'Power rankings', '/power-rankings'),
]
PAGE_BY_GID = {}


def weekly_snaps():
    out = {k: {} for k, *_ in WK_KINDS}
    for f in sorted(WEEKLY_DIR.glob('*.json')) if WEEKLY_DIR.exists() else []:
        m = re.fullmatch(r'(usage|tiers|power)-(\d+)\.json', f.name)
        if m:
            out[m.group(1)][int(m.group(2))] = json.loads(f.read_text())
    return out


def wk_path(kind, w):
    pre = next(x[1] for x in WK_KINDS if x[0] == kind)
    return f'/weekly/{pre}-week-{w}'


def wk_nav(kind, w, weeks):
    prev = max([x for x in weeks if x < w], default=None)
    nxt = min([x for x in weeks if x > w], default=None)
    parts = [f'<a href="{wk_path(kind, prev)}">← Week {prev}</a>' if prev else '<span></span>',
             f'<a href="/weekly">All weeks</a>',
             f'<a href="{wk_path(kind, nxt)}">Week {nxt} →</a>' if nxt else '<span></span>']
    return '<nav class="wknav" aria-label="Other weeks">' + ''.join(parts) + '</nav>'


def wk_other(w, have, kind):
    """Chips to the other two weekly pages for the same week, when they exist."""
    items = [f'<li><a href="{wk_path(k, w)}">{esc(n)}, week {w}</a></li>' for k, _p, n, _a in WK_KINDS if k != kind and w in have[k]]
    return f'<h2>Also from week {w}</h2><ul class="chips">{"".join(items)}<li><a href="/weekly">Every week</a></li></ul>' if items else ''


def pct(v):
    return '–' if v is None else f'{round(v * 100)}%'


def pts(v):
    if v is None:
        return '–'
    n = round(v * 100)
    return f'+{n} pts' if n > 0 else f'−{-n} pts' if n < 0 else '0 pts'


def tname(tid):
    return TEAMS[tid]['name'] if tid in TEAMS else tid


def tposs(tid):
    n = tname(tid)
    return n + ("'" if n.endswith('s') else "'s")


def wk_player(r):
    p = PAGE_BY_GID.get(r['gid'])
    return f'<a href="/players/{p.slug}">{esc(r["n"])}</a>' if p else esc(r['n'])


USAGE_KIND = {  # list key: (heading, now, before, change, games before, count words)
    't': ('Target share', 's', 'sb', 'ds', 'np', lambda r: f"{r['tg']} of {r['tt']} targets"),
    'c': ('Carry share', 'cs', 'cb', 'dc', 'np', lambda r: f"{r['ca']} of {r['tc']} carries"),
    's': ('Snap share', 'ss', 'ssb', 'dss', 'nps', lambda r: f"{r['sn']} of {r['ts']} snaps"),
}


def usage_table(rows, k, up):
    head, now, was, chg, npk, cnt = USAGE_KIND[k]
    if not rows:
        return '<p class="note">No one qualified this week.</p>'
    body = ''.join(
        f'<tr><td class="r">{i + 1}</td><td>{wk_player(r)}<span class="sub">{esc(r["pos"])} · {esc(tname(r["t"]))} · {cnt(r)}</span></td>'
        f'<td class="r">{pct(r[now])}</td><td class="r">{pct(r[was]) if r[npk] else "–"}</td><td class="r {"up" if up else "dn"}">{pts(r[chg])}</td></tr>'
        for i, r in enumerate(rows))
    return (f'<div class="scroll"><table><thead><tr><th class="r">#</th><th>Player</th><th class="r">Week</th><th class="r">Before</th>'
            f'<th class="r">Change</th></tr></thead><tbody>{body}</tbody></table></div>')


def usage_take(d, w):
    c = [(r, 't') for r in d['tUp'][:1]] + [(r, 'c') for r in d['cUp'][:1]]
    if not c:
        return ''
    r, k = max(c, key=lambda x: x[0]['ds'] if x[1] == 't' else x[0]['dc'])
    a, b = (r['sb'], r['s']) if k == 't' else (r['cb'], r['cs'])
    what = f"of the {tposs(r['t'])} {'targets' if k == 't' else 'carries'}"
    if not r['np'] or a is None:
        return f"Biggest jump in week {w}: {r['n']} took {pct(b)} {what} in his first game this season."
    return f"Biggest jump in week {w}: {r['n']} went from {pct(a)} to {pct(b)} {what}."


def build_weekly_usage(w, d, have):
    weeks = sorted(have['usage'])
    path = wk_path('usage', w)
    mn = d.get('min') or {'t': 5, 'c': 8, 's': .5, 'sb': .6}
    take = usage_take(d, w)
    title = brand(f'Usage risers, week {w} {SEASON_YEAR}: target, carry and snap share')
    lead = [r for r in (d['tUp'][:1] + d['cUp'][:1] + d['sUp'][:1])]
    names = ', '.join(dict.fromkeys(r['n'] for r in lead))
    desc = clip(f'{take} Week {w} target, carry and snap share risers and fallers' + (f', led by {names}' if names else '') + '.', 158)
    sections = [('Risers', True, [('tUp', 't', f"Pass catchers with {mn['t']}+ targets this week"), ('cUp', 'c', f"Ball carriers with {mn['c']}+ carries this week"),
                                  ('sUp', 's', f"Played {round(mn['s'] * 100)}%+ of the offense's snaps this week")]),
                ('Fallers', False, [('tDn', 't', f"Had {mn['t']}+ targets a game over 2+ earlier games"), ('cDn', 'c', f"Had {mn['c']}+ carries a game over 2+ earlier games"),
                                    ('sDn', 's', f"Played {round(mn['sb'] * 100)}%+ of the snaps over 2+ earlier games")])]
    html = ''
    for name, up, lists in sections:
        html += f'<h2>{name}: {"biggest gains" if up else "biggest drops"} in share of the team\'s work</h2>'
        for key, k, sub in lists:
            html += f'<h3>{USAGE_KIND[k][0]} {"risers" if up else "fallers"}</h3><p class="note">{esc(sub)}.</p>'
            if k == 's' and not d.get('snaps'):
                html += f'<p class="note">Snap counts for week {w} were not out when this page was built.</p>'
            else:
                html += usage_table(d.get(key) or [], k, up)
    faq = []
    if d['tUp']:
        r = d['tUp'][0]
        faq.append((f'Who had the biggest target share jump in week {w}?', f"{r['n']} ({r['pos']}, {tname(r['t'])}): {pct(r['s'])} of his team's targets ({r['tg']} of {r['tt']}), up from {pct(r['sb'])} in his earlier games, a change of {pts(r['ds'])}."))
    if d['cUp']:
        r = d['cUp'][0]
        faq.append((f'Who gained the most carries in week {w}?', f"{r['n']} ({r['pos']}, {tname(r['t'])}) took {pct(r['cs'])} of his team's carries ({r['ca']} of {r['tc']}), up from {pct(r['cb'])} before."))
    if d['tDn']:
        r = d['tDn'][0]
        faq.append((f'Whose role shrank the most in week {w}?', f"{r['n']} ({r['pos']}, {tname(r['t'])}) fell to {pct(r['s'])} of the targets from {pct(r['sb'])} over his earlier games ({pts(r['ds'])})."))
    faq.append(('What is target share?', "A player's targets divided by all of his team's targets in that game. Carry share is the same with carries (quarterback runs count in the team total), and snap share is his share of the offense's snaps. \"Before\" is his share over his earlier games this season, so a jump means a bigger role than he has had."))
    body = (f'<h1>Usage risers and fallers, week {w}</h1><p class="lede">{esc(take or f"Who gained and lost a share of the work in week {w}.")}</p>'
            f'<p>Whose share of his team\'s targets, carries and snaps jumped or dropped in week {w} of the {SEASON_YEAR} NFL season, compared with his earlier games. '
            f'Change is in percentage points of the team\'s share. <a href="/usage-risers">Open the live usage risers</a> to sort every player or pick another week.</p>'
            f'{wk_nav("usage", w, weeks)}{html}'
            f'<p class="note">Source: nflverse weekly box scores and snap counts (CC BY 4.0), regular season. A game counts when the player recorded a stat or took an offensive snap. Fantasy points use PPR scoring.</p>'
            f'{faq_html(faq)}{wk_other(w, have, "usage")}'
            + doors_html([('Usage risers, live', '/usage-risers', 'Every running back, receiver and tight end, sortable'), ('Season stats', '/stats', f'Every {SEASON_YEAR} stat leader'),
                          ('Player ratings', '/player-ratings', 'How players rank on the field this season'), ('Compare players', '/compare', 'Any two players side by side')])
            + signup_html())
    crumbs = [('PlainStats', '/'), ('Weekly', '/weekly'), (f'Usage risers, week {w}', path)]
    graph = [{'@type': 'Article', 'headline': f'Usage risers and fallers, week {w}', 'description': desc, 'url': SITE + path, 'dateModified': LM_TOKEN,
              'author': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}, 'publisher': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld(crumbs)]
    top = (d['tUp'] or d['cUp'] or [None])[0]
    card = og_add('pages', f'weekly-usage-{w}', m='brand', c=OG_BRAND, e=f'Week {w} · {SEASON_YEAR}', t=f'Usage risers, week {w}', s='Target, carry and snap share',
                  n=pts(top['ds'] if top in d['tUp'] else top['dc']) if top else '', l=(f"{top['n']}, {tname(top['t'])}" if top else ''), x='PlainStats')
    write(f'weekly/usage-risers-week-{w}.html', shell(path, title, desc, body, graph, crumbs=crumbs, card=card))
    URLS.append((path, '0.6' if w == weeks[-1] else '0.4', 'weekly' if w == weeks[-1] else 'monthly'))


def mv_html(m):
    if m is None:
        return '<span class="note">new</span>'
    return f'<span class="up">▲{m}</span>' if m > 0 else f'<span class="dn">▼{-m}</span>' if m < 0 else '<span class="note">–</span>'


def tier_move(m):
    if m is None:
        return 'new this week'
    return 'same spot as last week' if m == 0 else f'{mv_html(m)} from last week'


def build_weekly_tiers(w, d, have):
    weeks = sorted(have['tiers'])
    path = wk_path('tiers', w)
    tt = {k: v for k, v in d['teams'].items() if k in TEAMS}
    order = sorted(tt, key=lambda k: tt[k]['rank'])
    off_r = {k: i + 1 for i, k in enumerate(sorted(tt, key=lambda k: -tt[k]['off']))}
    def_r = {k: i + 1 for i, k in enumerate(sorted(tt, key=lambda k: tt[k]['def']))}
    tiers = d.get('tiers') or []
    t1 = [tname(k) for k in order if tt[k]['tier'] == 1]
    best = order[0]
    movers = sorted([k for k in order if tt[k].get('move')], key=lambda k: -tt[k]['move'])
    up = movers[0] if movers and tt[movers[0]]['move'] > 0 else None
    dn = movers[-1] if movers and tt[movers[-1]]['move'] < 0 else None
    lede = (f"Through week {w} the {TEAMS[best]['full']} are the best team in the NFL by net EPA per play ({tt[best]['net']:+.3f}). "
            f"Tier 1: {', '.join(t1)}." if t1 else '')
    html = ''
    for tid, tn, tdesc in tiers:
        ks = [k for k in order if tt[k]['tier'] == tid]
        if not ks:
            continue
        rows = ''.join(f'<tr><td class="r">{tt[k]["rank"]}</td><td>{team_link(k)}<span class="sub">{tier_move(tt[k].get("move"))}</span></td>'
                       f'<td class="r">{tt[k]["net"]:+.3f}</td><td class="r">{tt[k]["off"]:+.3f}<span class="sub">{ordn(off_r[k])}</span></td>'
                       f'<td class="r">{tt[k]["def"]:+.3f}<span class="sub">{ordn(def_r[k])}</span></td></tr>' for k in ks)
        html += (f'<h2>{esc(tn)}: {esc(tdesc.lower() if tdesc else "")}</h2><div class="scroll"><table><thead><tr><th class="r">#</th><th>Team</th>'
                 f'{th_x("Net EPA", "epa", "r")}<th class="r">Offense</th><th class="r">Defense</th></tr></thead><tbody>{rows}</tbody></table></div>')
    faq = [(f'Who is the best team in the NFL after week {w}?', f"By net EPA per play (offense EPA minus defense EPA allowed), the {TEAMS[best]['full']} at {tt[best]['net']:+.3f}. "
            f"The best offense belongs to the {TEAMS[min(off_r, key=off_r.get)]['full']} and the best defense to the {TEAMS[min(def_r, key=def_r.get)]['full']}.")]
    if up:
        faq.append((f'Which team rose the most in week {w}?', f"The {TEAMS[up]['full']}, up {tt[up]['move']} spots to {ordn(tt[up]['rank'])}."))
    if dn:
        faq.append((f'Which team fell the most in week {w}?', f"The {TEAMS[dn]['full']}, down {-tt[dn]['move']} spots to {ordn(tt[dn]['rank'])}."))
    faq.append(('How are the team tiers built?', 'Every team is ranked by net EPA per play: how many points its offense adds per pass or run play, minus how many its defense allows. '
                'The 32 teams are then grouped into five tiers. For a defense, a lower EPA allowed is better.'))
    title = brand(f'NFL team tiers after week {w}, {SEASON_YEAR}: offense vs. defense EPA')
    desc = clip(f"{lede} All 32 teams ranked by offense and defense EPA per play, with the movers from last week.", 158)
    body = (f'<h1>NFL team tiers after week {w}</h1><p class="lede">{esc(lede)}</p>'
            f'<p>Every team ranked by EPA per play on offense and defense through week {w} of the {SEASON_YEAR} season, grouped into five tiers. '
            f'<a href="/team-tiers">Open the live team tiers</a> for the chart of offense against defense.</p>{wk_nav("tiers", w, weeks)}{html}'
            f'<p class="note">{esc(d.get("source") or "From nflverse play-by-play.")} <a href="/learn/epa">What is EPA?</a></p>'
            f'{faq_html(faq)}{wk_other(w, have, "tiers")}'
            + doors_html([('Team tiers, live', '/team-tiers', 'The offense vs. defense chart'), ('Power rankings', '/power-rankings', 'Results, roster and efficiency together'),
                          ('Standings', '/standings', 'Every division race'), ('Playoff odds', '/projections/playoff-odds', 'Each team\'s chances, from the PlainStats model')])
            + signup_html())
    crumbs = [('PlainStats', '/'), ('Weekly', '/weekly'), (f'Team tiers, week {w}', path)]
    graph = [{'@type': 'Article', 'headline': f'NFL team tiers after week {w}', 'description': desc, 'url': SITE + path, 'dateModified': LM_TOKEN,
              'author': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}, 'publisher': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld(crumbs)]
    card = og_add('pages', f'weekly-tiers-{w}', m='brand', c=OG_BRAND, e=f'Week {w} · {SEASON_YEAR}', t=f'NFL team tiers, week {w}', s='Offense vs. defense EPA per play',
                  n=f"{tt[best]['net']:+.2f}", l=f"net EPA per play, {TEAMS[best]['name']}", x='PlainStats')
    write(f'weekly/team-tiers-week-{w}.html', shell(path, title, desc, body, graph, crumbs=crumbs, card=card))
    URLS.append((path, '0.6' if w == weeks[-1] else '0.4', 'weekly' if w == weeks[-1] else 'monthly'))


def build_weekly_power(w, d, have):
    weeks = sorted(have['power'])
    path = wk_path('power', w)
    T = [t for t in d['teams'] if t['id'] in TEAMS]
    top = T[0]
    movers = sorted([t for t in T if t.get('move')], key=lambda t: -t['move'])
    up = movers[0] if movers and movers[0]['move'] > 0 else None
    dn = movers[-1] if movers and movers[-1]['move'] < 0 else None
    better = sorted([t for t in T if t['outlook'] == 'Better than record'], key=lambda t: t['rkRes'] - t['rkRos'], reverse=True)
    flat = sorted([t for t in T if t['outlook'] == 'Record flatters'], key=lambda t: t['rkRos'] - t['rkRes'], reverse=True)
    lede = (f"The {TEAMS[top['id']]['full']} ({top['rec']}) are No. 1 after week {w} with a power score of {top['score']}."
            + (f" Biggest climb: the {TEAMS[up['id']]['full']}, up {up['move']} to {ordn(up['rank'])}." if up else ''))
    rows = ''.join(f'<tr><td class="r">{t["rank"]}</td><td>{team_link(t["id"])}<span class="sub">{esc(t["rec"])} · {esc(t["tier"])}'
                   + (f' · best unit: {esc(t["best"])}' if t.get('best') else '') + '</span></td>'
                   f'<td class="r">{t["score"]}</td><td class="r">{mv_html(t.get("move"))}</td><td>{esc(t["outlook"])}</td></tr>' for t in T)
    table = ('<div class="scroll"><table><thead><tr><th class="r">#</th><th>Team</th><th class="r">Score</th><th class="r">Move</th><th>Outlook</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>')
    gap = lambda L, words: ('<ul>' + ''.join(f'<li>{team_link(t["id"])} ({esc(t["rec"])}): record ranks {ordn(t["rkRes"])}, roster and efficiency {ordn(t["rkRos"])}.</li>' for t in L[:4]) + '</ul>') if L else f'<p class="note">No team stands out as {words} this week.</p>'
    faq = [(f'Who is No. 1 in the NFL power rankings after week {w}?', f"The {TEAMS[top['id']]['full']} ({top['rec']}), with a power score of {top['score']} out of 100. "
            f"Next are the {TEAMS[T[1]['id']]['name']} and the {TEAMS[T[2]['id']]['name']}.")]
    if up:
        faq.append((f'Which team moved up the most in week {w}?', f"The {TEAMS[up['id']]['full']}, up {up['move']} spots to {ordn(up['rank'])}."))
    if dn:
        faq.append((f'Which team dropped the most in week {w}?', f"The {TEAMS[dn['id']]['full']}, down {-dn['move']} spots to {ordn(dn['rank'])}."))
    faq.append(('How are the PlainStats power rankings made?', 'Each team gets a score from 0 to 100: 28% win percentage, 28% scoring margin, 24% roster strength '
                '(the PlainStats player ratings) and 20% efficiency (offense and defense EPA per play, sacks and turnovers), each as a rank among the 32 teams. No opinions or votes go in.'))
    title = brand(f'NFL power rankings, week {w} {SEASON_YEAR}: all 32 teams by the numbers')
    desc = clip(lede + ' All 32 teams ranked on results, roster and efficiency, with each team\'s move from last week.', 158)
    body = (f'<h1>NFL power rankings, week {w}</h1><p class="lede">{esc(lede)}</p>'
            f'<p>All 32 teams after week {w} of the {SEASON_YEAR} season, ranked on record, scoring margin, roster strength and efficiency. '
            f'<a href="/power-rankings">Open the live power rankings</a> to sort by offense, defense or projected wins.</p>{wk_nav("power", w, weeks)}'
            f'<h2>All 32 teams</h2>{table}'
            f'<h2>Better than their record</h2><p>Teams whose roster and efficiency rank well above their results so far.</p>{gap(better, "better than its record")}'
            f'<h2>Record flatters them</h2><p>Teams whose results are ahead of what their roster and efficiency suggest.</p>{gap(flat, "flattered by its record")}'
            f'<p class="note">Records and scores from nflverse; player ratings and EPA from PlainStats, built on nflverse data. Through week {w}.</p>'
            f'{faq_html(faq)}{wk_other(w, have, "power")}'
            + doors_html([('Power rankings, live', '/power-rankings', 'Sort by offense, defense or projected wins'), ('Team tiers', '/team-tiers', 'Offense vs. defense EPA'),
                          ('Awards race', '/awards', 'MVP and the other awards, by the numbers'), ('Playoff odds', '/projections/playoff-odds', 'Each team\'s chances')])
            + signup_html())
    crumbs = [('PlainStats', '/'), ('Weekly', '/weekly'), (f'Power rankings, week {w}', path)]
    graph = [{'@type': 'Article', 'headline': f'NFL power rankings, week {w}', 'description': desc, 'url': SITE + path, 'dateModified': LM_TOKEN,
              'author': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}, 'publisher': {'@type': 'Organization', 'name': 'PlainStats', 'url': SITE + '/'}},
             faq_ld(faq), crumbs_ld(crumbs)]
    card = og_add('pages', f'weekly-power-{w}', m='brand', c=OG_BRAND, e=f'Week {w} · {SEASON_YEAR}', t=f'NFL power rankings, week {w}', s='All 32 teams by the numbers',
                  n=str(top['score']), l=f"power score, {TEAMS[top['id']]['name']} ({top['rec']})", x='PlainStats')
    write(f'weekly/power-rankings-week-{w}.html', shell(path, title, desc, body, graph, crumbs=crumbs, card=card))
    URLS.append((path, '0.6' if w == weeks[-1] else '0.4', 'weekly' if w == weeks[-1] else 'monthly'))


def build_weekly():
    for p in PAGES:
        if p.gid:
            PAGE_BY_GID.setdefault(p.gid, p)
    have = weekly_snaps()
    for w, d in have['usage'].items():
        build_weekly_usage(w, d, have)
    for w, d in have['tiers'].items():
        build_weekly_tiers(w, d, have)
    for w, d in have['power'].items():
        build_weekly_power(w, d, have)
    weeks = sorted(set().union(*[set(v) for v in have.values()]), reverse=True)
    if not weeks:
        return
    path = '/weekly'
    title = brand(f'NFL weekly rankings, team tiers and usage risers, {SEASON_YEAR}')
    desc = f'Every week of the {SEASON_YEAR} NFL season: power rankings, team tiers by EPA and the players whose target, carry and snap share jumped. Updated each Tuesday.'
    items = ''
    for w in weeks:
        links = [f'<li><a href="{wk_path(k, w)}"><b>{esc(n)}</b><span>Week {w}</span></a></li>' for k, _p, n, _a in WK_KINDS if w in have[k]]
        items += f'<h2>Week {w}</h2><ul class="doors">{"".join(links)}</ul>'
    body = (f'<h1>Weekly rankings and usage</h1><p class="lede">Three tables each week of the {SEASON_YEAR} season, kept for every week so you can look back: '
            f'power rankings, team tiers by EPA per play, and the players whose share of the work jumped or dropped.</p>'
            f'<p>New weeks are added each Tuesday once every game of the week is final. For this week\'s numbers as they change, open the live '
            f'<a href="/power-rankings">power rankings</a>, <a href="/team-tiers">team tiers</a> and <a href="/usage-risers">usage risers</a>.</p>{items}{signup_html()}')
    crumbs = [('PlainStats', '/'), ('Weekly', path)]
    graph = [{'@type': 'CollectionPage', 'name': 'Weekly rankings and usage', 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN}, crumbs_ld(crumbs)]
    card = og_add('pages', 'weekly', m='brand', c=OG_BRAND, e=f'{SEASON_YEAR} season', t='Weekly rankings and usage', s='Power rankings, team tiers, usage risers',
                  n=str(weeks[0]), l='latest week', x='Updated each Tuesday')
    write('weekly/index.html', shell(path, title, desc, body, graph, crumbs=crumbs, card=card))
    URLS.append((path, '0.7', 'weekly'))


def build_nav():
    teams = ''.join(f'<a href="/teams/{t["slug"]}">{esc(t["full"])}</a> ' for t in sorted(TEAMS.values(), key=lambda t: t['full']))
    (ROOT / 'tools' / 'seo-nav.html').write_text(
        '<nav aria-label="Browse PlainStats" style="max-width:1100px;margin:0 auto;padding:8px 20px 48px;color:var(--muted);font:.85rem/2 var(--body)">'
        '<strong style="color:var(--fg)">Browse:</strong> <a href="/teams">All teams</a> <a href="/players">Players</a> <a href="/draft">2027 Draft</a> <a href="/weekly">Weekly rankings</a> <a href="/learn">Stat explainers</a><br>' + teams.replace('</a> <a', '</a> · <a') + '</nav>\n', encoding='utf-8')

# App pages (one URL per section of the single-page app; vercel.json sends them to index.html)
APP_URLS = [('/scores', '0.9', 'daily'), ('/standings', '0.9', 'weekly'), ('/projections', '0.8', 'weekly'), ('/news', '0.8', 'daily'),
            ('/player-ratings', '0.8', 'weekly'), ('/player-ratings/roles', '0.5', 'weekly'), ('/player-ratings/pay-vs-play', '0.6', 'weekly'), ('/player-ratings/rankings', '0.7', 'weekly'), ('/player-ratings/traits', '0.6', 'weekly'),
            ('/stats', '0.8', 'weekly'), ('/contracts', '0.9', 'daily'), ('/power-rankings', '0.8', 'weekly'),
            ('/mock-draft', '0.8', 'weekly'), ('/big-board', '0.7', 'weekly'), ('/free-agency', '0.8', 'weekly'), ('/free-agency/key-dates', '0.5', 'monthly'),
            ('/team-ratings', '0.7', 'weekly'), ('/team-tiers', '0.8', 'weekly'), ('/usage-risers', '0.8', 'weekly'), ('/cap-room', '0.8', 'daily'), ('/awards', '0.6', 'weekly'), ('/best-worst-contracts', '0.6', 'weekly'),
            ('/rookie-contracts', '0.6', 'weekly'), ('/rookie-pay', '0.5', 'monthly'), ('/draft-guide', '0.4', 'monthly'), ('/cap-lab', '0.5', 'weekly'),
            ('/roster-builder', '0.6', 'weekly'), ('/trade-checker', '0.5', 'weekly'), ('/trade-deadline', '0.8', 'daily'), ('/compare', '0.5', 'weekly'), ('/cap-101', '0.6', 'monthly'),
            ('/about', '0.3', 'monthly'), ('/links', '0.3', 'weekly')]
# One page per panel inside a section tab (SUBS in src.html)
APP_URLS += [(u, '0.5', 'weekly') for u in [
    '/team-ratings/best',
    '/team-ratings/traits',
    '/team-ratings/roster-ratings',
    '/team-tiers/offense-vs-defense',
    '/team-tiers/all-teams',
    '/usage-risers/fallers',
    '/usage-risers/all-players',
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


# ---------------------------------------------------------------- player comparison pages (/players/<a>-vs-<b>)
# "Player A vs Player B" searches, answered with this season's numbers side by side. Which pairs get a page:
#   searched   pairs listed by hand in data/compare_pairs.json (from the "A vs B" searches in the Monday Search Console report)
#   teammates  two quarterbacks who have both started (60+ attempts each), or two running backs splitting the carries
#              (the second has 30+ carries and at least 40% of the first's)
#   paid       the six biggest confirmed deals at QB, RB and WR and the four at TE (all pairs), by reported yearly average;
#              a tie at the cutoff takes every tied deal, up to eight players
#   class      first-round quarterbacks from the same draft class
# Both players need a /players page and 2+ games this season, at the same position group. data/vs_pairs.json (generated,
# never hand-edit) keeps every pair ever built, so a page stays up after its rule stops picking it, as long as both players
# still qualify. Contract figures follow the same rules as the player pages: only when contract_facts() confirms them.
VS_FILE = DATA / 'vs_pairs.json'
VS_SEARCHED = _load('compare_pairs.json', {'pairs': []})
USAGE = _load('usage.json', {'players': [], 'teams': {}})
DRAFTED = _load('drafted.json', {'cols': [], 'picks': []})
VS_GROUP = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE'}
VS_WORD = {'QB': 'quarterback', 'RB': 'running back', 'WR': 'wide receiver', 'TE': 'tight end'}
VS_PAGES = []      # (slug, a, b) built this run
VS_BY_GID = {}     # gid -> [(slug, other player)] for the "more comparisons" links


def _usage_shares():
    """Season target, carry and snap share per gsis id, pooled over his games (data/usage.json, from nflverse)."""
    T, out = USAGE.get('teams', {}), {}
    for gid, _n, _pos, games in USAGE.get('players', []):
        a = [0, 0, 0, 0, 0, 0]
        for g in games:
            w, t, tg, ca = g[0], g[1], g[2], g[3]
            sn = g[5] if len(g) > 5 else None
            tt = T.get(t, {}).get(str(w), [0, 0, 0])
            a[0] += tg; a[1] += tt[0]; a[2] += ca; a[3] += tt[1]
            if sn is not None and len(tt) > 2 and tt[2]:
                a[4] += sn; a[5] += tt[2]
        out[gid] = {'tgt': a[0] / a[1] if a[1] else None, 'car': a[2] / a[3] if a[3] else None, 'snap': min(1, a[4] / a[5]) if a[5] else None}
    return out


USHARE = _usage_shares()


def vs_ok(p):
    return hasattr(p, 'slug') and not p.gone and p.pos in VS_GROUP and p.gid and p.s26 and (p.s26.get('g') or 0) >= 2


def vs_pairs():
    """{(gid, gid): (reason, extra)} for this run: the rules above plus every pair built before (data/vs_pairs.json)."""
    ok = [p for p in PAGES if vs_ok(p)]
    by_gid = {p.gid: p for p in ok}
    out = {}

    def add(a, b, why, extra=''):
        if a is not b and VS_GROUP[a.pos] == VS_GROUP[b.pos]:
            out.setdefault(tuple(sorted((a.gid, b.gid))), (why, extra))

    for row in VS_SEARCHED.get('pairs', []):
        a, b = by_gid.get(row.get('a')), by_gid.get(row.get('b'))
        if a and b:
            add(a, b, 'searched')
    team = {}
    for p in ok:
        team.setdefault((p.team, VS_GROUP[p.pos]), []).append(p)
    for (t, g), L in sorted(team.items()):
        if g not in ('QB', 'RB') or len(L) < 2:
            continue
        k = 'att' if g == 'QB' else 'car'
        L = sorted(L, key=lambda p: -(p.s26.get(k) or 0))
        top, two = L[0].s26.get(k) or 0, L[1].s26.get(k) or 0
        if (g == 'QB' and two >= 60) or (g == 'RB' and two >= 30 and two >= .4 * top):
            add(L[0], L[1], 'teammates', t)
    for g, n in (('QB', 6), ('RB', 6), ('WR', 6), ('TE', 4)):
        L = sorted([p for p in ok if VS_GROUP[p.pos] == g and p.prov == 'r' and contract_facts(p)['apy']],
                   key=lambda p: (-contract_facts(p)['apy'], p.name))
        cut = n
        while cut < min(len(L), 8) and contract_facts(L[cut])['apy'] == contract_facts(L[n - 1])['apy']:
            cut += 1   # a tie at the cutoff: take every tied deal (up to 8 players) rather than let the alphabet decide
        L = L[:cut]
        for a, b in itertools.combinations(L, 2):
            add(a, b, 'paid')
    cols = DRAFTED.get('cols', [])
    classes = {}
    for row in DRAFTED.get('picks', []):
        d = dict(zip(cols, row))
        if d.get('pos') == 'QB' and d.get('round') == 1 and d.get('gsis') in by_gid:
            classes.setdefault(d['season'], []).append(by_gid[d['gsis']])
    for yr, L in sorted(classes.items()):
        for a, b in itertools.combinations(L, 2):
            add(a, b, 'class', str(yr))
    try:
        old = json.loads(VS_FILE.read_text()).get('pairs', {})
    except Exception:
        old = {}
    for key in old:
        a, b = (by_gid.get(g) for g in key.split('|'))
        if a and b:
            add(a, b, 'kept')
    return out, by_gid, old


def vs_slug(a, b):
    a, b = sorted((a, b), key=lambda p: p.slug)
    return f'{a.slug}-vs-{b.slug}', a, b


def _ratio(x, y):
    return x / y if y else None


# (label, value from the season dict and shares, format, higher is better (False = lower is better))
def vs_rows(g):
    i0 = lambda v: f'{v:,.0f}'
    f1 = lambda v: f'{v:.1f}'
    pc = lambda v: f'{v * 100:.0f}%'
    G = lambda s: s.get('g') or 0
    per = lambda k: (lambda s, u: _ratio(s.get(k) or 0, G(s)))
    tot = lambda k: (lambda s, u: s.get(k) or 0)
    fp = ('Fantasy points a game (PPR)', per('fp'), f1, True)
    share = lambda k, lab: (lab, lambda s, u: u.get(k), pc, True)
    if g == 'QB':
        return [('Games', lambda s, u: G(s), i0, True),
                ('Completion rate', lambda s, u: _ratio(s.get('cmp') or 0, s.get('att') or 0), pc, True),
                ('Passing yards', tot('pyd'), i0, True), ('Passing yards a game', per('pyd'), f1, True),
                ('Yards per attempt', lambda s, u: _ratio(s.get('pyd') or 0, s.get('att') or 0), f1, True),
                ('Passing touchdowns', tot('ptd'), i0, True), ('Interceptions', tot('int'), i0, False),
                ('Sacks taken', tot('sk'), i0, False), ('Rushing yards', tot('ryd'), i0, True),
                ('Rushing touchdowns', tot('rtd'), i0, True), fp]
    if g == 'RB':
        return [('Games', lambda s, u: G(s), i0, True), ('Carries', tot('car'), i0, True), ('Rushing yards', tot('ryd'), i0, True),
                ('Yards per carry', lambda s, u: _ratio(s.get('ryd') or 0, s.get('car') or 0), f1, True),
                ('Rushing touchdowns', tot('rtd'), i0, True), ('Catches', tot('rec'), i0, True),
                ('Receiving yards', tot('reyd'), i0, True), ('Receiving touchdowns', tot('retd'), i0, True),
                ('Fumbles lost', tot('fl'), i0, False), share('car', 'Share of team carries'), share('tgt', 'Share of team targets'),
                share('snap', 'Share of offensive snaps'), fp]
    return [('Games', lambda s, u: G(s), i0, True), ('Targets', tot('tgt'), i0, True), ('Catches', tot('rec'), i0, True),
            ('Catch rate', lambda s, u: _ratio(s.get('rec') or 0, s.get('tgt') or 0), pc, True),
            ('Receiving yards', tot('reyd'), i0, True), ('Receiving yards a game', per('reyd'), f1, True),
            ('Yards per catch', lambda s, u: _ratio(s.get('reyd') or 0, s.get('rec') or 0), f1, True),
            ('Receiving touchdowns', tot('retd'), i0, True), share('tgt', 'Share of team targets'),
            share('snap', 'Share of offensive snaps'), fp]


def build_vs(a, b, slug, why, extra):
    g = VS_GROUP[a.pos]
    word = VS_WORD[g]
    fa, fb = contract_facts(a), contract_facts(b)
    pa, pb = plainscore(a, fa), plainscore(b, fb)
    sa, sb = a.s26, b.s26
    ua, ub = USHARE.get(a.gid, {}), USHARE.get(b.gid, {})
    wk = HIST.get('thru')
    la, lb = a.name.split(' ', 1)[-1], b.name.split(' ', 1)[-1]   # last names for tight spots
    if la == lb:
        la, lb = a.name, b.name
    path = f'/players/{slug}'

    # the side-by-side table: the better value in bold, ties plain
    rows_html, wins = '', [0, 0]
    for lab, fn, fmt, hi in vs_rows(g):
        va, vb = fn(sa, ua), fn(sb, ub)
        if va is None and vb is None:
            continue
        best = None
        if va is not None and vb is not None and lab != 'Games' and round(va, 4) != round(vb, 4):
            best = 0 if (va > vb) == hi else 1
            wins[best] += 1
        cell = lambda v, i: f'<td class="r">{"<b>" if best == i else ""}{fmt(v) if v is not None else "–"}{"</b>" if best == i else ""}</td>'
        rows_html += f'<tr><td>{esc(lab)}</td>{cell(va, 0)}{cell(vb, 1)}</tr>'
    if fa['apy'] or fb['apy']:
        pay = lambda f: mon(f['apy']) if f['apy'] else 'Being verified'
        rows_html += f'<tr><td>Pay per year</td><td class="r">{esc(pay(fa))}</td><td class="r">{esc(pay(fb))}</td></tr>'
        if fa['end'] or fb['end']:
            rows_html += f'<tr><td>Signed through</td><td class="r">{fa["end"] or "–"}</td><td class="r">{fb["end"] or "–"}</td></tr>'
    else:
        rows_html += '<tr><td>Contract</td><td class="r">Being verified</td><td class="r">Being verified</td></tr>'
    TA, TB_ = TEAMS[a.team], TEAMS[b.team]
    head = (f'<tr><th>{SEASON_YEAR}, through week {wk}</th><th class="r"><a href="/players/{a.slug}">{esc(a.name)}</a><br><span class="note">{esc(TA["name"])}</span></th>'
            f'<th class="r"><a href="/players/{b.slug}">{esc(b.name)}</a><br><span class="note">{esc(TB_["name"])}</span></th></tr>')
    table = f'<div class="card scroll"><table><thead>{head}</thead><tbody>{rows_html}</tbody></table></div>'
    table += (f'<p class="note">Bold marks the better number. Season stats from nflverse box scores; shares of team targets, carries and snaps from nflverse box scores and snap counts. '
              f'Contract figures only when a named report confirms them.</p>')

    # PlainScore, bar by bar
    ps_html = ''
    if pa and pb and pa['grp'] == pb['grp']:
        la_bars = {x[3]: x for x in pa['bars']}
        lines = ''
        for lab, v, val, k in pb['bars']:
            if k in la_bars:
                xa = la_bars[k]
                lines += f'<tr><td>{esc(lab)}</td><td class="r">{xa[1]} <span class="note">({esc(xa[2])})</span></td><td class="r">{v} <span class="note">({esc(val)})</span></td></tr>'
        ps_html = (f'<h2>PlainScore</h2><div class="card scroll"><table><thead><tr><th>Percentile among {pa["n"]} {esc(pa["grp"])}</th><th class="r">{esc(la)}</th><th class="r">{esc(lb)}</th></tr></thead>'
                   f'<tbody><tr><td><b>PlainScore</b></td><td class="r"><b>{pa["s"]}</b></td><td class="r"><b>{pb["s"]}</b></td></tr>{lines}</tbody></table></div>'
                   f'<p class="note">Each number is a percentile against every qualified {word} this season: 90 means better than 90% of them. <a href="/cap-101">How PlainScore works</a></p>')

    # plain-English answers
    why_s = {'teammates': f"They share the {TEAMS.get(extra, TA)['full']} {word} work this season.",
             'paid': f"Both are on two of the biggest {word} contracts in the NFL.",
             'class': f"Both were first-round quarterbacks in the {extra} draft.",
             'searched': 'Fans search this comparison on Google.'}.get(why, '')
    if pa and pb:
        if pa['s'] == pb['s']:
            better = f"{a.name} and {b.name} have the same PlainScore, {pa['s']}, through week {PSCORE['week']} of {SEASON_YEAR}."
        else:
            hi_, lo_, ph, pl_ = (a, b, pa, pb) if pa['s'] > pb['s'] else (b, a, pb, pa)
            better = (f"By this season's play, {hi_.name}: his PlainScore is {ph['s']} to {poss(lo_.name)} {pl_['s']}, "
                      f"so he ranks ahead of more of the {ph['n']} qualified {ph['grp']} through week {PSCORE['week']}.")
    elif pa or pb:
        x, px = (a, pa) if pa else (b, pb)
        y = b if pa else a
        better = (f"Only {x.name} has played enough this season for a PlainScore ({px['s']} out of 100). "
                  f"{y.name} has not qualified yet, so compare the season numbers below.")
    else:
        better = "Neither has played enough this season for a PlainScore yet, so compare the season numbers below."
    lead = (f"{a.name} leads in {wins[0]} of the {sum(wins)} stats below that can be compared, {b.name} in {wins[1]}."
            if sum(wins) else '')
    mk = {'QB': ('pyd', 'passing yards'), 'RB': ('ryd', 'rushing yards'), 'WR': ('reyd', 'receiving yards'), 'TE': ('reyd', 'receiving yards')}[g]
    va, vb = sa.get(mk[0]) or 0, sb.get(mk[0]) or 0
    more = (f"{a.name} has {va:,} {mk[1]} in {sa['g']} games ({va / sa['g']:.1f} a game); "
            f"{b.name} has {vb:,} in {sb['g']} games ({vb / sb['g']:.1f} a game).")
    fpa, fpb = (sa.get('fp') or 0) / sa['g'], (sb.get('fp') or 0) / sb['g']
    fant = f"{a.name} has averaged {fpa:.1f} PPR fantasy points a game this season, {b.name} {fpb:.1f}."
    if g != 'QB':
        k, kw = ('car', 'carries') if g == 'RB' else ('tgt', 'targets')
        if ua.get(k) is not None and ub.get(k) is not None:
            fant += f" {a.name} has had {ua[k] * 100:.0f}% of his team's {kw}, {b.name} {ub[k] * 100:.0f}%."
        if ua.get('snap') is not None and ub.get('snap') is not None:
            fant += f" On the field: {ua['snap'] * 100:.0f}% of snaps for {la}, {ub['snap'] * 100:.0f}% for {lb}."
    faq = [(f"Who is better, {a.name} or {b.name}?", better + ' This is a read of the season so far, not a forecast.'),
           (f"Who has more {mk[1]} in {SEASON_YEAR}?", more),
           (f"Who is the better fantasy option, {a.name} or {b.name}?", fant + ' Fantasy points use nflverse PPR scoring.')]
    if fa['apy'] and fb['apy']:
        hi_, lo_ = (a, b) if fa['apy'] >= fb['apy'] else (b, a)
        fh, fl = contract_facts(hi_), contract_facts(lo_)
        src = lambda p: {'r': 'a named report', 'f': 'calculated from the CBA rookie scale', 'm': 'the CBA league minimum', 'p': 'the CBA practice squad scale'}.get(p.prov, '')
        faq.append((f"Who gets paid more, {a.name} or {b.name}?",
                    f"{hi_.name} averages {mon(fh['apy'])} a year ({src(hi_)}), {lo_.name} {mon(fl['apy'])} ({src(lo_)})."))

    lede = ' '.join(x for x in (better, why_s, lead) if x)
    core = next(t for t in (f"{a.name} vs. {b.name}: {SEASON_YEAR} stats compared", f"{a.name} vs. {b.name}: {SEASON_YEAR} stats",
                            f"{a.name} vs. {b.name} stats", f"{a.name} vs. {b.name}") if len(t) <= 60 or t == f"{a.name} vs. {b.name}")
    title = core + ' | PlainStats' if len(core) + 13 <= 60 else core
    desc = pack([f"{a.name} vs. {b.name} in {SEASON_YEAR}, side by side: {mk[1]}, touchdowns, fantasy points and PlainScore.", better, more])
    h1 = f"{a.name} vs. {b.name}"

    imgs = ''.join(f'<img src="{esc(u)}" alt="{esc(p.name)}" width="72" height="72" loading="lazy" decoding="async" onerror="this.remove()">'
                   for p in (a, b) for u in [headshot(p.name, p.team)] if u)
    others = []
    for p in (a, b):
        for s2, q in VS_BY_GID.get(p.gid, []):
            if s2 != slug and s2 not in [o[0] for o in others]:
                others.append((s2, f"{p.name} vs. {q.name}"))
    more_html = ('<h2>More comparisons</h2><ul class="chips">' + ''.join(f'<li><a href="/players/{s2}">{esc(t)}</a></li>' for s2, t in others[:8]) + '</ul>') if others else ''
    app = f'/compare?p={a.gid},{b.gid}'
    body = (f'<div class="id">{imgs}<div><h1>{esc(h1)}</h1><p class="note">{esc(VS_WORD[g].capitalize())}s · {SEASON_YEAR} season through week {wk}</p></div></div>'
            f'<p class="lede">{esc(lede)}</p>{table}{ps_html}{faq_html(faq)}'
            f'<p><a class="cta" href="{esc(app)}">Compare them in the PlainStats app</a><a class="cta alt" href="/players/{a.slug}">{esc(a.name)}</a><a class="cta alt" href="/players/{b.slug}">{esc(b.name)}</a></p>'
            f'{more_html}'
            + doors_html([('Compare any players', '/compare', 'Pick two to four players and see them side by side'),
                          ('Weekly usage risers', '/usage-risers', 'Whose share of the targets, carries and snaps jumped this week'),
                          ('Season stats', '/stats', f'Every {SEASON_YEAR} stat leader, filter by team or position'),
                          ('Player ratings', '/player-ratings', f'How {word}s rank on the field this season')])
            + signup_html())
    crumbs = [('PlainStats', '/'), ('Players', '/players'), (h1, path)]
    graph = [{'@type': 'WebPage', 'name': title, 'url': SITE + path, 'description': desc, 'dateModified': LM_TOKEN,
              'isPartOf': {'@type': 'WebSite', 'name': 'PlainStats', 'url': SITE + '/'},
              'about': [{'@type': 'Person', 'name': p.name, 'url': f'{SITE}/players/{p.slug}'} for p in (a, b)]},
             faq_ld(faq), crumbs_ld(crumbs)]
    n = f"{pa['s']} – {pb['s']}" if pa and pb else f"{fpa:.1f} – {fpb:.1f}"
    card = og_add('pages', 'vs-' + slug, m='brand', c=OG_BRAND, e='Player vs. player', t=f"{la} vs. {lb}", s=f"{a.name} and {b.name}",
                  n=n, l='PlainScore, out of 100' if pa and pb else 'PPR fantasy points a game', x=f"{SEASON_YEAR} season, side by side")
    write(f'players/{slug}.html', shell(path, title, desc, body, graph, crumbs=crumbs, card=card))
    URLS.append((path, '0.6', 'weekly'))
    PAGEMAP.setdefault('v', {})['|'.join(sorted((a.gid, b.gid)))] = slug


def vs_links_html(p):
    L = sorted(VS_BY_GID.get(getattr(p, 'gid', None), []), key=lambda x: x[1].name)
    if not L:
        return ''
    return (f'<h2>{esc(p.name)} compared</h2><ul class="chips">'
            + ''.join(f'<li><a href="/players/{s}">{esc(p.name)} vs. {esc(q.name)}</a></li>' for s, q in L[:10]) + '</ul>')


def build_vs_pages():
    pairs, by_gid, old = vs_pairs()
    built = []
    for (ga, gb), (why, extra) in sorted(pairs.items()):
        slug, a, b = vs_slug(by_gid[ga], by_gid[gb])
        assert slug not in slug_seen, f'comparison slug {slug} clashes with a player page'
        built.append((slug, a, b, why, extra))
        VS_BY_GID.setdefault(a.gid, []).append((slug, b))
        VS_BY_GID.setdefault(b.gid, []).append((slug, a))
    for slug, a, b, why, extra in built:
        build_vs(a, b, slug, why, extra)
        VS_PAGES.append((slug, a, b))
    keep = {'|'.join(sorted((a.gid, b.gid))): old.get('|'.join(sorted((a.gid, b.gid))), TODAY) for _s, a, b, _w, _e in built}
    VS_FILE.write_text(json.dumps({'note': 'Generated by tools/build_seo.py: every player comparison page built, with the date it first was. Never edit by hand.',
                                   'pairs': keep}, separators=(',', ':'), sort_keys=True) + '\n', encoding='utf-8')
    counts = {}
    for _s, _a, _b, why, _e in built:
        counts[why] = counts.get(why, 0) + 1
    print(f'comparisons {len(built)} {counts}', end=' | ')


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


# ---------------------------------------------------------------- app page summaries (data/app_summaries.json)
# App pages (/free-agency, /roster-builder, ...) draw their tables with JavaScript, so a crawler that doesn't run it (ChatGPT's,
# the largest source of visitors in Nov 2026) sees only the app menu. cf/worker.js puts the summary for its path at the top of
# <body>, under the page's own title and description, and hides it as the page loads. Same data rules as the search pages:
# end years only when contract_facts() confirms them, PlainScores from data/plainscore.json, no pay figures.
SUM_GROUPS = ['quarterbacks', 'running backs', 'wide receivers', 'tight ends', 'left tackles', 'left guards', 'centers',
              'right guards', 'right tackles', 'edge rushers', 'def. tackles', 'linebackers', 'cornerbacks', 'safeties',
              'kickers', 'punters']


def build_app_summaries():
    rated = []
    for p in PLAYERS:
        f = contract_facts(p)
        rated.append((p, f, plainscore(p, f)))

    def who(p, ps=None, team=True):
        name = f'<a href="/players/{p.slug}">{esc(p.name)}</a>' if getattr(p, 'slug', None) else esc(p.name)
        return (f"{name}, {esc(POSNAME.get(p.pos, p.pos))}" + (f", {esc(TEAMS[p.team]['full'])}" if team else '')
                + (f": PlainScore {ps['s']}" if ps else ''))

    fa_year = SEASON_YEAR + 1
    cls = [(p, ps) for p, f, ps in rated if f['end'] == SEASON_YEAR]
    top = sorted((x for x in cls if x[1]), key=lambda x: (-x[1]['s'], x[0].name))[:25]
    lead = (f"<p>The {fa_year} free agent class: {len(cls):,} players whose contracts end after the {SEASON_YEAR} season, counting only "
            f"deals whose end year a named report or the CBA confirms. Data as of {esc(ASOF)}.</p>")
    top_html = ('<h2>Highest PlainScores in the class</h2><ol>' + ''.join(f'<li>{who(p, ps)}</li>' for p, ps in top) + '</ol>'
                '<p>PlainScore ranks a player\'s play this season against everyone at his position with enough snaps, from 0 to 100. '
                '<a href="/learn">How the numbers work</a>.</p>')
    by_pos = {}
    for p, ps in cls:
        by_pos.setdefault(POSNAME.get(p.pos, p.pos), []).append(p)
    pos_html = '<h2>By position</h2><ul>' + ''.join(f'<li>{esc(k.capitalize())}: {len(v)}</li>' for k, v in sorted(by_pos.items(), key=lambda kv: -len(kv[1]))) + '</ul>'
    by_team = {}
    for p, ps in cls:
        by_team.setdefault(p.team, []).append((p, ps))
    team_html = '<h2>By team</h2><ul>' + ''.join(
        f'<li><a href="/teams/{TEAMS[t]["slug"]}">{esc(TEAMS[t]["full"])}</a>: {len(v)} pending free agents'
        + (lambda b: f'; highest PlainScore: {who(b[0], b[1], team=False)}' if b else '')(max((x for x in v if x[1]), key=lambda x: x[1]['s'], default=None)) + '</li>'
        for t, v in sorted(by_team.items(), key=lambda kv: (-len(kv[1]), TEAMS[kv[0]]['full']))) + '</ul>'
    fa_open = '<p><a href="/free-agency">Open the free agency tool</a> to sort the class by position, team and estimated next deal.</p>'
    out = {'/free-agency': lead + top_html + pos_html + fa_open, '/free-agency/all': lead + top_html + fa_open,
           '/free-agency/by-position': lead + pos_html + top_html + fa_open, '/free-agency/by-team': lead + team_html + fa_open}

    groups = {}
    for p, f, ps in rated:
        if ps:
            groups.setdefault(ps['grp'], []).append((p, ps))
    rb = ['<p>The roster builder lets you pick a player at every position from all 32 rosters and rates the team you build, '
          'using each player\'s PlainScore. It shows no contract costs: it is about who plays best. '
          f'Data as of {esc(ASOF)}.</p><h2>Highest PlainScores by position</h2>']
    for g in SUM_GROUPS:
        best = sorted(groups.get(g, []), key=lambda x: (-x[1]['s'], x[0].name))[:3]
        if best:
            rb.append(f'<h3>{esc(g.capitalize())}</h3><ol>' + ''.join(f'<li>{who(p, ps)}</li>' for p, ps in best) + '</ol>')
    rb.append('<p><a href="/roster-builder">Open the roster builder</a> to build your own team.</p>')
    out['/roster-builder'] = ''.join(rb)
    (ROOT / 'data' / 'app_summaries.json').write_text(json.dumps(out, separators=(',', ':'), sort_keys=True), encoding='utf-8')


def main():
    for d in ('players', 'teams', 'draft', 'learn', 'weekly'):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    build_vs_pages()   # first: player pages link to their comparisons (VS_BY_GID)
    for p in PAGES:
        build_player(p)
    for t in TEAMS.values():
        build_team(t)
    for pr in PROS:
        build_prospect(pr)
    build_hubs()
    build_learn()
    build_weekly()
    build_sitemap()
    build_nav()
    build_og_data()
    build_app_summaries()
    (ROOT / 'data' / 'pageslugs.json').write_text(json.dumps(PAGEMAP, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    print(f'social cards {sum(len(c) for c in OG.values())}', end=' | ')
    print(f'players {len(PAGES)} of {len(PLAYERS)} | teams {len(TEAMS)} x3 | draft {len(PROS)} | sitemap urls {len(URLS) + 3}')


if __name__ == '__main__':
    main()
