// Preview the social cards in a browser without Vercel. Turns the same element tree api/og.js draws into plain HTML.
//
//   node tools/preview_og.mjs OUT_DIR [IMAGE_DIR] [kind/slug ...]
//
// Writes OUT_DIR/<kind>__<slug>.html (1200x630, Inter loaded from assets/fonts). Pass IMAGE_DIR with head.png and logo.png to stand in
// for ESPN's images when the machine can't reach them (omit it to see the initials fallback). With no kind/slug list it writes a mixed sample.
// Screenshot the files with any browser at 1200x630 (python3 -I tools/shot_og.py OUT_DIR does it with Playwright).
// This is Chromium's flexbox, close to Satori's but not identical, so the final check is the live /api/og URL.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { card, W, H } from '../api/_og-layout.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [out, imgDir, ...picks] = process.argv.slice(2);
if (!out) { console.error('usage: node tools/preview_og.mjs OUT_DIR [IMAGE_DIR] [kind/slug ...]'); process.exit(1); }
fs.mkdirSync(out, { recursive: true });

const uri = f => imgDir && fs.existsSync(path.join(imgDir, f)) ? 'data:image/png;base64,' + fs.readFileSync(path.join(imgDir, f)).toString('base64') : null;
const imgs = { main: uri('head.png'), logo: uri('logo.png') };

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const UNITLESS = new Set(['fontWeight', 'lineHeight', 'opacity', 'flex', 'flexGrow']);
const css = s => Object.entries(s || {}).map(([k, v]) => `${k.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}:${typeof v === 'number' && !UNITLESS.has(k) ? v + 'px' : v}`).join(';');
const html = n => n == null || n === false ? '' : typeof n === 'string' || typeof n === 'number' ? esc(n) : Array.isArray(n) ? n.map(html).join('')
  : n.type === 'img' ? `<img src="${n.props.src}" style="${css(n.props.style)}">` : `<${n.type} style="${css(n.props.style)}">${html(n.props.children)}</${n.type}>`;

const font = (file, w) => `@font-face{font-family:Inter;font-weight:${w};src:url(data:font/otf;base64,${fs.readFileSync(path.join(root, 'assets/fonts', file)).toString('base64')})}`;
const page = body => `<!doctype html><meta charset="utf-8"><style>${font('Inter-ExtraBold.otf', 800)}${font('Inter-SemiBold.otf', 600)}*{box-sizing:border-box;margin:0}body{width:${W}px;height:${H}px;overflow:hidden}</style>${body}`;

const wanted = picks.length ? picks : ['players/patrick-mahomes', 'players/aaron-banks', 'players/antoine-winfield-jr', 'players/matt-stafford', 'teams/chiefs', 'teams/cardinals-dead-money', 'teams/packers-cap', 'draft/jeremiah-smith', 'pages/teams', 'pages/draft'];
for (const w of wanted) {
  const [kind, slug] = w.split('/');
  const file = path.join(root, 'og-data', `${kind}.json`);
  const { asOf, cards } = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!cards[slug]) { console.error('no card', w); continue; }
  const c = cards[slug];
  // brand cards never draw images; keep the preview honest about the initials fallback when no IMAGE_DIR is given
  fs.writeFileSync(path.join(out, `${kind}__${slug}.html`), page(html(card(c, imgs, asOf))));
}
console.log(`wrote ${wanted.length} previews to ${out}`);
