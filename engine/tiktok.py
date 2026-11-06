"""TikTok drafts (Content Posting API, "upload to inbox"). TikTok only lets audited apps post publicly, and it won't
audit a tool that posts to its owner's own account, so the bot sends each day's video to the TikTok inbox as a draft;
Luis taps TikTok's notification, pastes the caption (Telegram sends it), turns on the AI-generated label and posts.

Secrets: TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_TOKEN_KEY. Tokens (2 h access, 180-day refresh that changes on every
refresh) live encrypted in state/tt_token.enc, so the bot can store the new refresh token. Set up once with
`pipeline.py tt-auth`; check with `pipeline.py tt-whoami`.
"""
import base64, getpass, hashlib, json, os, secrets, shutil, subprocess, time, urllib.parse
from pathlib import Path
from cryptography.fernet import Fernet
from common import ROOT, STATE, env, http, log

API = "https://open.tiktokapis.com/v2"
AUTHORIZE = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.upload"
REDIRECT = "https://allholysaints.com/"  # must match the app's Login Kit redirect URI exactly
TOKEN_FILE = STATE / "tt_token.enc"
CHUNK = 10 * 1024 * 1024  # 5–64 MB per chunk; the last one takes the remainder (up to 128 MB)


def configured():
    return bool(env("TT_CLIENT_KEY") and env("TT_CLIENT_SECRET") and env("TT_TOKEN_KEY") and TOKEN_FILE.exists())


def _fernet():
    k = env("TT_TOKEN_KEY", required=True)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode()).digest()))


def _load():
    return json.loads(_fernet().decrypt(TOKEN_FILE.read_bytes()))


def _store(js):
    now = int(time.time())
    TOKEN_FILE.write_bytes(_fernet().encrypt(json.dumps({
        "access_token": js["access_token"], "access_expires": now + int(js.get("expires_in", 7200)),
        "refresh_token": js["refresh_token"], "refresh_expires": now + int(js.get("refresh_expires_in", 0)),
        "open_id": js.get("open_id"), "scope": js.get("scope")}).encode()))


def _token_call(**data):
    r = http.post(f"{API}/oauth/token/", timeout=30, headers={"Content-Type": "application/x-www-form-urlencoded"},
                  data={"client_key": env("TT_CLIENT_KEY", required=True),
                        "client_secret": env("TT_CLIENT_SECRET", required=True), **data})
    js = r.json() if r.content else {}
    if not r.ok or "access_token" not in js:
        raise RuntimeError(f"TikTok token call failed {r.status_code}: {r.text[:300]}")
    return js


def access_token():
    """A valid access token, refreshing (and storing TikTok's new refresh token) when the old one is near expiry."""
    tok = _load()
    if tok["access_expires"] - time.time() > 300:
        return tok["access_token"]
    js = _token_call(grant_type="refresh_token", refresh_token=tok["refresh_token"])
    _store(js)  # the old refresh token stops working: the new one must reach state/ (poll commits it)
    log(f"TikTok token refreshed; refresh valid {int(js.get('refresh_expires_in', 0)) // 86400} days")
    return js["access_token"]


class Failed(RuntimeError):
    """TikTok said the upload failed: safe to try again."""


def _check(r, what):
    js = r.json() if r.content else {}
    err = js.get("error") or {}
    if not r.ok or (err.get("code") not in (None, "", "ok")):
        raise RuntimeError(f"TikTok {what} failed {r.status_code}: {r.text[:300]}")
    return js.get("data") or {}


def me():
    tok = access_token()
    return _check(http.get(f"{API}/user/info/", params={"fields": "open_id,display_name"},
                           headers={"Authorization": f"Bearer {tok}"}, timeout=30), "user info").get("user")


def _wait(tok, publish_id, max_wait=300):
    """Until TikTok has the draft in the inbox; returns the last status. Raises only if TikTok says it failed."""
    st = {}
    for _ in range(max_wait // 10):
        st = _check(http.post(f"{API}/post/publish/status/fetch/", json={"publish_id": publish_id}, timeout=30,
                              headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}),
                    "status")
        if st.get("status") == "FAILED":
            raise Failed(f"TikTok processing failed: {st.get('fail_reason') or st}")
        if st.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return st
        time.sleep(10)
    log(f"TikTok draft still processing after {max_wait}s:", st)  # accepted: it lands on its own (a retry would duplicate it)
    return st


def upload_draft(video_path: Path):
    """Send the video to the TikTok inbox as a draft. Returns {publish_id, status} once TikTok has all of it."""
    tok = access_token()
    size = Path(video_path).stat().st_size
    chunk = size if size < 5 * 1024 * 1024 else CHUNK
    count = max(1, size // chunk)
    init = _check(http.post(f"{API}/post/publish/inbox/video/init/", timeout=60, json={"source_info": {
        "source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}},
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}), "upload start")
    with open(video_path, "rb") as f:
        for i in range(count):
            first = i * chunk
            last = size - 1 if i == count - 1 else first + chunk - 1
            body = f.read(last - first + 1)
            r = http.put(init["upload_url"], data=body, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)), "Content-Range": f"bytes {first}-{last}/{size}"})
            if r.status_code not in (201, 206):
                raise RuntimeError(f"TikTok upload chunk {i + 1}/{count} failed {r.status_code}: {r.text[:200]}")
    log("TikTok draft uploaded:", init["publish_id"])
    try:
        st = _wait(tok, init["publish_id"]).get("status", "")
    except Failed:
        raise
    except Exception as e:  # uploaded: a failed status check must not send it again
        log("TikTok status check failed:", str(e)[:200])
        st = ""
    return {"publish_id": init["publish_id"], "status": st}


def authorize():
    """One-time local setup: opens TikTok's consent page, trades the code for tokens, writes state/tt_token.enc and
    stores TT_CLIENT_KEY / TT_CLIENT_SECRET / TT_TOKEN_KEY in .env and (with `gh`) the Production secrets."""
    key = getpass.getpass("TikTok client key (hidden): ").strip()
    secret = getpass.getpass("TikTok client secret (hidden): ").strip()
    vals = {"TT_CLIENT_KEY": key, "TT_CLIENT_SECRET": secret, "TT_TOKEN_KEY": env("TT_TOKEN_KEY") or secrets.token_urlsafe(32)}
    os.environ.update(vals)
    state = secrets.token_urlsafe(16)
    print("\nOpen this, log in as @allholysaints and allow access:\n")
    print(AUTHORIZE + "?" + urllib.parse.urlencode({"client_key": key, "scope": SCOPES, "response_type": "code",
                                                   "redirect_uri": REDIRECT, "state": state}))
    handoff = ROOT / "work" / "tiktok" / "redirect.txt"  # lets the address come from a browser without an address bar
    back = getpass.getpass(f"\nPaste the full address TikTok sent you to, or press Enter to read {handoff.relative_to(ROOT)} (hidden): ").strip()
    if not back and handoff.exists():
        back = handoff.read_text().strip()
        handoff.unlink()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
    if q.get("error"):
        raise SystemExit(f"TikTok refused: {q.get('error_description', q['error'])[0]}")
    if not q.get("code"):
        raise SystemExit(f"No code in that address (it had: {', '.join(q) or 'nothing'}). Paste the allholysaints.com "
                         "address TikTok opens after you tap Authorize, not the tiktok.com link.")
    if q.get("state", [""])[0] != state:  # a local one-off, so a code from an earlier run's link is fine if still fresh
        print("(That address is from an earlier tt-auth link; trying its code anyway.)")
    _store(_token_call(grant_type="authorization_code", code=q["code"][0], redirect_uri=REDIRECT))
    print("Connected as:", me().get("display_name"))
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if l.split("=", 1)[0].strip() not in vals]
    envf.write_text("\n".join(lines + [f"{k}={v}" for k, v in vals.items()]) + "\n")
    print("Saved TT_CLIENT_KEY / TT_CLIENT_SECRET / TT_TOKEN_KEY to .env and the tokens to state/tt_token.enc (commit it).")
    if shutil.which("gh"):
        for k, v in vals.items():
            subprocess.run(["gh", "secret", "set", k, "--env", "Production"], input=v, text=True, check=True, cwd=ROOT)
        print("Set the same three as GitHub secrets (environment: Production).")
    else:
        print("`gh` not found: add the three as GitHub secrets in the Production environment by hand.")
