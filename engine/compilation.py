"""Monthly compilation: every Short published in a month, back to back, as one 16:9 YouTube video.

Each Short sits in the middle of the frame on its own icon (blurred, darkened); the left panel names the saint and
the feast, the right carries the monogram. A title card opens and an end card closes, both over Luis's music bed.
Chapters (one per saint) go in the description. No AI involved, so a render costs only runner minutes.

It uploads **private** and sends a Telegram message with a Publish button; nothing goes public until Luis taps it
(then: public + added to "Saints of <Month>"). State: state/compilations/YYYY-MM.json.
Schedule: .github/workflows/compilation.yml runs `pipeline.py compilation` on the last days of the month;
config "compilation_from" (YYYY-MM) is the first month made.
"""
import json, subprocess, datetime as dt
from pathlib import Path
from common import BRAND, ROOT, STATE, WORK, load_config, load_episodes, log, tz

W, H = 1920, 1080
VW = 608                      # the vertical Short scaled to full height (1080 × 9/16)
VX = (W - VW) // 2
PANEL = VX - 2 * 72           # text width of the left panel
CARD_S = 6                    # title / end card length
DIR = STATE / "compilations"
C = BRAND["colors"]
ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n):
    out = ""
    for v, r in ROMAN:
        while n >= v:
            out, n = out + r, n - v
    return out


def load(month):
    p = DIR / f"{month}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save(comp):
    DIR.mkdir(parents=True, exist_ok=True)
    comp["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (DIR / f"{comp['month']}.json").write_text(json.dumps(comp, indent=1, ensure_ascii=False) + "\n")


def month_name(month, lang="en"):
    from youtube import MESES
    m = int(month[5:7])
    return MESES[m - 1] if lang == "es" else dt.date(2000, m, 1).strftime("%B")


def episodes(month):
    """The month's published episodes, in feast order."""
    return [e for k, e in sorted(load_episodes().items())
            if k.startswith(month + "-") and e.get("status") == "published" and (e.get("assets") or {}).get("video.mp4")]


# ---------------- frames (Pillow, brand fonts; same vocabulary as playlist_cover.py) ----------------
def _art(ep, work):
    """The episode's icon: clean art.jpg when it has one, else the painted band of the video cover."""
    import storage
    from PIL import Image
    a = ep["assets"]
    clean = bool(a.get("art.jpg"))
    p = storage.download(a["art.jpg"] if clean else a["cover.jpg"], work / f"{ep['id']}-art.jpg")
    im = Image.open(p).convert("RGB")
    if not clean:
        w, h = im.size
        im = im.crop((0, int(h * 0.2), w, int(h * 0.64)))  # below the cover's monogram, above its name
    return im


def _backdrop(art):
    """The icon filling the frame, blurred and sunk into soot so the Short and the words stay in front."""
    from PIL import Image, ImageFilter
    w, h = art.size
    s = max(W / w, H / h)
    im = art.resize((int(w * s) + 1, int(h * s) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    im = im.filter(ImageFilter.GaussianBlur(28))
    return Image.blend(im, Image.new("RGB", (W, H), C["soot"]), 0.72)


def _monogram(d, x, y, size, fill):
    from playlist_cover import _font, _tracked
    f = _font("Cinzel-SemiBold.ttf", size)
    x += _tracked(d, (x, y), "A.S.", f, fill, tracking=0.04) + size * 0.15
    top, bottom = y + f.getbbox("A")[1] - size * 0.12, y + f.getbbox("A")[3] + size * 0.12
    stem, arm = max(2, size // 18), size * 0.45
    d.rectangle([x + (arm - stem) / 2, top, x + (arm + stem) / 2, bottom], fill=fill)  # Cinzel has no dagger
    bar = top + (bottom - top) * 0.3
    d.rectangle([x, bar, x + arm, bar + stem], fill=fill)


def _wrap(d, text, font, width, tracking=0.02):
    from playlist_cover import _width
    lines = []
    for word in text.split():
        if lines and _width(d, f"{lines[-1]} {word}", font, tracking) <= width:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def saint_frame(ep, art, out):
    from PIL import ImageDraw
    from playlist_cover import _font, _tracked
    s = ep["script"]["saint"]
    img = _backdrop(art)
    d = ImageDraw.Draw(img)
    x, y = 72, 300
    day = dt.date.fromisoformat(ep["id"])
    _tracked(d, (x, y), f"{roman(day.day)} · {day.strftime('%B').upper()}", _font("Cinzel-Regular.ttf", 30), C["ash"], 0.16)
    y += 80
    for size in (64, 56, 48, 42):
        f = _font("Cinzel-SemiBold.ttf", size)
        lines = _wrap(d, s["name"], f, PANEL)
        if len(lines) <= 4 or size == 42:
            break
    for l in lines:
        _tracked(d, (x, y), l, f, C["vellum"], 0.02)
        y += int(size * 1.12)
    y += 22
    it = _font("Cormorant-MediumItalic.ttf", 38)
    for l in [m for part in (s.get("dates"), s.get("region")) if part for m in _wrap(d, part, it, PANEL, 0)]:
        d.text((x, y), l, font=it, fill=C["giltLight"])
        y += 46
    d.rectangle([x, y + 24, x + 96, y + 27], fill=C["martyr"])
    _monogram(d, VX + VW + 72, 300, 44, C["giltLight"])
    d.text((VX + VW + 72, H - 120), "allholysaints.com", font=_font("EBGaramond-Medium.ttf", 30), fill=C["ash"])
    img.save(out, "PNG")
    return out


def title_frame(month, eps, art, out, end=False):
    from PIL import ImageDraw
    from playlist_cover import _font, _tracked, _width
    img = _backdrop(art)
    d = ImageDraw.Draw(img)

    def centred(text, font, y, fill, tracking):
        _tracked(d, ((W - _width(d, text, font, tracking)) / 2, y), text, font, fill, tracking)
    if end:
        _monogram(d, W / 2 - 110, 330, 96, C["giltLight"])
        centred(BRAND["tagline"].upper(), _font("Cinzel-SemiBold.ttf", 44), 520, C["vellum"], 0.08)
        it = _font("Cormorant-MediumItalic.ttf", 44)
        line = BRAND["youtube"].get("footer", "")
        d.text(((W - d.textlength(line, font=it)) / 2, 620), line, font=it, fill=C["giltLight"])
        site = _font("EBGaramond-Medium.ttf", 34)
        d.text(((W - d.textlength("allholysaints.com", font=site)) / 2, 720), "allholysaints.com", font=site, fill=C["ash"])
    else:
        _monogram(d, W / 2 - 70, 250, 60, C["giltLight"])
        centred("SAINTS OF", _font("Cinzel-SemiBold.ttf", 64), 400, C["gilt"], 0.12)
        centred(month_name(month).upper(), _font("Cinzel-SemiBold.ttf", 170), 490, C["vellum"], 0.06)
        d.rectangle([W / 2 - 60, 720, W / 2 + 60, 723], fill=C["martyr"])
        it = _font("Cormorant-MediumItalic.ttf", 48)
        line = f"{len(eps)} forgotten saints, one for each feast day of {month_name(month)} {month[:4]}"
        d.text(((W - d.textlength(line, font=it)) / 2, 760), line, font=it, fill=C["giltLight"])
    img.save(out, "PNG")
    return out


def thumbnail(month, arts, out):
    """1280×720: up to five icons side by side, soot rising from the bottom, the month in big Cinzel."""
    from PIL import Image, ImageDraw
    from playlist_cover import _font, _tracked, _width
    TW, TH = 1280, 720
    img = Image.new("RGB", (TW, TH), C["soot"])
    picks = arts[:: max(1, len(arts) // 5)][:5] or arts[:1]
    pw = TW // max(1, len(picks))
    for i, a in enumerate(picks):
        w, h = a.size
        s = max(pw / w, TH / h)
        im = a.resize((int(w * s) + 1, int(h * s) + 1), Image.LANCZOS)
        left = (im.width - pw) // 2
        img.paste(im.crop((left, 0, left + pw, TH)), (i * pw, 0))
        if i:
            ImageDraw.Draw(img).rectangle([i * pw - 2, 0, i * pw + 1, TH], fill=C["soot"])
    shade = Image.new("L", (TW, TH), 0)
    sd = ImageDraw.Draw(shade)
    for yy in range(240, TH):
        sd.line([(0, yy), (TW, yy)], fill=int(255 * min(1, (yy - 240) / 330) ** 1.6))
    img.paste(Image.new("RGB", (TW, TH), C["soot"]), (0, 0), shade)
    d = ImageDraw.Draw(img)
    big = month_name(month).upper()
    size = 150
    while _width(d, big, _font("Cinzel-SemiBold.ttf", size), 0.06) > TW - 120:
        size -= 4
    _tracked(d, (60, 470), "SAINTS OF", _font("Cinzel-SemiBold.ttf", 52), C["gilt"], 0.12)
    _tracked(d, (54, 530), big, _font("Cinzel-SemiBold.ttf", size), C["vellum"], 0.06)
    img.save(out, "JPEG", quality=90, optimize=True)
    return out


# ---------------- video (ffmpeg) ----------------
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout.strip())


def card_clip(png, out, start=0.0):
    """A still card over the music bed (from `start` s into it), faded in and out."""
    bed = ROOT / "assets" / "music" / "allsaints-2.mp3"
    f = f"afade=t=in:d=1,afade=t=out:st={CARD_S - 1.5}:d=1.5,volume=0.8"
    _ff("-loop", "1", "-t", str(CARD_S), "-i", str(png), "-ss", str(start), "-t", str(CARD_S), "-i", str(bed),
        "-filter_complex", f"[0:v]fade=t=in:d=0.6,fade=t=out:st={CARD_S - 0.6}:d=0.6[v];[1:a]{f}[a]",
        "-map", "[v]", "-map", "[a]", "-t", str(CARD_S), *ENC, str(out))
    return out


def saint_clip(png, video, out):
    _ff("-loop", "1", "-i", str(png), "-i", str(video),
        "-filter_complex", f"[1:v]scale={VW}:{H},setsar=1[s];[0:v][s]overlay={VX}:0:shortest=1[v]",
        "-map", "[v]", "-map", "1:a", *ENC, str(out))
    return out


def stamp(sec):
    sec = int(round(sec))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def render(month, eps, work):
    """Returns (video, thumbnail, chapters [(seconds, label)])."""
    import storage
    work.mkdir(parents=True, exist_ok=True)
    arts, clips, chapters, t = [], [], [], 0.0
    for ep in eps:
        log("Compilation:", ep["id"], ep["saint"]["display_name"])
        art = _art(ep, work)
        arts.append(art)
        vid = storage.download(ep["assets"]["video.mp4"], work / f"{ep['id']}-video.mp4")
        clips.append(saint_clip(saint_frame(ep, art, work / f"{ep['id']}-frame.png"), vid, work / f"{ep['id']}-clip.mp4"))
    intro = card_clip(title_frame(month, eps, arts[0], work / "title.png"), work / "title.mp4")
    end = card_clip(title_frame(month, eps, arts[-1], work / "end.png", end=True), work / "end.mp4", start=20)
    chapters.append((0, f"Saints of {month_name(month)}"))
    t = duration(intro)
    for ep, clip in zip(eps, clips):
        d = dt.date.fromisoformat(ep["id"])
        chapters.append((t, f"{ep['saint']['display_name']} ({d.strftime('%B')} {d.day})"))
        t += duration(clip)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in [intro, *clips, end]))
    out = work / f"saints-of-{month}.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out))
    return out, thumbnail(month, arts, work / "thumbnail.jpg"), chapters


# ---------------- YouTube text ----------------
def title(month, n):
    return f"Saints of {month_name(month)} {month[:4]}: {n} forgotten saints, one for each feast day"[:100]


def description(month, eps, chapters):
    from youtube import page_url
    yt = BRAND.get("youtube", {})
    support = load_config().get("support_url", "").strip()
    support = yt.get("support", "{url}").format(url=support) + "\n\n" if support else ""
    chap = "\n".join(f"{stamp(t)} {label}" for t, label in chapters)
    pages = "\n".join(f"• {e['saint']['display_name']}: {page_url(e)}" for e in eps)
    desc = f"""Every lesser-known saint we remembered in {month_name(month)} {month[:4]}, one after another: {len(eps)} short lives, each told on the saint's feast day. {BRAND['tagline']}

{chap}

Read each saint's full story, with sources:
{pages}

—
{yt.get('disclosure', '').replace('the sources above', 'the sources listed on each saint’s page')}

{support}{yt.get('footer', '')}

#CatholicSaints #SaintOfTheDay #AllHolySaints"""
    return desc.replace("<", "").replace(">", "")[:4900]


def localizations(month, eps, chapters):
    from youtube import page_url
    if not all(e.get("es") for e in eps):
        return None
    m = month_name(month, "es")
    chap = "\n".join(f"{stamp(t)} {e['es'].get('name') or e['saint']['display_name']}"
                     for (t, _), e in zip(chapters[1:], eps))
    pages = "\n".join(f"• {e['es'].get('name') or e['saint']['display_name']}: {page_url(e, 'es')}" for e in eps)
    tag = BRAND.get("site_es", {}).get("tagline", "")
    return {"es": {
        "title": f"Santos de {m} {month[:4]}: {len(eps)} santos olvidados, uno por cada fiesta"[:100],
        "description": f"""Los santos poco conocidos que recordamos en {m} de {month[:4]}, uno tras otro. {tag}

0:00 Santos de {m}
{chap}

La historia completa de cada santo, con fuentes:
{pages}""".replace("<", "").replace(">", "")[:4900]}}


# ---------------- the monthly job ----------------
def due_month(now=None):
    """The month to make today: the current one on its last day, or last month on the 1st–3rd if it isn't done yet."""
    now = now or dt.datetime.now(tz())
    d = now.date()
    if (d + dt.timedelta(days=1)).day == 1:
        return d.strftime("%Y-%m")
    if d.day <= 3:
        return (d.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    return None


def make(month=None, force=False, upload=True):
    """Render, upload private, send the Telegram Publish button. Safe to rerun: a month already uploaded is skipped."""
    import telegram, youtube
    cfg = load_config()
    month = month or due_month()
    if not month:
        log("Compilation: not the end of a month")
        return
    if not force and month < cfg.get("compilation_from", "9999"):
        log(f"Compilation: {month} is before compilation_from ({cfg.get('compilation_from')})")
        return
    comp = load(month) or {"month": month, "status": "new", "attempts": 0}
    if (comp.get("youtube") or {}).get("id") and not force:
        log("Compilation already uploaded:", comp["youtube"]["url"])
        return
    if comp["attempts"] >= 3 and not force:
        log("Compilation: 3 failed attempts; run it by hand")
        return
    eps = episodes(month)
    if len(eps) < 3:  # YouTube needs 3+ chapters, and a two-saint "month" isn't worth a video
        log(f"Compilation: only {len(eps)} published episodes in {month}")
        return
    if not upload:
        video, thumb, chapters = render(month, eps, WORK / f"compilation-{month}")
        print(video, thumb, *(f"{stamp(t)} {l}" for t, l in chapters), sep="\n")
        return
    comp.update(status="rendering", attempts=comp["attempts"] + 1, episodes=[e["id"] for e in eps])
    save(comp)
    try:
        video, thumb, chapters = render(month, eps, WORK / f"compilation-{month}")
        meta = {"snippet": {"title": title(month, len(eps)), "description": description(month, eps, chapters),
                            "tags": ["Catholic saints", "saint of the day", "lives of the saints", f"saints of {month_name(month)}",
                                     *[e["saint"]["name"] for e in eps]][:30],
                            "categoryId": youtube.CATEGORY_EDUCATION, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "embeddable": True}}
        if BRAND.get("youtube", {}).get("synthetic_media"):
            meta["status"]["containsSyntheticMedia"] = True
        if loc := localizations(month, eps, chapters):
            meta["localizations"] = loc
        res = youtube.upload_video(meta, video, thumbnail=thumb)
        url = f"https://youtu.be/{res['id']}"
        comp.update(status="review", youtube={"id": res["id"], "url": url, "privacy": "private"},
                    length=stamp(duration(video)), chapters=[[round(t), l] for t, l in chapters])
        comp.pop("error", None)
        save(comp)
        msg = telegram.send(f"🎞 Saints of {month_name(month)}: the month's {len(eps)} Shorts in one video ({comp['length']}), "
                            f"uploaded private.\nWatch it here (signed in to YouTube): {url}\nIt goes public only when you tap Publish.",
                            reply_markup=buttons(month))
        comp["review_message_id"] = (msg or {}).get("message_id")
        save(comp)
    except Exception as e:
        comp.update(status="failed", error=str(e)[:500])
        save(comp)
        telegram.send(f"❌ Saints of {month_name(month)} compilation failed ({comp['attempts']}x): {str(e)[:300]}"
                      + ("\nIt retries tomorrow." if comp["attempts"] < 3 and dt.date.today().day != 3 else ""))
        raise


def buttons(month):
    return {"inline_keyboard": [[{"text": "📣 Publish on YouTube", "callback_data": f"comppublish:{month}"}]]}


def publish(month):
    """Luis tapped Publish: make the video public and put it at the top of its month's playlist."""
    import youtube
    comp = load(month)
    vid = comp["youtube"]["id"]
    youtube.set_privacy(vid, "public")
    comp["youtube"]["privacy"] = "public"
    comp.update(status="published", published_at=dt.datetime.now(tz()).isoformat(timespec="minutes"))
    save(comp)
    try:
        youtube.add_video_to_playlist(f"Saints of {month_name(month)}", vid, position=0)
        comp["youtube"]["playlist"] = True
    except Exception as e:
        log("Compilation playlist skipped:", str(e)[:200])
    save(comp)
    return comp
