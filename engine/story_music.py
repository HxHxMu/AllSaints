"""Weekly music card for Instagram/Facebook Stories (config "music_story", default "Sun 15:00"; "" = off): an album from
data/music.json and one of its tracks, rotating week by week, skipped on solemnities and great Sundays. Queued in
state/stories.json for stories.run_seasonal to post. Run by stories.run_due (poll)."""
import datetime as dt, json, traceback
from PIL import Image, ImageDraw
from common import DATA, ROOT, load_config, load_json, log, save_json
from cards import font as _font, monogram as _monogram, roman, tracked as _tracked
from stories import C, FILE, SAFE_BOTTOM, TOP, W, H, X, _lines

MUSIC_FROM = dt.date(2026, 11, 1)  # week 0 of the rotation
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


def _music_pick(day):
    """(album, track number from 1) for the week of `day`: albums take turns, and each album's tracks take turns."""
    albums = json.loads((DATA / "music.json").read_text())
    n = (day - MUSIC_FROM).days // 7
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
    why = _music_skip(day) or next((f"another Story ({x['id']})" for x in items if not x["id"].startswith("music-")
                                    and x.get("status") != "skipped" and x["at"][:10] == day.isoformat()), None)
    if not s:
        s = {"id": sid, "at": now.isoformat(timespec="minutes")}
        items.append(s)
    if why:
        s.update(status="skipped", reason=why)
        log("Music Story skipped:", why)
    else:
        album, track = _music_pick(day)
        try:
            out = ROOT / "work" / "music-stories"
            out.mkdir(parents=True, exist_ok=True)
            jpg = out / f"{day}.jpg"
            music_card(album, track)[0].save(jpg, quality=92)
            url = storage.upload(f"stories-music-{day.year}", {jpg.name: jpg}, name=f"Stories: music {day.year}")[jpg.name]
            s.update(image=url, status="pending", album=album["title"], track=album["tracks"][track - 1])
            s.pop("error", None)
            log("Music Story queued:", album["title"], album["tracks"][track - 1])
        except Exception as e:
            traceback.print_exc()
            s.update(status="failed", attempts=s.get("attempts", 0) + 1, error=str(e)[:300])
            telegram.send(f"❌ Music Story failed ({s['attempts']}x): {str(e)[:200]}"
                          + ("\nWill retry." if s["attempts"] < 3 else ""))
    save_json(FILE, items)
