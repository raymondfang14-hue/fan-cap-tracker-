"""Facts sheet for a PlainStats player social post. Every number a slide may quote comes from here.

  python3 -I .claude/skills/player-post/scripts/player_facts.py "Brock Purdy" [--team SF] [--top 6]

Prints, from data/plainscore.json (exported from src.html plainScore(); never recomputed) and data/nfl.json, matched by
gsis id: the player's PlainScore, rank, group size, play rating and every bar (percentile, value); his yearly pay only when
the export has a pay bar (a confirmed contract; otherwise "Contract being verified"); the named report behind it
(data/ledger.csv); the top N of his rating group with pay; his team's players at or near the top of their own groups; his
page path (data/pageslugs.json) and a ready content.json gid list. Hook candidates are listed at the end.
"""
import argparse, csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
J = lambda f: json.load(open(ROOT / 'data' / f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('--team'); ap.add_argument('--top', type=int, default=6)
    a = ap.parse_args()
    PS = J('plainscore.json'); P = PS['players']
    rows = {r[19]: r for r in J('nfl.json')['players'] if len(r) > 19 and r[19]}
    slugs = J('pageslugs.json')['p']
    hits = [g for g, r in rows.items() if r[0].lower() == a.name.lower() and (not a.team or r[1] == a.team)]
    if not hits:
        sys.exit(f'no player named {a.name!r}' + (f' on {a.team}' if a.team else '') + ' in data/nfl.json')
    if len(hits) > 1:
        sys.exit('several players match; add --team: ' + ', '.join(rows[g][1] for g in hits))
    gid = hits[0]; name, team, pos = rows[gid][0], rows[gid][1], rows[gid][2]
    pay = lambda v: next((b[2] for b in v['bars'] if b[3] == 'pay'), None)
    print(f'{name} ({team} {pos}) gsis {gid} · PlainScore export thru Week {PS["week"]}')
    key = f'p-{re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")}-{team.lower()}'
    print(f'page: ' + (f'/players/{slugs[key]}' if key in slugs else f'(no static page; app path /player/{key[2:]})'))
    if gid not in P:
        sys.exit('no PlainScore (not qualified yet, or export is stale: ./build.sh then tools/refresh_helpers.py plainscore)')
    v = P[gid]
    print(f'PlainScore {v["s"]} · #{v["rk"]} of {v["n"]} qualified {v["grp"]} · play rating {v["play"]}')
    for b in v['bars']:
        n = b[1]; suf = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        print(f'  {b[0]:<22} {n:>3}{suf} pct   {b[2]}')
    p = pay(v)
    print('pay: ' + (p or 'Contract being verified (no pay on slides)'))
    if p:
        for r in csv.reader(open(ROOT / 'data' / 'ledger.csv')):
            if r and r[0] == name and r[1] == team:
                print(f'  ledger: {r[3]} {r[4]}, {r[5]} yrs through {r[6]}, source {r[13]} {r[14]}')

    grp = sorted((x for x in P.items() if x[1]['grp'] == v['grp']), key=lambda x: x[1]['rk'])
    print(f'\nTop {a.top} {v["grp"]}:')
    for g, x in grp[:a.top]:
        epa = next((b[2] for b in x['bars'] if b[3] == 'epa'), '')
        print(f'  #{x["rk"]:<3} {rows[g][0]:<24} {rows[g][1]:<4} {x["s"]:>3}  {("EPA " + epa) if epa else "":<10} {pay(x) or "Contract being verified"}   {g}')

    mates = sorted(((g, x) for g, x in P.items() if g in rows and rows[g][1] == team and g != gid and x['rk'] <= 3), key=lambda t: (t[1]['rk'], -t[1]['s']))
    if mates:
        print(f'\n{team} teammates ranked top 3 in their group:')
        for g, x in mates:
            print(f'  #{x["rk"]} of {x["n"]} {x["grp"]:<16} {rows[g][0]:<24} {x["s"]:>3}  {pay(x) or "Contract being verified"}   {g}')

    print('\nHook candidates (check each against the lines above):')
    if v['rk'] == 1:
        print(f'  - #1 of {v["n"]} {v["grp"]} by PlainScore ({v["s"]}).')
    paid_more = [rows[g][0] for g, x in grp[:max(v['rk'] + 3, 4)] if g != gid and pay(x) and p and float(re.sub(r'[^0-9.]', '', pay(x))) > float(re.sub(r'[^0-9.]', '', p)) and x['rk'] > v['rk']]
    if paid_more:
        print(f'  - Ranked above, and paid less than: {", ".join(paid_more)} (compare "a year" figures only).')
    top_bars = [b[0] for b in v['bars'] if b[3] != 'pay' and b[1] >= 95]
    if top_bars:
        print(f'  - 95th percentile or better in: {", ".join(top_bars)}.')
    if len(mates) >= 3:
        print(f'  - {len(mates)} {team} teammates rank top 3 at their spot.')


if __name__ == '__main__':
    main()
