---
name: weekly-tiers-post
description: Make PlainStats social posts (Instagram carousel 1080x1350, TikTok / Reels / Stories 1080x1920, a silent MP4 Reel and an Instagram Story frame with a link-sticker area): the weekly NFL team-tiers post from data/tiers.json, and player posts built on PlainScore (data/plainscore.json), with a hot-take hook, full-bleed Wikimedia photos, team logos, a team-coloured cover accent, a tracked link to the PlainStats page, and captions. Use when asked for the weekly tiers post, a risers-and-fallers post, a social post of this week's team tiers, or a social post, Story or Reel about a player or a PlainScore ranking.
---

# Weekly team-tiers post (Instagram + TikTok)

Turns `data/tiers.json` (PlainStats net EPA per play, built every Tuesday) into 8 slides. The ranks, tiers, rank changes and the net number on each row are **schedule-adjusted**: net EPA per play compared with what an average unit would have done against the same opponents (`data/build_tiers.py`, README "Weekly team tiers"). The slides: cover with a hot-take hook, Tier 1 to Tier 5 (one slide each), risers and fallers, closing call to action. Every number on a slide comes from PlainStats data; only the wording is hand-written. Do all work in the session scratchpad (`WORK=<scratchpad>/tiers-post`), never in the repo. Do not commit the images.

## 0. Before you start
- `data/tiers.json` must cover the latest finished week (`thru`). If it is stale, say so and stop; the Tuesday refresh rebuilds it (README, "Weekly team tiers").
- It must also carry the schedule adjustment (`"adjusted": true`; `facts.py` prints a WARNING when it does not). A file built before the model change has raw numbers only. Then do not write schedule claims, and tell the user the posted ranks would not match the website's adjusted tiers once the next refresh runs. If they want the adjusted numbers now, build a preview that leaves the repo untouched: download `play_by_play_<season>.csv.gz` from the nflverse release (github.com/nflverse/nflverse-data/releases/download/pbp/), run `python3 -I data/build_tiers.py <pbp.gz> data/schedule.json $WORK/tiers.json`, and pass `$WORK/tiers.json` to `facts.py` (first argument) and `render_post.py` (`--tiers`). Say in the closing message that the website will show the same numbers only after the weekly refresh (or after `data/tiers.json` is rebuilt and committed).
- Network: logos need `a.espncdn.com`; photos need `commons.wikimedia.org` and `upload.wikimedia.org`. If a host is blocked, tell the user to add it under Allowed domains in the cloud environment's network settings, then continue with the parts that do not need it. Do not stand in with made-up images.
- Python needs `playwright` + Chromium (pre-installed in the cloud sandbox; `render_post.py` finds `/opt/pw-browsers/chromium`, or set `PLAYWRIGHT_CHROMIUM`). Run scripts with `python3 -I`.

## 1. Facts sheet
```bash
python3 -I .claude/skills/weekly-tiers-post/scripts/facts.py
```
Prints, per team: tier, rank, rank change, record, streak, adjusted net/offense/defense EPA, raw net and raw rank (before adjustment), strength of schedule (average adjusted net of the opponents faced; `sos` rank 1 = toughest so far), the league rank of each split (1 = best; defense = EPA allowed, lower is better), and the latest week's result. Also lists risers/fallers, the teams the schedule moved by 3 or more places, the toughest and easiest schedules, and record-vs-rank and schedule hook candidates. **Quote only numbers from this sheet.** Overall offense and defense ranks (`off`, `def`) are schedule-adjusted; the pass, run and hit-rate split ranks are raw (not adjusted).

## Cover colour
The second cover line (and, on player slides, the tag, the big score, the bars and the highlighted row) uses the **featured team's colour**, never a fixed brand blue. `render_post.py` takes it from `ACCENT` (one readable-on-dark colour per team): `cover.line2_color` if given, else `ACCENT[cover.team]`, else the first team key in `cover.pills`. Set `cover.team` to the team the hook is about (the #1 team, the riser, the player's team). Override with `line2_color` only for a post that is about no single team, and then pick a colour tied to the post (e.g. the riser's green `#34d399`), not blue.

## 2. The hook (ask if the user has not given one)
A hot take on the cover that the data proves, e.g. "The 6-1 Bills and 6-1 Vikings aren't top-5 teams. Jacksonville is #1." Good shapes: a winning team ranked outside the top 5, a losing team ranked high, the best team by net EPA vs the team people assume is best, or a schedule hook (a top-5 team with one of the easiest schedules so far, a team the adjustment lifts many places because its schedule was brutal, a team whose record outruns its adjusted rank). Fans push back on unadjusted stats ("Jags play in the AFC South"), so when the #1 team has an easy schedule say so in a reason or the caption. Offer 2 or 3 options with the supporting ranks and let the user pick; if they already chose, use it. Re-check the hook against `facts.py` before using it.

## 3. Write the reasons
One reason per team, in `content.json` (`why`). Rules:
- Facts only from the sheet: league ranks written as "#3 defense" / "28th-ranked run defense", EPA per play with sign, the team's latest result ("Lost 28-24 at DEN", "Won 43-36 in OT"), streaks. Defense numbers are EPA allowed.
- Overall offense and defense ranks and EPA are the schedule-adjusted ones from the sheet (`adjOff`, `adjDef`, `off`/`def` ranks). Pass, run and hit-rate splits are raw: label them ("best raw pass offense", "+0.27 raw EPA per dropback") or leave the word "raw" in the caption note, and never mix an adjusted and a raw number in one claim.
- Strength of schedule: say "the #25 schedule of 32 so far (1 = toughest)" or "faced the 2nd-toughest schedule", never "played nobody"; the adjustment is already in the rank, so say that ("even after adjusting for schedule"). Schedule rank is from games played so far, not the rest of the season.
- Raw-vs-adjusted moves are fair game ("raw #19, #12 once schedule is counted") but name which one is the PlainStats rank (adjusted).
- Never say a team "moved up a tier": last week's tier is not stored, only the rank change. Say "up 7 spots".
- Records come from the data automatically (including ties, e.g. 4-2-1); do not type records in a reason.
- No betting data, no contract or cap figures (data rules in CLAUDE.md), no injury speculation.
- Do not hand-type net EPA or `sched` numbers: rows show the adjusted net and (on 5-team slides) `sched #N` from the data.
- Length: tiers with up to 7 teams get about 100 characters (two lines); a tier with 8 or more teams (Tier 3 is usually 10) gets one line of about 48 characters. `render_post.py` warns on anything longer or overflowing.
- Movers slide: two risers, two fallers with reasons; everyone else with a rank move of 3 or more goes in the "also up / also down" line (ties at the same move size: list them all).
- Say what the numbers say, not what a record says: contrast record vs ranking where it is true ("5-3 flatters them: 25th net EPA").

## 4. Photos (full-bleed; Wikimedia Commons first)
Need 8: cover, tier 1 to 5, movers, closing. Use a different player on each slide and pick the tier's lead team where a good photo exists.
```bash
python3 -I .claude/skills/weekly-tiers-post/scripts/photos.py search "Patrick Mahomes"
python3 -I .claude/skills/weekly-tiers-post/scripts/photos.py fetch t1 "File:Patrick Mahomes (51615475056).jpg" --dir $WORK/photos --width 1920
```
- Only CC0, public domain, CC BY, CC BY-SA are listed (never NC/ND). `fetch` writes `photos.json`; the credit prints on every slide automatically. Put the "Photos: Wikimedia Commons" line in both captions.
- The Commons API is rate limited (HTTP 429). Fetches retry patiently and can take minutes each. Search once per player, pick, then run the fetches in the background (`run_in_background`) and keep working.
- **Look at every downloaded photo before using it** (Read the image): right team uniform (searches mix in college photos: Bo Nix in an Oregon jersey, Brock Purdy at Iowa State; skip those), face clearly visible, in-game or game-day. Prefer portrait (2:3) photos with the face in the top half: stat rows cover the lower two thirds of each slide. If the only clear face is a pregame/warm-up shot, use it and tell the user.
- Check the team the photo shows, not just the player's name: players in the PlainStats rosters may be photographed in an older jersey.

### Photos from other sources (owner's decision, Nov 17 2026)
The owner allows NFL player photos from most sources for **social posts only**, accepting the risk while the account is small. Prefer a Commons photo when a good one exists; otherwise:
- Add the photo with `photos.py add SLOT <file or URL> --credit "Photographer / outlet"` (a file the user uploaded, or a URL on a host the environment allows). Always fill in the credit with the photographer or outlet; it prints on every slide like a Commons credit. Unknown source: ask the user, do not leave it blank.
- Avoid photo-agency images: Getty Images, AP, Imagn / USA Today Sports, Reuters, and anything with an agency watermark or caption. Those agencies run automated takedowns and claims against small accounts too, and each Instagram takedown is a strike on the account. Team and league site photos, fan photos and social posts with a named photographer are the lower-risk choices.
- Never put these photos on plainstatsnfl.com (pages, og cards, repo): the site's photo rules are unchanged. Keep them in the scratchpad.
- Real photos only, cropped, zoomed and recoloured as needed. Never edit a player into a uniform, team or scene he was not in (no swapped helmets or jerseys, no AI composites), and no trading-card scans.
- If a photographer or agency asks for a photo to come down, tell the user to remove the post right away.
- Captions: "Photos: <credits>" instead of "Photos: Wikimedia Commons" when any slide uses one of these.

## 5. Build
Write `$WORK/content.json` (copy `content.example.json` from this folder: the Week 8 example. Its reasons were written for the raw numbers before the schedule adjustment, so keep the structure and rewrite every reason from a fresh facts sheet; `render_post.py` warns when a tier's teams or lengths no longer match) and render:
```bash
python3 -I .claude/skills/weekly-tiers-post/scripts/render_post.py --content $WORK/content.json --photos $WORK/photos --out $WORK/out --format both   # add --tiers $WORK/tiers.json for a preview file
```
Output: `$WORK/out/ig/NN_*.png`, `$WORK/out/tt/NN_*.png`, and `contact.png` for each. Logos are fetched on first run. Fix every `WARNING`.

**Crops** (`crop` in content.json, per photo and format: `[size, position]`). Default is `["cover", "50% 15%"]`. If the face sits behind the stat block, zoom and shift the photo up: `["auto 128%", "50% 100%"]` for portrait photos on TikTok (try `auto 115%` to `auto 128%`), `["cover", "50% 100%"]` on Instagram. A face needs to end above the top of the stat block; open each PNG and check. Do not zoom past the photo's resolution (1280 px wide source: about 120% max; 1920 px: about 130%).

**Layout facts** (already built in): Instagram 1080x1350 with page dots; TikTok 1080x1920 with the bottom 350 px and right 110 px kept clear for TikTok's caption and buttons, pill lowered below the top bar, no dots. Fonts are `assets/fonts/Inter-*.otf`. Photo credit sits at the bottom of the content area. Team logos on light tiles (dark logos like the Raiders stay readable).

## 6. Review before sharing
1. No warnings; look at all 16 PNGs (or the two contact sheets, then each slide that changed).
2. Spot-check every quoted rank, EPA figure and score against `facts.py`. Re-check records that show ties.
3. The hook is still true, no "moved up a tier" wording, no contract figures.
4. Each photo: right team, face visible, credit line readable, license is on the allowed list.
5. TikTok: nothing important in the bottom 350 px or right 110 px.

## 7. Captions
Write both and save as text files in `$WORK/out`.
- **Instagram caption:** hook line + emoji; one line on net EPA per play, adjusted for strength of schedule; Tier 1 list; risers and fallers; two data-backed takes; "Swipe for the numbers behind every team"; plainstatsnfl.com/team-tiers; source line ("nflverse play-by-play, regular season thru Week N, garbage time included; adjusted for the opponents each team has played"); "Photos: Wikimedia Commons (credits on each slide)"; 8 to 10 hashtags.
- **TikTok caption:** title of about 90 characters (hook shortened) + description with the same facts, a question to bait comments ("Which team is ranked too high or too low?"), "link in bio", photo credit line, hashtags (#nfl #nflfootball #nflpowerrankings #footballtok #nflstats), and a pinned-comment suggestion. TikTok photo posts take up to 35 images; upload the 8 PNGs in order as a photo carousel and add a trending sound.

## Player posts (PlainScore)
Same look, different slides. Use for "post about <player>" or a PlainScore ranking.
- Slides: `cover` (hook, `team`, text pills like `{"text": "Purdy 98"}`, `sub`, `swipe`), `player` (one player: big PlainScore, rank among his group, the bars from `data/plainscore.json`), `players` (a ranked list by gsis id: logo, name, team, PlainScore; `star` outlines one row in the accent; `pos: true` shows "#1 RG" for mixed positions; `why` overrides the sub line), and `cta` with `title`, `text`, `source`. Set the top-level `url` to the player's page (`plainstatsnfl.com/players/<slug>`, from `data/pageslugs.json`) and `foot`.
- Numbers: only from `data/plainscore.json` (export with `python3 -I tools/refresh_helpers.py plainscore` after `./build.sh` if stats changed) and `data/nfl.json`; never compute PlainScore another way. Match by gsis id. Pay appears only where plainscore.json has a `pay` bar (confirmed contract); a player without one shows "Contract being verified", so never hand-type a salary into `why` for him. Say "a year" (average per year), not cap hit. Name the report for the featured player's pay in the cta `source` (ledger.csv `source`).
- Write sums or comparisons only from the shown figures and say what they are ("together they make less a year than Purdy": average per year).
- `content.purdy-week10.json` in this folder is the worked example (cover, player, top-5 list, position list, cta, story).

## Stories, Reels and the link
```bash
python3 -I .claude/skills/weekly-tiers-post/scripts/render_post.py --content $WORK/content.json --photos $WORK/photos --out $WORK/out --format both --story --reel
```
- `out/tt/*.png` (1080x1920) work as Story slides, TikTok photo posts and Reel frames: nothing important in the bottom 350 px or right 110 px.
- `out/story/story.png` (from `content.json` `story`): one Story frame with an empty band above the reply bar and a "Tap the link ↓" cue in the accent. The user adds Instagram's **Link** sticker there.
- `out/reel/reel.mp4`: silent 1080x1920 H.264, 3 s per slide (`--sec`), 0.5 s crossfades, from the tt slides. Licensed music cannot be added here: the user picks a sound in Instagram or TikTok.
- Link sticker URL (tracked in GA4): `https://plainstatsnfl.com/<path>?utm_source=instagram&utm_medium=social&utm_campaign=<post-slug>&utm_content=story`. For captions and comments, the short form `plainstatsnfl.com/ig/<path>` (`/tt/<path>` on TikTok) redirects to the page with `utm_campaign=post` (vercel.json). The slides themselves show the plain address (`url`).
- Add the post to `data/links.json` (`posts`, newest first, `path` = the page on the end slide) so the bio link page lists it; that file must stay valid JSON (a hook checks it). Commit only that line, never the images.

## 8. Deliver
Send the PNGs (cover first), `contact.png`, the story frame, the reel and the caption files with `SendUserFile` (absolute scratchpad paths, `display: attach`). Write the closing message in plain words: what each slide shows, anything the user should check (pregame photos, weak photos, small Tier 3 text), the folder path. Offer: a different hook, replacement photos, a short MP4 slideshow. Never post anything; never commit the images.

## Known pitfalls
- Two different "schedule" numbers exist on the site: the tiers' `sosRank` (EPA-based, what this skill quotes) and the Sched column on `/power-rankings` (points-based, from `data/season.json` `sos`). They can differ by several places (DEN is #2 by EPA, #6 by points). Quote only the tiers' one in a tiers post, and say "by EPA" if the post also mentions power rankings.
- Schedule adjustment: ranks and the net on every row are adjusted; the splits are not. A `tiers.json` built before the model change has no `adjusted` flag (render prints a WARNING and the slides show raw net). Strength of schedule from the adjusted model is not the same as a raw-opponent average (JAX was 29th-toughest by raw opponent net EPA, 25th by the adjusted model): quote only the sheet's `sosRank`.
- Ties: records like 4-2-1 must show the tie (the renderer does; hand-typed records dropped it once).
- Python `playwright` may not match the installed Chromium; the script passes `executable_path`.
- `python3 -I` ignores the script folder, so helper scripts here are standalone (no sibling imports).
- `pkill -f <script>` can kill your own shell if the pattern matches the command line; kill by PID.
- Wikimedia only serves standard thumbnail widths; `fetch` downloads the original file when it is no wider than `--width` (asking for a 1024 px thumb of a 1024 px photo is an HTTP 400).
- Commons has few photos of some current players in their NFL uniform (Brock Purdy: only Iowa State close-ups and one wide shot from the stands in 2026). Search the player, then "<team> <year>" game photos; use a team game photo and say so rather than a college photo.
- Wikimedia: `thumb.wikimedia.org` is blocked in the sandbox, `upload.wikimedia.org` works (the script builds those URLs). Use standard thumbnail widths (1280, 1920, 3840).
- Do not use ESPN headshots for the photo slides (not license-free). Team logos from ESPN are used as on the PlainStats site.
