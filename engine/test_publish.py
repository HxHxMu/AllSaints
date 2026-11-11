"""Offline tests for the publish flow, captions and cost: every platform module is a stub, nothing touches the network
or state/. Run: cd engine && ../.venv/bin/python -m unittest discover -p 'test_*.py'"""
import copy, json, sys, types, unittest
from pathlib import Path
from unittest import mock

PLATFORMS = ("telegram", "storage", "instagram", "facebook", "threads", "tiktok", "youtube")
TESTDATA = Path(__file__).resolve().parent / "testdata"


def episode(status="published", **kw):
    ep = {"id": "2026-11-20", "date": "2026-11-20", "status": status, "caption": "Hook\n\ncaption",
          "saint": {"display_name": "St. Test", "name": "Saint Test"},
          "assets": {"video.mp4": "https://x/video.mp4"}}
    ep.update(kw)
    return ep


class Harness(unittest.TestCase):
    """Stubs the platform modules in sys.modules and records the order of saves and Telegram messages."""

    def setUp(self):
        self.events = []
        self.stubs = {}
        for name in PLATFORMS:
            m = types.ModuleType(name)
            m.configured = lambda: True
            self.stubs[name] = m
        tg = self.stubs["telegram"]
        tg.send = lambda text, **kw: self.events.append(("send", text))
        st = self.stubs["storage"]
        st.resolve_direct = lambda url: url + "?signed"
        st.download = lambda url, path: path
        yt = self.stubs["youtube"]
        yt.page_url = lambda ep, lang="en": "https://allholysaints.com/x/"
        yt.add_to_playlists = lambda ep, done=(): ["Saints of November"]
        yt.set_thumbnail = lambda vid, jpg: None
        self.stubs["threads"].build_text = lambda ep, url: "text"
        patch = mock.patch.dict(sys.modules, self.stubs)
        patch.start()
        self.addCleanup(patch.stop)
        import publish as P
        self.P = P
        for target in ("save_episode",):
            p = mock.patch.object(P, target, side_effect=lambda ep: self.events.append(("save", copy.deepcopy(ep))))
            p.start()
            self.addCleanup(p.stop)

    def saves(self):
        return [e[1] for e in self.events if e[0] == "save"]

    def sends(self):
        return [e[1] for e in self.events if e[0] == "send"]


# platform key in ep, publisher, stub module, stub call, result the stub returns, field that marks it done
CASES = [
    ("facebook", "publish_facebook", "facebook", "publish_reel", {"id": "fb1", "url": "https://fb/1"}, "id"),
    ("threads", "publish_threads", "threads", "publish_video", {"id": "th1", "url": "https://th/1"}, "id"),
    ("tiktok", "publish_tiktok", "tiktok", "upload_draft", {"publish_id": "tt1", "status": "SENT"}, "publish_id"),
    ("youtube", "publish_youtube", "youtube", "upload_short", {"id": "yt1", "url": "https://yt/1", "privacy": "public"}, "id"),
]


class SecondaryPlatforms(Harness):
    def run_case(self, case, ep, side_effect=None):
        key, fn, mod, call, res, done = case
        m = mock.Mock(return_value=copy.deepcopy(res), side_effect=side_effect)
        setattr(self.stubs[mod], call, m)
        getattr(self.P, fn)(ep)
        return m

    def test_success_records_before_notifying(self):
        for case in CASES:
            with self.subTest(case[0]):
                self.events.clear()
                ep = episode()
                m = self.run_case(case, ep)
                key, done = case[0], case[5]
                self.assertEqual(m.call_count, 1)
                self.assertEqual(ep[key][done], case[4][done])
                first_send = next(i for i, e in enumerate(self.events) if e[0] == "send")
                first_record = next(i for i, e in enumerate(self.events) if e[0] == "save" and (e[1].get(key) or {}).get(done))
                self.assertLess(first_record, first_send, "the post must be saved before any Telegram note")
                self.assertEqual(ep["status"], "published")

    def test_done_is_never_posted_again(self):
        for case in CASES:
            with self.subTest(case[0]):
                ep = episode(**{case[0]: {case[5]: "already"}})
                m = self.run_case(case, ep)
                self.assertEqual(m.call_count, 0)

    def test_failing_notify_keeps_the_record(self):
        def boom(text, **kw):
            raise RuntimeError("telegram down")
        self.stubs["telegram"].send = boom
        quiet = mock.patch("traceback.print_exc")
        quiet.start()
        self.addCleanup(quiet.stop)
        for case in CASES:
            with self.subTest(case[0]):
                ep = episode()
                m = self.run_case(case, ep)
                self.assertEqual(ep[case[0]][case[5]], case[4][case[5]])
                self.run_case(case, ep)  # a rerun after the failed note
                self.assertEqual(m.call_count, 1)

    def test_failures_count_attempts_and_stop_at_three(self):
        for case in CASES:
            with self.subTest(case[0]):
                self.events.clear()
                ep = episode()
                key, fn, mod, call = case[:4]
                m = mock.Mock(side_effect=RuntimeError("platform said no"))
                setattr(self.stubs[mod], call, m)
                with mock.patch("traceback.print_exc"):
                    for _ in range(5):
                        getattr(self.P, fn)(ep)
                self.assertEqual(m.call_count, 3)
                self.assertEqual(ep[key]["attempts"], 3)
                self.assertIn("platform said no", ep[key]["error"])
                self.assertEqual(ep["status"], "published", "a secondary failure never moves the episode")
                self.assertEqual(len(self.sends()), 2, "Telegram on the 1st and 3rd failure only")
                label = {"facebook": "Facebook post", "threads": "Threads post", "tiktok": "TikTok draft", "youtube": "YouTube upload"}[key]
                self.assertEqual(self.sends(), [f"❌ {label} failed (1x): platform said no\nWill retry.",
                                                f"❌ {label} failed (3x): platform said no"])

    def test_not_configured_is_skipped(self):
        for case in CASES:
            with self.subTest(case[0]):
                self.stubs[case[2]].configured = lambda: False
                ep = episode()
                m = self.run_case(case, ep)
                self.assertEqual(m.call_count, 0)
                self.stubs[case[2]].configured = lambda: True

    def test_meta_platforms_wait_for_the_reel(self):
        for case in CASES[:3]:  # YouTube is independent of Instagram: it gates on assets only
            with self.subTest(case[0]):
                m = self.run_case(case, episode(status="approved"))
                self.assertEqual(m.call_count, 0)

    def test_youtube_gates_on_assets(self):
        m = self.run_case(CASES[3], episode(status="approved"))
        self.assertEqual(m.call_count, 1)
        m = self.run_case(CASES[3], episode(status="approved", assets={}))
        self.assertEqual(m.call_count, 0)

    def test_youtube_cover_and_playlists_after_upload(self):
        ep = episode(assets={"video.mp4": "v", "cover.jpg": "c"})
        resp = mock.Mock(content=b"jpg")
        with mock.patch("common.http.get", return_value=resp):
            self.run_case(CASES[3], ep)
        self.assertTrue(ep["youtube"]["cover"])
        self.assertTrue(ep["youtube"]["playlists_done"])
        self.assertEqual(ep["youtube"]["playlists"], ["Saints of November"])

    def test_youtube_cover_failure_keeps_the_upload(self):
        ep = episode(assets={"video.mp4": "v", "cover.jpg": "c"})
        with mock.patch("common.http.get", side_effect=RuntimeError("cdn")), mock.patch("traceback.print_exc"):
            self.run_case(CASES[3], ep)
        self.assertEqual(ep["youtube"]["id"], "yt1")
        self.assertTrue(ep["youtube"]["playlists_done"])


class DailyReel(Harness):
    def setUp(self):
        super().setUp()
        for fn in ("publish_facebook", "publish_threads", "publish_youtube", "publish_tiktok"):
            p = mock.patch.object(self.P, fn)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(self.P, "assign_slugs")
        p.start()
        self.addCleanup(p.stop)
        self.ig = self.stubs["instagram"]

    def test_existing_reel_is_recorded_not_reposted(self):
        self.ig.find_reel = mock.Mock(return_value={"media_id": "ig1", "permalink": "https://ig/1"})
        self.ig.publish_reel = mock.Mock()
        ep = episode(status="approved", assets={"video.mp4": "v", "cover.jpg": "c"})
        self.P.publish_episode(ep)
        self.ig.publish_reel.assert_not_called()
        self.assertEqual(ep["status"], "published")
        self.assertEqual(ep["published"]["media_id"], "ig1")

    def test_posted_reel_is_saved_published_before_notes(self):
        self.ig.find_reel = mock.Mock(return_value=None)
        self.ig.publish_reel = mock.Mock(return_value={"media_id": "ig2", "permalink": "p"})
        ep = episode(status="approved", assets={"video.mp4": "v", "cover.jpg": "c"})
        self.P.publish_episode(ep)
        self.ig.publish_reel.assert_called_once()
        statuses = [s["status"] for s in self.saves()]
        self.assertEqual(statuses, ["publishing", "published"])
        self.assertEqual(self.events[-1][0], "send")

    def test_reel_failure_goes_back_to_approved(self):
        self.ig.find_reel = mock.Mock(return_value=None)
        self.ig.publish_reel = mock.Mock(side_effect=RuntimeError("ig down"))
        ep = episode(status="approved", assets={"video.mp4": "v", "cover.jpg": "c"})
        with mock.patch("traceback.print_exc"), self.assertRaises(RuntimeError):
            self.P.publish_episode(ep)
        self.assertEqual(ep["status"], "approved")
        self.assertEqual(ep["publish_attempts"], 1)
        self.P.publish_youtube.assert_called_once()  # the Short isn't held back by a Reel failure

    def test_failed_reel_check_still_posts(self):
        self.ig.find_reel = mock.Mock(side_effect=RuntimeError("graph 500"))
        self.ig.publish_reel = mock.Mock(return_value={"media_id": "ig3"})
        ep = episode(status="approved", assets={"video.mp4": "v", "cover.jpg": "c"})
        self.P.publish_episode(ep)
        self.assertEqual(ep["status"], "published")


class Captions(unittest.TestCase):
    def test_captions_match_snapshot(self):
        from captions import build_caption
        for case in json.loads((TESTDATA / "captions.json").read_text()):
            with self.subTest(case["episode"]["id"]):
                self.assertEqual(build_caption(case["episode"]), case["caption"])

    def test_hashtag_limit(self):
        from captions import CAP, ig_hashtags
        for case in json.loads((TESTDATA / "captions.json").read_text()):
            tags = ig_hashtags(case["episode"]["script"])
            self.assertLessEqual(len(tags), CAP.get("hashtags_max", 5))
            self.assertEqual(tags[0], CAP["hashtag_brand"])


class Cost(unittest.TestCase):
    def test_call_cost(self):
        from costs import call_cost
        row = {"model": "claude-sonnet-5-5", "in": 1_000_000, "out": 100_000, "cache_write": 1_000_000, "cache_read": 1_000_000}
        self.assertAlmostEqual(call_cost(row), 2.00 + 1.00 + 2.50 + 0.20)
        self.assertAlmostEqual(call_cost({"model": "claude-haiku-5-5", "in": 1_000_000}), 0.10)


if __name__ == "__main__":
    unittest.main()
