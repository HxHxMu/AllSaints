"""Instagram caption for an episode: hook, follow line, summary, prayer, rotating CTA, sources, credits, ≤5 hashtags (rules in brand.json → caption)."""
import datetime as dt, re, unicodedata
from common import BRAND

CAP = BRAND["caption"]


def _fold(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def saint_tags(s, n=2):
    """The saint's own tags: the name tag, then the first tag that isn't another spelling of the name."""
    tags = [t if t.startswith("#") else "#" + t for t in (s.get("hashtags") or [])]
    names = [w for w in re.findall(r"[a-z]{4,}", _fold(s["saint"]["name"])) if w not in ("saint", "saints")]
    out = tags[:1]
    for t in tags[1:]:
        if len(out) >= n:
            break
        if not any(w in _fold(t) for w in names) and t.lower() not in (x.lower() for x in CAP["hashtags_base"]):
            out.append(t)
    return out


def ig_hashtags(s):
    tags = [CAP["hashtag_brand"]] + CAP["hashtags_base"] + saint_tags(s)
    return list(dict.fromkeys(tags))[:CAP.get("hashtags_max", 5)]


def pick_cta(ep):
    """Rotate caption CTAs by date; the script's own share line (name/patron) joins the rotation."""
    s = ep["script"]
    opts = ([s["share_cta"].strip()] if s.get("share_cta", "").strip() else []) + CAP["ctas"]
    try:
        k = dt.date.fromisoformat(ep["date"]).toordinal()
    except (KeyError, ValueError):
        k = 0
    return opts[k % len(opts)].format(feast=s["saint"].get("feast", "feast day"), display_name=s["saint"].get("display_name", s["saint"]["name"]))


def build_caption(ep):
    s = ep["script"]
    saint = s["saint"]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    tags = ig_hashtags(s)
    if ep.get("caption_hook_override"):
        body = ep["caption_hook_override"].strip()
    else:
        body = f"{s.get('caption_hook', '').strip()}\n\n{saint['name']} · Feast day: {saint.get('feast', '')}\n{s.get('summary', '').strip()}\n\n{prayer} 🕯"
    # source names without the article ("Santi e Beati: San X" → "Santi e Beati"; old "Catholic Encyclopedia (1913)/St. X" too)
    # follow line right under the hook, above Instagram's "more" fold
    if CAP.get("follow_line"):
        hook, _, rest = body.partition("\n")
        body = f"{hook}\n{CAP['follow_line']}" + (f"\n{rest}" if rest else "")
    srcs = " · ".join(dict.fromkeys(re.split(r"[:/]", x["title"])[0].strip() for x in ep.get("sources", [])))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", [])))
    cap = f"{body}\n\n{pick_cta(ep)}\n\n—\nSources: {srcs}\nArt: {credits or 'public domain'}\n\n{' '.join(tags)}"
    return cap[:2150]
