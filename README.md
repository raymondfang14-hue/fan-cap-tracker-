# Plain Cap

Every NFL contract and team salary cap in plain English, for everyday fans.

## Files
- `src.html` is the page (also published as the Plain Cap artifact). Edit this one.
- `build.sh` wraps `src.html` into `index.html`, which Vercel serves. On a phone, edit `index.html` directly in Koder and make the same change in `src.html`.
- `data/nfl.json` holds all 32 teams' cap figures and every player contract. `data/moves.json` is the NFL news feed (contract moves, injuries, games, coaching, league news) and the trade deadline date. A daily scheduled task refreshes both.
- `data/season.json` holds standings (record, points for and against), head coaches, 2025 records, the rookie and comeback-candidate lists, and `prevRanks` (last week's power ranking, for the movement arrows). It feeds the Awards and Power rankings page (`#awards`, `#rankings`), which scores everything in the browser from `data/stats.json` plus this file, so a data refresh updates the page.
- `api/contracts.js` reads the featured deal breakdowns from Airtable (optional).
- `data/contracts.csv` is the starting data for the Airtable `Contracts` table.

## Vercel settings
Add `AIRTABLE_TOKEN` (a personal access token with `data.records:read` on the Cap Tracker base). The function already points at the Cap Tracker base and its deals table; set `AIRTABLE_BASE_ID` or `AIRTABLE_TABLE` only to use a different one. Without them the page shows its built-in breakdowns.

## Views
Open a view directly with its anchor (`#teams` has the power ratings, and each `#team-XX` page has ratings, traits, lineup and depth chart): `#home`, `#news`, `#teams`, `#team-KC` (any team code), `#contracts`, `#tools`, `#builder` (Roster Builder), `#cut`, `#trade`, `#compare`, `#decode`, `#learn`.

## Free agency and year-by-year contracts (#freeagency)
- `data/teamyears.json`: Over The Cap's reported cap room for 2027 and 2028, per team (refreshed daily).
- `data/freeagency.json`: cap projections, cap growth rate, the offseason calendar and official franchise tag prices once announced.
- `data/years_exact.json`: reported year-by-year cap hits for individual contracts. Every other player's later years are estimated in the browser from the contract terms and labeled as estimates. The daily task upgrades more contracts to exact each run.

## PFF rankings (data/pff.json)
PFF's player grades are paywalled, so the site uses what PFF publishes for free: its 2026 preseason top-32 lists (QB, RB, WR, TE, tackles, guards, centers, edge, interior defenders, LB, CB, S) with the grades those articles quote. A listed player's play rating is 60% PFF rank and 40% 2026 stats; unlisted players use stats scaled below the ranked group. Offensive linemen also get roles and traits from PFF's pass-block and run-block grades. The daily task re-reads the PFF articles.
