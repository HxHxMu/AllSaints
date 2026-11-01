"""One-off scheduled posts (state/shares.json), e.g. a Facebook Page post linking a sung-prayer video on its release day.

Each entry: {"id", "at": ISO time with offset, "platform": "facebook", "message", "link", "status": "pending"}.
`poll` posts what's due. A YouTube link waits until that video is public (the link preview is built at posting time,
and a private video would show "Video unavailable"); max 3 failed attempts, each reported to Telegram.
Entries are added by hand (Luis approves the text in chat before it's queued).
"""
import re, datetime as dt
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


def run_due(now=None):
    import facebook, telegram
    shares = load_json(FILE, [])
    now = now or dt.datetime.now(dt.timezone.utc)
    changed = False
    for s in shares:
        if s.get("status") != "pending" or dt.datetime.fromisoformat(s["at"]) > now or s.get("attempts", 0) >= 3:
            continue
        if s["platform"] != "facebook" or not facebook.configured():
            continue
        try:
            if not _youtube_public(s.get("link")):
                log("Share waiting for the video to go public:", s["id"])
                continue
            res = facebook.post_link(s["message"], s["link"])
            s.update(status="posted", posted=res, posted_at=now.isoformat(timespec="minutes"))
            telegram.send(f"📣 Shared on Facebook: {s['id']}\n{res['url']}")
        except Exception as e:
            s["attempts"] = s.get("attempts", 0) + 1
            s["error"] = str(e)[:300]
            telegram.send(f"❌ Facebook share failed ({s['attempts']}x): {s['id']}\n{str(e)[:200]}"
                          + ("\nWill retry." if s["attempts"] < 3 else ""))
        changed = True
    if changed:
        save_json(FILE, shares)
