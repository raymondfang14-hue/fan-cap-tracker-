# PlainStats

Simple, analytical NFL contracts and stats site for everyday fans. Live at plainstatsnfl.com (Vercel, deployed from this repo's main branch). Static single page plus two Vercel functions; data is JSON in `data/`. See README.md for the full data pipeline.

## Editing the page
- Edit `src.html`, never `index.html`. `build.sh` wraps `src.html` into `index.html`; a hook runs it after every `src.html` edit and blocks direct `index.html` edits.
- CSS has two layers in `src.html`: the original base styles, then the storefront redesign layer (apple.com / CraftedNBA-inspired: translucent nav, sentence-case labels, soft grey field, white panels). Put new styles in the redesign layer and follow its tokens (`--bg`, `--surface`, `--fg`, `--muted`, `--brand`, `--r`, `--r-lg`).
- No all-caps tracked labels, no hover lift on cards. Respect `prefers-reduced-motion` and keep dark mode working (both `prefers-color-scheme` and `[data-theme]`).
- Every table needs a filter search. The Roster Builder shows no contract costs.
- Must work on phones: the owner edits from Koder / Working Copy on iPhone.

- Every page has a clean URL (README "Views"). A new section needs an entry in `ROUTES` in src.html, `rewrites` in vercel.json (destination `"/"`, never `"/index.html"`: with `cleanUrls` that 404s on reload) and `APP_URLS` in `tools/build_seo.py`. Never give an app page a path under `/players`, `/teams` or `/draft` (static pages). Link with `href="/path"` or `pathOf(key)`, never `#key`. Give a new page a `PDESC` line too: crawlers get its title and description from `api/page.js` (the first, bot-only rewrite in vercel.json; keep it first).

## Data rules
- Never copy Over The Cap, Spotrac or other restricted sources. Contract figures come from `data/ledger.csv` (named report + URL), CBA calculations (`data/cba.json`, `data/rookie_scale.py`) or stay unverified.
- A contract figure without a named report shows "Contract being verified". Do not guess numbers.
- No Pro Football Reference or Next Gen Stats data, with one written exception: nflverse `snap_counts` (PFR's copy of the official gamebook snap counts; no free in-season alternative). Never use nflverse `pfr_advstats`; pass rush comes from box-score sacks and QB hits.
- Free data only, current season (2026). Pipeline: `data/build_contracts.py` → `data/fix_ol.py` → `data/build_market.py`. Run Python with `python3 -I`.
- The nflverse rebuilds run in GitHub Actions (`.github/workflows/nflverse-refresh.yml` → `tools/refresh.sh daily|gameday|weekly`). A new nflverse build step goes in `tools/refresh.sh`, not only in a scheduled-task prompt.
- A hook checks that any edited `data/*.json` still parses.
- Contract end years (`end` in `data/ledger.csv`): it is the LAST season under contract (the page shows free agency as end + 1). An extension adds its years onto the old contract, so end = old contract's final season + years added; it never starts in the current season unless the old deal already expired. Rookie deal ends are draft year + 3 (+ 4 with an exercised fifth-year option). Prefer a report's "through 20XX" over arithmetic; when two named reports disagree, leave `end` blank rather than pick one, and say in notes when it is calculated. Write the derivation in `notes` ("old deal through 2026 plus 2 years"). A re-signing of an expired deal is a Signing, not an Extension. Cards in the Airtable Contracts table and `DEALS` must show the same end year as the ledger.
- Recent deals stay current: every news sweep that adds a signing, extension or restructure to `data/ledger.csv` / `data/moves.json` must also add a breakdown card to the Airtable Contracts table (base `app7vEpDdwBT0xCUr`, table `tblMvDcAIUpr9Zuor`) in the same format as the existing cards (Name, Team, League, Position, Headline, Subhead, NewMoneyPerYear, Scale, ScaleNote, Bar, Facts, Plain, Watch, Sources, CheckNotes, Sort 0, Verified), and mirror it at the top of `DEALS` in src.html. Use only figures the named report gives; say what was not reported instead of guessing. Newsome and Adebawore (Nov 3, 2026) are the model for thin-report cards.
- Featured deal breakdowns live in Airtable (Cap Tracker base). `/api/contracts` only serves a deal with `Verified` ticked and at least one `Sources` line (`Outlet | https://link`). Tick Verified only after every figure on the card is checked against those reports; record what was checked or calculated in `CheckNotes`. The built-in `DEALS` in src.html is the fallback and must match the verified Airtable records.

- Trade deadline page (`/trade-deadline`) is built from `Trade` items in `data/moves.json`. Every news sweep that adds a trade must also give it a `deal` field (README, "trade deadline page"): for each team, the players it gets (name, gsis id, team that sent him) and the picks it gets, as the report states them; add `dead` only when a named report gives the old team's dead money. Never guess a pick's year or round; leave it out and say so in `plain`.

## Search pages (SEO)
- `players/`, `teams/`, `draft/`, `sitemap.xml` and `tools/seo-nav.html` are generated by `python3 -I tools/build_seo.py`. Never edit them by hand; edit the script. Re-run it after every `data/*.json` change (including the daily refresh), then run `./build.sh` and commit the generated files.
- URLs: `/players/<name>`, `/teams/<team>`, `/teams/<team>/cap`, `/teams/<team>/dead-money`, `/draft/<name>`, plus hubs `/teams`, `/players`, `/draft`. Static HTML, inline CSS, no JavaScript apart from two inline snippets in `build_seo.py`: `VA` (cookieless Vercel Web Analytics) and `GA` (Google Analytics 4 plus the cookie notice; loads only after Accept, shares the `pc.consent` choice with the app, live domain only). Keep the measurement ID in `GA` equal to `ANALYTICS.ga4` in `src.html`.
- The script follows the data rules: contract figures appear only when the player's `ver` letters confirm them; players with no confirmed contract get "Contract being verified" and `noindex` (kept out of the sitemap until a named report confirms the deal). Each page repeats its FAQ in visible text and in JSON-LD; do not add schema for text that is not on the page.
- Player and team pages end with doorway links into the app (`player_doors` / `team_doors` in `build_seo.py`; the app's player sheet and team page carry the same block from `playerDoors` / `teamDoors` in `src.html`, so change both together) and The Cap Sheet signup (`signup_html`). The signup is a plain no-JS form that opens the beehiiv hosted subscribe page (`CAP_SHEET_URL`); left empty, it links to `/?signup=1`, which scrolls to the home-page signup.
- Team cap space and dead money pages use the team totals in `data/nfl.json` and say so; update their wording if those totals are re-sourced.
- Social cards: `build_seo.py` also writes `og-data/*.json` (generated, never hand-edited) and every page's `og:image` is `/api/og?k=&s=&v=`, drawn by the function `api/og.js` using `api/_og-layout.js` and `assets/fonts/`. Card text is built in `build_seo.py` under the same data rules as the page. Keep `Allow: /api/og` in `robots.txt`. Preview layout changes with `tools/preview_og.mjs` + `tools/shot_og.py`; the sandbox can't reach ESPN or npm, so confirm the live `/api/og` URL after deploy.
- "Share this" (last `<script>` in `src.html`) puts a button on every panel with a chart or table; styles are in the redesign layer (`.ps-*`). Keep the offscreen copy out of the observer (`.ps-cap`) and read typed filter values from the live panel, not the clone.

- Share card (last `<script>` in `src.html`): a "Share" button on every player sheet, prospect sheet and team page (`data-card="p-…" | "d-…" | "team-XX"`, added by `sheetLink()` and `renderTeam()`) draws a 1080x1350 PNG on a canvas and opens the "Share this" preview (`window.psShowImage`). `playerSpec` / `teamSpec` / `prospectSpec` pick 3 to 5 percentile bars from numbers the page already computed; a card with fewer than three bars is not made. The data rules apply: a player whose contract is "being verified" gets no pay bars. The static pages in `build_seo.py` have a plain "Share" link to the app with `?share=1`, which opens the card as soon as the data loads. `tools/check_pages.py` checks each card is 1080x1350.

- Share links: Copy link, Share this and Send to a friend build their address with `shareUrl()` in `src.html` (utm_ tags, and `/players/<name>` or `/draft/<name>` when the page exists). `build_seo.py` writes `data/pageslugs.json` for that lookup; do not edit it by hand.

- Match players across data files by gsis id (`gid`, row index 19 in `data/nfl.json`), never by name: nflverse files spell names differently (Greg / Gregory Rousseau). `data/stats.json` rows carry `gid`.

- Season stats load from small files in `data/hist/` (built by `data/build_hist_split.py`, run by `build_history.py` and `build_history_old.py`): `meta.json`, `s<year>.json`, and 64 player shards `p<NN>.json` keyed by gsis id. The page never loads `history.json` / `history_old.json` (build inputs, kept out of the deployment). Match players by `gid`, never by team, so mid-season trades stay one record.

- Games tab (`/scores`, `/standings`, `/projections`, game pages `/game/<id>`): `data/schedule.json` (daily, `data/build_schedule.py`) and `data/projections.json` (weekly, `data/build_projections.py`, PlainStats Elo model). Never use the betting columns in nflverse games.csv. This week's game pages use `data/gameday.json` (daily, `data/build_gameday.py`: official injury report via nflverse plus injury-adjusted picks) and live weather from api.weather.gov (public domain, fetched in the browser; the sandbox can't reach it).

## Checks
- `python3 -I tools/check_pages.py` opens every view at phone and desktop size, light and dark, and fails on JS errors, failed data loads or sideways scroll. Run it before pushing page changes (`--shots DIR` saves screenshots).
- `python3 -I tools/check_stats.py <nflverse folder>` checks every player card's season stats (On the field tab) against the raw nflverse box scores, by gsis id, and flags players listed twice. Run it after rebuilding `data/stats.json`.
- `python3 -I tools/check_ledger.py` checks `data/ledger.csv` for missing sources, totals that don't add up and duplicates. After adding ledger rows, have the `ledger-checker` agent compare them with their source links.
- `.mcp.json` adds Playwright (browser checks) and Vercel (deploy logs) for Claude Code sessions.

## Shipping
- Push changes to GitHub without asking first (standing instruction from the owner).
- Secrets (`AIRTABLE_TOKEN`) live only in Vercel env vars; never commit them.

## Keeping the setup private
- `.vercelignore` keeps notes, build scripts, `src.html`, `tools/` and raw sources (`data/*.py`, `*.csv`, `*.txt`, `cba.json`, `years_calc.json`) out of the public deployment. If the page starts loading a new `data/` file, make sure it is not matched there. Keep the GitHub repo private.
