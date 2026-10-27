"""Telegram approval bot (polling, stateless between runs; state lives in state/telegram.json)."""
import json, re, datetime as dt
from common import env, http, log, load_config, save_config, load_episodes, load_episode, save_episode, load_json, save_json, today

API = "https://api.telegram.org/bot{token}/{method}"


def api(method, files=None, **params):
    url = API.format(token=env("TELEGRAM_BOT_TOKEN", required=True), method=method)
    for k, v in list(params.items()):
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v)
    r = http.post(url, data=params, files=files, timeout=300)
    js = r.json()
    if not js.get("ok"):
        log("Telegram error", method, js)
    return js.get("result")


def chat_id():
    return load_config().get("telegram_chat_id")


def send(text, **kw):
    cid = chat_id()
    if not cid:
        log("No Telegram chat yet (send /start to the bot)")
        return None
    return api("sendMessage", chat_id=cid, text=text[:4096], disable_web_page_preview=True, **kw)


def buttons(ep_id):
    return {"inline_keyboard": [
        [{"text": "✅ Approve", "callback_data": f"approve:{ep_id}"}, {"text": "🔁 Redo", "callback_data": f"redo:{ep_id}"}],
        [{"text": "✏️ Edit caption", "callback_data": f"caption:{ep_id}"}, {"text": "🔄 New saint", "callback_data": f"newsaint:{ep_id}"}],
    ]}


def send_review(ep, preview_path):
    cid = chat_id()
    if not cid:
        return None
    cfg = load_config()
    fc = ep.get("factcheck", {})
    head = (f"🕯 {ep['saint']['display_name']} · {ep['saint'].get('feast', '')}\n"
            f"Scheduled: {ep['date']} at {cfg['post_time']} ({cfg['timezone'].split('/')[-1].replace('_', ' ')})\n"
            f"Fact-check: {fc.get('verdict', '?')} · confidence {fc.get('confidence', '?')}%\n"
            f"Note: {fc.get('reviewer_note', '—')}")
    with open(preview_path, "rb") as f:
        msg = api("sendVideo", files={"video": f}, chat_id=cid, caption=head[:1024], supports_streaming="true",
                  width=1080, height=1920, reply_markup=buttons(ep["id"]))
    send("📝 Caption:\n\n" + ep["caption"] + ("\n\n⚠️ Issues fixed by fact-check:\n- " + "\n- ".join(fc.get("issues", [])) if fc.get("issues") else ""))
    return msg["message_id"] if msg else None


HELP = """A.S.† Studio commands
/status – upcoming queue
/launch YYYY-MM-DD – set launch date (nothing posts before it)
/time HH:MM – daily post time
/pause · /resume – stop/start publishing
/generate – make missing episodes now"""


def _status_text():
    cfg = load_config()
    eps = [e for e in load_episodes().values() if e["date"] >= today().isoformat()]
    eps.sort(key=lambda e: e["date"])
    lines = [f"Launch: {cfg.get('launch_date') or 'not set'} · Post time {cfg['post_time']} · {'⏸ paused' if cfg.get('paused') else '▶️ active'}"]
    icon = {"review": "👀", "approved": "✅", "published": "📣", "generating": "⚙️", "redo_requested": "🔁", "failed": "❌"}
    for e in eps[:14]:
        lines.append(f"{icon.get(e['status'], '•')} {e['date']} {e.get('saint', {}).get('display_name', '…')} – {e['status']}")
    return "\n".join(lines)


def process_updates():
    """Handle button presses and messages. Returns list of actions for the pipeline (e.g. 'generate')."""
    st = load_json("telegram.json", {"offset": 0, "pending": None})
    ups = api("getUpdates", offset=st["offset"], timeout=0, allowed_updates=["message", "callback_query"]) or []
    actions = []
    cfg = load_config()
    for u in ups:
        st["offset"] = u["update_id"] + 1
        if "callback_query" in u:
            cq = u["callback_query"]
            if cfg.get("telegram_chat_id") and cq["message"]["chat"]["id"] != cfg["telegram_chat_id"]:
                continue
            kind, ep_id = cq["data"].split(":", 1)
            ep = load_episode(ep_id)
            if not ep:
                api("answerCallbackQuery", callback_query_id=cq["id"], text="Episode not found")
                continue
            if kind == "approve":
                ep["status"] = "approved"
                save_episode(ep)
                api("answerCallbackQuery", callback_query_id=cq["id"], text="Approved ✅")
                api("editMessageReplyMarkup", chat_id=cq["message"]["chat"]["id"], message_id=cq["message"]["message_id"],
                    reply_markup={"inline_keyboard": [[{"text": f"✅ Approved – posts {ep['date']}", "callback_data": f"noop:{ep_id}"}],
                                                      [{"text": "↩️ Undo", "callback_data": f"unapprove:{ep_id}"}]]})
            elif kind == "unapprove":
                ep["status"] = "review"
                save_episode(ep)
                api("answerCallbackQuery", callback_query_id=cq["id"], text="Back in review")
                api("editMessageReplyMarkup", chat_id=cq["message"]["chat"]["id"], message_id=cq["message"]["message_id"], reply_markup=buttons(ep_id))
            elif kind in ("redo", "caption"):
                st["pending"] = {"kind": kind, "ep": ep_id}
                api("answerCallbackQuery", callback_query_id=cq["id"])
                send("What should change? (e.g. 'stronger hook', 'better art for the second scene', 'slower ending'). Send 'fresh' for a new take."
                     if kind == "redo" else "Send the new caption text (I'll keep the sources, credits and hashtags).")
            elif kind == "newsaint":
                ep["status"] = "redo_requested"
                ep["redo"] = {"new_saint": True, "note": None}
                save_episode(ep)
                api("answerCallbackQuery", callback_query_id=cq["id"], text="Picking a different saint…")
                actions.append("generate")
            else:
                api("answerCallbackQuery", callback_query_id=cq["id"])
            continue
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        cid = msg.get("chat", {}).get("id")
        if not text or not cid:
            continue
        if text.startswith("/start"):
            if not cfg.get("telegram_chat_id"):
                cfg["telegram_chat_id"] = cid
                save_config(cfg)
                api("sendMessage", chat_id=cid, text="🕯 A.S.† Studio connected. New episodes will arrive here for approval.\n\n" + HELP)
            elif cfg["telegram_chat_id"] == cid:
                api("sendMessage", chat_id=cid, text=HELP)
            continue
        if cid != cfg.get("telegram_chat_id"):
            continue
        if text.startswith("/status"):
            send(_status_text())
        elif text.startswith("/help"):
            send(HELP)
        elif text.startswith("/launch"):
            m = re.search(r"\d{4}-\d{2}-\d{2}", text)
            if m:
                cfg["launch_date"] = m.group(0)
                save_config(cfg)
                send(f"Launch date set: {m.group(0)}. Approved episodes from that day on will publish at {cfg['post_time']}.")
                actions.append("generate")
            else:
                send("Usage: /launch 2026-11-08")
        elif text.startswith("/time"):
            m = re.search(r"(\d{1,2}):(\d{2})", text)
            if m:
                cfg["post_time"] = f"{int(m.group(1)):02d}:{m.group(2)}"
                save_config(cfg)
                send(f"Post time set to {cfg['post_time']}.")
        elif text.startswith("/pause"):
            cfg["paused"] = True
            save_config(cfg)
            send("⏸ Publishing paused.")
        elif text.startswith("/resume"):
            cfg["paused"] = False
            save_config(cfg)
            send("▶️ Publishing resumed.")
        elif text.startswith("/generate"):
            actions.append("generate")
            send("⚙️ Generating missing episodes…")
        elif st.get("pending"):
            p = st["pending"]
            ep = load_episode(p["ep"])
            st["pending"] = None
            if not ep:
                continue
            if p["kind"] == "caption":
                ep["caption_hook_override"] = text
                from pipeline import build_caption
                ep["caption"] = build_caption(ep)
                save_episode(ep)
                send("✏️ Caption updated:\n\n" + ep["caption"], reply_markup=buttons(ep["id"]))
            else:
                ep["status"] = "redo_requested"
                ep["redo"] = {"new_saint": False, "note": None if text.lower() == "fresh" else text}
                save_episode(ep)
                send(f"🔁 Redoing {ep['saint']['display_name']}…")
                actions.append("generate")
    save_json("telegram.json", st)
    return actions
