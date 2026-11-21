#!/usr/bin/env python3
"""Tell Bing (and the other IndexNow engines: Yandex, Seznam, Naver; Bing passes it to DuckDuckGo and Yahoo) which pages changed.

IndexNow needs no account: the key file at the site root (<key>.txt, holding the key) proves the site is ours. The key is
public by design; it is not a secret. Bing fetches the key file when it reads the ping, so the page must be live first.

  python3 -I tools/indexnow.py              # pages whose sitemap lastmod is within the last 2 days (the default)
  python3 -I tools/indexnow.py --days 7
  python3 -I tools/indexnow.py --all        # every address in sitemap.xml (first run, or after a big rebuild)
  python3 -I tools/indexnow.py --dry-run    # print what would be sent

Run by .github/workflows/indexnow.yml after each push to main and each nflverse refresh. Only sitemap addresses are sent,
so noindex pages never go out.
"""
import argparse, datetime as dt, glob, json, os, re, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'www.plainstatsnfl.com'
ENDPOINT = 'https://api.indexnow.org/indexnow'
BATCH = 10000  # IndexNow's limit per request
# Cloudflare answers 403 to Python's default user agent (Python-urllib), so name ours.
UA = {'User-Agent': 'PlainStats-IndexNow/1.0 (+https://www.plainstatsnfl.com)'}


def key():
    files = [f for f in glob.glob(os.path.join(ROOT, '*.txt')) if re.fullmatch(r'[0-9a-f]{32}\.txt', os.path.basename(f))]
    if len(files) != 1:
        sys.exit(f'expected one IndexNow key file (<32 hex>.txt) at the repo root, found {len(files)}')
    k = open(files[0]).read().strip()
    if k + '.txt' != os.path.basename(files[0]):
        sys.exit('the key file must contain its own name (without .txt)')
    return k


def sitemap():
    xml = open(os.path.join(ROOT, 'sitemap.xml')).read()
    return re.findall(r'<loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?', xml)


def wait_live(k, tries):
    url = f'https://{HOST}/{k}.txt'
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                if r.status == 200 and r.read().decode().strip() == k:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        if i < tries - 1:
            time.sleep(30)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--days', type=int, default=2)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--wait', type=int, default=12, help='times to check (30 s apart) that the key file is live')
    a = ap.parse_args()

    k = key()
    rows = sitemap()
    if a.all:
        urls = [u for u, _ in rows]
    else:
        since = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=a.days)).isoformat()
        urls = [u for u, lm in rows if lm and lm >= since]
    urls = [u for u in urls if u.startswith(f'https://{HOST}/')]
    print(f'{len(urls)} of {len(rows)} sitemap addresses to send' + (' (all)' if a.all else f' (lastmod in the last {a.days} days)'))
    if not urls:
        return
    if a.dry_run:
        print('\n'.join(urls[:20]) + ('\n...' if len(urls) > 20 else ''))
        return
    if not wait_live(k, a.wait):
        sys.exit(f'https://{HOST}/{k}.txt is not live yet; nothing sent')

    for i in range(0, len(urls), BATCH):
        body = json.dumps({'host': HOST, 'key': k, 'keyLocation': f'https://{HOST}/{k}.txt',
                           'urlList': urls[i:i + BATCH]}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, method='POST',
                                     headers={'Content-Type': 'application/json; charset=utf-8', **UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f'sent {len(urls[i:i + BATCH])}: HTTP {r.status}')
        except urllib.error.HTTPError as e:
            # 200 and 202 are success. 403: key file not valid; 422: address not on this host; 429: too many requests.
            sys.exit(f'IndexNow refused the batch: HTTP {e.code} {e.read().decode(errors="replace")[:300]}')


if __name__ == '__main__':
    main()
