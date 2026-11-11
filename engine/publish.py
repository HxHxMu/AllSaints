"""Posting. The daily Reel first (publish_episode), then each other platform once (Facebook, Threads, YouTube, TikTok),
plus one-off carousels. Invariant: record a post the moment the platform accepts it, before any note or extra, so a
retry can never post it twice (engine/CLAUDE.md → Reliability rules)."""
import datetime as dt, json, re, traceback
from common import BRAND, STATE, WORK, assign_slugs, log, load_config, load_json, save_json, load_episode, save_episode, tz


def publish_due():
    import telegram
    cfg = load_config()
    now = dt.datetime.now(tz())
    if cfg.get("paused") or not cfg.get("launch_date") or now.date() < dt.date.fromisoformat(cfg["launch_date"]):
        return
    hh, mm = map(int, cfg["post_time"].split(":"))
    due_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    ep = load_episode(now.date().isoformat())
    if not ep:
        return
    if ep["status"] == "review" and now >= due_time - dt.timedelta(hours=2) and not ep.get("reminded"):
        telegram.send(f"⏰ Today's episode ({ep['saint']['display_name']}) still needs approval – it posts at {cfg['post_time']}.")
        ep["reminded"] = True
        save_episode(ep)
    if ep["status"] == "publishing":
        # a job killed mid-upload leaves "publishing" behind; after 30 min treat it as a failed attempt
        started = dt.datetime.fromisoformat(ep.get("updated", now.isoformat()))
        if now - started > dt.timedelta(minutes=30):
            ep["status"] = "approved"
    if ep["status"] == "published":
        publish_youtube(ep)  # retries a Short that failed after the Reel went out
        youtube_playlists(ep)
        publish_facebook(ep)
        publish_threads(ep)
        publish_tiktok(ep)
        pinterest_boards(ep)
        return
    if ep["status"] != "approved" or now < due_time:
        return
    try:
        publish_episode(ep)
    except Exception:
        pass  # logged + reported to Telegram; retried on the next poll


def publish_episode(ep):
    """Post one episode's Reel now, then its YouTube Short (used by the daily schedule and `pipeline.py publish <id>`)."""
    import instagram, locations, storage, telegram
    now = dt.datetime.now(tz())
    log("Publishing", ep["id"])
    assign_slugs(ep)  # the web page's address is fixed from here on
    ep["status"] = "publishing"
    save_episode(ep)
    try:
        vid = WORK / f"{ep['id']}-video.mp4"
        storage.download(ep["assets"]["video.mp4"], vid)
        video_url = storage.resolve_direct(ep["assets"]["video.mp4"])
        cover_url = storage.resolve_direct(ep["assets"]["cover.jpg"])
        try:
            res = instagram.find_reel(ep["caption"])
        except Exception as e:  # can't ask: post anyway, since a missed day is worse than a rare double
            log("Instagram check for an earlier post failed:", str(e)[:200])
            res = None
        if res:
            log("Already on Instagram (earlier attempt), recording it:", res["media_id"])
        else:
            loc = locations.for_episode(ep)
            res = instagram.publish_reel(ep["caption"], video_url=video_url, cover_url=cover_url, video_path=vid,
                                         location_id=loc and loc["id"])
            if loc:
                res["location"] = loc["name"] if res.get("location_id") else f"{loc['name']} (rejected, posted untagged)"
    except Exception as e:
        traceback.print_exc()
        publish_youtube(ep)  # a Reel failure shouldn't hold the Short back
        ep["status"] = "approved"
        ep["publish_error"] = str(e)[:500]
        ep["publish_attempts"] = ep.get("publish_attempts", 0) + 1
        save_episode(ep)
        if ep["publish_attempts"] in (1, 3):
            telegram.send(f"❌ Publishing failed ({ep['publish_attempts']}x): {str(e)[:300]}\nWill retry.")
        raise
    # the Reel is live: record it before anything else can fail (a retry from "approved" would post it twice)
    ep.update(status="published", published=res, published_at=now.isoformat(timespec="minutes"))
    save_episode(ep)
    _notify(f"📣 Posted: {ep['saint']['display_name']}\n{res.get('permalink') or ''}"
            + (f"\n📍 {res['location']}" if res.get("location") else ""))
    publish_facebook(ep, vid)
    publish_threads(ep)
    publish_youtube(ep, vid)
    publish_tiktok(ep, vid)


def _notify(text):
    """Telegram note after a post has succeeded: a failure here must not mark the post failed (a retry would double-post)."""
    import telegram
    try:
        telegram.send(text)
    except Exception:
        traceback.print_exc()


def publish_once(ep, key, label, post, ready=lambda ep: ep.get("status") == "published", done="id", stamp="published_at"):
    """Post ep to one platform at most once: post() is called only while ep[key] has no `done` field, fewer than 3
    attempts and ready(ep). Returns the platform's result once recorded (ep[key] saved BEFORE the caller's Telegram
    note, so a failure after this point can never post it again), else None. A failure counts an attempt, stores the
    error and tells Telegram on the 1st and 3rd; it never touches ep["status"]."""
    import telegram
    rec = ep.get(key) or {}
    if rec.get(done) or rec.get("attempts", 0) >= 3 or not ready(ep):
        return None
    try:
        res = post()
    except Exception as e:
        traceback.print_exc()
        rec["attempts"] = rec.get("attempts", 0) + 1
        rec["error"] = str(e)[:500]
        ep[key] = rec
        save_episode(ep)
        if rec["attempts"] in (1, 3):
            telegram.send(f"❌ {label} failed ({rec['attempts']}x): {str(e)[:300]}" + ("\nWill retry." if rec["attempts"] < 3 else ""))
        return None
    # accepted: record it first, so nothing after this can post it again
    ep[key] = {**res, stamp: dt.datetime.now(tz()).isoformat(timespec="minutes")}
    save_episode(ep)
    return res


def publish_facebook(ep, video=None):
    """Post the Reel to the Facebook Page once, after it's on Instagram; independent, max 3 attempts."""
    import facebook, storage
    if not facebook.configured():
        return
    res = publish_once(ep, "facebook", "Facebook post", lambda: facebook.publish_reel(
        ep["caption"], video_url=storage.resolve_direct(ep["assets"]["video.mp4"]), video_path=video,
        cover_url=storage.resolve_direct(ep["assets"]["cover.jpg"]) if ep["assets"].get("cover.jpg") else None))
    if res:
        _notify(f"📘 On Facebook: {ep['saint']['display_name']}\n{res['url']}")


def publish_threads(ep):
    """Post the video to Threads once, after it's on Instagram; independent, max 3 attempts."""
    import threads, storage, yt_meta
    if not threads.configured():
        return
    res = publish_once(ep, "threads", "Threads post", lambda: threads.publish_video(
        threads.build_text(ep, yt_meta.page_url(ep)), storage.resolve_direct(ep["assets"]["video.mp4"])))
    if res:
        _notify(f"🧵 On Threads: {ep['saint']['display_name']}\n{res['url']}")


def publish_tiktok(ep, video=None):
    """Send the video to the TikTok inbox as a draft once, after it's on Instagram (TikTok won't let our app post publicly),
    then Telegram the caption for Luis to paste when he posts it. Independent, max 3 attempts."""
    import tiktok, storage
    if not tiktok.configured():
        return
    res = publish_once(ep, "tiktok", "TikTok draft", lambda: tiktok.upload_draft(
        video or storage.download(ep["assets"]["video.mp4"], WORK / f"{ep['id']}-video.mp4")), done="publish_id", stamp="sent_at")
    if res:
        _notify(f"🎵 TikTok draft ready: {ep['saint']['display_name']}\nTap TikTok's notification, paste the caption below, "
                "tap Edit cover and pick a frame with the saint, turn on \"AI-generated content\" (More options) and post.")
        _notify(ep["caption"])


def publish_youtube(ep, video=None):
    """Upload the episode as a YouTube Short once; independent of Instagram (needs only the uploaded assets), max 3 attempts."""
    import youtube, storage
    if not youtube.configured():
        return
    res = publish_once(ep, "youtube", "YouTube upload", lambda: youtube.upload_short(
        ep, video or storage.download(ep["assets"]["video.mp4"], WORK / f"{ep['id']}-video.mp4")), ready=lambda ep: bool(ep.get("assets")))
    if not res:
        return
    note = "" if res["privacy"] == "public" else f" ({res['privacy']}: publish it in YouTube Studio)"
    _notify(f"▶️ On YouTube{note}: {ep['saint']['display_name']}\n{res['url']}")
    try:
        youtube_cover(ep)
    except Exception:
        traceback.print_exc()
    try:
        youtube_playlists(ep)
    except Exception:
        traceback.print_exc()


def youtube_cover(ep):
    """The episode's cover.jpg as the Short's thumbnail (YouTube otherwise picks a frame). Raises; callers log."""
    import youtube, storage
    from common import http
    yt = ep.get("youtube") or {}
    if not yt.get("id") or yt.get("cover") or "cover.jpg" not in (ep.get("assets") or {}):
        return
    r = http.get(storage.resolve_direct(ep["assets"]["cover.jpg"]), timeout=60)
    r.raise_for_status()
    youtube.set_thumbnail(yt["id"], r.content)
    yt["cover"] = True
    ep["youtube"] = yt
    save_episode(ep)


def youtube_playlists(ep):
    """Put a published Short in its month + continent playlists; max 3 attempts, never blocks anything else."""
    import youtube, yt_playlists, telegram
    yt = ep.get("youtube") or {}
    if not youtube.configured() or not yt.get("id") or yt.get("playlists_done") or yt.get("playlist_attempts", 0) >= 3:
        return
    try:
        yt["playlists"] = yt.get("playlists", []) + yt_playlists.add_to_playlists(ep, done=yt.get("playlists", []))
        yt["playlists_done"] = True
        yt.pop("playlist_error", None)
        log("Playlists:", ", ".join(yt["playlists"]))
    except Exception as e:
        traceback.print_exc()
        yt["playlist_attempts"] = yt.get("playlist_attempts", 0) + 1
        yt["playlist_error"] = str(e)[:300]
        if yt["playlist_attempts"] == 1:
            hint = "\nRerun `pipeline.py yt-auth` once (playlists need a new permission)." if "403" in str(e) else ""
            try:
                telegram.send(f"⚠️ Couldn't add {ep['saint']['display_name']} to playlists: {str(e)[:200]}{hint}")
            except Exception:
                traceback.print_exc()
    ep["youtube"] = yt
    save_episode(ep)


def pinterest_boards(ep):
    """Pinterest won't take an empty RSS feed, so each board's feed (site: /pin/<board>.xml) is connected by hand the day
    its first saint publishes: Telegram tells Luis which. Boards already announced/connected: state/pinterest.json."""
    import telegram
    st = load_json("pinterest.json", {"announced": []})
    month = dt.date.fromisoformat(ep["date"]).strftime("%B")
    names = [month] + ([ep["continent"]] if ep.get("continent") else [])
    new = [n for n in names if re.sub(r"\s+", "-", re.sub(r"^the ", "", n.lower())) not in st["announced"]]
    for n in new:
        slug = re.sub(r"\s+", "-", re.sub(r"^the ", "", n.lower()))
        title = BRAND["youtube"]["playlists"]["region" if n != month else "month"].replace("{name}", n)
        try:
            telegram.send(f"📌 Pinterest board ready: {title}\nIts first saint is out. In ~10 min (site update): create the board "
                          f"\"{title}\" (description in docs/pinterest-boards.md), then Settings → Bulk create Pins → Auto-publish "
                          f"→ Connect RSS feed:\nhttps://allholysaints.com/pin/{slug}.xml")
        except Exception:
            traceback.print_exc()
            return
        st["announced"].append(slug)
        save_json("pinterest.json", st)


def cmd_post(post_id):
    """A one-off carousel Luis approved in chat (images hosted on a GitHub release). Each platform once; reruns skip what's done."""
    import facebook, instagram, storage, telegram
    p = STATE / "posts" / f"{post_id}.json"
    post = json.loads(p.read_text())
    save = lambda: p.write_text(json.dumps(post, indent=1, ensure_ascii=False) + "\n")
    ig, fb = post.get("instagram"), post.get("facebook")
    if ig and not ig.get("media_id"):
        ig.update(instagram.publish_carousel(ig["caption"], [storage.resolve_direct(u) for u in post["images"]]))
        save()
        _notify(f"📣 Instagram carousel posted: {post['title']}\n{ig.get('permalink') or ''}")
    if fb and not fb.get("url") and facebook.configured():
        WORK.mkdir(exist_ok=True)
        files = [storage.download(u, WORK / f"post-{post_id}-{i}.jpg") for i, u in enumerate(post["images"])]
        fb.update(facebook.post_photos(fb["message"], files))
        save()
        _notify(f"📣 Facebook post: {post['title']}\n{fb['url']}")
