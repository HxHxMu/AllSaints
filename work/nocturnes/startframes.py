"""Start frames for image-to-video (Luis animates them on free tiers): a still per clip shot, with Margaret kept to one face
by giving Gemini frames of her from Part I as reference.   python startframes.py part2 2 4 5 8"""
import base64, json, sys, concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import illustrate
from common import env, http, log

ROOT = Path(__file__).parent
REFS = [ROOT / "part2/start/ref2-6.png", ROOT / "part2/start/ref5.png"]   # Margaret in Part I (shots 2 and 5)
LOOK = ("A single still frame from a black-and-white 1920s German Expressionist silent film: orthochromatic film stock, extreme "
        "chiaroscuro, one hard light source, deep black shadows, painted theatrical sets with skewed angular architecture, drifting "
        "mist, visible film grain. Thirteenth-century Italy. Solemn and reverent. Vertical 9:16, the image fills the frame. No text.")
SAME = ("The young woman in this scene is the same woman as in the reference images: the same face, features, age and dark hooded "
        "cloak with a light linen veil. The small boy is the same child as in the second reference image.")


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
    part, shots = sys.argv[1], [int(x) for x in sys.argv[2:]]
    D = ROOT / part
    prompts = json.loads((D / "start" / "prompts.json").read_text())
    with cf.ThreadPoolExecutor(4) as ex:
        print(list(ex.map(lambda n: frame(prompts[str(n)], D / "start" / f"{n}.png"), shots)))
