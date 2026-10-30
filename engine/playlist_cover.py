"""YouTube playlist cover: a saint's icon on the right fading into soot, the playlist name inscribed
on the left in Cinzel. Built from art the channel already has; no image generation.
The API only takes square images (playlistImages, 1:1) but YouTube shows playlists as 16:9 cards,
so every word sits inside the square's middle 16:9 band (y 236..844 at 1080)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import BRAND, ROOT

W = H = 1080
FONTS = ROOT / "brand" / "fonts"
C = BRAND["colors"]
MARGIN, TEXT_W = 72, 600  # left column; the icon panel starts at x=560 and fades in under the text
PANEL_X = 480
BAND = (int(H / 2 - W * 9 / 32), int(H / 2 + W * 9 / 32))  # the 16:9 crop YouTube may show


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _tracked(draw, xy, text, font, fill, tracking=0.12):
    """Draw text with letter-spacing (Cinzel is set at +0.12em); returns the drawn width."""
    x, y = xy
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + (font.size * tracking if i < len(text) - 1 else 0)
    return x - xy[0]


def _width(draw, text, font, tracking=0.12):
    return sum(draw.textlength(ch, font=font) for ch in text) + font.size * tracking * max(len(text) - 1, 0)


def _icon_panel(art: Path, cover_crop: bool, focus=0.5):
    """The icon, cropped to the panel. Video covers carry the name/date from ~65% down and the
    monogram near the top, so only their painted middle band is used; clean art.jpg is used whole-height."""
    im = Image.open(art).convert("RGB")
    w, h = im.size
    top, bottom = (int(h * 0.19), int(h * 0.64)) if cover_crop else (0, int(h * 0.72))
    pw, ph = W - PANEL_X, H
    crop_w = int((bottom - top) * pw / ph)
    left = max(0, min(w - crop_w, int(w * focus - crop_w * 0.62)))  # focus lands right of the fade
    return im.crop((left, top, left + crop_w, bottom)).resize((pw, ph), Image.LANCZOS)


def make_cover(title: str, art: Path, out: Path, cover_crop=True, focus=0.5):
    """focus: where the saint stands in the art, 0 = left edge, 1 = right edge."""
    img = Image.new("RGB", (W, H), C["soot"])
    panel = _icon_panel(art, cover_crop, focus)
    # fade the icon's left edge into soot (depth from the ground, never a glow)
    mask = Image.new("L", panel.size, 255)
    fade = 300
    md = ImageDraw.Draw(mask)
    for x in range(fade):
        md.line([(x, 0), (x, H)], fill=int(255 * (x / fade) ** 1.6))
    img.paste(panel, (PANEL_X, 0), mask)

    d = ImageDraw.Draw(img)
    # "Saints of" (+ "the") small in gilt; the place or month large in vellum
    rest = title.split(" of ", 1)[1] if " of " in title else title
    lead = "SAINTS OF THE" if rest.lower().startswith("the ") else "SAINTS OF"
    big = (rest[4:] if rest.lower().startswith("the ") else rest).upper()

    small = _font("Cinzel-SemiBold.ttf", 40)
    size = 150
    lines = [big]
    while size > 60 and _width(d, big, _font("Cinzel-SemiBold.ttf", size), 0.06) > TEXT_W:
        size -= 2
    if size <= 100 and " " in big:  # two short lines read bigger than one long one
        lines = big.split(" ", 1)
        size = 150
        while size > 60 and max(_width(d, l, _font("Cinzel-SemiBold.ttf", size), 0.06) for l in lines) > TEXT_W:
            size -= 2
    bigf = _font("Cinzel-SemiBold.ttf", size)
    line_h = int(size * 1.02)

    tag = _font("Cormorant-MediumItalic.ttf", 34)
    tag_lines = [l.strip() + "." for l in BRAND["tagline"].replace("'", "’").split(".") if l.strip()]
    mono = _font("Cinzel-SemiBold.ttf", 34)
    block_h = 34 + 50 + 40 + 24 + line_h * len(lines) + 40 + 42 * len(tag_lines)
    y = (BAND[0] + BAND[1] - block_h) // 2

    # monogram A.S.†: Cinzel has no dagger, so the cross is drawn (as in brand/make_logo.py)
    x = MARGIN + _tracked(d, (MARGIN, y), "A.S.", mono, C["gilt"], tracking=0.04) + 6
    top, bottom = y + mono.getbbox("A")[1] - 4, y + mono.getbbox("A")[3] + 4
    d.rectangle([x + 7, top, x + 9, bottom], fill=C["gilt"])
    bar = top + int((bottom - top) * 0.3)
    d.rectangle([x, bar, x + 16, bar + 2], fill=C["gilt"])
    y += 34 + 50
    d.rectangle([MARGIN, y - 22, MARGIN + 100, y - 20], fill=C["martyr"])  # the rubric hairline of the video covers
    _tracked(d, (MARGIN, y), lead, small, C["gilt"])
    y += 40 + 24
    for l in lines:
        _tracked(d, (MARGIN - 6, y), l, bigf, C["vellum"], tracking=0.06)
        y += line_h
    y += 14
    d.rectangle([MARGIN, y, MARGIN + 100, y + 2], fill=C["gilt"])
    y += 22
    for l in tag_lines:
        d.text((MARGIN, y), l, font=tag, fill=C["ash"])
        y += 42
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=90, optimize=True)
    return out


if __name__ == "__main__":
    import sys
    make_cover(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), focus=float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)
