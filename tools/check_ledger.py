"""Offline checks on data/ledger.csv, the list of reported contracts.

Catches the mistakes that slip in when a row is typed by hand: a missing source or link, totals that
don't add up, guarantees bigger than the deal, end years that don't match the length, duplicate rows.
It does not open the links; the ledger-checker agent does that (.claude/agents/ledger-checker.md).

Run:  python3 -I tools/check_ledger.py      (exit code 1 if anything needs a look)
"""
import csv, os, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {'Extension', 'Signing', 'Restructure', 'Trade', 'Release', 'Rookie'}


def num(v):
    v = (v or '').strip()
    return int(float(v)) if v else None


def main():
    path = os.path.join(ROOT, 'data', 'ledger.csv')
    issues, seen = [], {}
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, start=2):
        who = f"line {i} ({r.get('name') or 'no name'})"
        say = lambda msg: issues.append(f'{who}: {msg}')
        if not (r.get('name') and r.get('team') and r.get('pos')):
            say('name, team or position is blank')
        if not r.get('source'):
            say('no named source')
        if not (r.get('url') or '').startswith('https://'):
            say('link is missing or not https')
        if r.get('kind') and r['kind'] not in KINDS:
            say(f"unknown kind '{r['kind']}'")
        try:
            signed = date.fromisoformat(r['signed']) if r.get('signed') else None
        except ValueError:
            signed = None
            say(f"signed date '{r['signed']}' is not YYYY-MM-DD")
        if signed and signed > date.today():
            say('signed date is in the future')
        try:
            years, end, total, apy = num(r.get('years')), num(r.get('end')), num(r.get('total')), num(r.get('apy'))
            gtd, fully, bonus = num(r.get('gtd')), num(r.get('fully_gtd')), num(r.get('bonus'))
        except ValueError as e:
            say(f'a money or year field is not a number ({e})')
            continue
        if total and apy and years and r.get('kind') != 'Restructure':
            if abs(apy * years - total) > 0.05 * total:
                say(f'apy x years = {apy * years:,} but total is {total:,}')
        for label, v in (('guarantee', gtd), ('fully guaranteed', fully), ('signing bonus', bonus)):
            if v and total and v > total:
                say(f'{label} {v:,} is bigger than the total {total:,}')
        if fully and gtd and fully > gtd:
            say('fully guaranteed is bigger than total guarantees')
        if apy and not (750_000 <= apy <= 80_000_000):
            say(f'apy {apy:,} looks out of range')
        key = (r.get('name'), r.get('signed'), r.get('kind'))
        if key in seen:
            say(f'duplicate of line {seen[key]}')
        seen[key] = i
    for line in issues:
        print('CHECK', line)
    print(f'{len(rows)} ledger rows, {len(issues)} need a look')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
