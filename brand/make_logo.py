"""Generate A.S.† logo assets as pure-path SVGs (no font dependency)."""
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(HERE, "brand.json")))
C = B["colors"]


def text_path(text, font_file, size, tracking=0.0):
    """Return (svg_path_d, width, cap_top, baseline) for text at given px size, origin at baseline-left."""
    f = TTFont(os.path.join(HERE, "fonts", font_file))
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    s = size / upm
    pen = SVGPathPen(gs)
    x = 0.0
    for i, ch in enumerate(text):
        g = cmap.get(ord(ch))
        if g is None:
            continue
        tp = TransformPen(pen, (s, 0, 0, -s, x, 0))
        gs[g].draw(tp)
        x += gs[g].width * s + (tracking * size if i < len(text) - 1 else 0)
    bp = BoundsPen(gs)
    return pen.getCommands(), x


def cross(cx, top, h, w, stroke):
    """Slender Latin cross: crossbar at ~30% height."""
    bar_y = top + h * 0.30
    return (f'<rect x="{cx - stroke/2:.2f}" y="{top:.2f}" width="{stroke:.2f}" height="{h:.2f}"/>'
            f'<rect x="{cx - w/2:.2f}" y="{bar_y - stroke/2:.2f}" width="{w:.2f}" height="{stroke:.2f}"/>')


def monogram(size=1080, bg=True, fg=None, ring=True):
    fg = fg or C["gilt"]
    S = size
    cs = S * 0.30  # cap size
    dA, wA = text_path("A", "Cinzel-SemiBold.ttf", cs)
    dS, wS = text_path("S", "Cinzel-SemiBold.ttf", cs)
    cap_h = cs * 0.70  # Cinzel cap height ~0.7em
    gap = S * 0.17
    total = wA + gap + wS
    x0 = (S - total) / 2
    base = S / 2 + cap_h / 2
    ch = cap_h * 1.55
    ctop = S / 2 - ch * 0.56
    parts = []
    if bg:
        parts.append(f'<rect width="{S}" height="{S}" fill="{C["soot"]}"/>')
    if ring:
        r = S * 0.40
        parts.append(f'<circle cx="{S/2}" cy="{S/2}" r="{r:.1f}" fill="none" stroke="{fg}" stroke-width="{S*0.008:.1f}"/>')
        parts.append(f'<circle cx="{S/2}" cy="{S/2}" r="{r - S*0.022:.1f}" fill="none" stroke="{fg}" stroke-opacity="0.45" stroke-width="{S*0.003:.1f}"/>')
    parts.append(f'<g fill="{fg}">')
    parts.append(f'<path transform="translate({x0:.2f},{base:.2f})" d="{dA}"/>')
    parts.append(f'<path transform="translate({x0 + wA + gap:.2f},{base:.2f})" d="{dS}"/>')
    parts.append(cross(x0 + wA + gap / 2, ctop, ch, ch * 0.44, S * 0.014))
    parts.append('</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">' + "".join(parts) + "</svg>"


def wordmark(fg=None, bg=None, h=200):
    fg = fg or C["gilt"]
    size = h * 0.5
    d, w = text_path("ALL SAINTS", "Cinzel-SemiBold.ttf", size, tracking=0.18)
    pad = h * 0.4
    cw = h * 0.18
    W = w + pad * 2 + cw * 3.2
    cap = size * 0.70
    base = h / 2 + cap / 2
    parts = []
    if bg:
        parts.append(f'<rect width="{W:.0f}" height="{h}" fill="{bg}"/>')
    parts.append(f'<g fill="{fg}"><path transform="translate({pad:.2f},{base:.2f})" d="{d}"/>')
    parts.append(cross(pad + w + cw * 2.2, h / 2 - cap * 0.68, cap * 1.36, cap * 0.62, h * 0.02))
    parts.append('</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {h}" width="{W:.0f}" height="{h}">' + "".join(parts) + "</svg>"


def initials(fg=None, h=120):
    """Small 'A.S.†' watermark for video corner."""
    fg = fg or C["gilt"]
    size = h * 0.62
    d, w = text_path("A.S.", "Cinzel-SemiBold.ttf", size, tracking=0.06)
    cap = size * 0.70
    W = w + h * 0.45
    base = h / 2 + cap / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {h}" width="{W:.0f}" height="{h}"><g fill="{fg}">'
            f'<path transform="translate(0,{base:.2f})" d="{d}"/>'
            + cross(w + h * 0.22, h / 2 - cap * 0.78, cap * 1.55, cap * 0.62, h * 0.05) + '</g></svg>')


if __name__ == "__main__":
    out = os.path.join(HERE, "logo")
    os.makedirs(out, exist_ok=True)
    open(f"{out}/monogram.svg", "w").write(monogram())
    open(f"{out}/monogram-transparent.svg", "w").write(monogram(bg=False))
    open(f"{out}/monogram-cream.svg", "w").write(monogram(bg=False, fg=C["vellum"]))
    open(f"{out}/wordmark.svg", "w").write(wordmark())
    open(f"{out}/wordmark-dark.svg", "w").write(wordmark(bg=C["soot"]))
    open(f"{out}/initials.svg", "w").write(initials())
    open(f"{out}/initials-cream.svg", "w").write(initials(fg=C["vellum"]))
    print("ok")
