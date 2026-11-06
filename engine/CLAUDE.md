# engine/ — Python pipeline

Entry: `pipeline.py {generate|poll|publish|youtube|yt-playlists|yt-localize|books|backfill-story|cost|compilation|yt-auth|yt-whoami|gsc-auth|metrics|dash-key|facebook|fb-auth|fb-whoami|tt-auth|tt-whoami|tiktok|th-auth|th-whoami|threads|refresh-token|build-calendar|whoami}`. Run from the repo root with `.venv/bin/python engine/pipeline.py …`; one-off `python -c` imports need `cd engine` first.
Shared: `common.py` (config, Claude helper with model auto-pick and `USAGE` logging, state I/O).

## Flow
```
data/calendar.json (Wikidata: saints by feast day, sitelink count = fame proxy)
 → research.select_saint   Claude picks 1 of ~12 candidates for the date (told which have Catholic references; prefers them)
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
 → illustrate.illustrate   Gemini image per beat (brand.json → illustration); overrides from art/<ep_id>/
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
- **Record a post the moment the platform accepts it, then do the extras** (permalink lookup, Telegram note, covers, playlists). Anything that fails after that point logs and moves on; it must never send the item back to a state that posts it again. Applies to Reels (`publish_episode`), Shorts (`publish_youtube`), Facebook, `shares.py`, `stories.py`, carousels (`cmd_post` keys on `media_id`). Telegram notes after a success go through `_notify`.
- `common.http` retries network blips: connections that never opened (any method), and errors/5xx for GET/HEAD only. POSTs are never resent.
- Every workflow ends with `scripts/notify-failure.sh` on failure: one Telegram ⚠️ with the run link, not repeated while the job keeps failing (it checks the previous run). Per-post failures still report themselves (❌, ≤3 attempts).
- Missed days are reported, never posted late (a feast-day post a day late is wrong): the evening check says so.

## State (`state/`, committed by the bot)
- `checks.json` (date of the last evening check). `config.json` (post_time — change via Telegram `/time`, check_time (default 20:00), story_time (default 20:30), music_story (default "Sun 15:00", "" = off), timezone, youtube_channel, youtube_privacy, support_url, art_source…), `episodes/<id>.json`, `telegram.json`, `ig_token.enc`.
- Status flow: `generating → review → approved → publishing → published`; side states `redo_requested`, `failed` (≤3 retries, `attempts`).
- Episode extras: `slug` / `es.slug` (the web page address, fixed at publish by `common.assign_slugs`, never changed: a name another episode owns gets `-YYYY`, then `-YYYY-MM-DD`; the site and YouTube links read it); `youtube` {id, url, privacy | attempts, error}; `usage` (Claude tokens per call); `narrator` (`gemini:Riko` or `elevenlabs`); `rejected` (saints the fact-check turned down).
- Fact-check rejects: max 3 saints per date (`MAX_REJECTS`), then the episode fails without auto-retry (`GiveUp`); Telegram `/generate` resets `attempts`. ElevenLabs-narrated episodes get a ⚠️ in the review: free-tier audio isn't licensed for commercial use, redo them.

## Secrets (GitHub → Environments → **Production**; locally `.env`)
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `IG_ACCESS_TOKEN`, `IG_TOKEN_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `FB_PAGE_ID`, `FB_PAGE_TOKEN`, `TT_CLIENT_KEY`, `TT_CLIENT_SECRET`, `TT_TOKEN_KEY`, `TH_APP_ID`, `TH_APP_SECRET`, `TH_TOKEN_KEY`. Optional: `ELEVENLABS_VOICE_ID`, `ANTHROPIC_MODEL`. Dashboard: `DASH_INGEST_KEY` (also in Cloudflare Pages; `pipeline.py dash-key`), `GSC_REFRESH_TOKEN` (`pipeline.py gsc-auth`).

## Backfill
`pipeline.py backfill-story <ep_id|all>`: for episodes made before the website story/Spanish existed (10-29…11-04, done 2026-11-01). Fresh sources → `script.write_story` → fact-check of the whole script; only story fixes apply (the video is made), beat problems go in `ep.recheck` (`beats_need_fixing`) for Luis to judge (🔁 Redo if serious).

## Workflows
`generate.yml` (daily 09:17 UTC + dispatch), `poll.yml` (odd minutes + extra runs at post time), `maintenance.yml` (weekly IG token refresh, monthly calendar, nightly 10:17 UTC dashboard `metrics`; tasks `whoami`, `yt-whoami`), `compilation.yml` (15:07 UTC on the 28th–31st and 1st–3rd; see below), `site.yml` (website build check: on pushes touching site/state/brand, and called by poll after a commit that rebuilds the site; a failure sends Telegram ⚠️ — bot pushes use GITHUB_TOKEN, which starts no push workflows, hence the call). `scripts/commit-state.sh` commits state with rebase retries.

## YouTube
- Google Cloud project "All Saints"; OAuth app External, In production, unverified (fine, 100-user cap). Don't add a logo on Branding (forces verification); ignore the github.com home-page verification failure.
- Re-auth: `pipeline.py yt-auth <client_secret.json>` (writes `.env` + gh secrets). Luis's Google login also owns **Alianza Divina Collective**: always pick **@AllHolySaints**; `config.youtube_channel` makes uploads refuse any other channel. Verify with `yt-whoami`.
- Uploads are public (`youtube_privacy: "public"` since 2026-10-29; Google closed our audit as unnecessary; quota 100 uploads/day). `"private"` = publish from Studio by hand.
- Playlists: after each upload the Short goes into "Saints of <Month>" (feast month) and "Saints of <continent>" (`youtube.continent`: Haiku sorts `saint.region` into Africa / Asia / Europe / the Americas / the Middle East / Oceania once, cached as `ep.continent`). Playlists are created public on first use; titles/description in `brand.json → youtube.playlists`. State: `ep.youtube.playlists`, `playlists_done`, `playlist_attempts` (≤3, today's episode only; a fresh playlist 409s for a few seconds, so inserts retry; reruns skip videos already in a playlist). Backfill/retry: `pipeline.py yt-playlists [ep_id|all]`. Covers: `playlist_cover.py`, square 1080 (the API only takes type "hero" at 1:1, and YouTube shows the whole square inside its 16:9 card, so it's designed to read small: icon full-bleed, face in the top third, big Cinzel words on soot at the bottom). Icon from the episode that opens the playlist (clean `art.jpg`, else the painted band of `cover.jpg`); Haiku (`locate_saint`) finds the saint's face to frame the crop. A new playlist gets its cover automatically (failure only logs). Redo one by hand: `playlist_cover.py "Saints of X" art.jpg out.jpg [focus face_y zoom]`, then `youtube.set_playlist_cover(token, playlist_id, jpg)` (deletes the old image first; the API's update call doesn't work). Needs the `youtube.force-ssl` scope (added 2026-10-30: rerun `yt-auth` once).
- Cover: right after the upload, `pipeline.youtube_cover` sets the episode's `cover.jpg` as the thumbnail (`youtube.set_thumbnail`; without it YouTube shows a frame it picks); `ep.youtube.cover` = true once set; a failure only logs. Backfill: `pipeline.py yt-cover <ep_id> …` (Shorts before 2026-11-04 done by hand that day).
- Title: `script.youtube_title` (fallback "St. X, Region") + `#Shorts`; category Education; not made for kids. Spanish title/description go in as YouTube `localizations.es` when `ep.es` exists (shown to Spanish-language viewers and search; backfill `pipeline.py yt-localize [ep|all]`). Both descriptions link the saint's web page ("Read the full story"; `youtube.page_url` mirrors the site's slug rule). Description carries `brand.json → youtube.disclosure` (AI assistance), sources, art credits, the Ko-fi line when `config.support_url` is set, and the footer.

## Facebook Page
- Instagram's "share to Facebook" setting doesn't apply to API-published Reels, so `facebook.publish_reel` posts the same video to the Page (Graph `video_reels`: start → upload by `file_url`, falling back to the file → finish PUBLISHED with the IG caption). Runs only after the Reel is on Instagram; state `ep.facebook` {id, url | attempts, error}; ≤3 attempts; never blocks Instagram/YouTube. Skipped until `FB_PAGE_ID`/`FB_PAGE_TOKEN` exist.
- Setup: Meta app (the Instagram one) → add Facebook Login; Graph API Explorer → user token with `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, tick the Page → `pipeline.py fb-auth` (hidden prompts: App ID, secret, token; exchanges for a never-expiring Page token, writes `.env` + gh secrets). Check: `fb-whoami`. Retry/backfill one: `pipeline.py facebook <ep_id>`. The cover: Facebook ignores it at publish, so `facebook.set_cover` uploads `cover.jpg` as the preferred thumbnail right after (failure only logs); backfill with `pipeline.py fb-cover <ep_id> …` (Reels before 2026-11-03 got a frame Facebook picked).
- One-off carousels: `state/posts/<id>.json` (image URLs on a GitHub release `post-<id>`, IG caption, FB message), published by `pipeline.py post <id>` (Instagram `publish_carousel`, Facebook `post_photos`; reruns skip a platform already done). Instagram's token exists only in GitHub secrets, so run it as Maintenance → task `post <id>`. Only after Luis approves the slides and text in chat.
- One-off scheduled posts: `state/shares.json` (`shares.py`, run by `poll`): Page link posts at a set time, e.g. a sung-prayer video on release day. A YouTube link waits until the video is public (FB builds the preview at posting time); ≤3 attempts; Telegram reports each result. Entries are added by hand once Luis approves the text.

## TikTok (`tiktok.py`)
- TikTok only lets audited apps post publicly and won't audit a tool that posts to its owner's own account ("A utility tool to help upload contents to the account(s) you or your team manages" is listed as unacceptable), so the bot uses **upload to inbox** (scope `video.upload`): after the Reel is on Instagram, `upload_draft` sends `video.mp4` (FILE_UPLOAD, 10 MB chunks) to @allholysaints's TikTok inbox; Telegram then sends the caption to paste. Luis taps TikTok's notification, pastes it, picks a cover frame (the API can't set one; pre-Nov-13 renders start on a dark frame), turns on "AI-generated content" and posts. The API can't send a caption or the AI label with a draft. Max 5 pending drafts per 24 h.
- State `ep.tiktok` {publish_id, status, sent_at | attempts, error}; ≤3 attempts; never blocks the others. Skipped until the three secrets and `state/tt_token.enc` exist.
- Tokens: access 2 h, refresh 180 days and **replaced on every refresh**, so they live encrypted (`TT_TOKEN_KEY`) in `state/tt_token.enc`, rewritten by whichever job refreshes; poll/maintenance commit it. Don't refresh from a local run without committing the file (Actions would hold a dead token). Daily use keeps it alive; after 180 days idle, rerun `tt-auth`.
- Runs on the app's **Sandbox** ("All Saints bot", app "All Holy Saints"; @allholysaints is its target user), so no review was needed; connected 2026-11-06, first draft Nov 5. Domain verified by URL prefix `https://allholysaints.com/` (signature file in `site/public/tiktokpub….txt`: keep it). Review (Production) would need a demo video.
- Setup: developers.tiktok.com app with Login Kit (redirect URI exactly `https://allholysaints.com/`) + Content Posting API (upload only, no Direct Post), scopes `user.info.basic`, `video.upload`; `pipeline.py tt-auth` (hidden prompts: client key, secret, then the address TikTok redirects to; Enter instead reads `work/tiktok/redirect.txt`, for when the browser has no address bar), then commit `state/tt_token.enc`. Check: `tt-whoami` (Maintenance task, so the refreshed token gets committed). Retry/backfill one: `pipeline.py tiktok <ep_id>`.

## Threads (`threads.py`)
- Instagram's "share to Threads" switch skips API posts (like its Facebook one), so after the Reel is on Instagram `publish_threads` posts `video.mp4` to @all.holy.saints's Threads (graph.threads.net: VIDEO container by URL → wait FINISHED → `threads_publish`). Text ≤490 chars (`build_text`: hook, name · feast, summary trimmed to fit, prayer, saint page, art credit). State `ep.threads` {id, url, published_at | attempts, error}; ≤3 attempts; never blocks the others. Skipped until `TH_TOKEN_KEY` and `state/th_token.enc` exist.
- Token: long-lived, 60 days, encrypted in `state/th_token.enc`; any run renews it once it is under 15 days from expiry (poll/maintenance commit it). Daily posting keeps it alive; once expired, rerun `th-auth`.
- Setup: Meta app → use case "Access the Threads API" (`threads_basic`, `threads_content_publish`; redirect callback `https://allholysaints.com/`; @all.holy.saints added as a Threads tester and accepted in Threads → Settings → Account → Website permissions) → `pipeline.py th-auth` (hidden prompts: the *Threads* app id and secret, then the redirect address; Enter reads `work/threads/redirect.txt`), then commit `state/th_token.enc`. Check: `th-whoami`. Retry/backfill one: `pipeline.py threads <ep_id>`.

## Instagram Stories (`stories.py`, run by `poll`, no AI)
- Nightly card from `config.story_time` (default 20:30): the painted band of today's `cover.jpg`, the manuscript date, the episode's close beat ("Saint X, pray for us."), and "Tomorrow: St. Y" + region when tomorrow's episode is approved. Only once today's Reel is published; hosted as `story.jpg` on the episode release; `instagram.publish_story` (image Story, no caption, no link stickers via the API). State `ep.story` {media_id | attempts, error}, ≤3 attempts, failures to Telegram. Render one locally: `python engine/stories.py night <ep_id>`.
- Facebook Page Stories: Instagram's "share story to Facebook" skips API posts, so every card (nightly and seasonal) also goes to the Page once it's on Instagram: `facebook.publish_story` (photo uploaded unpublished → `/{page}/photo_stories`). Its own state (`ep.story_fb`, the seasonal entry's `facebook`) {id | attempts, error}, ≤3 attempts, ❌ to Telegram, never re-posts the Instagram one. Started 2026-11-04; earlier cards have no `image` and are skipped.
- Seasonal cards: `state/stories.json` entries {id, at, image, status}; `draft` waits for Luis's OK in chat (flip to `pending`). O Antiphons Dec 17–23 at 12:30: `stories.py o-antiphons <year> [--upload]` (typeset on soot; Latin from the Roman Office, English is All Saints' own literal translation since ICEL's is copyrighted; images on release `stories-o-antiphons-<year>`). Uploading locally needs `GITHUB_REPOSITORY=HxHxMu/AllSaints GITHUB_TOKEN=$(gh auth token)`.
- Instagram's top ~150 px (progress bar, name) and bottom ~250 px (reply bar) are covered: text stays between `TOP` and `SAFE_BOTTOM`.

## Monthly compilation (`compilation.py`)
- On a month's last day (after the 7:30 post) the month's **published** Shorts become one 16:9 video: each Short centred on its own blurred icon, saint name/feast on the left, monogram on the right; a "Saints of <Month>" title card and an end card (tagline + `youtube.footer`) over `assets/music/allsaints-2.mp3`. Chapters per saint, links to each saint's page, the disclosure, Spanish `localizations` when every episode has `es`. Custom thumbnail (five icons + month). No AI, ~1 min of runner time per saint.
- Uploads **private**, then Telegram gets a 📣 Publish button (`comppublish:YYYY-MM`); the tap makes it public and puts it first in "Saints of <Month>". Ignoring it leaves it private.
- State `state/compilations/YYYY-MM.json` (status rendering → review → published | failed, `attempts` ≤ 3; the 1st–3rd runs retry a failed month). Skipped with fewer than 3 published episodes. First month: `config.compilation_from` ("2026-11").
- By hand: `pipeline.py compilation 2026-11 [--no-upload] [--force]` (`--no-upload` renders to `work/compilation-YYYY-MM/` only).

## Sung prayers (`sung_video.py`)
Original music on prayers written by saints (`docs/sung-prayers/`: research catalogue, one lyric master `.md` + video spec `.json` per release). `python engine/sung_video.py docs/sung-prayers/<spec>.json [--frames]` makes a 1920×1080 lyric video from `work/sung/NN/` (audio + icon): icon left, Latin + English per stanza cross-faded on soot, title cards, credits. `--frames` = layout check only. Stanza times come from a faster-whisper pass over the song. Upload is by hand (private first); not part of the daily pipeline.

## Captions
Instagram: 5 hashtags max (`#AllHolySaints` + `caption.hashtags_base` + 2 saint tags) and one rotating CTA (`caption.ctas` + the script's `share_cta`). CTAs live in captions/descriptions only, never in the narration. Links aren't clickable in IG captions; the Ko-fi link is in the bio.

## Cost
- Model auto-picks the newest Sonnet; sources sent once as a cached context block shared by script and fact-check; per-call usage stored in `ep.usage`. Output/thinking tokens dominate cost.
- `pipeline.py cost`: Claude $ per episode from `ep.usage` (prices in `pipeline.PRICES`) plus Gemini as a flat `GEMINI_PER_EPISODE` (~$0.22: Nano Banana 2 Lite art + 3.8 Flash TTS, measured in Google Cloud billing Oct 29–31; a 7-episode batch day costs ~$1.80 and can hit Tier 1 429s). 2026-11-01: ~$0.17/episode Claude + ~$0.22 Gemini ≈ $0.39/episode, ~$12 per 30 days all in (script ~9¢, fact-check ~7¢, select ~1.4¢).
- Haiku tier exists (`claude_json(..., tier="haiku")`, used by translate_es). `select_saint` stays on Sonnet: tested 2026-10-30 on Nov 7–10, Haiku matched or was fine on 3 dates but picked Herodion of Patras for Nov 10 (mostly legend, main feast April 8; Sonnet chose Justus of Canterbury). It would save ~1.3¢/episode (~$0.40/mo), and one bad pick costs a fact-check reject plus a new script (~15¢). Not built: effort medium vs high comparison (needs a paid side-by-side, quote cost first); Batch API.

## Dashboard (`metrics.py`, nightly via Maintenance, no AI)
Private page at allholysaints.com/dash/ (code `site/src/pages/dash/`, `site/functions/api/dash-*.ts`, `kofi.ts`; setup in `docs/website.md`). `metrics.collect` gathers the queue (next 8 days, problems), cost (`call_cost` + `GEMINI_PER_EPISODE`), per-Short numbers (YouTube Data API views/likes; Analytics API avg % viewed, shares, subscribers, views per day, countries; Instagram Reel insights; WHO-line word counts for the retention question) and Search Console (28 days: daily, queries, pages, countries), then POSTs it to `/api/dash-ingest` (bearer `DASH_INGEST_KEY`) → Cloudflare KV `DASH`. **Never written to `state/`: the repo is public.** Each source fails on its own and shows as a note on the page. YouTube Analytics needs the `yt-analytics.readonly` scope (added 2026-11-05: rerun `yt-auth` once); Search Console uses Luis's own Google account (`gsc-auth`, same OAuth client, `GSC_REFRESH_TOKEN`). Local check: `pipeline.py metrics --out work/metrics.json`.
