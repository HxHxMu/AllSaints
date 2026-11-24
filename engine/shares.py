"""One-off scheduled posts (state/shares.json), e.g. a Facebook Page post linking a sung-prayer video on its release day.

Each entry: {"id", "at": ISO time with offset, "platform": "facebook" | "instagram" | "facebook_reel" | "tiktok" | "youtube", "message",
"link", "status": "pending"}; an Instagram or facebook_reel entry also has "video" (and optionally "cover"), URLs of a
Reel uploaded ahead of time, and posts it as a Reel with "message" as the caption ("link" is only checked, since
Instagram captions can't carry links). A tiktok entry sends "video" to the TikTok inbox as a draft and Telegram carries
"message" for Luis to paste when he posts it (the series teaser and parts, 2026-11). A youtube entry uploads "video"
publicly at its time with "title" and "message" as the description (a Short when it is vertical and under 3 min).
`poll` posts what's due. A YouTube link waits until that video is public (the link preview is built at posting time,
and a private video would show "Video unavailable"); max 3 failed attempts, each reported to Telegram.
Entries are added by hand (Luis approves the text in chat before it's queued).
"""
import re, traceback, datetime as dt
from common import load_json, save_json, log

FILE = "shares.json"


def _youtube_public(link):
    m = re.search(r"(?:youtu\.be/|v=|shorts/)([\w-]{11})", link or "")
    if not m:
        return True
    import youtube
    from common import http
    r = http.get(f"{youtube.API}/videos", params={"part": "status", "id": m.group(1)},
                 headers={"Authorization": f"Bearer {youtube._access_token()}"}, timeout=30)
    r.raise_for_status()
    items = r.json().get("items") or []
    return bool(items) and items[0]["status"]["privacyStatus"] == "public"


def _post(s):
    """Posts one entry. Returns (platform name, API result, url of the post)."""
    if s["platform"] == "instagram":
        import instagram, storage
        res = instagram.publish_reel(s["message"], video_url=storage.resolve_direct(s["video"]),
                                     cover_url=storage.resolve_direct(s["cover"]) if s.get("cover") else None)
        return "Instagram", res, res.get("permalink") or ""
    import facebook, storage
    if s["platform"] == "facebook_reel":
        res = facebook.publish_reel(s["message"], video_url=storage.resolve_direct(s["video"]),
                                    cover_url=storage.resolve_direct(s["cover"]) if s.get("cover") else None)
        return "Facebook (Reel)", res, res["url"]
    if s["platform"] == "youtube":
        import tempfile, youtube
        from common import BRAND, http
        from pathlib import Path
        meta = {"snippet": {"title": s["title"], "description": s["message"], "tags": s.get("tags", []), "categoryId": "1",
                            "defaultLanguage": "en"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True}}
        if s.get("synthetic", BRAND.get("youtube", {}).get("synthetic_media")):   # realistic AI footage must be disclosed
            meta["status"]["containsSyntheticMedia"] = True
        r = http.get(storage.resolve_direct(s["video"]), timeout=300)
        r.raise_for_status()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(r.content)
            vid = youtube.upload_video(meta, path, "snippet,status")
        return "YouTube", {"id": vid["id"]}, f"https://youtube.com/shorts/{vid['id']}"
    if s["platform"] == "tiktok":
        import tempfile, tiktok
        from common import http
        from pathlib import Path
        r = http.get(storage.resolve_direct(s["video"]), timeout=300)
        r.raise_for_status()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.mp4"
            path.write_bytes(r.content)
            res = tiktok.upload_draft(path)
        return "TikTok (inbox draft; caption below)", res, s["message"]
    res = facebook.post_link(s["message"], s["link"])
    return "Facebook", res, res["url"]


def run_due(now=None):
    import facebook, telegram, tiktok
    shares = load_json(FILE, [])
    now = now or dt.datetime.now(dt.timezone.utc)
    changed = False
    for s in shares:
        if s.get("status") != "pending" or dt.datetime.fromisoformat(s["at"]) > now or s.get("attempts", 0) >= 3:
            continue
        if s["platform"] not in ("facebook", "instagram", "facebook_reel", "tiktok", "youtube"):
            continue
        if s["platform"].startswith("facebook") and not facebook.configured() or s["platform"] == "tiktok" and not tiktok.configured():
            continue
        try:
            if not _youtube_public(s.get("link")):
                log("Share waiting for the video to go public:", s["id"])
                continue
            where, res, url = _post(s)
        except Exception as e:
            s["attempts"] = s.get("attempts", 0) + 1
            s["error"] = str(e)[:300]
            telegram.send(f"❌ {s['platform'].title()} share failed ({s['attempts']}x): {s['id']}\n{str(e)[:200]}"
                          + ("\nWill retry." if s["attempts"] < 3 else ""))
            changed = True
            continue
        s.update(status="posted", posted=res, posted_at=now.isoformat(timespec="minutes"))  # live: never retried
        changed = True
        try:
            telegram.send(f"📣 Shared on {where}: {s['id']}\n{url}")
        except Exception:
            traceback.print_exc()
    if changed:
        save_json(FILE, shares)
