"""Build data/feasts.json: the saints listed on the website's day pages (/calendar/november-11/).

Reads data/calendar.json (Wikidata, unchecked) and keeps only saints a Catholic hagiography
source has on record, so the Orthodox-only and other non-Catholic entries Wikidata tags as saints
stay off a Catholic site. Adds Spanish names, one-line descriptions and Wikipedia links.
Runs after build-calendar (monthly).
"""
import json, re
from common import DATA, get_json, http, log
from calendar_build import parse_day

WD = "https://www.wikidata.org/w/api.php"
# Catholic sources that list a saint as venerated (the Catholic Encyclopedia and the ecumenical
# Heiligenlexikon also cover non-Catholic saints, so they don't count here)
REFS = [
    ("P6126", "Santi e Beati", "https://www.santiebeati.it/dettaglio/{}"),
    ("P9588", "Dicastero delle Cause dei Santi", "https://www.causesanti.va/it/santi-e-beati/{}.html"),
    ("P4286", "Nominis", "https://nominis.cef.fr/contenus/saint/{}.html"),
]
# Wikidata descriptions that say nothing a reader can use
EMPTY = re.compile(r"^(|saint|santo|santa|san|catholic saint|christian saint|santo católico|santa católica|santo cristiano|"
                   r"santa cristiana|santo de la iglesia católica|wikimedia .*)$", re.I)
PREFIX = re.compile(r"^(Saints?|Sts?\.|Santos?|Santas?|San)\s+")
# a feast date Wikidata ties to a church (religion / "statement supported by") counts only if one of them is Catholic:
# Philip the Apostle's November 14 is the Orthodox date (Catholics keep May 3)
CHURCH_QUALIFIERS = ("P140", "P3680")
CATHOLIC = {"Q9592", "Q1841"}  # Catholic Church, Catholicism
# Wikidata tags some Blesseds "Catholic saint" too (Alicja Kotowska), and real saints keep an old "blessed"; for anyone
# tagged blessed / venerable / servant of God, the Catholic source's own page title decides ("Beata …" stays off)
UNSURE = {"Q2369287", "Q12774503", "Q51619", "Q869974"}
NOT_SAINT = re.compile(r"^\s*(beat[oaie]|bienheureu|venerabil|vénérable|serv[oa] di dio|serviteur|servante)", re.I)
# "Polish nun (1899-1939)": the dates already show beside it
YEARS = re.compile(r"\s*\((?:c\.\s*)?[\d/–\- c.]+\)$")


def entities(qids):
    out = {}
    for i in range(0, len(qids), 50):
        r = get_json(WD, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "format": "json",
                          "props": "labels|descriptions|claims|sitelinks", "languages": "en|es", "sitefilter": "enwiki|eswiki"})
        out.update(r.get("entities", {}))
    return out


def text(e, key, lang):
    return (e.get(key, {}).get(lang) or {}).get("value") or ""


def other_church_days(ents):
    """{qid: {"11-14", ...}}: feast dates Wikidata gives only for a non-Catholic church."""
    tagged = {}
    for q, e in ents.items():
        for c in e.get("claims", {}).get("P841", []):
            day = (c["mainsnak"].get("datavalue") or {}).get("value", {}).get("id")
            churches = {(x.get("datavalue") or {}).get("value", {}).get("id") for p in CHURCH_QUALIFIERS for x in c.get("qualifiers", {}).get(p, [])}
            churches.discard(None)
            if day and churches and not churches & CATHOLIC:
                tagged.setdefault(q, set()).add(day)
    items = sorted({d for days in tagged.values() for d in days})
    labels = {}
    for i in range(0, len(items), 50):
        r = get_json(WD, {"action": "wbgetentities", "ids": "|".join(items[i:i + 50]), "props": "labels", "languages": "en", "format": "json"})
        labels.update({k: parse_day(v.get("labels", {}).get("en", {}).get("value", "")) for k, v in r.get("entities", {}).items()})
    return {q: {labels[d] for d in days if labels.get(d)} for q, days in tagged.items()}


def canonized(url):
    """False when the source page names a Blessed, Venerable or Servant of God; None if it can't be read."""
    try:
        r = http.get(url, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
    except Exception:
        return None
    m = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
    return bool(m) and not NOT_SAINT.match(m.group(1))


def clean(desc):
    desc = YEARS.sub("", desc).strip()
    return "" if EMPTY.match(desc) else desc


def main():
    cal = json.loads((DATA / "calendar.json").read_text())
    qids = sorted({s["qid"] for day in cal.values() for s in day})
    log(f"Reading {len(qids)} saints from Wikidata…")
    ents = entities(qids)
    people = {}
    for q, e in ents.items():
        claims = e.get("claims", {})
        ref = next(((title, url.format(claims[p][0]["mainsnak"]["datavalue"]["value"])) for p, title, url in REFS
                    if claims.get(p) and claims[p][0]["mainsnak"].get("datavalue")), None)
        if not ref:
            continue
        name = text(e, "labels", "en")
        if not name or re.match(r"^Q\d+$", name):
            continue
        status = {(c["mainsnak"].get("datavalue") or {}).get("value", {}).get("id") for c in claims.get("P411", [])}
        if status & UNSURE and not canonized(ref[1]):  # unreadable counts as not shown: accuracy first
            log(f"Not listed (not a canonized saint, or the source didn't load): {name}")
            continue
        desc = {l: clean(text(e, "descriptions", l)) for l in ("en", "es")}
        links = {l: (e.get("sitelinks", {}).get(f"{l}wiki") or {}).get("title") for l in ("en", "es")}
        people[q] = {
            "qid": q, "name": PREFIX.sub("", name), "name_es": PREFIX.sub("", text(e, "labels", "es") or name),
            "desc": desc["en"], "desc_es": desc["es"],
            "enwiki": links["en"], "eswiki": links["es"], "ref": {"title": ref[0], "url": ref[1]},
        }
    skip = other_church_days(ents)
    out = {}
    for day, saints in cal.items():
        rows = []
        for s in saints:
            p = people.get(s["qid"])
            if p and day not in skip.get(s["qid"], ()):
                rows.append({**p, "birth": s.get("birth"), "death": s.get("death")})
        # oldest first, like a martyrology; undated saints last
        rows.sort(key=lambda r: (r["death"] is None, r["death"] or 0, r["name"]))
        out[day] = rows
    (DATA / "feasts.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
    n = sum(len(v) for v in out.values())
    log(f"Wrote data/feasts.json: {n} saints on {sum(1 for v in out.values() if v)} days (of {len(qids)} in the calendar)")


if __name__ == "__main__":
    main()
