"""Find freely licensed sacred art on Wikimedia Commons and assign it to beats with Claude vision."""
import base64, io, re, html
from PIL import Image
from common import http, get_json, log, claude_json

API = "https://commons.wikimedia.org/w/api.php"
OK_LICENSE = re.compile(r"public domain|^pd|cc0|cc[ -]by(-sa)?[ -]\d|cc[ -]by(-sa)?$", re.I)
BAD_LICENSE = re.compile(r"\bnc\b|\bnd\b|fair use|non-commercial", re.I)
BAD_NAME = re.compile(r"\.(svg|gif|pdf|djvu|webm|ogv|ogg|mp3|tif)$|coat[_ ]of[_ ]arms|\bmap\b|\blogo\b|signature|\bstamp\b|\bcoin\b|\bseal\b|\bplan\b|diagram", re.I)


def _get(params):
    params = {**params, "format": "json", "formatversion": 2}
    return get_json(API, params)


def category_files(cat, depth=1, limit=60):
    titles, cats = [], [f"Category:{cat}"]
    seen = set()
    for level in range(depth + 1):
        nxt = []
        for c in cats:
            if c in seen:
                continue
            seen.add(c)
            r = _get({"action": "query", "list": "categorymembers", "cmtitle": c, "cmlimit": 100, "cmtype": "file|subcat"})
            for m in r.get("query", {}).get("categorymembers", []):
                if m["ns"] == 6:
                    titles.append(m["title"])
                elif m["ns"] == 14 and level < depth:
                    nxt.append(m["title"])
            if len(titles) >= limit:
                return titles[:limit]
        cats = nxt[:8]
    return titles[:limit]


def search_files(q, limit=8):
    r = _get({"action": "query", "list": "search", "srsearch": f"{q} filetype:bitmap", "srnamespace": 6, "srlimit": limit})
    return [h["title"] for h in r.get("query", {}).get("search", [])]


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
    return re.sub(r"\s+", " ", s)


def image_info(titles, width=1600):
    out = {}
    titles = [t for t in dict.fromkeys(titles) if not BAD_NAME.search(t)]
    for i in range(0, len(titles), 40):
        r = _get({"action": "query", "titles": "|".join(titles[i:i + 40]), "prop": "imageinfo",
                  "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width})
        for p in r.get("query", {}).get("pages", []):
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            md = ii.get("extmetadata", {})
            lic = _clean(md.get("LicenseShortName", {}).get("value", ""))
            if not OK_LICENSE.search(lic) or BAD_LICENSE.search(lic):
                continue
            if ii.get("mime") not in ("image/jpeg", "image/png") or min(ii["width"], ii["height"]) < 700:
                continue
            artist = _clean(md.get("Artist", {}).get("value", ""))[:60]
            date = _clean(md.get("DateTimeOriginal", {}).get("value", ""))[:30]
            name = _clean(md.get("ObjectName", {}).get("value", "")) or p["title"][5:].rsplit(".", 1)[0]
            out[p["title"]] = {
                "title": p["title"], "thumb": ii.get("thumburl") or ii["url"], "w": ii["width"], "h": ii["height"],
                "license": lic, "artist": artist, "date": date, "name": name[:90],
                "page": ii.get("descriptionurl"),
                "desc": _clean(md.get("ImageDescription", {}).get("value", ""))[:200],
            }
    return out


def collect_candidates(saint, script, max_n=28):
    titles = []
    titles += ["File:" + f.replace("_", " ") for f in saint.get("images", [])]
    if saint.get("commonscat"):
        try:
            titles += category_files(saint["commonscat"])
        except Exception as e:
            log("category fetch failed", e)
    short = re.sub(r"^(Saint|St\.?|Saints)\s+", "", saint["name"])
    queries = [f'"{short}" saint', f"{short} icon", f"{short} painting"]
    for b in script["beats"]:
        if b.get("visual") == "art" and b.get("art_hint"):
            queries.append(b["art_hint"].split(":")[-1][:80])
    for q in queries:
        try:
            titles += search_files(q)
        except Exception as e:
            log("search failed", q, e)
    info = image_info(titles)
    # keep order: wikidata image first, category, then searches
    cands = [info[t] for t in dict.fromkeys(titles) if t in info]
    return cands[:max_n]


def _thumb_b64(url, size=420):
    raw = http.get(url, timeout=60).content
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def assign_art(saint, script, cands):
    """Ask Claude (vision) to pick images per art beat, with focus points."""
    imgs, usable = [], []
    for c in cands:
        try:
            b64 = _thumb_b64(c["thumb"])
        except Exception as e:
            log("thumb failed", c["title"], e)
            continue
        usable.append(c)
        imgs.append({"type": "text", "text": f"Image {len(usable) - 1}: {c['name']} — {c['artist']} {c['date']} ({c['desc'][:120]})"})
        imgs.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    beats = [{"i": i, "role": b["role"], "text": b["text"], "hint": b.get("art_hint", "")}
             for i, b in enumerate(script["beats"]) if b.get("visual") == "art"]
    prompt = f"""These are freely licensed images found for an episode about {saint['name']} ({script['saint'].get('dates', '')}, {script['saint'].get('region', '')}).
Art beats needing an image:
{beats}

Choose images for a reverent, beautiful vertical (9:16) video. Rules:
- Prefer paintings, icons, frescoes, mosaics, manuscript illuminations, or fine photos of historic churches/places tied to the story. Reject modern clip-art, low quality scans, text-heavy pages, maps, unrelated saints, anything irreverent.
- The hook beat needs the most striking image. Portraits/icons of the saint suit the "who"/"turn" beats.
- An image may be used at most twice (with different focus points). Each beat must get an image if any acceptable image exists.
- focus: normalized (x,y) of the key subject (usually the saint's face) so the vertical crop keeps it; move: one of in, out, left, right, up, down (slow camera move that suits the composition; use left/right for wide images).
Return ONLY JSON: {{"beats": [{{"i": <beat index>, "image": <image number>, "focus": {{"x": 0.5, "y": 0.35}}, "move": "in"}}], "cover": {{"image": <n>, "focus": {{"x":0.5,"y":0.35}}}}, "close_bg": <n>, "rejected": [<n>...], "quality": "good|thin|none"}}"""
    res = claude_json(prompt, images=imgs)
    return usable, res


def download(url, path, width=2000):
    url = re.sub(r"/(\d+)px-", f"/{width}px-", url)
    r = http.get(url, timeout=120)
    if r.status_code != 200:
        r = http.get(re.sub(r"/\d+px-", "/1600px-", url), timeout=120)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if max(im.size) > 2400:
        im.thumbnail((2400, 2400))
    im.save(path, "JPEG", quality=90)
    return im.size


def credit_line(c):
    who = c["artist"] or "Unknown artist"
    lic = "Public domain" if re.search(r"public domain|^pd|cc0", c["license"], re.I) else c["license"]
    return f"{c['name']} — {who}{(', ' + c['date']) if c['date'] and c['date'] not in c['name'] else ''} · {lic}"
