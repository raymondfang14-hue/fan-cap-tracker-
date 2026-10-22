# PlainStats

Every NFL contract and team salary cap in plain English, for everyday fans.

## Files
- `src.html` is the page (also published as the PlainStats artifact). Edit this one.
- `build.sh` wraps `src.html` into `index.html`, which Vercel serves. On a phone, edit `index.html` directly in Koder and make the same change in `src.html`.
- `data/nfl.json` holds all 32 teams' cap figures and every player contract. `data/moves.json` is the NFL news feed (contract moves, injuries, games, coaching, league news) and the trade deadline date. A daily scheduled task refreshes both.
- `data/season.json` holds standings (record, points for and against), head coaches, 2025 records, the rookie and comeback-candidate lists, and `prevRanks` (last week's power ranking, for the movement arrows). It feeds the Awards and Power rankings page (`#awards`, `#rankings`), which scores everything in the browser from `data/stats.json` plus this file, so a data refresh updates the page.
- `api/contracts.js` reads the featured deal breakdowns from Airtable (optional).
- `data/contracts.csv` is the starting data for the Airtable `Contracts` table.

## Vercel settings
Add `AIRTABLE_TOKEN` (a personal access token with `data.records:read` on the Cap Tracker base). The function already points at the Cap Tracker base and its deals table; set `AIRTABLE_BASE_ID` or `AIRTABLE_TABLE` only to use a different one. Without them the page shows its built-in breakdowns.

## Views
Open a view directly with its anchor (`#teams` has the power ratings, and each `#team-XX` page has ratings, traits, lineup and depth chart): `#home`, `#news`, `#teams`, `#team-KC` (any team code), `#contracts`, `#tools`, `#builder` (Roster Builder), `#cut`, `#trade`, `#compare`, `#decode`, `#learn`.

## Search pages (players/, teams/, draft/, sitemap.xml)
`python3 -I tools/build_seo.py` turns the data files into crawlable pages: one for every player with a confirmed contract or 2026 stats, three per team (overview, cap space, dead money), one per draft prospect, and hub pages for teams, players and the draft. Each has its own title, description, plain-English summary, FAQ and schema markup (Person, SportsTeam, FAQPage, BreadcrumbList), and the script rewrites `sitemap.xml` and `tools/seo-nav.html` (the team links `build.sh` adds to the bottom of the home page). Players whose contract is still being verified get `noindex` and stay out of the sitemap until a named report confirms the deal. Run it after every data refresh, then `./build.sh`, then commit.
To submit to Google: add `https://www.plainstatsnfl.com` as a property in Search Console, open Sitemaps and submit `sitemap.xml`.

## Where contract numbers come from (data/nfl.json, data/ledger.csv, data/cba.json)
PlainStats does not copy Over The Cap or Spotrac. `data/build_contracts.py` builds every player row and tags where it comes from:
- `r` reported: `data/ledger.csv` has one row per deal from a named news report or team announcement, with its URL. Blank fields stay unverified and the player page says so.
- `f` calculated: rookie contracts for the last four draft classes, from the draft slot with PlainStats' rookie scale (`data/rookie_scale.py`, anchored to real 2026 signings listed in `data/cba.json`) and the CBA minimum salaries, including the proven performance escalator, fifth-year options and trades. Undrafted rookies get the minimum.
- `m` league minimum and `p` practice squad: valued with the CBA tables in `data/cba.json`.
- `u` unverified: no sourced figure yet. The dollar fields are blank in `nfl.json` and the page says "Contract being verified". The daily refresh moves these into the ledger (starting with quarterbacks and the best-known players, using nflverse snap counts to choose), and `data/build_market.py` waits to rebuild the price ladder until most contracts are verified.
- Suggest a fix: the button on every player sheet and in the footer opens a form that composes an email to info@plainstatsnfl.com. A contract figure changes only when the sender's link, or our own search, finds a named report.
Run `python3 -I data/build_contracts.py <folder with nflverse roster_2026.csv, draft_picks.csv, snap_counts_2023-2025.csv>`, then `data/fix_ol.py`, then `data/build_market.py`.
- `data/years_calc.json`: year-by-year cap hits PlainStats calculates (rookie deals). Other players' later years are estimated in the browser and labeled.
- `data/freeagency.json`: PlainStats cap projection (2026 cap grown 7% a year), the offseason calendar and official franchise tag prices once announced.
- Team cap space and dead money per team are still the older figures until enough contracts are re-sourced to add them up.
## Offensive line team measures (data/olwin.json)
Built by `python3 -I data/build_olwin.py <play_by_play_2026.csv.gz>` from nflverse play-by-play: pass protection (dropbacks with no sack or QB hit) and run success (designed runs with positive expected points). PlainStats no longer uses ESPN win rates or PFF figures.

## Draft (#draft, data/draft.json)
The Draft page covers the 2027 class: a big board, a full page for each prospect (grade, role, trait badges, 2026 college stats, NFL players in the same role, rookie contract, team fits), the projected first-round order with a model mock, and the rookie pay scale. `data/draft.json` is built by `python3 -I data/build_draft.py` from the prospect list in that script (WalterFootball and NFL Draft Buzz board ranks, cfbstats ids) the season totals in `data/draft_stats.txt` and the ESPN athlete ids in `data/draft_espn.txt` (prospect headshots; school logos use the ESPN team id at the end of each SCHOOLS row, the same ESPN CDN images the NFL cards use); the script's docstring explains the format. The page computes everything else at load: the consensus order, grades, roles, traits, team needs from the 2026 roster, the draft order from `data/season.json` with traded picks applied, and rookie pay grown with the projected 2027 cap from `data/freeagency.json`.

## Season stats, links, value, rookie deals, offseason (#stats, #p-..., #value, #rookies, #offseason)
- `data/history.json`: regular-season box scores for every player from 2023 to the current season, plus this season's game log, built by `python3 -I data/build_history.py <dir> <season>` from nflverse `stats_player_week_<S>.csv` files. `data/drafted.json` (the last six draft classes, from nflverse `draft_picks.csv`) is written by the same script. `data/history_old.json` holds season totals (no game logs) from 1999 up to the season before history.json starts, only for players on a current roster; `python3 -I data/build_history_old.py <dir>` builds it from nflverse `stats_player_reg_<S>.csv` and re-matches the roster, so new signings pick up earlier seasons, and the page loads it only when a player's Stats tab opens. Weekly game logs are kept for the current season only. All of these load only when someone opens the Season stats tab, a player's Stats tab, or the Contracts page tabs.
- Links: every player opens at `#p-<first-last>-<team>` and every draft prospect at `#d-<id>`; the player and prospect pages have a Copy link button that copies the Vercel address.
- Contracts > Best & worst: market value is today's price for a player who ranks where he ranks on the field (data/market.json), minus his yearly pay.
- Contracts > Rookie deals: draft classes matched to contracts by name and team; fifth-year option prices are rough CBA estimates.
- Tools > Offseason: 2027 cap room is estimated from every contract on the site; release, restructure, re-sign, tag and free-agent costs are PlainStats estimates, and moves are saved per team in the browser.
