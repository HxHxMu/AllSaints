"""YouTube playlist cover: a saint's icon full-bleed with the face up top, soot rising from the
bottom, and the playlist name inscribed across it in Cinzel. Built from art the channel already has.
The API only takes square images (playlistImages, type "hero", 1:1) and YouTube shows the whole
square inside its 16:9 card, so the square is designed to be read whole and small: big words, no fine print."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import BRAND, ROOT, claude_json

W = H = 1080
FONTS = ROOT / "brand" / "fonts"
C = BRAND["colors"]
MARGIN = 76
TEXT_W = W - 2 * MARGIN


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


def _icon_square(art: Path, cover_crop: bool, focus=0.5, face_y=None, zoom=1.0):
    """A square of the icon. Video covers carry the monogram near the top and the name/date from ~65%
    down, so only their painted band (17-64%) is used; clean art.jpg is taken from the top."""
    im = Image.open(art).convert("RGB")
    w, h = im.size
    top, bottom = (int(h * 0.17), int(h * 0.64)) if cover_crop else (int(h * 0.02), h)
    side = int(min(w, bottom - top) * zoom)
    left = max(0, min(w - side, int(w * focus - side / 2)))
    if face_y is not None:  # put the face about a third of the way down
        top = max(top, min(bottom - side, int(h * face_y - side * 0.3)))
    return im.crop((left, top, left + side, top + side)).resize((W, H), Image.LANCZOS)


def locate_saint(art: Path):
    """Ask Haiku where the main saint's face is in the icon: (focus, face_y) as 0..1 fractions."""
    import base64, io
    im = Image.open(art).convert("RGB")
    im.thumbnail((540, 960))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    out = claude_json(
        "This is a Byzantine-style icon of a Catholic saint. Where is the face of the main saint (the central, "
        "haloed or most prominent figure)? Give the face centre as fractions of the image width and height, "
        'left/top = 0, right/bottom = 1. Answer JSON: {"x": 0.0, "y": 0.0}',
        images=[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                              "data": base64.b64encode(buf.getvalue()).decode()}}],
        label="saint-face", tier="haiku")
    x, y = float(out["x"]), float(out["y"])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"face out of range: {out}")
    return x, y


def make_cover(title: str, art: Path, out: Path, cover_crop=True, focus=0.5, face_y=None, zoom=1.0):
    """title like "Saints of Africa" / "Saints of the Middle East". Hand-tuning for a given icon:
    focus = where the saint stands across the art (0..1), face_y = face height in the art (0..1), zoom < 1 = closer."""
    img = _icon_square(art, cover_crop, focus, face_y, zoom)
    d = ImageDraw.Draw(img)
    # "Saints of" (+ "the") in gilt; the place or month large in vellum
    rest = title.split(" of ", 1)[1] if " of " in title else title
    lead = "SAINTS OF THE" if rest.lower().startswith("the ") else "SAINTS OF"
    big = (rest[4:] if rest.lower().startswith("the ") else rest).upper()

    def fit(lines, start=190):
        size = start
        while size > 70 and max(_width(d, l, _font("Cinzel-SemiBold.ttf", size), 0.06) for l in lines) > TEXT_W:
            size -= 2
        return size
    lines, size = [big], fit([big])
    if size < 100 and " " in big:  # two lines only when one would be too small to read
        two = big.split(" ", 1)
        if fit(two) > size:
            lines, size = two, fit(two)
    bigf = _font("Cinzel-SemiBold.ttf", size)
    line_h = int(size * 1.0)
    small = _font("Cinzel-SemiBold.ttf", 58)
    mono = _font("Cinzel-SemiBold.ttf", 40)

    y = H - 70 - line_h * len(lines) - 24 - 58 - 40 - 40 - 40
    # soot rises from the bottom so the words sit on the ground, not on the paint (depth, never a glow)
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    a, b = max(0, y - 300), y + 20
    for yy in range(a, H):
        sd.line([(0, yy), (W, yy)], fill=int(255 * min(1, (yy - a) / (b - a)) ** 1.3))
    img.paste(Image.new("RGB", (W, H), C["soot"]), (0, 0), shade)
    d = ImageDraw.Draw(img)
    # monogram A.S.†: Cinzel has no dagger, so the cross is drawn (as in brand/make_logo.py)
    x = MARGIN + _tracked(d, (MARGIN, y), "A.S.", mono, C["gilt"], tracking=0.04) + 6
    top, bottom = y + mono.getbbox("A")[1] - 5, y + mono.getbbox("A")[3] + 5
    d.rectangle([x + 8, top, x + 10, bottom], fill=C["gilt"])
    bar = top + int((bottom - top) * 0.3)
    d.rectangle([x, bar, x + 18, bar + 2], fill=C["gilt"])
    y += 40 + 40
    d.rectangle([MARGIN, y - 22, MARGIN + 110, y - 19], fill=C["martyr"])  # the rubric hairline of the video covers
    _tracked(d, (MARGIN, y), lead, small, C["gilt"])
    y += 58 + 24
    for l in lines:
        _tracked(d, (MARGIN - 6, y), l, bigf, C["vellum"], tracking=0.06)
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=90, optimize=True)
    return out


if __name__ == "__main__":
    import sys
    f = [float(x) for x in sys.argv[4:]]  # optional: focus face_y zoom
    make_cover(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), focus=f[0] if f else 0.5,
               face_y=f[1] if len(f) > 1 else None, zoom=f[2] if len(f) > 2 else 1.0)
