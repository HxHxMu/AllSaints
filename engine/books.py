"""Books about one saint for the website's "Go deeper" shelf (Open Library; plain code, no AI).

Only exact matches: the saint's name (without "Saint") must be in the book's title. Most of our saints have
none, and that's fine: the site fills the shelf from brand/books.json. Bookshop.org blocks automated stock
checks, so these are suggestions: they're listed in the Telegram review and `/nobooks <date>` drops them.
"""
import re, unicodedata
from common import http as session, log

SEARCH = "https://openlibrary.org/search.json"
HEADERS = {"User-Agent": "AllSaints/1.0 (https://allholysaints.com; hello@allholysaints.com)"}
MAX = 2


def _fold(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()).strip()


def core_name(name):
    return re.sub(r"^(saints?|sts?\.)\s+", "", name.strip(), flags=re.I)


def _newest_isbn(work_key):
    """ISBN-13 of the most recently published edition (likeliest to be in print)."""
    r = session.get(f"https://openlibrary.org{work_key}/editions.json", params={"limit": 50}, headers=HEADERS, timeout=30)
    best = None
    for e in r.json().get("entries", []) if r.status_code == 200 else []:
        isbn = next((i for i in e.get("isbn_13", []) if i.startswith(("978", "979"))), None)
        year = int(m.group(0)) if (m := re.search(r"\d{4}", e.get("publish_date", ""))) else 0
        if isbn and (not best or year > best[0]):
            best = (year, isbn)
    return best


def find(saint):
    """[{title, author, isbn, year}] for books whose title names this saint; [] when there are none."""
    name = core_name(saint.get("name", ""))
    if len(name) < 4:
        return []
    r = session.get(SEARCH, params={"title": name, "language": "eng", "limit": 10,
                                    "fields": "key,title,subtitle,author_name,first_publish_year"}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    out, want = [], _fold(name)
    # a one-word name ("Winifred") also matches novels and other people: then the title must say "Saint"/"St.",
    # and not "St. Winifred's" (schools, churches)
    pattern = (rf"\b{re.escape(want)}\b" if " " in want else rf"\b(saint|st\.?) {re.escape(want)}\b(?!['’]s)")
    for doc in r.json().get("docs", []):
        title = doc.get("title", "")
        if not re.search(pattern, _fold(f"{title} {doc.get('subtitle', '')}")):
            continue
        newest = _newest_isbn(doc["key"])
        if not newest:
            continue
        title = re.sub(r"\s*\[[^\]]*\]", "", title).strip()  # catalog notes like "[H. Foley]"
        if len(title) > 90 and "," in title[:90]:  # reprints carry the whole title page
            title = title[:title[:90].rindex(",")]
        out.append({"title": title, "author": (doc.get("author_name") or [""])[0], "isbn": newest[1], "year": newest[0]})
        if len(out) == MAX:
            break
    log(f"Books about {name}: {len(out)}")
    return out
