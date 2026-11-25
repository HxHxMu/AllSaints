"""Three cover directions for Lives of the Saints, shown in a mock 3-column feed beside daily-saint and Blue Chant tiles."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

S = Path(__file__).parent
REPO = Path("/Users/luisbonilla/Dev/AllSaints")
F = REPO / "brand/fonts"
FRAK = REPO / "work/lives/UnifrakturMaguntia-Book.ttf"
W, H = 1080, 1920
PAPER, AMBER = (236, 232, 222), (226, 150, 58)
TITLES = ["The Hound", "The Closed Door", "The Rope", "The Habit", "The House of Mercy", "The Hermitage"]
NUM = ["I", "II", "III", "IV", "V", "VI"]


def ft(p, s): return ImageFont.truetype(str(p), s)


def frame(i):
    im = Image.open(S / f"f{i+1}.png").convert("L")
    im = ImageOps.fit(im, (W, H), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=1)
    return Image.merge("RGB", [im.point(lambda v: int(v * .96)), im.point(lambda v: int(v * .98)), im])  # cold tint


def ctext(d, y, t, f, fill=PAPER):
    w = d.textlength(t, font=f); d.text(((W - w) / 2, y), t, font=f, fill=fill)


def border(d, inset=50, col=PAPER):
    for k in (0, 14):
        d.rectangle([inset + k, inset + k, W - inset - k, H - inset - k], outline=col, width=3 if k == 0 else 1)


def iris(i):   # A: the silent-film iris shot on a black intertitle card
    c = Image.new("RGB", (W, H), (8, 8, 9)); d = ImageDraw.Draw(c); border(d)
    ctext(d, 250, "Lives of the Saints", ft(FRAK, 92))
    r = 400; ph = ImageOps.fit(frame(i), (2 * r, 2 * r), Image.LANCZOS, centering=(.5, .35))
    m = Image.new("L", (2 * r, 2 * r), 0); ImageDraw.Draw(m).ellipse([0, 0, 2 * r, 2 * r], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(14)); c.paste(ph, (W // 2 - r, 470), m)
    ctext(d, 1300, NUM[i], ft(F / "Cinzel-Bold.ttf", 150), AMBER)
    ctext(d, 1490, TITLES[i], ft(F / "Cormorant-MediumItalic.ttf", 84))
    ctext(d, 1610, "ST. MARGARET OF CORTONA", ft(F / "Cinzel-Regular.ttf", 44))
    return c


def nitrate(i):   # B: full-bleed still, intertitle border, huge numeral
    c = frame(i); g = Image.new("L", (W, H)); gd = ImageDraw.Draw(g)
    for y in range(H): gd.line([(0, y), (W, y)], fill=int(200 * max(0, (y - 1000) / 920) ** 1.3 + 120 * max(0, (500 - y) / 500)))
    c = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), c, g); d = ImageDraw.Draw(c); border(d)
    ctext(d, 250, "Lives of the Saints", ft(FRAK, 92))
    ctext(d, 1180, NUM[i], ft(F / "Cinzel-Bold.ttf", 300))
    ctext(d, 1520, TITLES[i], ft(F / "Cormorant-MediumItalic.ttf", 84))
    ctext(d, 1640, "ST. MARGARET OF CORTONA", ft(F / "Cinzel-Regular.ttf", 44))
    return c


def ember(i):   # C: full-bleed still with an amber band, like a tinted film strip
    c = frame(i); d = ImageDraw.Draw(c)
    d.rectangle([0, 1240, W, 1640], fill=AMBER)
    d.text((90, 1270), NUM[i], font=ft(F / "Cinzel-Bold.ttf", 280), fill=(14, 12, 10))
    x = 90 + d.textlength(NUM[i], font=ft(F / "Cinzel-Bold.ttf", 280)) + 50
    d.text((x, 1320), "Lives of the Saints", font=ft(FRAK, 72), fill=(14, 12, 10))
    d.text((x, 1430), TITLES[i], font=ft(F / "Cormorant-MediumItalic.ttf", 70), fill=(14, 12, 10))
    return c


def feed(make, name):
    ns = [Image.open(S / f"ep-{d}.jpg").convert("RGB") for d in ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-23"]]
    mu = Image.open(S / "music.jpg").convert("RGB")
    tiles = [make(0), ns[0], make(1), ns[1], mu, ns[2], make(2), ns[3], make(3)]
    tw, th, gap = 360, 480, 6   # Instagram-style 3:4 grid tiles
    out = Image.new("RGB", (3 * tw + 2 * gap, 3 * th + 2 * gap + 90), (250, 250, 250))
    ImageDraw.Draw(out).text((20, 22), name, font=ft(F / "Cinzel-Bold.ttf", 44), fill=(20, 20, 20))
    for k, t in enumerate(tiles):
        out.paste(ImageOps.fit(t, (tw, th), Image.LANCZOS), ((k % 3) * (tw + gap), 90 + (k // 3) * (th + gap)))
    return out


if __name__ == "__main__":
    sheets = [feed(f, n) for f, n in [(iris, "A · Iris"), (nitrate, "B · Nitrate"), (ember, "C · Ember")]]
    w = sum(s.width for s in sheets) + 40; out = Image.new("RGB", (w, sheets[0].height), (200, 200, 200)); x = 0
    for s in sheets: out.paste(s, (x, 0)); x += s.width + 20
    out.save(S / "options-feed.jpg", quality=88)
    full = Image.new("RGB", (3 * W + 40, H), (200, 200, 200))
    for k, f in enumerate([iris, nitrate, ember]): full.paste(f(5), (k * (W + 20), 0))
    full.save(S / "options-full.jpg", quality=88)
