// Layout for the 1200x630 social cards drawn by api/og.js. The leading underscore keeps Vercel from serving it as a route.
//
// A card is a plain object tree shaped like React elements, so there is no JSX and no build step. Satori (inside @vercel/og)
// draws it with flexbox, which means: every element with more than one child is display:flex, sizes are in px, no grid and no calc().
// tools/preview_og.mjs turns the same tree into HTML so a card can be checked in a browser before it ships.
//
// Card data (see og-data/*.json, written by tools/build_seo.py):
//   m  look: 'face' (headshot on team color), 'logo' (team logo on team color) or 'brand' (PlainStats blue)
//   c  panel color    t  name    s  one line under the name    e  small label next to the PlainStats wordmark
//   n  the key number l  what it is    x  one extra line    i  main image URL    g  corner logo URL

export const W = 1200;
export const H = 630;

const INK = '#1d1d1f';
const MUTED = '#636368';
const BRAND = '#0071e3';
const PANEL_W = 430;
const TEXT_W = W - PANEL_W - 56 * 2; // right column minus its side padding

const h = (type, style, children, props) => ({ type, props: { ...props, style, children } });

// Darken a #rrggbb color by a fraction (0.4 = 40% toward black).
const shade = (hex, f) => {
  const n = parseInt(hex.slice(1), 16);
  return '#' + [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * (1 - f)).toString(16).padStart(2, '0')).join('');
};

const initials = name => String(name || '').replace(/[^A-Za-z .'-]/g, '').split(/\s+/).filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase();

// Biggest font size (up to max) at which `text` fits `width` on one line, assuming the average glyph is `ratio` em wide.
const fit = (text, max, width, ratio) => Math.max(36, Math.min(max, Math.floor(width / (Math.max(1, String(text).length) * ratio))));

function leftPanel(c, imgs) {
  const base = { display: 'flex', position: 'relative', width: PANEL_W, height: H, backgroundImage: `linear-gradient(165deg, ${c.c}, ${shade(c.c, 0.4)})` };

  if (c.m === 'brand') {
    return h('div', { ...base, alignItems: 'center', justifyContent: 'center', backgroundImage: `linear-gradient(165deg, ${BRAND}, ${shade(BRAND, 0.45)})` },
      h('div', { display: 'flex', flexDirection: 'column', color: '#ffffff', fontWeight: 800, fontSize: 84, lineHeight: 1, letterSpacing: -3 }, [
        h('div', { display: 'flex' }, 'Plain'),
        h('div', { display: 'flex', opacity: 0.72 }, 'Stats')
      ]));
  }

  if (c.m === 'logo') {
    // A white disc keeps every logo readable on every team color (the Packers' green logo on green, say).
    return h('div', { ...base, alignItems: 'center', justifyContent: 'center' },
      h('div', { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 320, height: 320, borderRadius: 160, backgroundColor: '#ffffff' },
        imgs.main
          ? h('img', { width: 236, height: 236, objectFit: 'contain' }, undefined, { src: imgs.main, width: 236, height: 236 })
          : h('div', { display: 'flex', fontSize: 120, fontWeight: 800, color: c.c }, initials(c.t))));
  }

  // face: headshot sitting on the bottom edge, small team or school logo in a white chip, top left.
  const kids = [];
  if (imgs.main) {
    kids.push(h('img', { position: 'absolute', left: 15, bottom: 0, width: 400, height: 290, objectFit: 'contain' }, undefined, { src: imgs.main, width: 400, height: 290 }));
  } else {
    kids.push(h('div', { position: 'absolute', left: 95, top: 215, width: 240, height: 240, borderRadius: 120, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', display: 'flex', color: '#ffffff', fontSize: 96, fontWeight: 800 }, initials(c.t)));
  }
  if (imgs.logo) {
    kids.push(h('div', { position: 'absolute', left: 32, top: 32, width: 104, height: 104, borderRadius: 52, backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center', display: 'flex' },
      h('img', { width: 72, height: 72, objectFit: 'contain' }, undefined, { src: imgs.logo, width: 72, height: 72 })));
  }
  return h('div', base, kids);
}

function rightColumn(c, asOf) {
  // Names run about 0.45 to 0.55 em per character, so assume 0.55: the name fills one line up to 84px, shrinks to 50px, and only the longest wrap.
  const nameSize = Math.max(50, Math.min(84, Math.floor(TEXT_W / (c.t.length * 0.55))));
  const n = String(c.n || '');
  // A short number ("$63.1M") goes big on one line. A phrase ("Contract being verified") is smaller and may wrap to two lines.
  const phrase = n.length > 9 && n.includes(' ');
  const numSize = phrase ? Math.max(44, Math.min(72, Math.floor((TEXT_W * 1.9) / (n.length * 0.56)))) : fit(n, 150, TEXT_W, 0.64);

  const wordmark = [h('div', { display: 'flex', color: INK, fontWeight: 800, fontSize: 30, letterSpacing: -0.5 }, 'PlainStats')];
  if (c.e && c.e !== 'PlainStats') {
    wordmark.push(h('div', { display: 'flex', color: MUTED, fontWeight: 600, fontSize: 30, marginLeft: 14 }, '·'));
    wordmark.push(h('div', { display: 'flex', color: MUTED, fontWeight: 600, fontSize: 30, marginLeft: 14 }, c.e));
  }

  const top = h('div', { display: 'flex', flexDirection: 'column' }, [
    h('div', { display: 'flex', alignItems: 'center' }, [h('div', { display: 'flex', width: 14, height: 14, borderRadius: 7, backgroundColor: BRAND, marginRight: 14 }), ...wordmark]),
    h('div', { display: 'flex', marginTop: 30, color: INK, fontWeight: 800, fontSize: nameSize, lineHeight: 1.04, letterSpacing: -2 }, c.t),
    c.s ? h('div', { display: 'flex', marginTop: 12, color: MUTED, fontWeight: 600, fontSize: 34 }, c.s) : null
  ].filter(Boolean));

  const middle = h('div', { display: 'flex', flexDirection: 'column' }, [
    h('div', { display: 'flex', color: BRAND, fontWeight: 800, fontSize: numSize, lineHeight: 1.02, letterSpacing: -4 }, n),
    c.l ? h('div', { display: 'flex', marginTop: 8, color: INK, fontWeight: 600, fontSize: Math.min(34, fit(c.l, 34, TEXT_W, 0.5)) }, c.l) : null,
    c.x ? h('div', { display: 'flex', marginTop: 8, color: MUTED, fontWeight: 600, fontSize: Math.min(30, fit(c.x, 30, TEXT_W, 0.5)) }, c.x) : null
  ].filter(Boolean));

  const foot = h('div', { display: 'flex', justifyContent: 'space-between', color: MUTED, fontWeight: 600, fontSize: 26 }, [
    h('div', { display: 'flex' }, 'plainstatsnfl.com'),
    asOf ? h('div', { display: 'flex' }, `As of ${asOf}`) : null
  ].filter(Boolean));

  return h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', flex: 1, height: H, padding: '48px 56px 40px 56px' }, [top, middle, foot]);
}

// imgs: { main, logo } as data: URIs, or null when an image could not be fetched (initials stand in).
export function card(c, imgs, asOf) {
  return h('div', { display: 'flex', width: W, height: H, backgroundColor: '#ffffff', fontFamily: 'Inter' }, [leftPanel(c, imgs), rightColumn(c, asOf)]);
}
