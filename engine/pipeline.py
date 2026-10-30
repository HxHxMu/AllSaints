"""All Saints pipeline CLI.

  python engine/pipeline.py generate [--date YYYY-MM-DD] [--max N] [--no-upload]
  python engine/pipeline.py poll            # Telegram updates + publish due episodes
  python engine/pipeline.py refresh-token
  python engine/pipeline.py youtube <episode>  # upload one episode's Short now
  python engine/pipeline.py yt-auth <client_secret.json>
  python engine/pipeline.py build-calendar
"""
import argparse, datetime as dt, json, re, shutil, sys, traceback, unicodedata
from pathlib import Path
from common import (BRAND, WORK, log, load_config, load_episodes, load_episode, save_episode, today, tz, month_day_label)

CAP = BRAND["caption"]


def _fold(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def saint_tags(s, n=2):
    """The saint's own tags: the name tag, then the first tag that isn't another spelling of the name."""
    tags = [t if t.startswith("#") else "#" + t for t in (s.get("hashtags") or [])]
    names = [w for w in re.findall(r"[a-z]{4,}", _fold(s["saint"]["name"])) if w not in ("saint", "saints")]
    out = tags[:1]
    for t in tags[1:]:
        if len(out) >= n:
            break
        if not any(w in _fold(t) for w in names) and t.lower() not in (x.lower() for x in CAP["hashtags_base"]):
            out.append(t)
    return out


def ig_hashtags(s):
    tags = [CAP["hashtag_brand"]] + CAP["hashtags_base"] + saint_tags(s)
    return list(dict.fromkeys(tags))[:CAP.get("hashtags_max", 5)]


def pick_cta(ep):
    """Rotate caption CTAs by date; the script's own share line (name/patron) joins the rotation."""
    s = ep["script"]
    opts = ([s["share_cta"].strip()] if s.get("share_cta", "").strip() else []) + CAP["ctas"]
    try:
        k = dt.date.fromisoformat(ep["date"]).toordinal()
    except (KeyError, ValueError):
        k = 0
    return opts[k % len(opts)].format(feast=s["saint"].get("feast", "feast day"), display_name=s["saint"].get("display_name", s["saint"]["name"]))


def build_caption(ep):
    s = ep["script"]
    saint = s["saint"]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    tags = ig_hashtags(s)
    if ep.get("caption_hook_override"):
        body = ep["caption_hook_override"].strip()
    else:
        body = f"{s.get('caption_hook', '').strip()}\n\n{saint['name']} · Feast day: {saint.get('feast', '')}\n{s.get('summary', '').strip()}\n\n{prayer} 🕯"
    srcs = " · ".join(x["title"].split(":")[0] if x["title"].startswith("Wikipedia") else "Catholic Encyclopedia (1913)" for x in ep.get("sources", []))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", [])))
    cap = f"{body}\n\n{pick_cta(ep)}\n\n—\nSources: {srcs}\nArt: {credits or 'public domain'}\n\n{' '.join(tags)}"
    return cap[:2150]


def build_art(ep_id, saint, final, work):
    """Art per beat: Luis's overrides in art/<ep_id>/ first, then icon illustrations (default) or Commons art.
    Returns ({beat_index|'cover'|'close': art}, credit lines)."""
    import illustrate
    art_map = illustrate.overrides(ep_id, work)
    credits = ["Additional artwork: All Saints"] if art_map else []
    if load_config().get("art_source", "illustrated") == "illustrated":
        painted = illustrate.illustrate(saint, final, work, skip=set(art_map))
        if painted:
            credits.append(illustrate.ILL["credit"])
        art_map = {**painted, **art_map}
        beats = sorted(k for k in art_map if isinstance(k, int))
        if beats:
            art_map.setdefault("cover", dict(art_map[beats[0]]))
            art_map.setdefault("close", dict(art_map[beats[-1]]))
        return art_map, credits
    commons_map, commons_credits = commons_art(saint, final, work)
    return {**commons_map, **art_map}, credits + commons_credits


def commons_art(saint, final, work):
    """Find, pick and download Wikimedia Commons art (art_source: "commons")."""
    import art
    cands = art.collect_candidates(saint, final)
    log(f"{len(cands)} art candidates")
    art_map, credits = {}, []
    if cands:
        usable, pick = art.assign_art(saint, final, cands)
        files = {}
        for k, sel in [(b["i"], b) for b in pick.get("beats", [])] + [("cover", pick.get("cover")), ("close", {"image": pick.get("close_bg")})]:
            if not sel or sel.get("image") is None or not (0 <= int(sel["image"]) < len(usable)):
                continue
            c = usable[int(sel["image"])]
            fn = work / f"art{int(sel['image'])}.jpg"
            if fn.name not in files:
                files[fn.name] = art.download(c["thumb"], fn, c.get("url"))
            w, h = files[fn.name]
            art_map[k] = {"image": fn, "w": w, "h": h, "focus": sel.get("focus") or {"x": 0.5, "y": 0.35},
                          "move": sel.get("move", "in"), "credit": f"{c['name']} — {c['artist'] or 'Unknown artist'}"[:80]}
            if k not in ("cover", "close"):
                credits.append(art.credit_line(c))
    return art_map, credits


MAX_REJECTS = 3  # saints per date the fact-check may reject before the episode fails


class GiveUp(RuntimeError):
    """A failure that retrying on the next run won't fix; waits for /generate."""


def generate_one(date: dt.date, upload=True, usage_start=None):
    import common, research, script as scriptmod, tts, render, music
    usage_start = len(common.USAGE) if usage_start is None else usage_start
    ep_id = date.isoformat()
    ep = load_episode(ep_id) or {"id": ep_id, "date": ep_id}
    redo = ep.get("redo") or {}
    note = redo.get("note")
    exclude = [ep["saint"]["qid"]] if redo.get("new_saint") and ep.get("saint", {}).get("qid") else []
    exclude += [r["qid"] for r in ep.get("rejected", [])]  # saints the fact-check turned down for this date
    prev_status = ep.get("status")
    ep["status"] = "generating"
    save_episode(ep)
    work = WORK / ep_id
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        if ep.get("saint_pick") and not redo.get("new_saint") and prev_status == "redo_requested":
            saint = ep["saint_pick"]
        else:
            saint = research.select_saint(date, exclude=exclude)
        sources = research.gather_sources(saint)
        draft = scriptmod.write_script(saint, sources, date, note=note)
        fc = scriptmod.fact_check(draft, sources)
        if fc.get("verdict") == "reject":
            ep.setdefault("rejected", []).append({"qid": saint["qid"], "name": saint["name"], "note": fc.get("reviewer_note")})
            if len(ep["rejected"]) >= MAX_REJECTS:  # don't keep paying for scripts on a date with no good candidate
                raise GiveUp(f"Fact-check rejected {len(ep['rejected'])} saints for this date: "
                                   + ", ".join(r["name"] for r in ep["rejected"]))
            log("Fact-check rejected saint; choosing another")
            ep["saint"] = {"qid": saint["qid"], "name": saint["name"]}
            ep["redo"] = {"new_saint": True}
            ep["status"] = "redo_requested"
            save_episode(ep)
            return generate_one(date, upload, usage_start)
        if fc.get("verdict") == "fixed" and not fc.get("script"):
            log("Fact-check said 'fixed' but returned no script; keeping the draft")
        final = fc.get("script") or draft
        final["saint"]["feast"] = month_day_label(date)
        final["saint"].setdefault("display_name", final["saint"]["name"].replace("Saint ", "St. ").replace("Saints ", "Sts. "))
        try:  # the website's Spanish edition; never blocks the video
            es = scriptmod.translate_es(final) if final.get("story") else None
        except Exception as e:
            log("Spanish translation failed:", e)
            es = None
        art_map, credits = build_art(ep_id, saint, final, work)
        icon = art_map.get("cover", {}).get("image")  # clean art (no title) for the website
        # narration
        t = tts.synthesize(final, work)
        bed = music.pick_bed(ep_id)
        rel = render.stage_assets(ep_id, {"voice": t["voice"], "music": bed, **{f"img_{a['image'].name}": a["image"] for a in art_map.values()}})
        for k, a in art_map.items():
            a["image"] = rel[f"img_{a['image'].name}"]
        props = render.build_props(ep_id, final, t, art_map, rel["music"])
        props["voice"] = rel["voice"]
        out = render.render(ep_id, props, work)
        ep.update({
            "saint": {"qid": saint["qid"], **final["saint"]},
            "saint_pick": {k: v for k, v in saint.items() if k != "intro"},
            "script": final,
            "factcheck": {k: fc.get(k) for k in ("verdict", "issues", "confidence", "reviewer_note")},
            "usage": common.USAGE[usage_start:],
            "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
            "art_credits": credits,
            "duration": round(t["voiceDuration"] + 3.8, 1),
            "narrator": t["narrator"],
        })
        if es:
            ep["es"] = es
        ep["caption"] = build_caption(ep)
        ep.pop("redo", None)
        ep.pop("error", None)
        ep["attempts"] = 0
        ep.pop("caption_hook_override", None)
        if upload:
            import storage, telegram
            urls = storage.upload(f"ep-{ep_id}", {"video.mp4": out["video"], "cover.jpg": out["cover"], "preview.mp4": out["preview"],
                                                      **({"art.jpg": icon} if icon else {})},
                                  name=f"{ep_id} · {final['saint']['name']}", body=ep["caption"])
            ep["assets"] = urls
            ep["status"] = "review"
            save_episode(ep)
            try:
                ep["review_message_id"] = telegram.send_review(ep)
            except Exception as e:  # the episode is done and uploaded; the poll re-sends missing reviews
                log("Telegram review not sent:", e)
        else:
            ep["status"] = "review"
            ep["local"] = {k: str(v) for k, v in out.items()}
        save_episode(ep)
        log(f"✔ {ep_id} {final['saint']['name']} ready for review")
        return ep
    except Exception as e:
        traceback.print_exc()
        ep["status"] = "failed"
        ep["attempts"] = 3 if isinstance(e, GiveUp) else ep.get("attempts", 0) + 1
        ep["error"] = f"{type(e).__name__}: {e}"[:500]
        save_episode(ep)
        try:
            import telegram
            telegram.send(f"❌ Episode {ep_id} failed ({ep['attempts']}/3): {ep['error']}" + ("\nWill retry next run." if ep["attempts"] < 3 else "\nGiving up – tap /generate after fixing."))
        except Exception:
            pass
        return ep


def dates_needing_work():
    cfg = load_config()
    eps = load_episodes()
    start = today() + dt.timedelta(days=1)
    if cfg.get("launch_date"):
        start = max(start, dt.date.fromisoformat(cfg["launch_date"]))
    want = [start + dt.timedelta(days=i) for i in range(cfg["days_ahead"])]
    redo = sorted(dt.date.fromisoformat(e["date"]) for e in eps.values() if (e["status"] in ("redo_requested", "generating") or (e["status"] == "failed" and e.get("attempts", 0) < 3)) and e["date"] >= today().isoformat())
    missing = [d for d in want if d.isoformat() not in eps]
    return list(dict.fromkeys(redo + missing))


def cmd_generate(a):
    cfg = load_config()
    if a.date:
        generate_one(dt.date.fromisoformat(a.date), upload=not a.no_upload)
        return
    todo = dates_needing_work()[: (a.max or cfg["max_generate_per_run"])]
    log("To generate:", [d.isoformat() for d in todo])
    for d in todo:
        generate_one(d, upload=not a.no_upload)


def publish_due():
    import telegram
    cfg = load_config()
    now = dt.datetime.now(tz())
    if cfg.get("paused") or not cfg.get("launch_date") or now.date() < dt.date.fromisoformat(cfg["launch_date"]):
        return
    hh, mm = map(int, cfg["post_time"].split(":"))
    due_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    ep = load_episode(now.date().isoformat())
    if not ep:
        return
    if ep["status"] == "review" and now >= due_time - dt.timedelta(hours=2) and not ep.get("reminded"):
        telegram.send(f"⏰ Today's episode ({ep['saint']['display_name']}) still needs approval – it posts at {cfg['post_time']}.")
        ep["reminded"] = True
        save_episode(ep)
    if ep["status"] == "publishing":
        # a job killed mid-upload leaves "publishing" behind; after 30 min treat it as a failed attempt
        started = dt.datetime.fromisoformat(ep.get("updated", now.isoformat()))
        if now - started > dt.timedelta(minutes=30):
            ep["status"] = "approved"
    if ep["status"] == "published":
        publish_youtube(ep)  # retries a Short that failed after the Reel went out
        youtube_playlists(ep)
        return
    if ep["status"] != "approved" or now < due_time:
        return
    try:
        publish_episode(ep)
    except Exception:
        pass  # logged + reported to Telegram; retried on the next poll


def publish_episode(ep):
    """Post one episode's Reel now, then its YouTube Short (used by the daily schedule and `pipeline.py publish <id>`)."""
    import instagram, storage, telegram
    now = dt.datetime.now(tz())
    log("Publishing", ep["id"])
    ep["status"] = "publishing"
    save_episode(ep)
    try:
        vid = WORK / f"{ep['id']}-video.mp4"
        storage.download(ep["assets"]["video.mp4"], vid)
        video_url = storage.resolve_direct(ep["assets"]["video.mp4"])
        cover_url = storage.resolve_direct(ep["assets"]["cover.jpg"])
        res = instagram.publish_reel(ep["caption"], video_url=video_url, cover_url=cover_url, video_path=vid)
        ep.update(status="published", published=res, published_at=now.isoformat(timespec="minutes"))
        save_episode(ep)
        telegram.send(f"📣 Posted: {ep['saint']['display_name']}\n{res.get('permalink', '')}")
    except Exception as e:
        traceback.print_exc()
        publish_youtube(ep)  # a Reel failure shouldn't hold the Short back
        ep["status"] = "approved"
        ep["publish_error"] = str(e)[:500]
        ep["publish_attempts"] = ep.get("publish_attempts", 0) + 1
        save_episode(ep)
        if ep["publish_attempts"] in (1, 3):
            telegram.send(f"❌ Publishing failed ({ep['publish_attempts']}x): {str(e)[:300]}\nWill retry.")
        raise
    publish_youtube(ep, vid)


def publish_youtube(ep, video=None):
    """Upload the episode as a YouTube Short once; independent of Instagram, max 3 attempts."""
    import youtube, storage, telegram
    yt = ep.get("youtube") or {}
    if not youtube.configured() or yt.get("id") or yt.get("attempts", 0) >= 3 or not ep.get("assets"):
        return
    try:
        if not video:
            video = storage.download(ep["assets"]["video.mp4"], WORK / f"{ep['id']}-video.mp4")
        res = youtube.upload_short(ep, video)
        ep["youtube"] = {**res, "published_at": dt.datetime.now(tz()).isoformat(timespec="minutes")}
        save_episode(ep)
        note = "" if res["privacy"] == "public" else f" ({res['privacy']}: publish it in YouTube Studio)"
        telegram.send(f"▶️ On YouTube{note}: {ep['saint']['display_name']}\n{res['url']}")
        youtube_playlists(ep)
    except Exception as e:
        traceback.print_exc()
        yt["attempts"] = yt.get("attempts", 0) + 1
        yt["error"] = str(e)[:500]
        ep["youtube"] = yt
        save_episode(ep)
        if yt["attempts"] in (1, 3):
            telegram.send(f"❌ YouTube upload failed ({yt['attempts']}x): {str(e)[:300]}" + ("\nWill retry." if yt["attempts"] < 3 else ""))


def youtube_playlists(ep):
    """Put a published Short in its month + continent playlists; max 3 attempts, never blocks anything else."""
    import youtube, telegram
    yt = ep.get("youtube") or {}
    if not youtube.configured() or not yt.get("id") or yt.get("playlists_done") or yt.get("playlist_attempts", 0) >= 3:
        return
    try:
        yt["playlists"] = yt.get("playlists", []) + youtube.add_to_playlists(ep, done=yt.get("playlists", []))
        yt["playlists_done"] = True
        yt.pop("playlist_error", None)
        log("Playlists:", ", ".join(yt["playlists"]))
    except Exception as e:
        traceback.print_exc()
        yt["playlist_attempts"] = yt.get("playlist_attempts", 0) + 1
        yt["playlist_error"] = str(e)[:300]
        if yt["playlist_attempts"] == 1:
            hint = "\nRerun `pipeline.py yt-auth` once (playlists need a new permission)." if "403" in str(e) else ""
            telegram.send(f"⚠️ Couldn't add {ep['saint']['display_name']} to playlists: {str(e)[:200]}{hint}")
    ep["youtube"] = yt
    save_episode(ep)


def cmd_poll(a):
    import telegram, storage
    actions = telegram.process_updates()
    telegram.resend_missing_reviews()
    if "generate" in actions:
        storage.dispatch_workflow("generate.yml")
    publish_due()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--date")
    g.add_argument("--max", type=int)
    g.add_argument("--no-upload", action="store_true")
    sub.add_parser("poll")
    pb = sub.add_parser("publish")
    pb.add_argument("episode", help="episode id, e.g. 2026-10-29 or intro")
    yb = sub.add_parser("youtube")
    yb.add_argument("episode")
    ya = sub.add_parser("yt-auth")
    ya.add_argument("client_secret", help="OAuth client JSON downloaded from Google Cloud (Desktop app)")
    sub.add_parser("yt-whoami")
    yp = sub.add_parser("yt-playlists", help="add published Shorts to their playlists (backfill / retry)")
    yp.add_argument("episode", nargs="?", default="all")
    sub.add_parser("refresh-token")
    sub.add_parser("build-calendar")
    sub.add_parser("whoami")
    a = p.parse_args()
    if a.cmd == "generate":
        cmd_generate(a)
    elif a.cmd == "poll":
        cmd_poll(a)
    elif a.cmd == "publish":
        ep = load_episode(a.episode)
        if not ep or ep.get("status") not in ("approved", "review") or not ep.get("assets"):
            raise SystemExit(f"Episode {a.episode} not found, already published, or not uploaded")
        publish_episode(ep)
    elif a.cmd == "youtube":
        ep = load_episode(a.episode)
        if not ep or not ep.get("assets"):
            raise SystemExit(f"Episode {a.episode} not found or not uploaded")
        (ep.get("youtube") or {}).pop("attempts", None)
        publish_youtube(ep)
    elif a.cmd == "yt-auth":
        import youtube
        youtube.authorize(a.client_secret)
    elif a.cmd == "yt-playlists":
        eps = [load_episode(a.episode)] if a.episode != "all" else load_episodes().values()
        for ep in eps:
            if ep and (ep.get("youtube") or {}).get("id"):
                ep["youtube"].pop("playlist_attempts", None)
                youtube_playlists(ep)
    elif a.cmd == "yt-whoami":
        import youtube
        print(youtube.me())
    elif a.cmd == "refresh-token":
        import instagram
        instagram.refresh_token()
    elif a.cmd == "build-calendar":
        import calendar_build
        calendar_build.main()
    elif a.cmd == "whoami":
        import instagram
        print(instagram.me())


if __name__ == "__main__":
    main()
