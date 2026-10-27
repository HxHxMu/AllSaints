"""ElevenLabs narration with word-level timestamps (one request per beat, stitched with pauses)."""
import base64, json, re, subprocess
from pathlib import Path
from common import BRAND, env, http, log

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
GAP_AFTER = {"hook": 0.7, "who": 0.5, "story": 0.45, "turn": 0.8, "close": 0.0}


def _apply_pron(text, pron):
    """Replace names token-by-token so word counts stay aligned with the display text."""
    out = []
    for tok in text.split():
        m = re.match(r"^([\W]*)(.*?)([\W]*)$", tok)
        pre, core, post = m.groups()
        for k, v in (pron or {}).items():
            if core.lower() == k.lower() or core.lower() == (k.lower() + "'s"):
                core = v.replace(" ", "-") + ("'s" if core.lower().endswith("'s") and not k.lower().endswith("'s") else "")
                break
        out.append(pre + core + post)
    return " ".join(out)


def _words_from_alignment(al):
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, s0, e0 = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append((cur, s0, e0))
            cur, s0 = "", None
            continue
        if s0 is None:
            s0 = s
        cur += c
        e0 = e
    if cur:
        words.append((cur, s0, e0))
    return words


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def synthesize(script, outdir: Path):
    key = env("ELEVENLABS_API_KEY", required=True)
    v = BRAND["voice"]["elevenlabs"]
    voice = env("ELEVENLABS_VOICE_ID", v["voice_id"])
    pron = script.get("pronunciations") or {}
    beats = script["beats"]
    parts, words, t = [], [], 0.25
    beat_starts = []
    for i, b in enumerate(beats):
        display = b["text"].strip()
        spoken = _apply_pron(display, pron)
        body = {
            "text": spoken,
            "model_id": v["model_id"],
            "voice_settings": {"stability": v["stability"], "similarity_boost": v["similarity_boost"],
                               "style": v["style"], "use_speaker_boost": True, "speed": v.get("speed", 1.0)},
            "previous_text": " ".join(x["text"] for x in beats[max(0, i - 2):i]) or None,
            "next_text": beats[i + 1]["text"] if i + 1 < len(beats) else None,
        }
        for attempt in range(3):
            r = http.post(API.format(voice=voice) + "?output_format=mp3_44100_128",
                          headers={"xi-api-key": key, "Content-Type": "application/json"}, data=json.dumps(body), timeout=120)
            if r.status_code == 200:
                break
            log("ElevenLabs error", r.status_code, r.text[:300])
        r.raise_for_status()
        js = r.json()
        mp3 = outdir / f"beat{i}.mp3"
        mp3.write_bytes(base64.b64decode(js["audio_base64"]))
        d = duration(mp3)
        aw = _words_from_alignment(js["alignment"])
        disp_tokens = display.split()
        if len(aw) != len(disp_tokens):
            log(f"Word count mismatch beat {i}: {len(aw)} vs {len(disp_tokens)}; using spoken tokens")
            disp_tokens = [w[0] for w in aw]
        beat_starts.append(t)
        for tok, (_, s, e) in zip(disp_tokens, aw):
            words.append({"text": tok, "start": round(t + s, 3), "end": round(t + e, 3)})
        parts.append((mp3, t))
        t += d + GAP_AFTER.get(b["role"], 0.45)
    # stitch with adelay, then loudness-normalize
    inputs, filters = [], []
    for k, (p, start) in enumerate(parts):
        inputs += ["-i", str(p)]
        ms = int(start * 1000)
        filters.append(f"[{k}]adelay={ms}|{ms},aformat=channel_layouts=mono[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(parts)))
    filters.append(f"{mix}amix=inputs={len(parts)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9[out]")
    out = outdir / "voice.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
                    "-ar", "44100", "-b:a", "160k", str(out)], check=True)
    total = duration(out)
    log(f"Voice: {total:.1f}s, {len(words)} words")
    return {"voice": out, "voiceDuration": total, "words": words, "beat_starts": beat_starts}
