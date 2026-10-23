// Vercel function: fetches ESPN's public NFL team + roster lists server-side.
//   /api/espn-csv            -> downloadable CSV (team_id, team_name, logo_url, player, position, headshot_url)
//   /api/espn-csv?format=json -> {teams, players} in the shape the site reads (data/espn_assets.json)
const BASE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl';
const FIX = { WSH: 'WAS', JAC: 'JAX' };
const norm = n => n.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/[^a-z]/g, '');
// Quote for CSV; a leading = + - @ would run as a formula in Excel or Sheets, so prefix it with '.
const q = v => { let t = String(v); if (/^[=+\-@\t\r]/.test(t)) t = "'" + t; return '"' + t.replace(/"/g, '""') + '"'; };
const j = async u => { const r = await fetch(u, { headers: { 'User-Agent': 'PlainStats/1.0' } }); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); };

module.exports = async (req, res) => {
  try {
    const teams = (await j(BASE + '/teams')).sports[0].leagues[0].teams.map(t => t.team);
    const rosters = await Promise.all(teams.map(t => j(`${BASE}/teams/${t.id}/roster`).catch(() => ({ athletes: [] }))));
    const rows = [['team_id', 'team_name', 'logo_url', 'player', 'position', 'headshot_url']];
    const assets = { teams: {}, players: {} };
    teams.forEach((t, i) => {
      const id = FIX[t.abbreviation] || t.abbreviation;
      const logos = t.logos || [];
      const logo = (logos.find(l => (l.rel || []).includes('default')) || logos[0] || {}).href || `https://a.espncdn.com/i/teamlogos/nfl/500/${t.abbreviation.toLowerCase()}.png`;
      assets.teams[id] = { logo, name: t.displayName };
      for (const g of rosters[i].athletes || []) for (const a of g.items || []) {
        const name = a.fullName || a.displayName; if (!name) continue;
        const hs = (a.headshot && a.headshot.href) || `https://a.espncdn.com/i/headshots/nfl/players/full/${a.id}.png`;
        rows.push([id, t.displayName, logo, name, (a.position || {}).abbreviation || '', hs]);
        assets.players[id + '|' + norm(name)] = hs;
      }
    });
    res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=604800');
    res.setHeader('Access-Control-Allow-Origin', '*');
    if (req.query && req.query.format === 'json') return res.status(200).json(assets);
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="plainstats_espn_assets.csv"');
    res.status(200).send(rows.map(r => r.map(q).join(',')).join('\n') + '\n');
  } catch (e) {
    console.error('espn-csv:', e);
    res.status(502).json({ error: 'Could not read ESPN right now. Try again in a few minutes.' });
  }
};
