"""Merge year-by-year cap hits scraped from Over The Cap team pages into data/years_exact.json.
Usage: python3 -I data/merge_years.py batch1.json [batch2.json ...]
Each batch: {TEAM: {player: {year: cap_dollars}}}. A player is merged only when OTC's 2026 cap hit matches data/nfl.json
(within 3%) and the listed years run unbroken from 2026 to about the contract's last year. Cap hit per year is exact;
the base/other split of 2027+ reuses the 2026 bonus share (OTC's team page lists totals only). Existing entries are kept."""
import json, sys, re, unicodedata
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[.'’,]", '', s); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()
nfl = json.load(open('data/nfl.json')); ye = json.load(open('data/years_exact.json'))
idx = {(r[1], norm(r[0])): r for r in nfl['players']}
added = skipped = 0; why = {}
for fn in sys.argv[1:]:
    for team, pl in json.load(open(fn)).items():
        for name, yrs in pl.items():
            r = idx.get((team, norm(name)))
            if not r: why['nomatch'] = why.get('nomatch', 0) + 1; continue
            key = r[0] + '|' + team
            if key in ye['contracts']: continue
            cap26 = r[10]; ys = sorted(int(y) for y in yrs)
            if not ys or ys[0] != 2026 or not cap26 or abs(yrs['2026'] - cap26) > max(150000, 0.03 * cap26): why['cap26'] = why.get('cap26', 0) + 1; skipped += 1; continue
            if ys != list(range(2026, ys[-1] + 1)): why['gap'] = why.get('gap', 0) + 1; skipped += 1; continue
            end = r[8]
            need = min(end - 1, 2031)
            if ys[-1] < (need - 2 if r[9] else need) or ys[-1] > end + 1: why['end'] = why.get('end', 0) + 1; skipped += 1; continue
            bshare = min(1, (r[11 + 1] or 0) / cap26) if cap26 else 0
            out = {}
            for y in [y for y in ys if y <= max(end - 1, 2026)]:
                c = yrs[str(y)]
                if y == 2026: out['2026'] = [r[11], r[12], c]
                else: b = round(c * bshare); out[str(y)] = [c - b, b, c]
            ye['contracts'][key] = out; added += 1
json.dump(ye, open('data/years_exact.json', 'w'), indent=1)
print('added', added, 'skipped', skipped, why, 'total', len(ye['contracts']))
