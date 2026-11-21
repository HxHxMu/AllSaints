"""Blue Chant, Volume I: the full album as a 16:9 YouTube video. The icon on the left, the track list
on the right with the playing piece lit; one still frame per track, cut when the track changes.
Writes frames/, chapters.txt and blue-chant-vol1-longform.mp4 next to this file."""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from playlist_cover import _font, _tracked, C

here = Path(__file__).parent
SRC = Path.home() / "Downloads"
TRACKS = [("Ave Maria", "Ave Maria.wav"), ("Benedicta in Mulieribus", "Benedicta In Mulieribus.wav"),
          ("Veritatis", "Veritatis.wav"), ("Trinitas", "Trinitas.m4a"), ("Rosa Mystica", "Rosa Mystica.wav")]
ROMAN = ["I", "II", "III", "IV", "V"]
GAP = 2.0  # seconds of silence between pieces
W, H = 1920, 1080
NIGHT = (11, 20, 36)
GILT_LIGHT = "#E6C878"


def duration(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).strip())


def monogram(d, x0, y0, size, fill):
    mono = _font("Cinzel-SemiBold.ttf", size)
    x = x0 + _tracked(d, (x0, y0), "A.S.", mono, fill, tracking=0.04) + size * 0.18
    top, bottom = y0 + mono.getbbox("A")[1] - size * 0.12, y0 + mono.getbbox("A")[3] + size * 0.12
    stem, cx = size * 0.075, x + size * 0.25
    d.rectangle([cx - stem / 2, top, cx + stem / 2, bottom], fill=fill)
    bar = top + (bottom - top) * 0.3
    d.rectangle([x, bar, x + size * 0.5, bar + stem], fill=fill)


def base():
    img = Image.new("RGB", (W, H), NIGHT)
    art = Image.open(here / "art.jpg").convert("RGB").resize((H, H), Image.LANCZOS)
    img.paste(art, (0, 0))
    # the painting's right edge melts into the night panel
    fade = Image.new("L", (H, H), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(H - 180, H):
        fd.line([(x, 0), (x, H)], fill=int(255 * ((x - (H - 180)) / 180) ** 1.6))
    img.paste(Image.new("RGB", (H, H), NIGHT), (0, 0), fade)
    d = ImageDraw.Draw(img)
    X = 1170
    monogram(d, X, 120, 46, GILT_LIGHT)
    _tracked(d, (X, 214), "THE MUSIC OF ALL SAINTS", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
    _tracked(d, (X - 4, 256), "BLUE CHANT", _font("Cinzel-SemiBold.ttf", 104), C["vellum"], 0.06)
    d.text((X, 388), "Volume I · Gregorian chant played as jazz", font=_font("Cormorant-MediumItalic.ttf", 40), fill=C["gilt"])
    d.rectangle([X, 470, X + 90, 472], fill=C["martyr"])
    d.text((X, H - 110), "allholysaints.com", font=_font("EBGaramond-Medium.ttf", 28), fill=C["ash"])
    return img, X


def frame(current):
    img, X = base()
    d = ImageDraw.Draw(img)
    num, name = _font("Cinzel-SemiBold.ttf", 34), _font("EBGaramond-Medium.ttf", 44)
    for i, (title, _) in enumerate(TRACKS):
        y = 530 + i * 74
        on = i == current
        if on:
            d.rectangle([X - 30, y + 8, X - 24, y + 46], fill=C["martyr"])
        d.text((X, y + 8), ROMAN[i], font=num, fill=C["gilt"] if on else "#5E5A52")
        d.text((X + 90, y), title, font=name, fill=C["vellum"] if on else "#6F6A60")
    return img


def main():
    (here / "frames").mkdir(exist_ok=True)
    durs = [duration(SRC / f) for _, f in TRACKS]
    concat, chapters, t = [], [], 0.0
    for i, d in enumerate(durs):
        p = here / "frames" / f"{i + 1}.png"
        frame(i).save(p)
        length = d + (GAP if i < len(durs) - 1 else 0)
        concat += [f"file '{p}'", f"duration {length:.3f}"]
        chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {ROMAN[i]}. {TRACKS[i][0]}")
        t += length
    concat.append(f"file '{here / 'frames' / f'{len(durs)}.png'}'")  # concat demuxer needs the last file twice
    (here / "frames.txt").write_text("\n".join(concat) + "\n")
    (here / "chapters.txt").write_text("\n".join(chapters) + "\n")

    # audio: the pieces back to back with a short silence between
    ins, parts = [], []
    for i, (_, f) in enumerate(TRACKS):
        ins += ["-i", str(SRC / f)]
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo" +
                     (f",apad=pad_dur={GAP}" if i < len(TRACKS) - 1 else "") + f"[a{i}]")
    graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(TRACKS))) + f"concat=n={len(TRACKS)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[a]",
                    "-c:a", "pcm_s16le", str(here / "album.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(here / "frames.txt"),
                    "-i", str(here / "album.wav"), "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage",
                    "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart",
                    str(here / "blue-chant-vol1-longform.mp4")], check=True)
    print("\n".join(chapters), f"\ntotal {t / 60:.1f} min")


if __name__ == "__main__":
    if sys.argv[1:] == ["preview"]:
        frame(0).save(here / "frame-preview.png")
    else:
        main()
