"""Build data/calendar.json: candidate saints per feast day from Wikidata.

Run occasionally (e.g. monthly). Popularity proxy = number of Wikipedia sitelinks;
lesser-known saints sit roughly in the 2-45 range.
"""
import json, re, collections
from common import http, DATA, log

SPARQL = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?s ?sLabel ?feastLabel ?links ?article ?image ?commonscat ?birth ?death ?coord ?relLabel WHERE {
  # saint · Catholic saint · canonized saint · pre-congregation saint
  VALUES ?status { wd:Q43115 wd:Q3464126 wd:Q123110154 wd:Q18344276 }
  ?s wdt:P411 ?status ;
     wdt:P841 ?feast ;
     wikibase:sitelinks ?links .
  ?article schema:about ?s ; schema:isPartOf <https://en.wikipedia.org/> .
  OPTIONAL { ?s wdt:P18 ?image }
  OPTIONAL { ?s wdt:P373 ?commonscat }
  OPTIONAL { ?s wdt:P569 ?birth }
  OPTIONAL { ?s wdt:P570 ?death }
  OPTIONAL { ?s wdt:P20 ?dp . ?dp wdt:P625 ?coord }
  OPTIONAL { ?s wdt:P140 ?rel }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}


def parse_day(label):
    l = label.lower().strip()
    m = re.match(r"([a-z]+)\s+(\d{1,2})$", l) or re.match(r"(\d{1,2})\s+([a-z]+)$", l)
    if not m:
        return None
    a, b = m.groups()
    month, day = (a, b) if a.isalpha() else (b, a)
    if month not in MONTHS:
        return None
    return f"{MONTHS[month]:02d}-{int(day):02d}"


def year(v):
    if not v:
        return None
    m = re.match(r"(-?)(\d{1,4})-", v.lstrip("+"))
    if not m:
        return None
    y = int(m.group(2))
    return -y if m.group(1) else y


def main():
    log("Querying Wikidata…")
    r = http.get(SPARQL, params={"query": QUERY, "format": "json"}, timeout=300,
                 headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    log(len(rows), "rows")
    people = {}
    for b in rows:
        g = lambda k: b.get(k, {}).get("value")
        qid = g("s").rsplit("/", 1)[-1]
        p = people.setdefault(qid, {"qid": qid, "name": g("sLabel"), "links": int(g("links")),
                                    "enwiki": g("article").rsplit("/wiki/", 1)[-1],
                                    "feasts": set(), "images": set(), "religions": set()})
        d = parse_day(g("feastLabel") or "")
        if d:
            p["feasts"].add(d)
        if g("image"):
            p["images"].add(g("image").rsplit("/", 1)[-1])
        if g("commonscat"):
            p["commonscat"] = g("commonscat")
        if g("relLabel"):
            p["religions"].add(g("relLabel"))
        p["birth"] = p.get("birth") or year(g("birth"))
        p["death"] = p.get("death") or year(g("death"))
        if g("coord") and "lat" not in p:
            m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", g("coord"))
            if m:
                p["lon"], p["lat"] = float(m.group(1)), float(m.group(2))
    cal = collections.defaultdict(list)
    for p in people.values():
        rel = " ".join(p["religions"]).lower()
        if rel and "orthodox" in rel and "catholic" not in rel:
            continue  # Orthodox-only veneration
        for d in p["feasts"]:
            item = {k: (sorted(v) if isinstance(v, set) else v) for k, v in p.items() if k != "feasts"}
            cal[d].append(item)
    for d in cal:
        cal[d].sort(key=lambda x: x["links"])
    out = DATA / "calendar.json"
    out.write_text(json.dumps(dict(sorted(cal.items())), ensure_ascii=False, indent=0))
    log(f"Wrote {out}: {len(cal)} days, {len(people)} saints")


if __name__ == "__main__":
    main()
