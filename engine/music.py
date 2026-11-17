"""Music bed selection (Luis's beds in assets/music) with a generated placeholder fallback."""
import subprocess, hashlib
from datetime import date
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, butter, sosfilt
from common import ROOT, WORK, log

MUSIC = ROOT / "assets" / "music"


def pick_bed(seed: str):
    beds = sorted([p for p in MUSIC.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac") and not p.name.startswith(("placeholder", "._"))]) if MUSIC.exists() else []
    if not beds:
        beds = sorted(MUSIC.glob("placeholder*.mp3")) or [make_placeholder()]
    try:  # episode ids are dates: rotate by day so neighbouring Shorts (back to back in the compilation) never share a bed
        i = date.fromisoformat(seed[:10]).toordinal() % len(beds)
    except ValueError:
        i = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(beds)
    return prepare(beds[i])


# Bed loudness, so every episode has the music at the same level under the narration (tts.py: voice at −16 LUFS).
# −15 LUFS keeps the balance the channel was tuned on: Episode.jsx plays the bed at 0.14 (−17 dB → about −32 LUFS,
# 16 LU under the voice) and lifts it to 0.30 for the close (about −25.5 LUFS). LRA 1 makes loudnorm level the bed
# slowly over time (the beds swing 4–6 LU inside; with LRA 11 a Reel's outro could land anywhere from −24 to −27 LUFS).
# A gentle slow 2:1 compressor first evens out phrase-to-phrase swells that loudnorm's 3 s window leaves (the outro
# heard 1.4 s at a time: 4.9 LU spread before, 2.3 after); set BED_COMP = "" to drop it.
# The limiter is a 4× oversampled brick wall at −1 dBTP (alimiter alone is sample-peak), after loudnorm's own −1.5.
BED_LUFS, BED_LRA, BED_TP = -15, 1, -1.0
BED_COMP = "acompressor=threshold=0.1:ratio=2:attack=200:release=1500:knee=6:makeup=1"


def bed_filter(target_lufs=BED_LUFS, lra=BED_LRA, tp=BED_TP, comp=BED_COMP):
    limit = 10 ** (tp / 20)
    return ((f"{comp}," if comp else "") + f"loudnorm=I={target_lufs}:TP={tp - 0.5}:LRA={lra},"
            f"aresample=176400,alimiter=limit={limit:.6f}:attack=5:release=80:level=disabled,aresample=44100")


def bed_path(src, min_seconds=100, **kw):
    """Cache name carries a hash of the settings, so changing them re-prepares every bed."""
    key = hashlib.md5(f"{bed_filter(**kw)}|{min_seconds}".encode()).hexdigest()[:8]
    return WORK / "music" / f"{src.stem}-bed-{key}.mp3"


def prepare(src, target_lufs=BED_LUFS, min_seconds=100):
    """Level a bed to BED_LUFS with a true-peak ceiling and, if shorter than an episode could run,
    extend it by crossfading it into itself (Remotion's loop would otherwise hard-cut)."""
    out = bed_path(src, min_seconds, target_lufs=target_lufs)
    if out.exists() and out.stat().st_size and out.stat().st_mtime > src.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip())
    copies = max(1, -(-min_seconds // int(dur - 4)))  # ceil; each crossfade overlaps 4 s
    steps, prev = [], "[0]"
    for k in range(1, copies):
        steps.append(f"{prev}[{k}]acrossfade=d=4:c1=tri:c2=tri[x{k}]")
        prev = f"[x{k}]"
    steps.append(f"{prev}{bed_filter(target_lufs)}")
    inputs = [a for _ in range(copies) for a in ("-i", str(src))]
    tmp = out.with_suffix(".tmp.mp3")  # rename only when complete, so a failed run never leaves a bad bed cached
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(steps),
                    "-ar", "44100", "-b:a", "192k", str(tmp)], check=True)
    tmp.replace(out)
    log(f"Prepared music bed {src.name}")
    return out


def make_placeholder(name="placeholder-pad-1.mp3", seconds=95, sr=44100, seed=7):
    """Slow modal organ/choir-like pad: D dorian chord changes, soft attack, long reverb."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    chords = [[50, 57, 62, 65], [48, 55, 60, 64], [46, 53, 58, 62], [45, 52, 57, 60], [50, 57, 62, 69]]
    seg = seconds / len(chords)
    out = np.zeros_like(t)
    for ci, ch in enumerate(chords):
        s0, s1 = ci * seg, (ci + 1) * seg + 3
        env = np.clip((t - s0) / 4, 0, 1) * np.clip((s1 - t) / 4, 0, 1)
        for n in ch:
            f = 440 * 2 ** ((n - 69) / 12)
            for det in (-0.12, 0.0, 0.11):
                ff = f * 2 ** (det / 12)
                ph = rng.uniform(0, 2 * np.pi)
                tone = (np.sin(2 * np.pi * ff * t + ph) + 0.35 * np.sin(4 * np.pi * ff * t + ph)
                        + 0.12 * np.sin(6 * np.pi * ff * t + ph))
                out += env * tone * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t + ph))
    sos = butter(2, 1800, "low", fs=sr, output="sos")
    out = sosfilt(sos, out)
    ir_t = np.arange(int(3.5 * sr)) / sr
    ir = rng.normal(0, 1, ir_t.size) * np.exp(-ir_t / 1.1)
    wet = fftconvolve(out, ir)[: out.size]
    mix = 0.55 * out / np.abs(out).max() + 0.45 * wet / np.abs(wet).max()
    mix *= np.clip(t / 3, 0, 1) * np.clip((seconds - t) / 3, 0, 1)
    mix = (mix / np.abs(mix).max() * 0.7 * 32767).astype(np.int16)
    MUSIC.mkdir(parents=True, exist_ok=True)
    wav = MUSIC / (name + ".wav")
    wavfile.write(wav, sr, np.stack([mix, mix], 1))
    mp3 = MUSIC / name
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k", str(mp3)], check=True)
    wav.unlink()
    log("Generated placeholder music", mp3)
    return mp3


if __name__ == "__main__":
    make_placeholder()
