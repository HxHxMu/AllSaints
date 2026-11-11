"""Drawing primitives shared by every card and video module (Stories, playlist covers, compilation, sung prayers,
music clips): brand fonts, tracked Cinzel, word wrap, the A.S.† monogram, Roman numerals, ffprobe duration.
Imports only PIL and common at the top: poll.yml installs pillow but not numpy."""
import subprocess
from PIL import ImageFont
from common import ROOT

FONTS = ROOT / "brand" / "fonts"
ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def tracked(draw, xy, text, font, fill, tracking=0.12):
    """Draw text with letter-spacing (Cinzel is set at +0.12em); returns the drawn width."""
    x, y = xy
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + (font.size * tracking if i < len(text) - 1 else 0)
    return x - xy[0]


def width(draw, text, font, tracking=0.12):
    return sum(draw.textlength(ch, font=font) for ch in text) + font.size * tracking * max(len(text) - 1, 0)


def wrap(d, text, font, max_width, tracking=0.02):
    """Greedy word wrap to max_width px of tracked text."""
    lines = []
    for word in text.split():
        if lines and width(d, f"{lines[-1]} {word}", font, tracking) <= max_width:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def monogram(d, x, y, size, fill):
    """The A.S.† mark at (x, y), cap height ~size. Cinzel has no dagger, so the cross is drawn."""
    f = font("Cinzel-SemiBold.ttf", size)
    x += tracked(d, (x, y), "A.S.", f, fill, tracking=0.04) + size * 0.15
    top, bottom = y + f.getbbox("A")[1] - size * 0.12, y + f.getbbox("A")[3] + size * 0.12
    stem, arm = max(2, size // 18), size * 0.45
    d.rectangle([x + (arm - stem) / 2, top, x + (arm + stem) / 2, bottom], fill=fill)
    bar = top + (bottom - top) * 0.3
    d.rectangle([x, bar, x + arm, bar + stem], fill=fill)


def roman(n):
    """1 → I … 31 → XXXI; 0 → ""."""
    out = ""
    for v, r in ROMAN:
        while n >= v:
            out, n = out + r, n - v
    return out


def duration(p):
    """Length of an audio/video file in seconds (ffprobe)."""
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout.strip())
