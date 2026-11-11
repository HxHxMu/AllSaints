// Episodes come straight from the pipeline's state files. Only published ones reach the site;
// SITE_ALL=1 (local preview) also shows episodes still in review/approved.
const files = import.meta.glob<any>("../../../state/episodes/*.json", { eager: true, import: "default" });
const art = import.meta.glob<{ default: ImageMetadata }>("../assets/art/*.jpg", { eager: true });
import config from "../../../state/config.json";
import brand from "../../../brand/brand.json";

export const SUPPORT_URL: string = (config as any).support_url || "";
export const DISCLOSURE: string = (brand as any).youtube?.disclosure || "";
export const TAGLINE: string = (brand as any).tagline;
const ES = (brand as any).site_es || {};
export const disclosure = (lang: "en" | "es") => (lang === "es" && ES.disclosure) || DISCLOSURE;
export const credit = (c: string, lang: "en" | "es") => (lang === "es" && ES.credits?.[c]) || c;

const showAll = process.env.SITE_ALL === "1";
const visible = new Set(showAll ? ["published", "approved", "review", "publishing"] : ["published"]);

export type Lang = "en" | "es";
export type Text = {
  slug: string; fixed: boolean; name: string; display: string; dates: string; region: string;
  hook: string; summary: string; story: string[]; prayer: string; patronages: string[]; places: string[];
};
export type Saint = Text & {
  id: string; date: string; martyr: boolean; es: Text | null;
  youtubeId: string | null; uploaded: string | null; duration: number | null; sources: { title: string; url?: string }[];
  credits: string[]; cover: string | null; art: ImageMetadata | null;
  continent: string | null; books: { title: string; author: string; isbn: string }[];
  qid: string | null; sameAs: string[];
};

// the Spanish edition: only saints the pipeline translated (ep.es)
export const inLang = (s: Saint, lang: Lang): (Saint & Text) | null => (lang === "en" ? s : s.es ? { ...s, ...s.es } : null);

const ROMAN: [number, string][] = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
export const roman = (n: number) => ROMAN.reduce((s, [v, r]) => { while (n >= v) { s += r; n -= v; } return s; }, "");
const MONTHS = {
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  es: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
};
export const monthName = (iso: string, lang: Lang = "en") => MONTHS[lang][Number(iso.slice(5, 7)) - 1];
export const manuscriptDate = (iso: string, lang: Lang = "en") => `${roman(Number(iso.slice(8, 10)))} · ${monthName(iso, lang)}`;
// the saint's 1200×630 link-preview card (scripts/share-cards.mjs); the Spanish edition has its own
export const shareCard = (s: Saint, lang: Lang) => `/og/${s.id}${lang === "es" && s.es ? "-es" : ""}.jpg`;
export const minutes = (s: number | null) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "");

const slugify = (name: string) =>
  name.replace(/^(Saints?|Sts?\.|San|Santos?|Santas?)\s+/i, "").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// older episodes stored Wikipedia titles URL-encoded ("Nuno %C3%81lvares"); screen readers read that letter by letter
const readableSource = (s: { title: string; url?: string }) => {
  try { return { ...s, title: decodeURIComponent(s.title) }; } catch { return s; }
};

function toSaint(ep: any): Saint {
  const s = ep.script, saint = s.saint;
  const beats: any[] = s.beats || [];
  const close = beats.find((b) => b.role === "close")?.text || `${saint.name}, pray for us.`;
  const es = ep.es?.story?.length ? ep.es : null;
  return {
    // the address the pipeline saved at publish (ep.slug); unpublished previews work one out
    id: ep.id, date: ep.date, slug: ep.slug || slugify(saint.name), name: saint.name, fixed: !!ep.slug,
    display: saint.display_name || saint.name, dates: saint.dates || "", region: saint.region || "",
    martyr: !!saint.martyr, hook: s.caption_hook || beats[0]?.text || "", summary: s.summary || "",
    // the long-form story (script.story) replaces the narration beats; older episodes don't have it
    story: s.story?.length ? s.story : beats.filter((b) => !["hook", "close"].includes(b.role)).map((b) => b.text),
    prayer: close, patronages: s.patronages || [], places: s.places || [],
    es: es && {
      slug: es.slug || slugify(es.name), fixed: !!es.slug, name: es.name, display: es.display_name || es.name, dates: es.dates || "",
      region: es.region || "", hook: es.hook || "", summary: es.summary || "", story: es.story,
      prayer: es.prayer || "", patronages: es.patronages || [], places: es.places || [],
    },
    youtubeId: ep.youtube?.id || null,
    // full ISO 8601 with seconds and zone (stored as "2026-11-04T07:33-05:00"); Google rejects a bare date
    uploaded: ep.youtube?.id ? new Date(ep.youtube.published_at || `${ep.date}T12:30:00Z`).toISOString() : null,
    duration: ep.duration || null, sources: (ep.sources || []).map(readableSource), credits: [...new Set<string>(ep.art_credits || [])],
    cover: ep.assets?.["cover.jpg"] || null, art: art[`../assets/art/${ep.id}.jpg`]?.default || null,
    continent: ep.continent || null, books: ep.books || [],
    // the saint's Wikidata and Wikipedia entries: tells search engines which saint the page is about
    qid: ep.saint?.qid || null,
    sameAs: [
      ep.saint?.qid && `https://www.wikidata.org/wiki/${ep.saint.qid}`,
      ep.saint_pick?.enwiki && `https://en.wikipedia.org/wiki/${encodeURIComponent(ep.saint_pick.enwiki.replace(/ /g, "_"))}`,
    ].filter(Boolean),
  };
}

const all: Saint[] = Object.values(files)
  .filter((ep) => ep?.script && /^\d{4}-\d{2}-\d{2}$/.test(ep.id) && visible.has(ep.status)) // skips the channel intro
  .map(toSaint)
  .sort((a, b) => a.date.localeCompare(b.date));

// Saved addresses never change. A preview whose worked-out address is already taken gets its date
// (the pipeline picks its real one at publish: common.assign_slugs).
for (const pick of [(s: Saint) => s as Text, (s: Saint) => s.es] as ((s: Saint) => Text | null)[]) {
  const seen = new Set<string>();
  for (const s of all) { const t = pick(s); if (t?.fixed) seen.add(t.slug); }
  for (const s of all) {
    const t = pick(s);
    if (!t || t.fixed) continue;
    if (seen.has(t.slug)) t.slug = `${t.slug}-${s.date}`;
    seen.add(t.slug);
  }
}

export const saints = all;
export const saintsIn = (lang: Lang) => all.map((s) => inLang(s, lang)).filter((s): s is Saint & Text => !!s);
export const latest = (lang: Lang = "en") => saintsIn(lang).at(-1);
export const neighbors = (s: Saint, lang: Lang = "en") => {
  const list = saintsIn(lang);
  const i = list.findIndex((x) => x.id === s.id);
  return { prev: list[i - 1], next: list[i + 1] };
};
