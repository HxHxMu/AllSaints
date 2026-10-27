"""Music bed selection (Luis's beds in assets/music) with a generated placeholder fallback."""
import subprocess, hashlib
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, butter, sosfilt
from common import ROOT, log

MUSIC = ROOT / "assets" / "music"


def pick_bed(seed: str):
    beds = sorted([p for p in MUSIC.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac") and not p.name.startswith("placeholder")]) if MUSIC.exists() else []
    if not beds:
        beds = sorted(MUSIC.glob("placeholder*.mp3")) or [make_placeholder()]
    i = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(beds)
    return beds[i]


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
