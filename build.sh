#!/bin/sh
# Wraps src.html into index.html for Vercel and turns on the Airtable data hook.
cd "$(dirname "$0")"
{
  printf '%s\n' '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style></head><body>'
  cat src.html
  printf '\n%s\n' '</body></html>'
} > index.html
# the data hook must run before the page script
python3 - <<'PY'
p='index.html'
s=open(p,encoding='utf8').read()
s=s.replace('<script>\n/* CALC-START */',"<script>window.PLAINCAP_API='/api/contracts';</script>\n<script>\n/* CALC-START */",1)
open(p,'w',encoding='utf8').write(s)
PY
