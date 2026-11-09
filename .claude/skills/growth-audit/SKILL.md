---
name: growth-audit
description: Audit the whole PlainStats site (plainstatsnfl.com) for growth and engagement against the PlainStats Growth Playbook, using real traffic, Search Console and site-health data, and write the findings and a ranked plan as a new dated tab in the playbook doc. Use when asked to audit PlainStats, review growth or engagement, check what to do next to get more users, or "run the growth audit".
---

# PlainStats growth audit

Goal: more users and more engagement on plainstatsnfl.com. The audit finds what is holding growth back, using numbers, and turns it into a short ranked plan the owner (Raymond) picks from. It reports first; it does not build fixes unless the owner says so in this conversation.

## Where things are

| What | Where |
| --- | --- |
| The playbook (Claude Docs doc) | "PlainStats Growth Playbook: What Top NFL Analytics Brands Do", https://claude.ai/artifact/Crx9awxyprQYDxs85MmVtA, doc id `600df4c7-5052-4c7b-808d-aa356138e1e7`. Main tab = the playbook; one tab per past audit ("Site audit, <date>") |
| Traffic | Vercel Web Analytics, project `prj_jkWznPC1AVOWO4jeHrKv53mI5nM1`, team `team_vAuSoYe3eYSnZIim6z7t9Sw1` (`mcp__Vercel__aggregate_pageviews`; load it with ToolSearch). UTM breakdowns need a paid add-on and are refused: use referrers |
| Google search | The Monday GitHub issue labelled `search-console` (built by `tools/gsc_report.py` via `.github/workflows/search-console-weekly.yml`): impressions, clicks, position per player page, week over week. Data trails by about 3 days |
| Google Analytics 4 | Not readable from a session. Events are listed in README ("Analytics"). Ask the owner for numbers you need |
| Newsletter (beehiiv), social accounts | Not readable. Ask the owner |
| Site health | `tools/check_pages.py`, the GitHub Actions runs of `nflverse-refresh.yml`, `mcp__Vercel__get_runtime_errors` |
| What shipped | `git log origin/main --since=<last audit date>` |

## Steps

1. **Start from the last audit.** Read the doc (Claude Docs connector: `read` the project, then each audit tab). Note the last audit's date, its "Next moves" and its checklist, and which boxes are ticked. Then `git fetch origin main` and list what shipped since that date. The ticks are often behind: judge from the commits.
2. **Ask before guessing.** Use AskUserQuestion (one call, at most 3 questions) for what the data cannot show and that changes the advice: whether and where they post on social, whether to only report or also build, and anything new since the last audit. Skip questions already answered in the doc or this conversation.
3. **Traffic (Vercel), last 14 days and the 14 before.** Pageviews by day; by `referrerHostname`; by `requestPath` (top 30); by `deviceType`; Google only by day (`filter: referrerHostname eq 'google.com'`). Work out visitors per source, pages per visitor (sum of daily pageviews over sum of daily visitors), and spikes. Leave out an obvious testing day (many pageviews from very few visitors) and say so.
4. **Search Console.** Read the latest `search-console` issue (and the one before, for trend): impressions, clicks, click rate (clicks / impressions), positions, biggest gains and drops. Compare Google clicks with Vercel's google.com visitors over the same dates to check the two agree.
5. **What Google shows.** For the 5 to 8 pages with the most impressions, read the `<title>` and meta description in `players/<slug>.html`. Ask: do they match why people search for that player this week (news, stats, contract)? Are descriptions cut off?
6. **Site health.** Run `PW_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome python3 -I tools/check_pages.py` (about 1.5 minutes). List the last 10 `nflverse-refresh.yml` runs and their conclusions. `get_runtime_errors` for 7 days. Fetch a few live pages with a Googlebot User-Agent (curl -A) and check title, canonical and robots: app pages (`/team-tiers`, a `/game/<id>`, a `/player/<slug>-<team>`), a static `/players/<slug>`, and a made-up path (must be 404). Check `sitemap.xml` (count, lastmod spread).
7. **Feature gaps.** Check which playbook and past-audit ideas exist (grep `src.html` routes and features, `tools/build_seo.py`), and which do not.
8. **Write the audit as a new tab** in the playbook doc, named "Site audit, <Mon D>", ordered after the last audit tab. Follow the Claude Docs guide (`guide` topic.index, topic.tabs): create the tab with one pending block per section, open the doc with the Artifact tool's `open` action, then fill one section per call. Sections:
   - Lead (no heading): the 2 to 3 sentence answer with the key numbers.
   - **Since <last audit>**: table of last checklist items and their status (shipped, with date; or not done).
   - **The numbers**: two small tables (Vercel periods; Search Console weeks) and 2 to 3 bullets on what moved and why.
   - **What is holding growth back**: table of findings: finding, evidence (a number), fix, size (Small, Medium, Large, Decision).
   - **Next moves, ranked**: numbered list, by expected visitors per hour of work; say which finding each comes from.
   - **Questions only you can answer**.
   - **Next two weeks**: a `- [ ]` checklist split by week.
   - **Sources**: what was read, with dates.
9. **Reply in chat** with a short summary: the headline numbers, the top 3 moves, and the questions. Offer to build any of them. Do not build unless asked.

## Rules

- Every number in the doc comes from a tool result in this run, with its date range. Never estimate a number you could not read; say what is missing and ask.
- Data rules from CLAUDE.md still apply to any recommendation: no Over The Cap, Spotrac, PFF or Next Gen Stats data; no Pro Football Reference data except nflverse snap counts; contract figures only from named reports; "Contract being verified" otherwise.
- Plain English, short sentences, sentence-case headings, no emoji. The owner reads on an iPhone: tables of at most 5 columns.
- Do not tick or edit the owner's checklists in old tabs. Report what shipped in the new tab instead.
- If a tool is unavailable (a connector failed to connect, Vercel MCP refused), say which data is missing in the doc's Sources section and in chat, and continue with the rest.
- When a finding needs a code change, name the file and function, so a later session can build it directly.
