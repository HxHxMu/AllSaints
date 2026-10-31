// Share cards: the 1200×630 image link previews show (WhatsApp, Facebook, iMessage, X). One per saint
// (public/og/<id>.jpg, and <id>-es.jpg for the Spanish edition) plus public/og/default.jpg for every other
// page. The icon from src/assets/art/ (fetch-art.mjs) on the left, fading into soot; name and feast on the right.
// Text is set with opentype.js from the brand's own TTFs and drawn as SVG outlines, so it looks the same on a Mac
// and on Cloudflare's Linux builders (no system fonts involved). No AI; rebuilt every build (a redo can change the saint).
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import opentype from "opentype.js";

const EPISODES = new URL("../../state/episodes/", import.meta.url);
const ART = new URL("../src/assets/art/", import.meta.url);
const OUT = new URL("../public/og/", import.meta.url);
const brand = JSON.parse(readFileSync(new URL("../../brand/brand.json", import.meta.url), "utf8"));
const C = brand.colors;
const load = (f) => { const b = readFileSync(new URL(`../../brand/fonts/${f}`, import.meta.url)); return opentype.parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
const F = {
  title: load("Cinzel-SemiBold.ttf"), caps: load("Cinzel-Regular.ttf"),
  italic: load("Cormorant-MediumItalic.ttf"), body: load("EBGaramond-Medium.ttf"),
};
// same rule as src/lib/episodes.ts: upcoming saints stay private until they're published
const VISIBLE = new Set(process.env.SITE_ALL === "1" ? ["published", "approved", "review", "publishing"] : ["published"]);
const W = 1200, H = 630, ART_W = 600, X = 660, TEXT_W = W - X - 56;
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

const MONTHS = {
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  es: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
};
const ROMAN = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
const roman = (n) => ROMAN.reduce((s, [v, r]) => { while (n >= v) { s += r; n -= v; } return s; }, "");

// width of a line with letter-spacing (em fraction), kerning on
const measure = (font, str, size, tracking = 0) => font.getAdvanceWidth(str, size, { kerning: true }) + tracking * size * Math.max(0, str.length - 1);

// greedy word wrap to `width`; "\n" forces a break
function wrap(font, str, size, width, tracking) {
  const lines = [];
  for (const para of str.split("\n")) {
    let line = null;
    for (const word of para.split(/\s+/).filter(Boolean)) {
      if (line !== null && measure(font, `${line} ${word}`, size, tracking) <= width) line = `${line} ${word}`;
      else { if (line !== null) lines.push(line); line = word; }
    }
    if (line !== null) lines.push(line);
  }
  return lines;
}

// SVG path data for one line; letters placed one by one when tracked
function linePath(font, str, x, y, size, tracking) {
  if (!tracking) return font.getPath(str, x, y, size, { kerning: true }).toPathData(2);
  let d = "", cx = x;
  for (const ch of str) {
    d += font.getPath(ch, cx, y, size).toPathData(2);
    cx += font.getAdvanceWidth(ch, size) + tracking * size;
  }
  return d;
}

// a text block whose first line's cap height starts at `top`; returns its SVG and the y below its last baseline
function block(str, { font, size, color, top, x = X, width = TEXT_W, tracking = 0, leading = 1.12 }) {
  const lines = wrap(font, str, size, width, tracking);
  const cap = ((font.tables.os2?.sCapHeight || font.ascender * 0.7) / font.unitsPerEm) * size;
  const base = (i) => top + cap + i * size * leading;
  const d = lines.map((l, i) => linePath(font, l, x, base(i), size, tracking)).join("");
  return { svg: `<path d="${d}" fill="${color}"/>`, bottom: base(lines.length - 1), lines: lines.length, cap };
}

// "A.S." in Cinzel with the cross drawn as two bars (Cinzel has no dagger), as on the cover and the video
function monogram(x, top, size) {
  const t = block("A.S.", { font: F.title, size, color: C.giltLight, top, x, tracking: 0.04, width: 400 });
  const cx = x + measure(F.title, "A.S.", size, 0.04) + size * 0.16, stem = size * 0.075, w = size * 0.5;
  const y0 = top - size * 0.1, h = t.cap + size * 0.2;
  return t.svg + `<rect x="${cx + (w - stem) / 2}" y="${y0}" width="${stem}" height="${h}" fill="${C.giltLight}"/>`
    + `<rect x="${cx}" y="${y0 + h * 0.3}" width="${w}" height="${stem}" fill="${C.giltLight}"/>`;
}

// the icon, cropped to the left panel
async function artPanel(id) {
  const src = new URL(`${id}.jpg`, ART);
  if (!existsSync(src)) return null;
  return sharp(fileURLToPath(src)).resize(ART_W, H, { fit: "cover", position: "top" }).toBuffer();
}

async function card({ art, eyebrow, name, meta, foot, out }) {
  const parts = [monogram(X, 66, 36)];
  let y = 150;
  if (eyebrow) {
    const e = block(eyebrow.toUpperCase(), { font: F.caps, size: 20, color: C.ash, top: y, tracking: 0.16 });
    parts.push(e.svg); y = e.bottom + 30;
  }
  // long names step down a size so they stay within three lines
  for (const size of [62, 54, 46, 40]) {
    if (wrap(F.title, name, size, TEXT_W, 0.02).length <= 3 || size === 40) {
      const n = block(name, { font: F.title, size, color: C.vellum, top: y, tracking: 0.02, leading: 1.1 });
      parts.push(n.svg); y = n.bottom + 26; break;
    }
  }
  if (meta) {
    const m = block(meta, { font: F.italic, size: 32, color: C.giltLight, top: y, leading: 1.15 });
    parts.push(m.svg); y = m.bottom + 30;
  }
  parts.push(`<rect x="${X}" y="${Math.min(y, H - 130)}" width="72" height="3" fill="${C.martyr}"/>`);
  parts.push(block(foot, { font: F.body, size: 23, color: C.ash, top: H - 92, leading: 1.3 }).svg);
  // the painting's right edge melts into the soot panel
  const fade = `<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0.72" stop-color="${C.soot}" stop-opacity="0"/>`
    + `<stop offset="1" stop-color="${C.soot}"/></linearGradient></defs><rect width="${ART_W}" height="${H}" fill="url(#g)"/>`;
  const svg = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">${art ? fade : ""}${parts.join("")}</svg>`);
  await sharp({ create: { width: W, height: H, channels: 3, background: C.soot } })
    .composite([...(art ? [{ input: art, left: 0, top: 0 }] : []), { input: svg, left: 0, top: 0 }])
    .jpeg({ quality: 86, mozjpeg: true }).toFile(fileURLToPath(new URL(out, OUT)));
}

const day = (iso, lang) => `${roman(Number(iso.slice(8, 10)))} · ${MONTHS[lang][Number(iso.slice(5, 7)) - 1]}`;
const meta = (x) => [x.dates, x.region].filter(Boolean).join(" · ");
let n = 0;
for (const f of readdirSync(EPISODES).filter((x) => x.endsWith(".json") && !x.startsWith("."))) {
  const ep = JSON.parse(readFileSync(new URL(f, EPISODES), "utf8"));
  const s = ep.script?.saint;
  if (!s || !/^\d{4}-\d{2}-\d{2}$/.test(ep.id) || !VISIBLE.has(ep.status)) continue;
  const art = await artPanel(ep.id);
  await card({ art, eyebrow: day(ep.date, "en"), name: s.name, meta: meta(s), foot: `allholysaints.com\n${brand.tagline}`, out: `${ep.id}.jpg` });
  if (ep.es?.name) {
    await card({ art, eyebrow: day(ep.date, "es"), name: ep.es.name, meta: meta({ dates: ep.es.dates || s.dates, region: ep.es.region }),
      foot: `allholysaints.com\n${brand.site_es.tagline}`, out: `${ep.id}-es.jpg` });
  }
  n++;
}
// every other page: the channel's own card, with the intro's icon when there is one
await card({ art: await artPanel("intro"), eyebrow: "One forgotten saint a day", name: "All Saints", meta: brand.tagline,
  foot: "allholysaints.com", out: "default.jpg" });
console.log(`share cards: ${n} saints + default`);
