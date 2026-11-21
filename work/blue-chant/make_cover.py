"""Blue Chant, Volume I: album cover, 3000 square. Art from Nano Banana, type set in Cinzel."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from playlist_cover import _font, _tracked, _width, C

S = 3000
here = Path(__file__).parent
img = Image.open(here / "art.jpg").convert("RGB").resize((S, S), Image.LANCZOS)
img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))

# deepen the bottom into night so the words sit on ground, not on paint
shade = Image.new("L", (S, S), 0)
sd = ImageDraw.Draw(shade)
a, b = int(S * 0.80), int(S * 0.90)
for y in range(a, S):
    sd.line([(0, y), (S, y)], fill=int(215 * min(1, (y - a) / (b - a)) ** 1.4))
img.paste(Image.new("RGB", (S, S), "#0B1424"), (0, 0), shade)
d = ImageDraw.Draw(img)


def centered(text, y, font, fill, tracking):
    return _tracked(d, ((S - _width(d, text, font, tracking)) / 2, y), text, font, fill, tracking)


# monogram A.S.† at the top centre; Cinzel has no dagger, so the cross is drawn
mono = _font("Cinzel-SemiBold.ttf", 96)
w = _width(d, "A.S.", mono, 0.04) + 18 + 50
x0, y0 = (S - w) / 2, 150
x = x0 + _tracked(d, (x0, y0), "A.S.", mono, C["gilt"], tracking=0.04) + 18
top, bottom = y0 + mono.getbbox("A")[1] - 12, y0 + mono.getbbox("A")[3] + 12
d.rectangle([x + 21, top, x + 28, bottom], fill=C["gilt"])
bar = top + int((bottom - top) * 0.3)
d.rectangle([x, bar, x + 49, bar + 7], fill=C["gilt"])

# title and volume at the foot
title = _font("Cinzel-SemiBold.ttf", 250)
vol = _font("Cinzel-SemiBold.ttf", 92)
centered("BLUE CHANT", S - 520, title, C["vellum"], 0.08)
d.rectangle([(S - 160) / 2, S - 222, (S + 160) / 2, S - 214], fill=C["martyr"])
centered("VOLUME I", S - 185, vol, C["gilt"], 0.3)

img.save(here / "blue-chant-vol1-3000.jpg", "JPEG", quality=94)
img.resize((1400, 1400), Image.LANCZOS).save(here / "blue-chant-vol1-1400.jpg", "JPEG", quality=90)
