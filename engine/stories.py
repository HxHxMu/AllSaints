"""Instagram Stories (no AI). Stories reach followers, not new people, so they carry what the Reels don't:

- Nightly card (config "story_time", default 20:30): today's saint's icon and the episode's closing line
  ("Saint X, pray for us."), and tomorrow's saint when that episode is already approved. Only after today's Reel is
  published; state ep["story"] {media_id, permalink, image | attempts, error}, max 3 attempts, failures to Telegram.
- Every card also goes to the Facebook Page as a Story once it is on Instagram (Instagram's "share to Facebook" skips
  API posts): state ep["story_fb"] / the entry's "facebook", {id | attempts, error}, independent of Instagram.
- Seasonal series (state/stories.json): prerendered cards on a GitHub release, each {"id", "at", "image" (or "video": Instagram only),
  "status"}. "draft" entries wait for Luis's OK in chat (then "pending"); poll posts pending ones once due.
  The O Antiphons (Dec 17-23) are made by `stories.py o-antiphons` (o_antiphons.py, texts in data/o-antiphons.json).
- Weekly music card (story_music.py; config "music_story", default "Sun 15:00"; "" turns it off): an album from data/music.json and
  one of its tracks, rotating week by week (albums alternate once there is more than one). Skipped on solemnities and
  great Sundays (`_music_skip`) and on days another Story is scheduled. Lands in stories.json as "music-YYYY-MM-DD"
  (the posted-already guard), then posts and goes to Facebook like a seasonal card. The copy is approved as a template.

    python engine/stories.py night <ep_id> [out.jpg]     # render tonight's card locally (no posting)
    python engine/stories.py o-antiphons <year> [--upload] # render the seven cards (and queue them as drafts)
    python engine/stories.py music <YYYY-MM-DD> [out.jpg]  # render that week's music card locally (no posting)
"""
import datetime as dt, io, sys, traceback
from pathlib import Path
from PIL import Image, ImageDraw
from common import BRAND, ROOT, http, load_config, load_episode, load_json, log, save_episode, save_json, tz
from cards import font as _font, monogram as _monogram, roman, tracked as _tracked, wrap

W, H = 1080, 1920
X = 80                      # text margin
TOP = 170                   # Instagram's progress bar and name sit over the top ~150 px
SAFE_BOTTOM = H - 270       # Instagram's reply bar covers the bottom ~250 px
C = BRAND["colors"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
FILE = "stories.json"


def _lines(d, text, font, width, tracking=0.0):
    return wrap(d, text, font, width, tracking) or [""]


def _manuscript(iso):
    y, m, d = map(int, iso.split("-"))
    return f"{roman(d)} · {MONTHS[m]}".upper()


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
    from story_music import run_music
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
        from story_music import SAFE_BOTTOM, _music_pick, _music_skip, music_card
        album, track = _music_pick(day)
        img, end = music_card(album, track)
        img.save(out, quality=92)
        print(out, f"{album['title']} {roman(track)}. {album['tracks'][track - 1]}", "skip: " + str(_music_skip(day)),
              "text ends", end, "footer at", SAFE_BOTTOM - 96)
    elif sys.argv[1] == "o-antiphons":
        from o_antiphons import make_o_antiphons
        print(make_o_antiphons(sys.argv[2], upload="--upload" in sys.argv))
