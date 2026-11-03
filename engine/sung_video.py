"""Lyric video for a sung prayer (docs/sung-prayers/): the saint's icon on the left, the sung words on soot to the right.

    python engine/sung_video.py docs/sung-prayers/01-veni-redemptor-gentium.json [--frames]
    python engine/sung_video.py docs/sung-prayers/01-veni-redemptor-gentium.json --teaser

--teaser cuts the spec's "teaser" span ({"from", "to", "stanzas", "intro", "intro_for", "end"}) as a 1080x1920 Instagram Reel: the icon on
top, the title, an opening card ("intro": [headline, line, ...]) already up on the first frame so a scrolling viewer
sees at once that it's a sung hymn, the stanzas as they're sung, then a card pointing to the full hymn on YouTube. Text stays inside the Reel's
safe area (clear of the top bar and the caption at the bottom).

The spec (JSON) names the audio and icon in its work dir, the crop of the icon, and each stanza's Latin, English and
start time; a stanza stays up until the next one starts (or its "until"). "cards" are spans that show the title
(intro, interludes); credits close the video. Each text state is a transparent PNG cross-faded over one base frame,
so the icon never flickers. --frames writes the PNGs and a contact sheet only (fast layout check). No AI involved.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
from common import BRAND, ROOT
from playlist_cover import _font, _tracked, _width
from compilation import _monogram, duration

W, H = 1920, 1080
PANEL = 860                 # icon width on the left
TX, TW = 960, 860           # text column
FADE = 0.8
C = BRAND["colors"]
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def base(spec, d):
    """Icon panel melting into soot, monogram and site on the right. Everything else is overlaid."""
    art = Image.open(d / spec["art"]).convert("RGB").crop(tuple(spec["art_crop"]))
    art = art.resize((PANEL, H), Image.LANCZOS)
    img = Image.new("RGB", (W, H), C["soot"])
    img.paste(art, (0, 0))
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    start = PANEL - 260
    for x in range(start, PANEL + 1):  # the painting's right edge sinks into the soot
        fd.line([(x, 0), (x, H)], fill=int(255 * ((x - start) / 260) ** 1.4))
    img.paste(Image.new("RGB", (W, H), C["soot"]), (0, 0), fade)
    d2 = ImageDraw.Draw(img)
    _monogram(d2, TX, 64, 34, C["gilt"])
    d2.text((TX, H - 84), "allholysaints.com", font=_font("EBGaramond-Medium.ttf", 26), fill=C["ash"])
    return img


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def stanza(spec, s):
    img = layer()
    d = ImageDraw.Draw(img)
    lat, en = _font(spec.get("text_font", "EBGaramond-Medium.ttf"), 52), _font("Cormorant-MediumItalic.ttf", 38)
    block = len(s["latin"]) * 68 + 44 + len(s["english"]) * 48
    y = (H - block) // 2 + 10
    _tracked(d, (TX, y - 92), f"{spec['title'].upper()}  ·  {ROMAN[s['n']]}", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.14)
    d.rectangle([TX, y - 46, TX + 72, y - 43], fill=C["martyr"])
    for line in s["latin"]:
        d.text((TX, y), line, font=lat, fill=C["vellum"])
        y += 68
    y += 44
    for line in s["english"]:
        d.text((TX, y), line, font=en, fill=C["giltLight"])
        y += 48
    return img


def card(spec):
    img = layer()
    d = ImageDraw.Draw(img)
    y = 360
    _tracked(d, (TX, y), spec["byline"].upper(), _font("Cinzel-Regular.ttf", 26), C["gilt"], 0.14)
    y += 70
    big = _font("Cinzel-SemiBold.ttf", 76)
    words, lines = spec["title"].upper().split(), [""]
    for w in words:  # wrap the title to the text column
        test = f"{lines[-1]} {w}".strip()
        if _width(d, test, big, 0.04) <= TW or not lines[-1]:
            lines[-1] = test
        else:
            lines.append(w)
    for l in lines:
        _tracked(d, (TX - 4, y), l, big, C["vellum"], 0.04)
        y += 92
    y += 18
    d.rectangle([TX, y, TX + 72, y + 3], fill=C["martyr"])
    d.text((TX, y + 34), spec["title_en"], font=_font("Cormorant-MediumItalic.ttf", 42), fill=C["giltLight"])
    d.text((TX, y + 96), spec["dates"], font=_font("EBGaramond-Medium.ttf", 30), fill=C["ash"])
    return img


def credits(spec):
    img = layer()
    d = ImageDraw.Draw(img)
    y = 380
    small, body = _font("Cinzel-Regular.ttf", 22), _font("EBGaramond-Medium.ttf", 34)
    for label, text in spec["credits"]:
        _tracked(d, (TX, y), label.upper(), small, C["ash"], 0.16)
        d.text((TX, y + 34), text, font=body, fill=C["vellum"])
        y += 104
    d.rectangle([TX, y + 10, TX + 72, y + 13], fill=C["martyr"])
    d.text((TX, y + 44), spec["closing"], font=_font("Cormorant-MediumItalic.ttf", 46), fill=C["giltLight"])
    return img


def timeline(spec, total):
    """[(name, layer, start, end)] with every text state, in order."""
    out = [(f"card{i}", card(spec), a, b) for i, (a, b) in enumerate(spec["cards"])]
    ss = spec["stanzas"]
    for i, s in enumerate(ss):
        end = s.get("until") or (ss[i + 1]["at"] - 0.3 if i + 1 < len(ss) else spec["credits_at"] - 1)
        out.append((f"st{i:02d}", stanza(spec, s), s["at"] - 1.2, end))
    out.append(("credits", credits(spec), spec["credits_at"], total))
    return sorted(out, key=lambda x: x[2])


def render(spec_path, frames_only=False):
    spec = json.loads(Path(spec_path).read_text())
    d = ROOT / spec["dir"]
    audio = d / spec["audio"]
    total = duration(audio)
    out = d / "frames"
    out.mkdir(exist_ok=True)
    bg = base(spec, d)
    bg.save(out / "base.png")
    tl = timeline(spec, total)
    for name, img, a, b in tl:
        img.save(out / f"{name}.png")
    if frames_only:  # contact sheet: every state composited at half size
        sheet = Image.new("RGB", (W, H // 2 * ((len(tl) + 1) // 2)), "black")
        for i, (name, img, a, b) in enumerate(tl):
            f = bg.copy()
            f.paste(img, (0, 0), img)
            sheet.paste(f.resize((W // 2, H // 2)), ((i % 2) * W // 2, (i // 2) * H // 2))
        sheet.save(out / "sheet.jpg", quality=85)
        return out / "sheet.jpg"
    args = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "24", "-i", str(out / "base.png")]
    chain, last = [], "[0:v]"
    for i, (name, img, a, b) in enumerate(tl, start=1):
        args += ["-loop", "1", "-framerate", "24", "-i", str(out / f"{name}.png")]
        chain.append(f"[{i}:v]format=rgba,fade=t=in:st={max(0, a):.2f}:d={FADE}:alpha=1,"
                     f"fade=t=out:st={max(0, b - FADE):.2f}:d={FADE}:alpha=1[t{i}]")
        chain.append(f"{last}[t{i}]overlay=0:0[v{i}]")
        last = f"[v{i}]"
    chain.append(f"{last}fade=t=in:d=1.5,fade=t=out:st={total - 2.5:.2f}:d=2.5,format=yuv420p[v]")
    video = d / (Path(spec_path).stem + ".mp4")
    args += ["-i", str(audio), "-filter_complex", ";".join(chain), "-map", "[v]", "-map", f"{len(tl) + 1}:a",
             "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage",
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(video)]
    subprocess.run(args, check=True)
    return video


VW, VH = 1080, 1920
VX = 72                     # text margin in the teaser
ICON_H = 900                # icon band at the top of the teaser
END = 4.0                   # closing card, while the music fades (spec "end" overrides)


def teaser_base(spec, d):
    """Icon band (top of the crop, where the face is) sinking into soot; title and byline under it."""
    x0, y0, x1, _ = spec["art_crop"]
    w = x1 - x0
    art = Image.open(d / spec["art"]).convert("RGB").crop((x0, y0, x1, y0 + round(w * ICON_H / VW)))
    img = Image.new("RGB", (VW, VH), C["soot"])
    img.paste(art.resize((VW, ICON_H), Image.LANCZOS), (0, 0))
    fade = Image.new("L", (VW, VH), 0)
    fd = ImageDraw.Draw(fade)
    for y in range(ICON_H - 240, ICON_H + 1):
        fd.line([(0, y), (VW, y)], fill=int(255 * ((y - ICON_H + 240) / 240) ** 1.4))
    fd.rectangle([0, ICON_H, VW, VH], fill=255)
    img.paste(Image.new("RGB", (VW, VH), C["soot"]), (0, 0), fade)
    d2 = ImageDraw.Draw(img)
    _tracked(d2, (VX, ICON_H + 20), spec["byline"].upper(), _font("Cinzel-Regular.ttf", 22), C["gilt"], 0.14)
    _tracked(d2, (VX - 2, ICON_H + 62), spec["title"].upper(), _font("Cinzel-SemiBold.ttf", 50), C["vellum"], 0.04)
    d2.rectangle([VX, ICON_H + 146, VX + 72, ICON_H + 149], fill=C["martyr"])
    return img


def teaser_stanza(spec, s):
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lat, en = _font(spec.get("text_font", "EBGaramond-Medium.ttf"), 44), _font("Cormorant-MediumItalic.ttf", 34)
    y = ICON_H + 184
    for line in s["latin"]:
        d.text((VX, y), line, font=lat, fill=C["vellum"])
        y += 56
    y += 26
    for line in s["english"]:
        d.text((VX, y), line, font=en, fill=C["giltLight"])
        y += 44
    return img


def teaser_intro(lines):
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((VX, ICON_H + 196), lines[0], font=_font("Cormorant-MediumItalic.ttf", 64), fill=C["giltLight"])
    y = ICON_H + 300
    for line in lines[1:]:
        d.text((VX, y), line, font=_font("EBGaramond-Medium.ttf", 42), fill=C["vellum"])
        y += 56
    return img


def teaser_end(lines=("The whole hymn, all eight stanzas,", "on YouTube.")):
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font("Cormorant-MediumItalic.ttf", 46)
    y = ICON_H + 200
    for line in lines:
        d.text((VX, y), line, font=f, fill=C["giltLight"])
        y += 60
    d.text((VX, y + 30), "allholysaints.com", font=_font("EBGaramond-Medium.ttf", 30), fill=C["ash"])
    return img


def teaser(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    d = ROOT / spec["dir"]
    t = spec["teaser"]
    a0, a1 = t["from"], t["to"]
    end_for = t.get("end", END)
    total = a1 - a0 + end_for
    out = d / "teaser"
    out.mkdir(exist_ok=True)
    teaser_base(spec, d).save(out / "base.png")
    ss = [s for s in spec["stanzas"] if s["n"] in t["stanzas"] and a0 <= s["at"] < a1]
    # the intro holds for "intro_for" s (default: until the first stanza is due) and fades out before the stanza fades in
    intro_for = t.get("intro_for", ss[0]["at"] - a0 - 1.2)
    tl = [("intro", teaser_intro(t["intro"]), 0, intro_for)] if t.get("intro") else []
    for i, s in enumerate(ss):
        end = ss[i + 1]["at"] - a0 - 0.3 if i + 1 < len(ss) else a1 - a0
        start = max(0, s["at"] - a0 - 1.2, intro_for if i == 0 and tl else 0)  # intro out, then stanza in
        tl.append((f"st{i}", teaser_stanza(spec, s), start, end))
    tl.append(("end", teaser_end(*[t["end_text"]] if t.get("end_text") else []), a1 - a0, total))
    for name, img, *_ in tl:
        img.save(out / f"{name}.png")
    args = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", str(out / "base.png")]
    chain, last = [], "[0:v]"
    for i, (name, img, a, b) in enumerate(tl, start=1):
        args += ["-loop", "1", "-framerate", "30", "-i", str(out / f"{name}.png")]
        fin = f"fade=t=in:st={a:.2f}:d={FADE}:alpha=1," if a > 0 else ""
        fout = f",fade=t=out:st={b - FADE:.2f}:d={FADE}:alpha=1" if b < total else ""
        chain.append(f"[{i}:v]format=rgba,{fin}format=rgba{fout}[t{i}]")
        chain.append(f"{last}[t{i}]overlay=0:0[v{i}]")
        last = f"[v{i}]"
    chain.append(f"{last}fade=t=out:st={total - 1:.2f}:d=1,format=yuv420p[v]")  # no fade-in: frame 1 is the hook
    chain.append(f"[{len(tl) + 1}:a]afade=t=in:d=0.25,afade=t=out:st={a1 - a0 - 0.5:.2f}:d={end_for:.2f}[a]")
    video = d / (Path(spec_path).stem + "-teaser.mp4")
    args += ["-ss", f"{a0:.2f}", "-t", f"{total:.2f}", "-i", str(d / spec["audio"]), "-filter_complex", ";".join(chain),
             "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-r", "30", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", str(video)]
    subprocess.run(args, check=True)
    return video


if __name__ == "__main__":
    if "--teaser" in sys.argv:
        print(teaser(sys.argv[1]))
    else:
        print(render(sys.argv[1], frames_only="--frames" in sys.argv))
