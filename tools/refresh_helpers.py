"""Small helpers for tools/refresh.sh (the GitHub Actions nflverse refresh). Run with python3 -I.

  python3 -I tools/refresh_helpers.py final-week <games.csv> <season>     last week whose regular-season games are ALL final
  python3 -I tools/refresh_helpers.py played-week <games.csv> <season>    last week with ANY final game (Sunday night: the week in progress)
  python3 -I tools/refresh_helpers.py count-final <games.csv> <season> <week>   "final/total" for that week
  python3 -I tools/refresh_helpers.py snapshot <out.json>                  window.__pcSnapshot() from the built page (power ranks, week)
  python3 -I tools/refresh_helpers.py prev-ranks <old.json>                set data/season.json week from data/stats.json "thru", and
                                                                          prevRanks from the old snapshot when the week moved forward
"""
import csv, functools, http.server, json, os, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reg_games(path, season):
    return [g for g in csv.DictReader(open(path, encoding='utf-8')) if g['season'] == str(season) and g['game_type'] == 'REG']


def final(g):
    return g['home_score'] not in ('', 'NA') and g['away_score'] not in ('', 'NA')


def final_week(path, season):
    weeks = {}
    for g in reg_games(path, season):
        weeks.setdefault(int(g['week']), []).append(final(g))
    done = [w for w, f in weeks.items() if all(f)]
    return max(done) if done else 0


def played_week(path, season):
    w = [int(g['week']) for g in reg_games(path, season) if final(g)]
    return max(w) if w else 0


def snapshot(out):
    from playwright.sync_api import sync_playwright
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get('PW_CHROMIUM') or None)
        page = b.new_page()
        page.goto(f'http://127.0.0.1:{srv.server_address[1]}/index.html#rankings')
        page.wait_for_function('() => window.__pcSnapshot && window.__pcSnapshot().power.length === 32', timeout=30000)
        snap = page.evaluate('() => window.__pcSnapshot()')
        b.close()
    srv.shutdown()
    json.dump({'week': snap['week'], 'power': snap['power']}, open(out, 'w'))
    print('snapshot week', snap['week'], 'top 3', [t['id'] for t in snap['power'][:3]])


def prev_ranks(old_path):
    sp = os.path.join(ROOT, 'data', 'season.json')
    season = json.load(open(sp))
    thru = json.load(open(os.path.join(ROOT, 'data', 'stats.json'))).get('thru')
    old = json.load(open(old_path)) if old_path and os.path.exists(old_path) else None
    if old and thru and old.get('week') and thru > old['week'] and len(old.get('power') or []) == 32:
        season['prevRanks'] = {t['id']: t['rank'] for t in old['power']}
        print('prevRanks set from week', old['week'])
    else:
        print('prevRanks kept (week did not move forward or no snapshot)')
    if thru:
        season['week'] = thru
    json.dump(season, open(sp, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'final-week':
        print(final_week(sys.argv[2], sys.argv[3]))
    elif cmd == 'played-week':
        print(played_week(sys.argv[2], sys.argv[3]))
    elif cmd == 'count-final':
        gs = [g for g in reg_games(sys.argv[2], sys.argv[3]) if int(g['week']) == int(sys.argv[4])]
        print(f"{sum(final(g) for g in gs)}/{len(gs)}")
    elif cmd == 'snapshot':
        snapshot(sys.argv[2])
    elif cmd == 'prev-ranks':
        prev_ranks(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        sys.exit('unknown command ' + cmd)
