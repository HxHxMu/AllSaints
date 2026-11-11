"""YouTube playlists: each Short goes into "Saints of <Month>" and "Saints of <continent>" (created public on first use,
with a cover from the episode that opened it). Titles/description: brand.json → youtube.playlists."""
import datetime as dt, json, secrets, time
from pathlib import Path
from common import BRAND, claude_json, http as session, log
from youtube import API, _access_token, _check_channel


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
