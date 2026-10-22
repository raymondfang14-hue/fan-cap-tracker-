# PlainStats

Simple, analytical NFL contracts and stats site for everyday fans. Live at plainstatsnfl.com (Vercel, deployed from this repo's main branch). Static single page plus two Vercel functions; data is JSON in `data/`. See README.md for the full data pipeline.

## Editing the page
- Edit `src.html`, never `index.html`. `build.sh` wraps `src.html` into `index.html`; a hook runs it after every `src.html` edit and blocks direct `index.html` edits.
- CSS has two layers in `src.html`: the original base styles, then the storefront redesign layer (apple.com / CraftedNBA-inspired: translucent nav, sentence-case labels, soft grey field, white panels). Put new styles in the redesign layer and follow its tokens (`--bg`, `--surface`, `--fg`, `--muted`, `--brand`, `--r`, `--r-lg`).
- No all-caps tracked labels, no hover lift on cards. Respect `prefers-reduced-motion` and keep dark mode working (both `prefers-color-scheme` and `[data-theme]`).
- Every table needs a filter search. The Roster Builder shows no contract costs.
- Must work on phones: the owner edits from Koder / Working Copy on iPhone.

## Data rules
- Never copy Over The Cap, Spotrac or other restricted sources. Contract figures come from `data/ledger.csv` (named report + URL), CBA calculations (`data/cba.json`, `data/rookie_scale.py`) or stay unverified.
- A contract figure without a named report shows "Contract being verified". Do not guess numbers.
- Free data only, current season (2026). Pipeline: `data/build_contracts.py` → `data/fix_ol.py` → `data/build_market.py`. Run Python with `python3 -I`.
- A hook checks that any edited `data/*.json` still parses.

## Shipping
- Push changes to GitHub without asking first (standing instruction from the owner).
- Secrets (`AIRTABLE_TOKEN`) live only in Vercel env vars; never commit them.
