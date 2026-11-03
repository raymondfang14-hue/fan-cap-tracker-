#!/usr/bin/env bash
# nflverse refresh: downloads the nflverse-data release files and runs the build scripts, in the order README.md documents.
# Run by .github/workflows/nflverse-refresh.yml; also works by hand:   tools/refresh.sh <daily|gameday|weekly> [download folder]
#
#   daily    contracts rebuild (roster, draft picks, snap counts, depth charts), older seasons, scores, this week's injury report
#   gameday  Sunday/Monday night: scores, season stats through the week being played, standings, game model, injury-adjusted picks
#   weekly   Tuesday: season stats through the last finished week, splits and history, standings, game model, OL measures, team tiers
#
# Every mode then rebuilds the search pages (build_seo.py), index.html (build.sh) and runs the checks. A step that fails is
# restored from git and reported; the rest still run. The exit code is 1 if any step failed, so the workflow shows it.
#
# This script only does the mechanical nflverse work. News, the contract ledger, the draft boards, cba.json and anything that needs
# judgment stay with the Claude scheduled tasks. Data rules (CLAUDE.md): nflverse only (CC BY 4.0); never the betting columns in games.csv.
set -u
MODE="${1:?usage: tools/refresh.sh <daily|gameday|weekly> [download folder]}"
cd "$(dirname "$0")/.."
SEASON=$(python3 -I -c "import json;print(json.load(open('data/nfl.json'))['season'])")
DL="${2:-${RUNNER_TEMP:-/tmp}/nflverse}"
mkdir -p "$DL"
REL=https://github.com/nflverse/nflverse-data/releases/download
FAILED=()
SUMMARY=()

say() { printf '\n== %s\n' "$*"; }
note() { SUMMARY+=("$*"); echo "$*"; }

# get <tag/file>...: download into $DL (skips files already fetched in this run), 3 tries each
get() {
  local f out
  for f in "$@"; do
    out="$DL/${f##*/}"
    [ -s "$out" ] && continue
    curl -sSfL --retry 3 --retry-delay 5 -o "$out.part" "$REL/$f" && mv "$out.part" "$out" || { echo "download failed: $f"; rm -f "$out.part"; return 1; }
  done
}

# step <name> <files to restore on failure> -- <command...>
step() {
  local name="$1" restore="$2"; shift 3
  say "$name"
  if ! "$@"; then
    echo "FAILED: $name; restoring $restore"
    git checkout -- $restore 2>/dev/null
    FAILED+=("$name")
    return 1
  fi
}

py() { python3 -I "$@"; }

contracts() {
  get rosters/roster_$SEASON.csv draft_picks/draft_picks.csv players/players.csv depth_charts/depth_charts_$SEASON.csv \
      snap_counts/snap_counts_$((SEASON-3)).csv snap_counts/snap_counts_$((SEASON-2)).csv snap_counts/snap_counts_$((SEASON-1)).csv snap_counts/snap_counts_$SEASON.csv &&
  py data/build_contracts.py "$DL" && py data/fix_ol.py "$DL/depth_charts_$SEASON.csv" && py data/build_depth.py "$DL/depth_charts_$SEASON.csv" "$SEASON" && py data/build_market.py
}

older_seasons() {
  local first s files=(players/players.csv)
  first=$(py -c "import json;print(json.load(open('data/history.json'))['seasons'][0])")
  for s in $(seq 1999 $((first-1))); do files+=(stats_player/stats_player_reg_$s.csv); done
  for s in $(seq 2013 $((first-1))); do files+=(snap_counts/snap_counts_$s.csv); done
  get "${files[@]}" && py data/build_history_old.py "$DL"
}

scores_injuries() {
  get schedules/games.csv injuries/injuries_$SEASON.csv &&
  py data/build_schedule.py "$DL/games.csv" "$SEASON" && py data/build_gameday.py "$DL/games.csv" "$DL/injuries_$SEASON.csv" "$SEASON" &&
  py data/build_injuries.py "$DL/injuries_$SEASON.csv" "$SEASON"
}

# stats <week>: season stats, the stats check, splits (weekly only) and history through <week>
stats() {
  local wk="$1" s
  get stats_player/stats_player_week_$SEASON.csv snap_counts/snap_counts_$SEASON.csv players/players.csv draft_picks/draft_picks.csv || return 1
  for s in $((SEASON-3)) $((SEASON-2)) $((SEASON-1)); do get stats_player/stats_player_week_$s.csv snap_counts/snap_counts_$s.csv || return 1; done
  get pbp/play_by_play_$SEASON.csv.gz || return 1   # estimated coverage in build_stats.py, splits below
  py data/build_stats.py "$DL" "$SEASON" data/stats.json "$wk" && py tools/check_stats.py "$DL" "$SEASON" || return 1
  if [ "$MODE" = weekly ]; then py data/build_splits.py "$DL" "$SEASON" || return 1; fi
  py data/build_history.py "$DL" "$SEASON"
}

standings_model() {
  get schedules/games.csv injuries/injuries_$SEASON.csv &&
  py data/build_standings.py "$DL/games.csv" "$SEASON" && py tools/refresh_helpers.py prev-ranks "$DL/old_snapshot.json" &&
  py data/build_schedule.py "$DL/games.csv" "$SEASON" && py data/build_projections.py "$DL/games.csv" "$SEASON" &&
  py data/build_gameday.py "$DL/games.csv" "$DL/injuries_$SEASON.csv" "$SEASON" &&
  py -c "
import json, sys
t = json.load(open('data/projections.json'))['teams'].values()
sb, po = sum(x.get('sb', 0) for x in t), sum(x.get('po', 0) for x in t)
print('model check: Super Bowl chances add to', round(sb, 1), '| playoff chances add to', round(po, 1))
sys.exit(0 if 95 <= sb <= 105 and 1350 <= po <= 1450 else 1)"
}

line_and_tiers() {
  get pbp/play_by_play_$SEASON.csv.gz && py data/build_olwin.py "$DL/play_by_play_$SEASON.csv.gz" && py data/build_tiers.py "$DL/play_by_play_$SEASON.csv.gz"
}

search_pages() { py tools/build_seo.py && sh build.sh && py -c "import xml.dom.minidom as m;m.parse('sitemap.xml')"; }

scripts_parse() {
  node -e "
const h=require('fs').readFileSync('index.html','utf8');let n=0;
for (const m of h.matchAll(/<script(?![^>]*(src=|application\/ld\+json))[^>]*>([\s\S]*?)<\/script>/g)) { new Function(m[2]); n++; }
console.log('inline scripts parse:', n);"
}

STATS_FILES="data/stats.json data/history.json data/drafted.json data/hist data/splits.json"
MODEL_FILES="data/season.json data/schedule.json data/projections.json data/gameday.json"

case "$MODE" in
  daily)
    step "contracts rebuild" "data/nfl.json data/years_calc.json data/ol_pos.json data/market.json data/depth.json" -- contracts
    step "older seasons" "data/history_old.json data/hist" -- older_seasons
    step "scores and injury report" "data/schedule.json data/gameday.json data/injuries.json" -- scores_injuries
    ;;
  gameday|weekly)
    get schedules/games.csv || FAILED+=("download games.csv")
    if [ "$MODE" = weekly ]; then WK=$(py tools/refresh_helpers.py final-week "$DL/games.csv" "$SEASON"); else WK=$(py tools/refresh_helpers.py played-week "$DL/games.csv" "$SEASON"); fi
    note "stats week $WK: $(py tools/refresh_helpers.py count-final "$DL/games.csv" "$SEASON" "$WK") games final"
    # last week's power ranks, read from the page before the stats change, for the movement arrows
    step "power snapshot" "" -- py tools/refresh_helpers.py snapshot "$DL/old_snapshot.json"
    step "season stats and history" "$STATS_FILES" -- stats "$WK"
    step "standings and game model" "$MODEL_FILES" -- standings_model
    if [ "$MODE" = weekly ]; then
      step "OL measures and team tiers" "data/olwin.json data/tiers.json" -- line_and_tiers
    else
      step "injury history" "data/injuries.json" -- py data/build_injuries.py "$DL/injuries_$SEASON.csv" "$SEASON"
    fi
    ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac

step "search pages" "players teams draft sitemap.xml tools/seo-nav.html data/pageslugs.json og-data index.html" -- search_pages
# A broken page must never be pushed: these two are hard failures (exit 3, the workflow commits nothing).
HARD=0
step "inline scripts parse" "" -- scripts_parse || HARD=1
if [ "${SKIP_PAGE_CHECK:-}" != 1 ]; then
  step "page check (every view, phone and desktop, light and dark)" "" -- py tools/check_pages.py || HARD=1
fi
git checkout -- data/__pycache__ 2>/dev/null || true

say "summary"
for s in "${SUMMARY[@]}"; do echo "- $s"; done
if [ $HARD = 1 ]; then
  echo "The page is broken (failed: ${FAILED[*]}). Nothing should be pushed."
  exit 3
fi
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "Failed steps (restored from git, the rest can be pushed): ${FAILED[*]}"
  exit 1
fi
echo "All steps ran."
