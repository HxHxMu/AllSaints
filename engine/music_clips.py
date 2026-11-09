"""Short vertical clips from an album (docs/music/*.json): one Reel / Short per track, pointing to the full hour on YouTube.

    python engine/music_clips.py docs/music/blue-chant-vol1.json 1        # track I
    python engine/music_clips.py docs/music/blue-chant-vol1.json all

1080x1920: the album art on top with a slow push-in (so it never reads as a still), the album and track title under it,
an opening card already up on frame 1 ("intro": what this is), then "under" while the music plays, then the closing
card (the mark, why to follow, where the full hour is). The music is audible from the first frame. Each track's clip
starts at its "from" (seconds into the track) or, if unset, at the loudest "clip"-long stretch of its middle; the
chosen start is written back to the spec so it can be tuned by ear. Writes <dir>/clips/<n>.mp4 and <n>-cover.jpg.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from common import BRAND, ROOT
from playlist_cover import _font, _tracked
from compilation import _monogram

VW, VH = 1080, 1920
VX = 72                     # text margin
ART = 1080                  # square art band at the top
TOP = 140                   # night sky above the art: headroom for the halo in grid crops (the art's floor sinks into the title fade)
NIGHT = (11, 20, 36)        # the album's night blue (its cover and long-form video)
FADE = 0.8
INTRO = 4.0                 # opening card, then "under"
ZOOM = 0.10                 # push-in over the whole clip
C = BRAND["colors"]
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def loudest(audio, at, length, clip, sr=8000):
    """Start (s into the track) of the loudest clip-long window between 15% and 85% of the track."""
    raw = subprocess.check_output(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{at:.2f}", "-t", f"{length:.2f}",
                                   "-i", str(audio), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"])
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    rms = np.sqrt(np.add.reduceat(x ** 2, np.arange(0, len(x), sr)) / sr)   # one value per second
    lo, hi = int(length * 0.15), int(length * 0.85 - clip)
    if hi <= lo:
        return 0.0
    win = int(clip)
    means = [rms[s:s + win].mean() for s in range(lo, hi)]
    return float(lo + int(np.argmax(means)))


def base(spec, track):
    """Night ground, the art's lower edge melting into it, album and track title. The art itself is a moving layer."""
    img = Image.new("RGBA", (VW, VH), NIGHT + (255,))
    fade = Image.new("L", (VW, VH), 255)
    fd = ImageDraw.Draw(fade)
    fd.rectangle([0, TOP, VW, ART - 260], fill=0)
    for y in range(TOP, TOP + 40):  # the art's top edge melts into the sky above it
        fd.line([(0, y), (VW, y)], fill=int(255 * (1 - (y - TOP) / 40)))
    for y in range(ART - 260, ART + 1):
        fd.line([(0, y), (VW, y)], fill=int(255 * ((y - ART + 260) / 260) ** 1.4))
    img.putalpha(fade)
    d = ImageDraw.Draw(img)
    _tracked(d, (VX, ART + 10), f"{spec['album']} · {spec['volume']}".upper(), _font("Cinzel-Regular.ttf", 32), C["gilt"], 0.14)
    _tracked(d, (VX - 3, ART + 62), f"{ROMAN[track['n']]}. {track['title']}".upper(), _font("Cinzel-SemiBold.ttf", 72), C["vellum"], 0.04)
    d.rectangle([VX, ART + 170, VX + 90, ART + 174], fill=C["martyr"])
    return img


def lines_card(lines, first_big=True):
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = ART + 220
    for line in lines:
        d.text((VX, y), line, font=_font("Cormorant-MediumItalic.ttf", 84 if first_big else 68), fill=C["giltLight"])
        y += 100 if first_big else 84
    return img


def end_card(spec):
    """The mark, why to follow, then where the whole album is."""
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _monogram(d, VX, ART + 220, 48, C["gilt"])
    y = ART + 320
    for line in ("A forgotten saint every morning,", "and music for the quiet hours."):
        d.text((VX, y), line, font=_font("Cormorant-MediumItalic.ttf", 68), fill=C["giltLight"])
        y += 84
    d.text((VX, y + 40), "The full hour on YouTube · @AllHolySaints", font=_font("EBGaramond-Medium.ttf", 46), fill=C["vellum"])
    return img


def render(spec_path, n):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text())
    d = ROOT / spec["dir"]
    track = next(t for t in spec["tracks"] if t["n"] == n)
    clip, end_for = spec["clip"], spec["end"]
    if track.get("from") is None:
        track["from"] = loudest(d / spec["audio"], track["at"], track["length"], clip)
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    total = clip + end_for
    out = d / "clips"
    work = out / f"{n}"
    work.mkdir(parents=True, exist_ok=True)
    art = Image.open(d / spec["art"]).convert("RGB").resize((ART * 3, ART * 3), Image.LANCZOS)  # big source: no zoompan jitter
    art.save(work / "art.png")
    layers = [("base", base(spec, track), 0, total),
              ("intro", lines_card(spec["intro"]), 0, INTRO),
              ("under", lines_card(spec["under"], first_big=False), INTRO, clip),
              ("end", end_card(spec), clip, total)]
    for name, img, *_ in layers:
        img.save(work / f"{name}.png")
    frames = round(total * 30)
    z = f"1+{ZOOM}*on/{frames}"
    chain = [f"[0:v]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/4-(ih/zoom/4)':d={frames}:s={ART}x{ART}:fps=30,"
             f"pad={VW}:{VH}:0:{TOP}:color=0x{''.join(f'{c:02x}' for c in NIGHT)}[bg]"]
    args = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", str(work / "art.png")]
    last = "[bg]"
    for i, (name, _, a, b) in enumerate(layers, start=1):
        args += ["-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", str(work / f"{name}.png")]
        fin = f"fade=t=in:st={a:.2f}:d={FADE}:alpha=1," if a > 0 else ""
        fout = f",fade=t=out:st={b - FADE:.2f}:d={FADE}:alpha=1" if b < total else ""
        chain.append(f"[{i}:v]format=rgba,{fin}format=rgba{fout}[t{i}]")
        chain.append(f"{last}[t{i}]overlay=0:0[v{i}]")
        last = f"[v{i}]"
    chain.append(f"{last}fade=t=out:st={total - 1:.2f}:d=1,format=yuv420p[v]")   # no fade-in: frame 1 is the hook
    chain.append(f"[{len(layers) + 1}:a]afade=t=in:d=0.25,afade=t=out:st={clip - 0.5:.2f}:d={end_for:.2f}[a]")
    video = out / f"{n}.mp4"
    args += ["-ss", f"{track['at'] + track['from']:.2f}", "-t", f"{total:.2f}", "-i", str(d / spec["audio"]),
             "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30", "-g", "60",   # Story-safe: Instagram showed a
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(video)]  # 256k/48k Story as a silent still
    subprocess.run(args, check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(video), "-frames:v", "1", "-q:v", "2",
                    str(out / f"{n}-cover.jpg")], check=True)
    return video


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    for n in ([t["n"] for t in spec["tracks"]] if sys.argv[2] == "all" else [int(sys.argv[2])]):
        print(render(sys.argv[1], n))
