#!/usr/bin/env python3
"""Fetch an NFL team's logo and roster headshot URLs from ESPN's public site API.

Usage:
    python tools/espn_assets.py "kansas city chiefs"     # one team
    python tools/espn_assets.py                          # prompts for a team
    python tools/espn_assets.py --all                    # all 32 teams

For each team it writes, under data/espn/<ID>/:
    logo.png        the team logo
    roster.txt      "Player Name | headshot URL" per line (clean text list)
and merges everything into data/espn_assets.json, which Plain Cap reads to show
logos and headshots (falling back to its own crests and initials where missing).

Endpoints (unofficial, no key needed):
    https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams
    https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{id}/roster

Note: ESPN's images are owned by ESPN, the NFL and its clubs. Check you may use
them on your site before publishing; Plain Cap hot-links nothing unless this
file exists.
"""
import argparse, csv, difflib, json, re, sys, unicodedata, urllib.request
from pathlib import Path

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "espn"
ASSETS = ROOT / "data" / "espn_assets.json"
# ESPN abbreviation -> Plain Cap team id (only where they differ)
ID_FIX = {"WSH": "WAS", "JAC": "JAX"}


ROWS = []


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "PlainCap/1.0 (+https://fan-cap-tracker.vercel.app)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else json.loads(data)


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"[^a-z]", "", s)


def load_teams():
    teams = get(f"{BASE}/teams")["sports"][0]["leagues"][0]["teams"]
    return [t["team"] for t in teams]


def find_team(teams, query):
    q = norm(query)
    names = {}
    for t in teams:
        for key in (t["displayName"], t["name"], t["location"], t["abbreviation"], t.get("shortDisplayName", "")):
            if key:
                names[norm(key)] = t
    if q in names:
        return names[q]
    hits = [t for k, t in names.items() if q and (q in k or k in q) and len(q) > 2]
    if len({t["id"] for t in hits}) == 1:
        return hits[0]
    close = difflib.get_close_matches(q, names.keys(), n=1, cutoff=0.6)
    if close:
        return names[close[0]]
    raise SystemExit(f"No NFL team matched '{query}'. Try e.g. 'chiefs' or 'KC'.")


def team_logo_url(t):
    logos = t.get("logos") or []
    for l in logos:  # prefer the default (light background) logo
        if "default" in (l.get("rel") or []):
            return l["href"]
    return logos[0]["href"] if logos else f"https://a.espncdn.com/i/teamlogos/nfl/500/{t['abbreviation'].lower()}.png"


def roster(team_id):
    data = get(f"{BASE}/teams/{team_id}/roster")
    out = []
    for grp in data.get("athletes", []):
        for a in grp.get("items", []):
            name = a.get("fullName") or a.get("displayName")
            if not name:
                continue
            hs = (a.get("headshot") or {}).get("href") or \
                f"https://a.espncdn.com/i/headshots/nfl/players/full/{a['id']}.png"
            out.append({"name": name, "pos": (a.get("position") or {}).get("abbreviation", ""), "headshot": hs})
    return out


def run_team(t, assets):
    pc_id = ID_FIX.get(t["abbreviation"], t["abbreviation"])
    folder = OUT / pc_id
    folder.mkdir(parents=True, exist_ok=True)
    logo = team_logo_url(t)
    (folder / "logo.png").write_bytes(get(logo, binary=True))
    players = roster(t["id"])
    (folder / "roster.txt").write_text(
        "\n".join(f"{p['name']} | {p['headshot']}" for p in players) + "\n", encoding="utf-8")
    assets["teams"][pc_id] = {"logo": logo, "name": t["displayName"]}
    for p in players:
        ROWS.append([pc_id, t["displayName"], logo, p["name"], p["pos"], p["headshot"]])
    for p in players:
        assets["players"][f"{pc_id}|{norm(p['name'])}"] = p["headshot"]
    print(f"{t['displayName']}: logo saved, {len(players)} players -> {folder.relative_to(ROOT)}/roster.txt")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("team", nargs="*", help="team name, city or abbreviation")
    ap.add_argument("--csv", action="store_true", help="also write data/plaincap_espn_assets.csv")
    ap.add_argument("--all", action="store_true", help="fetch all 32 teams")
    args = ap.parse_args()

    teams = load_teams()
    if args.all:
        chosen = teams
    else:
        q = " ".join(args.team) or input("NFL team: ").strip()
        chosen = [find_team(teams, q)]

    assets = {"teams": {}, "players": {}}
    if ASSETS.exists():  # merge with earlier runs
        assets.update(json.loads(ASSETS.read_text()))
    for t in chosen:
        try:
            run_team(t, assets)
        except Exception as e:  # keep going on --all
            print(f"{t['displayName']}: failed ({e})", file=sys.stderr)
    if args.csv:
        with open(ROOT / "data" / "plaincap_espn_assets.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["team_id", "team_name", "logo_url", "player", "position", "headshot_url"])
            w.writerows(ROWS)
    ASSETS.write_text(json.dumps(assets, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {ASSETS.relative_to(ROOT)} ({len(assets['teams'])} teams, {len(assets['players'])} players)")


if __name__ == "__main__":
    main()
