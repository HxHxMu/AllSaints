"""The O Antiphons (Dec 17-23) as seven Story cards, typeset on soot. Texts: data/o-antiphons.json.
    python engine/stories.py o-antiphons <year> [--upload]   # render (and queue them as drafts in state/stories.json)"""
import datetime as dt, json
from PIL import Image, ImageDraw
from common import DATA, ROOT, load_json, save_json, tz
from cards import font as _font, monogram as _monogram, roman, tracked as _tracked
from stories import C, FILE, SAFE_BOTTOM, TOP, W, H, X, _lines

O_ANTIPHONS = [(a["title"], a["latin"], a["english"]) for a in json.loads((DATA / "o-antiphons.json").read_text())["antiphons"]]


def antiphon_card(i, title, latin, english, day):
    """Typeset on soot, no picture: the antiphon is the image."""
    img = Image.new("RGB", (W, H), C["soot"])
    d = ImageDraw.Draw(img)
    big, lat, en = _font("Cinzel-SemiBold.ttf", 84), _font("EBGaramond-Medium.ttf", 46), _font("Cormorant-MediumItalic.ttf", 44)
    tl, ll, el = (_lines(d, title.upper(), big, W - 2 * X, 0.04), _lines(d, latin, lat, W - 2 * X),
                  _lines(d, english, en, W - 2 * X))
    block = 46 + 80 + 104 * len(tl) + 16 + 46 + 60 * len(ll) + 36 + 54 * len(el)
    y = max(TOP + 60, (TOP + SAFE_BOTTOM - 120 - block) // 2)  # centred between the top bar and the footnote
    _tracked(d, (X, y), f"THE O ANTIPHONS  ·  {roman(i + 1)} OF VII", _font("Cinzel-Regular.ttf", 24), C["gilt"], 0.16)
    y += 46
    _tracked(d, (X, y), f"{roman(day)} · DECEMBER", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
    y += 80
    for line in tl:
        _tracked(d, (X - 3, y), line, big, C["vellum"], 0.04)
        y += 104
    y += 16
    d.rectangle([X, y, X + 72, y + 3], fill=C["martyr"])
    y += 46
    for line in ll:
        d.text((X, y), line, font=lat, fill=C["vellum"])
        y += 60
    y += 36
    for line in el:
        d.text((X, y), line, font=en, fill=C["giltLight"])
        y += 54
    d.text((X, SAFE_BOTTOM - 96), "Sung at Vespers in the last days of Advent, since the early Middle Ages.",
           font=_font("Cormorant-MediumItalic.ttf", 30), fill=C["ash"])
    _monogram(d, X, SAFE_BOTTOM - 40, 30, C["gilt"])
    return img


def make_o_antiphons(year, upload=False, at="12:30"):
    out = ROOT / "work" / f"o-antiphons-{year}"
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for i, (title, latin, english) in enumerate(O_ANTIPHONS):
        p = out / f"{17 + i}-{title.split()[1].lower()}.jpg"
        antiphon_card(i, title, latin, english, 17 + i).save(p, quality=92)
        files[p.name] = p
    if upload:
        import storage
        urls = storage.upload(f"stories-o-antiphons-{year}", files, name=f"Stories: the O Antiphons {year}")
        items = [s for s in load_json(FILE, []) if not s["id"].startswith(f"o-antiphons-{year}-")]
        offset = dt.datetime(int(year), 12, 17, tzinfo=tz()).strftime("%z")
        for i, name in enumerate(files):
            items.append({"id": f"o-antiphons-{year}-{17 + i}", "at": f"{year}-12-{17 + i}T{at}:00{offset[:3]}:{offset[3:]}",
                          "image": urls[name], "status": "draft"})
        save_json(FILE, items)
    return out
