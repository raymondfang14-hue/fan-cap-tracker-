// Vercel function: reads the Contracts table from Airtable and returns it
// in the same shape the page uses for its built-in data.

const lines = s => String(s || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const parts = line => line.split('|').map(x => x.trim());
const num = v => { const x = Number(v); return Number.isFinite(x) ? x : 0; };

function toContract(f) {
  const c = {
    league: f.League || '',
    pos: f.Position || '',
    name: f.Name || '',
    team: f.Team || '',
    aav: num(f.NewMoneyPerYear),
    head: f.Headline || '',
    sub: f.Subhead || '',
    scale: num(f.Scale),
    scaleNote: f.ScaleNote || '',
    bar: lines(f.Bar).map(l => { const [k, v, label, shown] = parts(l); return [k, num(v), label || '', shown || '']; }),
    facts: lines(f.Facts).map(l => parts(l).slice(0, 2)),
    plain: f.Plain || '',
    watch: f.Watch || ''
  };
  if (f.ThisSeasonCapHit !== undefined && f.ThisSeasonCapHit !== '') c.hit = num(f.ThisSeasonCapHit);
  if (f.TableRows) {
    c.table = {
      title: f.TableTitle || 'Cap hit by year',
      cols: parts(f.TableCols || ''),
      rows: lines(f.TableRows).map(parts),
      note: f.TableNote || ''
    };
  }
  return c;
}

async function handler(req, res) {
  const token = process.env.AIRTABLE_TOKEN;
  const base = process.env.AIRTABLE_BASE_ID || 'app7vEpDdwBT0xCUr'; // Cap Tracker base
  const table = process.env.AIRTABLE_TABLE || 'tblMvDcAIUpr9Zuor'; // the deals table
  if (!token) {
    res.status(500).json({ error: 'Set AIRTABLE_TOKEN in the Vercel project settings.' });
    return;
  }
  try {
    const records = [];
    let offset;
    do {
      const url = new URL(`https://api.airtable.com/v0/${base}/${encodeURIComponent(table)}`);
      url.searchParams.set('pageSize', '100');
      url.searchParams.set('sort[0][field]', 'Sort');
      if (offset) url.searchParams.set('offset', offset);
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`Airtable answered ${r.status}`);
      const j = await r.json();
      records.push(...j.records);
      offset = j.offset;
    } while (offset);
    const contracts = records.map(r => toContract(r.fields)).filter(c => c.name && c.league);
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    res.status(200).json({ updated: new Date().toISOString(), contracts });
  } catch (e) {
    console.error('contracts:', e);
    res.status(502).json({ error: 'Could not read the deals table right now.' });
  }
}

module.exports = handler;
module.exports.toContract = toContract;
