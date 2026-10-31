// RSS: the newest 30 saints with their summary and a link to the page (EN at /rss.xml, ES at /es/rss.xml).
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
    })),
  });
}
