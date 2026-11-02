import sys, os, json
from playwright.sync_api import sync_playwright
F='/home/user/fan-cap-tracker-/assets/fonts/'; HERE=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]
PH=f'{HERE}/img/jonathan-taylor.jpg'; N=7
DATA=json.load(open(f'{HERE}/taylor_data.json'))
TH={'IND':('#1d4fd6','#0a1d5c','#8fb4ff'),'MIN':('#7a43c8','#2b1457','#ffc62f'),'SEA':('#2f6fbf','#00152e','#69be28'),'NYG':('#2a4fb8','#071642','#ff5a73')}
CSS=f"""
@font-face{{font-family:I;font-weight:800;src:url('file://{F}Inter-ExtraBold.otf')}}
@font-face{{font-family:I;font-weight:600;src:url('file://{F}Inter-SemiBold.otf')}}
*{{box-sizing:border-box;margin:0}}
body{{width:1080px;height:1350px;font-family:I,sans-serif;color:#fff;position:relative;overflow:hidden;background:#07101f}}
.abs{{position:absolute}}
.logo{{position:absolute;left:72px;top:54px;font-size:30px;font-weight:800;letter-spacing:-.02em;z-index:9;background:#fff;color:#000;padding:8px 20px 9px;border-radius:999px}}
.dots{{position:absolute;right:72px;top:78px;display:flex;gap:14px;z-index:9}}
.dots i{{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.35)}} .dots i.on{{background:#fff}}
.eyebrow{{position:absolute;left:72px;font-size:28px;font-weight:600;color:#dbe4f3;z-index:9}}
h1{{position:absolute;left:72px;width:936px;font-weight:800;letter-spacing:-.04em;line-height:1;z-index:9;text-shadow:0 2px 24px rgba(0,0,0,.55)}}
h1 em{{font-style:normal;color:var(--a)}}
.foot{{position:absolute;left:72px;right:72px;bottom:52px;display:flex;justify-content:space-between;font-size:24px;font-weight:600;color:#dbe4f3;z-index:9}}
.foot b{{color:#fff;font-weight:800;font-size:27px}}
.big{{font-weight:800;letter-spacing:-.05em;line-height:.92}}
.lab{{font-size:26px;font-weight:600;color:#dbe4f3;line-height:1.2;text-shadow:0 2px 14px rgba(0,0,0,.6)}}
.tile{{border-radius:28px;background:rgba(6,12,28,.62);border:1px solid rgba(255,255,255,.2);padding:22px 28px;backdrop-filter:blur(2px)}}
.chip{{display:inline-block;padding:8px 20px;border-radius:999px;font-size:26px;font-weight:800;background:#fff;color:#000}}
"""
def shell(i,theme,body,photo,foot='PlainStats · nflverse through Week 8'):
    c,d,a=TH[theme]
    dots=''.join(f'<i class="{"on" if k==i else ""}"></i>' for k in range(N))
    return f'<html><head><meta charset=utf-8><style>:root{{--a:{a}}}{CSS}</style></head><body><div class=abs style="inset:0;background:linear-gradient(115deg,{d},#070f20 70%)"></div>{photo}<div class=logo>PlainStats</div><div class=dots>{dots}</div>{body}<div class=foot><span>{foot}</span><b>plainstatsnfl.com</b></div></body></html>'
def photo(left,top,w,h,pos='center top',zoom=None):
    return f'<div class=abs style="left:{left}px;top:{top}px;width:{w}px;height:{h}px;background:url(file://{PH}) {pos}/{zoom or "cover"}"></div>'
D=DATA; S=[]
# 1 cover
ph=photo(0,0,1080,1350)+'<div class=abs style="inset:0;background:linear-gradient(180deg,rgba(7,16,31,.55) 0,rgba(7,16,31,0) 22%,rgba(7,16,31,0) 48%,rgba(5,10,22,.96) 80%)"></div><div class=abs style="inset:0;background:linear-gradient(115deg,rgba(29,79,214,.28),rgba(29,79,214,0) 60%)"></div>'
body='<div class=eyebrow style="top:870px">Colts are open to trading him</div><h1 style="top:915px;font-size:94px">Jonathan Taylor: <em>top 3</em> trade destinations</h1>'
S.append(shell(0,'IND',body,ph))
# 2 situation
t=D['taylor']; P2=f'{HERE}/img/jonathan-taylor-2.jpg'
def tile(x,y,n,l,w=420): return f'<div class="abs tile" style="left:{x}px;top:{y}px;width:{w}px;z-index:8"><div class=big style="font-size:66px">{n}</div><div class=lab style="margin-top:6px;font-size:24px">{l}</div></div>'
ph=f'<div class=abs style="left:520px;top:400px;width:488px;height:690px;border-radius:36px;background:url(file://{P2}) center top/cover;border:2px solid rgba(255,255,255,.25);box-shadow:0 30px 60px rgba(0,0,0,.5);z-index:3"></div><div class=abs style="inset:0;background:radial-gradient(800px 800px at 80% 50%,rgba(29,79,214,.45),transparent 70%)"></div>'
body=f'<div class=eyebrow style="top:150px">Jonathan Taylor, through Week 8</div><h1 style="top:190px;font-size:88px">Colts are {D["IND"]["rec"]} and <em>listening</em></h1>'
body+=tile(72,420,t['yds'],f'Rush yards, {t["yds_rk"]} in the NFL')+tile(72,585,t['td'],f'Rush TD, {t["td_rk"]}')+tile(72,750,t['car'],f'Carries, {t["car_rk"]}')+tile(72,915,t['recyds'],f'Receiving yards on {t["rec"]} catches')
body+=f'<div class="abs lab" style="left:72px;right:72px;top:1130px;z-index:8;font-size:26px">Week 8: {t["w8"]} in a {D["IND"]["w8"]}. Playoff odds: {D["IND"]["po"]}.</div>'
S.append(shell(1,'IND',body,ph,'Photo: Creative Commons BY 3.0 Unported'))
# 3-5 teams
def team(i,key,rank,pos,zoom,shift):
    d=D[key]; c,deep,a=TH[key]; lg=f'{HERE}/img/logos/{key.lower()}.png'
    ph=f'<div class=abs style="inset:0;background:radial-gradient(900px 900px at 80% 38%,{c}cc,transparent 70%),linear-gradient(115deg,{deep},#070f20 85%)"></div>'
    ph+=f'<div class=abs style="left:300px;top:150px;width:1000px;height:1000px;background:url(file://{lg}) center/contain no-repeat;opacity:.12"></div>'
    ph+=f'<div class=abs style="left:520px;top:330px;width:500px;height:500px;background:url(file://{lg}) center/contain no-repeat;filter:drop-shadow(0 18px 40px rgba(0,0,0,.5));z-index:2"></div>'
    def row(y,n,l,sub=''): return f'<div class=abs style="left:72px;top:{y}px;width:470px;z-index:8"><div class=big style="font-size:72px;color:{"var(--a)" if n==d["po"] else "#fff"}">{n}</div><div class=lab style="margin-top:6px">{l}</div></div>'
    body=f'<div class=abs style="left:72px;top:165px;z-index:9"><span class=chip>#{rank} · fit {d["fit"]}</span></div><h1 style="top:225px;font-size:112px">{d["name"]}</h1>'
    body+=f'<div class=abs lab style="left:72px;top:350px;width:470px;z-index:9;font-size:26px">{d["rec"]} · {d["last"]}</div>'
    body+=row(450,d['po'],'Playoff odds')+row(600,d['rk'],f'Run-game need (league rank)<br>RB rush EPA per carry {d["epa"]}')+row(790,d['space'],'Cap space (PlainStats team total)')
    body+=f'<div class="abs lab" style="left:72px;right:72px;top:1010px;z-index:8;font-size:28px;color:#fff"><b style="font-weight:800">Lead RB:</b> {d["lead"]}</div><div class="abs lab" style="left:72px;right:72px;top:1060px;z-index:8;font-size:26px">{d["tag"]}</div>'
    return shell(i,key,body,ph)
S.append(team(2,'MIN',1,'','',880))
S.append(team(3,'SEA',2,'','',960))
S.append(team(4,'NYG',3,'','',1040))
# 6 summary
ph=photo(0,0,1080,1350)+'<div class=abs style="inset:0;background:linear-gradient(180deg,rgba(7,16,31,.9),rgba(7,16,31,.8) 40%,rgba(7,16,31,.94))"></div>'
rows=''
for k,key in enumerate(['MIN','SEA','NYG']):
    d=D[key]
    rows+=f'<div class=tile style="display:grid;grid-template-columns:96px 1fr 120px;align-items:center;gap:12px;margin-bottom:18px"><div style="width:84px;height:84px;background:url(file://{HERE}/img/logos/{key.lower()}.png) center/contain no-repeat"></div><div><div style="font-size:42px;font-weight:800;letter-spacing:-.03em">{d["name"]}</div><div class=lab style="font-size:24px">{d["rec"]} · {d["po"]} playoff · run game {d["rk"]} · {d["space"]} space</div></div><div style="text-align:right"><div class=big style="font-size:60px">{d["fit"]}</div><div class=lab style="font-size:22px">fit score</div></div></div>'
body=f'<div class=eyebrow style="top:150px">How the three stack up</div><h1 style="top:190px;font-size:88px">Minnesota is the <em>best fit</em> on paper</h1><div class=abs style="left:72px;right:72px;top:470px;z-index:9">{rows}</div>'
body+=f'<div class="abs lab" style="left:72px;right:72px;top:1050px;z-index:9;font-size:26px">Fit score = run-game need and playoff odds, averaged (0-100). The {D["next"]} score above the Giants on our numbers but have not been linked to him. Taylor averages $22M a year (NFL.com). All three teams have less cap space than that, and his 2026 cap hit is not in our data, so salary may have to go back to Indianapolis.</div>'
S.append(shell(5,'MIN',body,ph))
# 7 closer
ph=photo(0,250,1080,1100)+'<div class=abs style="left:0;right:0;top:0;height:640px;background:linear-gradient(180deg,#07101f 0,#07101f 48%,rgba(7,16,31,0))"></div><div class=abs style="left:0;right:0;top:760px;height:590px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.95) 60%)"></div>'
body='<div class=eyebrow style="top:150px">Where should Taylor land?</div><h1 style="top:190px;font-size:104px">Vikings, Seahawks or <em>Giants?</em></h1><div class="abs lab" style="left:72px;right:72px;top:1130px;z-index:9;font-size:28px;color:#fff">Reported interest: Giants and Vikings (Pro Football Rumors, Oct 31). Seattle is our data pick.</div>'
S.append(shell(6,'IND',body,ph,'Photos: All-Pro Reels (CC BY-SA 2.0), CC BY 3.0'))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--no-sandbox']); pg=b.new_page(viewport={'width':1080,'height':1350})
    for i,h in enumerate(S,1):
        f=f'{OUT}/slide{i}.html'; open(f,'w').write(h); pg.goto(f'file://{f}'); pg.wait_for_timeout(300); pg.screenshot(path=f'{OUT}/slide{i}.png')
    b.close()
