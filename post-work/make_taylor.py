import sys, os, json
from playwright.sync_api import sync_playwright
F='/home/user/fan-cap-tracker-/assets/fonts/'; HERE=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]
PH=f'{HERE}/img/jonathan-taylor.jpg'; N=7; TT=len(sys.argv)>2 and sys.argv[2]=='tiktok'
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
    bgd=f'<div class=abs style="inset:0;background:linear-gradient(115deg,{d},#070f20 70%)"></div>'
    foot_html=f'<div class=foot><span>{foot}</span><b>plainstatsnfl.com</b></div>'
    if not TT:
        return f'<html><head><meta charset=utf-8><style>:root{{--a:{a}}}{CSS}</style></head><body>{bgd}{photo}<div class=logo>PlainStats</div><div class=dots>{dots}</div>{body}{foot_html}</body></html>'
    import re
    m=re.search(r"url\(file://([^)]*jonathan-taylor[^)]*)\)",photo)
    fill=f'<div class=abs style="inset:0;background:linear-gradient(115deg,{d},#070f20 70%)"></div>'
    if m: fill+=f'<div class=abs style="inset:-80px;background:url(file://{m.group(1)}) center/cover;filter:blur(40px) brightness(.5) saturate(1.1)"></div>'
    mask='mask-image:linear-gradient(180deg,transparent 0,#000 150px,#000 1200px,transparent 1350px);-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 150px,#000 1200px,transparent 1350px)'
    return f'<html><head><meta charset=utf-8><style>:root{{--a:{a}}}{CSS}body{{height:1920px}}.stage{{position:absolute;left:21px;top:150px;width:1080px;height:1350px;transform:scale(.96);transform-origin:0 0}}</style></head><body>{fill}<div class=stage><div class=abs style="inset:0;{mask}">{bgd}{photo}</div><div class=logo>PlainStats</div><div class=dots>{dots}</div>{body}{foot_html}</div></body></html>'

def photo(left,top,w,h,pos='center top',zoom=None):
    return f'<div class=abs style="left:{left}px;top:{top}px;width:{w}px;height:{h}px;background:url(file://{PH}) {pos}/{zoom or "cover"}"></div>'
D=DATA; S=[]
# 1 cover
ph=photo(0,0,1080,1350)+'<div class=abs style="inset:0;background:linear-gradient(180deg,rgba(7,16,31,.55) 0,rgba(7,16,31,0) 22%,rgba(7,16,31,0) 48%,rgba(5,10,22,.96) 80%)"></div><div class=abs style="inset:0;background:linear-gradient(115deg,rgba(29,79,214,.28),rgba(29,79,214,0) 60%)"></div>'
body='<div class=eyebrow style="top:870px">Colts are open to trading him</div><h1 style="top:915px;font-size:94px">Jonathan Taylor: <em>top 3</em> trade destinations</h1>'
S.append(shell(0,'IND',body,ph))
# 2 situation
t=D['taylor']; P3=f'{HERE}/img/jonathan-taylor-3.jpg'
def tile(x,y,n,l,w=454): return f'<div class="abs tile" style="left:{x}px;top:{y}px;width:{w}px;z-index:8"><div class=big style="font-size:70px">{n}</div><div class=lab style="margin-top:6px">{l}</div></div>'
ph=f'<div class=abs style="left:0;top:300px;width:1080px;height:1050px;background:url(file://{P3}) center top/cover"></div><div class=abs style="left:0;right:0;top:0;height:620px;background:linear-gradient(180deg,#07101f 0,#07101f 42%,rgba(7,16,31,0))"></div><div class=abs style="left:0;right:0;top:700px;height:650px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.95) 55%)"></div>'
body=f'<div class=eyebrow style="top:150px">Jonathan Taylor, through Week 8</div><h1 style="top:190px;font-size:88px">Colts are {D["IND"]["rec"]} and <em>listening</em></h1>'
body+=tile(72,830,t['yds'],f'Rush yards, {t["yds_rk"]} in the NFL')+tile(554,830,t['td'],f'Rush TD, {t["td_rk"]}')+tile(72,985,t['car'],f'Carries, {t["car_rk"]}')+tile(554,985,t['recyds'],f'Receiving yards on {t["rec"]} catches')
body+=f'<div class="abs lab" style="left:72px;right:72px;top:1135px;z-index:8;font-size:24px">Week 8: {t["w8"]} in a {D["IND"]["w8"]}. Playoff odds: {D["IND"]["po"]}.</div><div class="abs lab" style="left:72px;right:72px;top:1175px;z-index:8;font-size:24px;color:#fff">Colts reportedly turned down a 2nd plus another pick. Reported ask: a 1st and a DT (Pro Football Rumors, Oct 31).</div>'
S.append(shell(1,'IND',body,ph,'Photo: Creative Commons BY 3.0 Unported'))
# 3-5 teams
def team(i,key,rank,pos,zoom,shift):
    d=D[key]; c,deep,a=TH[key]; lg=f'{HERE}/img/logos/{key.lower()}.png'
    ph=f'<div class=abs style="inset:0;background:radial-gradient(900px 900px at 80% 38%,{c}cc,transparent 70%),linear-gradient(115deg,{deep},#070f20 85%)"></div>'
    ph+=f'<div class=abs style="left:300px;top:150px;width:1000px;height:1000px;background:url(file://{lg}) center/contain no-repeat;opacity:.12"></div>'
    if key=='NYG': ph+='<div class=abs style="left:520px;top:330px;width:500px;height:500px;border-radius:50%;background:rgba(255,255,255,.94);box-shadow:0 18px 50px rgba(0,0,0,.5);z-index:1"></div>'
    ph+=f'<div class=abs style="left:{570 if key=="NYG" else 520}px;top:{380 if key=="NYG" else 330}px;width:{400 if key=="NYG" else 500}px;height:{400 if key=="NYG" else 500}px;background:url(file://{lg}) center/contain no-repeat;filter:drop-shadow(0 18px 40px rgba(0,0,0,.5));z-index:2"></div>'
    def row(y,n,l,sub=''): return f'<div class=abs style="left:72px;top:{y}px;width:470px;z-index:8"><div class=big style="font-size:72px;color:{"var(--a)" if n==d["po"] else "#fff"}">{n}</div><div class=lab style="margin-top:6px">{l}</div></div>'
    body=f'<div class=abs style="left:72px;top:165px;z-index:9"><span class=chip>#{rank} · fit {d["fit"]}</span></div><h1 style="top:225px;font-size:112px">{d["name"]}</h1>'
    body+=f'<div class=abs lab style="left:72px;top:350px;width:470px;z-index:9;font-size:26px">{d["rec"]} · {d["last"]}</div>'
    body+=row(450,d['po'],'Playoff odds')+row(600,d['rk'],f'Run-game need (league rank)<br>RB rush EPA per carry {d["epa"]}')+row(790,d['space'],'Cap space (PlainStats team total)')
    body+=f'<div class="abs lab" style="left:72px;right:72px;top:1010px;z-index:8;font-size:28px;color:#fff"><b style="font-weight:800">Lead RB:</b> {d["lead"]}</div><div class="abs lab" style="left:72px;right:72px;top:1060px;z-index:8;font-size:26px">{d["tag"]}</div>'
    return shell(i,key,body,ph)
SC={'MIN':dict(h='Vikings: a <em>2nd-round pick</em> for Taylor',col=['2027 2nd-round pick','2027 6th-round pick'],
  price='Houston gave up the same, a 2027 2nd and a 2027 6th, for WR Marvin Harrison Jr. on Oct 11.',
  cap='Minnesota has $6.1M of cap space and Taylor averages $22M a year (NFL.com). Aaron Jones ($10M a year through 2026, AP) could go the other way as salary.'),
 'SEA':dict(h='Seahawks: a <em>2028 2nd</em> for Taylor',col=['2028 2nd-round pick','2027 6th-round pick'],
  price='A 2028 second plus a late pick is this year\'s price for a starter: Dallas paid it for CB Joey Porter Jr. (Sep 30). Seattle sent Indianapolis a 2027 3rd and 2028 5th for G Quenton Nelson on Oct 27.',
  cap='Seattle has $12.6M of cap space, the most of the three. RB Emanuel Wilson is on a $1.6M deal (Pro Football Rumors).'),
 'NYG':dict(h='Giants: <em>3rd + 5th</em> as an opening bid',col=['2027 3rd-round pick','2028 5th-round pick'],
  price='Seattle paid exactly that for G Quenton Nelson, who is on an expiring deal (Oct 27). Taylor is signed through 2028, so Indianapolis could ask for more.',
  cap='New York has $8.1M of cap space and already sent its 2027 5th to Minnesota for QB J.J. McCarthy (Sep 28).')}
def scen(i,key,rank):
    d=D[key]; c,deep,a=TH[key]; lg=f'{HERE}/img/logos/{key.lower()}.png'; sc=SC[key]
    ph=f'<div class=abs style="inset:0;background:radial-gradient(900px 900px at 85% 20%,{c}aa,transparent 70%),linear-gradient(115deg,{deep},#070f20 85%)"></div>'
    ph+=f'<div class=abs style="left:480px;top:600px;width:900px;height:900px;background:url(file://{lg}) center/contain no-repeat;opacity:.10"></div>'
    items=''.join(f'<div class=big style="font-size:34px;letter-spacing:-.03em;line-height:1.1;margin-top:14px">{x}</div>' for x in sc['col'])
    left=f'<div class="abs tile" style="left:72px;top:420px;width:444px;height:262px;z-index:8"><div class=lab style="color:var(--a);font-weight:800;font-size:26px">Colts get</div>{items}</div>'
    right=f'<div class="abs tile" style="left:564px;top:420px;width:444px;height:262px;z-index:8"><div class=lab style="color:var(--a);font-weight:800;font-size:26px">{d["name"]} get</div><div class=big style="font-size:34px;letter-spacing:-.03em;line-height:1.1;margin-top:14px">RB Jonathan Taylor</div><div class=lab style="margin-top:14px;font-size:24px">{t["yds"]} rush yds, {t["td"]} TD in 8 games</div></div>'
    arrow='<div class="abs" style="left:516px;top:510px;width:48px;text-align:center;font-size:44px;font-weight:800;z-index:9">⇄</div>'
    pr=f'<div class="abs tile" style="left:72px;right:72px;top:710px;z-index:8"><div class=lab style="color:var(--a);font-weight:800;font-size:24px">Price check</div><div class=lab style="color:#fff;font-size:28px;margin-top:8px">{sc["price"]}</div></div>'
    cp=f'<div class="abs tile" style="left:72px;right:72px;top:965px;z-index:8"><div class=lab style="color:var(--a);font-weight:800;font-size:24px">Cap check</div><div class=lab style="color:#fff;font-size:28px;margin-top:8px">{sc["cap"]}</div></div>'
    body=f'<div class=eyebrow style="top:150px">Trade scenario · #{rank} {d["name"]}</div><h1 style="top:190px;font-size:84px">{sc["h"]}</h1>{left}{right}{arrow}{pr}{cp}<div class="abs lab" style="left:72px;right:72px;top:1180px;z-index:8;font-size:23px">PlainStats scenario built from 2026 trade prices. Not a report.</div>'
    return shell(i,key,body,ph)
CM={'MIN':dict(price='Houston paid the same, a 2027 2nd and 2027 6th, for WR Marvin Harrison Jr. (Oct 11).',note='Aaron Jones ($10M a year through 2026, AP) could go back as salary. Taylor averages $22M a year (NFL.com).'),
 'SEA':dict(price='Dallas paid a 2028 2nd and a late pick for CB Joey Porter Jr. (Sep 30). Seattle sent a 2027 3rd and 2028 5th to Indianapolis for G Quenton Nelson (Oct 27).',note='Most cap space of the three. RB Emanuel Wilson is on a $1.6M deal (Pro Football Rumors).'),
 'NYG':dict(price='Seattle paid that for G Quenton Nelson on an expiring deal (Oct 27). Taylor is signed through 2028, so Indianapolis could ask for more.',note='The Giants already sent their 2027 5th to Minnesota for QB J.J. McCarthy (Sep 28).')}
def combined(i,key,rank):
    d=D[key]; c,deep,a=TH[key]; lg=f'{HERE}/img/logos/{key.lower()}.png'; sc=SC[key]; cm=CM[key]
    ph=f'<div class=abs style="inset:0;background:radial-gradient(900px 900px at 80% 22%,{c}cc,transparent 70%),linear-gradient(115deg,{deep},#070f20 85%)"></div>'
    ph+=f'<div class=abs style="left:360px;top:60px;width:900px;height:900px;background:url(file://{lg}) center/contain no-repeat;opacity:.10"></div>'
    if key=='NYG': ph+='<div class=abs style="left:690px;top:150px;width:310px;height:310px;border-radius:50%;background:rgba(255,255,255,.94);box-shadow:0 18px 50px rgba(0,0,0,.5);z-index:1"></div>'
    ph+=f'<div class=abs style="left:{725 if key=="NYG" else 650}px;top:{185 if key=="NYG" else 150}px;width:{240 if key=="NYG" else 330}px;height:{240 if key=="NYG" else 330}px;background:url(file://{lg}) center/contain no-repeat;filter:drop-shadow(0 14px 30px rgba(0,0,0,.5));z-index:2"></div>'
    def st(x,n,l,col=False): return f'<div class="abs tile" style="left:{x}px;top:500px;width:300px;height:150px;z-index:8;padding:18px 22px"><div class=big style="font-size:50px;color:{"var(--a)" if col else "#fff"}">{n}</div><div class=lab style="margin-top:6px;font-size:21px">{l}</div></div>'
    body=f'<div class=abs style="left:72px;top:150px;z-index:9"><span class=chip>#{rank} · fit {d["fit"]}</span></div><h1 style="top:205px;font-size:100px">{d["name"]}</h1>'
    body+=f'<div class="abs lab" style="left:72px;top:325px;width:520px;z-index:9;font-size:25px">{d["rec"]} · {d["last"]}</div><div class="abs lab" style="left:72px;top:395px;width:520px;z-index:9;font-size:24px;color:#fff"><b style="font-weight:800">Lead RB:</b> {d["lead"].replace(" · ","<br>",1)}</div>'
    body+=st(72,d['po'],'Playoff odds',True)+st(390,d['rk'],f'Run-game need<br>RB EPA {d["epa"]}/carry')+st(708,d['space'],'Cap space<br>(PlainStats team total)')
    items=''.join(f'<div class=big style="font-size:32px;letter-spacing:-.03em;line-height:1.1;margin-top:10px">{x}</div>' for x in sc['col'])
    body+=f'<div class="abs lab" style="left:72px;top:690px;z-index:9;font-size:24px;color:var(--a);font-weight:800">Trade scenario · {d["tag"]}</div>'
    body+=f'<div class="abs tile" style="left:72px;top:735px;width:444px;height:215px;z-index:8;padding:16px 24px"><div class=lab style="color:var(--a);font-weight:800;font-size:24px">Colts get</div>{items}</div>'
    body+=f'<div class="abs tile" style="left:564px;top:735px;width:444px;height:215px;z-index:8;padding:16px 24px"><div class=lab style="color:var(--a);font-weight:800;font-size:24px">{d["name"]} get</div><div class=big style="font-size:32px;letter-spacing:-.03em;line-height:1.1;margin-top:10px">RB Jonathan Taylor</div><div class=lab style="margin-top:10px;font-size:22px">{t["yds"]} rush yds, {t["td"]} TD in 8 games</div></div><div class="abs" style="left:516px;top:815px;width:48px;text-align:center;font-size:40px;font-weight:800;z-index:9">⇄</div>'
    body+=f'<div class="abs lab" style="left:72px;right:72px;top:972px;z-index:8;font-size:24px;color:#fff"><b style="font-weight:800;color:var(--a)">Price check:</b> {cm["price"]}</div><div class="abs lab" style="left:72px;right:72px;top:1118px;z-index:8;font-size:24px;color:#fff"><b style="font-weight:800;color:var(--a)">Cap check:</b> {cm["note"]}</div>'
    body+='<div class="abs lab" style="left:72px;right:72px;top:1214px;z-index:8;font-size:21px">PlainStats scenario built from the reports and 2026 trade prices. Not a report.</div>'
    return shell(i,key,body,ph)
SC['MIN']['col']=['2027 1st-round pick']
SC['SEA']['col']=['2028 1st-round pick']
SC['NYG']['col']=['2027 2nd-round pick','2028 2nd-round pick','DT D.J. Reader']
CM['MIN']=dict(price='The Colts reportedly turned down a 2nd plus another pick (Pelissero, via PFR). A first meets the reported ask minus the DT. Minnesota\'s top D-lineman has 5 pressures, so a pick-only deal is likelier.',note='Minnesota has $6.1M of cap space. PFR reports a buyer owes only the rest of this season\'s salary; his 2027 pay becomes guaranteed in February.')
CM['SEA']=dict(price='A first, since a 2nd plus a pick was turned down (PFR). Seattle sent Indianapolis a 2027 3rd and 2028 5th for G Quenton Nelson on Oct 27. DT Leonard Williams (12 pressures) is their best rusher, so he stays.',note='Seattle has $12.6M of cap space, the most of the three. A buyer owes only the rest of this season\'s salary (PFR).')
CM['NYG']=dict(price='Two seconds are worth about a first, and D.J. Reader (22 tackles, signed through 2027) is the DT the Colts reportedly want (Anderson, via PFR). Giants are a reported front-runner (Jones, The Athletic).',note='New York has $8.1M of cap space. A buyer owes only the rest of this season\'s salary (PFR).')
S.append(combined(2,'MIN',1)); S.append(combined(3,'SEA',2)); S.append(combined(4,'NYG',3))
# 6 summary
ph=photo(0,0,1080,1350)+'<div class=abs style="inset:0;background:linear-gradient(180deg,rgba(7,16,31,.9),rgba(7,16,31,.8) 40%,rgba(7,16,31,.94))"></div>'
rows=''
for k,key in enumerate(['MIN','SEA','NYG']):
    d=D[key]
    rows+=f'<div class=tile style="display:grid;grid-template-columns:96px 1fr 120px;align-items:center;gap:12px;margin-bottom:18px"><div style="width:84px;height:84px;background:url(file://{HERE}/img/logos/{key.lower()}.png) center/contain no-repeat"></div><div><div style="font-size:42px;font-weight:800;letter-spacing:-.03em">{d["name"]}</div><div class=lab style="font-size:24px">{d["rec"]} · {d["po"]} playoff · run game {d["rk"]} · {d["space"]} space</div></div><div style="text-align:right"><div class=big style="font-size:60px">{d["fit"]}</div><div class=lab style="font-size:22px">fit score</div></div></div>'
body=f'<div class=eyebrow style="top:150px">How the three stack up</div><h1 style="top:190px;font-size:88px">Minnesota is the <em>best fit</em> on paper</h1><div class=abs style="left:72px;right:72px;top:470px;z-index:9">{rows}</div>'
body+=f'<div class="abs lab" style="left:72px;right:72px;top:1050px;z-index:9;font-size:26px">Fit score = run-game need and playoff odds, averaged (0-100). The {D["next"]} score above the Giants on our numbers but have not been linked to him. The Colts reportedly turned down a 2nd plus another pick and want a 1st and a DT (Pro Football Rumors, Oct 31), so every scenario here starts at first-round value.</div>'
S.append(shell(5,'MIN',body,ph))
# 7 closer
ph=photo(0,250,1080,1100)+'<div class=abs style="left:0;right:0;top:0;height:640px;background:linear-gradient(180deg,#07101f 0,#07101f 48%,rgba(7,16,31,0))"></div><div class=abs style="left:0;right:0;top:760px;height:590px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.95) 60%)"></div>'
body='<div class=eyebrow style="top:150px">Where should Taylor land?</div><h1 style="top:190px;font-size:104px">Vikings, Seahawks or <em>Giants?</em></h1><div class="abs lab" style="left:72px;right:72px;top:1130px;z-index:9;font-size:28px;color:#fff">Reported interest: Giants and Vikings (Pro Football Rumors, Oct 31). Seattle is our data pick.</div>'
S.append(shell(6,'IND',body,ph,'Photos: All-Pro Reels (CC BY-SA 2.0), CC BY 3.0'))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--no-sandbox']); pg=b.new_page(viewport={'width':1080,'height':1920 if TT else 1350})
    for i,h in enumerate(S,1):
        f=f'{OUT}/slide{i}.html'; open(f,'w').write(h); pg.goto(f'file://{f}'); pg.wait_for_timeout(300); pg.screenshot(path=f'{OUT}/slide{i}.png')
    b.close()
