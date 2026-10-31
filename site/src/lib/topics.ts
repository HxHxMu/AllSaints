// Patron and place pages: every patronage and place the script call tagged (script.patronages / places,
// and the Spanish ones in ep.es) gets a page listing its saints. They grow with each saint; long-tail
// searches like "patron saint of soldiers" or "saints of Lisbon" land here.
import { saintsIn, type Lang, type Saint, type Text } from "./episodes";

export type Kind = "patron" | "place";
export type Topic = { slug: string; name: string; saints: (Saint & Text)[] };

const slugify = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export function topics(lang: Lang, kind: Kind): Topic[] {
  const by = new Map<string, Topic>();
  for (const s of saintsIn(lang)) {
    for (const name of kind === "patron" ? s.patronages : s.places) {
      const slug = slugify(name);
      if (!slug) continue;
      const t = by.get(slug) || { slug, name: name.trim(), saints: [] };
      if (!t.saints.some((x) => x.id === s.id)) t.saints.push(s);
      by.set(slug, t);
    }
  }
  return [...by.values()].sort((a, b) => a.name.localeCompare(b.name, lang));
}

export const topicSlug = slugify;
