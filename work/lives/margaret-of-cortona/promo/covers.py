"""Ember covers (design C) for the six parts, and release copies that open on them for 0.5 s (YouTube's Shorts grid
shows a frame of the video, not the uploaded cover). The approved cut is untouched: picture and audio start 0.5 s later.
    ../../../../.venv/bin/python covers.py [part ...]      (from work/lives/margaret-of-cortona/promo)"""
import json, subprocess
from pathlib import Path
from PIL import Image
from teaser import GRADE, band, ff

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "promo" / "covers"; OUT.mkdir(exist_ok=True)
# part -> (clip with her face, second, approved master)
PARTS = {
    1: (ROOT / "part1/live/2.mp4", 6.0, ROOT / "part1/nocturnes-margaret-part1-live-approved.mp4"),
    2: (ROOT / "part2/live/2.mp4", 4.0, ROOT / "part2/nocturnes-margaret-part2-live-approved.mp4"),
    3: (ROOT / "part3/live/6.mp4", 1.5, ROOT / "part3/nocturnes-margaret-part3-live-approved.mp4"),
    4: (ROOT / "part4/live/8.mp4", 4.0, ROOT / "part4/nocturnes-margaret-part4-live-approved.mp4"),
    5: (ROOT / "part5/live/3.mp4", 4.0, ROOT / "part5/nocturnes-margaret-part5-live-approved.mp4"),
    6: (ROOT / "part6/live/8.mp4", 4.0, ROOT / "part6/nocturnes-margaret-part6-live-approved.mp4"),
}
# part -> (zoom, face x, face y in the frame); the face lands at (0.5, 0.33) of the cover
CROP = {2: (1.7, .53, .40), 4: (1.7, .51, .39), 5: (1.8, .58, .47)}
NUM = ["I", "II", "III", "IV", "V", "VI"]


def title(n):
    ep = ROOT / f"part{n}/episode.json"
    return json.loads(ep.read_text())["part_title"]


import sys
ONLY = {int(a) for a in sys.argv[1:]}
for n, (clip, ss, master) in PARTS.items():
    if ONLY and n not in ONLY: continue
    bg, bnd, cov = OUT / f"part{n}-bg.png", OUT / f"part{n}-band.png", OUT / f"part{n}-cover.jpg"
    vf = GRADE
    if n in CROP:
        z, fx, fy = CROP[n]
        vf = f"crop=iw/{z}:ih/{z}:iw*{fx - .5 / z}:ih*{fy - .33 / z},scale=1080:1920:flags=lanczos," + GRADE
    ff("-ss", ss, "-i", clip, "-frames:v", 1, "-vf", vf, bg)
    band(bnd, NUM[n - 1], "Lives of the Saints", title(n))
    im = Image.open(bg).convert("RGB"); b = Image.open(bnd); im.paste(b, (0, 0), b); im.save(cov, quality=94)
    rel = OUT / f"part{n}-release.mp4"
    ff("-loop", 1, "-framerate", 24, "-t", 0.5, "-i", cov, "-i", master, "-filter_complex",
       "[0:v]scale=1080:1920,setsar=1,fps=24,format=yuv420p[c];[1:v]scale=1080:1920,setsar=1,fps=24,format=yuv420p[m];"
       "[c][m]concat=n=2:v=1:a=0[v];[1:a]adelay=500|500[a]",
       "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", 18, "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
       "-ar", 44100, "-movflags", "+faststart", rel)
    print(rel)
