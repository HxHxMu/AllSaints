"""Weekly music card for Instagram/Facebook Stories (config "music_story", default "Sun 15:00"; "" = off): an album from
data/music.json and one of its tracks, one track a Sunday, skipped on solemnities, great Sundays and any Sunday that already has another post (a sung-prayer
release, a seasonal Story); a skipped Sunday holds the track for the next week. Queued in state/stories.json for
stories.run_seasonal to post: Instagram plays the animated art (music_story_video.py), Facebook gets the same video
from 2026-11-16, and music_short puts it on YouTube as a Short (texts: data/music.json "short"). Run by
stories.run_due (poll)."""
import datetime as dt, json, traceback
from PIL import Image, ImageDraw
from common import DATA, ROOT, load_config, load_json, log, save_json
from cards import font as _font, monogram as _monogram, roman, tracked as _tracked
from stories import C, FILE, SAFE_BOTTOM, TOP, W, H, X, _lines

MUSIC_FROM = dt.date(2026, 11, 1)  # week 0 of the rotation
PIVOT = dt.date(2026, 11, 15)       # last Sunday of the old by-the-calendar count (track III); strict cadence after it
# Fixed solemnities (and All Souls) that can fall on a Sunday; Dec 17-Jan 1 is the O Antiphons and the Christmas octave.
SOLEMNITIES = {"01-06", "03-19", "03-25", "06-24", "06-29", "08-15", "11-01", "11-02", "12-08"}


def _easter(y):
    """Gregorian computus (Meeus/Jones/Butcher)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e, f = b // 4, b % 4, (b + 8) // 25
    h = (19 * a + b - d - (b - f + 1) // 3 + 15) % 30
    l = (32 + 2 * e + 2 * (c // 4) - h - c % 4) % 7
    m = (a + 11 * h + 22 * l) // 451
    return dt.date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def _music_skip(day):
    """Why the music card stands aside on this date (None = post). US calendar: Epiphany, Ascension and Corpus Christi
    on Sundays."""
    md = day.strftime("%m-%d")
    if md in SOLEMNITIES:
        return "solemnity"
    if md >= "12-17" or md == "01-01":
        return "O Antiphons / Christmas octave"
    if day.month == 1 and 2 <= day.day <= 8 and day.weekday() == 6:
        return "Epiphany"
    if day.month == 11 and 20 <= day.day <= 26 and day.weekday() == 6:
        return "Christ the King"
    great = {-7: "Palm Sunday", 0: "Easter", 7: "Divine Mercy Sunday", 42: "Ascension", 49: "Pentecost",
             56: "Trinity Sunday", 63: "Corpus Christi"}
    return great.get((day - _easter(day.year)).days)


def _other_post(day, stories=None):
    """Another queued Story or post (a sung-prayer release, a seasonal card) on `day`: it takes the Sunday (Luis, 2026-11-15)."""
    d = day.isoformat()
    for f, items in (("stories.json", stories), ("shares.json", None)):
        for x in (load_json(f, []) if items is None else items):
            if not x["id"].startswith("music-") and x.get("status") != "skipped" and x["at"][:10] == d:
                return x["id"]
    return None


def _why_not(day, stories=None):
    why = _music_skip(day)
    if not why and (other := _other_post(day, stories)):
        why = f"another post ({other})"
    return why


def _week(day, stories=None):
    """Weeks into the rotation. From 2026-11-15 a strict cadence: a skipped Sunday holds the next track for the week
    after, so every track gets its turn (before that, a skipped week also skipped its track)."""
    if day <= PIVOT:
        return (day - MUSIC_FROM).days // 7
    s = PIVOT + dt.timedelta(days=7)
    items = load_json(FILE, []) if stories is None else stories
    # a Sunday counts if it was free, or if its music card went out anyway (Christ the King 2026, posted late by hand)
    sent = {x["id"] for x in items if x["id"].startswith("music-") and x.get("status") in ("pending", "posted")}
    return (PIVOT - MUSIC_FROM).days // 7 + sum(1 for k in range((day - s).days // 7)
                                                if f"music-{s + dt.timedelta(days=7 * k)}" in sent
                                                or not _why_not(s + dt.timedelta(days=7 * k), stories)) + 1


def _music_pick(day, stories=None):
    """(album, track number from 1) for the week of `day`: albums take turns, and each album's tracks take turns."""
    albums = json.loads((DATA / "music.json").read_text())
    n = _week(day, stories)
    album = albums[n % len(albums)]
    return album, (n // len(albums)) % len(album["tracks"]) + 1


def music_card(album, track):
    """The album cover as a sleeve, the line under it, this week's track, where to listen, the credit."""
    img = Image.new("RGB", (W, H), C["soot"])
    side = W - 2 * X
    img.paste(Image.open(ROOT / album["cover"]).convert("RGB").resize((side, side), Image.LANCZOS), (X, TOP + 10))
    d = ImageDraw.Draw(img)
    y = TOP + 10 + side + 50
    _tracked(d, (X, y), "THE MUSIC OF ALL SAINTS", _font("Cinzel-Regular.ttf", 26), C["gilt"], 0.16)
    y += 62
    big = _font("Cormorant-MediumItalic.ttf", 58)
    for line in _lines(d, album["line"], big, side):
        d.text((X, y), line, font=big, fill=C["giltLight"])
        y += 68
    y += 8
    small = _font("Cormorant-MediumItalic.ttf", 34)
    for line in _lines(d, album["about"], small, side):
        d.text((X, y), line, font=small, fill=C["ash"])
        y += 42
    y += 26
    d.rectangle([X, y, X + 72, y + 3], fill=C["martyr"])
    y += 40
    _tracked(d, (X, y), f"THIS WEEK  ·  {roman(track)}", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
    y += 44
    d.text((X, y), album["tracks"][track - 1], font=_font("EBGaramond-Medium.ttf", 50), fill=C["vellum"])
    d.text((X, SAFE_BOTTOM - 96), f"Listen at {album['url']}", font=_font("EBGaramond-Medium.ttf", 32), fill=C["vellum"])
    _monogram(d, X, SAFE_BOTTOM - 40, 30, C["gilt"])
    d.text((X + 110, SAFE_BOTTOM - 37), "Music by Luis E. Bonilla · made with AI tools", font=_font("EBGaramond-Medium.ttf", 28),
           fill=C["ash"])
    return img, y + 62


def run_music(now):
    """Once a week at config "music_story": render, host, and queue this week's music card for run_seasonal."""
    import storage, telegram
    when = load_config().get("music_story", "Sun 15:00")
    if not when:
        return
    wday, hm = when.split()
    if now.strftime("%a") != wday or (now.hour, now.minute) < tuple(map(int, hm.split(":"))):
        return
    day = now.date()
    sid = f"music-{day}"
    items = load_json(FILE, [])
    s = next((x for x in items if x["id"] == sid), None)
    if s and (s.get("image") or s.get("status") == "skipped" or s.get("attempts", 0) >= 3):
        return
    why = _why_not(day, items)
    if not s:
        s = {"id": sid, "at": now.isoformat(timespec="minutes")}
        items.append(s)
    if why:
        s.update(status="skipped", reason=why)
        log("Music Story skipped:", why)
    else:
        album, track = _music_pick(day, items)
        try:
            out = ROOT / "work" / "music-stories"
            out.mkdir(parents=True, exist_ok=True)
            jpg = out / f"{day}.jpg"
            music_card(album, track)[0].save(jpg, quality=92)
            url = storage.upload(f"stories-music-{day.year}", {jpg.name: jpg}, name=f"Stories: music {day.year}")[jpg.name]
            s.update(image=url, status="pending", album=album["title"], track=album["tracks"][track - 1])
            if album.get("story_video"):  # Instagram plays the animated art with the track (music_story_video.py);
                s["video"] = album["story_video"].format(n=track)  # Facebook keeps the still card (image-only there)
            s.pop("error", None)
            log("Music Story queued:", album["title"], album["tracks"][track - 1])
        except Exception as e:
            traceback.print_exc()
            s.update(status="failed", attempts=s.get("attempts", 0) + 1, error=str(e)[:300])
            telegram.send(f"❌ Music Story failed ({s['attempts']}x): {str(e)[:200]}"
                          + ("\nWill retry." if s["attempts"] < 3 else ""))
    save_json(FILE, items)


SHORTS_FROM = "2026-11-15"   # the weekly music Story also goes up as a YouTube Short from this Sunday


def short_meta(album, n):
    """YouTube title/description/tags for track n's Short, from data/music.json "short" (texts Luis approved)."""
    sh, k, track = album["short"], str(n), album["tracks"][n - 1]
    desc = (f"{sh['lines'].get(k, sh['line'])} Track {roman(n)} of {album['title']}, {album['volume']}.\n\n"
            f"▶ The full hour: {sh['full_hour']}\n🎧 {album['title']} on the web: https://{album['url']}/\n\n"
            f"{sh['credits'].get(k, sh['credit'])}\n\nSubscribe for a forgotten saint every morning, and pray with us.\n\n"
            f"{sh['hashtags']}")
    return {"title": sh["titles"].get(k, sh["title"].format(track=track))[:100], "description": desc,
            "tags": [track] + sh["tags"]}


def music_short(items, now):
    """From run_seasonal: once this week's music Story is on Instagram, the same video goes up as a YouTube Short.
    Recorded on the entry ("youtube": {id, url} | attempts, error) the moment YouTube takes it. Returns True if changed."""
    import tempfile, telegram, youtube
    from pathlib import Path
    from common import BRAND, http
    from storage import resolve_direct
    changed = False
    for s in items:
        yt = s.get("youtube") or {}
        if (not s["id"].startswith("music-") or s.get("status") != "posted" or not s.get("video")
                or s["at"][:10] < SHORTS_FROM or yt.get("id") or yt.get("attempts", 0) >= 3 or not youtube.configured()):
            continue
        album = next((a for a in json.loads((DATA / "music.json").read_text()) if a["title"] == s.get("album")), None)
        if not album or not album.get("short") or s.get("track") not in album["tracks"]:
            continue
        n = album["tracks"].index(s["track"]) + 1
        m = short_meta(album, n)
        meta = {"snippet": {**m, "categoryId": "10", "defaultLanguage": "en"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True}}
        if BRAND.get("youtube", {}).get("synthetic_media"):
            meta["status"]["containsSyntheticMedia"] = True
        try:
            src = album["short_video"].format(n=n) if album.get("short_video") else s["video"]  # words clear of Shorts' UI
            r = http.get(resolve_direct(src), timeout=300)
            r.raise_for_status()
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "short.mp4"
                path.write_bytes(r.content)
                vid = youtube.upload_video(meta, path, "snippet,status")
            s["youtube"] = {"id": vid["id"], "url": f"https://youtube.com/shorts/{vid['id']}"}
            log("Music Short:", s["youtube"]["url"])
            try:
                telegram.send(f"▶️ Music Short up: {m['title']}\n{s['youtube']['url']}")
            except Exception:
                traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
            s["youtube"] = {"attempts": yt.get("attempts", 0) + 1, "error": str(e)[:300]}
            try:
                telegram.send(f"❌ Music Short failed ({s['youtube']['attempts']}x): {s['track']}\n{str(e)[:200]}")
            except Exception:
                traceback.print_exc()
        changed = True
    return changed
