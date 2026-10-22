"""Rookie pay scale and CBA minimum salaries, shared by build_contracts.py and build_draft.py.
All inputs live in data/cba.json (official figures and real signings with their sources)."""
import json, math, pathlib
CBA = json.load(open(pathlib.Path(__file__).parent / 'cba.json'))
MIN26 = {int(k): v for k, v in CBA['minSalary']['2026'].items()}
STEP = CBA['minSalary']['stepPerYearEst']
def minsal(cs, year):
    cs = max(0, min(7, cs))
    return MIN26[cs] + STEP * (year - 2026)

PS = CBA['practiceSquad']['2026']
RS = CBA['rookieScale']
ANCH = sorted(RS['anchors2026'], key=lambda a: a['pick'])
LAST_PICK = 257
# floor = four minimum-salary years for a 2026 rookie (CS 0,1,2,3 in 2026..2029)
FLOOR26 = sum(minsal(k, 2026 + k) for k in range(4))

def interp(pick, pts):
    """log-linear interpolation of (pick, value) points; flat beyond the ends"""
    pts = sorted(pts)
    if pick <= pts[0][0]: return pts[0][1]
    if pick >= pts[-1][0]: return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= pick <= x1:
            t = (pick - x0) / (x1 - x0)
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))

# total above the minimum floor, by pick (so late picks converge on the minimum ladder)
TOT_PTS = [(a['pick'], max(1.0, a['total'] - FLOOR26)) for a in ANCH] + [(LAST_PICK, 200000.0)]
SHARE_PTS = [(a['pick'], a['bonus'] / a['total']) for a in ANCH if a.get('bonus')] + [(LAST_PICK, 0.03)]
def share(pick):
    pts = sorted(SHARE_PTS)
    if pick <= pts[0][0]: return pts[0][1]
    if pick >= pts[-1][0]: return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= pick <= x1: return y0 + (y1 - y0) * (pick - x0) / (x1 - x0)

NO1 = {int(k): v[0] for k, v in RS['classNo1'].items()}
def class_factor(c): return NO1.get(c, NO1[2026]) / NO1[2026]

def rookie_deal(pick, cls):
    """four-year rookie contract for draft slot `pick` in class `cls` -> dict"""
    f = class_factor(cls)
    total26 = FLOOR26 + interp(pick, TOT_PTS)
    total = round(total26 * f)
    bonus = round(total26 * share(pick) * f)
    years = [cls + k for k in range(4)]
    floor = [minsal(k, cls + k) for k in range(4)]
    extra = max(0, total - bonus - sum(floor))
    W = (0, 0.25, 0.33, 0.42)  # rookie base salaries climb each year (CBA limits on yearly raises)
    base = [round(floor[k] + extra * W[k]) for k in range(4)]
    cap = {y: round(bonus / 4 + base[k]) for k, y in enumerate(years)}
    return dict(total=total, bonus=bonus, base=dict(zip(years, base)), cap=cap, end=cls + 3, r1=pick <= 32)

