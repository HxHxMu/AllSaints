"""The evening heads-up in Telegram about tomorrow's episode, the next days and yesterday (run by `poll`)."""
import datetime as dt
from common import load_config, load_json, save_json, load_episode, tz


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
