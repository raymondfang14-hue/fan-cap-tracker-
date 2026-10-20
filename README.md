# Plain Cap

NFL and NBA contracts in plain English. One page, no build step.

## Files
- `src.html` is the page. Edit this one.
- `build.sh` wraps `src.html` into `index.html` (what Vercel serves). Run it after edits, or edit `index.html` directly if you are on a phone and skip `src.html`.
- `api/contracts.js` reads your Airtable table and feeds the page.
- `data/contracts.csv` is the starting data for Airtable.

## Setup
1. Airtable: create a base with a table named `Contracts`, import `data/contracts.csv` (easiest in a browser at airtable.com). Make a personal access token with the `data.records:read` scope for that base and note the base ID.
2. Working Copy: create a repository, import these files, commit, push to GitHub.
3. Vercel: import the GitHub repo. Add environment variables `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID` and, only if your table has another name, `AIRTABLE_TABLE`. Deploy.
4. Koder: open `index.html` through the Files app (Working Copy lists its repos there), edit, then commit and push in Working Copy. Vercel redeploys on its own.

If Airtable cannot be reached, the page shows the contracts built into it.

## Editing on a phone
`index.html` is the file Vercel serves, so edit it directly in Koder. If you also use `src.html`, make the same change in both, or run `build.sh` from a computer.
