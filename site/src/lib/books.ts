// "Go deeper": the saint's own books (ep.books, found by engine/books.py) first, then the best matches from the
// curated shelf (brand/books.json), 3 in all. Links carry the Bookshop.org affiliate id (config
// "bookshop_affiliate_id"); without it the section isn't rendered.
import config from "../../../state/config.json";
import data from "../../../brand/books.json";

export type Book = { title: string; author: string; isbn: string };
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
