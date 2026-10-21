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

## PFF in-season data (data/pff.json)
PFF's full player grades are paywalled, so the site uses only what PFF publishes for free during the current season (no preseason rankings): weekly QB and WR rankings, top game grades each week, Team of the Week, and rookie rankings. This is a light signal: 25% of a player's play rating (PFF_W in src.html). Offensive linemen get roles (Road grader, Blindside protector, Two-way anchor...) from the pass-block and run-block grades PFF states. Traits are separate from roles: they are gold, silver or bronze tiers on stats that no role uses, and there are no PFF-based traits. The daily task re-reads the newest PFF pages.

## Free offensive line data (data/olwin.json, data/pff_ol.json)
No free source tracks every block by individual lineman, so Plain Cap blends what is free:
- `data/olwin.json`: ESPN's team Pass Block Win Rate (PBWR) and Run Block Win Rate (RBWR), built by `data/build_olwin.py` from the free NFL Lines table. The page merges these into each team's stats. They feed the lineman play rating (35% snap share, 15% penalties, 15% PBWR, 15% RBWR, 10% sack rate, 10% yards before contact).
- `data/pff_ol.json`: individual lineman figures PFF states in its free weekly OL rankings article (pressures, pass-blocking snaps, grades), built by `data/build_pff_ol.py`. They show on the lineman's card and do not change his rating. Only figures tied to one named lineman are kept.
Refresh both weekly: edit the rows in each script, run it, then `sh build.sh`.

## Draft (#draft, data/draft.json)
The Draft page covers the 2027 class: a big board, a full page for each prospect (grade, role, trait badges, 2026 college stats, NFL players in the same role, rookie contract, team fits), the projected first-round order with a model mock, and the rookie pay scale. `data/draft.json` is built by `python3 -I data/build_draft.py` from the prospect list in that script (WalterFootball and NFL Draft Buzz board ranks, cfbstats ids) the season totals in `data/draft_stats.txt` and the ESPN athlete ids in `data/draft_espn.txt` (prospect headshots; school logos use the ESPN team id at the end of each SCHOOLS row, the same ESPN CDN images the NFL cards use); the script's docstring explains the format. The page computes everything else at load: the consensus order, grades, roles, traits, team needs from the 2026 roster, the draft order from `data/season.json` with traded picks applied, and rookie pay grown with the projected 2027 cap from `data/freeagency.json`.

## Season stats, links, value, rookie deals, offseason (#stats, #p-..., #value, #rookies, #offseason)
- `data/history.json`: regular-season box scores for every player from 2023 to the current season, plus this season's game log, built by `python3 -I data/build_history.py <dir> <season>` from nflverse `stats_player_week_<S>.csv` files. `data/drafted.json` (the last six draft classes, from nflverse `draft_picks.csv`) is written by the same script. Both load only when someone opens the Season stats tab, a player's Stats tab, or the Contracts page tabs.
- Links: every player opens at `#p-<first-last>-<team>` and every draft prospect at `#d-<id>`; the player and prospect pages have a Copy link button that copies the Vercel address.
- Contracts > Best & worst: market value is today's price for a player who ranks where he ranks on the field (data/market.json), minus his yearly pay.
- Contracts > Rookie deals: draft classes matched to contracts by name and team; fifth-year option prices are rough CBA estimates.
- Tools > Offseason: 2027 cap room starts from Over The Cap's 2027 table (data/teamyears.json); release, restructure, re-sign, tag and free-agent costs are Plain Cap estimates, and moves are saved per team in the browser.
