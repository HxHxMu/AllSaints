// Downloads each episode's icon art from its GitHub release into src/assets/art/<id>.jpg
// (Astro then makes responsive AVIF/WebP). Prefers art.jpg (the clean icon); older episodes
// only have cover.jpg, whose title text sits below ~60% height, so we keep the top part.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import sharp from "sharp";

const EPISODES = new URL("../../state/episodes/", import.meta.url);
const OUT = new URL("../src/assets/art/", import.meta.url);
const REPO = "https://github.com/HxHxMu/AllSaints/releases/download";
mkdirSync(OUT, { recursive: true });

async function get(url) {
  const r = await fetch(url, { redirect: "follow" });
  return r.ok ? Buffer.from(await r.arrayBuffer()) : null;
}

for (const f of readdirSync(EPISODES).filter((n) => n.endsWith(".json") && !n.startsWith("."))) {
  const ep = JSON.parse(readFileSync(new URL(f, EPISODES), "utf8"));
  const dest = new URL(`${ep.id}.jpg`, OUT);
  if (!ep.assets || existsSync(dest)) continue;
  let img = await get(`${REPO}/ep-${ep.id}/art.jpg`);
  if (!img) {
    const cover = await get(`${REPO}/ep-${ep.id}/cover.jpg`);
    if (!cover) { console.warn(`no art for ${ep.id}`); continue; }
    const { width, height } = await sharp(cover).metadata();
    img = await sharp(cover).extract({ left: 0, top: 0, width, height: Math.round(height * 0.58) }).jpeg({ quality: 90 }).toBuffer();
  }
  writeFileSync(dest, img);
  console.log(`art ${ep.id}`);
}
