"""Instagram Stories (no AI). Stories reach followers, not new people, so they carry what the Reels don't:

- Nightly card (config "story_time", default 20:30): tomorrow's saint, full-bleed icon, with the hook of tomorrow's
  episode when it is already approved (today's saint is already in the feed); else tonight's closing prayer on
  today's icon. Only after today's Reel is
  published; state ep["story"] {media_id, permalink, image | attempts, error}, max 3 attempts, failures to Telegram.
- Every card also goes to the Facebook Page as a Story once it is on Instagram (Instagram's "share to Facebook" skips
  API posts): state ep["story_fb"] / the entry's "facebook", {id | attempts, error}, independent of Instagram.
- Seasonal series (state/stories.json): prerendered cards on a GitHub release, each {"id", "at", "image" (or "video": Instagram only, unless "facebook_video": true),
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


SAFE_TEXT = H - 290         # v2: text block ends above the reply bar


def _shaded(art: Image.Image, dark_from: float):
    """The whole icon, full bleed (heads stay clear of Instagram's bar), sinking into soot under the text."""
    img = art.convert("RGB").resize((W, H), Image.LANCZOS)
    shade = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(shade)
    y0 = int(H * dark_from)
    for y in range(y0, H):
        d.line([(0, y), (W, y)], fill=min(235, int(235 * ((y - y0) / (H * 0.30)) ** 1.2)))
    for y in range(0, 200):  # keep Instagram's name and progress bar readable
        d.line([(0, y), (W, y)], fill=int(120 * (1 - y / 200)))
    img.paste(Image.new("RGB", (W, H), C["soot"]), (0, 0), shade)
    return img


def _text_layer(label, line, size, name=None, region=None):
    """Transparent 1080x1920 layer: small-caps label, the big italic line, then (tomorrow) the saint's name."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    big = _font("Cormorant-MediumItalic.ttf", size)
    lines = _lines(d, line, big, W - 2 * X)
    lh = int(size * 1.16)
    total = 66 + len(lines) * lh + (134 if name else 0) + (50 if region else 0)
    y = SAFE_TEXT - total
    _tracked(d, (X, y), label, _font("Cinzel-Regular.ttf", 38), C["gilt"], 0.14)
    y += 66
    for ln in lines:
        d.text((X, y), ln, font=big, fill=C["giltLight"])
        y += lh
    if name:
        y += 30
        d.rectangle([X, y, X + 90, y + 4], fill=C["martyr"])
        y += 30
        d.text((X, y), name, font=_font("EBGaramond-Medium.ttf", 60), fill=C["vellum"])
        y += 74
    if region:
        d.text((X, y), region, font=_font("Cormorant-MediumItalic.ttf", 44), fill=C["ash"])
    return lay


def _hook(ep):
    return next((b["text"] for b in ep["script"]["beats"] if b.get("role") == "hook"), "")


def night_card(ep, nxt=None, art=None, nxt_art=None):
    """Tonight's card: tomorrow's saint, full-bleed icon, with the hook of tomorrow's (approved) episode, so followers
    come back for the Reel (today's saint is already in their feed). Falls back to tonight's closing prayer on today's
    icon when tomorrow isn't approved yet."""
    if nxt and nxt_art is not None and _hook(nxt):
        hook = _hook(nxt)
        bg, txt = _shaded(nxt_art, 0.36), _text_layer("TOMORROW · " + _post_time(), hook, 88 if len(hook) < 80 else 76,
                                                      nxt["saint"]["display_name"], nxt["saint"].get("region", ""))
    else:
        close = next((b["text"] for b in ep["script"]["beats"] if b.get("role") == "close"),
                     f"{ep['saint']['name']}, pray for us.")
        bg, txt = _shaded(art, 0.42), _text_layer(_manuscript(ep["date"]), close, 92 if len(close) < 80 else 80)
    return Image.alpha_composite(bg.convert("RGBA"), txt).convert("RGB")


def _post_time():
    hh, mm = map(int, load_config().get("post_time", "07:30").split(":"))
    return f"{(hh - 1) % 12 + 1}:{mm:02d} {'AM' if hh < 12 else 'PM'}"


def _asset(ep, name="art.jpg"):
    """An episode's release image: the clean icon (art.jpg), else the Reel cover."""
    import storage
    a = ep.get("assets", {})
    url = a.get(name) or a.get("cover.jpg")
    r = http.get(storage.resolve_direct(url), timeout=60)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _tomorrow(ep):
    nid = (dt.date.fromisoformat(ep["id"]) + dt.timedelta(days=1)).isoformat()
    try:
        nxt = load_episode(nid)
    except Exception:
        return None
    return nxt if nxt and nxt.get("status") in ("approved", "publishing", "published") and nxt.get("assets") else None


def render_night(ep, out_dir: Path):
    """Tonight's card as story.jpg. Returns its path."""
    nxt = _tomorrow(ep)
    try:
        nxt_art = _asset(nxt) if nxt else None
    except Exception:
        traceback.print_exc()
        nxt_art = None
    jpg = out_dir / "story.jpg"
    night_card(ep, nxt, None if nxt_art is not None else _asset(ep), nxt_art).save(jpg, quality=92)
    return jpg


def post_night(ep):
    """Render, host on the episode's release, post as a Story."""
    import instagram, storage
    out = ROOT / "work" / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    url = storage.resolve_direct(storage.upload(f"ep-{ep['id']}", {"story.jpg": render_night(ep, out)})["story.jpg"])
    return {**instagram.publish_story(url), "image": url}


def _facebook(st, image_url, what, video_url=None):
    """Post a card that is already on Instagram to the Facebook Page as a Story (the video when there is one). `st` is
    its state dict ({id | attempts, error}), updated in place; returns True when it changed. Skips what's done, given
    up, or has nothing to post."""
    import facebook, telegram
    if not (image_url or video_url) or st.get("id") or st.get("attempts", 0) >= 3 or not facebook.configured():
        return False
    try:
        st.update(facebook.publish_video_story(video_url) if video_url else facebook.publish_story(image_url))
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
        # the weekly music Story has both: Facebook gets the animated video too (from 2026-11-16; before, the still card).
        # Video-only Stories (sung-prayer teasers) stay Instagram-only: Facebook gets their own post from shares.json.
        if s.get("status") == "posted" and s.get("video") and s.get("facebook_video") and not s.get("image"):
            # a video-only Story that should reach the Facebook Page too (the series teaser, 2026-11)
            fb = s.get("facebook") or {}
            if _facebook(fb, None, s["id"], storage.resolve_direct(s["video"])):
                s["facebook"] = fb
                changed = True
            continue
        if s.get("status") == "posted" and s.get("image"):
            fb = s.get("facebook") or {}
            video = storage.resolve_direct(s["video"]) if s.get("video") and s["at"][:10] >= "2026-11-16" else None
            if _facebook(fb, storage.resolve_direct(s["image"]), s["id"], video):
                s["facebook"] = fb
                changed = True
    from story_music import music_short
    changed = music_short(items, now) or changed
    if changed:
        save_json(FILE, items)


if __name__ == "__main__":
    if sys.argv[1] == "night":
        ep = load_episode(sys.argv[2])
        out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "work" / ep["id"] / "story.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(render_night(ep, out.parent))
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
