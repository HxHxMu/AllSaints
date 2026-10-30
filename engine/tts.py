"""Narration with word-level timings (one request per beat, stitched with pauses).

Provider: Gemini TTS (voice + director's notes in brand.json, timings recovered with Whisper);
ElevenLabs (returns its own timings) is the silent fallback if Gemini fails.
"""
import base64, difflib, json, re, subprocess
from pathlib import Path
from common import BRAND, env, http, log

EL_API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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


# ---------------- Gemini + Whisper ----------------
_whisper = None


def _norm(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return {"st": "saint", "sts": "saints"}.get(w, w)


def _whisper_words(path):
    """Word timings from faster-whisper; audio decoded with ffmpeg (avoids PyAV version issues)."""
    global _whisper
    import numpy as np
    from faster_whisper import WhisperModel
    if _whisper is None:
        _whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    segs, _ = _whisper.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, word_timestamps=True, language="en")
    return [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]


def _align(display_tokens, heard):
    """Give every display token a (start, end): matched words take Whisper's times; the rest
    (numbers read as words, unusual names) are interpolated between their matched neighbours."""
    a, b = [_norm(t) for t in display_tokens], [_norm(w[0]) for w in heard]
    times = [None] * len(a)
    for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(m.size):
            times[m.a + k] = (heard[m.b + k][1], heard[m.b + k][2])
    end = heard[-1][2] if heard else 0.5
    i = 0
    while i < len(a):
        if times[i]:
            i += 1
            continue
        j = i
        while j < len(a) and not times[j]:
            j += 1
        t0 = times[i - 1][1] if i else (heard[0][1] if heard else 0.0)
        t1 = times[j][0] if j < len(a) else end
        weights = [max(len(x), 1) for x in a[i:j]]
        step = (t1 - t0) / sum(weights)
        for k, wgt in zip(range(i, j), weights):
            times[k] = (t0, t0 + step * wgt)
            t0 += step * wgt
        i = j
    return times


def _gemini_beat(beat, pron, path):
    g = BRAND["voice"]["gemini"]
    names = "; ".join(f"{k} is pronounced {v}" for k, v in (pron or {}).items())
    prompt = (f"# AUDIO PROFILE: {g['profile']}\n\n## THE SCENE\n{g['scene']}\n\n### DIRECTOR'S NOTES\n{g['notes']} "
              f"{g['beats'].get(beat['role'], '')}" + (f"\nPronunciation: {names}." if names else "") +
              f"\n\n#### TRANSCRIPT\n{beat['text'].strip()}")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": g["voice"]}}}}}
    display = beat["text"].strip().split()
    for attempt in range(3):
        r = http.post(GEMINI_API.format(model=g["model"]), json=body, timeout=180,
                      headers={"x-goog-api-key": env("GEMINI_API_KEY", required=True)})
        if not r.ok:
            log("Gemini TTS error", r.status_code, r.text[:300])
            continue
        part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        raw = path.with_suffix(".raw")
        raw.write_bytes(base64.b64decode(part["data"]))
        fmt = [] if raw.read_bytes()[:4] == b"RIFF" else ["-f", "s16le", "-ar", "24000", "-ac", "1"]  # WAV, or bare 24 kHz PCM
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *fmt, "-i", str(raw), "-b:a", "192k", str(path)], check=True)
        heard = _whisper_words(path)
        # guard against the model reading the director's notes aloud or skipping text
        if heard and 0.7 <= len(heard) / len(display) <= 1.35:
            return [(tok, s, e) for tok, (s, e) in zip(display, _align(display, heard))]
        log(f"Gemini TTS beat '{beat['role']}': heard {len(heard)} words for {len(display)}; retrying")
    raise RuntimeError("Gemini TTS failed")


def _pace(per_beat, paths):
    """Gemini ignores pace directions and reads at ~105 wpm; speed up (pitch kept) toward the brand pace."""
    target = BRAND["voice"]["gemini"].get("wpm", 140)
    speech = sum(duration(p) for p in paths)
    f = min(1.25, max(1.0, target / (sum(len(b) for b in per_beat) / speech * 60)))
    if f < 1.01:
        return per_beat
    for p in paths:
        tmp = p.with_suffix(".pace.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-filter:a", f"atempo={f:.3f}", "-b:a", "192k", str(tmp)], check=True)
        tmp.replace(p)
    log(f"Narration sped up {f:.2f}x toward {target} wpm")
    return [[(tok, s / f, e / f) for tok, s, e in b] for b in per_beat]


def _elevenlabs_beat(beats, i, pron, path):
    v = BRAND["voice"]["elevenlabs"]
    key = env("ELEVENLABS_API_KEY", required=True)
    voice = env("ELEVENLABS_VOICE_ID", v["voice_id"])
    b = beats[i]
    display = b["text"].strip()
    body = {
        "text": _apply_pron(display, pron),
        "model_id": v["model_id"],
        "voice_settings": {"stability": v["stability"], "similarity_boost": v["similarity_boost"],
                           "style": v["style"], "use_speaker_boost": True, "speed": v.get("speed", 1.0)},
        "previous_text": " ".join(x["text"] for x in beats[max(0, i - 2):i]) or None,
        "next_text": beats[i + 1]["text"] if i + 1 < len(beats) else None,
    }
    for attempt in range(3):
        r = http.post(EL_API.format(voice=voice) + "?output_format=mp3_44100_128",
                      headers={"xi-api-key": key, "Content-Type": "application/json"}, data=json.dumps(body), timeout=120)
        if r.status_code == 200:
            break
        log("ElevenLabs error", r.status_code, r.text[:300])
    r.raise_for_status()
    js = r.json()
    path.write_bytes(base64.b64decode(js["audio_base64"]))
    aw = _words_from_alignment(js["alignment"])
    disp_tokens = display.split()
    if len(aw) != len(disp_tokens):
        log(f"Word count mismatch beat {i}: {len(aw)} vs {len(disp_tokens)}; using spoken tokens")
        disp_tokens = [w[0] for w in aw]
    return [(tok, s, e) for tok, (_, s, e) in zip(disp_tokens, aw)]


def synthesize(script, outdir: Path):
    pron = script.get("pronunciations") or {}
    beats = script["beats"]
    provider = BRAND["voice"].get("provider", "elevenlabs")
    per_beat, narrator = None, "elevenlabs"
    if provider == "gemini":
        try:
            per_beat = [_gemini_beat(b, pron, outdir / f"beat{i}.mp3") for i, b in enumerate(beats)]
            per_beat = _pace(per_beat, [outdir / f"beat{i}.mp3" for i in range(len(beats))])
            narrator = f"gemini:{BRAND['voice']['gemini']['voice']}"
            log(f"Narration: Gemini {BRAND['voice']['gemini']['voice']}")
        except Exception as e:
            log("Gemini narration failed, falling back to ElevenLabs:", e)
    if per_beat is None:
        per_beat = [_elevenlabs_beat(beats, i, pron, outdir / f"beat{i}.mp3") for i in range(len(beats))]
        log("Narration: ElevenLabs")
    parts, words, t = [], [], 0.25
    beat_starts = []
    for i, (b, bw) in enumerate(zip(beats, per_beat)):
        mp3 = outdir / f"beat{i}.mp3"
        beat_starts.append(t)
        words += [{"text": tok, "start": round(t + s, 3), "end": round(t + e, 3)} for tok, s, e in bw]
        parts.append((mp3, t))
        t += duration(mp3) + GAP_AFTER.get(b["role"], 0.45)
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
    return {"voice": out, "voiceDuration": total, "words": words, "beat_starts": beat_starts, "narrator": narrator}
