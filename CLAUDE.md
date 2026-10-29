# CLAUDE.md — A.S.† (All Saints) handoff

Read this first. It is the source of truth for where the project stands.
Owner: Luis Bonilla (designer / producer / web dev). Repo: https://github.com/HxHxMu/AllSaints (public).
Local working copy: `/Volumes/lebe/Dev/AllSaints` (external drive — see "Gotchas"). Python: `.venv/bin/python`.

## What this is
An automated devotional short-video channel: **one ~60 s vertical video per day about a lesser-known Catholic saint, posted on their feast day** — as an Instagram Reel and a YouTube Short.
AI does research → script → fact-check → art → narration → render. **Nothing posts without Luis tapping Approve in Telegram.**

## Decisions already made (don't re-ask)
| Topic | Decision |
|---|---|
| Name / mark | **All Saints**, monogram **A.S.†** (halo ring + A†S). Tagline: "The saints the world forgot. Heaven didn't." |
| Platforms | **Instagram Reels** — **@all.holy.saints**. **YouTube Shorts** — **@AllHolySaints** (same MP4, own title/description; Shorts only for now, no long-form compilations yet). |
| Scope | Canonized saints (incl. pre-congregation), **Eastern Catholic** saints, **early Church martyrs**. *Not* Blesseds/Venerables. Must be venerated in the Catholic Church. Lesser-known only. |
| Tone | **Devotional**: reverent story, ends with "Saint ___, pray for us." History vs. tradition clearly separated ("tradition holds…"). |
| Visuals | **AI-painted Byzantine icons** (Gemini image, `brand.json` → `illustration`) per beat, slow Ken Burns + branded overlays (globe map zoom, name card, gold captions). Per-episode overrides: drop files in `art/<ep_id>/`. Commons art still available via config `art_source: "commons"`. |
| Voice | **Gemini TTS (paid)**, voice **"Riko"**, director's notes in `brand.json` → `voice.gemini`; word timings via faster-whisper. **ElevenLabs = backup only, free tier** — free-tier audio isn't licensed for commercial use, so a fallback-narrated episode should be redone once the channel earns. |
| Music | **Luis produces the beds** → `assets/music/` (`allsaints-2.mp3` in use; beds auto-prepared by `music.py`). |
| Cadence | Daily, on feast day, **7:30 AM America/New_York** (configurable via Telegram `/time`). YouTube uploads at the same time. |
| Approval | Telegram bot: ✅ Approve · 🔁 Redo (with note) · ✏️ Edit caption · 🔄 New saint. Generate ~7 days ahead, approve in batches. One Approve covers both platforms. |
| Hosting | GitHub Actions on the **public** repo (free minutes; release assets give Instagram a public video URL). |
| Budget | ~$20–60/mo: Anthropic API + Gemini (TTS + images). ElevenLabs free. Goal: the channel pays for itself (see Monetization). |
| AI disclosure | Every YouTube description says: AI-assisted research/writing, checked against sources, human-approved, AI voice, AI icon art (`brand.json` → `youtube.disclosure`). |

## Monetization (plan, 2026-10-28 — mostly not built yet)
- Phase 1 (0–2k followers): saint web pages with affiliate "go deeper" links (books, medals), daily email list, support link. Support tagline: **"Help keep the forgotten remembered."** (button: "Light a candle"). Never paywall prayers; no guilt/urgency copy.
- Phase 2: cross-post — **YouTube Shorts done**; Facebook Reels possible later.
- Phase 3: digital products (printable calendars, prayer cards), print-on-demand, **B2B daily-saint subscription for Catholic schools/parishes**.
- Phase 4 (10k+): sponsors, IG subscriptions.
- **Website: not started.** Open questions to Luis: host (Vercel Hobby forbids commercial use → Cloudflare Pages recommended), domain (buy ~$10/yr vs free subdomain), code in `/site` of this repo vs separate, video on saint pages (IG embed / self-host / cover+link / YT embed). Pages would be generated from `state/episodes/*.json` on publish.
- Cost idea not built: route cheap Claude steps (`research.select_saint`) to Haiku via a per-call tier; keep script/fact-check on Sonnet.

## Architecture
```
data/calendar.json (Wikidata: saints by feast day, sitelink count = fame proxy)
 → research.select_saint   Claude picks 1 of ~12 candidates for the date
 → research.gather_sources Wikipedia full text + Catholic Encyclopedia 1913 (Wikisource)
 → script.write_script     Claude, JSON beats (hook/who/story…/turn/close), 125–145 words, + youtube_title
 → script.fact_check       second Claude pass vs sources; may fix or reject
 → illustrate.illustrate   Gemini image per beat (Byzantine icon style); overrides from art/<ep_id>/
   (art.collect_candidates / assign_art only when art_source = "commons")
 → tts.synthesize          Gemini TTS per beat + Whisper timings (fallback ElevenLabs), paced, loudnorm −16 LUFS
 → render.build_props/render  Remotion → video.mp4 (1080×1920 h264) + cover.jpg
 → storage.upload          GitHub Release `ep-YYYY-MM-DD`
 → telegram.send_review    preview + buttons
poll (every 10 min): telegram.process_updates → publish_due
   → instagram.publish_reel → youtube.upload_short (independent; ≤3 retries; never re-posts the Reel)
```

### Layout
- `brand/brand.json` — colors, fonts, motion, voice, illustration style, YouTube disclosure/footer + **writing rules used verbatim in prompts**. `brand/make_logo.py` → `brand/logo/*`.
- `video/` — Remotion 4 project (JSX). `src/Episode.jsx`, `src/components.jsx` (ArtScene, MapScene globe, TitleCard, CloseScene+outro, Captions, Atmosphere, Credit), `src/Cover.jsx`, `src/sample.json`.
- `engine/` — Python pipeline. Entry: `engine/pipeline.py {generate|poll|publish|youtube|yt-auth|yt-whoami|refresh-token|build-calendar|whoami}`. Shared: `common.py` (config, Claude helper w/ model auto-pick, state I/O). `youtube.py` (OAuth refresh-token upload, channel guard), `illustrate.py`, `music.py`.
- `state/` — committed by the bot. `config.json`, `episodes/<id>.json` (one file per episode; `youtube` sub-object tracks the Short), `telegram.json`, `ig_token.enc`.
- `.github/workflows/` — `generate.yml` (daily 09:17 UTC + dispatch), `poll.yml` (odd minutes + extra runs at post time), `maintenance.yml` (weekly IG token refresh, monthly calendar; tasks `whoami`, `yt-whoami`). `scripts/commit-state.sh` commits state with rebase retries.
- `PRIVACY.md`, `TERMS.md` — linked from the Google OAuth consent screen. Don't delete/move.

### Episode status flow
`generating → review → approved → publishing → published`; side states `redo_requested`, `failed` (retries ≤3, `attempts` counter). YouTube state lives separately in `ep.youtube` (`id`, `url`, `privacy` or `attempts`, `error`).

### Secrets (GitHub → Settings → Environments → **Production**)
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `IG_ACCESS_TOKEN`, `IG_TOKEN_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Optional env: `ELEVENLABS_VOICE_ID`, `ANTHROPIC_MODEL`.
Locally they live in `.env` (gitignored). **Never print/cat `.env`; never ask Luis to paste keys in chat.** Check key *names* only (`grep -o '^[A-Z_]*=' .env`).

### YouTube specifics
- Google Cloud project "All Saints": YouTube Data API v3 enabled; OAuth app **External, In production, unverified** (fine — 100-user cap, Luis is 1). Don't add a logo on Branding (forces verification). Home-page branding verification fails for github.com — ignore it.
- Re-auth: `.venv/bin/python engine/pipeline.py yt-auth <client_secret.json>` (writes `.env` + gh secrets). Luis's Google login also owns **Alianza Divina Collective** — always pick **@AllHolySaints**; `config.youtube_channel` makes uploads refuse any other channel. Verify with `yt-whoami`.
- **Uploads are private** (`config.youtube_privacy: "private"`) until Google's YouTube API compliance audit passes — Luis publishes from Studio via the Telegram link. After approval → set `"public"`.
- Title from `script.youtube_title` (fallback "St. X, Region") + `#Shorts`; category Education; not made for kids.

## Status (2026-10-28)
**Live and working:** calendar built; full generate pipeline runs on Actions (research → script → fact-check → icon art → Gemini voice → render → release → Telegram review); Telegram approval flow; Instagram publishing (**intro Reel published**); YouTube upload (private test Short of 10-28 uploaded to @AllHolySaints and checked in Studio, then to be deleted).
**Launch date: 2026-10-29.** Queue: 10-29 and 11-01 approved; 10-28, 10-30, 10-31, 11-02–11-04 in review.
**Not yet exercised live:** a scheduled YouTube upload from `poll.yml` on Actions (first one: 10-29); `youtube_title` from a freshly generated script.

## Known issues / TODO (small)
- `pipeline.generate_one`: fact-check `reject` recurses with no cap → add max 3 saints per date.
- Telegram `/generate` should reset `attempts` on `failed` episodes.
- ElevenLabs fallback is silent (only a log line) → record the narrator in the episode and flag it in the Telegram review.
- Map place label can collide with captions when the location sits low on the globe.
- Render speed ~0.3 s/frame on 2 cores; grain uses PNG tiles; close-scene blur at ¼ res — keep it that way.
- Videos are ~45–70 MB (10-28 was 69 MB); Telegram preview uses a downscaled `preview.mp4`.
- Remotion license: free for individuals/≤3-person companies — fine for now.

## Next steps
1. YouTube API audit **submitted 2026-10-28** (evidence in `work/audit/`). On approval → `youtube_privacy: "public"`. Test Short UrIN6H8q_18 is the reviewer's example — delete after review, before 10-28's real upload.
2. Watch the first live day (10-29): Reel posts + private Short uploads; publish the Short from Studio.
3. Keep the review queue ≥7 days approved.
4. Website (see Monetization open questions) → saint pages, email signup, support page.
5. Haiku routing for cheap Claude steps; flag ElevenLabs-fallback episodes.

## Commands
```bash
pip install -r requirements.txt && (cd video && npm ci)
cd video && npx remotion studio src/index.js          # preview templates with src/sample.json
.venv/bin/python engine/pipeline.py generate --date 2026-11-05 --no-upload
.venv/bin/python engine/pipeline.py poll              # needs TELEGRAM_BOT_TOKEN etc.
.venv/bin/python engine/pipeline.py youtube <ep_id>   # upload one episode's Short now
.venv/bin/python engine/pipeline.py yt-whoami         # must print @allholysaints
```

## Gotchas
- **External drive (`/Volumes/lebe`)**: macOS writes `._*` files everywhere (gitignored; `load_episodes` skips them). Use `git config core.filemode false`.
- The bot commits `state/` constantly — `git pull --rebase --autostash` before pushing.
- `node_modules/` is not in the repo — run `npm ci` in `video/`.
- `work/` and `video/public/episodes/*` (except `sample/`) are scratch, gitignored.
- Keep writing rules in `brand/brand.json`, not hard-coded in prompts — prompts read them.
- Captions: 5 Instagram hashtags max (`#AllHolySaints` + `caption.hashtags_base` + 2 saint tags) and one rotating CTA (`caption.ctas` + the script's `share_cta`). CTAs live in captions/descriptions only, never in the narration; no engagement bait.
- Accuracy and reverence beat engagement tricks. Never invent saint quotes; label legend as tradition.
