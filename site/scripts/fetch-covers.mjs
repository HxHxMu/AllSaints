// Book covers for "Go deeper": every ISBN on the curated shelf (brand/books.json) and in the episodes' own books,
// downloaded once into src/assets/books/<isbn>.jpg (Astro then makes responsive AVIF/WebP). Bookshop.org's image
// first (the store the links go to), Open Library as the fallback; a book with neither gets a typeset cover on the page.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import sharp from "sharp";

const EPISODES = new URL("../../state/episodes/", import.meta.url);
const OUT = new URL("../src/assets/books/", import.meta.url);
mkdirSync(OUT, { recursive: true });
const isbns = new Set(JSON.parse(readFileSync(new URL("../../brand/books.json", import.meta.url), "utf8")).shelf.map((b) => b.isbn));
for (const f of readdirSync(EPISODES).filter((n) => n.endsWith(".json") && !n.startsWith("."))) {
  for (const b of JSON.parse(readFileSync(new URL(f, EPISODES), "utf8")).books || []) isbns.add(b.isbn);
}

async function get(url) {
  try {
    const r = await fetch(url, { redirect: "follow", headers: { "User-Agent": "Mozilla/5.0 (allholysaints.com build)" } });
    if (!r.ok || !(r.headers.get("content-type") || "").startsWith("image/")) return null;
    const img = Buffer.from(await r.arrayBuffer());
    const { width, height } = await sharp(img).metadata();
    return width >= 100 && height > width ? img : null;  // a real portrait cover, not a 1px or placeholder image
  } catch { return null; }
}

let n = 0;
for (const isbn of isbns) {
  const dest = new URL(`${isbn}.jpg`, OUT);
  if (existsSync(dest)) continue;
  const img = await get(`https://images-us.bookshop.org/ingram/${isbn}.jpg?height=600&v=v2`)
    || await get(`https://covers.openlibrary.org/b/isbn/${isbn}-L.jpg?default=false`);
  if (!img) { console.warn(`no cover ${isbn}`); continue; }
  writeFileSync(dest, await sharp(img).resize({ height: 600, withoutEnlargement: true }).jpeg({ quality: 88 }).toBuffer());
  n++;
}
console.log(`book covers: ${n} new`);
