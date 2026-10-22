#!/usr/bin/env python3
"""Screenshot the HTML previews written by tools/preview_og.mjs at 1200x630.

Run:  python3 -I tools/shot_og.py PREVIEW_DIR [PNG_DIR]     (PNGs default to PREVIEW_DIR)
"""
import pathlib, sys
from playwright.sync_api import sync_playwright

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src
dst.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1200, 'height': 630})
    for f in sorted(src.glob('*.html')):
        pg.goto(f.resolve().as_uri())
        pg.wait_for_timeout(150)
        pg.screenshot(path=str(dst / (f.stem + '.png')))
        print(dst / (f.stem + '.png'))
    b.close()
