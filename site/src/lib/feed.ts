// RSS: the newest 30 saints with their summary and a link to the page (EN at /rss.xml, ES at /es/rss.xml).
// English items carry the saint's Pinterest pin (public/pin/, share-cards.mjs) as an enclosure: Pinterest
// auto-publishes the feed, one Pin per item, linking to the page.
import { existsSync, statSync } from "node:fs";
import rss from "@astrojs/rss";
import { saintsIn, type Lang } from "./episodes";
import { paths, t } from "./i18n";

export function feed(lang: Lang, site: URL) {
  const T = t[lang], P = paths[lang];
  return rss({
    title: lang === "es" ? "All Saints (español)" : "All Saints",
    description: `${T.homeDesc} ${T.tagline}`,
    site,
    customData: `<language>${lang}</language>`,
    items: [...saintsIn(lang)].reverse().slice(0, 30).map((s) => ({
      title: s.name,
      link: P.saint(s.slug),
      pubDate: new Date(`${s.date}T12:30:00Z`),  // 7:30 AM New York, the posting time
      description: [s.hook, s.summary].filter(Boolean).join(" "),
      categories: [...s.patronages, ...s.places],
      enclosure: pin(lang, s.id, site),
    })),
  });
}

function pin(lang: Lang, id: string, site: URL) {
  const file = `${process.cwd()}/public/pin/${id}.jpg`;  // builds run from site/
  if (lang !== "en" || !existsSync(file)) return undefined;
  return { url: new URL(`/pin/${id}.jpg`, site).href, length: statSync(file).size, type: "image/jpeg" };
}
