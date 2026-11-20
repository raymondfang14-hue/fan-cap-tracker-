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
import contracts from '../api/contracts.js';

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api/og') return og(url, env);
    if (url.pathname === '/api/contracts') return deals(request, env, ctx);
    if (url.pathname.startsWith('/api/')) return json({ error: 'Not found' }, 404);
    return env.ASSETS.fetch(request);
  }
};
