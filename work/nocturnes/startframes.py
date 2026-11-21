"""Start frames for image-to-video (Luis animates them on free tiers): a still per clip shot, with Margaret kept to one face
by giving Gemini frames of her from Part I as reference.   python startframes.py part2 2 4 5 8"""
import base64, json, sys, concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import illustrate
from common import env, http, log

ROOT = Path(__file__).parent
# Margaret in Part I: shot 2 is her canonical face (where we meet her), plus a tight crop of it and shot 5 (with her son).
# Refs are frames pulled from work/nocturnes/live/ (ffmpeg -ss 6 / 9 of 2.mp4, -ss 5 of 5.mp4).
REFS = [ROOT / "part2/start/ref2-6.png", ROOT / "part2/start/ref-face.png", ROOT / "part2/start/ref5.png"]
LOOK = ("A single still frame from a black-and-white 1920s German Expressionist silent film: orthochromatic film stock, extreme "
        "chiaroscuro, one hard light source, deep black shadows, painted theatrical sets with skewed angular architecture, drifting "
        "mist, visible film grain. Thirteenth-century Italy. Solemn and reverent. Vertical 9:16, the image fills the frame. No text.")
SAME = ("The young woman in this scene is exactly the same woman as in the three reference images (the second is a close-up of her "
        "face): the same face shape, long straight nose, pale skin, high cheekbones, dark eyes and dark brows, the same age, the same "
        "dark hooded wool cloak over a light linen veil. Keep her face recognisable even when she is small in the frame or turned "
        "away. The small boy is the same child as in the third reference image.")


def frame(prompt, out):
    parts = [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(p.read_bytes()).decode()}} for p in REFS]
    parts.append({"text": f"{LOOK}\n\n{SAME}\n\nScene: {prompt}"})
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
    # python startframes.py part2 2 4 5 8 [--variants a,b]: one frame per shot, or one per variant (2a.png, 2b.png)
    args = [a for a in sys.argv[1:] if not a.startswith("--") and "," not in a]
    var = sys.argv[sys.argv.index("--variants") + 1].split(",") if "--variants" in sys.argv else [""]
    part, shots = args[0], [int(x) for x in args[1:]]
    D = ROOT / part
    prompts = json.loads((D / "start" / "prompts.json").read_text())
    jobs = [(n, v) for n in shots for v in var]
    with cf.ThreadPoolExecutor(3) as ex:   # 3 at a time: the new Gemini key rate-limits (429) at 4+
        print(list(ex.map(lambda j: frame(prompts[str(j[0])], D / "start" / f"{j[0]}{j[1]}.png"), jobs)))
