"""The weekly music Story as a video (Instagram): Luis's animated album art behind this week's track, its opening
playing, and the music card's words over the foot of the picture.

    python engine/music_story_video.py docs/music/blue-chant-vol1.json <loop.mp4> all     # or a track number

The loop (a ~10 s animation; its last frame doesn't meet its first) is cross-faded back into its own start, so the
15 s Story never jumps. Writes <dir>/story-videos/<n>.mp4; upload them to the album's release as story-<n>.mp4 and
set data/music.json "story_video" (story_music.run_music then queues the video for Instagram and keeps the still card
for Facebook, whose Stories here are image-only). Encoded like music_clips.py (AAC 128k / 44.1k, CRF 18): a heavier
Story showed on Instagram as a silent still.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
from common import BRAND, ROOT
from cards import font as _font, monogram as _monogram, roman, tracked as _tracked
from stories import W, H, X, SAFE_BOTTOM

LENGTH = 15.0   # seconds
XFADE = 1.0     # loop seam
C = BRAND["colors"]


def _rgb(hexcol):
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def overlay(spec, track):
    """Transparent 1080x1920: a soot fade up from the foot, then the card's words inside Instagram's safe area."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    soot = _rgb(C["soot"])
    top, solid = 960, 1250    # fade starts below the lectern's book; fully dark from `solid`
    px = img.load()
    for y in range(top, H):
        a = int(235 * min(1, (y - top) / (solid - top)) ** 1.4)
        for x in range(W):
            px[x, y] = (*soot, a)
    d = ImageDraw.Draw(img)
    y = 1280   # the block ends ~50 px above the "Listen at" line
    _tracked(d, (X, y), "THE MUSIC OF ALL SAINTS", _font("Cinzel-Regular.ttf", 26), _rgb(C["gilt"]), 0.16)
    y += 50
    _tracked(d, (X, y), f"THIS WEEK  ·  {roman(track['n'])}", _font("Cinzel-Regular.ttf", 24), _rgb(C["ash"]), 0.16)
    y += 40
    d.text((X, y), track["title"], font=_font("EBGaramond-Medium.ttf", 62), fill=_rgb(C["vellum"]))
    y += 80
    d.text((X, y), f"{spec['album']}, {spec['volume']}", font=_font("Cormorant-MediumItalic.ttf", 40), fill=_rgb(C["giltLight"]))
    d.text((X, SAFE_BOTTOM - 96), "Listen at allholysaints.com/music", font=_font("EBGaramond-Medium.ttf", 32), fill=_rgb(C["vellum"]))
    _monogram(d, X, SAFE_BOTTOM - 40, 30, _rgb(C["gilt"]))
    d.text((X + 110, SAFE_BOTTOM - 37), "Music by Luis E. Bonilla · made with AI tools", font=_font("EBGaramond-Medium.ttf", 28),
           fill=_rgb(C["ash"]))
    return img


def render(spec_path, loop, n):
    spec = json.loads(Path(spec_path).read_text())
    track = next(t for t in spec["tracks"] if t["n"] == n)
    d = ROOT / spec["dir"]
    out = d / "story-videos"
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{n}-text.png"
    overlay(spec, track).save(png)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(loop)]))
    # two passes of the loop, the second fading in over the last second of the first
    chain = [f"[0:v]scale={W}:{H},setsar=1,fps=30,split[a][b]",
             f"[a][b]xfade=transition=fade:duration={XFADE}:offset={dur - XFADE:.3f}[bg]",
             "[bg][1:v]overlay=0:0,fade=t=out:st=%.2f:d=1,format=yuv420p[v]" % (LENGTH - 1),
             f"[2:a]afade=t=in:d=0.3,afade=t=out:st={LENGTH - 2:.2f}:d=2[aud]"]
    video = out / f"{n}.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(loop),
                    "-loop", "1", "-framerate", "30", "-t", f"{LENGTH:.2f}", "-i", str(png),
                    "-ss", f"{track['at'] + track.get('from', 0):.2f}", "-t", f"{LENGTH:.2f}", "-i", str(d / spec["audio"]),
                    "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "[aud]", "-t", f"{LENGTH:.2f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30", "-g", "60",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(video)], check=True)
    return video


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    for n in ([t["n"] for t in spec["tracks"]] if sys.argv[3] == "all" else [int(sys.argv[3])]):
        print(render(sys.argv[1], Path(sys.argv[2]), n))
