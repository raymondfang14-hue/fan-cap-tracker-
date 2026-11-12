// Pick'em grading, shared by api/pickem.js. The same rules as pkGrade / pkTally / pkLocked in src.html:
// a pick counts only for a final, non-tied game; it is graded against the model pick the fan saw when picking (pick.m),
// or the weekly model pick (data/projections.json) for older picks without one. Picks lock at kickoff.
// Schedule rows (data/schedule.json games): [id, week, date, time ET, away, home, awayScore, homeScore, ot, site].

const final = g => g[6] != null && g[7] != null;

// kickoff in ms from the schedule's Eastern date and time (the page uses the same rule when gameday.json has no time)
function kickoff(g) {
  const [y, mo, d] = g[2].split('-').map(Number), [h, mi] = (g[3] || '00:00').split(':').map(Number);
  let off = -5;
  try {
    const z = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', timeZoneName: 'shortOffset' }).formatToParts(Date.UTC(y, mo - 1, d, 12)).find(x => x.type === 'timeZoneName');
    const m = z && z.value.match(/GMT([+-]\d+)/); if (m) off = +m[1];
  } catch (e) { /* keep -5 */ }
  return Date.UTC(y, mo - 1, d, h - off, mi);
}
const locked = (g, now = Date.now()) => final(g) || now >= kickoff(g);

const TEAM = /^[A-Z]{2,3}$/;
// Clean a picks object from the browser: known games of this season only, team must be one of the two sides.
function cleanPicks(raw, games) {
  const byId = new Map(games.map(g => [g[0], g])), out = {};
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return out;
  for (const [id, p] of Object.entries(raw).slice(0, 400)) {
    const g = byId.get(id);
    if (!g || !p || typeof p !== 'object' || !TEAM.test(p.t || '') || (p.t !== g[4] && p.t !== g[5])) continue;
    out[id] = { t: p.t, m: p.m === g[4] || p.m === g[5] ? p.m : null, at: Number.isFinite(+p.at) ? +p.at : null };
  }
  return out;
}

// What the server keeps when a browser sends its picks: a game that has kicked off keeps the pick stored before kickoff
// (or stays unpicked); only open games take the browser's version. So nobody can pick, or change a pick, after the result.
function mergePicks(stored, incoming, games, now = Date.now()) {
  const out = {};
  for (const g of games) {
    const id = g[0];
    const src = locked(g, now) ? stored : incoming;
    if (src[id]) out[id] = src[id];
  }
  return out;
}

function grade(g, pk, proj) {
  if (!pk || !final(g) || g[6] === g[7]) return null;
  const win = g[7] > g[6] ? g[5] : g[4], P = proj && proj.games && proj.games[g[0]];
  const m = pk.m || (P ? (P[0] >= 0.5 ? g[5] : g[4]) : null);
  return { you: +(pk.t === win), model: m ? +(m === win) : null, diff: !!m && m !== pk.t };
}

function tally(picks, games, proj, filter) {
  const o = { w: 0, l: 0, mw: 0, ml: 0, dw: 0, dl: 0, n: 0 };
  for (const g of games) {
    if (filter && !filter(g)) continue;
    const r = grade(g, picks[g[0]], proj); if (!r) continue;
    o.n++; r.you ? o.w++ : o.l++;
    if (r.model != null) r.model ? o.mw++ : o.ml++;
    if (r.diff) r.you ? o.dw++ : o.dl++;
  }
  return o;
}

// The last week whose games are all final (on Tuesday morning: the week that just ended with Monday night).
function lastDoneWeek(games) {
  const weeks = [...new Set(games.map(g => g[1]))].sort((a, b) => a - b);
  let done = 0;
  for (const w of weeks) { if (games.filter(g => g[1] === w).every(final)) done = w; else break; }
  return done;
}

const pct = (w, l) => (w + l ? ` (${Math.round(w / (w + l) * 100)}%)` : '');
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

// The three lines that go into The Cap Sheet as beehiiv custom fields.
function summary(picks, games, proj) {
  const wk = lastDoneWeek(games), W = tally(picks, games, proj, g => g[1] === wk), T = tally(picks, games, proj);
  const week = !wk ? 'No finished weeks yet' : W.n ? `Week ${wk}: you went ${W.w}-${W.l}, the model went ${W.mw}-${W.ml}` : `Week ${wk}: no picks`;
  const season = T.n ? `${T.w}-${T.l}${pct(T.w, T.l)} this season` : 'No graded picks yet';
  const d = T.w - T.mw;
  const model = !T.n ? 'Make your picks on plainstatsnfl.com/scores' : d > 0 ? `You lead the model by ${plural(d, 'pick')} (model ${T.mw}-${T.ml})` : d < 0 ? `The model leads you by ${plural(-d, 'pick')} (model ${T.mw}-${T.ml})` : `You and the model are tied at ${T.w}-${T.l}`;
  return { week, season, model, wk, W, T };
}

module.exports = { final, kickoff, locked, cleanPicks, mergePicks, grade, tally, lastDoneWeek, summary };
