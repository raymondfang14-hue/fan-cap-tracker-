import sys, os, glob
from playwright.sync_api import sync_playwright
F='/home/user/fan-cap-tracker-/assets/fonts/'; HERE=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]
COL={'BUF':'#1a56d6','BAL':'#5b3fd0','MIN':'#7a43c8','DET':'#1e9be0','KC':'#e8213f','DEN':'#fb4f14'}
DEEP={'BUF':'#0a2a6e','BAL':'#1b1260','MIN':'#3a1d6b','DET':'#0a4f7e','KC':'#7a0f21','DEN':'#0b2a52'}
ACC={'BUF':'#ff4a63','BAL':'#e0b84a','MIN':'#ffc62f','DET':'#dfe5ea','KC':'#ffb81c','DEN':'#fb4f14'}
BRAND='#f26a2e'
N=8
# star per team: slug, display name, number-free stat line, team
P={'BUF':('josh-allen','Josh Allen','QB','1,504 pass yds · 8 rush TD'),
   'BAL':('lamar-jackson','Lamar Jackson','QB','10.1 yds per attempt'),
   'MIN':('justin-jefferson','Justin Jefferson','WR','302 yds · 23 catches'),
   'DET':('jared-goff','Jared Goff','QB','1,788 pass yds · 14 TD'),
   'KC':('patrick-mahomes','Patrick Mahomes','QB','1,474 pass yds · 9 TD'),
   'DEN':('patrick-surtain','Patrick Surtain II','CB','9 catches allowed on 18 targets')}
def photo(slug):
    for e in ('jpg','jpeg','png','webp'):
        p=f'{HERE}/img/{slug}.{e}'
        if os.path.exists(p): return p
USED=[]
CSS=f"""
@font-face{{font-family:I;font-weight:800;src:url('file://{F}Inter-ExtraBold.otf')}}
@font-face{{font-family:I;font-weight:600;src:url('file://{F}Inter-SemiBold.otf')}}
*{{box-sizing:border-box;margin:0}}
body{{width:1080px;height:1350px;font-family:I,sans-serif;color:#fff;position:relative;overflow:hidden;background:#07101f}}
.bg{{position:absolute;inset:0}}
.logo{{position:absolute;left:72px;top:64px;font-size:34px;font-weight:800;letter-spacing:-.02em;z-index:5}}
.logo b{{color:#f26a2e}}
.dots{{position:absolute;right:72px;top:78px;display:flex;gap:14px;z-index:5}}
.dots i{{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.25)}} .dots i.on{{background:var(--a)}}
.eyebrow{{position:absolute;left:72px;top:160px;font-size:28px;font-weight:600;color:#c3cfe4;z-index:5}}
h1{{position:absolute;left:72px;top:205px;width:936px;font-size:104px;line-height:1;font-weight:800;letter-spacing:-.04em;z-index:5}}
h1 em{{font-style:normal;color:var(--a)}}
.foot{{position:absolute;left:72px;right:72px;bottom:52px;display:flex;justify-content:space-between;font-size:24px;font-weight:600;color:#aebbd3;z-index:5}}
.foot b{{color:#fff;font-weight:800;font-size:27px}}
.card{{position:absolute;border-radius:36px;overflow:hidden;border:2px solid rgba(255,255,255,.18);box-shadow:0 30px 60px rgba(0,0,0,.45)}}
.card .ph{{position:absolute;inset:0;background-size:cover;background-position:center top}}
.card .mono{{position:absolute;inset:0;display:grid;place-items:center;font-size:330px;font-weight:800;letter-spacing:-.06em;color:rgba(255,255,255,.22)}}
.card .shade{{position:absolute;left:0;right:0;bottom:0;height:55%;background:linear-gradient(180deg,transparent,rgba(5,10,22,.92))}}
.card .tag{{position:absolute;left:0;right:0;bottom:0;padding:0 28px 26px}}
.card .tag .n{{font-size:42px;font-weight:800;letter-spacing:-.025em;line-height:1.05}}
.card .tag .s{{font-size:25px;font-weight:600;color:#cfd9ec;margin-top:6px}}
.chip{{position:absolute;left:22px;top:22px;padding:9px 18px;border-radius:999px;font-size:25px;font-weight:800;color:#fff;background:rgba(5,10,22,.55);border:2px solid rgba(255,255,255,.5)}}
.big{{font-weight:800;letter-spacing:-.05em;line-height:.9}}
.h2h{{position:absolute;left:72px;right:72px}}
.r{{display:grid;grid-template-columns:1fr 250px 1fr;align-items:center;padding:20px 0;border-top:1px solid rgba(255,255,255,.14)}}
.r:first-child{{border-top:0}}
.r .lab{{text-align:center;font-size:25px;font-weight:600;color:#aebbd3;line-height:1.2}}
.r .v{{font-size:76px;font-weight:800;letter-spacing:-.045em;color:#6f819f}}
.r .v.w{{color:var(--a)}}
.r .v:last-child{{text-align:right}}
.note{{position:absolute;left:72px;right:72px;font-size:31px;line-height:1.35;font-weight:600;color:#c3cfe4;z-index:5}}
.hd{{display:flex;justify-content:space-between;align-items:center}}
.hd .t{{display:flex;align-items:center;gap:18px;font-size:44px;font-weight:800;letter-spacing:-.03em}}
.dot{{width:30px;height:30px;border-radius:50%}}
"""
def shell(i,away,home,body,foot,acc=BRAND):
    dots=''.join(f'<i class="{"on" if k==i else ""}"></i>' for k in range(N))
    bg=f'<div class=bg style="background:radial-gradient(760px 760px at 0% 100%,{COL[away]}88,transparent 70%),radial-gradient(760px 760px at 100% 100%,{COL[home]}88,transparent 70%),linear-gradient(115deg,{DEEP[away]} 0%,#070f20 52%,{DEEP[home]} 100%)"></div>' if away else '<div class=bg style="background:radial-gradient(900px 600px at 100% 0,rgba(242,106,46,.4),transparent 70%),radial-gradient(800px 700px at 0% 100%,rgba(30,100,220,.35),transparent 70%),linear-gradient(180deg,#10264a,#060d1c)"></div>'
    return f'<html><head><meta charset=utf-8><style>:root{{--a:{acc}}}{CSS}</style></head><body>{bg}<div class=logo>Plain<b>Stats</b></div><div class=dots>{dots}</div>{body}<div class=foot><span>{foot}</span><b>plainstatsnfl.com</b></div></body></html>'
def card(t,x,y,w,h):
    slug,name,pos,stat=P[t]; ph=photo(slug)
    inner=f'<div class=ph style="background-image:url(file://{ph})"></div>' if ph else f'<div class=mono>{name.split()[-1][0]}</div>'
    if ph: USED.append(slug)
    return f'<div class=card style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:linear-gradient(160deg,{COL[t]},#0b1630 85%)">{inner}<div class=shade></div><div class=chip>{t}</div><div class=tag><div class=n>{name}</div><div class=s>{stat}</div></div></div>'
def hero(i,away,home,eyebrow,h,pct_team,pct,sub,pick):
    body=f'<div class=eyebrow style="top:150px">{eyebrow}</div><h1 style="font-size:92px;top:190px">{h}</h1>'+card(away,72,410,462,660)+card(home,546,410,462,660)
    body+=f'<div style="position:absolute;left:72px;top:1090px;z-index:5;display:flex;align-items:flex-end;gap:24px"><div class=big style="font-size:112px;color:var(--a)">{pct}%</div><div style="font-size:28px;font-weight:600;color:#c3cfe4;line-height:1.25;padding-bottom:6px">{pct_team} win chance<br>{sub}</div></div>'
    return shell(i,away,home,body,'PlainStats Elo model · nflverse · NFL injury reports',ACC[pick])
def h2h(i,away,home,eyebrow,h,rows,note,pick):
    r=''
    for lab,a,b,win in rows:
        ca=f' style="color:{ACC[away]}"' if win=='a' else ''; cb=f' style="color:{ACC[home]}"' if win=='h' else ''
        r+=f'<div class=r><div class=v{ca}>{a}</div><div class=lab>{lab}</div><div class=v{cb}>{b}</div></div>'
    hdr=f'<div class="h2h hd" style="top:455px;z-index:5"><div class=t><span class=dot style="background:{COL[away]}"></span>{away}</div><div class=t>{home}<span class=dot style="background:{COL[home]}"></span></div></div>'
    body=f'<div class=eyebrow>{eyebrow}</div><h1>{h}</h1>{hdr}<div class=h2h style="top:520px;z-index:5">{r}</div><div class=note style="top:1130px;font-size:29px">{note}</div>'
    return shell(i,away,home,body,'PlainStats · nflverse through Week 7 · team color = edge',ACC[pick])
S=[]
# cover
def band(a,b,txt,sub,y):
    c=lambda t:f'<div class=card style="position:relative;left:0;top:0;width:170px;height:170px;border-radius:85px;flex:none;background:linear-gradient(160deg,{COL[t]},#0b1630 90%)">'+(f'<div class=ph style="background-image:url(file://{photo(P[t][0])})"></div>' if photo(P[t][0]) else f'<div class=mono style="font-size:125px">{P[t][1].split()[-1][0]}</div>')+'</div>'
    return f'<div style="position:absolute;left:72px;right:72px;top:{y}px;height:210px;border-radius:40px;background:rgba(10,22,48,.62);border:1px solid rgba(255,255,255,.16);display:flex;align-items:center;gap:0;padding:0 28px;z-index:5">{c(a)}<div style="margin-left:-34px">{c(b)}</div><div style="margin-left:34px"><div class=big style="font-size:62px;letter-spacing:-.04em;line-height:1">{txt}</div><div style="font-size:28px;font-weight:600;color:#c3cfe4;margin-top:10px">{sub}</div></div></div>'
cov='<div class=eyebrow>PlainStats model</div><h1 style="font-size:150px;top:195px;line-height:.92">Week 8<br><em>picks</em></h1>'
cov+=band('BAL','BUF','Bills 72%','Ravens at Bills',525)+band('MIN','DET','Vikings 55%','Vikings at Lions',760)+band('KC','DEN','Broncos 63%','Chiefs at Broncos',995)
S.append(shell(0,None,None,cov,'PlainStats Elo model · nflverse'))
S.append(hero(1,'BAL','BUF','Baltimore at Buffalo','Bills are the <em>safe pick</em>','Bills','72','Predicted 29-22','BUF'))
S.append(h2h(2,'BAL','BUF','Head to head','Closer than <em>72%</em> sounds',[('Points per game','24.1','32.8','h'),('QB EPA per play','+0.346','+0.314','a'),('Pass D, EPA allowed','+0.076','+0.215','a'),('Run-block win rate','40.3%','51.0%','h')],'Lamar is more efficient but has played 4 of 7 games. Buffalo gets the edge from home field and results (Elo rank 2nd vs 15th).','BUF'))
S.append(hero(3,'MIN','DET','Minnesota at Detroit','A coin flip. <em>Slight</em> Vikings','Vikings','55','Predicted 24-22','MIN'))
S.append(h2h(4,'MIN','DET','Head to head','Defense vs <em>offense</em>',[('Points allowed per game','12.3','27.5','a'),('Pass offense EPA','-0.073','+0.295','h'),('Pass D, EPA allowed','-0.252','+0.206','a'),('Net EPA rank','6th','17th','a')],'Minnesota is 6-0 on defense. Detroit has the best pass offense of these six teams and is 3-0 at home.','MIN'))
S.append(hero(5,'KC','DEN','Kansas City at Denver','The pick we <em>trust least</em>','Broncos','63','Predicted 23-20','DEN'))
S.append(h2h(6,'KC','DEN','Head to head','Elo says Denver. <em>EPA says KC.</em>',[('Net EPA per play','+0.174','+0.009','a'),('QB EPA per play','+0.112','-0.052','a'),('Elo rating','1562','1618','h'),('Pass-block win rate','85.2%','89.7%','h')],'Denver leans on rating and home field. Kansas City leads on efficiency and beat Denver 31-10 in Week 1.','KC'))
# closer
cl='<div class=eyebrow>Week 8</div><h1 style="font-size:130px;top:195px">Who are <em>you</em> taking?</h1>'
for k,(t,txt) in enumerate([('BUF','Bills 72%'),('MIN','Vikings 55%'),('DEN','Broncos 63%')]):
    cl+=card(t,72+k*322,470,292,560).replace('font-size:330px','font-size:220px').replace('class=tag','class=tag style=display:none')
    cl+=f'<div class=big style="position:absolute;left:{72+k*322}px;top:1050px;width:292px;text-align:center;font-size:44px;letter-spacing:-.03em;z-index:5">{txt.split()[1]}</div><div style="position:absolute;left:{72+k*322}px;top:1100px;width:292px;text-align:center;font-size:28px;font-weight:600;color:#c3cfe4;z-index:5">{txt.split()[0]}</div>'
cl+='<div class=note style="top:1170px;font-size:29px">Picks update after Friday\'s injury report.</div>'
cr=os.path.join(HERE,'img','credits.txt')
S.append(shell(7,'BUF','DEN',cl,('Photos: '+open(cr).read().strip()) if os.path.exists(cr) else 'PlainStats Elo model · nflverse · NFL injury reports'))
credit=os.path.join(HERE,'img','credits.txt')
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--no-sandbox']); pg=b.new_page(viewport={'width':1080,'height':1350})
    for i,h in enumerate(S,1):
        if os.path.exists(credit): h=h.replace('PlainStats Elo model · nflverse · NFL injury reports','Photos: '+open(credit).read().strip()[:70]) if False else h
        f=f'{OUT}/slide{i}.html'; open(f,'w').write(h); pg.goto(f'file://{f}'); pg.wait_for_timeout(300); pg.screenshot(path=f'{OUT}/slide{i}.png')
    b.close()
print('photos used:',sorted(set(USED)))
