"""Find and download license-free in-game photos from Wikimedia Commons for the weekly tiers post.

  python3 -I photos.py search "Trevor Lawrence" [--min-width 1500] [--limit 25]
  python3 -I photos.py fetch  SLOT "File:Trevor Lawrence (52377887812).jpg" --dir WORK/photos [--width 1920]
  python3 -I photos.py logos  --dir WORK/logos        (all 32 ESPN team logos; needs a.espncdn.com allowed)

`search` prints numbered candidates (title, size, license, artist). Only CC0, public domain, CC BY and CC BY-SA files are
listed (never NC or ND). `fetch` saves WORK/photos/SLOT.jpg and records the credit in WORK/photos/photos.json, which
render_post.py prints on each slide ("Title" by Artist, license).

Notes learned the hard way:
- Wikimedia asks for a descriptive User-Agent; the one below is generic on purpose (never put a personal email in it).
- The shared egress IP is rate limited (HTTP 429, retry-after 10 s). Requests are retried patiently; downloading ten photos
  can take 30+ minutes, so choose a few photos, run `fetch` in the background and keep working.
- Images load from upload.wikimedia.org (thumb.wikimedia.org is blocked in the cloud sandbox). Use a standard thumbnail
  width (1280, 1920, 3840). 1920 wide is enough for a 1080x1920 slide even when zoomed to 128%.
- ALWAYS look at the downloaded photo before using it. Check: right team's uniform (search results mix in college
  photos of the same player, e.g. Oregon for Bo Nix, Iowa State for Brock Purdy), the face is visible, in-game or
  game-day shot, portrait (2:3) is best because the slide text covers the lower two thirds.
"""
import argparse, json, os, random, re, sys, time, urllib.parse, urllib.request, urllib.error

UA = 'PlainStatsPostBuilder/1.0 (NFL stats social graphics)'
API = 'https://commons.wikimedia.org/w/api.php'
OK_LICENSE = ('CC BY', 'CC0', 'Public domain', 'PD')


def get(url, binary=False, tries=80):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60)
            return r.read() if binary else json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(int(e.headers.get('retry-after') or 10) + random.randint(2, 8))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10)
    raise RuntimeError('gave up on ' + url)


def api(**params):
    params.update(action='query', format='json')
    return get(API + '?' + urllib.parse.urlencode(params))


def license_ok(lic):
    return lic.startswith(OK_LICENSE) and 'ND' not in lic and 'NC' not in lic


def describe(page):
    i = page['imageinfo'][0]
    m = i['extmetadata']
    lic = m.get('LicenseShortName', {}).get('value', '')
    artist = re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', m.get('Artist', {}).get('value', ''))).strip()
    return {'title': page['title'], 'w': i['width'], 'h': i['height'], 'lic': lic, 'artist': artist,
            'url': i['url'].split('?')[0], 'page': i['descriptionurl']}


def thumb_url(url, width):
    m = re.match(r'(.*/commons)/(\w/\w\w/)(.+)$', url)
    return f'{m.group(1)}/thumb/{m.group(2)}{m.group(3)}/{width}px-{m.group(3)}'


def cmd_search(a):
    d = api(generator='search', gsrsearch=f'{a.query} filetype:bitmap', gsrnamespace=6, gsrlimit=a.limit,
            prop='imageinfo', iiprop='url|size|extmetadata')
    n = 0
    for p in sorted((d.get('query', {}).get('pages') or {}).values(), key=lambda p: p.get('index', 0)):
        x = describe(p)
        if not license_ok(x['lic']) or x['w'] < a.min_width or x['h'] < 1000:
            continue
        n += 1
        shape = 'portrait' if x['h'] > x['w'] else 'landscape'
        print(f"{n:>2}. {x['title']}  {x['w']}x{x['h']} {shape}  {x['lic']}  by {x['artist'][:40]}")
    if not n:
        print('no usable results (try a different query, or lower --min-width)')


def cmd_fetch(a):
    d = api(titles=a.title, prop='imageinfo', iiprop='url|size|extmetadata')
    page = next(iter(d['query']['pages'].values()))
    if 'imageinfo' not in page:
        sys.exit('file not found: ' + a.title)
    x = describe(page)
    if not license_ok(x['lic']):
        sys.exit(f"license not allowed: {x['lic']}")
    os.makedirs(a.dir, exist_ok=True)
    width = min(a.width, x['w'])
    b = get(thumb_url(x['url'], width), binary=True)
    open(os.path.join(a.dir, a.slot + '.jpg'), 'wb').write(b)
    meta_path = os.path.join(a.dir, 'photos.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    meta[a.slot] = {k: x[k] for k in ('title', 'artist', 'lic', 'page')}
    json.dump(meta, open(meta_path, 'w'), indent=1)
    print(f"saved {a.slot}.jpg ({len(b) // 1024} KB) {x['title']} | {x['lic']} | {x['page']}")


def cmd_logos(a):
    assets = json.load(open('data/espn_assets.json'))['teams']
    os.makedirs(a.dir, exist_ok=True)
    for k, v in assets.items():
        f = os.path.join(a.dir, k + '.png')
        if not os.path.exists(f):
            open(f, 'wb').write(urllib.request.urlopen(v['logo'], timeout=30).read())
    print(f'{len(assets)} logos in {a.dir}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search'); s.add_argument('query'); s.add_argument('--min-width', type=int, default=1500); s.add_argument('--limit', type=int, default=25); s.set_defaults(f=cmd_search)
    f = sub.add_parser('fetch'); f.add_argument('slot'); f.add_argument('title'); f.add_argument('--dir', required=True); f.add_argument('--width', type=int, default=1920); f.set_defaults(f=cmd_fetch)
    l = sub.add_parser('logos'); l.add_argument('--dir', required=True); l.set_defaults(f=cmd_logos)
    a = ap.parse_args()
    a.f(a)
