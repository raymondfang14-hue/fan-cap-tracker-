// Cloudflare Worker for plainstatsnfl.com (Vercel Hobby paused Nov 20, 2026). Static files are served by Workers static assets
// (dist/, built by tools/build_cf.py) without running this script; only /api/* reaches it (run_worker_first in wrangler.jsonc),
// so the free plan's request count is spent on API calls alone.
//
//   /api/og?k=&s=     the social card, drawn ahead of time by tools/render_og.mjs into /og/<kind>/<slug>.png
//                     (the free plan's CPU limit is too small to draw it here); unknown cards redirect to /og-image.png
//   /api/contracts    the verified Airtable deal cards, same filter and shape as api/contracts.js on Vercel. Needs the
//                     Worker secret AIRTABLE_TOKEN (Cloudflare dashboard: plainstats > Settings > Variables and Secrets).
//                     Cached 5 minutes at the edge. Without the secret it answers 503 and the page shows the built-in DEALS.
//   other /api/*      404 JSON (the page falls back: /api/espn-csv -> data/espn_assets.json)
//   app paths         /scores, /team-tiers, /team/kc, /player/<slug>-<team>, /game/<id>, ... (the rewrites to "/" in vercel.json):
//                     index.html with its own title, description, canonical and social card tags, the job api/page.js did for
//                     bots on Vercel. Everyone gets it here (crawlers, link previews, people), so the raw HTML never says
//                     canonical "/" on a page that isn't home. An app-shaped path pageMeta() doesn't know (a mistyped team) gets
//                     the 404 page for bots and the app as before for people. wrangler.jsonc's run_worker_first sends only these
//                     paths here; every other file is served without running this script.
import contracts from '../api/contracts.js';
import { pageMeta, SITE } from '../api/_page-meta.js';
import C from './_meta.json'; // written by tools/build_cf_meta.mjs at deploy
import SUMMARY from '../data/app_summaries.json'; // written by tools/build_seo.py (build_app_summaries)

const KINDS = new Set(['players', 'teams', 'draft', 'pages']);
const OG_CACHE = 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800';
const json = (body, status, extra) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...extra } });

async function og(url, env) {
  const kind = url.searchParams.get('k'), slug = url.searchParams.get('s') || '';
  if (KINDS.has(kind) && /^[a-z0-9-]{1,90}$/.test(slug)) {
    const r = await env.ASSETS.fetch(new URL(`/og/${kind}/${slug}.png`, url.origin));
    if (r.ok && (r.headers.get('content-type') || '').startsWith('image/png')) {
      return new Response(r.body, { headers: { 'Content-Type': 'image/png', 'Cache-Control': OG_CACHE } });
    }
  }
  return Response.redirect(`${url.origin}/og-image.png`, 302);
}

async function deals(request, env, ctx) {
  const cache = caches.default, key = new Request(new URL('/api/contracts', request.url).href);
  const hit = await cache.match(key);
  if (hit) return hit;
  const token = env.AIRTABLE_TOKEN;
  if (!token) return json({ error: 'Set the AIRTABLE_TOKEN secret on the plainstats Worker.' }, 503, { 'Cache-Control': 'no-store' });
  const base = env.AIRTABLE_BASE_ID || 'app7vEpDdwBT0xCUr'; // Cap Tracker base
  const table = env.AIRTABLE_TABLE || 'tblMvDcAIUpr9Zuor';  // the deals table
  try {
    const records = [];
    let offset;
    do {
      const u = new URL(`https://api.airtable.com/v0/${base}/${encodeURIComponent(table)}`);
      u.searchParams.set('pageSize', '100');
      u.searchParams.set('sort[0][field]', 'Sort');
      if (offset) u.searchParams.set('offset', offset);
      const r = await fetch(u, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`Airtable answered ${r.status}`);
      const j = await r.json();
      records.push(...j.records);
      offset = j.offset;
    } while (offset);
    const list = records.filter(r => contracts.isVerified(r.fields)).map(r => contracts.toContract(r.fields)).filter(c => c.name && c.league);
    const res = json({ updated: new Date().toISOString(), held: records.length - list.length, contracts: list }, 200, { 'Cache-Control': 'public, max-age=60, s-maxage=300' });
    ctx.waitUntil(cache.put(key, res.clone()));
    return res;
  } catch (e) {
    console.error('contracts:', e && e.message);
    return json({ error: 'Could not read the deals table right now.' }, 502, { 'Cache-Control': 'no-store' });
  }
}

const APPS = C.apps.map(r => new RegExp(r));
const BOT = C.botUA ? new RegExp(C.botUA) : null;

// Set an attribute on the first matching element only (index.html has each tag once).
const attr = (name, value) => ({ element(el) { el.setAttribute(name, value); } });
const escH = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

// App pages draw their tables with JavaScript, so a crawler that doesn't run it (ChatGPT's) saw only the app menu. For the
// paths in data/app_summaries.json, put a plain-text summary first in <body>; the script right after it removes it as the
// page loads, so people see the app exactly as before. index.html has a second <body> (the wrapped src.html): first one only.
function summaryAt(path, pm) {
  const body = SUMMARY[path];
  if (!body) return null;
  let done = false;
  const html = `<section id="ps-sum"><h1>${escH(pm.title)}</h1><p>${escH(pm.desc)}</p>${body}</section>` +
    `<script>document.getElementById('ps-sum').remove()</script>`;
  return { element(el) { if (!done) { done = true; el.prepend(html, { html: true }); } } };
}

async function appPage(request, env, url) {
  let path = url.pathname.replace(/\/+$/, '') || '/';
  if (!/^\/[a-z0-9/-]*$/.test(path)) path = '/x-invalid';
  const pm = pageMeta(path, C);
  const isBot = BOT && BOT.test(request.headers.get('user-agent') || '');
  if (!pm && isBot) {
    const r = await env.ASSETS.fetch(new URL('/404', url.origin));
    return new Response(r.body, { status: 404, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }
  const app = await env.ASSETS.fetch(new URL('/', url.origin));
  const headers = new Headers(app.headers);
  headers.delete('ETag'); // the body differs per path
  headers.set('Cache-Control', 'public, max-age=0, must-revalidate');
  if (!pm) return new Response(app.body, { status: app.status, headers });
  const img = pm.img || `${SITE}/og-image.png`;
  let rw = new HTMLRewriter()
    .on('title', { element(el) { el.setInnerContent(pm.title); } })
    .on('meta[name="description"]', attr('content', pm.desc))
    .on('link[rel="canonical"]', attr('href', pm.canon))
    .on('meta[property="og:title"]', attr('content', pm.title))
    .on('meta[property="og:description"]', attr('content', pm.desc))
    .on('meta[property="og:url"]', attr('content', pm.canon))
    .on('meta[property="og:image"]', attr('content', img))
    .on('meta[name="twitter:title"]', attr('content', pm.title))
    .on('meta[name="twitter:description"]', attr('content', pm.desc))
    .on('meta[name="twitter:image"]', attr('content', img));
  if (pm.img) rw = rw.on('meta[property="og:image:alt"]', attr('content', pm.title));
  const sum = summaryAt(path, pm);
  if (sum) rw = rw.on('body', sum);
  return rw.transform(new Response(app.body, { status: 200, headers }));
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api/og') return og(url, env);
    if (url.pathname === '/api/contracts') return deals(request, env, ctx);
    if (url.pathname.startsWith('/api/')) return json({ error: 'Not found' }, 404);
    if ((request.method === 'GET' || request.method === 'HEAD') && APPS.some(re => re.test(url.pathname))) return appPage(request, env, url);
    return env.ASSETS.fetch(request);
  }
};
