# A.S.† — All Saints

Daily one-minute Instagram Reels on lesser-known Catholic saints, posted on their feast day.
Fully automated, with human approval in Telegram before anything goes live.

```
Wikidata feast calendar ─► Claude picks the saint ─► Wikipedia + Catholic Encyclopedia (1913)
   ─► Claude writes script ─► independent Claude fact-check ─► Wikimedia Commons art (PD / CC)
   ─► Claude vision picks images + focus points ─► ElevenLabs narration (word timestamps)
   ─► Remotion renders 1080×1920 Reel + cover ─► GitHub Release ─► Telegram: ✅ / 🔁 / ✏️ / 🔄
   ─► approved Reel publishes on its feast day at the set time (Instagram API)
```

## How it runs (GitHub Actions, free on a public repo)

| Workflow | When | What |
|---|---|---|
| `generate.yml` | daily + on demand | Keeps the next 7 days filled (max 3 per run). Also re-runs redo requests. |
| `poll.yml` | every 10 min | Reads Telegram buttons/commands, publishes today's approved episode at post time. |
| `maintenance.yml` | weekly / monthly | Refreshes the Instagram token; rebuilds the saints calendar. |

State lives in `state/` (one JSON per episode) and is committed back by the bot.

## Telegram commands

`/status` queue · `/launch 2026-11-08` set launch date · `/time 07:30` post time · `/pause` `/resume` · `/generate`

Buttons on each preview: **Approve**, **Redo** (reply with what to change, or `fresh`), **Edit caption**, **New saint**.

## Secrets (repo → Settings → Secrets and variables → Actions)

| Name | From |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Developers → API keys (Text to Speech permission) |
| `TELEGRAM_BOT_TOKEN` | @BotFather → /newbot |
| `IG_ACCESS_TOKEN` | Meta App Dashboard (below) |
| `IG_TOKEN_KEY` | any long random string (encrypts the refreshed token in `state/`) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | set by `pipeline.py yt-auth` (below) |

Optional repo variable / env: `ELEVENLABS_VOICE_ID` to change narrator, `ANTHROPIC_MODEL` to pin a model.

## Instagram API setup (once)

1. Instagram account must be **Professional** (Creator or Business) and **public**.
2. developers.facebook.com/apps → **Create App** → use case **Other** → type **Business** → name + email → **Next**.
3. Find **Instagram** → **Set up** (this adds *API setup with Instagram login*). No Facebook Page needed.
4. Under *Generate access tokens* → **Add account** → log into the A.S.† Instagram.
5. Click **Generate token** next to the account → log in → copy the token → save as `IG_ACCESS_TOKEN`.
   Dashboard tokens last 60 days; `maintenance.yml` refreshes it weekly.
6. Make sure `instagram_business_basic` and `instagram_business_content_publish` are among the permissions.
   Your own account = Standard Access → no App Review needed.

## YouTube Shorts setup (once)

Each published episode is also uploaded as a Short (same MP4, its own title/description from `youtube.py`).
Instagram and YouTube are tracked separately: a failed Short retries up to 3x and never re-posts the Reel.

1. console.cloud.google.com → **New project** ("All Saints").
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **OAuth consent screen** (Google Auth Platform): External, app name "All Saints", your email.
   Add yourself as a test user, then **Publish app → In production** (unverified is fine for your own account).
   Left in *Testing*, the refresh token expires after 7 days and uploads stop.
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → download the JSON (keep it out of the repo).
5. Locally: `python engine/pipeline.py yt-auth ~/Downloads/client_secret_….json`.
   Click past "Google hasn't verified this app", choose the **All Saints channel** (Brand Account) when asked.
   It writes the three `YT_*` values to `.env` and, if `gh` is installed, to GitHub secrets (Production environment).
6. Check: `python engine/pipeline.py yt-whoami` → should print the channel name.
7. **API audit:** uploads from a new API project are forced *private* until Google's YouTube API compliance audit
   passes. Apply via the "YouTube API Services – Audit and Quota Extension" form. Until then set
   `"youtube_privacy": "private"` in `state/config.json` and hit Publish in YouTube Studio (the Telegram message links it).
8. YouTube Studio → Settings → Channel → Advanced: audience **"No, not made for kids"** (also set per upload).

Test one: `python engine/pipeline.py youtube 2026-10-28` (needs the episode's release assets).

## Brand

`brand/brand.json` holds colors, type, motion and writing rules used by both the script prompts and the video templates.
Logo files: `brand/logo/`. Fonts: Cinzel (display), EB Garamond (text), Cormorant Garamond Italic (accent) — all OFL.

## Music

Drop 75–90 s ambient beds (mp3/wav) into `assets/music/`. Episodes rotate through them; `placeholder-*` files are used only when none exist.

## Local test

```bash
pip install -r requirements.txt && (cd video && npm ci)
python engine/pipeline.py build-calendar
python engine/pipeline.py generate --date 2026-11-03 --no-upload
cd video && npx remotion studio src/index.js   # live-preview templates with sample props
```
