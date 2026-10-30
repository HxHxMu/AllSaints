// Episodes come straight from the pipeline's state files. Only published ones reach the site;
// SITE_ALL=1 (local preview) also shows episodes still in review/approved.
const files = import.meta.glob<any>("../../../state/episodes/*.json", { eager: true, import: "default" });
const art = import.meta.glob<{ default: ImageMetadata }>("../assets/art/*.jpg", { eager: true });
import config from "../../../state/config.json";
import brand from "../../../brand/brand.json";

export const SUPPORT_URL: string = (config as any).support_url || "";
export const DISCLOSURE: string = (brand as any).youtube?.disclosure || "";
export const TAGLINE: string = (brand as any).tagline;

const showAll = process.env.SITE_ALL === "1";
const visible = new Set(showAll ? ["published", "approved", "review", "publishing"] : ["published"]);

export type Saint = {
  id: string; date: string; slug: string; name: string; display: string; dates: string; region: string;
  martyr: boolean; hook: string; summary: string; story: string[]; prayer: string;
  youtubeId: string | null; duration: number | null; sources: { title: string; url?: string }[];
  credits: string[]; cover: string | null; art: ImageMetadata | null;
};

const ROMAN: [number, string][] = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
export const roman = (n: number) => ROMAN.reduce((s, [v, r]) => { while (n >= v) { s += r; n -= v; } return s; }, "");
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const monthName = (iso: string) => MONTHS[Number(iso.slice(5, 7)) - 1];
export const manuscriptDate = (iso: string) => `${roman(Number(iso.slice(8, 10)))} · ${monthName(iso)}`;
export const minutes = (s: number | null) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "");

const slugify = (name: string) =>
  name.replace(/^(Saints?|Sts?\.)\s+/i, "").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function toSaint(ep: any): Saint {
  const s = ep.script, saint = s.saint;
  const beats: any[] = s.beats || [];
  const close = beats.find((b) => b.role === "close")?.text || `${saint.name}, pray for us.`;
  return {
    id: ep.id, date: ep.date, slug: slugify(saint.name), name: saint.name,
    display: saint.display_name || saint.name, dates: saint.dates || "", region: saint.region || "",
    martyr: !!saint.martyr, hook: s.caption_hook || beats[0]?.text || "", summary: s.summary || "",
    // the long-form story replaces the narration beats once the pipeline writes it (ep.story)
    story: ep.story?.paragraphs || beats.filter((b) => !["hook", "close"].includes(b.role)).map((b) => b.text),
    prayer: close,
    youtubeId: ep.youtube?.id || null,
    duration: ep.duration || null, sources: ep.sources || [], credits: [...new Set<string>(ep.art_credits || [])],
    cover: ep.assets?.["cover.jpg"] || null, art: art[`../assets/art/${ep.id}.jpg`]?.default || null,
  };
}

const all: Saint[] = Object.values(files)
  .filter((ep) => ep?.script && /^\d{4}-\d{2}-\d{2}$/.test(ep.id) && visible.has(ep.status)) // skips the channel intro
  .map(toSaint)
  .sort((a, b) => a.date.localeCompare(b.date));

// two different saints with the same name get the date appended
const seen = new Map<string, number>();
for (const s of all) seen.set(s.slug, (seen.get(s.slug) || 0) + 1);
for (const s of all) if ((seen.get(s.slug) || 0) > 1) s.slug = `${s.slug}-${s.date.slice(0, 4)}`;

export const saints = all;
export const latest = () => all[all.length - 1];
export const neighbors = (s: Saint) => {
  const i = all.findIndex((x) => x.id === s.id);
  return { prev: all[i - 1], next: all[i + 1] };
};
