# Plain Cap

Every NFL contract and team salary cap in plain English, for everyday fans.

## Files
- `src.html` is the page (also published as the Plain Cap artifact). Edit this one.
- `build.sh` wraps `src.html` into `index.html`, which Vercel serves. On a phone, edit `index.html` directly in Koder and make the same change in `src.html`.
- `data/nfl.json` holds all 32 teams' cap figures and every player contract. `data/moves.json` is the NFL news feed (contract moves, injuries, games, coaching, league news) and the trade deadline date. A daily scheduled task refreshes both.
- `api/contracts.js` reads the featured deal breakdowns from Airtable (optional).
- `data/contracts.csv` is the starting data for the Airtable `Contracts` table.

## Vercel settings
Add `AIRTABLE_TOKEN` (a personal access token with `data.records:read` on the Cap Tracker base). The function already points at the Cap Tracker base and its deals table; set `AIRTABLE_BASE_ID` or `AIRTABLE_TABLE` only to use a different one. Without them the page shows its built-in breakdowns.

## Views
Open a view directly with its anchor (`#teams` has the power ratings, and each `#team-XX` page has ratings, traits, lineup and depth chart): `#home`, `#news`, `#teams`, `#team-KC` (any team code), `#contracts`, `#tools`, `#builder` (Roster Builder), `#cut`, `#trade`, `#compare`, `#decode`, `#learn`.
