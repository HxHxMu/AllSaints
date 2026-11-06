"""Nightly numbers for the private dashboard (allholysaints.com/dash/). No AI.

Collects the pipeline's own state plus YouTube, Instagram and Search Console metrics into one JSON,
then POSTs it to the site's Pages Function (/api/dash-ingest), which keeps it in Cloudflare KV.
The repo is public, so these numbers are never written to state/.

Each source is optional and fails on its own: a missing permission shows as a note on the dashboard.
- YouTube: views/likes/comments from the Data API (existing token); retention, shares and subscribers
  from the Analytics API, which needs the yt-analytics.readonly scope (rerun `pipeline.py yt-auth` once).
- Instagram: Reel insights (needs instagram_business_manage_insights on the token), followers.
- Threads: post views/likes/replies/reposts and followers; needs threads_manage_insights on the token (add it to the
  use case, regenerate in User Token Generator, rerun `pipeline.py th-auth`).
- TikTok: followers and video views; needs the user.info.stats and video.list scopes (add them in the TikTok app, rerun
  `pipeline.py tt-auth`). Luis posts the drafts by hand, so videos are matched to saints by name, else by posting date.
- Search Console: GSC_REFRESH_TOKEN from `pipeline.py gsc-auth <client_secret.json>` (Luis's own Google
  account, the one that owns the allholysaints.com property).
Secrets: DASH_INGEST_KEY (same value in GitHub Production and Cloudflare Pages). Optional DASH_INGEST_URL.

Run: `pipeline.py metrics` (posts) or `pipeline.py metrics --out work/metrics.json` (local file only).
"""
import datetime as dt, json, urllib.parse
from common import env, http, load_config, load_episodes, log, today, tz
from pipeline import GEMINI_PER_EPISODE, call_cost

INGEST_URL = "https://allholysaints.com/api/dash-ingest"
YT_API = "https://www.googleapis.com/youtube/v3"
YTA_API = "https://youtubeanalytics.googleapis.com/v2/reports"
GSC_SITE = "sc-domain:allholysaints.com"
DAYS = 28  # daily series length
BUDGET = (20, 60)  # $/month, CLAUDE.md


def _words(text):
    return len((text or "").split())


def _daily(ep):
    """The channel's daily saints, not the intro or one-off posts."""
    return ep["id"][:4].isdigit() and ep.get("saint_pick") is not None


def pipeline(eps):
    now = dt.datetime.now(tz())
    t = today()
    rows, fails = [], []
    for ep in sorted(eps, key=lambda e: e["id"]):
        if not _daily(ep):
            continue
        d = dt.date.fromisoformat(ep["date"])
        yt, fb, ig = ep.get("youtube") or {}, ep.get("facebook") or {}, ep.get("published") or {}
        row = {"date": ep["date"], "saint": ep["saint"]["name"], "status": ep["status"], "attempts": ep.get("attempts", 0),
               "instagram": bool(ig.get("media_id")), "youtube": bool(yt.get("id")), "facebook": bool(fb.get("id")),
               "threads": bool((ep.get("threads") or {}).get("id")), "tiktok": bool((ep.get("tiktok") or {}).get("publish_id")),
               "story": bool((ep.get("story") or {}).get("media_id")),
               "errors": [f"{k}: {v['error'][:160]}" for k, v in (("youtube", yt), ("facebook", fb), ("threads", ep.get("threads") or {}),
                                                                ("tiktok", ep.get("tiktok") or {})) if v.get("error")]}
        if t <= d <= t + dt.timedelta(days=13):
            rows.append(row)
        if ep["status"] == "failed" or (d < t and ep["status"] != "published") or row["errors"] and d >= t - dt.timedelta(days=7):
            fails.append(row)
    want = [(t + dt.timedelta(days=i)).isoformat() for i in range(8)]
    have = {r["date"] for r in rows}
    rows += [{"date": d, "saint": None, "status": "missing"} for d in want if d not in have]
    month = t.strftime("%Y-%m")
    costs = {e["id"]: sum(call_cost(r) for r in e["usage"]) for e in eps if e.get("usage") and _daily(e)}
    in_month = [c for k, c in costs.items() if k.startswith(month)]
    avg = sum(costs.values()) / len(costs) if costs else 0
    return {"upcoming": sorted(rows, key=lambda r: r["date"]), "problems": fails[-10:],
            "cost": {"month": month, "episodes": len(in_month),
                     "month_to_date": round(sum(in_month) + GEMINI_PER_EPISODE * len(in_month), 2),
                     "per_episode": round(avg + GEMINI_PER_EPISODE, 3), "per_30_days": round((avg + GEMINI_PER_EPISODE) * 30, 2),
                     "budget": BUDGET},
            "now": now.isoformat(timespec="minutes")}


def episode_rows(eps):
    rows = []
    for ep in sorted(eps, key=lambda e: e["id"]):
        if not (_daily(ep) and ep["status"] == "published"):
            continue
        beats = ep["script"]["beats"]
        rows.append({"date": ep["date"], "saint": ep["saint"]["name"], "slug": ep.get("slug"),
                     "duration": ep.get("duration"), "words": sum(_words(b["text"]) for b in beats),
                     "who_words": sum(_words(b["text"]) for b in beats if b.get("role") == "who"),
                     "close_words": sum(_words(b["text"]) for b in beats if b.get("role") in ("turn", "close")),
                     "spanish": bool(ep.get("es")),
                     "yt_id": (ep.get("youtube") or {}).get("id"), "ig_id": (ep.get("published") or {}).get("media_id"),
                     "fb_id": (ep.get("facebook") or {}).get("id"), "th_id": (ep.get("threads") or {}).get("id")})
    return rows


# --- YouTube -----------------------------------------------------------------------------------

def youtube(rows, notes):
    import youtube as yt
    if not yt.configured():
        return notes.append("YouTube: no credentials here.") or None
    token = yt._access_token()
    h = {"Authorization": f"Bearer {token}"}
    ch = http.get(f"{YT_API}/channels", params={"part": "statistics", "mine": "true"}, headers=h, timeout=30).json()
    st = (ch.get("items") or [{}])[0].get("statistics", {})
    channel = {"subscribers": int(st.get("subscriberCount", 0)), "views": int(st.get("viewCount", 0)),
               "videos": int(st.get("videoCount", 0))}
    ids = [r["yt_id"] for r in rows if r["yt_id"]]
    by_id = {r["yt_id"]: r for r in rows if r["yt_id"]}
    for i in range(0, len(ids), 50):
        js = http.get(f"{YT_API}/videos", params={"part": "statistics", "id": ",".join(ids[i:i + 50])}, headers=h, timeout=30).json()
        for v in js.get("items", []):
            s = v["statistics"]
            by_id[v["id"]]["yt"] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                                    "comments": int(s.get("commentCount", 0))}

    # Analytics API: retention, shares, subscribers. 403 = the token predates the yt-analytics scope.
    start = min((r["date"] for r in rows), default=today().isoformat())
    end = today().isoformat()
    def report(**p):
        r = http.get(YTA_API, params={"ids": "channel==MINE", "startDate": start, "endDate": end, **p}, headers=h, timeout=60)
        if r.status_code == 403:
            raise PermissionError("api off" if "has not been used" in r.text or "disabled" in r.text else "scope")
        r.raise_for_status()
        js = r.json()
        cols = [c["name"] for c in js.get("columnHeaders", [])]
        return [dict(zip(cols, row)) for row in js.get("rows", [])]
    daily = []
    try:
        if ids:
            for i in range(0, len(ids), 50):
                for row in report(dimensions="video", filters="video==" + ",".join(ids[i:i + 50]), sort="-views", maxResults=200,
                                  metrics="views,averageViewPercentage,averageViewDuration,shares,subscribersGained,estimatedMinutesWatched"):
                    by_id[row["video"]].setdefault("yt", {}).update(
                        {"avg_pct": round(row["averageViewPercentage"], 1), "avg_sec": row["averageViewDuration"],
                         "shares": row["shares"], "subs": row["subscribersGained"], "minutes": row["estimatedMinutesWatched"]})
        start = (today() - dt.timedelta(days=DAYS)).isoformat()
        daily = [{"date": r["day"], "views": r["views"], "subs": r["subscribersGained"] - r["subscribersLost"]}
                 for r in report(dimensions="day", metrics="views,subscribersGained,subscribersLost", sort="day")]
        countries = report(dimensions="country", metrics="views", sort="-views", maxResults=10)
        channel["countries"] = [{"country": r["country"], "views": r["views"]} for r in countries]
    except PermissionError as e:
        notes.append("YouTube retention needs the YouTube Analytics API switched on in Google Cloud (project All Saints → APIs → Enable)."
                     if str(e) == "api off" else
                     "YouTube retention, shares and subscribers need one more permission: run `pipeline.py yt-auth` again.")
    channel["daily"] = daily
    return channel


# --- Instagram ---------------------------------------------------------------------------------

IG_METRICS = "views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time"


def instagram(rows, notes):
    import instagram as ig
    try:
        tok = ig.get_token()
    except RuntimeError:
        return notes.append("Instagram: no token here (it lives in GitHub secrets).") or None
    acct = http.get(f"{ig.GRAPH}/me", params={"fields": "followers_count,media_count", "access_token": tok}, timeout=30).json()
    denied = False
    for r in rows:
        if not r["ig_id"]:
            continue
        js = http.get(f"{ig.GRAPH}/{r['ig_id']}/insights", params={"metric": IG_METRICS, "access_token": tok}, timeout=30).json()
        if "error" in js:
            denied = True
            f = http.get(f"{ig.GRAPH}/{r['ig_id']}", params={"fields": "like_count,comments_count", "access_token": tok}, timeout=30).json()
            r["ig"] = {"likes": f.get("like_count"), "comments": f.get("comments_count")}
            continue
        vals = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in js.get("data", [])}
        r["ig"] = {"views": vals.get("views"), "reach": vals.get("reach"), "likes": vals.get("likes"), "comments": vals.get("comments"),
                   "shares": vals.get("shares"), "saved": vals.get("saved"),
                   "avg_sec": round(vals["ig_reels_avg_watch_time"] / 1000, 1) if vals.get("ig_reels_avg_watch_time") else None}
    if denied:
        notes.append("Instagram views and shares need the insights permission on the token (only likes/comments shown).")
    return {"followers": acct.get("followers_count"), "posts": acct.get("media_count")}


# --- Facebook Page -----------------------------------------------------------------------------

def facebook(rows, notes):
    import facebook as fb
    if not fb.configured():
        return notes.append("Facebook: no Page token here.") or None
    page, tok = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    js = http.get(f"{fb.GRAPH}/{page}", params={"fields": "followers_count", "access_token": tok}, timeout=30).json()
    denied = False
    for r in rows:
        if not r["fb_id"] or denied:
            continue
        v = http.get(f"{fb.GRAPH}/{r['fb_id']}/video_insights", params={"metric": "blue_reels_play_count", "access_token": tok}, timeout=30).json()
        if "error" in v:
            denied = True
            continue
        vals = (v.get("data") or [{}])[0].get("values") or [{}]
        r["fb"] = {"plays": vals[0].get("value")}
    if denied:
        notes.append("Facebook Reel plays need the read_insights permission on the Page token (rerun `pipeline.py fb-auth` with it ticked).")
    return {"followers": js.get("followers_count")}


# --- Threads ----------------------------------------------------------------------------------

TH_METRICS = "views,likes,replies,reposts,quotes,shares"


def threads(rows, notes):
    import threads as th
    if not th.configured():
        return notes.append("Threads: not connected here.") or None
    tok = th.access_token()
    def get(path, **p):
        return http.get(f"{th.GRAPH}/{path}", params={**p, "access_token": tok}, timeout=30).json()
    js = get("me/threads_insights", metric="followers_count")
    if "error" in js:
        notes.append("Threads views and followers need the threads_manage_insights permission: add it to the Threads use case, "
                     "generate a new token (User Token Generator) and run `pipeline.py th-auth`.")
        return {"followers": None}
    followers = next((m.get("total_value", {}).get("value") for m in js.get("data", []) if m["name"] == "followers_count"), None)
    for r in rows:
        if not r["th_id"]:
            continue
        v = get(f"{r['th_id']}/insights", metric=TH_METRICS)
        if "error" not in v:
            r["th"] = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in v.get("data", [])}
    return {"followers": followers}


# --- TikTok ------------------------------------------------------------------------------------

TT_FIELDS = "id,title,video_description,create_time,view_count,like_count,comment_count,share_count"


def tiktok(rows, notes):
    import tiktok as tt
    if not tt.configured():
        return notes.append("TikTok: not connected here.") or None
    tok = tt.access_token()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    try:
        user = tt._check(http.get(f"{tt.API}/user/info/", params={"fields": "follower_count,likes_count,video_count"},
                                  headers=h, timeout=30), "user stats").get("user", {})
        vids, cursor = [], None
        for _ in range(10):  # 20 a page, newest first
            body = {"max_count": 20, **({"cursor": cursor} if cursor else {})}
            js = tt._check(http.post(f"{tt.API}/video/list/", params={"fields": TT_FIELDS}, json=body, headers=h, timeout=30), "video list")
            vids += js.get("videos", [])
            if not js.get("has_more"):
                break
            cursor = js.get("cursor")
    except RuntimeError as e:
        if "scope" not in str(e):
            raise
        notes.append("TikTok followers and views need two more scopes, user.info.stats and video.list: add them in the TikTok "
                     "developer app (Sandbox), then run `pipeline.py tt-auth` again.")
        return {"followers": None}
    used = set()
    def day(v):
        return dt.datetime.fromtimestamp(v["create_time"], tz()).date().isoformat()
    for by_name in (True, False):  # the saint's name in the caption first, then a video posted on the feast day
        for r in rows:
            if "tt" in r:
                continue
            name = r["saint"].lower()
            v = next((v for v in vids if v["id"] not in used and (
                name in f"{v.get('title', '')} {v.get('video_description', '')}".lower() if by_name else day(v) == r["date"])), None)
            if v:
                used.add(v["id"])
                r["tt"] = {"views": v.get("view_count"), "likes": v.get("like_count"), "comments": v.get("comment_count"),
                           "shares": v.get("share_count")}
    return {"followers": user.get("follower_count"), "likes": user.get("likes_count"), "videos": user.get("video_count")}


# --- Search Console ----------------------------------------------------------------------------

def search(notes):
    import youtube as yt
    if not env("GSC_REFRESH_TOKEN"):
        return notes.append("Search Console isn't connected yet: run `pipeline.py gsc-auth <client_secret.json>`.") or None
    r = http.post(yt.TOKEN_URL, data={"client_id": env("YT_CLIENT_ID", required=True), "client_secret": env("YT_CLIENT_SECRET", required=True),
                                      "refresh_token": env("GSC_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        return notes.append(f"Search Console token refresh failed: {r.text[:120]}") or None
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(GSC_SITE, safe='')}/searchAnalytics/query"
    start, end = (today() - dt.timedelta(days=DAYS)).isoformat(), today().isoformat()
    def q(dims, limit=1000):
        r = http.post(url, json={"startDate": start, "endDate": end, "dimensions": dims, "rowLimit": limit}, headers=h, timeout=60)
        if r.status_code == 403 and ("has not been used" in r.text or "disabled" in r.text):
            raise RuntimeError("the Google Search Console API is off in Google Cloud (project All Saints → APIs → Enable)")
        r.raise_for_status()
        return r.json().get("rows", [])
    out = {"daily": [{"date": x["keys"][0], "clicks": x["clicks"], "impressions": x["impressions"]} for x in q(["date"])]}
    for dim, limit in (("query", 15), ("page", 15), ("country", 8)):
        out[dim] = [{"key": x["keys"][0], "clicks": x["clicks"], "impressions": x["impressions"], "position": round(x["position"], 1)}
                    for x in q([dim], limit)]
    if not out["daily"]:
        notes.append("Search Console: no rows yet (Google shows data a few days after pages first appear in results).")
    return out


def collect():
    eps = list(load_episodes().values())
    notes, rows = [], episode_rows(eps)
    data = {"generated_at": dt.datetime.now(tz()).isoformat(timespec="minutes"), "timezone": load_config().get("timezone"),
            "pipeline": pipeline(eps), "episodes": rows, "notes": notes}
    for key, fn in (("youtube", lambda: youtube(rows, notes)), ("instagram", lambda: instagram(rows, notes)),
                     ("facebook", lambda: facebook(rows, notes)), ("threads", lambda: threads(rows, notes)),
                     ("tiktok", lambda: tiktok(rows, notes)), ("search", lambda: search(notes))):
        try:
            data[key] = fn()
        except Exception as e:  # one broken source never hides the others
            log(f"metrics {key}:", e)
            notes.append(f"{key.title()}: {str(e)[:160]}")
            data[key] = None
    for r in rows:
        r.pop("ig_id", None), r.pop("fb_id", None), r.pop("th_id", None)
    return data


def run(out=None):
    data = collect()
    if out:
        with open(out, "w") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        return print(f"Wrote {out}; notes: {data['notes']}")
    if not env("DASH_INGEST_KEY"):  # not set up yet: skip quietly rather than fail the job every night
        return log("Dashboard not set up (no DASH_INGEST_KEY); numbers not sent")
    r = http.post(env("DASH_INGEST_URL", INGEST_URL), json=data, timeout=60,
                  headers={"Authorization": f"Bearer {env('DASH_INGEST_KEY')}"})
    if r.status_code != 200:
        raise RuntimeError(f"dashboard ingest failed: {r.status_code} {r.text[:200]}")
    log(f"Dashboard updated ({len(data['episodes'])} episodes); notes: {data['notes']}")


def setup_key():
    """One-time: a fresh DASH_INGEST_KEY in .env, GitHub (Production) and Cloudflare Pages. Never printed."""
    import secrets, shutil, subprocess
    from common import ROOT
    key = secrets.token_urlsafe(32)
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text().splitlines() if envf.exists() else []) if not l.startswith("DASH_INGEST_KEY=")]
    envf.write_text("\n".join(lines + [f"DASH_INGEST_KEY={key}"]) + "\n")
    print("Saved DASH_INGEST_KEY to .env")
    if shutil.which("gh"):
        subprocess.run(["gh", "secret", "set", "DASH_INGEST_KEY", "--env", "Production"], input=key, text=True, check=True, cwd=ROOT)
        print("Set it as a GitHub secret (environment: Production).")
    r = subprocess.run(["npx", "--yes", "wrangler", "pages", "secret", "put", "DASH_INGEST_KEY", "--project-name", "allholysaints"],
                       input=key, text=True, cwd=ROOT / "site")
    print("Set it in Cloudflare Pages (redeploy to apply)." if r.returncode == 0 else
          "Cloudflare didn't take it (run `npx wrangler login` in site/, then this again).")
