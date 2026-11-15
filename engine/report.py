"""Weekly Telegram report (Mondays, from the nightly metrics run). No AI.

Built from the same numbers as the dashboard (metrics.collect), so nothing new is stored. It answers the
question for the 2026-12-15 review (docs/roadmap.md): did the tighter format (first episode FORMAT_CHANGE)
turn more viewers into followers? Preview: `pipeline.py metrics --out work/m.json --report` prints it.
"""
import datetime as dt
from common import today

FORMAT_CHANGE = "2026-11-23"  # payoff-first hook, WHO under 15 words, 115-130 words (brand.json, 2026-11-15)
SETTLE_DAYS = 3  # YouTube Analytics lags 2-3 days; younger Shorts would drag the averages down
TARGETS = {"stayed_pct": 60, "avg_pct": 65}
WEEKDAY = 0  # Monday


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _pct(v):
    return "—" if v is None else f"{v:g}%"


def _num(v):
    return "—" if v is None else f"{v:,}"


def _per_1k(followers, views):
    return round(1000 * followers / views, 1) if followers is not None and views else None


def build(data, t=None):
    t = t or today()
    eps = data.get("episodes") or []
    yt, tt, ig = data.get("youtube") or {}, data.get("tiktok") or {}, data.get("instagram") or {}
    settled = [e for e in eps if e["date"] <= (t - dt.timedelta(days=SETTLE_DAYS)).isoformat() and (e.get("yt") or {}).get("avg_pct") is not None]
    lines = [f"📊 Weekly report · {t.strftime('%b %-d')}", ""]

    # 1. the channel's week (YouTube's daily series ends a few days back)
    daily = yt.get("daily") or []
    if daily:
        wk, prev = daily[-7:], daily[-14:-7]
        v, s = sum(d["views"] for d in wk), sum(d["subs"] for d in wk)
        pv, ps = sum(d["views"] for d in prev), sum(d["subs"] for d in prev)
        trend = f" ({'+' if v >= pv else ''}{round(100 * (v - pv) / pv)}% vs the week before)" if pv else ""
        lines += [f"YouTube, {wk[0]['date'][5:]}–{wk[-1]['date'][5:]}: {_num(v)} views{trend}, {'+' if s >= 0 else ''}{s} subscribers"
                  f" (week before: {_num(pv)} views, {'+' if ps >= 0 else ''}{ps}; YouTube reports a few days late)"]

    # 2. the format test
    new = [e for e in settled if e["date"] >= FORMAT_CHANGE]
    old = [e for e in settled if e["date"] < FORMAT_CHANGE]
    lines += ["", f"Format test (new format from {FORMAT_CHANGE[5:]}; Shorts {SETTLE_DAYS}+ days old)"]
    for key, label in (("stayed_pct", "Stayed to watch"), ("avg_pct", "Avg viewed")):
        o, n = _avg(e["yt"].get(key) for e in old), _avg(e["yt"].get(key) for e in new)
        lines.append(f"• {label}: before {_pct(o)} → new {_pct(n) if new else 'not yet'} (target >{TARGETS[key]}%)")
    lines.append(f"• Shorts counted: {len(old)} before, {len(new)} new")

    # 3. followers per 1,000 views (all-time; the review compares these across months)
    yt_views = yt.get("views") or sum((e.get("yt") or {}).get("views") or 0 for e in eps)
    tt_views = sum((e.get("tt") or {}).get("views") or 0 for e in eps)
    ig_views = sum((e.get("ig") or {}).get("views") or 0 for e in eps)
    lines += ["", "Followers per 1,000 views (all-time)"]
    for name, f, v in (("YouTube", yt.get("subscribers"), yt_views), ("TikTok", tt.get("followers"), tt_views),
                       ("Instagram", ig.get("followers"), ig_views)):
        if f is not None:
            lines.append(f"• {name}: {_per_1k(f, v) if v else '—'} ({_num(f)} followers, {_num(v)} views)")

    # 4. this week's Shorts, best and weakest by stayed-to-watch (views follow the feed's luck more than the video)
    week = [e for e in eps if (t - dt.timedelta(days=7)).isoformat() <= e["date"] < t.isoformat() and (e.get("yt") or {}).get("stayed_pct") is not None]
    if week:
        key = lambda e: (e["yt"].get("stayed_pct") or 0, e["yt"].get("views") or 0)
        best, worst = max(week, key=key), min(week, key=key)
        fmt = lambda e: (f"{e['saint']} ({e['date'][5:]}): {_num(e['yt'].get('views'))} views, "
                         f"stayed {_pct(e['yt'].get('stayed_pct'))}, viewed {_pct(e['yt'].get('avg_pct'))}")
        lines += ["", "This week's Shorts (with YouTube data so far)", f"• Best: {fmt(best)}"]
        if worst is not best:
            lines.append(f"• Weakest: {fmt(worst)}")

    if data.get("notes"):
        lines += ["", f"⚠️ {len(data['notes'])} data note(s) on the dashboard."]
    lines += ["", "allholysaints.com/dash/"]
    return "\n".join(lines)


def due(t=None):
    return (t or today()).weekday() == WEEKDAY


def send(data):
    import telegram
    telegram.send(build(data))
