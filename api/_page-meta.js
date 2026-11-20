// Page titles, descriptions, canonicals and social card images for app paths (/team-tiers, /team/kc, /player/<slug>, ...).
// Shared by api/page.js (Vercel) and cf/worker.js (Cloudflare) so the two hosts can never give a page different heads.
// C = { meta: { ROUTES, PTITLE, PDESC, TEAMSUBS } from index.html, teams: { kc: {city, name} }, slugs: data/pageslugs.json,
//       cards: { players, teams, draft } from og-data (only .t is read), asOf: data date for the og:image URL }.
export const SITE = 'https://www.plainstatsnfl.com';
export const DEFAULT_DESC = "NFL analytics in plain English: player ratings, team rankings, stats and contracts. Who's good, who's paid and whether it's worth it.";
export const esc = s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
export const slugify = s => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

// -> { title, desc, canon, img } for an app path, or null when the path is not an app page.
export function pageMeta(path, C) {
  const { meta, teams, slugs, cards } = C;
  const og = (k, s) => `${SITE}/api/og?k=${k}&s=${s}&v=${C.asOf}`;
  const route = meta.ROUTES.find(([, p]) => p === path);
  if (route && route[0] !== 'home') {
    const k = route[0];
    // /links/instagram, /links/tiktok and /links/facebook are the same page as /links (they only exist so each platform counts as its own path)
    return { title: (meta.PTITLE[k] || 'PlainStats') + ' · PlainStats', desc: meta.PDESC[k] || DEFAULT_DESC, canon: SITE + (/^links-/.test(k) ? '/links' : path) };
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
    const P = slugs.p || {};
    let key = 'p-' + m[1] + '-' + m[2];
    if (!P[key]) {
      // an old address from before a trade (/player/joe-milton-iii-den): find the player under his new team, as the app's
      // openPending() does; only when exactly one player has that name, so two players who share a name are never mixed up
      const re = new RegExp('^p-' + m[1] + '-[a-z]{2,3}$'), hits = Object.keys(P).filter(k => re.test(k));
      if (hits.length === 1) key = hits[0];
    }
    const stat = P[key], card = stat && cards.players[stat];
    const name = card ? card.t : m[1].split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    const t = teams[key.slice(key.lastIndexOf('-') + 1)] || teams[m[2]];
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

export function withHead(html, pm) {
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
