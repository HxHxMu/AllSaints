# engine/ — Python pipeline

Entry: `pipeline.py <cmd>` (`-h` lists the commands). Run from the repo root with `.venv/bin/python engine/pipeline.py …`; one-off `python -c` imports need `cd engine` first. Modules are flat (imported by bare name, no package).
- `pipeline.py` CLI + `cmd_poll` · `generate.py` the generate loop (`generate_one`, `backfill_story`) · `publish.py` the daily post and every platform after it (`publish_due`, `publish_episode`, `publish_once`), carousels · `checks.py` evening check · `captions.py` IG caption/hashtags · `costs.py` prices, `cmd_cost` · `cards.py` PIL/ffmpeg primitives for every card and video module · `youtube.py` upload/OAuth, `yt_meta.py` title/description/tags/Spanish (pure), `yt_playlists.py` playlists + covers · `stories.py` nightly card + seasonal Stories, `story_music.py` weekly music card, `o_antiphons.py` (texts in `data/o-antiphons.json`) · `common.py` config, Claude helper (model auto-pick, `USAGE`), state I/O.
- Workflow deps: `maintenance.yml` installs only `requests cryptography`, `poll.yml` adds `anthropic pillow` (no numpy). Keep heavy imports inside functions. Tests: `cd engine && ../.venv/bin/python -m unittest discover -p 'test_*.py'` (offline, platforms stubbed). Never run `poll`/`publish`/`post` locally to test: they act on real Telegram updates and post.

## Flow
```
data/calendar.json (Wikidata: saints by feast day, sitelink count = fame proxy)
 → research.select_saint   Claude picks 1 of ~12 candidates for the date (told which have Catholic references; prefers them)
                           config "pins" {"2026-12-17": "<qid>"} skips the pick (viewer requests; the qid may sit on any calendar day; ignored if already used or rejected)
 → research.gather_sources Wikipedia full text + up to 4 Catholic references found by Wikidata ID (CATHOLIC_REFS:
                           Catholic Encyclopedia/New Advent, causesanti.va, Santi e Beati, Nominis, Heiligenlexikon;
                           page text ≤8000 chars each), Wikisource Catholic Encyclopedia title search as fallback.
                           Wikipedia-only → fact-check confidence capped at 70 + ⚠️ in the Telegram review note
 → script.write_script     Claude, JSON beats (hook/who/story…/turn/close), 125–145 words, + youtube_title, share_cta,
                           + website fields: story (600–800 words, 5–8 paragraphs), patronages, places
 → script.fact_check       second Claude pass vs the same cached sources; checks beats + story; returns a script only when
                           beats need fixing, story fixes as find/replace pairs (applied in fact_check); may "reject"
 → script.translate_es     Haiku (common tier="haiku") → ep.es (Spanish name, hook, story, prayer…); failure never blocks
 → books.find              Open Library books whose title names the saint → ep.books (website; /nobooks in Telegram drops them)
 → illustrate.illustrate   Gemini image per beat (brand.json → illustration; the first art beat, which becomes the cover, also gets `cover_framing`: plain gold top fifth, head in the upper third, so grid crops keep the head); overrides from art/<ep_id>/
   (art.collect_candidates / assign_art only when config art_source = "commons")
 → tts.synthesize          Gemini TTS per beat + faster-whisper timings (fallback ElevenLabs), paced, loudnorm −16 LUFS
 → music.pick_bed        Luis's beds from assets/music/, rotated by date (neighbours differ; auto-prepared by music.py)
 → render.build_props/render  Remotion → video.mp4 (1080×1920 h264) + cover.jpg + preview.mp4
 → storage.upload          GitHub Release `ep-YYYY-MM-DD`
 → telegram.send_review    preview + ✅ Approve · 🔁 Redo (note) · ✏️ Edit caption · 🔄 New saint
poll (every 10 min): telegram.process_updates → publish_due
   → instagram.publish_reel → youtube.upload_short + facebook.publish_reel + tiktok.upload_draft + threads.publish_video (each independent; ≤3 retries; never re-posts the Reel)
   → shares.run_due (scheduled link/Reel posts) → stories.run_due (nightly prayer card, weekly music card from data/music.json, seasonal Stories)
   → check_queue (once a day after 20:00: Telegram if tomorrow is missing/failed/unapproved, the next days are empty, or yesterday never posted)
```

## Reliability rules
- **Record a post the moment the platform accepts it, then do the extras** (permalink lookup, Telegram note, covers, playlists). Anything that fails after that point logs and moves on; it must never send the item back to a state that posts it again. Applies to Reels (`publish_episode`), Shorts (`publish_youtube`), Facebook, `shares.py`, `stories.py`, carousels (`cmd_post` keys on `media_id`). Telegram notes after a success go through `_notify`. Before the daily Reel, `instagram.find_reel` looks for one with the same caption in the last 36 h and records it instead of posting (covers a publish that timed out after Instagram took it, and a run whose state commit never landed; if the check itself fails it posts anyway). Telegram's episode buttons (`EP_BUTTONS`) do nothing once an episode is publishing/published: Undo → Approve would re-post, Redo / New saint would regenerate a live episode.
- `common.http` retries network blips: connections that never opened (any method), and errors/5xx for GET/HEAD only. POSTs are never resent.
- Every workflow ends with `scripts/notify-failure.sh` on failure: one Telegram ⚠️ with the run link, not repeated while the job keeps failing (it checks the previous run). Per-post failures still report themselves (❌, ≤3 attempts).
- Missed days are reported, never posted late (a feast-day post a day late is wrong): the evening check says so.

## State (`state/`, committed by the bot)
- `checks.json` (date of the last evening check). `config.json` (post_time — change via Telegram `/time`, check_time (default 20:00), story_time (default 20:30), music_story (default "Sun 15:00", "" = off), timezone, youtube_channel, youtube_privacy, support_url, art_source, angles, pins…), `episodes/<id>.json`, `telegram.json`, `ig_token.enc`, `locations.json` (Instagram place IDs, Telegram `/loc`; see `docs/engine/meta.md`).
- Status flow: `generating → review → approved → publishing → published`; side states `redo_requested`, `failed` (≤3 retries, `attempts`).
- Episode extras: `slug` / `es.slug` (the web page address, fixed at publish by `common.assign_slugs`, never changed: a name another episode owns gets `-YYYY`, then `-YYYY-MM-DD`; the site and YouTube links read it); `youtube` {id, url, privacy | attempts, error}; `usage` (Claude tokens per call); `narrator` (`gemini:Riko` or `elevenlabs`); `rejected` (saints the fact-check turned down).
- Fact-check rejects: max 3 saints per date (`MAX_REJECTS`), then the episode fails without auto-retry (`GiveUp`); Telegram `/generate` resets `attempts`. ElevenLabs-narrated episodes get a ⚠️ in the review: free-tier audio isn't licensed for commercial use, redo them.

## Secrets (GitHub → Environments → **Production**; locally `.env`)
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `IG_ACCESS_TOKEN`, `IG_TOKEN_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `FB_PAGE_ID`, `FB_PAGE_TOKEN`, `TT_CLIENT_KEY`, `TT_CLIENT_SECRET`, `TT_TOKEN_KEY`, `TH_APP_ID`, `TH_APP_SECRET`, `TH_TOKEN_KEY`. Optional: `ELEVENLABS_VOICE_ID`, `ANTHROPIC_MODEL`. Dashboard: `DASH_INGEST_KEY` (also in Cloudflare Pages; `pipeline.py dash-key`), `GSC_REFRESH_TOKEN` (`pipeline.py gsc-auth`).

## Workflows
`generate.yml` (daily 09:17 UTC + dispatch), `poll.yml` (odd minutes + extra runs at post time), `maintenance.yml` (weekly IG token refresh, monthly calendar, nightly 10:17 UTC dashboard `metrics`; tasks `whoami`, `yt-whoami`), `compilation.yml` (15:07 UTC on the 28th–31st and 1st–3rd; see below), `site.yml` (website build check: on pushes touching site/state/brand, and called by poll after a commit that rebuilds the site; a failure sends Telegram ⚠️ — bot pushes use GITHUB_TOKEN, which starts no push workflows, hence the call). `scripts/commit-state.sh` commits state with rebase retries.

## Captions
Instagram: 5 hashtags max (`#AllHolySaints` + `caption.hashtags_base` + 2 saint tags) and one rotating CTA (`caption.ctas` + the script's `share_cta`). CTAs live in captions/descriptions only, never in the narration. Links aren't clickable in IG captions; the Ko-fi link is in the bio.

## Details (read when relevant)
| Topic | Doc |
|---|---|
| YouTube: OAuth, channel guard (`config.youtube_channel` refuses other channels), playlists, covers, titles | `docs/engine/youtube.md` |
| Facebook Page, Threads, Instagram + FB Stories, carousels, shares | `docs/engine/meta.md` |
| TikTok inbox drafts (Sandbox), tokens | `docs/engine/tiktok.md` |
| Monthly compilation, sung-prayer videos | `docs/engine/compilation.md` |
| Cost, model tiers, dashboard (`metrics.py`; never written to `state/`), backfill-story | `docs/engine/cost-dashboard.md` |
