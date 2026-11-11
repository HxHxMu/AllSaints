"""Make one episode end to end (research → script → fact-check → art → voice → render → upload → Telegram review), and the
backfill of website stories for episodes made before they existed. Run by `pipeline.py generate` / `backfill-story`."""
import datetime as dt, shutil, traceback
from common import BRAND, WORK, assign_slugs, log, load_config, load_episodes, load_episode, save_episode, today, month_day_label
from captions import build_caption


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
    # a format test for this date (config "angles": {"2026-11-15": "miracle"}); the text lives in brand.json
    angle_key = ep.get("angle") or load_config().get("angles", {}).get(ep_id)
    angle = BRAND.get("angles", {}).get(angle_key)
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
            saint = research.select_saint(date, exclude=exclude, angle=angle)
        sources = research.gather_sources(saint)
        draft = scriptmod.write_script(saint, sources, date, note=note, angle=angle)
        fc = scriptmod.fact_check(draft, sources, angle=angle)
        if research.wikipedia_only(sources) and fc.get("verdict") != "reject":
            # nothing independent to check against: say so where Luis approves, and cap the score
            fc["confidence"] = min(fc.get("confidence") or 0, 70)
            fc["reviewer_note"] = "⚠️ Wikipedia is the only source; check the facts before approving. " + (fc.get("reviewer_note") or "")
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
        try:  # the website's "Go deeper" books about this saint (suggestions; /nobooks in Telegram drops them)
            import books
            found_books = books.find(final["saint"])
        except Exception as e:
            log("Book lookup failed:", e)
            found_books = []
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
        if angle:
            ep["angle"] = angle_key
        ep["books"] = found_books
        ep["caption"] = build_caption(ep)
        ep.pop("redo", None)
        ep.pop("error", None)
        ep["attempts"] = 0
        ep.pop("caption_hook_override", None)
        ep.pop("review_message_id", None)  # a new version needs its own review; a failed send is retried by the poll
        ep.pop("review_sends", None)
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


def backfill_story(ep):
    """Website story + Spanish for an episode made before they existed, from today's sources. The fact-check
    reruns on the whole script; only story fixes are applied (the video is made), the rest goes in ep.recheck."""
    import common, research, script as scriptmod
    start = len(common.USAGE)
    s = ep["script"]
    sources = research.gather_sources(ep["saint_pick"])
    draft = {**s, **scriptmod.write_story(s, sources)}
    fc = scriptmod.fact_check(draft, sources)
    checked = fc.get("script") or draft
    for k in ("story", "patronages", "places"):
        s[k] = checked.get(k) or draft.get(k) or []
    ep["sources"] = [{"title": x["title"], "url": x["url"]} for x in sources]
    ep["recheck"] = {"date": today().isoformat(), "beats_need_fixing": bool(fc.get("script")),
                     **{k: fc.get(k) for k in ("verdict", "issues", "confidence", "reviewer_note")}}
    try:
        ep["es"] = {**scriptmod.translate_es(s), **({"slug": ep["es"]["slug"]} if ep.get("es", {}).get("slug") else {})}
    except Exception as e:
        log("Spanish translation failed:", e)
    if ep.get("status") == "published":
        assign_slugs(ep)  # the new Spanish page's address
    ep["usage"] = (ep.get("usage") or []) + common.USAGE[start:]
    save_episode(ep)
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


def cmd_backfill_story(arg):
    """`pipeline.py backfill-story <ep_id|all>`: all = approved/published daily saints without a website story."""
    eps = [load_episode(arg)] if arg != "all" else [
        e for e in load_episodes().values() if e.get("saint_pick") and e.get("status") in ("approved", "published")
        and not e["script"].get("story")]  # saint_pick: daily saints only, not the channel intro
    for ep in sorted(eps, key=lambda e: e["id"]):
        backfill_story(ep)
        r = ep["recheck"]
        print(f"{ep['id']} {ep['saint']['name']}: {len(ep['script']['story'])} paragraphs, sources: "
              f"{', '.join(x['title'].split(':')[0] for x in ep['sources'])}\n  recheck {r['verdict']} ({r['confidence']})"
              f"{' BEATS NEED FIXING' if r['beats_need_fixing'] else ''}: {r['reviewer_note']}")
        for i in r.get("issues") or []:
            print("   -", i)
