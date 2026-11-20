// Draw every social card ahead of time for the Cloudflare deploy (Cloudflare's free Workers plan allows ~10 ms of CPU per
// request, too little to draw a card on demand the way api/og.js does on Vercel).
//
//   node tools/render_og.mjs DIST_DIR [CACHE_DIR]
//
// Reads og-data/<kind>.json (written by tools/build_seo.py) and writes DIST_DIR/og/<kind>/<slug>.png with the same layout
// (api/_og-layout.js), fonts and @vercel/og renderer as api/og.js. cf/worker.js answers /api/og?k=&s= with that file, so the
// og:image URLs on the pages don't change. ESPN headshots and logos are fetched here (GitHub Actions can reach ESPN; a missing
// image shows initials, as on Vercel).
//
// CACHE_DIR (kept between runs by actions/cache) holds the last PNG of each card and the key it was drawn from (card text,
// date, layout and fonts). A card whose key has not changed is copied, not redrawn; a card drawn without its image is
// redrawn next time.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const KINDS = ['players', 'teams', 'draft', 'pages'];
const IMAGE_HOST = 'a.espncdn.com';

if (!isMainThread) {
  // Render worker: gets { file, card, imgs, asOf }, writes the PNG, answers with the file name.
  const { ImageResponse } = await import('@vercel/og');
  const { card, W, H } = await import(pathToFileURL(path.join(root, 'api/_og-layout.js')).href);
  const fonts = [['Inter-ExtraBold', 800], ['Inter-SemiBold', 600]].map(([f, weight]) =>
    ({ name: 'Inter', data: fs.readFileSync(path.join(root, 'assets/fonts', f + '.otf')), weight, style: 'normal' }));
  parentPort.on('message', async job => {
    try {
      const png = Buffer.from(await new ImageResponse(card(job.card, job.imgs, job.asOf), { width: W, height: H, fonts }).arrayBuffer());
      fs.mkdirSync(path.dirname(job.file), { recursive: true });
      fs.writeFileSync(job.file, png);
      parentPort.postMessage({ file: job.file });
    } catch (e) {
      parentPort.postMessage({ file: job.file, error: String(e && e.message || e) });
    }
  });
} else {
  const [dist, cacheDir = path.join(root, '.og-cache')] = process.argv.slice(2);
  if (!dist) { console.error('usage: node tools/render_og.mjs DIST_DIR [CACHE_DIR]'); process.exit(1); }
  const pngDir = path.join(cacheDir, 'png');
  const manifestFile = path.join(cacheDir, 'manifest.json');
  let manifest = {};
  try { manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8')); } catch {}

  const base = crypto.createHash('sha1');
  for (const f of ['api/_og-layout.js', 'assets/fonts/Inter-ExtraBold.otf', 'assets/fonts/Inter-SemiBold.otf']) base.update(fs.readFileSync(path.join(root, f)));
  const baseKey = base.digest('hex');

  const imgCache = new Map();
  async function toDataUri(url) {
    if (!url) return null;
    if (!imgCache.has(url)) imgCache.set(url, (async () => {
      try {
        const u = new URL(url);
        if (u.protocol !== 'https:' || u.hostname !== IMAGE_HOST) return null;
        const res = await fetch(u, { signal: AbortSignal.timeout(8000) });
        const type = (res.headers.get('content-type') || '').split(';')[0];
        if (!res.ok || !/^image\/(png|jpeg)$/.test(type)) return null;
        const bytes = Buffer.from(await res.arrayBuffer());
        return bytes.length > 1_500_000 ? null : `data:${type};base64,${bytes.toString('base64')}`;
      } catch { return null; }
    })());
    return imgCache.get(url);
  }

  const jobs = [];
  const next = {};
  let reused = 0;
  for (const kind of KINDS) {
    const { asOf, cards } = JSON.parse(fs.readFileSync(path.join(root, 'og-data', kind + '.json'), 'utf8'));
    for (const [slug, c] of Object.entries(cards)) {
      if (!/^[a-z0-9-]{1,90}$/.test(slug)) continue;
      const id = `${kind}/${slug}`;
      const key = crypto.createHash('sha1').update(baseKey + JSON.stringify(c) + asOf).digest('hex');
      const cached = path.join(pngDir, kind, slug + '.png');
      if (manifest[id] === key && fs.existsSync(cached)) { next[id] = key; reused++; continue; }
      jobs.push({ id, key, kind, slug, c, asOf, file: cached });
    }
  }

  const n = Math.max(1, Math.min(os.cpus().length, 8));
  const workers = Array.from({ length: n }, () => new Worker(fileURLToPath(import.meta.url)));
  let drawn = 0, failed = 0, noImage = 0, i = 0;
  const run = w => new Promise(resolve => {
    const take = async () => {
      if (i >= jobs.length) return resolve();
      const j = jobs[i++];
      const want = j.c.m !== 'brand';
      const [main, logo] = want ? await Promise.all([toDataUri(j.c.i), toDataUri(j.c.g)]) : [null, null];
      const missing = want && ((j.c.i && !main) || (j.c.g && !logo));
      w.once('message', m => {
        if (m.error) { failed++; console.error('card failed', j.id, m.error); }
        else {
          drawn++;
          if (missing) noImage++;
          next[j.id] = missing ? 'retry' : j.key; // drawn without its image: redraw next run
        }
        take();
      });
      w.postMessage({ file: j.file, card: j.c, imgs: { main, logo }, asOf: j.asOf });
    };
    take();
  });
  await Promise.all(workers.map(run));
  await Promise.all(workers.map(w => w.terminate()));

  // Copy every current card into dist/og/ (and drop cards that no longer exist from the cache).
  for (const id of Object.keys(next)) {
    const src = path.join(pngDir, id + '.png'), dst = path.join(dist, 'og', id + '.png');
    if (!fs.existsSync(src)) { delete next[id]; continue; }
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }
  for (const id of Object.keys(manifest)) if (!(id in next)) fs.rmSync(path.join(pngDir, id + '.png'), { force: true });
  fs.mkdirSync(cacheDir, { recursive: true });
  fs.writeFileSync(manifestFile, JSON.stringify(next));
  console.log(`og cards: ${drawn} drawn (${noImage} without an image), ${reused} unchanged, ${failed} failed`);
  if (failed > jobs.length / 10 && failed > 5) process.exit(1);
}
