"""Offline tests for Instagram location tags (locations.py, Telegram /loc, the rejected-ID fallback). state/ is a temp dir."""
import sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

import common, locations


def episode(**kw):
    ep = {"id": "2026-11-20", "date": "2026-11-20", "status": "review", "saint": {"display_name": "St. Winifred"},
          "script": {"places": ["Holywell", "Gwytherin", "Wales"]}}
    ep.update(kw)
    return ep


class Locations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        state = Path(self.tmp.name)
        (state / "episodes").mkdir()
        for p in (mock.patch.object(common, "STATE", state), mock.patch.object(common, "EPISODES", state / "episodes", create=True)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_map_uses_most_specific_place_with_an_id(self):
        self.assertIsNone(locations.for_episode(episode()))
        locations.remember("Wales", "111111")
        self.assertEqual(locations.for_episode(episode())["name"], "Wales")
        locations.remember("Holywell", "222222")
        self.assertEqual(locations.for_episode(episode())["id"], "222222")

    def test_episode_override_and_off(self):
        locations.remember("Holywell", "222222")
        self.assertEqual(locations.for_episode(episode(location={"name": "Shrewsbury", "id": "333333"}))["id"], "333333")
        self.assertIsNone(locations.for_episode(episode(location={})))

    def test_slug_ignores_accents_and_case(self):
        locations.remember("León", "444444")
        self.assertEqual(locations.for_episode(episode(script={"places": ["LEON"]}))["id"], "444444")

    def test_page_id_from_link(self):
        self.assertEqual(locations.page_id("https://www.facebook.com/profile.php?id=100064716389223"), "100064716389223")
        self.assertIsNone(locations.page_id("Holywell"))

    def test_review_line(self):
        self.assertIn("/loc 2026-11-20", locations.review_line(episode()))
        locations.remember("Holywell", "222222")
        self.assertEqual(locations.review_line(episode()), "📍 Location: Holywell")


class LocCommand(Locations):
    def setUp(self):
        super().setUp()
        import telegram
        self.tg = telegram
        self.ep = episode()
        for p in (mock.patch.object(telegram, "load_episode", lambda i: self.ep if i == self.ep["id"] else None),
                  mock.patch.object(telegram, "save_episode", lambda e: None)):
            p.start()
            self.addCleanup(p.stop)

    def test_sets_episode_and_remembers_first_place(self):
        out = self.tg._set_location("/loc 2026-11-20 108143175870935")
        self.assertIn("Holywell", out)
        self.assertEqual(self.ep["location"], {"name": "Holywell", "id": "108143175870935"})
        self.assertEqual(locations.for_episode(episode())["id"], "108143175870935")

    def test_named_place(self):
        self.tg._set_location("/loc 2026-11-20 108143175870935 St Winefride's Well")
        self.assertEqual(self.ep["location"]["name"], "St Winefride's Well")

    def test_off_and_posted(self):
        self.tg._set_location("/loc 2026-11-20 off")
        self.assertEqual(self.ep["location"], {})
        self.ep["status"] = "published"
        self.assertIn("already posted", self.tg._set_location("/loc 2026-11-20 108143175870935"))
        self.assertIn("Usage", self.tg._set_location("/loc tomorrow 1"))


class RejectedId(unittest.TestCase):
    def test_bad_location_retries_untagged(self):
        import instagram
        calls = []

        def post(url, data=None, **kw):
            calls.append(dict(data or {}))
            ok = "media_publish" in url or "location_id" not in (data or {})
            return mock.Mock(ok=ok, text="Invalid location", json=lambda: {"id": "c1"}, raise_for_status=lambda: None)
        with mock.patch.object(instagram, "get_token", lambda: "t"), mock.patch.object(instagram, "_uid", lambda: "u"), \
                mock.patch.object(instagram, "_wait", lambda c, t: (True, "FINISHED")), \
                mock.patch.object(instagram.http, "post", post), \
                mock.patch.object(instagram.http, "get", lambda *a, **k: mock.Mock(json=lambda: {"permalink": "p"})):
            res = instagram.publish_reel("cap", video_url="https://v", location_id="999999")
        self.assertIsNone(res["location_id"])
        self.assertEqual(calls[0]["location_id"], "999999")
        self.assertNotIn("location_id", calls[1])


if __name__ == "__main__":
    unittest.main()
