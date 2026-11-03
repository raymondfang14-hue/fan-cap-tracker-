// Vercel function: the app page with its own <head> for crawlers and link-preview bots.
//   vercel.json sends app paths (/team-tiers, /scores, /team/kc, /game/<id>, /player/<slug>, ...) here only when the request's
//   User-Agent looks like a bot. People still get the static index.html through the plain rewrites, so nothing changes for them.
//
// Why: every app path serves the same index.html, whose <head> says title "PlainStats", the generic description and
// canonical "/". The page fixes that with JavaScript, but Google reads the raw HTML first and X, iMessage, Reddit and Discord never
// run JavaScript, so without this every app page looked like a copy of the home page and shared the generic card.
//
// The body is index.html unchanged; only the title, description, canonical, og: and twitter: tags are replaced. Page titles and
// descriptions come from the ROUTES ... TEAMSUBS block of index.html itself (PTITLE, PDESC, SUBS), so they never drift from the
// app. Paths that are not app pages get the 404 page with status 404.
import vm from 'node:vm';

const SITE = 'https://www.plainstatsnfl.com';
const CACHE = 'public, max-age=0, s-maxage=3600, stale-while-revalidate=86400';
const DEFAULT_DESC = 'NFL contracts, stats and team analytics, explained in plain English.';

const esc = s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const slugify = s => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

let cached = null; // { at, html, meta, teams, slugs, cards }
async function load(origin) {
  if (cached && Date.now() - cached.at < 10 * 60 * 1000) return cached;
  const get = async (p, json) => {
    const r = await fetch(origin + p, { headers: { 'User-Agent': 'PlainStats page function' } });
    if (!r.ok) throw new Error(p + ' ' + r.status);
    return json ? r.json() : r.text();
  };
  const [html, nfl, slugs, pc, tc, dc] = await Promise.all([
    get('/', false), get('/data/nfl.json', true), get('/data/pageslugs.json', true).catch(() => ({ p: {}, d: {} })),
    get('/og-data/players.json', true).catch(() => ({ cards: {} })), get('/og-data/teams.json', true).catch(() => ({ cards: {} })),
    get('/og-data/draft.json', true).catch(() => ({ cards: {} }))]);
  const a = html.indexOf('const ROUTES = ['), b = html.indexOf('let teamSub');
  if (a < 0 || b < a) throw new Error('route block not found in index.html');
  const meta = vm.runInNewContext(html.slice(a, b) + ';({ ROUTES, PTITLE, PDESC, TEAMSUBS })', {}, { timeout: 200 });
  const teams = {};
  for (const t of nfl.teams) teams[t.id.toLowerCase()] = t;
  cached = { at: Date.now(), html, meta, teams, slugs, cards: { players: pc.cards || {}, teams: tc.cards || {}, draft: dc.cards || {} }, asOf: nfl.asOf };
  return cached;
}

// -> { title, desc, canon, img } for an app path, or null when the path is not an app page.
function pageMeta(path, C) {
  const { meta, teams, slugs, cards } = C;
  const og = (k, s) => `${SITE}/api/og?k=${k}&s=${s}&v=${C.asOf}`;
  const route = meta.ROUTES.find(([, p]) => p === path);
  if (route && route[0] !== 'home') {
    const k = route[0];
    return { title: (meta.PTITLE[k] || 'PlainStats') + ' · PlainStats', desc: meta.PDESC[k] || DEFAULT_DESC, canon: SITE + path };
  }
  let m = path.match(/^\/team\/([a-z]{2,3})(?:\/([a-z-]+))?$/);
  if (m && teams[m[1]]) {
    const t = teams[m[1]], sub = m[2] ? meta.TEAMSUBS.find(([s]) => s === m[2]) : ['', ''];
    if (!sub) return null;
    const full = `${t.city} ${t.name}`, slug = slugify(t.name);
    return {
      title: `${full}${sub[0] ? ' ' + sub[1].toLowerCase() : ''} · PlainStats`,
      desc: `${sub[0] ? sub[1] + ' for the ' + full + '. ' : 'The ' + full + ': '}lineup, team stats, depth chart, salary cap, spending and roster, explained in plain English.`.replace(/\. lineup/, '. Lineup'),
      canon: SITE + path, img: cards.teams[slug] ? og('teams', slug) : null
    };
  }
  m = path.match(/^\/player\/([a-z0-9-]+)-([a-z]{2,3})$/);
  if (m && teams[m[2]]) {
    const stat = (slugs.p || {})['p-' + m[1] + '-' + m[2]], card = stat && cards.players[stat];
    const name = card ? card.t : m[1].split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    const t = teams[m[2]];
    return {
      title: `${name}, ${t.city} ${t.name} · PlainStats`,
      desc: `${name} of the ${t.city} ${t.name}: contract, season stats and injury report, explained in plain English.`,
      // the static /players page is the one to index; the app sheet points at it
      canon: stat ? `${SITE}/players/${stat}` : SITE + path, img: card ? og('players', stat) : null
    };
  }
  m = path.match(/^\/prospect\/([a-z0-9-]+)$/);
  if (m) {
    const stat = (slugs.d || {})['d-' + m[1]], card = stat && cards.draft[stat];
    if (!card) return { title: '2027 NFL draft prospect · PlainStats', desc: 'A 2027 NFL draft prospect: grade, role, college stats and team fits.', canon: SITE + path };
    return { title: `${card.t}, 2027 NFL draft prospect · PlainStats`, desc: `${card.t}: 2027 NFL draft grade, role, college stats, NFL comparisons and team fits.`, canon: `${SITE}/draft/${stat}`, img: og('draft', stat) };
  }
  m = path.match(/^\/game\/(\d{4})-(\d{2})-([a-z]{2,3})-([a-z]{2,3})$/);
  if (m && teams[m[3]] && teams[m[4]]) {
    const wk = +m[2], aw = teams[m[3]], hm = teams[m[4]];
    const game = `${aw.city} ${aw.name} at ${hm.city} ${hm.name}`;
    return { title: `${aw.name} at ${hm.name}, Week ${wk} ${m[1]} · PlainStats`, desc: `${game}, Week ${wk} of the ${m[1]} NFL season: the PlainStats model's pick, team stats and injury report.`, canon: SITE + path };
  }
  return null;
}

function withHead(html, pm) {
  const img = pm.img || `${SITE}/og-image.png`;
  const set = (re, val) => { html = html.replace(re, (all, a, _v, c) => a + esc(val) + c); };
  set(/(<title>)([^<]*)(<\/title>)/, pm.title);
  set(/(<meta name="description" content=")([^"]*)(")/, pm.desc);
  set(/(<link rel="canonical" href=")([^"]*)(")/, pm.canon);
  set(/(<meta property="og:title" content=")([^"]*)(")/, pm.title);
  set(/(<meta property="og:description" content=")([^"]*)(")/, pm.desc);
  set(/(<meta property="og:url" content=")([^"]*)(")/, pm.canon);
  set(/(<meta property="og:image" content=")([^"]*)(")/, img);
  set(/(<meta name="twitter:title" content=")([^"]*)(")/, pm.title);
  set(/(<meta name="twitter:description" content=")([^"]*)(")/, pm.desc);
  set(/(<meta name="twitter:image" content=")([^"]*)(")/, img);
  if (pm.img) html = html.replace(/<meta property="og:image:alt" content="[^"]*">/, `<meta property="og:image:alt" content="${esc(pm.title)}">`);
  return html;
}

async function handler(request) {
  const url = new URL(request.url);
  const origin = url.origin;
  let path = (url.searchParams.get('p') || '/').replace(/\/+$/, '') || '/';
  if (!/^\/[a-z0-9/-]*$/.test(path)) path = '/x-invalid';
  try {
    const C = await load(origin);
    const pm = pageMeta(path, C);
    if (!pm) {
      const r = await fetch(origin + '/404', { headers: { 'User-Agent': 'PlainStats page function' } });
      return new Response(r.ok ? await r.text() : 'Not found', { status: 404, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': CACHE } });
    }
    return new Response(withHead(C.html, pm), { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': CACHE } });
  } catch (e) {
    console.error('page head failed', path, e && e.message);
    // 503 tells a crawler to come back later; a redirect or a generic page would be read as this page's content
    return new Response('Temporarily unavailable', { status: 503, headers: { 'Retry-After': '600', 'Cache-Control': 'no-store' } });
  }
}

// Web-standard handler shape, same as api/og.js.
export default { fetch: handler };
