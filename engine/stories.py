"""Instagram Stories (no AI). Stories reach followers, not new people, so they carry what the Reels don't:

- Nightly card (config "story_time", default 20:30): today's saint's icon and the episode's closing line
  ("Saint X, pray for us."), and tomorrow's saint when that episode is already approved. Only after today's Reel is
  published; state ep["story"] {media_id, permalink, image | attempts, error}, max 3 attempts, failures to Telegram.
- Every card also goes to the Facebook Page as a Story once it is on Instagram (Instagram's "share to Facebook" skips
  API posts): state ep["story_fb"] / the entry's "facebook", {id | attempts, error}, independent of Instagram.
- Seasonal series (state/stories.json): prerendered cards on a GitHub release, each {"id", "at", "image" (or "video": Instagram only),
  "status"}. "draft" entries wait for Luis's OK in chat (then "pending"); poll posts pending ones once due.
  The O Antiphons (Dec 17-23) are made by `stories.py o-antiphons`.
- Weekly music card (config "music_story", default "Sun 15:00"; "" turns it off): an album from data/music.json and
  one of its tracks, rotating week by week (albums alternate once there is more than one). Skipped on solemnities and
  great Sundays (`_music_skip`) and on days another Story is scheduled. Lands in stories.json as "music-YYYY-MM-DD"
  (the posted-already guard), then posts and goes to Facebook like a seasonal card. The copy is approved as a template.

    python engine/stories.py night <ep_id> [out.jpg]     # render tonight's card locally (no posting)
    python engine/stories.py o-antiphons <year> [--upload] # render the seven cards (and queue them as drafts)
    python engine/stories.py music <YYYY-MM-DD> [out.jpg]  # render that week's music card locally (no posting)
"""
import datetime as dt, io, json, sys, traceback
from pathlib import Path
from PIL import Image, ImageDraw
from common import BRAND, DATA, ROOT, http, load_config, load_episode, load_json, log, save_episode, save_json, tz
from playlist_cover import _font, _tracked, _width
from compilation import _monogram

W, H = 1080, 1920
X = 80                      # text margin
TOP = 170                   # Instagram's progress bar and name sit over the top ~150 px
SAFE_BOTTOM = H - 270       # Instagram's reply bar covers the bottom ~250 px
C = BRAND["colors"]
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX",
         "XXX", "XXXI"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
FILE = "stories.json"


def _lines(d, text, font, width, tracking=0.0):
    out = [""]
    for w in text.split():
        test = f"{out[-1]} {w}".strip()
        if not out[-1] or _width(d, test, font, tracking) <= width:
            out[-1] = test
        else:
            out.append(w)
    return out


def _manuscript(iso):
    y, m, d = map(int, iso.split("-"))
    return f"{ROMAN[d]} · {MONTHS[m]}".upper()


def _painted_band(cover: Image.Image):
    """The icon from a Reel cover: its painted band (17-64%), clear of the monogram and the title lettering."""
    w, h = cover.size
    return cover.crop((0, int(h * 0.17), w, int(h * 0.64))).resize((W, round(W * (h * 0.47) / w)), Image.LANCZOS)


def night_card(ep, nxt=None, cover: Image.Image = None):
    """Icon on top sinking into soot; the closing line; tomorrow's saint; the monogram. Long names shorten the icon
    (from the bottom of the painting) so the text never runs into the footer."""
    img, end = _night(ep, nxt, cover, 0)
    over = end + 60 - (SAFE_BOTTOM - 40)
    return _night(ep, nxt, cover, over)[0] if over > 0 else img


def _night(ep, nxt, cover, cut):
    img = Image.new("RGB", (W, H), C["soot"])
    band = _painted_band(cover)
    band = band.crop((0, 0, W, band.size[1] - cut))
    img.paste(band, (0, TOP))
    bh = TOP + band.size[1]
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    for y in range(TOP, TOP + 80):  # the painting rises out of the soot at the top...
        fd.line([(0, y), (W, y)], fill=int(255 * (1 - (y - TOP) / 80) ** 1.4))
    for y in range(bh - 260, bh + 1):  # ...and sinks back into it below
        fd.line([(0, y), (W, y)], fill=int(255 * ((y - bh + 260) / 260) ** 1.4))
    fd.rectangle([0, bh, W, H], fill=255)
    img.paste(Image.new("RGB", (W, H), C["soot"]), (0, 0), fade)
    d = ImageDraw.Draw(img)
    y = bh + 30
    _tracked(d, (X, y), _manuscript(ep["date"]), _font("Cinzel-Regular.ttf", 26), C["gilt"], 0.16)
    y += 70
    close = next((b["text"] for b in ep["script"]["beats"] if b.get("role") == "close"),
                 f"{ep['saint']['name']}, pray for us.")
    big = _font("Cormorant-MediumItalic.ttf", 76)
    for line in _lines(d, close, big, W - 2 * X):
        d.text((X, y), line, font=big, fill=C["giltLight"])
        y += 90
    y += 34
    d.rectangle([X, y, X + 72, y + 3], fill=C["martyr"])
    if nxt:
        y += 60
        _tracked(d, (X, y), "TOMORROW", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
        y += 48
        name = _font("EBGaramond-Medium.ttf", 50)
        for line in _lines(d, nxt["saint"]["display_name"], name, W - 2 * X):
            d.text((X, y), line, font=name, fill=C["vellum"])
            y += 62
        d.text((X, y + 4), nxt["saint"].get("region", ""), font=_font("Cormorant-MediumItalic.ttf", 36), fill=C["ash"])
        y += 48
    _monogram(d, X, SAFE_BOTTOM - 40, 30, C["gilt"])
    d.text((X + 110, SAFE_BOTTOM - 37), "allholysaints.com", font=_font("EBGaramond-Medium.ttf", 28), fill=C["ash"])
    return img, y


def _cover(ep):
    import storage
    r = http.get(storage.resolve_direct(ep["assets"]["cover.jpg"]), timeout=60)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _tomorrow(ep):
    nid = (dt.date.fromisoformat(ep["id"]) + dt.timedelta(days=1)).isoformat()
    try:
        nxt = load_episode(nid)
    except Exception:
        return None
    return nxt if nxt and nxt.get("status") in ("approved", "publishing", "published") else None


def post_night(ep):
    """Render, host on the episode's release, post as a Story."""
    import instagram, storage
    out = ROOT / "work" / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    jpg = out / "story.jpg"
    night_card(ep, _tomorrow(ep), _cover(ep)).save(jpg, quality=92)
    url = storage.resolve_direct(storage.upload(f"ep-{ep['id']}", {"story.jpg": jpg})["story.jpg"])
    return {**instagram.publish_story(url), "image": url}


def _facebook(st, image_url, what):
    """Post a card that is already on Instagram to the Facebook Page as a Story. `st` is its state dict ({id | attempts,
    error}), updated in place; returns True when it changed. Skips what's done, given up, or has no image."""
    import facebook, telegram
    if not image_url or st.get("id") or st.get("attempts", 0) >= 3 or not facebook.configured():
        return False
    try:
        st.update(facebook.publish_story(image_url))
        st.pop("error", None)
    except Exception as e:
        traceback.print_exc()
        st["attempts"] = st.get("attempts", 0) + 1
        st["error"] = str(e)[:300]
        try:
            telegram.send(f"❌ Facebook Story failed ({st['attempts']}x): {what}\n{str(e)[:200]}"
                          + ("\nWill retry." if st["attempts"] < 3 else ""))
        except Exception:
            traceback.print_exc()
    return True


def run_due(now=None):
    """From poll: tonight's card once today's Reel is out, then any due seasonal card."""
    import telegram
    now = now or dt.datetime.now(tz())
    hh, mm = map(int, load_config().get("story_time", "20:30").split(":"))
    if (now.hour, now.minute) >= (hh, mm):
        try:
            ep = load_episode(now.date().isoformat())
        except Exception:
            ep = None
        st = (ep or {}).get("story") or {}
        if ep and ep.get("status") == "published" and not st.get("media_id") and st.get("attempts", 0) < 3:
            try:
                ep["story"] = {**post_night(ep), "posted_at": now.isoformat(timespec="minutes")}
                log("Night Story:", ep["id"])
            except Exception as e:
                traceback.print_exc()
                st["attempts"] = st.get("attempts", 0) + 1
                st["error"] = str(e)[:300]
                ep["story"] = st
                telegram.send(f"❌ Night Story failed ({st['attempts']}x): {str(e)[:200]}"
                              + ("\nWill retry." if st["attempts"] < 3 else ""))
            save_episode(ep)
        if ep and ep.get("story", {}).get("media_id"):
            fb = ep.get("story_fb") or {}
            if _facebook(fb, ep["story"].get("image"), f"night card {ep['id']}"):
                ep["story_fb"] = fb
                save_episode(ep)
    run_music(now)
    run_seasonal(now)


def run_seasonal(now):
    import instagram, storage, telegram
    items = load_json(FILE, [])
    changed = False
    for s in items:
        if s.get("status") != "pending" or dt.datetime.fromisoformat(s["at"]) > now or s.get("attempts", 0) >= 3:
            continue
        try:
            media = {"video_url": storage.resolve_direct(s["video"])} if s.get("video") else {"image_url": storage.resolve_direct(s["image"])}
            s.update(status="posted", posted=instagram.publish_story(**media),
                     posted_at=now.isoformat(timespec="minutes"))
        except Exception as e:
            s["attempts"] = s.get("attempts", 0) + 1
            s["error"] = str(e)[:300]
            telegram.send(f"❌ Story failed ({s['attempts']}x): {s['id']}\n{str(e)[:200]}")
        changed = True
    for s in items:
        if s.get("status") == "posted" and s.get("image"):  # video Stories are Instagram-only
            fb = s.get("facebook") or {}
            if _facebook(fb, storage.resolve_direct(s["image"]), s["id"]):
                s["facebook"] = fb
                changed = True
    if changed:
        save_json(FILE, items)


# ---------------- Weekly music card ----------------
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
    _tracked(d, (X, y), f"THIS WEEK  ·  {ROMAN[track]}", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
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


# ---------------- O Antiphons (Dec 17-23) ----------------
# Latin: the Magnificat antiphons of the Roman Office. English: All Saints' own literal translation (the ICEL text is
# under copyright).
O_ANTIPHONS = [
    ("O Sapientia",
     "O Sapientia, quae ex ore Altissimi prodiisti, attingens a fine usque ad finem, fortiter suaviterque disponens "
     "omnia: veni ad docendum nos viam prudentiae.",
     "O Wisdom, who came forth from the mouth of the Most High, reaching from end to end and ordering all things "
     "mightily and sweetly: come, and teach us the way of prudence."),
    ("O Adonai",
     "O Adonai, et Dux domus Israel, qui Moysi in igne flammae rubi apparuisti, et ei in Sina legem dedisti: veni ad "
     "redimendum nos in brachio extento.",
     "O Adonai, and leader of the house of Israel, who appeared to Moses in the flame of the burning bush and gave "
     "him the law on Sinai: come, and redeem us with outstretched arm."),
    ("O Radix Iesse",
     "O Radix Iesse, qui stas in signum populorum, super quem continebunt reges os suum, quem gentes deprecabuntur: "
     "veni ad liberandum nos, iam noli tardare.",
     "O Root of Jesse, who stand as a sign for the peoples, before whom kings shall keep silence, whom the nations "
     "shall implore: come and set us free, delay no longer."),
    ("O Clavis David",
     "O Clavis David, et sceptrum domus Israel, qui aperis, et nemo claudit, claudis, et nemo aperit: veni, et educ "
     "vinctum de domo carceris, sedentem in tenebris et umbra mortis.",
     "O Key of David, and sceptre of the house of Israel, who open and no one shuts, who shut and no one opens: come, "
     "and lead the prisoner out of the prison house, who sits in darkness and the shadow of death."),
    ("O Oriens",
     "O Oriens, splendor lucis aeternae, et sol iustitiae: veni, et illumina sedentes in tenebris et umbra mortis.",
     "O Dayspring, splendour of eternal light and sun of justice: come, and give light to those who sit in darkness "
     "and the shadow of death."),
    ("O Rex Gentium",
     "O Rex Gentium, et desideratus earum, lapisque angularis, qui facis utraque unum: veni, et salva hominem, quem de "
     "limo formasti.",
     "O King of the nations, and their desire, the cornerstone who makes the two one: come, and save man, whom you "
     "formed from the clay."),
    ("O Emmanuel",
     "O Emmanuel, Rex et legifer noster, exspectatio gentium, et Salvator earum: veni ad salvandum nos, Domine, Deus "
     "noster.",
     "O Emmanuel, our King and lawgiver, the hope of the nations and their Saviour: come and save us, O Lord our God."),
]


def antiphon_card(i, title, latin, english, day):
    """Typeset on soot, no picture: the antiphon is the image."""
    img = Image.new("RGB", (W, H), C["soot"])
    d = ImageDraw.Draw(img)
    big, lat, en = _font("Cinzel-SemiBold.ttf", 84), _font("EBGaramond-Medium.ttf", 46), _font("Cormorant-MediumItalic.ttf", 44)
    tl, ll, el = (_lines(d, title.upper(), big, W - 2 * X, 0.04), _lines(d, latin, lat, W - 2 * X),
                  _lines(d, english, en, W - 2 * X))
    block = 46 + 80 + 104 * len(tl) + 16 + 46 + 60 * len(ll) + 36 + 54 * len(el)
    y = max(TOP + 60, (TOP + SAFE_BOTTOM - 120 - block) // 2)  # centred between the top bar and the footnote
    _tracked(d, (X, y), f"THE O ANTIPHONS  ·  {ROMAN[i + 1]} OF VII", _font("Cinzel-Regular.ttf", 24), C["gilt"], 0.16)
    y += 46
    _tracked(d, (X, y), f"{ROMAN[day]} · DECEMBER", _font("Cinzel-Regular.ttf", 24), C["ash"], 0.16)
    y += 80
    for line in tl:
        _tracked(d, (X - 3, y), line, big, C["vellum"], 0.04)
        y += 104
    y += 16
    d.rectangle([X, y, X + 72, y + 3], fill=C["martyr"])
    y += 46
    for line in ll:
        d.text((X, y), line, font=lat, fill=C["vellum"])
        y += 60
    y += 36
    for line in el:
        d.text((X, y), line, font=en, fill=C["giltLight"])
        y += 54
    d.text((X, SAFE_BOTTOM - 96), "Sung at Vespers in the last days of Advent, since the early Middle Ages.",
           font=_font("Cormorant-MediumItalic.ttf", 30), fill=C["ash"])
    _monogram(d, X, SAFE_BOTTOM - 40, 30, C["gilt"])
    return img


def make_o_antiphons(year, upload=False, at="12:30"):
    out = ROOT / "work" / f"o-antiphons-{year}"
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for i, (title, latin, english) in enumerate(O_ANTIPHONS):
        p = out / f"{17 + i}-{title.split()[1].lower()}.jpg"
        antiphon_card(i, title, latin, english, 17 + i).save(p, quality=92)
        files[p.name] = p
    if upload:
        import storage
        urls = storage.upload(f"stories-o-antiphons-{year}", files, name=f"Stories: the O Antiphons {year}")
        items = [s for s in load_json(FILE, []) if not s["id"].startswith(f"o-antiphons-{year}-")]
        offset = dt.datetime(int(year), 12, 17, tzinfo=tz()).strftime("%z")
        for i, name in enumerate(files):
            items.append({"id": f"o-antiphons-{year}-{17 + i}", "at": f"{year}-12-{17 + i}T{at}:00{offset[:3]}:{offset[3:]}",
                          "image": urls[name], "status": "draft"})
        save_json(FILE, items)
    return out


if __name__ == "__main__":
    if sys.argv[1] == "night":
        ep = load_episode(sys.argv[2])
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "work" / ep["id"] / "story.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        night_card(ep, _tomorrow(ep), _cover(ep)).save(out, quality=92)
        print(out)
    elif sys.argv[1] == "music":
        day = dt.date.fromisoformat(sys.argv[2])
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "work" / "music-stories" / f"{day}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        album, track = _music_pick(day)
        img, end = music_card(album, track)
        img.save(out, quality=92)
        print(out, f"{album['title']} {ROMAN[track]}. {album['tracks'][track - 1]}", "skip: " + str(_music_skip(day)),
              "text ends", end, "footer at", SAFE_BOTTOM - 96)
    elif sys.argv[1] == "o-antiphons":
        print(make_o_antiphons(sys.argv[2], upload="--upload" in sys.argv))
