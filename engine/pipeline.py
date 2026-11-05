"""All Saints pipeline CLI.

  python engine/pipeline.py generate [--date YYYY-MM-DD] [--max N] [--no-upload]
  python engine/pipeline.py poll            # Telegram updates + publish due episodes
  python engine/pipeline.py refresh-token
  python engine/pipeline.py youtube <episode>  # upload one episode's Short now
  python engine/pipeline.py books [episode|all]  # website books about the saint (all = only episodes without)
  python engine/pipeline.py yt-auth <client_secret.json>
  python engine/pipeline.py build-calendar
"""
import argparse, datetime as dt, json, re, shutil, sys, traceback, unicodedata
from pathlib import Path
from common import (BRAND, STATE, WORK, assign_slugs, log, load_config, load_json, save_json, load_episodes, load_episode, save_episode, today, tz, month_day_label)

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
    # source names without the article ("Santi e Beati: San X" → "Santi e Beati"; old "Catholic Encyclopedia (1913)/St. X" too)
    # follow line right under the hook, above Instagram's "more" fold
    if CAP.get("follow_line"):
        hook, _, rest = body.partition("\n")
        body = f"{hook}\n{CAP['follow_line']}" + (f"\n{rest}" if rest else "")
    srcs = " · ".join(dict.fromkeys(re.split(r"[:/]", x["title"])[0].strip() for x in ep.get("sources", [])))
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
        ep["books"] = found_books
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


# $ per million tokens (input, output); cache writes bill 1.25x input, cache reads 0.1x. Thinking is in "out".
PRICES = {"sonnet": (2.00, 10.00), "haiku": (0.10, 0.50), "opus": (4.00, 20.00)}
GEMINI_PER_EPISODE = 0.22  # art + narration, from Google Cloud billing (Oct 29-31 2026, one episode a day, after savings)


def call_cost(row):
    p_in, p_out = next((v for k, v in PRICES.items() if k in row.get("model", "")), PRICES["sonnet"])
    return (row.get("in", 0) * p_in + row.get("cache_write", 0) * p_in * 1.25
            + row.get("cache_read", 0) * p_in * 0.1 + row.get("out", 0) * p_out) / 1e6


def cmd_cost(a):
    """Claude cost per episode from ep.usage, plus Gemini art/voice (a measured flat rate), and what a month costs."""
    eps = sorted((e for e in load_episodes().values() if e.get("usage")), key=lambda e: e["id"])
    steps, totals = {}, []
    for ep in eps:
        total = sum(call_cost(r) for r in ep["usage"])
        totals.append(total)
        for r in ep["usage"]:
            steps.setdefault(r["step"], []).append(call_cost(r))
        print(f"{ep['id']}  ${total:.3f}  {ep['saint']['name']}  ({len(ep['usage'])} calls)")
    if not totals:
        return print("No episodes with usage yet")
    avg = sum(totals) / len(totals)
    print(f"\nAverage ${avg:.3f}/episode -> ${avg * 30:.2f} per 30 days of Claude")
    both = avg + GEMINI_PER_EPISODE
    print(f"With Gemini (~${GEMINI_PER_EPISODE:.2f}/episode): ${both:.2f}/episode -> ${both * 30:.2f} per 30 days")
    print("By step (average per call): " + ", ".join(f"{k} ${sum(v) / len(v):.3f}" for k, v in steps.items()))


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
        publish_facebook(ep)
        pinterest_boards(ep)
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
    assign_slugs(ep)  # the web page's address is fixed from here on
    ep["status"] = "publishing"
    save_episode(ep)
    try:
        vid = WORK / f"{ep['id']}-video.mp4"
        storage.download(ep["assets"]["video.mp4"], vid)
        video_url = storage.resolve_direct(ep["assets"]["video.mp4"])
        cover_url = storage.resolve_direct(ep["assets"]["cover.jpg"])
        res = instagram.publish_reel(ep["caption"], video_url=video_url, cover_url=cover_url, video_path=vid)
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
    # the Reel is live: record it before anything else can fail (a retry from "approved" would post it twice)
    ep.update(status="published", published=res, published_at=now.isoformat(timespec="minutes"))
    save_episode(ep)
    _notify(f"📣 Posted: {ep['saint']['display_name']}\n{res.get('permalink') or ''}")
    publish_facebook(ep, vid)
    publish_youtube(ep, vid)


def _notify(text):
    """Telegram note after a post has succeeded: a failure here must not mark the post failed (a retry would double-post)."""
    import telegram
    try:
        telegram.send(text)
    except Exception:
        traceback.print_exc()


def publish_facebook(ep, video=None):
    """Post the Reel to the Facebook Page once, after it's on Instagram; independent, max 3 attempts."""
    import facebook, storage, telegram
    fb = ep.get("facebook") or {}
    if not facebook.configured() or fb.get("id") or fb.get("attempts", 0) >= 3 or ep.get("status") != "published":
        return
    try:
        res = facebook.publish_reel(ep["caption"], video_url=storage.resolve_direct(ep["assets"]["video.mp4"]), video_path=video,
                                    cover_url=storage.resolve_direct(ep["assets"]["cover.jpg"]) if ep["assets"].get("cover.jpg") else None)
        ep["facebook"] = {**res, "published_at": dt.datetime.now(tz()).isoformat(timespec="minutes")}
        save_episode(ep)
        _notify(f"📘 On Facebook: {ep['saint']['display_name']}\n{res['url']}")
    except Exception as e:
        traceback.print_exc()
        fb["attempts"] = fb.get("attempts", 0) + 1
        fb["error"] = str(e)[:500]
        ep["facebook"] = fb
        save_episode(ep)
        if fb["attempts"] in (1, 3):
            telegram.send(f"❌ Facebook post failed ({fb['attempts']}x): {str(e)[:300]}" + ("\nWill retry." if fb["attempts"] < 3 else ""))


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
    except Exception as e:
        traceback.print_exc()
        yt["attempts"] = yt.get("attempts", 0) + 1
        yt["error"] = str(e)[:500]
        ep["youtube"] = yt
        save_episode(ep)
        if yt["attempts"] in (1, 3):
            telegram.send(f"❌ YouTube upload failed ({yt['attempts']}x): {str(e)[:300]}" + ("\nWill retry." if yt["attempts"] < 3 else ""))
        return
    # uploaded: record the id first, so nothing after this can lead to a second upload
    ep["youtube"] = {**res, "published_at": dt.datetime.now(tz()).isoformat(timespec="minutes")}
    save_episode(ep)
    note = "" if res["privacy"] == "public" else f" ({res['privacy']}: publish it in YouTube Studio)"
    _notify(f"▶️ On YouTube{note}: {ep['saint']['display_name']}\n{res['url']}")
    try:
        youtube_cover(ep)
    except Exception:
        traceback.print_exc()
    try:
        youtube_playlists(ep)
    except Exception:
        traceback.print_exc()


def youtube_cover(ep):
    """The episode's cover.jpg as the Short's thumbnail (YouTube otherwise picks a frame). Raises; callers log."""
    import youtube, storage
    from common import http
    yt = ep.get("youtube") or {}
    if not yt.get("id") or yt.get("cover") or "cover.jpg" not in (ep.get("assets") or {}):
        return
    r = http.get(storage.resolve_direct(ep["assets"]["cover.jpg"]), timeout=60)
    r.raise_for_status()
    youtube.set_thumbnail(yt["id"], r.content)
    yt["cover"] = True
    ep["youtube"] = yt
    save_episode(ep)


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
            try:
                telegram.send(f"⚠️ Couldn't add {ep['saint']['display_name']} to playlists: {str(e)[:200]}{hint}")
            except Exception:
                traceback.print_exc()
    ep["youtube"] = yt
    save_episode(ep)


def pinterest_boards(ep):
    """Pinterest won't take an empty RSS feed, so each board's feed (site: /pin/<board>.xml) is connected by hand the day
    its first saint publishes: Telegram tells Luis which. Boards already announced/connected: state/pinterest.json."""
    import telegram
    st = load_json("pinterest.json", {"announced": []})
    month = dt.date.fromisoformat(ep["date"]).strftime("%B")
    names = [month] + ([ep["continent"]] if ep.get("continent") else [])
    new = [n for n in names if re.sub(r"\s+", "-", re.sub(r"^the ", "", n.lower())) not in st["announced"]]
    for n in new:
        slug = re.sub(r"\s+", "-", re.sub(r"^the ", "", n.lower()))
        title = BRAND["youtube"]["playlists"]["region" if n != month else "month"].replace("{name}", n)
        try:
            telegram.send(f"📌 Pinterest board ready: {title}\nIts first saint is out. In ~10 min (site update): create the board "
                          f"\"{title}\" (description in docs/pinterest-boards.md), then Settings → Bulk create Pins → Auto-publish "
                          f"→ Connect RSS feed:\nhttps://allholysaints.com/pin/{slug}.xml")
        except Exception:
            traceback.print_exc()
            return
        st["announced"].append(slug)
        save_json("pinterest.json", st)


def check_queue(now=None):
    """Once a day after config "check_time" (default 20:00): tells Telegram if tomorrow isn't ready (missing, failed,
    or waiting for approval), if the next days have no episode yet (generation stuck), or if yesterday's saint
    never posted. Silent when all is well. State: state/checks.json {"evening": last date checked}."""
    import telegram
    cfg = load_config()
    now = now or dt.datetime.now(tz())
    hh, mm = map(int, cfg.get("check_time", "20:00").split(":"))
    st = load_json("checks.json", {})
    if (now.hour, now.minute) < (hh, mm) or st.get("evening") == now.date().isoformat() or cfg.get("paused"):
        return
    if not cfg.get("launch_date") or now.date() < dt.date.fromisoformat(cfg["launch_date"]) - dt.timedelta(days=1):
        return
    day = lambda n: now.date() + dt.timedelta(days=n)
    label = lambda d: f"{d.strftime('%b')} {d.day}"
    notes = []
    tom = load_episode(day(1).isoformat())
    if not tom:
        notes.append(f"⚠️ Nothing is ready for tomorrow ({label(day(1))}). Tap /generate.")
    elif tom["status"] == "review":
        notes.append(f"⏰ Tomorrow's saint ({tom['saint']['display_name']}) still needs your approval. It posts at {cfg['post_time']}.")
    elif tom["status"] in ("failed", "redo_requested", "generating"):
        notes.append(f"⚠️ Tomorrow's episode ({label(day(1))}) isn't ready: {tom['status']}"
                     + (f" ({tom.get('error', '')[:150]})" if tom["status"] == "failed" else "") + ".")
    empty = [label(day(n)) for n in (2, 3, 4) if not load_episode(day(n).isoformat())]
    if len(empty) >= 2:
        notes.append(f"⚠️ No episode made yet for {', '.join(empty)}. Generation may be stuck: tap /generate.")
    yest = load_episode(day(-1).isoformat())
    if yest and yest["status"] != "published" and day(-1) >= dt.date.fromisoformat(cfg["launch_date"]):
        notes.append(f"⚠️ Yesterday's saint ({yest['saint']['display_name']}) never posted (status: {yest['status']}). "
                     "It won't post a day late on its own.")
    if notes:
        telegram.send("\n\n".join(notes))
    st["evening"] = now.date().isoformat()
    save_json("checks.json", st)


def cmd_poll(a):
    import telegram, storage
    actions = telegram.process_updates()
    telegram.resend_missing_reviews()
    if "generate" in actions:
        storage.dispatch_workflow("generate.yml")
    publish_due()
    try:
        import shares
        shares.run_due()  # one-off scheduled posts (state/shares.json); never blocks the daily post
    except Exception:
        traceback.print_exc()
    try:
        import stories
        stories.run_due()  # nightly prayer card + seasonal Stories (state/stories.json)
    except Exception:
        traceback.print_exc()
    try:
        check_queue()  # evening heads-up about tomorrow
    except Exception:
        traceback.print_exc()


def cmd_post(post_id):
    """A one-off carousel Luis approved in chat (images hosted on a GitHub release). Each platform once; reruns skip what's done."""
    import facebook, instagram, storage, telegram
    p = STATE / "posts" / f"{post_id}.json"
    post = json.loads(p.read_text())
    save = lambda: p.write_text(json.dumps(post, indent=1, ensure_ascii=False) + "\n")
    ig, fb = post.get("instagram"), post.get("facebook")
    if ig and not ig.get("media_id"):
        ig.update(instagram.publish_carousel(ig["caption"], [storage.resolve_direct(u) for u in post["images"]]))
        save()
        _notify(f"📣 Instagram carousel posted: {post['title']}\n{ig.get('permalink') or ''}")
    if fb and not fb.get("url") and facebook.configured():
        WORK.mkdir(exist_ok=True)
        files = [storage.download(u, WORK / f"post-{post_id}-{i}.jpg") for i, u in enumerate(post["images"])]
        fb.update(facebook.post_photos(fb["message"], files))
        save()
        _notify(f"📣 Facebook post: {post['title']}\n{fb['url']}")


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
    ga = sub.add_parser("gsc-auth", help="one-time: Search Console access for the dashboard (pick Luis's own Google account)")
    ga.add_argument("client_secret")
    mp = sub.add_parser("metrics", help="collect the dashboard's numbers and send them to allholysaints.com/dash/")
    mp.add_argument("--out", help="write the JSON to this file instead of sending it")
    sub.add_parser("dash-key", help="one-time: make the dashboard's ingest key (.env, GitHub, Cloudflare Pages)")
    sub.add_parser("fb-auth", help="one-time: store a never-expiring Facebook Page token (FB_PAGE_ID/FB_PAGE_TOKEN)")
    sub.add_parser("fb-whoami")
    fp = sub.add_parser("facebook", help="post one published episode's Reel to the Facebook Page now")
    fp.add_argument("episode")
    fc = sub.add_parser("fb-cover", help="set the cover on Facebook Reels already posted (backfill)")
    fc.add_argument("episodes", nargs="+")
    yc = sub.add_parser("yt-cover", help="set cover.jpg as the thumbnail on Shorts already uploaded (backfill)")
    yc.add_argument("episodes", nargs="+")
    yp = sub.add_parser("yt-playlists", help="add published Shorts to their playlists (backfill / retry)")
    yp.add_argument("episode", nargs="?", default="all")
    lp = sub.add_parser("yt-localize", help="add the Spanish title/description to uploaded Shorts")
    lp.add_argument("episode", nargs="?", default="all")
    bp = sub.add_parser("books", help="look up books about the saint for the website (backfill / redo)")
    bp.add_argument("episode", nargs="?", default="all")
    sub.add_parser("cost", help="Claude cost per episode (from ep.usage) and per month")
    sp = sub.add_parser("backfill-story", help="website story + Spanish for episodes made before they existed, with a fresh fact-check")
    sp.add_argument("episode", help="episode id, or 'all' for every episode without a story")
    cp = sub.add_parser("compilation", help="the month's Shorts as one video, uploaded private (default: the month ending today)")
    cp.add_argument("month", nargs="?", help="YYYY-MM")
    cp.add_argument("--force", action="store_true", help="redo even if uploaded / before compilation_from")
    cp.add_argument("--no-upload", action="store_true", help="render only (work/compilation-YYYY-MM/)")
    po = sub.add_parser("post", help="publish an approved one-off carousel, state/posts/<id>.json (Instagram + Facebook)")
    po.add_argument("post_id")
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
    elif a.cmd == "gsc-auth":
        import youtube
        youtube.authorize(a.client_secret, scopes=youtube.GSC_SCOPE, refresh_key="GSC_REFRESH_TOKEN")
    elif a.cmd == "metrics":
        import metrics
        metrics.run(a.out)
    elif a.cmd == "dash-key":
        import metrics
        metrics.setup_key()
    elif a.cmd == "yt-playlists":
        eps = [load_episode(a.episode)] if a.episode != "all" else load_episodes().values()
        for ep in eps:
            if ep and (ep.get("youtube") or {}).get("id"):
                ep["youtube"].pop("playlist_attempts", None)
                youtube_playlists(ep)
    elif a.cmd == "yt-localize":
        import youtube
        eps = [load_episode(a.episode)] if a.episode != "all" else load_episodes().values()
        for ep in eps:
            if ep and ep.get("es") and (ep.get("youtube") or {}).get("id"):
                youtube.set_localizations(ep)
    elif a.cmd == "books":
        import books
        eps = [load_episode(a.episode)] if a.episode != "all" else load_episodes().values()
        for ep in eps:
            if ep and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ep["id"]) and (a.episode != "all" or "books" not in ep):
                ep["books"] = books.find(ep["saint"])
                save_episode(ep)
                print(ep["id"], ep["saint"]["name"], [b["title"] for b in ep["books"]])
    elif a.cmd == "cost":
        cmd_cost(a)
    elif a.cmd == "backfill-story":
        eps = [load_episode(a.episode)] if a.episode != "all" else [
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
    elif a.cmd == "compilation":
        import compilation
        compilation.make(a.month, force=a.force, upload=not a.no_upload)
    elif a.cmd == "fb-auth":
        import facebook
        facebook.authorize()
    elif a.cmd == "fb-whoami":
        import facebook
        print(facebook.me())
    elif a.cmd == "facebook":
        ep = load_episode(a.episode)
        (ep.get("facebook") or {}).pop("attempts", None)
        publish_facebook(ep)
    elif a.cmd == "fb-cover":
        import facebook, storage
        for ep_id in a.episodes:
            ep = load_episode(ep_id)
            facebook.set_cover(ep["facebook"]["id"], storage.resolve_direct(ep["assets"]["cover.jpg"]))
    elif a.cmd == "yt-cover":
        for ep_id in a.episodes:
            youtube_cover(load_episode(ep_id))
    elif a.cmd == "post":
        cmd_post(a.post_id)
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
