#!/bin/sh
# Wraps src.html (the page, also published as the Plain Cap artifact) into index.html, which Vercel serves.
cd "$(dirname "$0")"
{
  printf '%s\n' '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}</style></head><body>'
  cat src.html
  printf '\n%s\n' '</body></html>'
} > index.html
