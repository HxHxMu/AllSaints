"""YouTube text for a Short: title, description, tags, the Spanish localization, and the saint's web page address.
Pure functions of the episode (plus config "support_url"); upload and API calls live in youtube.py."""
import datetime as dt, urllib.parse
from common import BRAND, assign_slugs, load_config


def build_title(ep):
    s = ep["script"]
    name = s["saint"].get("display_name") or s["saint"]["name"]
    title = (s.get("youtube_title") or f"{name}, {s['saint'].get('region', '')}".rstrip(", ")).strip()
    if name.split()[-1] not in title:  # the saint's name is what people search for
        title = f"{name}: {title}"
    return (title[:90].rstrip() + " #Shorts")[:100]


def build_description(ep):
    s = ep["script"]
    saint = s["saint"]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    srcs = "\n".join(f"• {urllib.parse.unquote(x['title'])}: {x['url']}" if x.get("url") else f"• {urllib.parse.unquote(x['title'])}" for x in ep.get("sources", []))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", []))) or "public domain"
    from captions import saint_tags, CAP
    tags = " ".join(dict.fromkeys(saint_tags(s, 1) + CAP["hashtags_base"]))  # YouTube shows the first 3 above the title
    share = (s.get("share_cta") or "").strip()
    yt = BRAND.get("youtube", {})
    support = load_config().get("support_url", "").strip()  # Ko-fi page; the line is skipped until it's set
    support = yt.get("support", "{url}").format(url=support) + "\n" if support else ""
    desc = f"""{s.get('caption_hook', '').strip()}

{s.get('summary', '').strip()}

{saint['name']} · {saint.get('dates', '')} · Feast day: {saint.get('feast', '')}

{prayer} 🕯

Read the full story: {page_url(ep)}

—
Sources:
{srcs}
Art: {credits}
{yt.get('disclosure', '')}

{share + chr(10) if share else ''}{support}{yt.get('footer', '')}

{tags} #Shorts"""
    return desc.replace("<", "").replace(">", "")[:4900]  # YouTube rejects angle brackets


SITE = "https://allholysaints.com"


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def page_url(ep, lang="en"):
    assign_slugs(ep)  # the saved address (common.assign_slugs); the caller saves the episode
    if lang == "es":
        return f"{SITE}/es/santos/{ep['es']['slug']}/"
    return f"{SITE}/saints/{ep['slug']}/"


def _short_title(name, text):
    """"Name: text" cut at a word to fit YouTube's 100 characters with " #Shorts"."""
    title = f"{name}: {text}".strip()
    if len(title) > 90:
        title = title[:90].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return title + " #Shorts"


def localizations(ep):
    """The Spanish title and description (ep.es from translate_es), so the Short shows in Spanish searches."""
    es = ep.get("es")
    if not es or not es.get("name"):
        return {}
    s, site_es = ep["script"], BRAND.get("site_es", {})
    d = dt.date.fromisoformat(ep["date"])
    srcs = "\n".join(f"• {urllib.parse.unquote(x['title'])}: {x['url']}" if x.get("url") else f"• {urllib.parse.unquote(x['title'])}" for x in ep.get("sources", []))
    credits = "; ".join(site_es.get("credits", {}).get(c, c) for c in dict.fromkeys(ep.get("art_credits", []))) or "dominio público"
    desc = f"""{es.get('hook', '').strip()}

{es.get('summary', '').strip()}

{es['name']} · {es.get('dates') or s['saint'].get('dates', '')} · Fiesta: {d.day} de {MESES[d.month - 1]}

{es.get('prayer', '').strip()} 🕯

Lee su historia completa: {page_url(ep, 'es')}

—
Fuentes:
{srcs}
Arte: {credits}
{site_es.get('disclosure', '')}

#santos #catolico #Shorts"""
    return {"es": {"title": _short_title(es.get("display_name") or es["name"], es.get("hook", "")),
                   "description": desc.replace("<", "").replace(">", "")[:4900]}}


def build_tags(ep):
    s = ep["script"]
    tags = [s["saint"]["name"], s["saint"].get("display_name", ""), s["saint"].get("region", ""),
            "Catholic saints", "saint of the day", "lives of the saints"]
    tags += [t.lstrip("#") for t in s.get("hashtags") or []]
    out, total = [], 0
    for t in dict.fromkeys(x.strip() for x in tags if x and x.strip()):
        if total + len(t) + 1 > 450:  # 500-char limit across all tags
            break
        out.append(t)
        total += len(t) + 1
    return out
