"""Lives of the Saints: series teaser for St. John of God (~29 s, vertical).
Opens on the Ember cover frame (the Shorts grid tile), then quick cuts from the six parts under Riko's lines,
the Ember title band, and the date card.   ../../../../.venv/bin/python teaser.py   (from work/lives/john-of-god/promo)"""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "teaser"; OUT = D / "build"; OUT.mkdir(parents=True, exist_ok=True)
F = ROOT.parents[2] / "brand/fonts"; FRAK = ROOT.parent / "UnifrakturMaguntia-Book.ttf"
W, H, FPS = 1080, 1920, 24
INK, PAPER, AMBER = (14, 12, 10), (226, 219, 203), (226, 150, 58)
SCORE = (227.0, 257.0)   # the score's loudest stretch, ending on its phrase dip at 257 s
GAP = 0.35
L = lambda p, n: ROOT / f"part{p}/live" / f"{n}.mp4"
# line -> cuts: (part, clip, in-point s, weight)
CUTS = [
    [(1, 1, 2.0, 1), (1, 4, 2.5, 1)],                    # at eight he followed a stranger away
    [(2, 1, 1.5, 1), (2, 2, 3.0, 1)],                    # a soldier under the gallows
    [(4, 1, 0.5, 1.2), (4, 3, 2.5, 1), (4, 6, 1.5, 1)],  # ran through Granada, weeping, chained
    [(6, 1, 0.5, 1), (6, 3, 2.0, 1.3)],                  # the hospital burned, he carried the sick out
    [(5, 8, 1.5, 1), (6, 6, 2.0, 1.3)],                  # how he became a saint
]
TITLE = (6, 4, 2.0)   # the river, under the Ember band


def ft(n, s): return ImageFont.truetype(str(F / n if not str(n).startswith("/") else n), s)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def ff(*a): subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *map(str, a)], check=True)


GRADE = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,unsharp=5:5:0.6,"
         "hue=s=0.3,colorbalance=bs=0.06:bm=0.04:rs=-0.03,eq=contrast=1.12:gamma=0.95")


def caption(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img); f = ft("EBGaramond-Medium.ttf", 50)
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > W - 200: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur); lh = 64; top = 1430 - lh * len(lines) // 2
    d.rectangle((0, top - 40, W, top + lh * len(lines) + 40), fill=(0, 0, 0, 150))
    for i, ln in enumerate(lines):
        d.text(((W - d.textlength(ln, font=f)) / 2, top + i * lh), ln, font=f, fill=PAPER + (255,))
    img.save(path)


def band(path, big, top, sub):
    """The Ember band (cover design C): amber strip, black numeral or word, Fraktur series name, italic line."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle([0, 1240, W, 1640], fill=AMBER + (255,))
    fb = ft("Cinzel-Bold.ttf", 280 if len(big) < 4 else 150)
    d.text((90, 1270 if len(big) < 4 else 1345), big, font=fb, fill=INK)
    x = 90 + d.textlength(big, font=fb) + 50
    d.text((x, 1320), top, font=ft(FRAK, 72), fill=INK)
    d.text((x, 1430), sub, font=ft("Cormorant-MediumItalic.ttf", 64), fill=INK)
    img.save(path)


def clip(src, ss, secs, name, over=None):
    o = OUT / f"{name}.mp4"
    ins = ["-ss", f"{ss:.2f}", "-i", src] + (["-i", over] if over else [])
    fc = f"[0:v]{GRADE}[bg];" + ("[bg][1:v]overlay=0:0,format=yuv420p[v]" if over else "[bg]format=yuv420p[v]")
    ff(*ins, "-filter_complex", fc, "-map", "[v]", "-r", FPS, "-frames:v", round(secs * FPS), "-c:v", "libx264", "-crf", 16, o)
    return o


def still(img, secs, name):
    o = OUT / f"{name}.mp4"
    ff("-loop", 1, "-framerate", FPS, "-i", img, "-vf", f"scale={W}:{H},format=yuv420p", "-r", FPS,
       "-frames:v", round(secs * FPS), "-c:v", "libx264", "-crf", 16, o)
    return o


TV = ROOT / "teaser" / "voice"
LINES = [  # same text as teaser/episode.json, voiced by build.py voice --part teaser
    "At eight years old, he followed a stranger away from home.", "Years later, a soldier, he stood under the gallows.",
    "Then he ran through Granada crying for mercy, and they called him mad.",
    "When the hospital burned, he carried the sick out through the flames.",
    "This is how he became a saint."]
VARIANTS = {
    # the series teaser (Thu Nov 26): five story lines, the title band, the date card
    "teaser": dict(story=[0, 1, 2, 3, 4], title=True, cover_sub="A vertical drama in six parts",
                   date=[("Begins Monday", "it"), ("DECEMBER 14", "num"), ("One part each evening", "it")],
                   date_voice=TV / "6.mp3", out="lives-of-the-saints-john-of-god-teaser.mp4"),
    # the Advent Sunday reminder (Sun Nov 29): the hook, the hound, her portrait, "begins tomorrow evening"
    "tomorrow": dict(story=[0, 1, 4], title=False, cover_sub="Begins tomorrow evening",
                     date=[("Tomorrow evening", "it"), ("PART I", "num"), ("St. John of God", "it")],
                     date_voice=ROOT / "tomorrow" / "voice" / "0.mp3", out="lives-of-the-saints-john-of-god-tomorrow.mp4"),
}


def main(name="teaser"):
    V = VARIANTS[name]
    ep_lines = LINES
    v = [TV / f"{i}.mp3" for i in range(6)] + [V["date_voice"]]
    segs, starts, t = [], [], 0.0
    # 1. cover frame: the Ember tile, held 0.5 s (YouTube's Shorts grid shows a frame of the video)
    cov = OUT / "cover.png"
    Image.open(ROOT / "promo/covers/part3-bg.png").convert("RGB").save(OUT / "cover-bg.png")
    # the teaser's tile says what it is, not a part number
    bg = Image.open(OUT / "cover-bg.png").convert("RGB"); band(OUT / "cover-band.png", "6", "Lives of the Saints", V["cover_sub"])
    bb = Image.open(OUT / "cover-band.png"); bg.paste(bb, (0, 0), bb); bg.save(cov)
    segs.append(still(cov, 0.5, "c00")); t = 0.5
    # 2. the story lines, two or three quick cuts each
    for i in V["story"]:
        cuts = CUTS[i]
        secs = dur(v[i]) + GAP + (0.25 if i == 4 else 0)
        caption(ep_lines[i], OUT / f"cap{i}.png"); starts.append(t)
        tot = sum(c[3] for c in cuts); left = secs
        for k, (p, n, ss, wgt) in enumerate(cuts):
            s = round(secs * wgt / tot * FPS) / FPS if k < len(cuts) - 1 else left
            segs.append(clip(L(p, n), ss, s, f"l{i}{k}", OUT / f"cap{i}.png")); left -= s
        t += secs
    # 3. series title over the climb, under the Ember band
    voiced = [v[i] for i in V["story"]]
    if V["title"]:
        secs = dur(v[5]) + 0.5; starts.append(t); voiced.append(v[5])
        band(OUT / "title-band.png", "6", "Lives of the Saints", "St. John of God")
        segs.append(clip(L(*TITLE[:2]), TITLE[2], secs, "t0", OUT / "title-band.png")); t += secs
    voiced.append(v[6])
    # 4. date card
    secs = dur(v[6]) + 1.1; starts.append(t)
    img = Image.new("RGB", (W, H), INK); d = ImageDraw.Draw(img)
    for k, w_ in ((70, 3), (84, 1)): d.rectangle((k, k + 260, W - k, H - k - 260), outline=PAPER, width=w_)
    (a, _), (b, _), (c, _) = V["date"]
    for txt, f, y, col in (("Lives of the Saints", ft(FRAK, 88), 700, PAPER), (a, ft("Cormorant-MediumItalic.ttf", 84), 880, PAPER),
                           (b, ft("Cinzel-Bold.ttf", 110), 1000, AMBER), (c, ft("Cormorant-MediumItalic.ttf", 60), 1170, PAPER)):
        d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=col)
    img.save(OUT / "date.jpg"); segs.append(still(OUT / "date.jpg", secs, "d0")); t += secs
    total = t
    (OUT / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
    pic = OUT / "picture.mp4"
    ff("-f", "concat", "-safe", 0, "-i", OUT / "list.txt", "-c:v", "libx264", "-crf", 14, "-pix_fmt", "yuv420p", "-r", FPS, pic)
    # audio: the voice over the score, score dipped -12 dB under the lines, full on the date card's tail
    inputs = sum((["-i", p] for p in voiced), []); nv = len(voiced)
    mix = ";".join(f"[{k + 1}:a]adelay={int(s * 1000)}|{int(s * 1000)}[n{k}]" for k, s in enumerate(starts))
    end_v = starts[-1] + dur(v[6])
    duck = f"1-0.75*clip(min((t-{starts[0] - 0.4:.2f})/0.4,({end_v + 0.8:.2f}-t)/0.8),0,1)"
    look = (f"[0:v]noise=alls=22:allf=t,eq=brightness='0.025*sin(2*PI*t*7.3)+0.015*sin(2*PI*t*2.1)':eval=frame,"
            f"vignette=PI/4.2,crop={W - 16}:{H - 16}:8+3*sin(t*5):8+3*cos(t*4.3),scale={W}:{H},"
            f"fade=t=out:st={total - 0.8:.2f}:d=0.8,format=yuv420p[v]")
    audio = (f"{mix};{''.join(f'[n{k}]' for k in range(nv))}amix=inputs={nv}:normalize=0[nar];"
             f"[{nv + 1}:a]atrim={SCORE[1] - total:.2f}:{SCORE[1]:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.3,volume=0.9,"
             f"volume='{duck}':eval=frame,afade=t=out:st={total - 1.2:.2f}:d=1.2[bed];[nar][bed]amix=inputs=2:normalize=0,apad[a]")
    final = ROOT / "teaser" / V["out"]
    ff("-i", pic, *inputs, "-i", ROOT / "score.wav", "-filter_complex", f"{look};{audio}", "-map", "[v]", "-map", "[a]",
       "-t", f"{total:.2f}", "-c:v", "libx264", "-crf", 18, "-preset", "medium", "-r", FPS, "-c:a", "aac", "-b:a", "160k", "-ar", 44100,
       "-movflags", "+faststart", final)
    m = subprocess.run(["ffmpeg", "-nostdin", "-i", str(final), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(m.rsplit("I:", 1)[1].split("LUFS")[0]); tmp = final.with_suffix(".tmp.mp4")
    ff("-i", final, "-c:v", "copy", "-af", f"volume={-16 - lufs:.2f}dB,alimiter=limit=0.84:level=false", "-c:a", "aac", "-b:a", "160k",
       "-ar", 44100, "-movflags", "+faststart", tmp)
    tmp.replace(final)
    print(final, round(total, 2), "s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "teaser")
