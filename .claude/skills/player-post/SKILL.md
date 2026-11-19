---
name: player-post
description: Make a PlainStats social post about one NFL player from his PlainScore (data/plainscore.json): a hot-take hook the data proves, game-day team photos with photographer credit, a 5-slide Instagram carousel (1080x1350), the same slides for TikTok / Reels / Stories (1080x1920), a silent MP4 Reel, an Instagram Story frame with room for the link sticker, Instagram and TikTok captions, and tracked links to the player's PlainStats page. Use when asked for a post, carousel, Story, Reel or TikTok about a player, a "best QB" / "best value" / PlainScore ranking post, or to redo a player post with new photos.
---

# Player social post (Instagram, TikTok, Reels, Stories)

Same look and renderer as the weekly tiers post (`.claude/skills/weekly-tiers-post`, shared scripts), built around one player. Worked example: `content.example.json` in this folder (Brock Purdy, Week 10: "The NFL's best QB so far isn't Burrow or Lawrence. It's Brock Purdy."). Work in the scratchpad (`WORK=<scratchpad>/<player>-post`), never in the repo; never commit images.

Scripts:
- `scripts/player_facts.py` (this skill): the facts sheet.
- `../weekly-tiers-post/scripts/photos.py`: `gallery` (team-site photos with credits), `add` (any photo + credit), `search`/`fetch` (Wikimedia Commons), `logos`.
- `../weekly-tiers-post/scripts/render_post.py`: slides, Story frame, Reel.

## 1. Facts sheet
```bash
python3 -I .claude/skills/player-post/scripts/player_facts.py "Brock Purdy" [--team SF]
```
Prints his PlainScore, rank, bars, pay (only for a confirmed contract) with the ledger's named report, the top of his group, teammates ranked top 3 at their spot, his page path and hook candidates. **Quote only numbers from this sheet.** If stats or contracts changed since the last export, run `./build.sh` and `python3 -I tools/refresh_helpers.py plainscore` first. Never compute PlainScore any other way.

## 2. Hook
Offer 2 or 3 hooks from the candidates with the supporting numbers (AskUserQuestion) unless the user already chose one. Good shapes: "#1 at his position, and paid less than the names people expect", "elite in one stat", "his line / receivers are why". Pay comparisons use "a year" (average per year), never cap hit, and only players with a confirmed pay figure.

## 3. Photos: game-day first (owner's rules)
1. **Game-day photos.** In-game photos from this season, not camp, practice or Media Day. Best source: the team's own game galleries (e.g. 49ers.com "Game Photos", photographer Kym Fortino):
   ```bash
   python3 -I .claude/skills/weekly-tiers-post/scripts/photos.py gallery "https://www.49ers.com/photos/<gallery>" "Brock Purdy" --fetch --dir $WORK/gallery
   ```
   It lists every photo captioned with the player and its credit ("Terrell Lloyd/49ers"), downloads the full-size originals, and skips agency photos. The team site and `static.clubs.nfl.com` must be allowed in the environment's network settings (49ers: done; other teams: add `www.<team>.com`). The user may also send photos and name the photographer: use those first.
2. **Credit every photo**: `photos.py add SLOT <file> --credit "Kym Fortino/49ers" --title "Brock Purdy at Dallas" --dir $WORK/photos`. Slots: `cover`, `p1`, `p2`, `p3`, `cta` (the Story reuses `cover`).
3. **Never**: Getty, AP, Imagn / USA Today, Reuters or watermarked photos; trading-card scans; a player edited into a uniform or scene he was not in (no swapped helmets or jerseys, no AI composites). These photos are for social posts only: never on plainstatsnfl.com or in the repo.
4. **Look at every photo** (Read it): this season's uniform, face visible, in-game. Use a different photo on each slide where possible; the player must be in the cover photo.

## 4. Content
Copy `content.example.json` to `$WORK/content.json` and rewrite it from the facts sheet:
- `url`: the player's page from the sheet (`plainstatsnfl.com/players/<slug>`); `foot`: "PlainScore · 2026 thru Week N".
- `cover`: `team` (sets the accent colour: never a fixed blue), `label`, `line1`, `line2` (accent), `sub`, text `pills` like `{"text": "Purdy 98"}`, `swipe`.
- Slides: `player` (gid; tag, title, hook); `players` (ranked list: `gids`, `star` = the player, `why` per gid with EPA and pay from the sheet, or `pos: true` for a mixed-position list such as his offensive line); `cta` (title, text, `source` naming the pay report, e.g. "Purdy: CBS Sports").
- `story`: kicker, title, `line2` (accent), text, `sticker` ("See why").
- Sums and comparisons only from shown figures, and say what they are ("together they make less a year than Purdy").

## 5. Crops
Team-site game photos are usually 1280x720 landscape. Per slot in `content.json` `crop`: `{"ig": ["auto 100%", "50% 0%"], "tt": ["auto 100%", "50% 0%"]}`: the height fills the slide and the first percentage slides the frame sideways onto the player. Zoom the Instagram cover up to `auto 118%`. His face must sit above the text block: on slides with a two-line title (top-5 list) pick the photo with the face highest in the frame. Tall portrait photos with headroom: pre-crop them (PIL) so the helmet is near the top.

## 6. Render
```bash
python3 -I .claude/skills/weekly-tiers-post/scripts/render_post.py --content $WORK/content.json --photos $WORK/photos --out $WORK/out --format both --story --reel
```
Output: `out/ig/01..05` (Instagram carousel), `out/tt/01..05` (TikTok photo post, Reels and extra Story frames), `out/story/story.png` (Story with a link-sticker band), `out/reel/reel.mp4` (silent, 3 s a slide, crossfades). Fix every WARNING. Check `contact.png` for both formats and the Story: face above the text on every slide, credit line readable, nothing important in the bottom 350 px or right 110 px of the tt slides.

## 7. Captions and links
Write `out/caption_instagram.txt`, `out/caption_tiktok.txt` and `out/links_and_how_to_post.txt` (templates: `examples/` in this folder, the Purdy post: hook, the ranked list with pay, two data takes, a comment question, "link in bio" + the page address, the source line, "Photos: <credits>", hashtags; TikTok adds a title of about 90 characters and a pinned comment).
- **Story link sticker** (tracked): `https://plainstatsnfl.com/players/<slug>?utm_source=instagram&utm_medium=social&utm_campaign=<player>-plainscore&utm_content=story`
- **Captions / comments**: `plainstatsnfl.com/ig/players/<slug>` (Instagram), `plainstatsnfl.com/tt/players/<slug>` (TikTok pinned comment). Both redirect with UTM tags (vercel.json).
- **Bio link page**: add the post at the top of `posts` in `data/links.json` (`{"date": "YYYY-MM-DD", "title": "...", "path": "/players/<slug>", "platform": "both"}`), commit and push that line only. It goes live on plainstatsnfl.com/links when the branch reaches `main` (Vercel deploys main).

## 8. Deliver
Send with `SendUserFile` (`display: attach`): the Reel, the Story, the 5 Instagram slides, the captions and the links sheet; on request the 5 TikTok slides. Say which photo is on which slide and anything soft or cropped tight. How to post: carousel = `ig/` in order; Reel = `reel.mp4` + a sound picked in the app; Story = `story.png` + Link sticker in the empty band; TikTok = `tt/` as a photo post (or the MP4) + a sound + pinned comment. Never post anything yourself.

## Known pitfalls
- Wikimedia Commons rarely has current players in NFL uniforms (Purdy: only Iowa State close-ups) and rate-limits the sandbox for many minutes; go to the team galleries first.
- `www.49ers.com` and `static.clubs.nfl.com` were blocked until added to the environment; `flic.kr` / Flickr photos are mostly NC/ND or card scans.
- 1280x720 photos look soft on the 9:16 slides (about 405 px of width is used); ask the user for full-size originals when the face is small.
- Two-line titles push the text block up; re-check faces after any wording change.
