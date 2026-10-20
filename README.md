# Plain Cap

Every NFL contract and team salary cap in plain English, for everyday fans.

## Files
- `src.html` is the page (also published as the Plain Cap artifact). Edit this one.
- `build.sh` wraps `src.html` into `index.html`, which Vercel serves. On a phone, edit `index.html` directly in Koder and make the same change in `src.html`.
- `data/nfl.json` holds all 32 teams' cap figures and every player contract. `data/moves.json` is the news feed and trade deadline date. A daily scheduled task refreshes both.
- `api/contracts.js` reads the featured deal breakdowns from Airtable (optional).
- `data/contracts.csv` is the starting data for the Airtable `Contracts` table.

## Vercel settings
Add `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID` and, if your table has another name, `AIRTABLE_TABLE`. Without them the page shows its built-in breakdowns.

## Views
Open a view directly with its anchor: `#home`, `#news`, `#teams`, `#team-KC` (any team code), `#contracts`, `#tools`, `#cut`, `#trade`, `#compare`, `#decode`, `#learn`.
