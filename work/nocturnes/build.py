"""Lives of the Saints (silent-film series) test: a saint micro-drama part in the style of 1920s German Expressionist silent film.
    ../.venv/bin/python build.py art|voice|video   (run from engine/ via sys.path)"""
import json, subprocess, sys, concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent   # shared: score.wav, fonts
# --part part2: build that part from its own folder (episode.json, voice/, live/, build/); default is Part I here
D = ROOT / sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else ROOT
EP = json.loads((D / "episode.json").read_text())
W, H = 1080, 1920
FONTS = Path(__file__).resolve().parents[2] / "brand/fonts"
STYLE = ("A still frame from a 1920s German Expressionist silent film, in the manner of the great silent epics: "
         "black-and-white orthochromatic film, extreme chiaroscuro, a single hard light source, deep black shadows, long "
         "distorted shadows cast on walls and ground, theatrical painted sets with skewed angular architecture, mist and "
         "shafts of light, visible film grain, soft vignette. Setting: thirteenth-century central Italy, with authentic "
         "medieval clothing and buildings. Solemn and reverent in mood, never horror, never gore. Vertical 9:16 "
         "composition, the image fills the frame edge to edge. No text, no letters, no title cards, no border, no frame.")


def art():
    import illustrate
    (D / "art").mkdir(exist_ok=True)
    def one(i):
        p = D / "art" / f"{i}.jpg"
        if "scene" in EP["beats"][i] and not p.exists():   # only beats with a scene get a still
            raw = illustrate._generate(f"{STYLE}\n\nScene: {EP['beats'][i]['scene']}")
            illustrate._save(raw, p, trim=0.0)
        return p
    with cf.ThreadPoolExecutor(3) as ex:   # the Gemini key rate-limits (429) at 4+
        print(list(ex.map(one, range(len(EP["beats"])))))


def voice():
    import tts
    (D / "voice").mkdir(exist_ok=True)
    paths = [D / "voice" / f"{i}.mp3" for i in range(len(EP["beats"]))]
    beats = list(EP["beats"])
    if EP.get("next_voice"):  # the narrated teaser on the "next" card
        beats.append({"role": "close", "text": EP["next_voice"]}); paths.append(D / "voice" / "next.mp3")
    per = [tts._gemini_beat(b, {}, p) for b, p in zip(beats, paths)]
    tts._pace(per, paths)
    trim(paths)
    print([round(tts.duration(p), 2) for p in paths])


def trim(paths):
    """Cut the silence Gemini leaves before and after a line (it varies by take; the pause between lines is GAP)."""
    sr = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08"
    for p in paths:
        t = p.with_suffix(".trim.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-af", f"{sr},areverse,{sr},areverse",
                        "-b:a", "192k", str(t)], check=True)
        t.replace(p)


# ---- video ----
def font(name, size):
    return ImageFont.truetype(str(name if "/" in str(name) else FONTS / name), size)


FRAK = ROOT / "UnifrakturMaguntia-Book.ttf"
LIVE = "--live" in sys.argv
# --timings f.json --audio f.mp4: rebuild a cut whose audio survived (after the 2026-11-20 drive loss, Part I's approved
# master existed only as a 720p phone copy): segments take the measured durations [title, beat 1..n, question, next]
# and the saved audio track is copied in unchanged instead of mixing voice and score again
_arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
TIMES = json.loads(Path(_arg("--timings")).read_text()) if _arg("--timings") else None
AUDIO = _arg("--audio")
GAP = EP.get("gap", 0.9)   # pause after each line (lines are silence-trimmed; 0.35 s was the gap when takes kept their own pauses)
SCORE_FROM, SCORE_END = EP.get("score", [0.0, 65.5])   # score.wav seconds; each part ends on a phrase dip
INK, PAPER = (12, 11, 10), (226, 219, 203)


def border(d, inset=70):
    """A silent-film intertitle frame: double rule with corner ornaments."""
    for k, w in ((inset, 3), (inset + 14, 1)):
        d.rectangle((k, k + 260, W - k, H - k - 260), outline=PAPER, width=w)
    for x, y in ((inset, inset + 260), (W - inset, inset + 260), (inset, H - inset - 260), (W - inset, H - inset - 260)):
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=PAPER)


def centered(d, y, text, f, fill=PAPER, gap=1.25):
    for line in text.split("\n"):
        w = d.textlength(line, font=f)
        d.text(((W - w) / 2, y), line, font=f, fill=fill)
        y += int(f.size * gap)
    return y


def card(path, kind):
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    border(d)
    if kind == "title":
        y = centered(d, 690, "Lives of the Saints", font(FRAK, 92))
        y = centered(d, y + 50, "SAINT MARGARET\nOF CORTONA", font("Cinzel-SemiBold.ttf", 76), gap=1.2)
        d.line((W / 2 - 120, y + 40, W / 2 + 120, y + 40), fill=PAPER, width=2)
        centered(d, y + 90, f"Part {EP['part']}\n{EP['part_title']}", font("Cormorant-MediumItalic.ttf", 64), gap=1.15)
    elif kind == "question":
        centered(d, 820, EP["question"], font("Cormorant-MediumItalic.ttf", 72), gap=1.25)
    else:
        y = centered(d, 760, EP["next"].replace(" · ", "\n"), font("Cormorant-MediumItalic.ttf", 72), gap=1.2)
        from cards import monogram
        monogram(d, W / 2 - 64, y + 110, 44, PAPER)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(path, quality=95)


def caption(path, text):
    """Narration line in a silent-film lower card: pale serif on a dark band."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("EBGaramond-Medium.ttf", 50)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > W - 200:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    lh = 64
    top = 1430 - lh * len(lines) // 2
    d.rectangle((0, top - 40, W, top + lh * len(lines) + 40), fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        w = d.textlength(line, font=f)
        d.text(((W - w) / 2, top + i * lh), line, font=f, fill=PAPER + (255,))
    img.save(path)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def video():
    out = D / "build"; out.mkdir(exist_ok=True)
    for k in ("title", "question", "next"):
        card(out / f"card-{k}.jpg", k)
    fps, segs = 24, []
    moves = ["in", "out", "in", "right", "in", "left", "in", "out"]
    # card: still, flicker; image beats: slow push, B/W grade, flicker
    def still(img, secs, name):
        o = out / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{secs:.3f}", "-i", str(img),
                        "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(fps), "-frames:v", str(round(secs * fps)), "-c:v", "libx264", "-crf", "16", str(o)], check=True)
        return o
    # Part I runs on the score from its start (organ intro under the title) to its phrase end at 65.5 s; the cards
    # take up the difference, so the music breathes on them
    beats = sum(dur(D / "voice" / f"{i}.mp3") + GAP for i in range(len(EP["beats"])))
    spare = SCORE_END - SCORE_FROM - beats
    # the narrator voices the teaser over the "next" card (Luis, 2026-11-18: an open story can't end on "pray for us")
    nv = D / "voice" / "next.mp3" if EP.get("next_voice") else None   # the last part has no teaser: an end card
    t_next = dur(nv) + 1.4 if nv else 5.0
    spare -= t_next
    t_title, t_q = spare * 0.45, spare * 0.55
    if TIMES:
        t_title, t_q, t_next = TIMES[0], TIMES[-2], TIMES[-1]
    segs.append((still(out / "card-title.jpg", t_title, "s00"), t_title, None))
    for i, b in enumerate(EP["beats"]):
        v = D / "voice" / f"{i}.mp3"
        secs = TIMES[1 + i] if TIMES else dur(v) + GAP
        caption(out / f"cap{i}.png", b["text"])
        n = int(secs * fps)
        z = {"in": f"1.0+0.10*on/{n}", "out": f"1.10-0.10*on/{n}"}.get(moves[i % len(moves)], "1.08")
        x = {"right": f"(iw-iw/zoom)*on/{n}", "left": f"(iw-iw/zoom)*(1-on/{n})"}.get(moves[i % len(moves)], "(iw-iw/zoom)/2")
        o = out / f"s{i + 1:02d}.mp4"
        clip = D / "live" / f"{i + 1}.mp4"
        if LIVE and clip.exists():  # Luis's live-action clips (any length >= the beat, 24 fps): cover-crop, grade to the series look;
            # shots without a clip fall back to the still in art/ with a slow push (mixed parts, 2026-11-18)
            ss = max(0.0, dur(clip) - secs - 0.5) if i == len(EP["beats"]) - 1 else 0.0   # the prayer: end on her face
            sat = 0.0 if (D == ROOT and i == 3) else 0.3   # keep a trace of amber in flame and lantern; Part I shot 4 came out sepia
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{ss:.2f}", "-i", str(clip), "-i", str(out / f"cap{i}.png"),
                            "-filter_complex", f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,unsharp=5:5:0.6,"   # Gemini free clips are ~720p: firm up the upscale (grain goes on after)
                            f"hue=s={sat},colorbalance=bs=0.06:bm=0.04:rs=-0.03,eq=contrast=1.12:gamma=0.95[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]",
                            "-map", "[v]", "-r", str(fps), "-frames:v", str(round(secs * fps)), "-c:v", "libx264", "-crf", "16", str(o)], check=True)
            segs.append((o, secs, v))
            if i == len(EP["beats"]) - 1:
                segs.append((still(out / "card-question.jpg", t_q, "s07q"), t_q, None))
            continue
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{secs:.3f}",
                        "-i", str(D / "art" / f"{i}.jpg"), "-i", str(out / f"cap{i}.png"), "-filter_complex",
                        f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d=1:s={W}x{H}:fps={fps},"
                        f"hue=s=0,eq=contrast=1.15[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]",
                        "-map", "[v]", "-r", str(fps), "-frames:v", str(round(secs * fps)), "-c:v", "libx264", "-crf", "16", str(o)], check=True)
        segs.append((o, secs, v))
        if i == len(EP["beats"]) - 1:  # the question card, after the prayer (Luis, 2026-11-17)
            segs.append((still(out / "card-question.jpg", t_q, "s07q"), t_q, None))
    segs.append((still(out / "card-next.jpg", t_next, "s99"), t_next, nv))
    # concat picture
    lst = out / "list.txt"
    lst.write_text("".join(f"file '{s}'\n" for s, _, _ in segs))
    pic = out / "picture.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(fps), str(pic)], check=True)
    total = sum(s for _, s, _ in segs)
    # narration track: each beat at its segment's start
    t, inputs, delays = 0.0, [], []
    for s, secs, v in segs:
        if v:
            inputs += ["-i", str(v)]
            delays.append(t)
        t += secs
    mix = ";".join(f"[{k + 1}:a]adelay={int(d * 1000)}|{int(d * 1000)}[n{k}]" for k, d in enumerate(delays))
    music = str(ROOT / "score.wav")
    nb = len(delays)
    n = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}.get(EP["part"], EP["part"])
    final = D / f"nocturnes-margaret-part{n}{'-live' if LIVE else ''}{'-approved' if AUDIO else ''}.mp4"
    # film look: grain, flicker (brightness wobble), vignette, gate weave; music low under the voice, louder on cards
    look = (f"[0:v]noise=alls=22:allf=t,eq=brightness='0.025*sin(2*PI*t*7.3)+0.015*sin(2*PI*t*2.1)':eval=frame,"
            f"vignette=PI/4.2,crop={W - 16}:{H - 16}:8+3*sin(t*5):8+3*cos(t*4.3),scale={W}:{H},"
            f"fade=t=in:d=0.8,fade=t=out:st={total - 1:.2f}:d=1,format=yuv420p[v]")
    # the score carries the story: full on the cards, one gentle dip (-12 dB; -6 dB was too loud under the live-action cut, Luis 2026-11-18) for the whole narration, eased in over
    # 1.2 s and out over 1.5 s. A sidechain compressor pumped on every syllable (Luis, 2026-11-18: distracting).
    # one dip for the story, the music rises on the question card, a second dip for the teaser
    last = len(EP["beats"]) - 1
    a, b = delays[0], delays[last] + dur(D / "voice" / f"{last}.mp3")
    win = lambda x, y: f"clip(min((t-{x - 1.2:.2f})/1.2,({y + 1.5:.2f}-t)/1.5),0,1)"
    duck = f"1-0.75*max({win(a, b)},{win(delays[-1], delays[-1] + dur(nv))})" if nv else f"1-0.75*{win(a, b)}"
    audio = (f"{mix};{''.join(f'[n{k}]' for k in range(nb))}amix=inputs={nb}:normalize=0[nar];"
             f"[{nb + 1}:a]atrim={SCORE_FROM}:{SCORE_FROM + total:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.6,volume=0.9,"
             f"volume='{duck}':eval=frame,afade=t=out:st={total - 1.6:.2f}:d=1.6[bed];"
             f"[nar][bed]amix=inputs=2:normalize=0,apad[a]")
    if AUDIO:  # the approved mix as it was: picture graded here, audio stream copied untouched
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(pic), "-i", AUDIO, "-filter_complex", look,
                        "-map", "[v]", "-map", "1:a", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "21", "-preset", "slow",
                        "-tune", "grain", "-r", str(fps), "-c:a", "copy", "-movflags", "+faststart", str(final)], check=True)
        print(final, round(total, 2), "s")
        return
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(pic), *inputs, "-i", music,
                    "-filter_complex", f"{look};{audio}", "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-r", str(fps), "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                    "-movflags", "+faststart", str(final)], check=True)
    m = subprocess.run(["ffmpeg", "-nostdin", "-i", str(final), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(m.rsplit("I:", 1)[1].split("LUFS")[0])
    tmp = final.with_suffix(".tmp.mp4")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(final), "-c:v", "copy",
                    "-af", f"volume={-16 - lufs:.2f}dB,alimiter=limit=0.84:level=false", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(final)
    print(final, round(total, 1), "s")


if __name__ == "__main__":
    {"art": art, "voice": voice, "trim": lambda: trim(sorted((D / "voice").glob("*.mp3"))), "video": video}[sys.argv[1]]()
