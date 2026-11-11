// The day pages (/calendar/november-11/, /es/calendario/11-de-noviembre/): every day of the year, with the
// saints All Saints has remembered on it and the other Catholic saints of that feast (data/feasts.json,
// built by engine/feasts_build.py from Wikidata and kept only when a Catholic hagiography lists them).
import feasts from "../../../data/feasts.json";
import { saintsIn, monthName, type Lang } from "./episodes";

export interface Feast {
  qid: string; name: string; name_es: string; desc: string; desc_es: string;
  enwiki: string | null; eswiki: string | null; ref: { title: string; url: string };
  birth: number | null; death: number | null;
}

const table = feasts as Record<string, Feast[]>;
// a leap year, so February 29 gets its page
export const days = Array.from({ length: 366 }, (_, i) => new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(5, 10));

const iso = (key: string) => `2024-${key}`;
const num = (key: string) => Number(key.slice(3));
export const dayLabel = (key: string, lang: Lang) =>
  lang === "es" ? `${num(key)} de ${monthName(iso(key), lang)}` : `${monthName(iso(key))} ${num(key)}`;
export const daySlug = (key: string, lang: Lang) =>
  lang === "es" ? `${num(key)}-de-${monthName(iso(key), lang)}` : `${monthName(iso(key)).toLowerCase()}-${num(key)}`;

export function day(key: string, lang: Lang) {
  // the saints we made a video about on this date (any year, newest first), then the rest of the day's saints
  const ours = saintsIn(lang).filter((s) => s.date.slice(5) === key).reverse();
  const told = new Set(ours.map((s) => s.qid));
  const others = (table[key] || []).filter((f) => !told.has(f.qid));
  const i = days.indexOf(key);
  return { key, ours, others, prev: days[(i + 365) % 366], next: days[(i + 1) % 366] };
}

const year = (y: number, lang: Lang) => (y < 0 ? `${-y} ${lang === "es" ? "a. C." : "BC"}` : String(y));
export const lifespan = (f: Feast, lang: Lang) =>
  f.birth != null && f.death != null ? `${year(f.birth, lang)}–${year(f.death, lang)}`
    : f.death != null ? `† ${year(f.death, lang)}` : "";

export function wiki(f: Feast, lang: Lang) {
  const [site, title] = lang === "es" && f.eswiki ? ["es", f.eswiki] : ["en", f.enwiki];
  return title ? `https://${site}.wikipedia.org/wiki/${encodeURIComponent(title.replace(/ /g, "_"))}` : null;
}
