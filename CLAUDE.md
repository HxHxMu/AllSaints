# CLAUDE.md — A.S.† (All Saints) handoff

Read this first. It is the source of truth for where the project stands.
Owner: Luis Bonilla (designer / producer / web dev). Repo: https://github.com/HxHxMu/AllSaints (public).
Local working copy: `/Volumes/lebe/Dev/AllSaints` (external drive — see "Gotchas").

## What this is
An automated Instagram Reels channel: **one ~60 s Reel per day about a lesser-known Catholic saint, posted on their feast day.**
AI does research → script → fact-check → art → narration → render. **Nothing posts without Luis tapping Approve in Telegram.**

## Decisions already made (don't re-ask)
| Topic | Decision |
|---|---|
| Name / mark | **All Saints**, monogram **A.S.†** (halo ring + A†S). Tagline: "The saints the world forgot. Heaven didn't." |
| Platform | Instagram only (Reels). New Professional (Creator) account — **not created yet**. |
| Scope | Canonized saints (incl. pre-congregation), **Eastern Catholic** saints, **early Church martyrs**. *Not* Blesseds/Venerables. Must be venerated in the Catholic Church. Lesser-known only. |
| Tone | **Devotional**: reverent story, ends with "Saint ___, pray for us." History vs. tradition clearly separated ("tradition holds…"). |
| Visuals | Public-domain / CC sacred art (Wikimedia Commons) with slow Ken Burns + branded overlays (globe map, name card, gold captions). |
| Voice | AI narrator, **warm deep male** (ElevenLabs). Current voice_id `JBFqnCBsd6RMkjVDRZzb` ("George") is a placeholder — audition alternatives before launch. |
| Music | **Luis produces the beds** (75–90 s ambient/choral loops → `assets/music/`). A generated placeholder pad is there now. |
| Cadence | Daily, on feast day, **7:30 AM America/New_York** (configurable via Telegram `/time`). |
| Approval | Telegram bot: ✅ Approve · 🔁 Redo (with note) · ✏️ Edit caption · 🔄 New saint. Generate ~7 days ahead, approve in batches. |
| Launch | **"When it's ready"** — set with `/launch YYYY-MM-DD` once a week of episodes is approved. |
| Hosting | GitHub Actions on the **public** repo (free minutes; release assets give Instagram a public video URL). |
| Budget | ~$20–60/mo (Anthropic API + ElevenLabs Starter/Creator). |

## Architecture
```
data/calendar.json (Wikidata: saints by feast day, sitelink count = fame proxy)
 → research.select_saint   Claude picks 1 of ~12 candidates for the date
 → research.gather_sources Wikipedia full text + Catholic Encyclopedia 1913 (Wikisource)
 → script.write_script     Claude, JSON beats (hook/who/story…/turn/close), 125–145 words
 → script.fact_check       second Claude pass vs sources; may fix or reject
 → art.collect_candidates  Commons: P18 image, Commons category, searches; license filter (PD/CC0/CC-BY[-SA])
 → art.assign_art          Claude vision picks image per beat + focus point + camera move
 → tts.synthesize          ElevenLabs /with-timestamps per beat, stitched w/ pauses, loudnorm −16 LUFS
 → render.build_props/render  Remotion → video.mp4 (1080×1920 h264) + cover.jpg
 → storage.upload          GitHub Release `ep-YYYY-MM-DD`
 → telegram.send_review    preview + buttons
poll (every 10 min): telegram.process_updates → publish_due → instagram.publish_reel
```

### Layout
- `brand/brand.json` — colors, fonts, motion + **writing rules used verbatim in prompts**. `brand/make_logo.py` → `brand/logo/*` (pure-path SVGs, profile PNG).
- `video/` — Remotion 4 project (JSX). `src/Episode.jsx` (composition), `src/components.jsx` (ArtScene, MapScene globe, TitleCard, CloseScene+outro, Captions, Atmosphere grain/vignette/candle, Credit), `src/Cover.jsx` (Still; key content inside 3:4 grid crop), `src/sample.json` (placeholder props for Studio).
- `engine/` — Python pipeline. Entry: `engine/pipeline.py {generate|poll|refresh-token|build-calendar|whoami}`. Shared: `common.py` (config, Claude helper w/ model auto-pick, state I/O).
- `state/` — committed by the bot. `config.json`, `episodes/<date>.json` (one file per episode to avoid git conflicts), `telegram.json` (offset + pending input), `ig_token.enc` (Fernet-encrypted refreshed token).
- `.github/workflows/` — `generate.yml` (daily 09:17 UTC + dispatch), `poll.yml` (*/10), `maintenance.yml` (weekly token refresh, monthly calendar). `scripts/commit-state.sh` commits state with rebase retries.

### Episode status flow
`generating → review → approved → publishing → published`; side states `redo_requested`, `failed` (retries ≤3, `attempts` counter).

### Secrets (GitHub → Settings → Secrets → Actions)
`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `IG_ACCESS_TOKEN`, `IG_TOKEN_KEY` (random string; generate one). Optional env: `ELEVENLABS_VOICE_ID`, `ANTHROPIC_MODEL`.
Locally, ElevenLabs key lives in `.env` (gitignored). **Never print/cat `.env`; never ask Luis to paste keys in chat.** Verify with `npx -y @elevenlabs/cli@latest onboard check --env-path .env`.

## Status — what's real vs. untested
**Done & verified:** brand kit + logo renders; Remotion templates render end-to-end with placeholder art/silent voice (full 71 s sample rendered OK); placeholder music; all Python modules parse; workflows written; README.

**Written but NEVER run against live services** (built in a sandbox with no access to Wikimedia/Wikipedia/ElevenLabs/Telegram/Instagram). Expect first-run bugs here:
1. `calendar_build.py` — SPARQL assumes `wdt:P411 wd:Q43115` = canonization status "saint"; feast labels parsed from `P841` item labels; Orthodox-only filter via P140. **Verify counts look sane (~thousands of saints, every MM-DD covered).**
2. `research.py` — Wikipedia extracts; Wikisource Catholic Encyclopedia search heuristics.
3. `script.py` / `common.claude_json` — prompt quality, JSON robustness, word-count loop. Model auto-picks newest "sonnet" from `models.list`.
4. `art.py` — license regexes, `BAD_NAME` filter, vision prompt with ~28 images, thumb URL width rewrite in `download()`.
5. `tts.py` — ElevenLabs `/with-timestamps` response shape; display↔spoken word alignment (pronunciations must stay 1 token); adelay stitching.
6. `render.py` — props from real data; `stage_assets`; Remotion browser download on Actions (`npx remotion browser ensure`).
7. `storage.py` — release create/upload; `resolve_direct()` (signed object URL for Instagram).
8. `instagram.py` — `video_url` path is documented for Instagram Login. The **resumable fallback (`rupload`) is only documented for Facebook Login** — may fail; if `video_url` doesn't work, fall back to a direct public host (GitHub Pages / R2).
9. `telegram.py` — full button/command flow; owner lock = first `/start`.
10. `commit-state.sh` concurrency between generate/poll.

## Known issues / TODO (small)
- `pipeline.generate_one`: fact-check `reject` recurses with no cap → add max 3 saints per date.
- Telegram `/generate` should reset `attempts` on `failed` episodes.
- No-art fallback just reuses the map scene → add an "illumination" scene (gilt drop-cap / symbol plate) in `components.jsx`.
- Map place label can collide with captions when the location sits low on the globe.
- Render speed ~0.3 s/frame on 2 cores (~10 min/episode); expect ~4–5 min on Actions 4-core. Grain uses PNG tiles (feTurbulence was too slow); close-scene blur is done at ¼ res — keep it that way.
- Output ~44 MB/min at CRF 19; Telegram preview auto-downscales >45 MB.
- Remotion license: free for individuals/≤3-person companies — fine for now.

## Next steps (in order)
1. **Luis:** finish ElevenLabs key in `.env` → run `onboard check`. Add GitHub secrets (list above).
2. Set remote & push: `git remote add origin https://github.com/HxHxMu/AllSaints.git && git push -u origin main`.
3. Run `python engine/pipeline.py build-calendar` locally; sanity-check `data/calendar.json`; commit it.
4. Local dry run: `python engine/pipeline.py generate --date <tomorrow> --no-upload`. Fix bugs in the untested list. Watch the MP4 with Luis.
5. Voice audition: render the same script with 3–4 deep warm male ElevenLabs voices; Luis picks → update `brand.json`.
6. Telegram: Luis creates bot via @BotFather, adds secret, sends `/start` (after first poll run).
7. Push → run `generate.yml` manually (max 1) → confirm the Telegram review arrives.
8. Instagram: create account (Professional/Creator, public), upload `brand/logo/profile-1080.png`, bio. Meta app per README → `IG_ACCESS_TOKEN` → `maintenance.yml` task `whoami`.
9. Test publish to the real account once (a launch-intro Reel is a good candidate), then `/launch YYYY-MM-DD`.
10. Swap in Luis's music beds; delete `assets/music/placeholder-*`.

## Commands
```bash
pip install -r requirements.txt && (cd video && npm ci)
cd video && npx remotion studio src/index.js          # preview templates with src/sample.json
python engine/pipeline.py generate --date 2026-11-03 --no-upload
python engine/pipeline.py poll                        # needs TELEGRAM_BOT_TOKEN etc.
```

## Gotchas
- **External drive (`/Volumes/lebe`)**: macOS writes `._*` files everywhere. They're excluded locally via `.git/info/exclude`; consider adding `._*` to `.gitignore`. Use `git config core.filemode false`.
- `node_modules/` is not in the repo — run `npm ci` in `video/`.
- `work/` and `video/public/episodes/*` (except `sample/`) are scratch, gitignored.
- Keep writing rules in `brand/brand.json`, not hard-coded in prompts — prompts read them.
- Accuracy and reverence beat engagement tricks. Never invent saint quotes; label legend as tradition.
