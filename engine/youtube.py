"""YouTube Shorts upload (Data API v3, OAuth refresh token; no Google client libraries needed).

Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (get them once with `pipeline.py yt-auth <client_secret.json>`).
Privacy comes from config "youtube_privacy" (public; set "private" to publish from YouTube Studio by hand).
Uploads from unverified API projects are no longer forced private (Google, 2026-10), so no audit is needed.
"""
import http.server, json, re, secrets, shutil, subprocess, time, urllib.parse, webbrowser
from pathlib import Path
import datetime as dt
from common import BRAND, ROOT, claude_json, env, http as session, load_config, log

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
# youtube.force-ssl = manage playlists (added 2026-10-30; older refresh tokens lack it until `yt-auth` is rerun)
SCOPES = ("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly "
          "https://www.googleapis.com/auth/youtube.force-ssl")
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
    srcs = "\n".join(f"• {urllib.parse.unquote(x['title'])}: {x['url']}" if x.get("url") else f"• {urllib.parse.unquote(x['title'])}" for x in ep.get("sources", []))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", []))) or "public domain"
    from pipeline import saint_tags, CAP
    tags = " ".join(dict.fromkeys(saint_tags(s, 1) + CAP["hashtags_base"]))  # YouTube shows the first 3 above the title
    share = (s.get("share_cta") or "").strip()
    yt = BRAND.get("youtube", {})
    support = load_config().get("support_url", "").strip()  # Ko-fi page; the line is skipped until it's set
    support = yt.get("support", "{url}").format(url=support) + "\n" if support else ""
    desc = f"""{s.get('caption_hook', '').strip()}

{s.get('summary', '').strip()}

{saint['name']} · {saint.get('dates', '')} · Feast day: {saint.get('feast', '')}

{prayer} 🕯

Read the full story: {page_url(ep)}

—
Sources:
{srcs}
Art: {credits}
{yt.get('disclosure', '')}

{share + chr(10) if share else ''}{support}{yt.get('footer', '')}

{tags} #Shorts"""
    return desc.replace("<", "").replace(">", "")[:4900]  # YouTube rejects angle brackets


SITE = "https://allholysaints.com"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def site_slug(name):
    """Same rule as site/src/lib/episodes.ts slugify: the page address for a saint's name."""
    import unicodedata
    name = re.sub(r"^(Saints?|Sts?\.|San|Santos?|Santas?)\s+", "", name, flags=re.I)
    name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def page_url(ep, lang="en"):
    if lang == "es":
        return f"{SITE}/es/santos/{site_slug(ep['es']['name'])}/"
    return f"{SITE}/saints/{site_slug(ep['script']['saint']['name'])}/"


def _short_title(name, text):
    """"Name: text" cut at a word to fit YouTube's 100 characters with " #Shorts"."""
    title = f"{name}: {text}".strip()
    if len(title) > 90:
        title = title[:90].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return title + " #Shorts"


def localizations(ep):
    """The Spanish title and description (ep.es from translate_es), so the Short shows in Spanish searches."""
    es = ep.get("es")
    if not es or not es.get("name"):
        return {}
    s, site_es = ep["script"], BRAND.get("site_es", {})
    d = dt.date.fromisoformat(ep["date"])
    srcs = "\n".join(f"• {urllib.parse.unquote(x['title'])}: {x['url']}" if x.get("url") else f"• {urllib.parse.unquote(x['title'])}" for x in ep.get("sources", []))
    credits = "; ".join(site_es.get("credits", {}).get(c, c) for c in dict.fromkeys(ep.get("art_credits", []))) or "dominio público"
    desc = f"""{es.get('hook', '').strip()}

{es.get('summary', '').strip()}

{es['name']} · {es.get('dates') or s['saint'].get('dates', '')} · Fiesta: {d.day} de {MESES[d.month - 1]}

{es.get('prayer', '').strip()} 🕯

Lee su historia completa: {page_url(ep, 'es')}

—
Fuentes:
{srcs}
Arte: {credits}
{site_es.get('disclosure', '')}

#santos #catolico #Shorts"""
    return {"es": {"title": _short_title(es.get("display_name") or es["name"], es.get("hook", "")),
                   "description": desc.replace("<", "").replace(">", "")[:4900]}}


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
    if thumbnail:  # custom thumbnails need a phone-verified channel; a failure only logs
        t = session.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set", params={"videoId": vid["id"]},
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                         data=thumbnail.read_bytes(), timeout=120)
        if t.status_code != 200:
            log("Thumbnail not set:", t.status_code, t.text[:200])
    return vid


def set_privacy(video_id, privacy):
    """videos.update replaces the whole status part, so the other fields are sent again."""
    token = _access_token()
    _check_channel(token)
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}
    if BRAND.get("youtube", {}).get("synthetic_media"):
        status["containsSyntheticMedia"] = True
    r = session.put(f"{API}/videos", params={"part": "status"}, headers={"Authorization": f"Bearer {token}"},
                    json={"id": video_id, "status": status}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube privacy change failed {r.status_code}: {r.text[:300]}")


def add_video_to_playlist(title, video_id, position=None):
    """Put one video in the channel playlist with this title (created if missing); `position` 0 = first."""
    token = _access_token()
    pid, h = _playlist_id(token, title), {"Authorization": f"Bearer {token}"}
    snippet = {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}
    if position is not None:
        snippet["position"] = position
    r = session.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=h, json={"snippet": snippet}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Adding to playlist {title!r} failed {r.status_code}: {r.text[:300]}")


CONTINENTS = ["Africa", "Asia", "Europe", "the Americas", "the Middle East", "Oceania"]


def continent(ep):
    """Where the saint lived, as one of CONTINENTS (Haiku, once per episode; cached on ep["continent"])."""
    if ep.get("continent") in CONTINENTS:
        return ep["continent"]
    s = ep["saint"]
    out = claude_json(
        f"Saint: {s.get('name')} ({s.get('dates', '')}). Region: {s.get('region', '')}.\n"
        f"Which one of {CONTINENTS} did this saint live and work in? Use today's geography: Egypt and North Africa "
        "are Africa; the Holy Land, Syria, Lebanon, Mesopotamia, Persia, Arabia, Armenia and Anatolia (Asia Minor) are "
        "the Middle East; Russia and Constantinople are Europe. If they lived in several, pick where they did their "
        'main work or died. Answer JSON: {"continent": "..."}', label="continent", tier="haiku")
    c = out.get("continent") if isinstance(out, dict) else None
    if c not in CONTINENTS:
        raise RuntimeError(f"Continent not recognised: {out}")
    ep["continent"] = c
    return c


def playlist_titles(ep):
    pl = BRAND.get("youtube", {}).get("playlists", {})
    month = dt.date.fromisoformat(ep["id"]).strftime("%B")  # episode id = feast date
    return [pl.get("month", "Saints of {name}").format(name=month),
            pl.get("region", "Saints of {name}").format(name=continent(ep))]


def _playlist_id(token, title, ep=None):
    """The channel's playlist with this exact title, created (public) if missing."""
    h = {"Authorization": f"Bearer {token}"}
    params = {"part": "snippet", "mine": "true", "maxResults": 50}
    while True:
        r = session.get(f"{API}/playlists", params=params, headers=h, timeout=30)
        r.raise_for_status()
        data = r.json()
        for it in data.get("items", []):
            if it["snippet"]["title"] == title:
                return it["id"]
        if not data.get("nextPageToken"):
            break
        params["pageToken"] = data["nextPageToken"]
    desc = BRAND.get("youtube", {}).get("playlists", {}).get("description", "")
    r = session.post(f"{API}/playlists", params={"part": "snippet,status"}, headers=h, timeout=30,
                     json={"snippet": {"title": title, "description": desc.format(title=title), "defaultLanguage": "en"},
                           "status": {"privacyStatus": "public"}})
    if r.status_code != 200:
        raise RuntimeError(f"Creating playlist {title!r} failed {r.status_code}: {r.text[:300]}")
    log("YouTube playlist created:", title)
    pid = r.json()["id"]
    if ep:
        _new_playlist_cover(token, pid, title, ep)
    return pid


def set_playlist_cover(token, playlist_id, jpg: Path):
    """Upload a square JPEG as the playlist's image (playlistImages, type "hero", 1:1 only; replaces an existing one)."""
    h = {"Authorization": f"Bearer {token}"}
    have = session.get(f"{API}/playlistImages", params={"part": "snippet", "parent": playlist_id}, headers=h, timeout=30)
    for old in (have.json().get("items") or []) if have.status_code == 200 else []:
        session.delete(f"{API}/playlistImages", params={"id": old["id"]}, headers=h, timeout=30)  # update() rejects every part
    meta = {"snippet": {"playlistId": playlist_id, "type": "hero"}}
    b = "allsaints" + secrets.token_hex(8)
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
            f"--{b}\r\nContent-Type: image/jpeg\r\n\r\n").encode() + jpg.read_bytes() + f"\r\n--{b}--".encode()
    r = session.post("https://www.googleapis.com/upload/youtube/v3/playlistImages",
                     params={"part": "snippet", "uploadType": "multipart"},
                     headers={**h, "Content-Type": f"multipart/related; boundary={b}"}, data=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Playlist cover upload failed {r.status_code}: {r.text[:300]}")


def _new_playlist_cover(token, playlist_id, title, ep):
    """Cover for a playlist the pipeline just created, from the episode that opened it. Never fails the caller."""
    try:
        import playlist_cover, storage
        from common import WORK
        assets = ep.get("assets", {})
        url, clean = (assets["art.jpg"], True) if assets.get("art.jpg") else (assets["cover.jpg"], False)
        art = storage.download(url, WORK / f"{ep['id']}-playlist-art.jpg")
        try:
            focus, face_y, zoom = *playlist_cover.locate_saint(art), 0.8
        except Exception as e:
            log("Saint not located, centred crop:", str(e)[:120])
            focus, face_y, zoom = 0.5, None, 1.0
        jpg = playlist_cover.make_cover(title, art, WORK / f"playlist-{playlist_id}.jpg", cover_crop=not clean,
                                        focus=focus, face_y=face_y, zoom=zoom)
        set_playlist_cover(token, playlist_id, jpg)
        log("Playlist cover set:", title)
    except Exception as e:
        log("Playlist cover skipped:", title, str(e)[:200])


def add_to_playlists(ep, done=()):
    """Add the episode's Short to its month and continent playlists; skips titles in `done`. Returns the titles added."""
    token = _access_token()
    _check_channel(token)
    added = []
    for title in playlist_titles(ep):
        if title in done:
            continue
        pid, vid, h = _playlist_id(token, title, ep), ep["youtube"]["id"], {"Authorization": f"Bearer {token}"}
        have = session.get(f"{API}/playlistItems", params={"part": "id", "playlistId": pid, "videoId": vid},
                           headers=h, timeout=30)
        if have.status_code == 200 and have.json().get("items"):  # already there (rerun after a partial failure)
            added.append(title)
            continue
        for wait in (0, 5, 15, 30):  # a just-created playlist answers 409 "aborted" for a few seconds
            time.sleep(wait)
            r = session.post(f"{API}/playlistItems", params={"part": "snippet"}, timeout=30, headers=h,
                             json={"snippet": {"playlistId": pid, "position": 0,  # newest first
                                               "resourceId": {"kind": "youtube#video", "videoId": vid}}})
            if r.status_code not in (409, 500, 503):
                break
        if r.status_code != 200:
            raise RuntimeError(f"Adding to playlist {title!r} failed {r.status_code}: {r.text[:300]}")
        added.append(title)
    return added


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
