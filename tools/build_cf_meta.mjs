// Writes cf/_meta.json, the data cf/worker.js needs to give app paths their own <head> on Cloudflare (run by tools/build_cf.py).
// It is the same input api/page.js loads at run time on Vercel, worked out once at deploy instead, because Workers can't
// run node:vm and the free plan's CPU limit is small:
//   meta   ROUTES, PTITLE, PDESC, TEAMSUBS evaluated from the ROUTES ... teamSub block of index.html (so titles never drift from the app)
//   teams  { kc: { city, name } } from data/nfl.json      slugs  data/pageslugs.json      asOf  nfl.json's data date
//   cards  og-data players / teams / draft, keeping only the name (t) pageMeta() reads
// Generated, gitignored; never edit by hand.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = f => fs.readFileSync(path.join(root, f), 'utf8');
const json = (f, dflt) => { try { return JSON.parse(read(f)); } catch (e) { if (dflt !== undefined) return dflt; throw e; } };

const html = read('index.html');
const a = html.indexOf('const ROUTES = ['), b = html.indexOf('let teamSub');
if (a < 0 || b < a) throw new Error('route block not found in index.html');
const meta = vm.runInNewContext(html.slice(a, b) + ';({ ROUTES, PTITLE, PDESC, TEAMSUBS })', {}, { timeout: 2000 });

const nfl = json('data/nfl.json');
const teams = {};
for (const t of nfl.teams) teams[t.id.toLowerCase()] = { city: t.city, name: t.name };

const names = kind => {
  const out = {};
  for (const [slug, c] of Object.entries(json(`og-data/${kind}.json`, { cards: {} }).cards || {})) out[slug] = { t: c.t };
  return out;
};

// App paths (from vercel.json's rewrites to "/") and the bot user agents (its first, bot-only rewrite), so the Worker matches
// exactly the paths and bots Vercel did.
const vj = json('vercel.json');
const bot = vj.rewrites.find(r => r.has && r.destination.startsWith('/api/page'));
const toRe = src => '^' + src.replace(/:\w+\(([^)]*)\)/g, '($1)').replace(/:\w+/g, '[a-z0-9-]+') + '/?$';
const apps = vj.rewrites.filter(r => r.destination === '/' && !r.has).map(r => toRe(r.source));
const botUA = bot ? bot.has[0].value : '';

const C = { apps, botUA, meta, teams, slugs: json('data/pageslugs.json', { p: {}, d: {} }), cards: { players: names('players'), teams: names('teams'), draft: names('draft') }, asOf: nfl.asOf };
fs.writeFileSync(path.join(root, 'cf/_meta.json'), JSON.stringify(C));
console.log(`cf/_meta.json: ${meta.ROUTES.length} routes, ${Object.keys(teams).length} teams, ${Object.keys(C.cards.players).length} player cards`);
