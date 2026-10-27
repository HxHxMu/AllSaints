"""Assemble Remotion props from script + narration + art, then render video and cover."""
import json, os, shutil, subprocess
from pathlib import Path
from common import VIDEO, log

MOVES = ["in", "right", "out", "up", "left", "in", "down", "out"]


def build_props(ep_id, script, tts, art_map, music_rel):
    """art_map: {beat_index: {image, w, h, focus, move, credit}}, plus 'cover' and 'close' keys."""
    beats = script["beats"]
    starts = tts["beat_starts"]
    scenes = []
    last_art = None
    for i, b in enumerate(beats):
        st = 0 if i == 0 else round(starts[i] - 0.15, 3)
        if b["visual"] == "map":
            scenes.append({"kind": "map", "start": st, "lat": b.get("lat", 41.9), "lon": b.get("lon", 12.5), "place": b.get("place", "")})
        elif b["visual"] == "close":
            close = art_map.get("close") or last_art or {}
            scenes.append({"kind": "close", "start": st, "image": close.get("image"), "text": b["text"]})
        else:
            a = art_map.get(i) or (dict(last_art, move=MOVES[i % len(MOVES)]) if last_art else None)
            if not a:
                scenes.append({"kind": "map", "start": st, "lat": beats[1].get("lat", 41.9), "lon": beats[1].get("lon", 12.5), "place": beats[1].get("place", "")})
                continue
            scenes.append({"kind": "art", "start": st, **a})
            last_art = a
    who = next((i for i, b in enumerate(beats) if b["role"] == "who"), 1)
    t0 = starts[who] + 0.1
    t1 = starts[who + 1] - 0.2 if who + 1 < len(starts) else t0 + 4
    t1 = max(t1, t0 + 3.2)
    props = {
        "id": ep_id,
        "saint": script["saint"],
        "voice": f"episodes/{ep_id}/voice.mp3",
        "voiceDuration": tts["voiceDuration"],
        "music": music_rel,
        "words": tts["words"],
        "scenes": scenes,
        "title": {"start": round(t0, 3), "end": round(t1, 3)},
        "outro": 3,
        "cover": art_map.get("cover") or (last_art or {}),
    }
    return props


def remotion(args):
    cmd = ["npx", "remotion", *args, "--log=error"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    subprocess.run(cmd, cwd=VIDEO, check=True)


def render(ep_id, props, outdir: Path):
    pub = VIDEO / "public" / "episodes" / ep_id
    pub.mkdir(parents=True, exist_ok=True)
    pfile = outdir / "props.json"
    pfile.write_text(json.dumps(props, ensure_ascii=False))
    video = outdir / "video.mp4"
    log("Rendering video…")
    remotion(["render", "src/index.js", "Episode", str(video), f"--props={pfile}", "--codec=h264", "--crf=19",
              "--audio-bitrate=192k", "--x264-preset=medium", "--concurrency=100%"])
    cover_png = outdir / "cover.png"
    remotion(["still", "src/index.js", "Cover", str(cover_png), f"--props={pfile}"])
    cover = outdir / "cover.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cover_png), "-q:v", "2", str(cover)], check=True)
    preview = video
    if video.stat().st_size > 45 * 1024 * 1024:
        preview = outdir / "preview.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=720:-2", "-c:v", "libx264",
                        "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", str(preview)], check=True)
    log(f"Rendered {video} ({video.stat().st_size / 1e6:.1f} MB)")
    return {"video": video, "cover": cover, "preview": preview}


def stage_assets(ep_id, files: dict):
    """Copy files into video/public/episodes/<id>/ and return their public-relative paths."""
    pub = VIDEO / "public" / "episodes" / ep_id
    pub.mkdir(parents=True, exist_ok=True)
    rel = {}
    for k, src in files.items():
        dst = pub / Path(src).name
        if Path(src).resolve() != dst.resolve():
            shutil.copy(src, dst)
        rel[k] = f"episodes/{ep_id}/{dst.name}"
    return rel
