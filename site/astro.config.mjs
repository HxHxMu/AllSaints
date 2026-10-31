import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { readdirSync, readFileSync } from "node:fs";

// The patron/place index pages are noindex while empty (TopicIndex.astro), so leave them out of the sitemap too.
const visible = new Set(process.env.SITE_ALL === "1" ? ["published", "approved", "review", "publishing"] : ["published"]);
const dir = new URL("../state/episodes/", import.meta.url);
const eps = readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("."))
  .map((f) => JSON.parse(readFileSync(new URL(f, dir), "utf8"))).filter((e) => e.script && visible.has(e.status));
const has = (pick) => eps.some((e) => pick(e)?.length);
const empty = [
  ...(has((e) => e.script.patronages) ? [] : ["/patrons/"]), ...(has((e) => e.es?.patronages) ? [] : ["/es/patronos/"]),
  ...(has((e) => e.script.places) ? [] : ["/places/"]), ...(has((e) => e.es?.places) ? [] : ["/es/lugares/"]),
];

export default defineConfig({
  site: "https://allholysaints.com",
  trailingSlash: "always",
  integrations: [sitemap({
    filter: (page) => !/\/(check-email|subscribed)\/$/.test(page) && !empty.some((p) => new URL(page).pathname === p),
  })],
  build: { inlineStylesheets: "always" },
  vite: { server: { fs: { allow: [".."] } } },
});
