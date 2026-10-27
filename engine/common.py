"""Shared config, HTTP, Claude helper and state for the All Saints pipeline."""
import json, os, re, time, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
STATE = ROOT / "state"
DATA = ROOT / "data"
WORK = ROOT / "work"          # scratch per episode (gitignored)
VIDEO = ROOT / "video"
BRAND = json.loads((ROOT / "brand" / "brand.json").read_text())
for d in (STATE, DATA, WORK):
    d.mkdir(exist_ok=True)

UA = "AllSaintsBot/1.0 (https://github.com; educational Catholic saints Reels) python-requests"
http = requests.Session()
http.headers.update({"User-Agent": UA})


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        raise SystemExit(f"Missing required environment variable {name}")
    return v


# ---------------- config ----------------
CONFIG_PATH = STATE / "config.json"
DEFAULT_CONFIG = {
    "timezone": "America/New_York",
    "post_time": "07:30",
    "days_ahead": 7,
    "max_generate_per_run": 3,
    "launch_date": None,          # YYYY-MM-DD; nothing publishes before this
    "telegram_chat_id": None,     # set automatically by first /start
    "anthropic_models": ["claude-sonnet-4-5", "claude-sonnet-4-5-20250929", "claude-3-7-sonnet-latest"],
    "scope": "Canonized saints (incl. pre-congregation saints), Eastern Catholic saints, early Church martyrs. Must be venerated in the Catholic Church (Latin or Eastern Catholic). Prefer lesser-known figures with a vivid, documented story.",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def tz():
    return ZoneInfo(load_config()["timezone"])


def today():
    return dt.datetime.now(tz()).date()


# ---------------- episode state (one file per episode = fewer git conflicts) ----------------
EP_DIR = STATE / "episodes"
EP_DIR.mkdir(parents=True, exist_ok=True)


def load_episodes():
    return {p.stem: json.loads(p.read_text()) for p in sorted(EP_DIR.glob("*.json"))}


def load_episode(ep_id):
    p = EP_DIR / f"{ep_id}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_episode(ep):
    ep["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (EP_DIR / f"{ep['id']}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False) + "\n")


def load_json(name, default):
    p = STATE / name
    return json.loads(p.read_text()) if p.exists() else default


def save_json(name, obj):
    (STATE / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def log(*a):
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------- Claude ----------------
_client = None


def claude(messages, system=None, max_tokens=4000, temperature=0.6):
    """Call Claude, trying configured models in order. Returns text."""
    global _client
    import anthropic
    if _client is None:
        _client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY", required=True))
    models = [env("ANTHROPIC_MODEL")] if env("ANTHROPIC_MODEL") else _auto_models() + load_config()["anthropic_models"]
    last = None
    for m in models:
        for attempt in range(3):
            try:
                kw = dict(model=m, max_tokens=max_tokens, messages=messages, temperature=temperature)
                if system:
                    kw["system"] = system
                r = _client.messages.create(**kw)
                return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            except anthropic.NotFoundError as e:
                last = e
                break
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                last = e
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Claude call failed: {last}")


_auto = None


def _auto_models():
    """Newest Sonnet model available to this key (models.list returns newest first)."""
    global _auto
    if _auto is None:
        _auto = []
        try:
            for m in _client.models.list(limit=50).data:
                if "sonnet" in m.id:
                    _auto = [m.id]
                    break
        except Exception as e:
            log("models.list failed:", e)
    return _auto


def parse_json(text):
    """Extract the first JSON object/array from model output."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("No JSON in model output:\n" + text[:500])
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(text[start:])
    return obj


def claude_json(prompt, system=None, max_tokens=4000, temperature=0.5, images=None):
    content = []
    for img in images or []:
        content.append(img)
    content.append({"type": "text", "text": prompt})
    for attempt in range(2):
        txt = claude([{"role": "user", "content": content}], system=system, max_tokens=max_tokens, temperature=temperature)
        try:
            return parse_json(txt)
        except Exception as e:
            log("JSON parse failed, retrying:", e)
    raise RuntimeError("Claude did not return valid JSON")


def month_day_label(d: dt.date):
    return d.strftime("%B ") + str(d.day)
