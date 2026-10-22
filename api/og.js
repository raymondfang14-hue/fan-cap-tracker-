// Vercel function (Node runtime; @vercel/og's edge build can't compile its wasm there): draws the social card (Open Graph image) for a PlainStats page.
//   /api/og?k=players&s=patrick-mahomes&v=2026-10-22
//     k  players | teams | draft | pages        s  the page's slug        v  data date, only there so X and Discord re-fetch after a refresh
//
// The card text is read from og-data/<k>.json (written by tools/build_seo.py, so it follows the same data rules as the page: nothing
// that is not confirmed). Only the slug comes from the URL, which means nobody can make this domain draw a card with text of their choosing.
// Headshots and logos are fetched from ESPN's image CDN here, because the build sandbox can't reach it; if an image is missing the card
// shows initials instead. If anything fails the request redirects to the static /og-image.png so a shared link never gets a broken image.
import { card, W, H } from './_og-layout.js';

const KINDS = new Set(['players', 'teams', 'draft', 'pages']);
// Cards change when the daily refresh runs, so keep them a day at the CDN and let stale ones serve while a new one draws.
const CACHE = 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800';
const IMAGE_HOST = 'a.espncdn.com';

let fontsPromise = null;
const dataPromises = {};

function loadFonts(origin) {
  if (!fontsPromise) {
    fontsPromise = Promise.all([['Inter-ExtraBold', 800], ['Inter-SemiBold', 600]].map(async ([file, weight]) => {
      const res = await fetch(`${origin}/assets/fonts/${file}.otf`);
      if (!res.ok) throw new Error(`font ${file} ${res.status}`);
      return { name: 'Inter', data: await res.arrayBuffer(), weight, style: 'normal' };
    })).catch(e => { fontsPromise = null; throw e; });
  }
  return fontsPromise;
}

function loadCards(origin, kind) {
  if (!dataPromises[kind]) {
    dataPromises[kind] = fetch(`${origin}/og-data/${kind}.json`).then(res => {
      if (!res.ok) throw new Error(`og-data ${kind} ${res.status}`);
      return res.json();
    }).catch(e => { delete dataPromises[kind]; throw e; });
  }
  return dataPromises[kind];
}

// ESPN image URL -> data: URI the renderer can draw, or null if it is not an ESPN image, is slow, or is not a small PNG or JPEG.
async function toDataUri(url) {
  try {
    if (!url) return null;
    const u = new URL(url);
    if (u.protocol !== 'https:' || u.hostname !== IMAGE_HOST) return null;
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 2500);
    const res = await fetch(u, { signal: ctl.signal });
    clearTimeout(timer);
    const type = (res.headers.get('content-type') || '').split(';')[0];
    if (!res.ok || !/^image\/(png|jpeg)$/.test(type)) return null;
    const bytes = new Uint8Array(await res.arrayBuffer());
    if (bytes.length > 1_500_000) return null;
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return `data:${type};base64,${btoa(bin)}`;
  } catch {
    return null;
  }
}

async function handler(request) {
  const url = new URL(request.url);
  const kind = url.searchParams.get('k');
  const slug = url.searchParams.get('s') || '';
  const fallback = () => Response.redirect(`${url.origin}/og-image.png`, 302);
  if (!KINDS.has(kind) || !/^[a-z0-9-]{1,90}$/.test(slug)) return fallback();

  try {
    const [{ asOf, cards }, fonts] = await Promise.all([loadCards(url.origin, kind), loadFonts(url.origin)]);
    const c = cards[slug];
    if (!c) return fallback();
    const [main, logo] = await Promise.all([toDataUri(c.i), toDataUri(c.g)]);
    // Draw to bytes here (not as a streamed ImageResponse) so a render error lands in the catch and becomes the fallback, not a broken 500.
    // @vercel/og is ES-module only and Vercel compiles this file to CommonJS, so it has to be loaded with a dynamic import.
    const { ImageResponse } = await import('@vercel/og');
    const png = await new ImageResponse(card(c, { main, logo }, asOf), { width: W, height: H, fonts }).arrayBuffer();
    return new Response(png, { headers: { 'Content-Type': 'image/png', 'Cache-Control': CACHE } });
  } catch (e) {
    console.error('og card failed', kind, slug, e && e.message);
    return fallback();
  }
}

// Web-standard handler shape: Vercel's Node runtime then passes a real Request (with a full URL) and accepts a Response back.
export default { fetch: handler };
