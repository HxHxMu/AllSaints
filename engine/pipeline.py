"""All Saints pipeline CLI.

  python engine/pipeline.py generate [--date YYYY-MM-DD] [--max N] [--no-upload]
  python engine/pipeline.py poll            # Telegram updates + publish due episodes
  python engine/pipeline.py refresh-token
  python engine/pipeline.py build-calendar
"""
import argparse, datetime as dt, json, shutil, sys, traceback
from pathlib import Path
from common import (BRAND, WORK, log, load_config, load_episodes, load_episode, save_episode, today, tz, month_day_label)

BASE_TAGS = BRAND["caption"]["hashtags_base"]


def build_caption(ep):
    s = ep["script"]
    saint = s["saint"]
    prayer = next((b["text"] for b in s["beats"] if b["role"] == "close"), f"{saint['name']}, pray for us.")
    tags = list(dict.fromkeys([t if t.startswith("#") else "#" + t for t in (s.get("hashtags") or [])] + BASE_TAGS))[:22]
    if ep.get("caption_hook_override"):
        body = ep["caption_hook_override"].strip()
    else:
        body = f"{s.get('caption_hook', '').strip()}\n\n{saint['name']} · Feast day: {saint.get('feast', '')}\n{s.get('summary', '').strip()}\n\n{prayer} 🕯"
    srcs = " · ".join(x["title"].split(":")[0] if x["title"].startswith("Wikipedia") else "Catholic Encyclopedia (1913)" for x in ep.get("sources", []))
    credits = "; ".join(dict.fromkeys(ep.get("art_credits", [])))
    cap = f"{body}\n\n—\nSources: {srcs}\nArt: {credits or 'public domain'}\n\n{' '.join(tags)}"
    return cap[:2150]


def build_art(saint, final, work):
    """Find, pick and download art; returns ({beat_index|'cover'|'close': art}, credit lines)."""
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


def generate_one(date: dt.date, upload=True):
    import research, script as scriptmod, tts, render, music
    ep_id = date.isoformat()
    ep = load_episode(ep_id) or {"id": ep_id, "date": ep_id}
    redo = ep.get("redo") or {}
    note = redo.get("note")
    exclude = [ep["saint"]["qid"]] if redo.get("new_saint") and ep.get("saint", {}).get("qid") else []
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
            log("Fact-check rejected saint; choosing another")
            ep["saint"] = {"qid": saint["qid"], "name": saint["name"]}
            ep["redo"] = {"new_saint": True}
            ep["status"] = "redo_requested"
            save_episode(ep)
            return generate_one(date, upload)
        final = fc.get("script") or draft
        final["saint"]["feast"] = month_day_label(date)
        final["saint"].setdefault("display_name", final["saint"]["name"].replace("Saint ", "St. ").replace("Saints ", "Sts. "))
        art_map, credits = build_art(saint, final, work)
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
            "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
            "art_credits": credits,
            "duration": round(t["voiceDuration"] + 3.8, 1),
        })
        ep["caption"] = build_caption(ep)
        ep.pop("redo", None)
        ep.pop("error", None)
        ep["attempts"] = 0
        ep.pop("caption_hook_override", None)
        if upload:
            import storage, telegram
            urls = storage.upload(f"ep-{ep_id}", {"video.mp4": out["video"], "cover.jpg": out["cover"]},
                                  name=f"{ep_id} · {final['saint']['name']}", body=ep["caption"])
            ep["assets"] = urls
            ep["status"] = "review"
            save_episode(ep)
            ep["review_message_id"] = telegram.send_review(ep, out["preview"])
        else:
            ep["status"] = "review"
            ep["local"] = {k: str(v) for k, v in out.items()}
        save_episode(ep)
        log(f"✔ {ep_id} {final['saint']['name']} ready for review")
        return ep
    except Exception as e:
        traceback.print_exc()
        ep["status"] = "failed"
        ep["attempts"] = ep.get("attempts", 0) + 1
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
    import instagram, storage, telegram
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
    if ep["status"] != "approved" or now < due_time:
        return
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
        ep["status"] = "approved"
        ep["publish_error"] = str(e)[:500]
        ep["publish_attempts"] = ep.get("publish_attempts", 0) + 1
        save_episode(ep)
        if ep["publish_attempts"] in (1, 3):
            telegram.send(f"❌ Publishing failed ({ep['publish_attempts']}x): {str(e)[:300]}\nWill retry.")


def cmd_poll(a):
    import telegram, storage
    actions = telegram.process_updates()
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
    sub.add_parser("refresh-token")
    sub.add_parser("build-calendar")
    sub.add_parser("whoami")
    a = p.parse_args()
    if a.cmd == "generate":
        cmd_generate(a)
    elif a.cmd == "poll":
        cmd_poll(a)
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
