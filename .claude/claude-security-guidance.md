# PlainStats security rules

- Any URL that comes from a data file (`data/*.json`, `data/ledger.csv`, Airtable, ESPN) and lands in an `href` or `src` must go through `safeUrl()` in src.html, which allows only http(s). `esc()` alone does not stop `javascript:` links.
- Every piece of data text inserted with `innerHTML` or a template string must go through `esc()`. Team ids may be used raw only after checking `TB[id]` exists.
- `data/moves.json` and `data/ledger.csv` are written by an automated daily refresh from web news, so treat their text and links as untrusted.
- Vercel functions in `api/` must not take a URL, host or path from the request and fetch it (no proxying). Error responses stay generic; details go to `console.error`.
- `AIRTABLE_TOKEN` and any other secret live only in Vercel environment variables. Never write a token into src.html, data files, CLAUDE.md or a commit.
- CSV output must neutralize cells that start with `= + - @` (spreadsheet formula injection).
- Third-party scripts are limited to Google Analytics, AdSense and the beehiiv signup embed, loaded only on the live domains after consent. Do not add others without the owner asking.
- The Suggest a fix form only composes a `mailto:` to info@plainstatsnfl.com; it must never post data to another host.
