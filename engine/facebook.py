"""Facebook Page Reels (Graph API video_reels). Reels the bot posts to Instagram through the API are not
cross-posted by Instagram's "share to Facebook" setting, so the Page gets its own upload of the same video.

Secrets: FB_PAGE_ID, FB_PAGE_TOKEN (a Page token made from a long-lived user token never expires;
get both once with `pipeline.py fb-auth`). Check with `pipeline.py fb-whoami`.
"""
import getpass, shutil, subprocess, time
from pathlib import Path
from common import ROOT, env, http, log

GRAPH = "https://graph.facebook.com/v24.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v24.0"
APP_ID = "1155309167189478"  # "All Saints Publisher" (public id; the secret is typed at fb-auth's hidden prompt)


def configured():
    return bool(env("FB_PAGE_ID") and env("FB_PAGE_TOKEN"))


def _check(r, what):
    if not r.ok:
        raise RuntimeError(f"Facebook {what} failed {r.status_code}: {r.text[:300]}")
    return r.json()


def me():
    page, tok = env("FB_PAGE_ID", required=True), env("FB_PAGE_TOKEN", required=True)
    return _check(http.get(f"{GRAPH}/{page}", params={"fields": "name,link", "access_token": tok}, timeout=30), "page lookup")


def _wait(vid, tok, max_wait=600):
    """Until Facebook has processed and published the Reel; returns its status."""
    st = {}
    for _ in range(max_wait // 10):
        st = _check(http.get(f"{GRAPH}/{vid}", params={"fields": "status", "access_token": tok}, timeout=30), "status")["status"]
        if st.get("video_status") == "error" or (st.get("processing_phase") or {}).get("status") == "error":
            raise RuntimeError(f"Facebook processing failed: {st}")
        if (st.get("publishing_phase") or {}).get("status") == "complete":
            return st
        time.sleep(10)
    raise RuntimeError(f"Facebook Reel not published after {max_wait}s: {st}")


def publish_reel(description, video_url=None, video_path: Path = None):
    """Upload the video by URL (falls back to sending the local file), publish it, return {id, url}."""
    page, tok = env("FB_PAGE_ID", required=True), env("FB_PAGE_TOKEN", required=True)
    vid = _check(http.post(f"{GRAPH}/{page}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60),
                 "upload start")["video_id"]
    up = None
    if video_url:
        up = http.post(f"{RUPLOAD}/{vid}", headers={"Authorization": f"OAuth {tok}", "file_url": video_url}, timeout=300)
        if not up.ok:
            log("Facebook file_url upload failed, sending the file:", up.status_code, up.text[:200])
    if video_path and (up is None or not up.ok):
        with open(video_path, "rb") as f:
            up = http.post(f"{RUPLOAD}/{vid}", data=f, timeout=900, headers={
                "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(Path(video_path).stat().st_size)})
    if up is None:
        raise RuntimeError("Facebook upload needs a video_url or video_path")
    _check(up, "upload")
    _check(http.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": description,
        "access_token": tok}), "publish")
    _wait(vid, tok)
    link = http.get(f"{GRAPH}/{vid}", params={"fields": "permalink_url", "access_token": tok}, timeout=30).json().get("permalink_url", "")
    url = f"https://www.facebook.com{link}" if link.startswith("/") else (link or f"https://www.facebook.com/reel/{vid}")
    log("Facebook Reel:", vid)
    return {"id": vid, "url": url}


def authorize():
    """One-time local setup: trades a short-lived user token (Graph API Explorer, with pages_show_list,
    pages_read_engagement, pages_manage_posts) for a never-expiring Page token, then stores FB_PAGE_ID and
    FB_PAGE_TOKEN in .env and (if `gh` is installed) as GitHub secrets in the Production environment.
    Everything is typed at hidden prompts; nothing is printed."""
    app_id = env("FB_APP_ID", APP_ID)
    print(f"Meta app: All Saints Publisher ({app_id})")
    app_secret = getpass.getpass("App secret (hidden): ").strip()
    short = getpass.getpass("User token from Graph API Explorer (hidden): ").strip()
    long_user = _check(http.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret, "fb_exchange_token": short}),
        "token exchange")["access_token"]
    pages = _check(http.get(f"{GRAPH}/me/accounts", params={"fields": "id,name,access_token", "access_token": long_user},
                            timeout=30), "page list").get("data", [])
    if not pages:
        raise SystemExit("No Pages on this token: in Graph API Explorer, tick your Page when Facebook asks, and the three permissions.")
    for i, p in enumerate(pages, 1):
        print(f"{i}. {p['name']}")
    p = pages[int(input("Which Page? ").strip() or 1) - 1] if len(pages) > 1 else pages[0]
    vals = {"FB_PAGE_ID": p["id"], "FB_PAGE_TOKEN": p["access_token"]}
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if l.split("=", 1)[0].strip() not in vals]
    envf.write_text("\n".join(lines + [f"{k}={v}" for k, v in vals.items()]) + "\n")
    print(f"Saved FB_PAGE_ID / FB_PAGE_TOKEN for “{p['name']}” to .env")
    if shutil.which("gh"):
        for k, v in vals.items():
            subprocess.run(["gh", "secret", "set", k, "--env", "Production"], input=v, text=True, check=True, cwd=ROOT)
        print("Set the same two as GitHub secrets (environment: Production).")
    else:
        print("`gh` not found: add FB_PAGE_ID and FB_PAGE_TOKEN as GitHub secrets in the Production environment by hand.")
