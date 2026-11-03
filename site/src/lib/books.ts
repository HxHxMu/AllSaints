// "Go deeper": the saint's own books (ep.books, found by engine/books.py) first, then the best matches from the
// curated shelf (brand/books.json), 3 in all. Links carry the Bookshop.org affiliate id (config
// "bookshop_affiliate_id"); without it the section isn't rendered.
import config from "../../../state/config.json";
import data from "../../../brand/books.json";
import { saintsIn, type Saint, type Text } from "./episodes";

export type Book = { title: string; author: string; isbn: string };
// covers downloaded at build time (scripts/fetch-covers.mjs); null = no cover anywhere, the page typesets one
const covers = import.meta.glob<{ default: ImageMetadata }>("../assets/books/*.jpg", { eager: true });
export const coverOf = (b: Book) => covers[`../assets/books/${b.isbn}.jpg`]?.default || null;
export const AFFILIATE: string = (config as any).bookshop_affiliate_id || "";
export const bookUrl = (b: Book) => `https://bookshop.org/a/${AFFILIATE}/${b.isbn}`;
const SHELF = (data as any).shelf as (Book & { tags: string[] })[];

// era from the death year at the end of "c. 250 – 298"
const era = (dates: string) => {
  const years = (dates.match(/\d{3,4}/g) || []).map(Number);
  const died = years.at(-1);
  return !died ? null : died < 600 ? "early" : died <= 1500 ? "medieval" : "modern";
};

// small stable hash so equal-scoring books vary from page to page instead of always the same three
const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

export function booksFor(s: { id: string; dates: string; martyr: boolean; continent: string | null; books: Book[] }): Book[] {
  if (!AFFILIATE) return [];
  // a specific book needs the saint's continent or martyrdom in common; era only breaks ties. General books fill the rest.
  const e = era(s.dates);
  const ERAS = ["early", "medieval", "modern"];
  const score = (b: { tags: string[] }) => {
    const has = (t: string | null) => !!t && b.tags.includes(t);
    if (e && b.tags.some((t) => ERAS.includes(t)) && !has(e)) return 0; // a book about another era
    if (b.tags.includes("Asia") && !has(s.continent)) return 0; // the one book that is only about one place
    const base = (has(s.continent) ? 2 : 0) + (s.martyr && has("martyr") ? 1 : 0) || (has("general") ? 0.75 : 0);
    return base && base + (has(e) ? 0.25 : 0);
  };
  const own = s.books.slice(0, 2);
  const picks = SHELF.filter((b) => !own.some((o) => o.isbn === b.isbn))
    .map((b) => ({ b, score: score(b), tie: hash(s.id + b.isbn) }))
    .filter((x) => x.score > 0)
    .sort((x, y) => y.score - x.score || x.tie - y.tie)
    .map((x) => x.b);
  return [...own, ...picks].slice(0, 3);
}

// The library (/library/): every book on the shelf plus each saint's own books, grouped by theme, each with the
// saints whose "Go deeper" recommends it. A book sits in the first section whose test it passes.
export type Shelved = Book & { saints: (Saint & Text)[] };
const SECTIONS: { title: string; test: (b: Book & { tags?: string[] }) => boolean }[] = [
  { title: "Lives of the saints", test: (b) => !!b.tags?.some((t) => t === "general" || t === "legend") },
  { title: "The early Church and the desert", test: (b) => !!b.tags?.includes("early") },
  { title: "Saints of the world", test: (b) => !!b.tags?.length },
  { title: "On a single saint", test: () => true },
];

export function library(): { title: string; books: Shelved[] }[] {
  if (!AFFILIATE) return [];
  const by = new Map<string, Shelved & { tags?: string[] }>();
  for (const b of SHELF) by.set(b.isbn, { ...b, saints: [] });
  for (const s of saintsIn("en")) {
    for (const b of s.books) if (!by.has(b.isbn)) by.set(b.isbn, { ...b, saints: [] });
    for (const b of booksFor(s)) by.get(b.isbn)?.saints.push(s);
  }
  const left = [...by.values()];
  return SECTIONS.map((sec) => {
    const books = left.filter((b) => sec.test(b));
    for (const b of books) left.splice(left.indexOf(b), 1);
    return { title: sec.title, books };
  }).filter((sec) => sec.books.length > 0);
}
