# CLAUDE.md — A.S.† (All Saints)

Owner: Luis Bonilla (designer / producer / web dev). Repo: https://github.com/HxHxMu/AllSaints (public). Python: `.venv/bin/python`.
Automated devotional channel: **one ~60 s vertical video a day about a lesser-known Catholic saint, on their feast day**, posted as an Instagram Reel (**@all.holy.saints**) and a YouTube Short (**@AllHolySaints**). AI researches, writes, fact-checks, paints, narrates and renders; **nothing posts without Luis tapping Approve in Telegram.**

## Hard rules
- **Never print/cat `.env`; never ask Luis to paste keys in chat.** Check key *names* only (`grep -o '^[A-Z_]*=' .env`).
- Accuracy and reverence beat engagement tricks. Never invent saint quotes; label legend as tradition ("tradition holds…"). No engagement bait, no guilt/urgency copy, never paywall prayers.
- Writing rules, voice, art style, captions and disclosures live in `brand/brand.json` (prompts read them verbatim), not hard-coded in prompts.
- The bot commits `state/` constantly: `git pull --rebase --autostash` before pushing.
- Don't delete/move `PRIVACY.md`, `TERMS.md` (linked from the Google OAuth consent screen).
- Current queue/status: read `state/episodes/*.json` and `git log`, not docs.

## Decisions (don't re-ask)
| Topic | Decision |
|---|---|
| Brand | **All Saints**, monogram **A.S.†**. Tagline: "The saints the world forgot. Heaven didn't." Support: "Help keep the forgotten remembered." / "Light a candle" (Ko-fi; never "donation"). |
| Scope | Canonized saints (incl. pre-congregation), Eastern Catholic saints, early Church martyrs; venerated in the Catholic Church; lesser-known only. *Not* Blesseds/Venerables. |
| Tone | Devotional story ending "Saint ___, pray for us."; history vs. tradition clearly separated. |
| Art / voice / music | AI Byzantine icons (Gemini image) · **Gemini TTS "Riko"** (paid; ElevenLabs free tier = backup only) · music beds produced by Luis (`assets/music/`). |
| Cadence | Daily, **7:30 AM America/New_York**, generated ~7 days ahead, approved in batches; one Approve covers both platforms. |
| Hosting / budget | GitHub Actions on the public repo · ~$20–60/mo (Anthropic + Gemini); goal: the channel pays for itself. |

## Where the details are (read when relevant)
- `engine/CLAUDE.md` — pipeline, state, secrets, YouTube/Instagram, captions, cost design (loads when working in `engine/`).
- `video/CLAUDE.md` — Remotion templates, render notes (loads when working in `video/`).
- `DESIGN.md` — the website's design system ("The Night Office"). **Read it before any visual/UI work; don't deviate without Luis's approval.**
- `docs/monetization.md` — revenue phases and plan. `docs/website.md` — website decisions (not built). `docs/roadmap.md` — open to-dos.

## Layout
`engine/` Python pipeline · `video/` Remotion 4 · `brand/` brand.json, logo, social art · `state/` bot-committed config + episodes · `data/calendar.json` saints by feast day · `.github/workflows/` generate / poll / maintenance · `relay/` Cloudflare Worker Telegram relay · `work/` scratch (gitignored).

## Commands
```bash
pip install -r requirements.txt && (cd video && npm ci)
.venv/bin/python engine/pipeline.py generate --date 2026-11-05 --no-upload
.venv/bin/python engine/pipeline.py youtube <ep_id>   # upload one episode's Short now
.venv/bin/python engine/pipeline.py yt-whoami         # must print @allholysaints
```

## Gotchas
- External drive (`/Volumes/lebe`): macOS writes `._*` files everywhere (gitignored; `load_episodes` skips them). Use `git config core.filemode false`.
- `node_modules/` isn't committed: `npm ci` in `video/`.
