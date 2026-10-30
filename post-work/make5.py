import sys, os
from PIL import Image
from playwright.sync_api import sync_playwright
F='/home/user/fan-cap-tracker-/assets/fonts/'; HERE=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]
COL={'BUF':'#1a56d6','BAL':'#5b3fd0','MIN':'#7a43c8','DET':'#1e9be0','KC':'#e8213f','DEN':'#fb4f14'}
DEEP={'BUF':'#0a2a6e','BAL':'#1b1260','MIN':'#3a1d6b','DET':'#0a4f7e','KC':'#7a0f21','DEN':'#0b2a52'}
ACC={'BUF':'#ff4a63','BAL':'#e0b84a','MIN':'#ffc62f','DET':'#dfe5ea','KC':'#ffb81c','DEN':'#fb4f14'}
BRAND='#f26a2e'; N=8
P={'BUF':('josh-allen','Josh Allen','1,504 pass yds · 8 rush TD',.55),
   'BAL':('lamar-jackson','Lamar Jackson','10.1 yds per attempt',.48),
   'MIN':('justin-jefferson','Justin Jefferson','302 yds · 23 catches',.50),
   'DET':('jared-goff','Jared Goff','1,788 pass yds · 14 TD',.56),
   'KC':('patrick-mahomes','Patrick Mahomes','1,474 pass yds · 9 TD',.40),
   'DEN':('patrick-surtain','Patrick Surtain II','9 catches allowed on 18 targets',.52)}
def path(t): return f'{HERE}/img/{P[t][0]}.jpg'
def bgcss(t,bw,bh,cx):
    im=Image.open(path(t)); a=im.width/im.height; w=a*bh
    if w<bw: return f'background:url(file://{path(t)}) center top/cover'
    off=max(bw-w,min(0,cx-P[t][3]*w))
    return f'background:url(file://{path(t)}) {off:.0f}px 0/auto 100% no-repeat'
CSS=f"""
@font-face{{font-family:I;font-weight:800;src:url('file://{F}Inter-ExtraBold.otf')}}
@font-face{{font-family:I;font-weight:600;src:url('file://{F}Inter-SemiBold.otf')}}
*{{box-sizing:border-box;margin:0}}
body{{width:1080px;height:1350px;font-family:I,sans-serif;color:#fff;position:relative;overflow:hidden;background:#07101f}}
.abs{{position:absolute}}
.logo{{position:absolute;left:72px;top:54px;font-size:30px;font-weight:800;letter-spacing:-.02em;z-index:9;background:#fff;color:#000;padding:8px 20px 9px;border-radius:999px}}
.dots{{position:absolute;right:72px;top:78px;display:flex;gap:14px;z-index:9}}
.dots i{{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.35)}} .dots i.on{{background:#fff}}
.eyebrow{{position:absolute;left:72px;top:150px;font-size:28px;font-weight:600;color:#d5deee;z-index:9}}
h1{{position:absolute;left:72px;top:190px;width:936px;font-size:88px;line-height:1;font-weight:800;letter-spacing:-.04em;z-index:9;text-shadow:0 2px 24px rgba(0,0,0,.5)}}
h1 em{{font-style:normal;color:var(--a)}}
.foot{{position:absolute;left:72px;right:72px;bottom:52px;display:flex;justify-content:space-between;font-size:24px;font-weight:600;color:#d5deee;z-index:9}}
.foot b{{color:#fff;font-weight:800;font-size:27px}}
.big{{font-weight:800;letter-spacing:-.05em;line-height:.9}}
.chip{{display:inline-block;padding:7px 16px;border-radius:999px;font-size:24px;font-weight:800;color:#fff;background:rgba(5,10,22,.6);border:2px solid rgba(255,255,255,.6);margin-bottom:10px}}
.nm{{font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1.05;text-shadow:0 2px 18px rgba(0,0,0,.6)}}
.st{{font-size:25px;font-weight:600;color:#e1e8f5;margin-top:6px;text-shadow:0 2px 14px rgba(0,0,0,.6)}}
.h2h{{position:absolute;left:72px;right:72px}}
.r{{display:grid;grid-template-columns:1fr 250px 1fr;align-items:center;padding:20px 0;border-top:1px solid rgba(255,255,255,.2)}}
.r:first-child{{border-top:0}}
.r .lab{{text-align:center;font-size:25px;font-weight:600;color:#d5deee;line-height:1.2}}
.r .v{{text-shadow:0 2px 18px rgba(0,0,0,.65);font-size:76px;font-weight:800;letter-spacing:-.045em;color:#aab9d3}}
.r .v:last-child{{text-align:right}}
.note{{position:absolute;left:72px;right:72px;font-size:29px;line-height:1.35;font-weight:600;color:#e1e8f5;z-index:9}}
.hd{{display:flex;justify-content:space-between;align-items:center}}
.hd .t{{display:flex;align-items:center;gap:18px;font-size:44px;font-weight:800;letter-spacing:-.03em}}
.dot{{width:30px;height:30px;border-radius:50%}}
"""
def shell(i,away,home,body,foot,acc=BRAND,photos=''):
    dots=''.join(f'<i class="{"on" if k==i else ""}"></i>' for k in range(N))
    if away: bg=f'<div class=abs style="inset:0;background:radial-gradient(760px 760px at 0% 100%,{COL[away]}88,transparent 70%),radial-gradient(760px 760px at 100% 100%,{COL[home]}88,transparent 70%),linear-gradient(115deg,{DEEP[away]} 0%,#070f20 52%,{DEEP[home]} 100%)"></div>'
    else: bg='<div class=abs style="inset:0;background:linear-gradient(180deg,#10264a,#060d1c)"></div>'
    return f'<html><head><meta charset=utf-8><style>:root{{--a:{acc}}}{CSS}</style></head><body>{bg}{photos}<div class=logo>PlainStats</div><div class=dots>{dots}</div>{body}<div class=foot><span>{foot}</span><b>plainstatsnfl.com</b></div></body></html>'
def split(away,home,top,h):
    L=f'<div class=abs style="left:0;top:{top}px;width:700px;height:{h}px;clip-path:polygon(0 0,100% 0,80% 100%,0 100%);{bgcss(away,700,h,330)}"></div>'
    R=f'<div class=abs style="left:380px;top:{top}px;width:700px;height:{h}px;clip-path:polygon(47.14% 0,100% 0,100% 100%,27.14% 100%);{bgcss(home,700,h,500)}"></div>'
    return L+R
def hero(i,away,home,eyebrow,h,pct_team,pct,sub,pick):
    ph=split(away,home,330,1020)
    ph+='<div class=abs style="left:0;right:0;top:0;height:640px;background:linear-gradient(180deg,#07101f 0,#07101f 50%,rgba(7,16,31,0) 100%)"></div>'
    ph+='<div class=abs style="left:0;right:0;top:820px;height:530px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.92) 62%)"></div>'
    def who(t,x): 
        _,n,s,_c=P[t]; return f'<div class=abs style="left:{x}px;top:960px;width:430px;z-index:8"><span class=chip>{t}</span><div class=nm>{n}</div><div class=st>{s}</div></div>'
    body=f'<div class=eyebrow>{eyebrow}</div><h1>{h}</h1>'+who(away,72)+who(home,574)
    body+=f'<div class=abs style="left:72px;top:1115px;z-index:8;display:flex;align-items:flex-end;gap:24px"><div class=big style="font-size:112px;color:var(--a)">{pct}%</div><div style="font-size:28px;font-weight:600;color:#e1e8f5;line-height:1.25;padding-bottom:6px">{pct_team} win chance<br>{sub}</div></div>'
    return shell(i,away,home,body,'PlainStats Elo model · nflverse · NFL injury reports',ACC[pick],ph)
def h2h(i,away,home,eyebrow,h,rows,note,pick):
    ph=split(away,home,0,1350)+'<div class=abs style="inset:0;background:linear-gradient(180deg,rgba(6,12,28,.82),rgba(6,12,28,.56) 45%,rgba(6,12,28,.88))"></div>'
    r=''
    for lab,a,b,win in rows:
        ca=f' style="color:{ACC[away]}"' if win=='a' else ''; cb=f' style="color:{ACC[home]}"' if win=='h' else ''
        r+=f'<div class=r><div class=v{ca}>{a}</div><div class=lab>{lab}</div><div class=v{cb}>{b}</div></div>'
    hdr=f'<div class="h2h hd" style="top:455px;z-index:9"><div class=t><span class=dot style="background:{COL[away]}"></span>{away}</div><div class=t>{home}<span class=dot style="background:{COL[home]}"></span></div></div>'
    body=f'<div class=eyebrow>{eyebrow}</div><h1>{h}</h1>{hdr}<div class=h2h style="top:520px;z-index:9">{r}</div><div class=note style="top:1130px">{note}</div>'
    return shell(i,away,home,body,'PlainStats · nflverse through Week 7 · team color = edge',ACC[pick],ph)
S=[]
# cover: six photos in three rows
rows=[('BAL','BUF','Bills 72%','Ravens at Bills'),('MIN','DET','Vikings 55%','Vikings at Lions'),('KC','DEN','Broncos 63%','Chiefs at Broncos')]
ph=''
for k,(a,b,t,s) in enumerate(rows):
    y=320+k*308
    for t2,x in ((a,0),(b,540)):
        pos='center 22%' if t2=='KC' else 'center top'
        ph+=f'<div class=abs style="left:{x}px;top:{y}px;width:540px;height:300px;background:url(file://{path(t2)}) {pos}/cover"></div>'
    ph+=f'<div class=abs style="left:0;right:0;top:{y+130}px;height:170px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.9))"></div>'
    ph+=f'<div class=abs style="left:72px;top:{y+226}px;z-index:8"><span style="font-size:48px;font-weight:800;letter-spacing:-.03em">{t}</span> <span style="font-size:26px;font-weight:600;color:#d5deee;margin-left:12px">{s}</span></div>'
ph+='<div class=abs style="left:0;right:0;top:0;height:420px;background:linear-gradient(180deg,#07101f 0,#07101f 60%,rgba(7,16,31,0))"></div><div class=abs style="left:0;right:0;bottom:0;height:130px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.95))"></div>'
body='<div class=eyebrow>PlainStats model</div><h1 style="font-size:124px;top:182px;line-height:.95">Week 8 <em>picks</em></h1>'
S.append(shell(0,None,None,body,'PlainStats Elo model · nflverse · NFL injury reports',BRAND,ph))
S.append(hero(1,'BAL','BUF','Baltimore at Buffalo','Bills are the <em>safe pick</em>','Bills','72','Predicted 29-22','BUF'))
S.append(h2h(2,'BAL','BUF','Head to head','Closer than <em>72%</em> sounds',[('Points per game','24.1','32.8','h'),('QB EPA per play','+0.346','+0.314','a'),('Pass D, EPA allowed','+0.076','+0.215','a'),('Run-block win rate','40.3%','51.0%','h')],'Lamar is more efficient but has played 4 of 7 games. Buffalo gets the edge from home field and results (Elo rank 2nd vs 15th).','BUF'))
S.append(hero(3,'MIN','DET','Minnesota at Detroit','A coin flip. <em>Slight</em> Vikings','Vikings','55','Predicted 24-22','MIN'))
S.append(h2h(4,'MIN','DET','Head to head','Defense vs <em>offense</em>',[('Points allowed per game','12.3','27.5','a'),('Pass offense EPA','-0.073','+0.295','h'),('Pass D, EPA allowed','-0.252','+0.206','a'),('Net EPA rank','6th','17th','a')],'Minnesota is 6-0 on defense. Detroit has the best pass offense of these six teams and is 3-0 at home.','MIN'))
S.append(hero(5,'KC','DEN','Kansas City at Denver','The pick we <em>trust least</em>','Broncos','63','Predicted 23-20','DEN'))
S.append(h2h(6,'KC','DEN','Head to head','Elo says Denver. <em>EPA says KC.</em>',[('Net EPA per play','+0.174','+0.009','a'),('QB EPA per play','+0.112','-0.052','a'),('Elo rating','1562','1618','h'),('Pass-block win rate','85.2%','89.7%','h')],'Denver leans on rating and home field. Kansas City leads on efficiency and beat Denver 31-10 in Week 1.','KC'))
# closer: three full-height panels
ph=''
for k,t in enumerate(['BUF','MIN','DEN']):
    ph+=f'<div class=abs style="left:{k*360}px;top:400px;width:352px;height:950px;{bgcss(t,352,950,176)}"></div>'
ph+='<div class=abs style="left:0;right:0;top:0;height:560px;background:linear-gradient(180deg,#07101f 0,#07101f 62%,rgba(7,16,31,0))"></div><div class=abs style="left:0;right:0;top:880px;height:470px;background:linear-gradient(180deg,rgba(5,10,22,0),rgba(5,10,22,.94) 70%)"></div>'
for k,(t,n,p) in enumerate([('BUF','Bills','72%'),('MIN','Vikings','55%'),('DEN','Broncos','63%')]):
    ph+=f'<div class=abs style="left:{k*360+36}px;top:1040px;z-index:8"><div class=big style="font-size:84px;color:{ACC[t]}">{p}</div><div style="font-size:32px;font-weight:800;margin-top:8px">{n}</div></div>'
body='<div class=eyebrow>Week 8 · picks update after Friday\'s injury report</div><h1 style="font-size:104px;top:190px">Who are <em>you</em> taking?</h1>'
cr=open(f'{HERE}/img/credits.txt').read().strip()
S.append(shell(7,'BUF','DEN',body,'Photos: '+cr,BRAND,ph))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--no-sandbox']); pg=b.new_page(viewport={'width':1080,'height':1350})
    for i,h in enumerate(S,1):
        f=f'{OUT}/slide{i}.html'; open(f,'w').write(h); pg.goto(f'file://{f}'); pg.wait_for_timeout(300); pg.screenshot(path=f'{OUT}/slide{i}.png')
    b.close()
