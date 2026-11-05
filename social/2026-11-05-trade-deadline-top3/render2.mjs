// Trade deadline carousel, team-logo design: node render2.mjs slides2.json outdir
import pw from '/opt/node-tools/node_modules/playwright/index.js';
import fs from 'fs';
import path from 'path';
const { chromium } = pw;

const [, , specPath, outDir] = process.argv;
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const DIR = path.dirname(path.resolve(specPath));
const FONTS = '/home/user/fan-cap-tracker-/assets/fonts';
const logo = t => `file://${DIR}/logos/${t.toLowerCase()}.png`;
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');

const css = `
@font-face{font-family:IX;src:url(file://${FONTS}/Inter-ExtraBold.otf);font-weight:800}
@font-face{font-family:IX;src:url(file://${FONTS}/Inter-SemiBold.otf);font-weight:600}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
body{font-family:IX,Inter,sans-serif;color:#fff;position:relative;background:var(--bg2)}
.bgc{position:absolute;inset:0;background:radial-gradient(1100px 900px at 85% 12%,var(--bg1) 0%,transparent 70%),linear-gradient(180deg,var(--bg1) 0%,var(--bg2) 55%,#080b14 100%)}
.wm{position:absolute;right:-260px;top:120px;width:1100px;height:1100px;background-size:contain;background-repeat:no-repeat;opacity:.07;filter:grayscale(1) brightness(2)}
.wrap{position:absolute;left:90px;right:90px;top:200px}
.top{display:flex;justify-content:space-between;align-items:center}
.pill{background:#fff;color:#0b0f1a;font-weight:800;font-size:31px;padding:10px 20px;border-radius:999px;letter-spacing:-.4px}
.dots{display:flex;gap:14px}.dots i{width:13px;height:13px;border-radius:50%;background:rgba(255,255,255,.35)}.dots i.on{background:#fff}
.hero{display:flex;justify-content:space-between;align-items:flex-start;margin-top:40px}
.badge{display:inline-block;background:#fff;color:#0b0f1a;font-weight:800;font-size:27px;padding:7px 18px;border-radius:999px}
.title{font-weight:800;font-size:116px;letter-spacing:-4px;line-height:1;margin-top:12px}
.rec{font-weight:600;font-size:29px;color:rgba(255,255,255,.8);margin-top:12px}
.who{font-size:27px;line-height:1.35;margin-top:30px;font-weight:600}.who b{font-weight:800}
.biglogo{width:300px;height:300px;object-fit:contain;filter:drop-shadow(0 12px 30px rgba(0,0,0,.45));margin-top:20px}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:44px}
.tile{background:rgba(8,10,20,.42);border:1px solid rgba(255,255,255,.12);border-radius:26px;padding:22px 22px 24px;min-height:150px}
.tile .v{font-weight:800;font-size:56px;letter-spacing:-2px;line-height:1}.tile .v.acc{color:var(--acc)}
.tile .l{font-weight:600;font-size:21px;line-height:1.25;color:rgba(255,255,255,.82);margin-top:10px}
.lab{font-weight:800;font-size:25px;color:var(--acc);margin-top:46px}
.deal{display:grid;grid-template-columns:1fr 46px 1fr;align-items:stretch;margin-top:16px}
.side{background:rgba(8,10,20,.45);border:1px solid rgba(255,255,255,.12);border-radius:26px;padding:22px 24px;min-height:180px}
.side .h{display:flex;align-items:center;gap:12px;font-weight:800;font-size:24px;color:var(--acc)}
.side .h img{width:52px;height:52px;object-fit:contain;background:rgba(255,255,255,.94);border-radius:50%;padding:6px}
.side .m{font-weight:800;font-size:32px;letter-spacing:-.6px;line-height:1.15;margin-top:12px}
.side .s{font-weight:600;font-size:21px;line-height:1.3;color:rgba(255,255,255,.75);margin-top:8px}
.side.dim .m{color:rgba(255,255,255,.7)}
.arrow{align-self:center;text-align:center;font-weight:800;font-size:36px}
.chk{font-weight:600;font-size:25px;line-height:1.36;margin-top:28px;color:rgba(255,255,255,.92)}.chk b{color:var(--acc);font-weight:800}
.fine{font-weight:600;font-size:19px;line-height:1.35;color:rgba(255,255,255,.6);margin-top:26px}
.foot{display:flex;justify-content:space-between;align-items:baseline;margin-top:22px;font-weight:600;font-size:23px;color:rgba(255,255,255,.75)}.foot b{color:#fff;font-weight:800;font-size:28px}
/* cover */
.kick{font-weight:600;font-size:32px;color:rgba(255,255,255,.8);margin-top:70px}
.hook{font-weight:800;font-size:100px;line-height:1.0;letter-spacing:-3.5px;margin-top:14px}
.hacc{font-weight:800;font-size:54px;line-height:1.08;letter-spacing:-1.6px;color:var(--acc);margin-top:20px}
.rows{margin-top:46px;display:grid;gap:18px}
.row{display:grid;grid-template-columns:96px 1fr 50px 96px;align-items:center;gap:16px;background:rgba(8,10,20,.45);border:1px solid rgba(255,255,255,.12);border-radius:28px;padding:18px 22px}
.row img{width:96px;height:96px;object-fit:contain;background:rgba(255,255,255,.94);border-radius:50%;padding:12px}
.row .n{font-weight:800;font-size:36px;letter-spacing:-.8px}.row .t{font-weight:600;font-size:22px;color:rgba(255,255,255,.75);margin-top:4px}
.row .q{width:96px;height:96px;border-radius:50%;border:3px dashed rgba(255,255,255,.4);display:grid;place-items:center;font-weight:800;font-size:46px;color:rgba(255,255,255,.6)}
.lrow{display:flex;gap:22px;margin-top:44px}.lrow img{width:150px;height:150px;object-fit:contain;background:rgba(255,255,255,.94);border-radius:50%;padding:20px}
.swipe{font-weight:600;font-size:31px;margin-top:34px;color:rgba(255,255,255,.88)}
.chips{display:flex;flex-wrap:wrap;gap:14px;margin-top:34px}.chip{background:#fff;color:#0b0f1a;font-weight:800;font-size:30px;padding:9px 20px;border-radius:999px}
`;

const dots = (n, i) => `<div class="dots">${Array.from({ length: n }, (_, k) => `<i class="${k === i ? 'on' : ''}"></i>`).join('')}</div>`;
const side = s => `<div class="side${s.dim ? ' dim' : ''}"><div class="h">${s.team ? `<img src="${logo(s.team)}">` : ''}${esc(s.h)}</div><div class="m">${esc(s.m)}</div>${s.s ? `<div class="s">${esc(s.s)}</div>` : ''}</div>`;
const foot = `<div class="foot"><span>PlainStats · nflverse through Week 8</span><b>plainstatsnfl.com</b></div>`;

function body(s, i, n) {
  const top = `<div class="top"><span class="pill">PlainStats</span>${dots(n, i)}</div>`;
  if (s.type === 'cover') return `${top}
    <div class="kick">${esc(s.kick)}</div><div class="hook">${esc(s.head)}</div><div class="hacc">${esc(s.acc)}</div>
    <div class="rows">${s.rows.map(r => `<div class="row"><img src="${logo(r.from)}"><div><div class="n">${esc(r.name)}</div><div class="t">${esc(r.note)}</div></div><div class="arrow">→</div>${r.to ? `<img src="${logo(r.to)}">` : '<div class="q">?</div>'}</div>`).join('')}</div>
    <div class="swipe">${esc(s.sub)}</div>`;
  if (s.type === 'outro') return `${top}
    <div class="kick">${esc(s.kick)}</div><div class="hook">${esc(s.head)}</div><div class="hacc">${esc(s.acc)}</div>
    ${s.logos ? `<div class="lrow">${s.logos.map(t => `<img src="${logo(t)}">`).join('')}</div>` : ''}<div class="chips">${s.chips.map(c => `<span class="chip">${esc(c)}</span>`).join('')}</div><div class="swipe">${esc(s.sub)}</div>`;
  return `${top}
    <div class="hero"><div><span class="badge">${esc(s.badge)}</span><div class="title">${esc(s.title)}</div><div class="rec">${esc(s.rec)}</div>
      <div class="who"><b>${esc(s.whoB)}</b> ${esc(s.who)}<br>${esc(s.who2)}</div></div><img class="biglogo" src="${logo(s.logo)}"></div>
    <div class="tiles">${s.tiles.map(t => `<div class="tile"><div class="v${t.acc ? ' acc' : ''}">${esc(t.v)}</div><div class="l">${esc(t.l)}</div></div>`).join('')}</div>
    <div class="lab">${esc(s.label)}</div>
    <div class="deal">${side(s.left)}<div class="arrow">⇄</div>${side(s.right)}</div>
    ${s.checks.map(c => `<div class="chk"><b>${esc(c[0])}</b> ${esc(c[1])}</div>`).join('')}
    <div class="fine">${esc(s.fine)}</div>${foot}`;
}

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
const n = spec.slides.length;
for (const [i, s] of spec.slides.entries()) {
  const vars = `--bg1:${s.bg1};--bg2:${s.bg2};--acc:${s.acc2 || s.accent}`;
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body style="${vars}">
    <div class="bgc"></div>${s.wm ? `<div class="wm" style="background-image:url('${logo(s.wm)}')"></div>` : ''}<div class="wrap">${body(s, i, n)}</div></body></html>`;
  const f = path.join(outDir, `_s${i}.html`); fs.writeFileSync(f, html);
  await page.goto('file://' + path.resolve(f)); await page.evaluate(() => document.fonts.ready);
  const bottom = await page.evaluate(() => document.querySelector('.wrap').getBoundingClientRect().bottom);
  if (bottom > 1660) console.warn(`slide ${i + 1}: content ends at ${Math.round(bottom)}px (TikTok caption zone)`);
  await page.screenshot({ path: path.join(outDir, `${String(i + 1).padStart(2, '0')}-${s.id}.png`) });
  fs.unlinkSync(f);
}
await browser.close();
console.log('rendered', n);
