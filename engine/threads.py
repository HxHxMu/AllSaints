"""Threads posts (Threads API, graph.threads.net). Instagram's "share to Threads" switch skips posts made through the
API (like its Facebook switch), so the bot posts the day's video to @all.holy.saints's Threads itself.

Secrets: TH_TOKEN_KEY; TH_APP_ID, TH_APP_SECRET only if th-auth signed in (the *Threads* app id and secret, not the
Facebook ones; renewing never needs them). The long-lived token (60 days, renewed by every run once it is under
15 days from expiry, and only renewable once it is a day old) lives encrypted in state/th_token.enc, so the bot can
store the renewed one; poll/maintenance commit it. Set up once with `pipeline.py th-auth`; check with `th-whoami`.
"""
import base64, getpass, hashlib, json, os, secrets, shutil, subprocess, time, urllib.parse
from cryptography.fernet import Fernet
from common import ROOT, STATE, env, http, log

GRAPH = "https://graph.threads.net/v1.0"
AUTHORIZE = "https://threads.net/oauth/authorize"
SCOPES = "threads_basic,threads_content_publish"
REDIRECT = "https://allholysaints.com/"  # must be listed exactly under the use case's "Redirect Callback URLs"
TOKEN_FILE = STATE / "th_token.enc"
MAX_TEXT = 490  # Threads allows 500; margin for emoji counted as two
RENEW_DAYS = 15


def configured():
    return bool(env("TH_TOKEN_KEY") and TOKEN_FILE.exists())


def _fernet():
    k = env("TH_TOKEN_KEY", required=True)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode()).digest()))


def _load():
    return json.loads(_fernet().decrypt(TOKEN_FILE.read_bytes()))


def _store(token, expires_in, user_id=None):
    old = _load() if TOKEN_FILE.exists() else {}
    TOKEN_FILE.write_bytes(_fernet().encrypt(json.dumps({
        "access_token": token, "expires": int(time.time()) + int(expires_in or 0), "issued": int(time.time()),
        "user_id": user_id or old.get("user_id")}).encode()))


def _check(r, what):
    js = r.json() if r.content else {}
    if not r.ok or "error" in js:
        raise RuntimeError(f"Threads {what} failed {r.status_code}: {r.text[:300]}")
    return js


def access_token():
    """The stored token, renewed (and stored) once it is within RENEW_DAYS of expiry."""
    tok = _load()
    left = tok["expires"] - time.time()
    if left < RENEW_DAYS * 86400 and time.time() - tok.get("issued", 0) > 86400:
        try:
            js = _check(http.get("https://graph.threads.net/refresh_access_token", timeout=30,
                                 params={"grant_type": "th_refresh_token", "access_token": tok["access_token"]}), "token refresh")
            _store(js["access_token"], js.get("expires_in"))
            log(f"Threads token renewed; valid {int(js.get('expires_in', 0)) // 86400} days")
            return js["access_token"]
        except Exception as e:  # the old one still works until it expires; the next run tries again
            log("Threads token renewal failed:", str(e)[:200])
    if left <= 0:
        raise RuntimeError("Threads token expired: rerun `pipeline.py th-auth`")
    return tok["access_token"]


def keep_alive():
    """Weekly (Maintenance, with the Instagram refresh): renew the token whatever its age, so it never nears expiry
    even when nothing posts, and raise on failure so the job's ❌ reaches Telegram."""
    tok = _load()
    if time.time() - tok.get("issued", 0) < 86400:  # Threads only renews tokens at least a day old
        return
    js = _check(http.get("https://graph.threads.net/refresh_access_token", timeout=30,
                         params={"grant_type": "th_refresh_token", "access_token": tok["access_token"]}), "token refresh")
    _store(js["access_token"], js.get("expires_in"))
    log(f"Threads token renewed; valid {int(js.get('expires_in', 0)) // 86400} days")


def me():
    return _check(http.get(f"{GRAPH}/me", params={"fields": "id,username", "access_token": access_token()}, timeout=30), "me")


def build_text(ep, page_url):
    """The post text, ≤500 characters (Threads' limit): hook, name and feast, summary, prayer, the saint's page, the art
    disclosure. The summary is what gets shortened when it doesn't fit."""
    s = ep["script"]
    saint = s["saint"]
    hook = (ep.get("caption_hook_override") or s.get("caption_hook") or "").strip().split("\n")[0]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    credit = "; ".join(dict.fromkeys(ep.get("art_credits", []))) or "public domain"
    head = f"{hook}\n\n{saint['name']} · Feast day: {saint.get('feast', '')}\n"
    tail = f"\n\n{prayer} 🕯\n\nThe full story: {page_url}\nArt: {credit}"
    summary = s.get("summary", "").strip()
    room = MAX_TEXT - len(head) - len(tail)
    if len(summary) > room:
        summary = summary[:max(0, room - 1)].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return (head + summary + tail)[:MAX_TEXT]


def _wait(container, tok, max_wait=300):
    """Until Threads has processed the video container. Nothing is posted yet, so a failure here is safe to retry."""
    st = {}
    for _ in range(max_wait // 10):
        st = _check(http.get(f"{GRAPH}/{container}", params={"fields": "status,error_message", "access_token": tok},
                             timeout=30), "container status")
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads processing failed: {st}")
        time.sleep(10)
    raise RuntimeError(f"Threads video still processing after {max_wait}s: {st}")


def publish_video(text, video_url):
    """Post a video with text. Returns {id, url}. The post exists once threads_publish answers; nothing after that raises."""
    tok = access_token()
    container = _check(http.post(f"{GRAPH}/me/threads", timeout=60, data={
        "media_type": "VIDEO", "video_url": video_url, "text": text, "access_token": tok}), "container")["id"]
    _wait(container, tok)
    pid = _check(http.post(f"{GRAPH}/me/threads_publish", data={"creation_id": container, "access_token": tok},
                           timeout=60), "publish")["id"]
    log("Threads post:", pid)
    try:  # posted already: a failed lookup only loses the nice link
        url = http.get(f"{GRAPH}/{pid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json().get("permalink", "")
    except Exception:
        url = ""
    return {"id": pid, "url": url or "https://www.threads.net/@all.holy.saints"}


def _save_secrets(vals):
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if l.split("=", 1)[0].strip() not in vals]
    envf.write_text("\n".join(lines + [f"{k}={v}" for k, v in vals.items()]) + "\n")
    names = " / ".join(vals)
    print(f"Saved {names} to .env and the token to state/th_token.enc (commit it).")
    if shutil.which("gh"):
        for k, v in vals.items():
            subprocess.run(["gh", "secret", "set", k, "--env", "Production"], input=v, text=True, check=True, cwd=ROOT)
        print(f"Set {names} as GitHub secrets (environment: Production).")
    else:
        print(f"`gh` not found: add {names} as GitHub secrets in the Production environment by hand.")


def authorize():
    """One-time local setup, writes state/th_token.enc and stores TH_TOKEN_KEY (plus TH_APP_ID / TH_APP_SECRET when
    signing in) in .env and (with `gh`) the Production secrets. Two ways in: paste a token from the use case's
    Settings → User Token Generator (already long-lived; renewing needs no app secret), or press Enter to sign in
    through Threads' consent page with the app id and secret."""
    vals = {"TH_TOKEN_KEY": env("TH_TOKEN_KEY") or secrets.token_urlsafe(32)}
    os.environ.update(vals)
    pasted = getpass.getpass("Token from the User Token Generator, or Enter to sign in instead (hidden): ").strip()
    if pasted:
        _store(pasted, 60 * 86400)  # the generator's tokens are long-lived (60 days); the first renewal stores the real expiry
        try:
            who = me()
        except RuntimeError as e:
            TOKEN_FILE.unlink()
            raise SystemExit(f"That token didn't work: {str(e)[:200]}")
        _store(pasted, 60 * 86400, str(who.get("id", "")))
        print("Connected as:", who.get("username"))
        return _save_secrets(vals)
    app_id = getpass.getpass("Threads app ID (hidden): ").strip()
    secret = getpass.getpass("Threads app secret (hidden): ").strip()
    print(f"(secret is {len(secret)} characters; a Threads app secret is 32)")
    vals.update({"TH_APP_ID": app_id, "TH_APP_SECRET": secret})
    os.environ.update(vals)
    state = secrets.token_urlsafe(16)
    print("\nOpen this, log in as @all.holy.saints and allow access:\n")
    print(AUTHORIZE + "?" + urllib.parse.urlencode({"client_id": app_id, "redirect_uri": REDIRECT, "scope": SCOPES,
                                                   "response_type": "code", "state": state}))
    handoff = ROOT / "work" / "threads" / "redirect.txt"  # for a browser without an address bar
    back = getpass.getpass(f"\nPaste the full allholysaints.com address Threads sent you to, or press Enter to read "
                           f"{handoff.relative_to(ROOT)} (hidden): ").strip()
    if not back and handoff.exists():
        back = handoff.read_text().strip()
        handoff.unlink()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
    if q.get("error"):
        raise SystemExit(f"Threads refused: {q.get('error_description', q['error'])[0]}")
    if not q.get("code"):
        raise SystemExit("No code in that address. Paste the allholysaints.com address Threads opens after you allow access.")
    code = q["code"][0].split("#")[0]  # Threads appends "#_"
    try:
        short = _check(http.post("https://graph.threads.net/oauth/access_token", timeout=30, data={
            "client_id": app_id, "client_secret": secret, "grant_type": "authorization_code", "redirect_uri": REDIRECT,
            "code": code}), "code exchange")
        long = _check(http.get("https://graph.threads.net/access_token", timeout=30, params={
            "grant_type": "th_exchange_token", "client_secret": secret, "access_token": short["access_token"]}), "long-lived token")
    except RuntimeError as e:  # Threads echoes a wrong secret back in its error: keep it off the screen
        raise SystemExit(str(e).replace(secret, "<secret>") + "\nCheck the Threads app secret (use case → Settings → Show), "
                         "or rerun th-auth and paste a User Token Generator token instead.")
    _store(long["access_token"], long.get("expires_in"), str(short.get("user_id", "")))
    print("Connected as:", me().get("username"))
    _save_secrets(vals)
