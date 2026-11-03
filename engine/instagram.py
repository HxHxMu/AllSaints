"""Publish Reels (and the odd carousel) with the Instagram API (Instagram Login, graph.instagram.com)."""
import base64, hashlib, os, time
from pathlib import Path
from cryptography.fernet import Fernet
from common import env, http, log, STATE, load_config, save_config

GRAPH = "https://graph.instagram.com"
TOKEN_FILE = STATE / "ig_token.enc"


def _fernet():
    k = env("IG_TOKEN_KEY", required=True)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode()).digest()))


def get_token():
    if TOKEN_FILE.exists() and env("IG_TOKEN_KEY"):
        try:
            return _fernet().decrypt(TOKEN_FILE.read_bytes()).decode()
        except Exception as e:
            log("Stored token unreadable, falling back to secret:", e)
    return env("IG_ACCESS_TOKEN", required=True)


def store_token(tok):
    TOKEN_FILE.write_bytes(_fernet().encrypt(tok.encode()))


def refresh_token():
    tok = get_token()
    r = http.get(f"{GRAPH}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    r.raise_for_status()
    js = r.json()
    store_token(js["access_token"])
    log(f"Instagram token refreshed; valid {int(js.get('expires_in', 0)) // 86400} days")
    return js


def me():
    tok = get_token()
    r = http.get(f"{GRAPH}/me", params={"fields": "user_id,username,account_type", "access_token": tok}, timeout=30)
    r.raise_for_status()
    js = r.json()
    cfg = load_config()
    if cfg.get("ig_user_id") != js.get("user_id"):
        cfg["ig_user_id"], cfg["ig_username"] = js.get("user_id"), js.get("username")
        save_config(cfg)
    return js


def _uid():
    cfg = load_config()
    return cfg.get("ig_user_id") or me()["user_id"]


def _wait(container, tok, max_wait=600):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        r = http.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        sc = r.get("status_code")
        if sc == "FINISHED":
            return True, r
        if sc in ("ERROR", "EXPIRED"):
            return False, r
        time.sleep(15)
    return False, {"status": "timeout"}


def _publish(container, tok):
    r = http.post(f"{GRAPH}/{_uid()}/media_publish", data={"creation_id": container, "access_token": tok}, timeout=60)
    r.raise_for_status()
    mid = r.json()["id"]
    pl = http.get(f"{GRAPH}/{mid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json().get("permalink")
    return {"media_id": mid, "permalink": pl}


def publish_reel(caption, video_url=None, cover_url=None, video_path: Path = None):
    tok = get_token()
    uid = _uid()
    errors = []
    if video_url:
        data = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true", "access_token": tok}
        if cover_url:
            data["cover_url"] = cover_url
        r = http.post(f"{GRAPH}/{uid}/media", data=data, timeout=60)
        if r.ok:
            ok, st = _wait(r.json()["id"], tok)
            if ok:
                return _publish(r.json()["id"], tok)
            errors.append(f"video_url container failed: {st}")
        else:
            errors.append(f"video_url create failed: {r.text[:300]}")
        log(errors[-1])
    if video_path:
        # resumable upload of the local file
        data = {"media_type": "REELS", "upload_type": "resumable", "caption": caption, "share_to_feed": "true", "access_token": tok}
        if cover_url:
            data["cover_url"] = cover_url
        r = http.post(f"{GRAPH}/{uid}/media", data=data, timeout=60)
        if r.ok:
            js = r.json()
            uri = js.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{js['id']}"
            size = os.path.getsize(video_path)
            with open(video_path, "rb") as f:
                up = http.post(uri, headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=f, timeout=900)
            if up.ok:
                ok, st = _wait(js["id"], tok)
                if ok:
                    return _publish(js["id"], tok)
                errors.append(f"resumable container failed: {st}")
            else:
                errors.append(f"rupload failed: {up.status_code} {up.text[:300]}")
        else:
            errors.append(f"resumable create failed: {r.text[:300]}")
    raise RuntimeError(" | ".join(errors))


def publish_story(image_url):
    """A one-image Story (stories.py). Stories take no caption; the image is the whole post."""
    tok = get_token()
    r = http.post(f"{GRAPH}/{_uid()}/media", data={"media_type": "STORIES", "image_url": image_url, "access_token": tok}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Story create failed: {r.text[:300]}")
    ok, st = _wait(r.json()["id"], tok)
    if not ok:
        raise RuntimeError(f"Story container failed: {st}")
    return _publish(r.json()["id"], tok)


def publish_carousel(caption, image_urls):
    """A feed carousel of 2-10 JPEGs at public URLs (Instagram fetches them). Returns {media_id, permalink}."""
    tok, uid = get_token(), _uid()
    children = []
    for url in image_urls:
        r = http.post(f"{GRAPH}/{uid}/media", data={"image_url": url, "is_carousel_item": "true", "access_token": tok}, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Carousel item failed: {r.text[:300]}")
        ok, st = _wait(r.json()["id"], tok, max_wait=180)
        if not ok:
            raise RuntimeError(f"Carousel item not ready: {st}")
        children.append(r.json()["id"])
    r = http.post(f"{GRAPH}/{uid}/media", timeout=60, data={"media_type": "CAROUSEL", "children": ",".join(children),
                                                            "caption": caption, "access_token": tok})
    if not r.ok:
        raise RuntimeError(f"Carousel container failed: {r.text[:300]}")
    ok, st = _wait(r.json()["id"], tok, max_wait=300)
    if not ok:
        raise RuntimeError(f"Carousel not ready: {st}")
    return _publish(r.json()["id"], tok)
