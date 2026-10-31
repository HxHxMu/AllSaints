# engine/ — Python pipeline

Entry: `pipeline.py {generate|poll|publish|youtube|yt-playlists|books|yt-auth|yt-whoami|refresh-token|build-calendar|whoami}`. Run from the repo root with `.venv/bin/python engine/pipeline.py …`; one-off `python -c` imports need `cd engine` first.
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
 → books.find              Open Library books whose title names the saint → ep.books (website; /nobooks in Telegram drops them)
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
- Playlists: after each upload the Short goes into "Saints of <Month>" (feast month) and "Saints of <continent>" (`youtube.continent`: Haiku sorts `saint.region` into Africa / Asia / Europe / the Americas / the Middle East / Oceania once, cached as `ep.continent`). Playlists are created public on first use; titles/description in `brand.json → youtube.playlists`. State: `ep.youtube.playlists`, `playlists_done`, `playlist_attempts` (≤3, today's episode only; a fresh playlist 409s for a few seconds, so inserts retry; reruns skip videos already in a playlist). Backfill/retry: `pipeline.py yt-playlists [ep_id|all]`. Covers: `playlist_cover.py`, square 1080 (the API only takes type "hero" at 1:1, and YouTube shows the whole square inside its 16:9 card, so it's designed to read small: icon full-bleed, face in the top third, big Cinzel words on soot at the bottom). Icon from the episode that opens the playlist (clean `art.jpg`, else the painted band of `cover.jpg`); Haiku (`locate_saint`) finds the saint's face to frame the crop. A new playlist gets its cover automatically (failure only logs). Redo one by hand: `playlist_cover.py "Saints of X" art.jpg out.jpg [focus face_y zoom]`, then `youtube.set_playlist_cover(token, playlist_id, jpg)` (deletes the old image first; the API's update call doesn't work). Needs the `youtube.force-ssl` scope (added 2026-10-30: rerun `yt-auth` once).
- Title: `script.youtube_title` (fallback "St. X, Region") + `#Shorts`; category Education; not made for kids. Description carries `brand.json → youtube.disclosure` (AI assistance), sources, art credits, the Ko-fi line when `config.support_url` is set, and the footer.

## Captions
Instagram: 5 hashtags max (`#AllHolySaints` + `caption.hashtags_base` + 2 saint tags) and one rotating CTA (`caption.ctas` + the script's `share_cta`). CTAs live in captions/descriptions only, never in the narration. Links aren't clickable in IG captions; the Ko-fi link is in the bio.

## Cost
- Model auto-picks the newest Sonnet; sources sent once as a cached context block shared by script and fact-check; per-call usage stored in `ep.usage`. Output/thinking tokens dominate cost.
- Haiku tier exists (`claude_json(..., tier="haiku")`, used by translate_es). `select_saint` stays on Sonnet: tested 2026-10-30 on Nov 7–10, Haiku matched or was fine on 3 dates but picked Herodion of Patras for Nov 10 (mostly legend, main feast April 8; Sonnet chose Justus of Canterbury). It would save ~1.3¢/episode (~$0.40/mo), and one bad pick costs a fact-check reject plus a new script (~15¢). Not built: effort medium vs high comparison (needs a paid side-by-side, quote cost first); Batch API.
