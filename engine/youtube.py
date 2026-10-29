"""YouTube Shorts upload (Data API v3, OAuth refresh token; no Google client libraries needed).

Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (get them once with `pipeline.py yt-auth <client_secret.json>`).
Privacy comes from config "youtube_privacy" (public; set "private" to publish from YouTube Studio by hand).
Uploads from unverified API projects are no longer forced private (Google, 2026-10), so no audit is needed.
"""
import http.server, json, secrets, shutil, subprocess, urllib.parse, webbrowser
from pathlib import Path
from common import BRAND, ROOT, env, http as session, load_config, log

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
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


def build_title(ep):
    s = ep["script"]
    name = s["saint"].get("display_name") or s["saint"]["name"]
    title = (s.get("youtube_title") or f"{name}, {s['saint'].get('region', '')}".rstrip(", ")).strip()
    if name.split()[-1] not in title:  # the saint's name is what people search for
        title = f"{name}: {title}"
    return (title[:90].rstrip() + " #Shorts")[:100]


def build_description(ep):
    s = ep["script"]
    saint = s["saint"]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    srcs = "\n".join(f"• {x['title']}: {x['url']}" if x.get("url") else f"• {x['title']}" for x in ep.get("sources", []))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", []))) or "public domain"
    from pipeline import saint_tags, CAP
    tags = " ".join(dict.fromkeys(saint_tags(s, 1) + CAP["hashtags_base"]))  # YouTube shows the first 3 above the title
    share = (s.get("share_cta") or "").strip()
    yt = BRAND.get("youtube", {})
    desc = f"""{s.get('caption_hook', '').strip()}

{s.get('summary', '').strip()}

{saint['name']} · {saint.get('dates', '')} · Feast day: {saint.get('feast', '')}

{prayer} 🕯

—
Sources:
{srcs}
Art: {credits}
{yt.get('disclosure', '')}

{share + chr(10) if share else ''}{yt.get('footer', '')}

{tags} #Shorts"""
    return desc.replace("<", "").replace(">", "")[:4900]  # YouTube rejects angle brackets


def build_tags(ep):
    s = ep["script"]
    tags = [s["saint"]["name"], s["saint"].get("display_name", ""), s["saint"].get("region", ""),
            "Catholic saints", "saint of the day", "lives of the saints"]
    tags += [t.lstrip("#") for t in s.get("hashtags") or []]
    out, total = [], 0
    for t in dict.fromkeys(x.strip() for x in tags if x and x.strip()):
        if total + len(t) + 1 > 450:  # 500-char limit across all tags
            break
        out.append(t)
        total += len(t) + 1
    return out


def upload_short(ep, video_path: Path):
    """Upload the episode's MP4 as a Short. Returns {"id", "url", "privacy"}."""
    privacy = load_config().get("youtube_privacy", "public")
    meta = {"snippet": {"title": build_title(ep), "description": build_description(ep), "tags": build_tags(ep),
                        "categoryId": CATEGORY_EDUCATION, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}}
    if BRAND.get("youtube", {}).get("synthetic_media"):
        meta["status"]["containsSyntheticMedia"] = True
    token = _access_token()
    _check_channel(token)
    size = video_path.stat().st_size
    r = session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=meta, timeout=60,
                     headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                              "X-Upload-Content-Length": str(size)})
    if r.status_code != 200:
        raise RuntimeError(f"YouTube upload init failed {r.status_code}: {r.text[:400]}")
    with open(video_path, "rb") as f:
        r = session.put(r.headers["Location"], data=f, timeout=900,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4", "Content-Length": str(size)})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed {r.status_code}: {r.text[:400]}")
    vid = r.json()
    log("YouTube upload:", vid["id"], vid.get("status", {}).get("uploadStatus"), vid.get("status", {}).get("privacyStatus"))
    return {"id": vid["id"], "url": f"https://youtube.com/shorts/{vid['id']}", "privacy": vid.get("status", {}).get("privacyStatus", privacy)}


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


def authorize(client_secret_file):
    """One-time local OAuth: opens the browser, catches the redirect on localhost, and stores the three
    YT_* values in .env and (if `gh` is installed) as GitHub secrets in the Production environment.
    Use a "Desktop app" OAuth client, and pick the channel's Brand Account when Google asks."""
    c = json.loads(Path(client_secret_file).read_text())
    c = c.get("installed") or c.get("web") or c
    port, state = 8765, secrets.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({"client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
                                                   "scope": SCOPES, "access_type": "offline", "prompt": "select_account consent", "state": state})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"All Saints: YouTube authorized. You can close this tab.")

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
    vals = {"YT_CLIENT_ID": c["client_id"], "YT_CLIENT_SECRET": c["client_secret"], "YT_REFRESH_TOKEN": refresh}
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if l.split("=", 1)[0].strip() not in vals]
    envf.write_text("\n".join(lines + [f"{k}={v}" for k, v in vals.items()]) + "\n")
    print("Saved YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN to .env")
    if shutil.which("gh"):
        for k, v in vals.items():
            subprocess.run(["gh", "secret", "set", k, "--env", "Production"], input=v, text=True, check=True, cwd=ROOT)
        print("Set the same three as GitHub secrets (environment: Production).")
    else:
        print("`gh` not found: add the three values as GitHub secrets in the Production environment by hand.")
