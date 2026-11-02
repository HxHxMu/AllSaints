// RSS: the newest 30 saints with their summary and a link to the page (EN at /rss.xml, ES at /es/rss.xml).
// English items carry the saint's Pinterest pin (public/pin/, share-cards.mjs) as an enclosure: Pinterest
// auto-publishes the feed, one Pin per item, linking to the page.
// Pinterest boards mirror the YouTube playlists: one feed per board (/pin/<board>.xml, pages/pin/[board].xml.ts),
// "Saints of <Month>" by feast month and "Saints of <continent>" by ep.continent; titles from brand.json.
import { existsSync, statSync } from "node:fs";
import rss from "@astrojs/rss";
import brand from "../../../brand/brand.json";
import { saintsIn, monthName, type Lang, type Saint, type Text } from "./episodes";
import { paths, t } from "./i18n";

const PL = (brand as any).youtube.playlists;
const CONTINENTS = ["Africa", "Asia", "Europe", "the Americas", "the Middle East", "Oceania"];
const slug = (x: string) => x.toLowerCase().replace(/^the /, "").replace(/\s+/g, "-");
export const boards = [
  ...Array.from({ length: 12 }, (_, m) => {
    const name = monthName(`2000-${String(m + 1).padStart(2, "0")}-01`);
    return { slug: slug(name), title: PL.month.replace("{name}", name), has: (s: Saint) => Number(s.date.slice(5, 7)) === m + 1 };
  }),
  ...CONTINENTS.map((name) => ({ slug: slug(name), title: PL.region.replace("{name}", name), has: (s: Saint) => s.continent === name })),
];

const item = (s: Saint & Text, lang: Lang, site: URL) => ({
  title: s.name,
  link: paths[lang].saint(s.slug),
  pubDate: new Date(`${s.date}T12:30:00Z`),  // 7:30 AM New York, the posting time
  description: [s.hook, s.summary].filter(Boolean).join(" "),
  categories: [...s.patronages, ...s.places],
  enclosure: pin(lang, s.id, site),
});

// Pinterest is search: the Pin title and description carry the words people type ("Catholic saint", "feast day",
// patronages, the region). Plain facts from the episode, no AI. Pinterest caps titles at 100, descriptions at 500.
const clip = (x: string, n: number) => (x.length <= n ? x : `${x.slice(0, n - 1).replace(/\s+\S*$/, "")}…`);
function pinItem(s: Saint & Text, site: URL) {
  const feast = `Feast Day ${monthName(s.date)} ${Number(s.date.slice(8, 10))}`;
  const lead = [s.patronages.length ? `Patron of ${s.patronages.slice(0, 4).join(", ")}.` : "", s.region ? `${s.region}${s.dates ? `, ${s.dates}` : ""}.` : ""];
  const tail = "Read the full story at allholysaints.com. Catholic saints, feast days and lives of the saints.";
  const body = clip(s.summary || s.hook, 500 - tail.length - lead.join(" ").length - 6);
  return {
    ...item(s, "en", site),
    title: clip(`${s.name} · Catholic Saint · ${feast}`, 100),
    description: [`${feast}.`, body, ...lead, tail].filter(Boolean).join(" ").slice(0, 500),
  };
}

// every saint on one board, newest first (Pinterest pins each item once, only items with a pin image)
export function boardFeed(slug: string, site: URL) {
  const b = boards.find((x) => x.slug === slug)!;
  return rss({
    title: b.title,
    description: PL.description.replace("{title}", b.title),
    site,
    customData: "<language>en</language>",
    items: [...saintsIn("en")].reverse().filter((s) => b.has(s) && pin("en", s.id, site)).map((s) => pinItem(s, site)),
  });
}

export function feed(lang: Lang, site: URL) {
  const T = t[lang];
  return rss({
    title: lang === "es" ? "All Saints (español)" : "All Saints",
    description: `${T.homeDesc} ${T.tagline}`,
    site,
    customData: `<language>${lang}</language>`,
    items: [...saintsIn(lang)].reverse().slice(0, 30).map((s) => item(s, lang, site)),
  });
}

function pin(lang: Lang, id: string, site: URL) {
  const file = `${process.cwd()}/public/pin/${id}.jpg`;  // builds run from site/
  if (lang !== "en" || !existsSync(file)) return undefined;
  return { url: new URL(`/pin/${id}.jpg`, site).href, length: statSync(file).size, type: "image/jpeg" };
}
