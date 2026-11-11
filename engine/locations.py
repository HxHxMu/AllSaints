"""Instagram location tags: a hand-kept map from a saint's place to its Facebook place Page ID (state/locations.json).

Instagram tags a Reel with `location_id`, the ID of a Facebook Page that has a location. Finding one by search needs
Meta's "Page Public Metadata Access" review, so Luis adds IDs from Telegram (`/loc`); every later saint tied to the same
place reuses it. An episode's own `location` {name, id} (set by `/loc YYYY-MM-DD …`) wins over the map; otherwise the
first of the script's places (most specific first) that has an ID is used. No match → the Reel posts untagged.
"""
import re
import unicodedata
from common import load_json, save_json

FILE = "locations.json"


def slug(name):
    s = unicodedata.normalize("NFD", name)
    s = re.sub(r"[̀-ͯ]", "", s).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def places(ep):
    return [p for p in ((ep.get("script") or {}).get("places") or []) if p.strip()]


def remember(name, page_id):
    m = load_json(FILE, {})
    m[slug(name)] = {"name": name.strip(), "id": str(page_id)}
    save_json(FILE, m)


def for_episode(ep):
    """{name, id} to tag the Reel with, or None."""
    loc = ep.get("location")
    if loc is not None:
        return loc or None  # {} = Luis turned it off for this episode
    m = load_json(FILE, {})
    return next((m[slug(p)] for p in places(ep) if slug(p) in m), None)


def page_id(text):
    """A Page ID typed in Telegram, bare or inside a facebook.com/profile.php?id=… link."""
    m = re.search(r"(?:id=)?(\d{6,20})", text)
    return m.group(1) if m else None


def review_line(ep):
    loc = for_episode(ep)
    if loc:
        return f"📍 Location: {loc['name']}"
    ps = places(ep)
    return (f"📍 No location yet ({', '.join(ps[:3]) or 'no places'}). "
            f"To tag it: /loc {ep['id']} <Facebook Page ID of {ps[0] if ps else 'the place'}>")
