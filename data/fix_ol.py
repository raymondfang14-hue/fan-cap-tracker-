"""Correct OL position labels (LT/LG/C/RG/RT) in nfl.json using the latest nflverse depth chart.
Run after nfl.json is refreshed:  python3 data/fix_ol.py /path/to/depth_charts_<season>.csv"""
import json, csv, sys, re, unicodedata
OL = ('LT','LG','C','RG','RT')
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    s = re.sub(r"[.'’\-]", '', s); s = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()
rows = list(csv.DictReader(open(sys.argv[1])))
mx = max(r['dt'] for r in rows)
fix = {'WSH':'WAS','LA':'LAR','JAC':'JAX','ARZ':'ARI','BLT':'BAL','CLV':'CLE','HST':'HOU','SD':'LAC','OAK':'LV'}
dc = {}
for r in rows:
    if r['dt'] != mx or r['pos_abb'] not in OL: continue
    try: rk = int(r['pos_rank'])
    except: rk = 9
    t = fix.get(r['team'], r['team'])
    dc.setdefault((t, norm(r['player_name'])), []).append((rk, r['pos_abb']))
d = json.load(open('data/nfl.json'))
ch = 0; miss = []
for p in d['players']:
    if p[2] not in OL: continue
    c = dc.get((p[1], norm(p[0])))
    if not c: miss.append((p[0], p[1], p[2])); continue
    new = sorted(c)[0][1]
    if new != p[2]: print('FIX', p[0], p[1], p[2], '->', new); p[2] = new; ch += 1
json.dump(d, open('data/nfl.json','w'), separators=(',',':'))
# Also write an override map the page applies at load, so a refreshed nfl.json can't undo the fix.
ov = {}
for p in d['players']:
    if p[2] in OL and dc.get((p[1], norm(p[0]))): ov[p[1] + '|' + norm(p[0])] = p[2]
json.dump({'asOf': mx[:10], 'pos': ov}, open('data/ol_pos.json','w'), separators=(',',':'))
print('changed', ch, 'unmatched', len(miss)); print(miss)
