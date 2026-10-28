"""Byzantine-icon illustrations per art beat with Gemini (Nano Banana), plus Luis's per-episode overrides."""
import base64, io, re, time, concurrent.futures as cf
from PIL import Image
from common import BRAND, ROOT, env, http, log

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ILL = BRAND["illustration"]
OVERRIDES = ROOT / "art"          # art/<episode id>/<beat index>.jpg|png or cover.jpg — replaces generated art
MOVES = ["in", "right", "out", "up", "left", "in", "down"]
W, H = 1080, 1920


def _scene(beat):
    """Scripts written before the 'scene' field: fall back to the descriptive part of art_hint."""
    if beat.get("scene"):
        return beat["scene"]
    return re.split(r";\s*search:|search:", beat.get("art_hint") or "")[0].strip() or beat["text"]


def _generate(prompt, tries=3):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    for attempt in range(tries):
        r = http.post(API.format(model=ILL["model"]), json=body, timeout=300,
                      headers={"x-goog-api-key": env("GEMINI_API_KEY", required=True)})
        if r.ok:
            cand = (r.json().get("candidates") or [{}])[0]
            img = next((p["inlineData"]["data"] for p in cand.get("content", {}).get("parts", []) if "inlineData" in p), None)
            if img:
                return base64.b64decode(img)
            log("Gemini returned no image:", cand.get("finishReason"))
        else:
            log("Gemini error", r.status_code, r.text[:300])
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Gemini image generation failed")


def _save(raw, path, trim=0.03):
    """Trim any painted panel edge, then fill 1080x1920 (Flash-Lite renders 768x1376)."""
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    im = im.crop((int(w * trim), int(h * trim), int(w * (1 - trim)), int(h * (1 - trim))))
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    im.crop((left, top, left + W, top + H)).save(path, "JPEG", quality=92)
    return W, H


def _art(path, i, credit):
    return {"image": path, "w": W, "h": H, "focus": {"x": 0.5, "y": 0.4}, "move": MOVES[i % len(MOVES)], "credit": credit}


def overrides(ep_id, work):
    """Images Luis dropped in art/<ep_id>/: {beat index | 'cover': art}."""
    d = OVERRIDES / ep_id
    out = {}
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        if p.name.startswith("._") or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        key = int(p.stem) if p.stem.isdigit() else p.stem.lower()
        if key == "cover" or isinstance(key, int):
            dst = work / f"override-{p.stem}.jpg"
            _save(p.read_bytes(), dst, trim=0)
            out[key] = _art(dst, key if isinstance(key, int) else 0, "")
    if out:
        log(f"Using {len(out)} override image(s) from {d}")
    return out


def illustrate(saint, script, work, skip=()):
    """Paint every art beat not in `skip`. The shared style prompt keeps the series consistent
    (a reference image made Gemini repeat the first composition in every beat)."""
    s = script["saint"]
    setting = ILL["setting_rule"].format(region=s.get("region") or "the saint's homeland", dates=s.get("dates") or "their lifetime")
    beats = [(i, b) for i, b in enumerate(script["beats"]) if b.get("visual") == "art" and i not in skip]

    def paint(item):
        i, b = item
        p = work / f"icon{i}.jpg"
        # style leads: with the scene first, long descriptions pull Gemini toward naturalistic painting
        _save(_generate(f"{ILL['style']}\n\nScene: {_scene(b)}\n\n{setting} {ILL['consistency']}"), p)
        return i, p

    art_map = {}
    with cf.ThreadPoolExecutor(4) as ex:
        for i, p in ex.map(paint, beats):
            art_map[i] = _art(p, i, ILL["credit"])
    log(f"Painted {len(art_map)} icon illustrations with {ILL['model']}")
    return art_map
