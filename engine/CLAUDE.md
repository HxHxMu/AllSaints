# engine/ — Python pipeline

Entry: `pipeline.py {generate|poll|publish|youtube|yt-auth|yt-whoami|refresh-token|build-calendar|whoami}`. Run from the repo root with `.venv/bin/python engine/pipeline.py …`; one-off `python -c` imports need `cd engine` first.
Shared: `common.py` (config, Claude helper with model auto-pick and `USAGE` logging, state I/O).

## Flow
```
data/calendar.json (Wikidata: saints by feast day, sitelink count = fame proxy)
 → research.select_saint   Claude picks 1 of ~12 candidates for the date
 → research.gather_sources Wikipedia full text + Catholic Encyclopedia 1913 (Wikisource)
 → script.write_script     Claude, JSON beats (hook/who/story…/turn/close), 125–145 words, + youtube_title, share_cta,
                           + website fields: story (600–800 words, 5–8 paragraphs), patronages, places
 → script.fact_check       second Claude pass vs the same cached sources; checks beats + story; returns a script only when
                           beats need fixing, story fixes as find/replace pairs (applied in fact_check); may "reject"
 → script.translate_es     Haiku (common tier="haiku") → ep.es (Spanish name, hook, story, prayer…); failure never blocks
 → illustrate.illustrate   Gemini image per beat (brand.json → illustration); overrides from art/<ep_id>/
   (art.collect_candidates / assign_art only when config art_source = "commons")
 → tts.synthesize          Gemini TTS per beat + faster-whisper timings (fallback ElevenLabs), paced, loudnorm −16 LUFS
 → music.pick_bed        Luis's beds from assets/music/ (auto-prepared by music.py)
 → render.build_props/render  Remotion → video.mp4 (1080×1920 h264) + cover.jpg + preview.mp4
 → storage.upload          GitHub Release `ep-YYYY-MM-DD`
 → telegram.send_review    preview + ✅ Approve · 🔁 Redo (note) · ✏️ Edit caption · 🔄 New saint
poll (every 10 min): telegram.process_updates → publish_due
   → instagram.publish_reel → youtube.upload_short (independent; ≤3 retries; never re-posts the Reel)
```

## State (`state/`, committed by the bot)
- `config.json` (post_time — change via Telegram `/time`, timezone, youtube_channel, youtube_privacy, support_url, art_source…), `episodes/<id>.json`, `telegram.json`, `ig_token.enc`.
- Status flow: `generating → review → approved → publishing → published`; side states `redo_requested`, `failed` (≤3 retries, `attempts`).
- Episode extras: `youtube` {id, url, privacy | attempts, error}; `usage` (Claude tokens per call); `narrator` (`gemini:Riko` or `elevenlabs`); `rejected` (saints the fact-check turned down).
- Fact-check rejects: max 3 saints per date (`MAX_REJECTS`), then the episode fails without auto-retry (`GiveUp`); Telegram `/generate` resets `attempts`. ElevenLabs-narrated episodes get a ⚠️ in the review: free-tier audio isn't licensed for commercial use, redo them.

## Secrets (GitHub → Environments → **Production**; locally `.env`)
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `IG_ACCESS_TOKEN`, `IG_TOKEN_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Optional: `ELEVENLABS_VOICE_ID`, `ANTHROPIC_MODEL`.

## Workflows
`generate.yml` (daily 09:17 UTC + dispatch), `poll.yml` (odd minutes + extra runs at post time), `maintenance.yml` (weekly IG token refresh, monthly calendar; tasks `whoami`, `yt-whoami`). `scripts/commit-state.sh` commits state with rebase retries.

## YouTube
- Google Cloud project "All Saints"; OAuth app External, In production, unverified (fine, 100-user cap). Don't add a logo on Branding (forces verification); ignore the github.com home-page verification failure.
- Re-auth: `pipeline.py yt-auth <client_secret.json>` (writes `.env` + gh secrets). Luis's Google login also owns **Alianza Divina Collective**: always pick **@AllHolySaints**; `config.youtube_channel` makes uploads refuse any other channel. Verify with `yt-whoami`.
- Uploads are public (`youtube_privacy: "public"` since 2026-10-29; Google closed our audit as unnecessary; quota 100 uploads/day). `"private"` = publish from Studio by hand.
- Title: `script.youtube_title` (fallback "St. X, Region") + `#Shorts`; category Education; not made for kids. Description carries `brand.json → youtube.disclosure` (AI assistance), sources, art credits, the Ko-fi line when `config.support_url` is set, and the footer.

## Captions
Instagram: 5 hashtags max (`#AllHolySaints` + `caption.hashtags_base` + 2 saint tags) and one rotating CTA (`caption.ctas` + the script's `share_cta`). CTAs live in captions/descriptions only, never in the narration. Links aren't clickable in IG captions; the Ko-fi link is in the bio.

## Cost
- Model auto-picks the newest Sonnet; sources sent once as a cached context block shared by script and fact-check; per-call usage stored in `ep.usage`. Output/thinking tokens dominate cost.
- Haiku tier exists (`claude_json(..., tier="haiku")`, used by translate_es). Not built: route `research.select_saint` to Haiku; effort medium vs high comparison (needs a paid side-by-side, quote cost first); Batch API.
