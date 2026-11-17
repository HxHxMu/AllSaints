"""Offline checks for the music-bed preparation settings (no ffmpeg run)."""
import unittest
from pathlib import Path
import music


class BedSettings(unittest.TestCase):
    def test_filter_has_level_and_true_peak_limiter(self):
        f = music.bed_filter()
        self.assertIn(f"loudnorm=I={music.BED_LUFS}:", f)
        self.assertIn("alimiter=limit=0.891251", f)  # −1 dBTP
        self.assertIn("level=disabled", f)  # alimiter must not auto-gain the bed back up
        self.assertIn("aresample=176400", f)  # oversampled, so the ceiling holds for true peak

    def test_cache_name_changes_with_settings(self):
        src = Path("allsaints-2.mp3")
        a = music.bed_path(src)
        self.assertEqual(a, music.bed_path(src))
        self.assertNotEqual(a, music.bed_path(src, target_lufs=-18))
        self.assertNotEqual(a, music.bed_path(src, min_seconds=120))
        self.assertTrue(a.name.startswith("allsaints-2-bed-"))


if __name__ == "__main__":
    unittest.main()
