// First step of every build (prebuild/predev): checks the episode fields the site and its scripts read, so a
// malformed episode stops the deploy with a clear message instead of a crash or a broken page.
// Extra fields are fine. CI: .github/workflows/site.yml.
import { readdirSync, readFileSync } from "node:fs";
import { z } from "astro/zod";

const EPISODES = new URL("../../state/episodes/", import.meta.url);
// same rule as src/lib/episodes.ts: upcoming saints stay private until they're published
const VISIBLE = new Set(process.env.SITE_ALL === "1" ? ["published", "approved", "review", "publishing"] : ["published"]);

const str = z.string(), strs = z.array(z.string());
const text = { name: str.min(1), display_name: str.optional(), dates: str.optional(), region: str.optional() };
const Episode = z.object({
  id: str.regex(/^\d{4}-\d{2}-\d{2}$/), date: str.regex(/^\d{4}-\d{2}-\d{2}$/), status: str,
  slug: str.regex(/^[a-z0-9-]+$/).nullish(),
  script: z.object({
    saint: z.object({ ...text, martyr: z.boolean().optional() }),
    beats: z.array(z.object({ role: str, text: str })).min(1),
    story: strs.nullish(), patronages: strs.nullish(), places: strs.nullish(),
    caption_hook: str.optional(), summary: str.optional(),
  }),
  es: z.object({
    ...text, slug: str.regex(/^[a-z0-9-]+$/).nullish(), story: strs.nullish(), hook: str.optional(),
    summary: str.optional(), prayer: str.optional(), patronages: strs.nullish(), places: strs.nullish(),
  }).nullish(),
  youtube: z.object({ id: str.optional() }).nullish(),
  duration: z.number().nullish(),
  sources: z.array(z.object({ title: str, url: str.optional() })).optional(),
  art_credits: strs.optional(),
  assets: z.record(z.string(), str).nullish(),
  continent: str.nullish(),
  books: z.array(z.object({ title: str, author: str, isbn: str })).optional(),
});

function check(ep) {
  const r = Episode.safeParse(ep);
  if (!r.success) {
    const issues = r.error.issues.map((i) => `${i.path.join(".") || "(file)"}: ${i.message}`).join("; ");
    throw new Error(`state/episodes/${ep.id}.json can't be shown on the site: ${issues}`);
  }
  return ep;
}

let n = 0;
for (const f of readdirSync(EPISODES).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n))) {
  let ep;
  try { ep = JSON.parse(readFileSync(new URL(f, EPISODES), "utf8")); }
  catch (e) { throw new Error(`state/episodes/${f} isn't valid JSON: ${e.message}`); }
  if (ep?.script && VISIBLE.has(ep.status)) { check(ep); n++; }
}
console.log(`episodes ok (${n})`);
