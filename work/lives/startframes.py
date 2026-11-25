"""Start frames for image-to-video (Luis animates them on free tiers): a still per clip shot. Look and the "same person" line come from <saint>/series.json; reference images
(frames of the saint, once a face is chosen) are listed there as "refs" (paths relative to the saint folder).
    .venv/bin/python work/lives/startframes.py john-of-god part1 2 4 5 [--variants a,b]"""
import base64, json, sys, concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import illustrate
from common import env, http, log

LIVES = Path(__file__).parent
ROOT = LIVES / sys.argv[1]
SER = json.loads((ROOT / "series.json").read_text())
REFS = [ROOT / p for p in SER.get("refs", [])]
LOOK = SER["look"]
SAME = SER.get("same", "") if REFS else ""


def frame(prompt, out):
    parts = [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(p.read_bytes()).decode()}} for p in REFS]
    parts.append({"text": f"{LOOK}\n\n{SAME}\n\nScene: {prompt}".replace("\n\n\n\n", "\n\n")})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    for _ in range(3):
        r = http.post(illustrate.API.format(model=illustrate.ILL["model"]), json=body, timeout=300,
                      headers={"x-goog-api-key": env("GEMINI_API_KEY", required=True)})
        if r.ok:
            img = next((p["inlineData"]["data"] for p in r.json()["candidates"][0].get("content", {}).get("parts", []) if "inlineData" in p), None)
            if img:
                out.write_bytes(base64.b64decode(img))
                return out
        log("retry", r.status_code, r.text[:200])
    raise RuntimeError("no image")


if __name__ == "__main__":
    # startframes.py <saint> part1 2 4 5 [--variants a,b]: one frame per shot, or one per variant (2a.png, 2b.png)
    args = [a for a in sys.argv[2:] if not a.startswith("--") and "," not in a]
    var = sys.argv[sys.argv.index("--variants") + 1].split(",") if "--variants" in sys.argv else [""]
    part, shots = args[0], [int(x) for x in args[1:]]
    D = ROOT / part
    prompts = json.loads((D / "start" / "prompts.json").read_text())
    jobs = [(n, v) for n in shots for v in var]
    with cf.ThreadPoolExecutor(3) as ex:   # 3 at a time: the new Gemini key rate-limits (429) at 4+
        print(list(ex.map(lambda j: frame(prompts[str(j[0])], D / "start" / f"{j[0]}{j[1]}.png"), jobs)))
