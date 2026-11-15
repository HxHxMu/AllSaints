"""Offline tests for the episode art: the cover is a portrait of the saint, painted apart from the beats (Gemini stubbed).
Run: cd engine && ../.venv/bin/python -m unittest discover -p 'test_*.py'"""
import json, tempfile, threading, unittest
from pathlib import Path
from unittest import mock

import illustrate

ILL = illustrate.ILL


def script(**kw):
    s = {"saint": {"name": "Saint Roque González", "dates": "1576 – 1628", "region": "Paraguay", "martyr": True},
         "portrait": "A Jesuit in a black cassock holding a martyr's palm, a wooden mission chapel behind him.",
         "beats": [{"role": "hook", "text": "Fire consumed his body.", "visual": "art", "scene": "A wooden chapel burning in the forest."},
                   {"role": "who", "text": "...", "visual": "map"},
                   {"role": "story", "text": "...", "visual": "art", "scene": "He builds a village with the Guaraní."},
                   {"role": "close", "text": "Saint Roque González, pray for us.", "visual": "close"}]}
    s.update(kw)
    return s


class Cover(unittest.TestCase):
    def paint(self, sc, skip=(), fail=None):
        prompts, lock = [], threading.Lock()

        def fake(prompt):
            with lock:
                prompts.append(prompt)
            if fail and fail in prompt:
                raise RuntimeError("gemini down")
            return b"jpg"
        with tempfile.TemporaryDirectory() as d, mock.patch.object(illustrate, "_generate", side_effect=fake), \
                mock.patch.object(illustrate, "_save", return_value=(1080, 1920)):
            art = illustrate.illustrate(sc["saint"], sc, Path(d), skip=set(skip))
        return art, prompts

    def test_cover_is_its_own_portrait(self):
        art, prompts = self.paint(script())
        self.assertEqual(set(art), {0, 2, "cover"})
        cover = next(p for p in prompts if "A portrait icon of" in p)
        self.assertIn("Saint Roque González", cover)
        self.assertIn("black cassock", cover)
        self.assertIn(ILL["cover_framing"], cover)
        self.assertNotIn("chapel burning", cover)

    def test_beats_no_longer_get_the_cover_framing(self):
        _, prompts = self.paint(script())
        beat_prompts = [p for p in prompts if "A portrait icon of" not in p]
        self.assertEqual(len(beat_prompts), 2)
        for p in beat_prompts:
            self.assertNotIn(ILL["cover_framing"], p)

    def test_luis_cover_override_skips_the_portrait(self):
        art, prompts = self.paint(script(), skip={"cover"})
        self.assertNotIn("cover", art)
        self.assertFalse(any("A portrait icon of" in p for p in prompts))

    def test_failed_portrait_falls_back_not_fails(self):
        with mock.patch.object(illustrate, "log"):
            art, _ = self.paint(script(), fail="A portrait icon of")
        self.assertEqual(set(art), {0, 2})

    def test_failed_beat_still_fails_the_episode(self):
        with self.assertRaises(RuntimeError):
            self.paint(script(), fail="village with the Guaraní")

    def test_old_scripts_without_portrait_get_a_generic_one(self):
        sc = illustrate.portrait_scene(script(portrait=None))
        self.assertIn("A portrait icon of Saint Roque González (1576 – 1628, Paraguay)", sc)
        self.assertIn("martyr's palm", sc)
        self.assertNotIn("martyr's palm", illustrate.portrait_scene(script(portrait=None, saint={"name": "Saint X"})))


class BuildArt(unittest.TestCase):
    def test_portrait_is_the_cover_and_website_icon(self):
        import generate
        painted = {0: {"image": Path("icon0.jpg")}, 2: {"image": Path("icon2.jpg")}, "cover": {"image": Path("iconcover.jpg")}}
        with mock.patch.object(illustrate, "overrides", return_value={}), \
                mock.patch.object(illustrate, "illustrate", return_value=painted), \
                mock.patch.object(generate, "load_config", return_value={}):
            art, credits = generate.build_art("2026-11-22", {}, script(), Path("."))
        self.assertEqual(art["cover"]["image"], Path("iconcover.jpg"))
        self.assertEqual(art["close"]["image"], Path("icon2.jpg"))
        self.assertEqual(credits, [ILL["credit"]])

    def test_without_portrait_the_first_beat_is_the_cover(self):
        import generate
        painted = {0: {"image": Path("icon0.jpg")}, 2: {"image": Path("icon2.jpg")}}
        with mock.patch.object(illustrate, "overrides", return_value={}), \
                mock.patch.object(illustrate, "illustrate", return_value=painted), \
                mock.patch.object(generate, "load_config", return_value={}):
            art, _ = generate.build_art("2026-11-22", {}, script(), Path("."))
        self.assertEqual(art["cover"]["image"], Path("icon0.jpg"))


class ScriptSchema(unittest.TestCase):
    def test_writer_is_asked_for_the_portrait(self):
        import script as scriptmod
        with mock.patch.object(scriptmod, "load_config", return_value={}):
            schema = scriptmod.schema()
        self.assertIn('"portrait"', schema)
        json.loads(schema)  # still valid JSON for the model to copy


if __name__ == "__main__":
    unittest.main()
