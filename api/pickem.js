// Vercel function: Pick'em results by email (The Cap Sheet).
//
// POST {action: 'join', email, season, picks}        opt in: saves the picks with the email in Airtable (table Pickem) and
//                                                     subscribes the email to The Cap Sheet on beehiiv (double opt-in).
//                                                     Returns {key}: the browser keeps it and sends it with every later call.
//                                                     The first join imports every pick this browser has made this season.
// POST {action: 'sync', email, key, season, picks}   the browser's picks changed. Games that have kicked off keep the pick
//                                                     stored before kickoff (see mergePicks), so results cannot be edited in.
// POST {action: 'stop', email, key}                  removes the row and blanks the three beehiiv fields; the Cap Sheet
//                                                     subscription stays (the email's unsubscribe link ends it).
// GET  (Vercel cron, Tuesday; Authorization: Bearer CRON_SECRET)   grades every row of this season and writes three
//                                                     custom fields on the beehiiv subscriber: pickem_week, pickem_season,
//                                                     pickem_model. ?dry=1 grades and writes Airtable only.
//
// Env (Vercel project settings): AIRTABLE_TOKEN (needs write access to the Cap Tracker base), BEEHIIV_API_KEY,
// BEEHIIV_PUBLICATION_ID, CRON_SECRET. Optional: AIRTABLE_PICKEM_TABLE, SITE_URL.

const crypto = require('crypto');
const G = require('./_pickem-grade');

const BASE = process.env.AIRTABLE_BASE_ID || 'app7vEpDdwBT0xCUr';            // Cap Tracker base
const TABLE = process.env.AIRTABLE_PICKEM_TABLE || 'tblqSmDZIhlnFuWTm';       // Pickem table
const SITE = (process.env.SITE_URL || 'https://www.plainstatsnfl.com').replace(/\/$/, '');
const BH = 'https://api.beehiiv.com/v2/publications/';
const EMAIL = /^[^\s@'"\\<>,;]{1,64}@[^\s@'"\\<>,;]{1,190}\.[A-Za-z]{2,24}$/;

const at = () => ({ Authorization: `Bearer ${process.env.AIRTABLE_TOKEN}`, 'Content-Type': 'application/json' });
const tableUrl = () => `https://api.airtable.com/v0/${BASE}/${TABLE}`;

async function airtable(path, opts = {}) {
  const r = await fetch(tableUrl() + path, Object.assign({ headers: at() }, opts));
  if (!r.ok) throw new Error(`Airtable ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}
async function findRow(email, season) {
  const f = `AND(LOWER({Email})='${email}',{Season}=${season})`;
  const j = await airtable(`?maxRecords=1&filterByFormula=${encodeURIComponent(f)}`);
  return j.records[0] || null;
}
async function allRows(season) {
  const rows = []; let offset;
  do {
    const j = await airtable(`?pageSize=100&filterByFormula=${encodeURIComponent(`{Season}=${season}`)}${offset ? '&offset=' + offset : ''}`);
    rows.push(...j.records); offset = j.offset;
  } while (offset);
  return rows;
}
async function patchRows(updates) {   // Airtable takes 10 records per request
  for (let i = 0; i < updates.length; i += 10) await airtable('', { method: 'PATCH', body: JSON.stringify({ records: updates.slice(i, i + 10) }) });
}

async function siteJSON(path) {
  const r = await fetch(`${SITE}/${path}`, { headers: { 'Cache-Control': 'no-cache' } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function beehiiv(path, method, body) {
  return fetch(BH + process.env.BEEHIIV_PUBLICATION_ID + path, {
    method, headers: { Authorization: `Bearer ${process.env.BEEHIIV_API_KEY}`, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined
  });
}
async function subscribe(email) {
  if (!process.env.BEEHIIV_API_KEY || !process.env.BEEHIIV_PUBLICATION_ID) return 'beehiiv not configured';
  const r = await beehiiv('/subscriptions', 'POST', {
    email, reactivate_existing: false, send_welcome_email: true, double_opt_override: 'on',
    utm_source: 'plainstats', utm_medium: 'pickem', utm_campaign: 'pickem_email', referring_site: SITE + '/scores'
  });
  return r.ok ? '' : `beehiiv ${r.status}`;
}
async function setFields(email, s) {
  const custom_fields = [{ name: 'pickem_week', value: s.week }, { name: 'pickem_season', value: s.season }, { name: 'pickem_model', value: s.model }];
  let r = await beehiiv(`/subscriptions/by_email/${encodeURIComponent(email)}`, 'PUT', { custom_fields });
  if (r.status === 404 || r.status === 405) {   // fall back to looking the subscriber up, then updating by id
    const g = await beehiiv(`/subscriptions/by_email/${encodeURIComponent(email)}`, 'GET');
    if (!g.ok) return `beehiiv lookup ${g.status}`;
    const id = ((await g.json()).data || {}).id; if (!id) return 'not a subscriber';
    r = await beehiiv(`/subscriptions/${id}`, 'PATCH', { custom_fields });
  }
  return r.ok ? '' : `beehiiv ${r.status}`;
}

const bad = (res, code, msg) => res.status(code).json({ error: msg });
const same = (a, b) => { const x = Buffer.from(String(a || '')), y = Buffer.from(String(b || '')); return x.length === y.length && crypto.timingSafeEqual(x, y); };

async function weekly(req, res) {
  const auth = req.headers.authorization || '';
  if (!process.env.CRON_SECRET || !same(auth, `Bearer ${process.env.CRON_SECRET}`)) return bad(res, 401, 'Not allowed.');
  const dry = req.query && req.query.dry === '1';
  const [sched, proj] = await Promise.all([siteJSON('data/schedule.json'), siteJSON('data/projections.json').catch(() => null)]);
  const games = sched.games, rows = await allRows(sched.season), now = new Date().toISOString(), out = { rows: rows.length, sent: 0, errors: 0, week: G.lastDoneWeek(games) };
  const updates = [];
  for (const row of rows) {
    let picks = {}; try { picks = JSON.parse(row.fields.Picks || '{}'); } catch (e) { /* empty */ }
    const s = G.summary(picks, games, proj);
    const err = dry ? '' : await setFields(row.fields.Email, s).catch(e => String(e.message || e).slice(0, 90));
    err ? out.errors++ : dry || out.sent++;
    const f = { Week: s.week, 'Season record': s.season, 'Vs model': s.model, Error: err };
    if (!dry && !err) f.Emailed = now;
    updates.push({ id: row.id, fields: f });
  }
  await patchRows(updates);
  console.log('pickem weekly', JSON.stringify(out));
  res.status(200).json(out);
}

async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (!process.env.AIRTABLE_TOKEN) return bad(res, 500, 'Pick\'em email is not set up yet.');
  try {
    if (req.method === 'GET') return await weekly(req, res);
    if (req.method !== 'POST') return bad(res, 405, 'Use POST.');
    let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } }
    b = b || {};
    if (b.website) return res.status(200).json({ ok: true });   // honeypot: bots fill every field
    const email = String(b.email || '').trim().toLowerCase();
    if (!EMAIL.test(email) || email.length > 254) return bad(res, 400, 'That email address does not look right.');
    const sched = await siteJSON('data/schedule.json'), season = sched.season, games = sched.games;
    const row = await findRow(email, season), now = new Date().toISOString();

    if (b.action === 'join') {
      if (row && !same(b.key, row.fields.Key)) return bad(res, 409, 'That email is already getting Pick\'em results from another phone or browser. Use that one, or write to us to move it.');
      const incoming = G.cleanPicks(b.picks, games);
      const key = row ? row.fields.Key : crypto.randomBytes(18).toString('base64url');
      // First opt-in brings the season this browser already played (there are no prizes or leaderboard, so a fan's own
      // history is taken as is); from then on a game's pick is frozen at kickoff.
      const picks = row ? G.mergePicks(JSON.parse(row.fields.Picks || '{}'), incoming, games) : incoming;
      const fields = { Email: email, Season: season, Key: key, Picks: JSON.stringify(picks), Updated: now };
      if (row) await airtable('', { method: 'PATCH', body: JSON.stringify({ records: [{ id: row.id, fields }] }) });
      else await airtable('', { method: 'POST', body: JSON.stringify({ records: [{ fields: Object.assign(fields, { Joined: now }) }] }) });
      const err = row ? '' : await subscribe(email).catch(e => String(e.message || e));
      if (err) console.error('pickem subscribe:', err);
      return res.status(200).json({ key, saved: Object.keys(picks).length });
    }
    if (!row || !same(b.key, row.fields.Key)) return bad(res, 403, 'This browser is not linked to that email.');
    if (b.action === 'sync') {
      const picks = G.mergePicks(JSON.parse(row.fields.Picks || '{}'), G.cleanPicks(b.picks, games), games);
      await airtable('', { method: 'PATCH', body: JSON.stringify({ records: [{ id: row.id, fields: { Picks: JSON.stringify(picks), Updated: now } }] }) });
      return res.status(200).json({ saved: Object.keys(picks).length });
    }
    if (b.action === 'stop') {
      await airtable(`?records[]=${row.id}`, { method: 'DELETE' });
      if (process.env.BEEHIIV_API_KEY) await setFields(email, { week: '', season: '', model: '' }).catch(() => {});   // so old lines stop showing
      return res.status(200).json({ stopped: true });
    }
    return bad(res, 400, 'Unknown action.');
  } catch (e) {
    console.error('pickem:', e);
    return bad(res, 502, 'Could not save right now. Try again in a minute.');
  }
}

module.exports = handler;
