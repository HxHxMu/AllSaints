"""Instagram Story Highlight covers: brand/social/highlights/<name>.jpg (1080x1920; Instagram shows the centre as a
circle, so each sign sits inside a ~460 px disc). Gilt line drawing on soot, one sign each, no words (Instagram
prints the highlight's name under the circle).

    .venv/bin/python brand/make_highlights.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "brand" / "brand.json").read_text())["colors"]
FONTS = ROOT / "brand" / "fonts"
OUT = ROOT / "brand" / "social" / "highlights"
W, H = 1080, 1920
CX, CY = W // 2, H // 2
S = 4                      # drawn at 4x and scaled down, for smooth lines
LINE = 9                   # stroke width at final size


def canvas():
    img = Image.new("RGB", (W * S, H * S), C["soot"])
    d = ImageDraw.Draw(img)
    r = 300 * S  # a thin gilt ring, the frame every cover shares
    d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], outline=C["gilt"], width=4 * S)
    return img, d


def p(x, y):
    return (x * S, y * S)


def line(d, pts, w=LINE, fill=None):
    d.line([p(*q) for q in pts], fill=fill or C["giltLight"], width=w * S, joint="curve")


def finish(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(OUT / f"{name}.jpg", quality=95)


def music():
    """A line of chant: the four-line staff and square neumes."""
    img, d = canvas()
    left, right, top, gap = CX - 200, CX + 200, CY - 75, 50
    for i in range(4):
        line(d, [(left, top + i * gap), (right, top + i * gap)], w=4, fill=C["gilt"])
    # punctum, then a two-note podatus (a stem joins them), then a punctum
    def note(x, y):
        d.rectangle([*p(x - 21, y - 19), *p(x + 21, y + 19)], fill=C["giltLight"])
    note(CX - 125, top + gap * 2.5)
    note(CX - 45, top + gap * 2)
    note(CX + 45, top + gap * 2.5)
    note(CX + 45, top + gap * 1.5)
    line(d, [(CX + 64, top + gap * 1.5), (CX + 64, top + gap * 2.5)], w=6)
    note(CX + 135, top + gap)
    finish(img, "music")


def library():
    """An open book."""
    img, d = canvas()
    y0, y1, spine = CY - 120, CY + 110, CX
    for side in (-1, 1):
        outer = spine + side * 210
        line(d, [(spine, y0 + 20), (spine + side * 70, y0 - 5), (outer, y0), (outer, y1), (spine + side * 70, y1 - 5), (spine, y1 + 20)])
        for k in range(4):  # lines of text
            yy = y0 + 50 + k * 40
            line(d, [(spine + side * 40, yy + 6), (outer - side * 35, yy)], w=4, fill=C["gilt"])
    line(d, [(spine, y0 + 20), (spine, y1 + 20)])
    finish(img, "library")


def advent():
    """The Advent wreath: four candles, the first one lit."""
    img, d = canvas()
    base = CY + 110
    xs = [CX - 150, CX - 50, CX + 50, CX + 150]
    for i, x in enumerate(xs):
        top = base - (230 if i == 0 else 200)
        d.rectangle([*p(x - 20, top), *p(x + 20, base)], outline=C["giltLight"], width=LINE * S)
        line(d, [(x, top), (x, top - 18)], w=4, fill=C["gilt"])  # wick
        if i == 0:  # flame: a teardrop
            fx, fy = x, top - 58
            d.polygon([p(fx, fy - 46), p(fx + 18, fy + 2), p(fx + 13, fy + 22), p(fx, fy + 30), p(fx - 13, fy + 22), p(fx - 18, fy + 2)],
                      fill=C["giltLight"])
    # the wreath: a low arc of evergreen under the candles
    d.arc([*p(CX - 230, base - 40), *p(CX + 230, base + 70)], 0, 180, fill=C["gilt"], width=LINE * S)
    for k in range(9):
        x = CX - 200 + k * 50
        line(d, [(x - 16, base + 34), (x, base + 12), (x + 16, base + 34)], w=4, fill=C["gilt"])
    finish(img, "advent")


def about():
    """The monogram, A.S.†"""
    img, d = canvas()
    size = 150 * S
    f = ImageFont.truetype(str(FONTS / "Cinzel-SemiBold.ttf"), size)
    text = "A.S."
    tw = sum(d.textlength(ch, font=f) for ch in text) + size * 0.04 * (len(text) - 1)
    arm = size * 0.45
    total = tw + size * 0.15 + arm
    x = CX * S - total / 2
    y = CY * S - size * 0.62
    for ch in text:
        d.text((x, y), ch, font=f, fill=C["giltLight"])
        x += d.textlength(ch, font=f) + size * 0.04
    x += size * 0.15 - size * 0.04
    top, bottom = y + f.getbbox("A")[1] - size * 0.12, y + f.getbbox("A")[3] + size * 0.12
    stem = max(2, size // 18)  # Cinzel has no dagger: draw the cross, as cards.monogram does
    d.rectangle([x + (arm - stem) / 2, top, x + (arm + stem) / 2, bottom], fill=C["giltLight"])
    bar = top + (bottom - top) * 0.3
    d.rectangle([x, bar, x + arm, bar + stem], fill=C["giltLight"])
    finish(img, "about")


if __name__ == "__main__":
    for make in (music, library, advent, about):
        make()
    print(OUT)
