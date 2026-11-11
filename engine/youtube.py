"""YouTube Shorts upload (Data API v3, OAuth refresh token; no Google client libraries needed): token, upload, thumbnail,
privacy, localizations, channel check, OAuth. Title/description/tags: yt_meta.py. Playlists: yt_playlists.py.

Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (get them once with `pipeline.py yt-auth <client_secret.json>`).
Privacy comes from config "youtube_privacy" (public; set "private" to publish from YouTube Studio by hand).
Uploads from unverified API projects are no longer forced private (Google, 2026-10), so no audit is needed.
"""
import http.server, json, secrets, shutil, subprocess, urllib.parse, webbrowser
from pathlib import Path
from common import BRAND, ROOT, env, http as session, load_config, log
from yt_meta import build_description, build_tags, build_title, localizations

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
# youtube.force-ssl = manage playlists (added 2026-10-30); yt-analytics.readonly = the dashboard's retention/shares
# (added 2026-11-05). Older refresh tokens lack them until `yt-auth` is rerun.
SCOPES = ("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly "
          "https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/yt-analytics.readonly")
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
CATEGORY_EDUCATION = "27"


def configured():
    return all(env(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _access_token():
    r = session.post(TOKEN_URL, data={"client_id": env("YT_CLIENT_ID", required=True),
                                      "client_secret": env("YT_CLIENT_SECRET", required=True),
                                      "refresh_token": env("YT_REFRESH_TOKEN", required=True),
                                      "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        # invalid_grant = token revoked, or the OAuth app was left in "Testing" (tokens die after 7 days)
        raise RuntimeError(f"YouTube token refresh failed: {r.text[:300]}")
    return r.json()["access_token"]


def set_localizations(ep):
    """Add the Spanish title/description to an already uploaded Short (backfill; new uploads carry them)."""
    loc = localizations(ep)
    vid = (ep.get("youtube") or {}).get("id")
    if not loc or not vid:
        return False
    token = _access_token()
    _check_channel(token)
    r = session.get(f"{API}/videos", params={"part": "snippet", "id": vid}, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    snippet = r.json()["items"][0]["snippet"]
    body = {"id": vid, "localizations": loc,
            "snippet": {"title": snippet["title"], "description": snippet.get("description", ""), "categoryId": snippet["categoryId"],
                        "tags": snippet.get("tags", []), "defaultLanguage": "en", "defaultAudioLanguage": snippet.get("defaultAudioLanguage", "en")}}
    r = session.put(f"{API}/videos", params={"part": "snippet,localizations"}, json=body,
                    headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube localizations failed {r.status_code}: {r.text[:300]}")
    log(f"YouTube: Spanish title/description on {vid}")
    return True


def upload_short(ep, video_path: Path):
    """Upload the episode's MP4 as a Short. Returns {"id", "url", "privacy"}."""
    privacy = load_config().get("youtube_privacy", "public")
    meta = {"snippet": {"title": build_title(ep), "description": build_description(ep), "tags": build_tags(ep),
                        "categoryId": CATEGORY_EDUCATION, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}}
    if BRAND.get("youtube", {}).get("synthetic_media"):
        meta["status"]["containsSyntheticMedia"] = True
    parts = "snippet,status"
    if loc := localizations(ep):  # Spanish title/description for Spanish-language search
        meta["localizations"] = loc
        parts += ",localizations"
    vid = upload_video(meta, video_path, parts)
    return {"id": vid["id"], "url": f"https://youtube.com/shorts/{vid['id']}", "privacy": vid.get("status", {}).get("privacyStatus", privacy)}


def upload_video(meta, video_path: Path, parts=None, thumbnail: Path = None):
    """Resumable upload of any video (Shorts and the monthly compilation). Returns the API's video resource."""
    parts = parts or ",".join(k for k in ("snippet", "status", "localizations") if k in meta)
    token = _access_token()
    _check_channel(token)
    size = video_path.stat().st_size
    r = session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": parts}, json=meta, timeout=60,
                     headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                              "X-Upload-Content-Length": str(size)})
    if r.status_code != 200:
        raise RuntimeError(f"YouTube upload init failed {r.status_code}: {r.text[:400]}")
    with open(video_path, "rb") as f:
        r = session.put(r.headers["Location"], data=f, timeout=3600,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4", "Content-Length": str(size)})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed {r.status_code}: {r.text[:400]}")
    vid = r.json()
    log("YouTube upload:", vid["id"], vid.get("status", {}).get("uploadStatus"), vid.get("status", {}).get("privacyStatus"))
    if thumbnail:  # custom thumbnails need a phone-verified channel; a failure only logs (the video is up)
        try:
            set_thumbnail(vid["id"], thumbnail.read_bytes(), token)
        except Exception as e:
            log("Thumbnail not set:", e)
    return vid


def set_thumbnail(video_id, jpg: bytes, token=None):
    """Custom thumbnail (the episode's cover.jpg for Shorts: without it YouTube shows a frame it picks). Raises on failure."""
    token = token or _access_token()
    t = session.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set", params={"videoId": video_id},
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}, data=jpg, timeout=120)
    if t.status_code != 200:
        raise RuntimeError(f"YouTube thumbnail failed {t.status_code}: {t.text[:300]}")
    log("YouTube thumbnail set:", video_id)


def set_privacy(video_id, privacy):
    """videos.update replaces the whole status part, so the other fields are sent again."""
    token = _access_token()
    _check_channel(token)
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True, "publicStatsViewable": True}
    if BRAND.get("youtube", {}).get("synthetic_media"):
        status["containsSyntheticMedia"] = True
    r = session.put(f"{API}/videos", params={"part": "status"}, headers={"Authorization": f"Bearer {token}"},
                    json={"id": video_id, "status": status}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube privacy change failed {r.status_code}: {r.text[:300]}")


def _check_channel(token):
    """Refuse to upload unless the token belongs to the configured channel (config "youtube_channel", e.g. "@allholysaints")."""
    want = (load_config().get("youtube_channel") or "").lower().lstrip("@")
    if not want:
        raise RuntimeError('Set "youtube_channel" (the channel handle) in state/config.json before uploading')
    got = me(token)
    if not isinstance(got, dict) or (got.get("handle") or "").lower().lstrip("@") != want:
        raise RuntimeError(f"YouTube token is for {got}, not @{want}; rerun `pipeline.py yt-auth` and pick the All Saints channel")


def me(token=None):
    token = token or _access_token()
    r = session.get(f"{API}/channels", params={"part": "snippet,statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    items = r.json().get("items", [])
    return {"title": items[0]["snippet"]["title"], "handle": items[0]["snippet"].get("customUrl"),
            "subscribers": items[0]["statistics"].get("subscriberCount")} if items else "No channel on this Google account"


def authorize(client_secret_file, scopes=SCOPES, refresh_key="YT_REFRESH_TOKEN"):
    """One-time local OAuth: opens the browser, catches the redirect on localhost, and stores the three
    YT_* values in .env and (if `gh` is installed) as GitHub secrets in the Production environment.
    Use a "Desktop app" OAuth client, and pick the channel's Brand Account when Google asks.
    Search Console (`gsc-auth`) reuses this with GSC_SCOPE / GSC_REFRESH_TOKEN and Luis's own account."""
    c = json.loads(Path(client_secret_file).read_text())
    c = c.get("installed") or c.get("web") or c
    port, state = 8765, secrets.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({"client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
                                                   "scope": scopes, "access_type": "offline", "prompt": "select_account consent", "state": state})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"All Saints: Google access authorized. You can close this tab.")

        def log_message(self, *a):
            pass

    print("Opening Google sign-in. If it doesn't open, visit:\n" + url)
    webbrowser.open(url)
    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if got.get("error") or got.get("state") != state:
        raise SystemExit(f"Authorization failed: {got.get('error', 'state mismatch')}")
    r = session.post(TOKEN_URL, data={"code": got["code"], "client_id": c["client_id"], "client_secret": c["client_secret"],
                                      "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    refresh = r.json().get("refresh_token")
    if not refresh:
        raise SystemExit("Google returned no refresh token; remove the app at myaccount.google.com/permissions and retry.")
    vals = {"YT_CLIENT_ID": c["client_id"], "YT_CLIENT_SECRET": c["client_secret"], refresh_key: refresh}
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if l.split("=", 1)[0].strip() not in vals]
    envf.write_text("\n".join(lines + [f"{k}={v}" for k, v in vals.items()]) + "\n")
    print(f"Saved {' / '.join(vals)} to .env")
    if shutil.which("gh"):
        for k, v in vals.items():
            subprocess.run(["gh", "secret", "set", k, "--env", "Production"], input=v, text=True, check=True, cwd=ROOT)
        print(f"Set the same as GitHub secrets (environment: Production): {', '.join(vals)}")
    else:
        print(f"`gh` not found: add {', '.join(vals)} as GitHub secrets in the Production environment by hand.")
