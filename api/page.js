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
import { SITE, pageMeta, withHead } from './_page-meta.js';

// A day at the edge: every function response counts toward Vercel's Fast Origin Transfer (10 GB on Hobby; the account was
// paused on Nov 20, 2026 after bots used it up), and the page only changes with the daily refresh.
const CACHE = 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800';


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

async function handler(request) {
  const url = new URL(request.url);
  const origin = url.origin;
  let path = (url.searchParams.get('p') || '/').replace(/\/+$/, '') || '/';
  if (!/^\/[a-z0-9/-]*$/.test(path)) path = '/x-invalid';
  try {
    const C = await load(origin);
    const pm = pageMeta(path, C);
    if (!pm) {
      // a short body: vercel.json only sends app paths here now, so this is a mistyped address, not worth a full page
      return new Response('<!doctype html><title>Not found · PlainStats</title><p>Page not found. <a href="/">PlainStats home</a></p>', { status: 404, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': CACHE } });
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
