"""All Saints pipeline CLI.

  python engine/pipeline.py generate [--date YYYY-MM-DD] [--max N] [--no-upload]
  python engine/pipeline.py poll            # Telegram updates + publish due episodes
  python engine/pipeline.py refresh-token
  python engine/pipeline.py youtube <episode>  # upload one episode's Short now
  python engine/pipeline.py books [episode|all]  # website books about the saint (all = only episodes without)
  python engine/pipeline.py yt-auth <client_secret.json>
  python engine/pipeline.py build-calendar
"""
import argparse, traceback
from common import WORK, load_episodes, load_episode
from generate import cmd_backfill_story, cmd_generate
from costs import cmd_cost
from publish import publish_due, publish_episode, publish_facebook, publish_threads, publish_tiktok, publish_youtube, youtube_cover, youtube_playlists, cmd_post
from checks import check_queue


def cmd_poll(a):
    import telegram
    actions = telegram.process_updates()
    telegram.resend_missing_reviews()
    if "generate" in actions:  # poll.yml starts generate.yml after its state commit: started from here, generate
        # checked out the commit before this poll's (no redo_requested yet) and found nothing to do (2026-11-08)
        WORK.mkdir(exist_ok=True)
        (WORK / "dispatch-generate").touch()
    publish_due()
    try:
        import shares
        shares.run_due()  # one-off scheduled posts (state/shares.json); never blocks the daily post
    except Exception:
        traceback.print_exc()
    try:
        import stories
        stories.run_due()  # nightly prayer card + seasonal Stories (state/stories.json)
    except Exception:
        traceback.print_exc()
    try:
        check_queue()  # evening heads-up about tomorrow
    except Exception:
        traceback.print_exc()


def _episodes(arg):
    """One episode by id, or every episode for "all"."""
    return [load_episode(arg)] if arg != "all" else list(load_episodes().values())


def _retry(publish, key, ep):
    """By hand: post one episode to one platform now, with a fresh set of attempts."""
    (ep.get(key) or {}).pop("attempts", None)
    publish(ep)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--date")
    g.add_argument("--max", type=int)
    g.add_argument("--no-upload", action="store_true")
    sub.add_parser("poll")
    pb = sub.add_parser("publish")
    pb.add_argument("episode", help="episode id, e.g. 2026-10-29 or intro")
    yb = sub.add_parser("youtube")
    yb.add_argument("episode")
    ya = sub.add_parser("yt-auth")
    ya.add_argument("client_secret", help="OAuth client JSON downloaded from Google Cloud (Desktop app)")
    sub.add_parser("yt-whoami")
    ga = sub.add_parser("gsc-auth", help="one-time: Search Console access for the dashboard (pick Luis's own Google account)")
    ga.add_argument("client_secret")
    mp = sub.add_parser("metrics", help="collect the dashboard's numbers and send them to allholysaints.com/dash/")
    mp.add_argument("--out", help="write the JSON to this file instead of sending it")
    sub.add_parser("dash-key", help="one-time: make the dashboard's ingest key (.env, GitHub, Cloudflare Pages)")
    sub.add_parser("fb-auth", help="one-time: store a never-expiring Facebook Page token (FB_PAGE_ID/FB_PAGE_TOKEN)")
    sub.add_parser("fb-whoami")
    fp = sub.add_parser("facebook", help="post one published episode's Reel to the Facebook Page now")
    fp.add_argument("episode")
    sub.add_parser("tt-auth", help="one-time: connect the TikTok account (TT_CLIENT_KEY/SECRET/TOKEN_KEY, state/tt_token.enc)")
    sub.add_parser("tt-whoami")
    sub.add_parser("th-auth", help="one-time: connect Threads (TH_APP_ID/SECRET/TOKEN_KEY, state/th_token.enc)")
    sub.add_parser("th-whoami")
    thp = sub.add_parser("threads", help="post one published episode's video to Threads now")
    thp.add_argument("episode")
    tp = sub.add_parser("tiktok", help="send one published episode's video to the TikTok inbox now")
    tp.add_argument("episode")
    fc = sub.add_parser("fb-cover", help="set the cover on Facebook Reels already posted (backfill)")
    fc.add_argument("episodes", nargs="+")
    yc = sub.add_parser("yt-cover", help="set cover.jpg as the thumbnail on Shorts already uploaded (backfill)")
    yc.add_argument("episodes", nargs="+")
    yp = sub.add_parser("yt-playlists", help="add published Shorts to their playlists (backfill / retry)")
    yp.add_argument("episode", nargs="?", default="all")
    lp = sub.add_parser("yt-localize", help="add the Spanish title/description to uploaded Shorts")
    lp.add_argument("episode", nargs="?", default="all")
    bp = sub.add_parser("books", help="look up books about the saint for the website (backfill / redo)")
    bp.add_argument("episode", nargs="?", default="all")
    sub.add_parser("cost", help="Claude cost per episode (from ep.usage) and per month")
    sp = sub.add_parser("backfill-story", help="website story + Spanish for episodes made before they existed, with a fresh fact-check")
    sp.add_argument("episode", help="episode id, or 'all' for every episode without a story")
    cp = sub.add_parser("compilation", help="the month's Shorts as one video, uploaded private (default: the month ending today)")
    cp.add_argument("month", nargs="?", help="YYYY-MM")
    cp.add_argument("--force", action="store_true", help="redo even if uploaded / before compilation_from")
    cp.add_argument("--no-upload", action="store_true", help="render only (work/compilation-YYYY-MM/)")
    po = sub.add_parser("post", help="publish an approved one-off carousel, state/posts/<id>.json (Instagram + Facebook)")
    po.add_argument("post_id")
    sub.add_parser("refresh-token")
    sub.add_parser("build-calendar")
    sub.add_parser("whoami")
    sub.add_parser("ig-media", help="what Instagram holds for a media id (type, product, status)").add_argument("media_id")
    a = p.parse_args()
    if a.cmd == "generate":
        cmd_generate(a)
    elif a.cmd == "poll":
        cmd_poll(a)
    elif a.cmd == "publish":
        ep = load_episode(a.episode)
        if not ep or ep.get("status") not in ("approved", "review") or not ep.get("assets"):
            raise SystemExit(f"Episode {a.episode} not found, already published, or not uploaded")
        publish_episode(ep)
    elif a.cmd == "youtube":
        ep = load_episode(a.episode)
        if not ep or not ep.get("assets"):
            raise SystemExit(f"Episode {a.episode} not found or not uploaded")
        _retry(publish_youtube, "youtube", ep)
    elif a.cmd in ("facebook", "threads", "tiktok"):
        _retry({"facebook": publish_facebook, "threads": publish_threads, "tiktok": publish_tiktok}[a.cmd], a.cmd, load_episode(a.episode))
    elif a.cmd == "yt-auth":
        import youtube
        youtube.authorize(a.client_secret)
    elif a.cmd == "gsc-auth":
        import youtube
        youtube.authorize(a.client_secret, scopes=youtube.GSC_SCOPE, refresh_key="GSC_REFRESH_TOKEN")
    elif a.cmd == "metrics":
        import metrics
        metrics.run(a.out)
    elif a.cmd == "dash-key":
        import metrics
        metrics.setup_key()
    elif a.cmd == "yt-playlists":
        for ep in _episodes(a.episode):
            if ep and (ep.get("youtube") or {}).get("id"):
                ep["youtube"].pop("playlist_attempts", None)
                youtube_playlists(ep)
    elif a.cmd == "yt-localize":
        import youtube
        for ep in _episodes(a.episode):
            if ep and ep.get("es") and (ep.get("youtube") or {}).get("id"):
                youtube.set_localizations(ep)
    elif a.cmd == "books":
        import books
        books.backfill(_episodes(a.episode), only_missing=a.episode == "all")
    elif a.cmd == "cost":
        cmd_cost(a)
    elif a.cmd == "backfill-story":
        cmd_backfill_story(a.episode)
    elif a.cmd == "compilation":
        import compilation
        compilation.make(a.month, force=a.force, upload=not a.no_upload)
    elif a.cmd == "fb-auth":
        import facebook
        facebook.authorize()
    elif a.cmd == "th-auth":
        import threads
        threads.authorize()
    elif a.cmd == "tt-auth":
        import tiktok
        tiktok.authorize()
    elif a.cmd == "whoami":
        import instagram
        print(instagram.me())
    elif a.cmd == "fb-whoami":
        import facebook
        print(facebook.me())
    elif a.cmd == "th-whoami":
        import threads
        print(threads.me())
    elif a.cmd == "tt-whoami":
        import tiktok
        print(tiktok.me())
    elif a.cmd == "yt-whoami":
        import youtube
        print(youtube.me())
    elif a.cmd == "fb-cover":
        import facebook, storage
        for ep_id in a.episodes:
            ep = load_episode(ep_id)
            facebook.set_cover(ep["facebook"]["id"], storage.resolve_direct(ep["assets"]["cover.jpg"]))
    elif a.cmd == "yt-cover":
        for ep_id in a.episodes:
            youtube_cover(load_episode(ep_id))
    elif a.cmd == "post":
        cmd_post(a.post_id)
    elif a.cmd == "refresh-token":
        import instagram, threads
        instagram.refresh_token()
        if threads.configured():
            threads.keep_alive()
    elif a.cmd == "build-calendar":
        import calendar_build
        calendar_build.main()
        import feasts_build  # the website's day pages read it
        feasts_build.main()
    elif a.cmd == "ig-media":
        import instagram
        print(*instagram.media_info(a.media_id))

if __name__ == "__main__":
    main()
