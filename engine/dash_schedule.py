"""Every scheduled post in one list, for the dashboard's schedule (metrics.collect, nightly). No AI, state only.

Sources: the daily saints (state/episodes, at config post_time, plus the nightly Story card at story_time),
state/shares.json and state/stories.json (Lives of the Saints, sung prayers, seasonal cards, music Stories), the
weekly music Story projected for Sundays not queued yet (story_music's own skip rule and rotation), and the monthly
compilation (last day of the month). Entries for one post on several platforms (same base id and day) merge into one item.

Item: {id, at, date, kind, title, status, platforms: [{p, s, url?}], cover?}
  kind: saint | lives | sung | music | seasonal | compilation
  status / platform s: posted | pending | approved | review | waiting | failed | missing | planned | skipped | draft
Warnings: {date, text}: days without a saint, saints not approved close to their day, two posts of different
items on one platform the same day, overdue or failing posts, release files that don't answer (next 21 days).
"""
import datetime as dt, re
from common import http, load_config, load_json, log, tz

PAST, FUTURE_SAINTS = 14, 8          # days of history; days ahead a saint is expected
PLATS = ("instagram", "youtube", "facebook", "threads", "tiktok", "story")  # story = IG Story; fb_story = FB Page Story
SUFFIX = re.compile(r"-(youtube|instagram|facebook|facebook_video|facebook_reel|tiktok|story)$")
SHARE_PLAT = {"instagram": "instagram", "youtube": "youtube", "facebook": "facebook", "facebook_video": "facebook",
              "facebook_reel": "facebook", "tiktok": "tiktok"}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _at(day, hm):
    h, m = map(int, hm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m), tz())


def _iso(t):
    return t.astimezone(tz()).isoformat(timespec="minutes")


def _ep_platforms(ep):
    ig, yt, fb = ep.get("published") or {}, ep.get("youtube") or {}, ep.get("facebook") or {}
    th, tt, st = ep.get("threads") or {}, ep.get("tiktok") or {}, ep.get("story") or {}
    def one(p, done, d, url=None, ok="posted"):
        s = ok if done else ("failed" if d.get("error") and d.get("attempts", 0) >= 3 else
                             "waiting" if d.get("error") else "pending")
        return {"p": p, "s": s, **({"url": url} if done and url else {})}
    return [one("instagram", ig.get("media_id"), ig, ig.get("permalink")), one("youtube", yt.get("id"), yt, yt.get("url")),
            one("facebook", fb.get("id"), fb, fb.get("url")), one("threads", th.get("id"), th, th.get("url")),
            one("tiktok", tt.get("publish_id"), tt, ok="draft"), one("story", st.get("media_id"), st, st.get("permalink"))]


def saints(eps, cfg, t):
    items, have = [], set()
    for ep in eps:
        if not (ep["id"][:4].isdigit() and ep.get("saint_pick") is not None):
            continue
        d = dt.date.fromisoformat(ep["date"])
        if d < t - dt.timedelta(days=PAST):
            continue
        have.add(ep["date"])
        st = ep["status"]
        plats = _ep_platforms(ep) if st in ("publishing", "published") else [{"p": p, "s": "pending"} for p in PLATS]
        items.append({"id": ep["id"], "at": _iso(_at(d, cfg.get("post_time", "07:30"))), "date": ep["date"], "kind": "saint",
                      "title": ep["saint"]["name"], "status": {"publishing": "pending", "redo_requested": "review",
                                                               "generating": "pending"}.get(st, st),
                      "platforms": plats, "cover": (ep.get("assets") or {}).get("cover.jpg"),
                      "slug": ep.get("slug") if st == "published" else None})
    for i in range(FUTURE_SAINTS):
        d = t + dt.timedelta(days=i)
        if d.isoformat() not in have:
            items.append({"id": d.isoformat(), "at": _iso(_at(d, cfg.get("post_time", "07:30"))), "date": d.isoformat(),
                          "kind": "saint", "title": None, "status": "missing", "platforms": []})
    return items


def _kind(base):
    if base.startswith("lots-"):
        return "lives"
    if base.startswith("music-") or "blue-chant" in base:
        return "music"
    if base.startswith("o-antiphons"):
        return "seasonal"
    return "sung"


def _title(base, entries, named):
    if base in named:
        return named[base]
    for e in entries:
        if e.get("title"):
            return e["title"]
    if base.startswith("music-"):
        e = entries[0]
        return f"Music: {e['track']} ({e.get('album', '')})" if e.get("track") else "Music Story"
    if base.startswith("o-antiphons"):
        return f"O Antiphons · Dec {base.rsplit('-', 1)[-1]}"
    if base.startswith("lots-"):
        parts = base[5:].split("-")
        what = parts[-1]
        what = f"Part {what[4:]}" if what.startswith("part") else what.title()
        return f"Lives of the Saints · {' '.join(parts[:-1]).title()} · {what}"
    return " ".join(base.split("-")).title()


def _entry_state(e, now):
    if e.get("status") == "posted":
        return "posted"
    if e.get("status") in ("skipped", "draft"):
        return e["status"]
    if e.get("attempts", 0) >= 3 or e.get("status") == "failed":
        return "failed"
    return "waiting" if e.get("error") else "pending"


def queued(shares, stories, now, t):
    """shares.json + stories.json, merged by (base id, day)."""
    groups = {}
    for src, rows in (("share", shares), ("story", stories)):
        for e in rows:
            at = dt.datetime.fromisoformat(e["at"])
            if at.astimezone(tz()).date() < t - dt.timedelta(days=PAST):
                continue
            base = SUFFIX.sub("", e["id"])
            groups.setdefault((base, at.astimezone(tz()).date().isoformat()), []).append((src, e, at))
    named = {SUFFIX.sub("", e["id"]): e["title"] for e in shares + stories if e.get("title")}
    items = []
    for (base, day), rows in groups.items():
        plats, entries = [], [e for _, e, _ in rows]
        for src, e, _ in rows:
            s = _entry_state(e, now)
            posted = e.get("posted") or {}
            if src == "share":
                p = SHARE_PLAT.get(e["platform"], e["platform"])
                url = posted.get("permalink") or posted.get("url") or (f"https://youtu.be/{posted['id']}" if p == "youtube" and posted.get("id") else None)
                plats.append({"p": p, "s": "draft" if p == "tiktok" and s == "posted" else s, **({"url": url} if url else {})})
            else:
                plats.append({"p": "story", "s": s, **({"url": posted["permalink"]} if posted.get("permalink") else {})})
                if e.get("facebook_video") or e.get("image"):
                    fb = e.get("facebook") or {}
                    plats.append({"p": "fb_story", "s": "posted" if fb.get("id") else ("skipped" if s == "skipped" else "pending")})
                if base.startswith("music-") and e.get("video") and day >= "2026-11-15":
                    yt = e.get("youtube") or {}
                    plats.append({"p": "youtube", "s": "posted" if yt.get("id") else
                                  ("failed" if yt.get("attempts", 0) >= 3 else "skipped" if s == "skipped" else "pending"),
                                  **({"url": yt["url"]} if yt.get("url") else {})})
        states = {x["s"] for x in plats}
        status = ("skipped" if states == {"skipped"} else "failed" if "failed" in states else "draft" if "draft" in states and states <= {"draft", "skipped"}
                  else "posted" if states <= {"posted", "draft", "skipped"} else "partial" if "posted" in states else
                  "waiting" if "waiting" in states else "pending")
        at = min(a for _, _, a in rows)
        item = {"id": f"{base}@{day}", "at": _iso(at), "date": day, "kind": _kind(base), "title": _title(base, entries, named),
                "status": status, "platforms": plats,
                "videos": sorted({u for e in entries if e.get("status") not in ("posted", "skipped")
                                  for u in (e.get("video"), e.get("cover"), e.get("image")) if u})}
        if base.startswith("music-") and entries[0].get("reason"):
            item["note"] = entries[0]["reason"]
        items.append(item)
    return items


def music_projection(stories, cfg, t, until):
    """Sundays from today to `until` with no music entry yet: what story_music would do (track or the reason it stands aside)."""
    when = cfg.get("music_story", "Sun 15:00")
    if not when:
        return []
    try:
        import story_music
    except Exception as e:  # needs Pillow; the dashboard simply goes without the projection
        log("schedule: music projection off:", e)
        return []
    wday, hm = when.split()
    have = {x["id"] for x in stories}
    items, d = [], t
    while d <= until:
        if d.strftime("%a") == wday and f"music-{d}" not in have:
            why = story_music._why_not(d, stories)
            item = {"id": f"music-{d}@{d}", "at": _iso(_at(d, hm)), "date": d.isoformat(), "kind": "music",
                    "status": "skipped" if why else "planned", "platforms": []}
            if why:
                item.update(title="Music Story", note=why)
            else:
                album, n = story_music._music_pick(d, stories)
                item["title"] = f"Music: {album['tracks'][n - 1]} ({album['title']})"
                item["platforms"] = [{"p": "story", "s": "planned"}, {"p": "fb_story", "s": "planned"}, {"p": "youtube", "s": "planned"}]
            items.append(item)
            stories = stories + [{"id": f"music-{d}", "at": item["at"], "status": "skipped" if why else "pending"}]
        d += dt.timedelta(days=1)
    return items


def compilations(cfg, t, until):
    from common import STATE
    import json
    items, first = [], cfg.get("compilation_from")
    if not first:
        return items
    m = dt.date(t.year, t.month, 1) - dt.timedelta(days=PAST + 31)
    m = m.replace(day=1)
    while m <= until:
        nxt = (m + dt.timedelta(days=32)).replace(day=1)
        last = nxt - dt.timedelta(days=1)
        key = m.strftime("%Y-%m")
        if key >= first and t - dt.timedelta(days=PAST) <= last:
            p = STATE / "compilations" / f"{key}.json"
            comp = json.loads(p.read_text()) if p.exists() else {}
            yt = comp.get("youtube") or {}
            s = ("posted" if yt.get("privacy") == "public" else "review" if yt.get("id") else
                 "failed" if comp.get("attempts", 0) >= 3 else "planned")
            items.append({"id": f"compilation-{key}", "at": _iso(_at(last, "10:07")), "date": last.isoformat(),
                          "kind": "compilation", "title": f"Saints of {m.strftime('%B')} (monthly compilation)",
                          "status": s, "platforms": [{"p": "youtube", "s": s, **({"url": yt["url"]} if yt.get("url") else {})}]})
        m = nxt
    return items


def _url_ok(url):
    try:
        r = http.head(url, allow_redirects=True, timeout=20)
        return r.status_code < 400
    except Exception:
        return False


def warnings(items, eps, now, t, check_files=True):
    out = []
    by_id = {e["id"]: e for e in eps}
    for it in items:
        d = dt.date.fromisoformat(it["date"])
        at = dt.datetime.fromisoformat(it["at"])
        if it["kind"] == "saint":
            if it["status"] == "missing" and d <= t + dt.timedelta(days=6):  # generate makes the 8th day each morning
                out.append({"date": it["date"], "text": "No saint made for this day yet."})
            elif it["status"] in ("review", "failed") and t <= d <= t + dt.timedelta(days=2):
                out.append({"date": it["date"], "text": f"{it['title']}: {'failed' if it['status'] == 'failed' else 'still waiting for your Approve'}."})
        if it["status"] in ("pending", "waiting", "approved", "partial") and at < now - dt.timedelta(hours=2) and it["kind"] != "compilation":
            late = [x["p"] for x in it["platforms"] if x["s"] in ("pending", "waiting")]
            if late:
                out.append({"date": it["date"], "text": f"{it['title'] or it['id']}: due {at.strftime('%-I:%M %p')}, not posted on {', '.join(late)}."})
        for x in it["platforms"]:
            if x["s"] == "failed":
                out.append({"date": it["date"], "text": f"{it['title'] or it['id']}: {x['p']} failed 3 times."})
        if it["status"] == "draft" and it["kind"] != "saint" and d >= t:
            out.append({"date": it["date"], "text": f"{it['title']}: a draft, waiting for your OK in chat."})
        if it["kind"] == "compilation" and it["status"] == "review":
            out.append({"date": it["date"], "text": f"{it['title']}: uploaded private, waiting for your Publish tap."})
    # two different items on one platform the same day (the daily saint and Stories don't count)
    seen = {}
    for it in items:
        if it["kind"] in ("saint", "compilation") or it["status"] == "skipped":  # a compilation uploads private
            continue
        for x in it["platforms"]:
            if x["p"] not in ("story", "fb_story") and x["s"] != "skipped":
                seen.setdefault((it["date"], x["p"]), []).append(it["title"])
    for (d, p), titles in sorted(seen.items()):
        if len(set(titles)) > 1 and d >= t.isoformat():
            out.append({"date": d, "text": f"Two posts on {p} the same day: {' / '.join(sorted(set(titles)))}."})
    if check_files:
        soon = t + dt.timedelta(days=21)
        urls = {}
        for it in items:
            d = dt.date.fromisoformat(it["date"])
            if t <= d <= soon and it["status"] not in ("posted", "skipped"):
                vids = list(it.get("videos") or [])
                if it["kind"] == "saint" and it["status"] in ("approved", "review"):
                    vids.append((by_id.get(it["id"], {}).get("assets") or {}).get("video.mp4"))
                for u in filter(None, vids):
                    urls.setdefault(u, it)
        bad = [(u, it) for u, it in urls.items() if u.startswith("http") and not _url_ok(u)]
        for u, it in bad:
            out.append({"date": it["date"], "text": f"{it['title'] or it['id']}: file not found ({u.rsplit('/', 2)[-2]}/{u.rsplit('/', 1)[-1]})."})
    return sorted(out, key=lambda w: w["date"])


def collect(eps, check_files=True):
    cfg, now = load_config(), dt.datetime.now(tz())
    t = now.date()
    shares, stories = load_json("shares.json", []), load_json("stories.json", [])
    items = saints(eps, cfg, t) + queued(shares, stories, now, t)
    until = max([dt.date.fromisoformat(i["date"]) for i in items] + [t + dt.timedelta(days=60)])
    items += music_projection(stories, cfg, t, until) + compilations(cfg, t, until)
    items.sort(key=lambda i: (i["at"], i["kind"] != "saint"))
    warn = warnings(items, eps, now, t, check_files)
    for it in items:
        it.pop("videos", None)
    return {"items": items, "warnings": warn, "post_time": cfg.get("post_time", "07:30"),
            "story_time": cfg.get("story_time", "20:30")}


if __name__ == "__main__":  # local check: python engine/dash_schedule.py
    import json
    from common import load_episodes
    data = collect(list(load_episodes().values()), check_files=False)
    for i in data["items"]:
        print(i["at"][:16], f"{i['kind']:<11} {i['status']:<8}", i["title"], " ".join(f"{p['p']}:{p['s']}" for p in i["platforms"]), i.get("note", ""))
    print(json.dumps(data["warnings"], indent=1))
