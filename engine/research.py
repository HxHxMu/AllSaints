"""Source gathering (Wikipedia, Catholic Encyclopedia 1913 via Wikisource) and saint selection."""
import json, random, re
from common import http, DATA, log, claude_json, load_config, load_episodes, month_day_label

WP = "https://en.wikipedia.org/w/api.php"
WS = "https://en.wikisource.org/w/api.php"


def _extract(api, title, intro=False):
    p = {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title, "format": "json"}
    if intro:
        p["exintro"] = 1
    r = http.get(api, params=p, timeout=30).json()
    page = next(iter(r["query"]["pages"].values()))
    return page.get("extract", "") or ""


def wiki_intro(title):
    return _extract(WP, title.replace("_", " "), intro=True)


def wiki_full(title):
    return _extract(WP, title.replace("_", " "))


def catholic_encyclopedia(name):
    q = name.replace("Saint ", "").replace("St. ", "")
    r = http.get(WS, params={"action": "query", "list": "search", "srsearch": f'"{q}" intitle:"Catholic Encyclopedia (1913)"',
                             "srlimit": 5, "format": "json"}, timeout=30).json()
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


def gather_sources(saint):
    """Return list of {title,url,text} for the research prompt."""
    src = []
    full = wiki_full(saint["enwiki"])
    src.append({"title": f"Wikipedia: {saint['enwiki'].replace('_', ' ')}",
                "url": f"https://en.wikipedia.org/wiki/{saint['enwiki']}", "text": full[:14000]})
    try:
        t, txt = catholic_encyclopedia(saint["name"])
        if t:
            src.append({"title": t, "url": "https://en.wikisource.org/wiki/" + t.replace(" ", "_"), "text": txt[:10000]})
    except Exception as e:
        log("Catholic Encyclopedia lookup failed:", e)
    return src


def used_qids():
    return {e.get("saint", {}).get("qid") for e in load_episodes().values() if e.get("status") not in ("rejected",)}


def recent_summary(n=10):
    eps = sorted(load_episodes().values(), key=lambda e: e["date"])[-n:]
    return "\n".join(f"- {e['date']}: {e.get('saint', {}).get('name')} ({e.get('saint', {}).get('region', '')})" for e in eps) or "(none yet)"


def select_saint(date, exclude=()):
    cal = json.loads((DATA / "calendar.json").read_text())
    key = date.strftime("%m-%d")
    used = used_qids() | set(exclude)
    cands = [c for c in cal.get(key, []) if c["qid"] not in used and 2 <= c["links"] <= 45]
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
    cfg = load_config()
    listing = "\n\n".join(
        f"[{i}] {c['name']} (qid {c['qid']}, {c['links']} wiki languages, images: {'yes' if c.get('images') or c.get('commonscat') else 'no'})\n{c['intro']}"
        for i, c in enumerate(shortlist))
    prompt = f"""You are the editor of "All Saints" (A.S.†), an Instagram Reels series of one-minute, reverent lives of lesser-known Catholic saints, posted on their feast day.

Feast day: {month_day_label(date)}
Editorial scope: {cfg['scope']}

Recently published (avoid repeating the same region/era/type back-to-back):
{recent_summary()}

Candidates:
{listing}

Pick the ONE candidate that will make the most moving, surprising, well-documented one-minute story, who is genuinely venerated as a saint in the Catholic Church (Latin or Eastern Catholic). Reject anyone venerated only by Orthodox, Anglican or other non-Catholic churches, anyone whose cult was suppressed, and anyone too famous (household names).
Return JSON: {{"index": <int>, "reason": "<one sentence>", "catholic_veneration": "<how they are venerated: Roman Martyrology / Eastern Catholic calendar / etc.>"}}"""
    res = claude_json(prompt)
    pick = shortlist[int(res["index"])]
    pick["selection_reason"] = res.get("reason")
    pick["catholic_veneration"] = res.get("catholic_veneration")
    log(f"Selected {pick['name']} for {key}: {res.get('reason')}")
    return pick
