"""Ember covers (design C) for the six John of God parts + release copies that open on the cover for 0.5 s.
    ../../../../.venv/bin/python covers.py [part ...]      (from work/lives/john-of-god/promo)"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))   # GRADE, band, ff from this series' teaser.py
from teaser import GRADE, band, ff

SAINT = Path(__file__).resolve().parent.parent
OUT = SAINT / "promo" / "covers"; OUT.mkdir(parents=True, exist_ok=True)
# part -> (live clip, second, (zoom, face x, face y) so the face lands at (0.5, 0.33) above the band)
PARTS = {1: ("6", 3.5, (1.5, .50, .33)), 2: ("1", 3.5, (1.3, .50, .40)), 3: ("1", 3.5, (1.5, .45, .45)),
         4: ("3", 3.5, (1.5, .50, .42)), 5: ("8", 1.5, (1.5, .47, .45)), 6: ("3", 2.0, (1.7, .50, .30))}
NUM = ["I", "II", "III", "IV", "V", "VI"]
ONLY = {int(a) for a in sys.argv[1:] if a.isdigit()}
for n, (clip, ss, (z, fx, fy)) in PARTS.items():
    if ONLY and n not in ONLY: continue
    title = json.loads((SAINT / f"part{n}/episode.json").read_text())["part_title"]
    bg, bnd, cov = OUT / f"part{n}-bg.png", OUT / f"part{n}-band.png", OUT / f"part{n}-cover.jpg"
    vf = f"crop=iw/{z}:ih/{z}:iw*{fx - .5 / z}:ih*{fy - .33 / z},scale=1080:1920:flags=lanczos," + GRADE
    ff("-ss", ss, "-i", SAINT / f"part{n}/live/{clip}.mp4", "-frames:v", 1, "-vf", vf, bg)
    band(bnd, NUM[n - 1], "Lives of the Saints", title)
    im = Image.open(bg).convert("RGB"); b = Image.open(bnd); im.paste(b, (0, 0), b); im.save(cov, quality=94)
    if "--nomovie" in sys.argv: continue
    master = SAINT / f"part{n}/lives-john-of-god-part{n}-live-approved.mp4"
    rel = OUT / f"part{n}-release.mp4"
    ff("-loop", 1, "-framerate", 24, "-t", 0.5, "-i", cov, "-i", master, "-filter_complex",
       "[0:v]scale=1080:1920,setsar=1,fps=24,format=yuv420p[c];[1:v]scale=1080:1920,setsar=1,fps=24,format=yuv420p[m];"
       "[c][m]concat=n=2:v=1:a=0[v];[1:a]adelay=500|500[a]",
       "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-b:v", "14M", "-maxrate", "16M", "-bufsize", "28M", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
       "-ar", 44100, "-movflags", "+faststart", rel)
    print(rel)
