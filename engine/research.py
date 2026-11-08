"""Source gathering (Wikipedia + Catholic references linked from Wikidata) and saint selection."""
import html, json, random, re, urllib.parse
from html.parser import HTMLParser
from common import get_json, http, DATA, log, claude_json, load_config, load_episodes, month_day_label

WP = "https://en.wikipedia.org/w/api.php"
WS = "https://en.wikisource.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"

# Catholic references Wikidata links by ID, most authoritative first: (property, title, URL pattern).
# Some are Italian/French/German; the writer reads them and the prompt says so.
CATHOLIC_REFS = [
    ("P3241", "Catholic Encyclopedia (1913)", "https://www.newadvent.org/cathen/{}.htm"),
    ("P9588", "Dicastery for the Causes of Saints", "https://www.causesanti.va/it/santi-e-beati/{}.html"),
    ("P6126", "Santi e Beati", "https://www.santiebeati.it/dettaglio/{}"),
    ("P4286", "Nominis (Église catholique en France)", "https://nominis.cef.fr/contenus/saint/{}.html"),
    ("P8080", "Ökumenisches Heiligenlexikon", "https://www.heiligenlexikon.de/Biographien{}"),
]
MAX_REFS = 4
REF_CHARS = 8000


def _extract(api, title, intro=False):
    p = {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title, "format": "json"}
    if intro:
        p["exintro"] = 1
    r = get_json(api, p)
    page = next(iter(r["query"]["pages"].values()))
    return page.get("extract", "") or ""


def wiki_intro(title):
    return _extract(WP, title.replace("_", " "), intro=True)


def wiki_full(title):
    return _extract(WP, title.replace("_", " "))


def catholic_encyclopedia(name):
    q = name.replace("Saint ", "").replace("St. ", "")
    r = get_json(WS, {"action": "query", "list": "search", "srsearch": f'"{q}" intitle:"Catholic Encyclopedia (1913)"',
                             "srlimit": 5, "format": "json"})
    ql = q.lower()
    for hit in r.get("query", {}).get("search", []):
        t = hit["title"]
        if not t.startswith("Catholic Encyclopedia (1913)/St"):
            continue
        # saint articles are "St. Name[ of Place]": accept the exact name, or a bare-name article
        leaf = re.sub(r"^(st\.|sts\.|saint)\s+", "", t.split("/", 1)[1].lower())
        if leaf.startswith(ql) or (leaf == ql.split()[0]):
            txt = _extract(WS, t)
            if len(txt) > 300:
                return t, txt
    return None, ""


class _Text(HTMLParser):
    """Visible page text, minus scripts, menus and footers."""
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "form", "aside", "select"}
    BREAK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "blockquote"}

    def __init__(self):
        super().__init__()
        self.out, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag in self.BREAK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.out.append(data)


def page_text(url):
    r = http.get(url, timeout=30)
    r.raise_for_status()
    p = _Text()
    p.feed(r.text)
    txt = re.sub(r"[ \t\xa0]+", " ", html.unescape("".join(p.out)))
    return re.sub(r"\n\s*\n+", "\n", txt).strip()


def catholic_ref_ids(qids):
    """{qid: [(property, id), ...]} for the CATHOLIC_REFS each saint has on Wikidata (one call per 50)."""
    out = {}
    qids = [q for q in qids if q]
    for i in range(0, len(qids), 50):
        r = get_json(WD, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "claims", "format": "json"})
        for q, e in r.get("entities", {}).items():
            claims = e.get("claims", {})
            out[q] = [(p, claims[p][0]["mainsnak"]["datavalue"]["value"]) for p, _, _ in CATHOLIC_REFS
                      if claims.get(p) and claims[p][0]["mainsnak"].get("datavalue")]
    return out


def catholic_refs(saint):
    """Catholic reference texts for this saint, found through its Wikidata IDs."""
    ids = dict(catholic_ref_ids([saint["qid"]]).get(saint["qid"], []))
    src = []
    for prop, title, pattern in CATHOLIC_REFS:
        if prop not in ids or len(src) >= MAX_REFS:
            continue
        url = pattern.format(ids[prop])
        try:
            txt = page_text(url)
        except Exception as e:
            log(f"{title} fetch failed:", e)
            continue
        if len(txt) > 500:
            src.append({"title": f"{title}: {saint['name']}", "url": url, "text": txt[:REF_CHARS]})
    return src


def wikipedia_only(sources):
    return all(s["url"].startswith("https://en.wikipedia.org/") for s in sources)


def gather_sources(saint):
    """Return list of {title,url,text} for the research prompt."""
    src = []
    full = wiki_full(saint["enwiki"])
    src.append({"title": f"Wikipedia: {urllib.parse.unquote(saint['enwiki']).replace('_', ' ')}",
                "url": f"https://en.wikipedia.org/wiki/{saint['enwiki']}", "text": full[:14000]})
    try:
        src += catholic_refs(saint)
    except Exception as e:
        log("Catholic reference lookup failed:", e)
    # Wikidata often lacks the Catholic Encyclopedia ID; fall back to a Wikisource title search
    if not any(s["title"].startswith("Catholic Encyclopedia") for s in src):
        try:
            t, txt = catholic_encyclopedia(saint["name"])
            if t:
                src.append({"title": t, "url": "https://en.wikisource.org/wiki/" + t.replace(" ", "_"), "text": txt[:10000]})
        except Exception as e:
            log("Catholic Encyclopedia lookup failed:", e)
    log("Sources:", ", ".join(s["title"].split(":")[0] for s in src))
    return src


def used_qids():
    return {e.get("saint", {}).get("qid") for e in load_episodes().values() if e.get("status") not in ("rejected",)}


def recent_summary(n=10):
    eps = sorted(load_episodes().values(), key=lambda e: e["date"])[-n:]
    return "\n".join(f"- {e['date']}: {e.get('saint', {}).get('name')} ({e.get('saint', {}).get('region', '')})" for e in eps) or "(none yet)"


def select_saint(date, exclude=(), angle=None):
    cal = json.loads((DATA / "calendar.json").read_text())
    key = date.strftime("%m-%d")
    used = used_qids() | set(exclude)
    # Luis's pins (config "pins": {"2026-12-17": "Q470597"}) skip the editor pick; the saint may sit on any calendar day
    pin = load_config().get("pins", {}).get(date.strftime("%Y-%m-%d"))
    if pin and pin not in used:
        pick = next((dict(c) for day in cal.values() for c in day if c["qid"] == pin), None)
        if pick:
            pick["selection_reason"] = "Pinned by the editor for this date."
            pick["catholic_veneration"] = ""
            log(f"Pinned {pick['name']} for {key}")
            return pick
        log(f"Pin {pin} not in calendar.json; choosing as usual")
    cands =[c for c in cal.get(key, []) if c["qid"] not in used and 2 <= c["links"] <= 45]
    if not cands:
        cands = [c for c in cal.get(key, []) if c["qid"] not in used]
    if not cands:
        raise RuntimeError(f"No candidates for {key}")
    # prefer ones with images / commons categories
    cands.sort(key=lambda c: (-(bool(c.get("images")) + bool(c.get("commonscat"))), abs(c["links"] - 15)))
    shortlist = cands[:12]
    for c in shortlist:
        try:
            c["intro"] = wiki_intro(c["enwiki"])[:900]
        except Exception:
            c["intro"] = ""
    try:
        refs = catholic_ref_ids([c["qid"] for c in shortlist])
    except Exception as e:
        log("Catholic reference lookup failed:", e)
        refs = {}
    names = {p: t for p, t, _ in CATHOLIC_REFS}
    cfg = load_config()
    listing = "\n\n".join(
        f"[{i}] {c['name']} (qid {c['qid']}, {c['links']} wiki languages, images: {'yes' if c.get('images') or c.get('commonscat') else 'no'}, "
        f"Catholic references: {', '.join(names[p] for p, _ in refs.get(c['qid'], [])) or 'none'})\n{c['intro']}"
        for i, c in enumerate(shortlist))
    prompt = f"""You are the editor of "All Saints" (A.S.†), an Instagram Reels series of one-minute, reverent lives of lesser-known Catholic saints, posted on their feast day.

Feast day: {month_day_label(date)}
Editorial scope: {cfg['scope']}
{(angle['select'] + chr(10)) if angle else ''}
Recently published (avoid repeating the same region/era/type back-to-back):
{recent_summary()}

Candidates:
{listing}

Pick the ONE candidate that will make the most moving, surprising, well-documented one-minute story (strongly prefer candidates with Catholic references: they are the sources the facts get checked against), who is genuinely venerated as a saint in the Catholic Church (Latin or Eastern Catholic). Reject anyone venerated only by Orthodox, Anglican or other non-Catholic churches, anyone whose cult was suppressed, and anyone too famous (household names).
Return JSON: {{"index": <int>, "reason": "<one sentence>", "catholic_veneration": "<how they are venerated: Roman Martyrology / Eastern Catholic calendar / etc.>"}}"""
    res = claude_json(prompt, label="select")
    pick = shortlist[int(res["index"])]
    pick["selection_reason"] = res.get("reason")
    pick["catholic_veneration"] = res.get("catholic_veneration")
    log(f"Selected {pick['name']} for {key}: {res.get('reason')}")
    return pick
