import datetime as dt, unittest
import report


def ep(date, stayed=None, avg=None, views=100, saint="Saint X"):
    return {"date": date, "saint": saint, "yt": {"views": views, "stayed_pct": stayed, "avg_pct": avg}}


class ReportTest(unittest.TestCase):
    def test_format_split_and_ranking(self):
        t = dt.date(2026, 11, 30)
        data = {"episodes": [ep("2026-11-20", 50, 55), ep("2026-11-22", 54, 59),
                             ep("2026-11-23", 62, 66, saint="Saint New"), ep("2026-11-24", 64, 70, saint="Saint Best"),
                             ep("2026-11-29", None, None, saint="Saint Fresh")],  # too young: no averages, no ranking
                "youtube": {"subscribers": 100, "views": 20000, "daily": [{"date": f"2026-11-{d:02d}", "views": 100, "subs": 1} for d in range(10, 24)]},
                "tiktok": {"followers": 90}, "notes": []}
        text = report.build(data, t)
        self.assertIn("Stayed to watch: before 52% → new 63%", text)
        self.assertIn("Avg viewed: before 57% → new 68%", text)
        self.assertIn("Shorts counted: 2 before, 2 new", text)
        self.assertIn("Best: Saint Best", text)
        self.assertNotIn("Saint Fresh", text)
        self.assertIn("YouTube: 5.0", text)
        self.assertNotIn("Instagram:", text)  # no followers figure, no line

    def test_mondays_only(self):
        self.assertTrue(report.due(dt.date(2026, 11, 16)))
        self.assertFalse(report.due(dt.date(2026, 11, 17)))


if __name__ == "__main__":
    unittest.main()
