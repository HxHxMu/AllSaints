# Architectural Thought Report & Systems Briefing: A.S.† (All Saints)

> **Audience:** Claude (Claude Code / Anthropic Assistant sessions in `HxHxMu/AllSaints`).  
> **Author:** Principal Systems & Software Architect  
> **Status:** Active Architectural Reference  
> **Primary Directive:** Read this document before executing non-trivial refactors, pipeline adjustments, or state machine alterations in this repository.

---

## 1. Executive Context & Mental Model

A.S.† is not merely a video generator; it is an **autonomous, self-scheduling, multi-platform liturgical broadcast network** running on a micro-budget (~$12–$15/mo) with zero permanent servers. 

The entire stack is anchored on three immutable non-negotiables:
1. **Sacred Reverence & Truth:** Never invent quotes, never blur legend into fact without "tradition holds", never use sensational clickbait, never paywall prayers.
2. **Human-in-the-Loop (HITL) Gate:** The pipeline may autonomously research, draft, fact-check, paint, narrate, and render up to 7 days in advance, but **zero public media can ever be published without Luis explicitly clicking "✅ Approve" in Telegram**.
3. **Publishing Idempotency:** The moment a social platform accepts a media payload, state is committed immediately *before* ancillary tasks (playlists, covers, notifications). A retry must *never* double-post a Reel or Short.

---

## 2. System Topology & Ownership Map

```
[Wikidata Calendar] ──► research.select_saint (Claude Sonnet)
                           │
                           ▼
[Multi-Source Ingestion] ─► Wikipedia + Catholic Encyclopedia + Santi e Beati + Causes of Saints
                           │
                           ▼
[Scripting & Verification]─► script.write_script (Sonnet) ──► script.fact_check (Sonnet pass)
                           │ (Max 3 rejects per date)
                           ├──────────────────────────────┬──────────────────────────────┐
                           ▼                              ▼                              ▼
                 script.translate_es              books.find                    illustrate.illustrate
                 (Claude Haiku)                  (OpenLibrary API)              (Gemini Imagen)
                           │                              │                              │
                           └──────────────────────────────┼──────────────────────────────┘
                                                          ▼
[Audio Engineering] ──────► tts.synthesize (Gemini Flash TTS "Riko") ──► faster-whisper (Int8 Alignment)
                           │
                           ▼
[DSP & Music] ────────────► music.pick_bed (assets/music/ rotating beds + loudnorm -15 LUFS)
                           │
                           ▼
[Video Render] ───────────► render.render (Remotion 4 / Headless Chrome 1080x1920 MP4 + Cover JPG)
                           │
                           ▼
[Asset Storage] ──────────► storage.upload (GitHub Releases: ep-YYYY-MM-DD)
                           │
                           ▼
[HITL Review] ────────────► telegram.send_review (720p preview video + buttons)
                           │
                           ▼
[Action / Webhook] ───────► Cloudflare Worker (relay/worker.js + Durable Object SQLite queue)
                           │
                           ▼
[Publishing (poll.yml)] ──► 07:30 ET: Instagram Reel ──► FB Reel ──► YT Short ──► Threads ──► TikTok draft
```

---

## 3. Critical Architectural Fault Lines (Claude: Read Carefully)

### 3.1. The Git-as-Database Concurrency Hazard
*Location:* [`scripts/commit-state.sh#L13-L20`](file:///Volumes/lebe/Dev/AllSaints/scripts/commit-state.sh#L13-L20)
```bash
git pull -q --rebase -X theirs origin main && git push -q origin HEAD:main
```
- **The Mechanism:** In Git rebase terminology, `-X theirs` forces the **incoming replayed commit** (the current runner's changes) to win over upstream commits (`origin/main`).
- **The Risk:** While `state/episodes/<id>.json` is sharded per date, shared files—specifically [`state/telegram.json`](file:///Volumes/lebe/Dev/AllSaints/state/telegram.json), [`state/config.json`](file:///Volumes/lebe/Dev/AllSaints/state/config.json), and [`state/checks.json`](file:///Volumes/lebe/Dev/AllSaints/state/checks.json)—are touched by multiple workflows (`poll.yml`, `generate.yml`, `maintenance.yml`).
- **Claude's Rule:** When editing workflow or commit logic, **never** allow two jobs to write to shared state files without checking offsets. If you refactor state handling, preserve the sharded nature of `state/episodes/`.

### 3.2. S3 Pre-signed URL Expiration on Social Ingest
*Location:* [`engine/storage.py#L55-L58`](file:///Volumes/lebe/Dev/AllSaints/engine/storage.py#L55-L58), [`engine/pipeline.py#L372-L373`](file:///Volumes/lebe/Dev/AllSaints/engine/pipeline.py#L372-L373)
- **The Mechanism:** Video and cover assets are hosted on GitHub Releases (`ep-YYYY-MM-DD`). `storage.resolve_direct()` follows the HTTP redirect from GitHub to AWS S3 (`github-releases.githubusercontent.com`).
- **The Risk:** GitHub's AWS S3 pre-signed URLs carry short expiration lifetimes (typically 300 to 900 seconds). Meta's Graph API (`video_url`) and other social platforms download asynchronously. If Meta's container ingestion queue delays beyond 5 minutes, Meta gets an `HTTP 403 Request has expired`.
- **Claude's Rule:** If social publishing fails with cryptic container download errors, check if the pre-signed S3 URL expired before Meta retrieved it. The long-term architectural remedy is migrating binary media to **Cloudflare R2** with persistent, vanity public URLs.

### 3.3. Token Encryption Key Derivation in Public Repository
*Location:* [`engine/instagram.py#L11-L14`](file:///Volumes/lebe/Dev/AllSaints/engine/instagram.py#L11-L14), [`engine/threads.py#L25-L27`](file:///Volumes/lebe/Dev/AllSaints/engine/threads.py#L25-L27), [`engine/tiktok.py#L27-L29`](file:///Volumes/lebe/Dev/AllSaints/engine/tiktok.py#L27-L29)
- **The Mechanism:**
  ```python
  def _fernet():
      k = env("IG_TOKEN_KEY", required=True)
      return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode()).digest()))
  ```
- **The Risk:** The encrypted files (`ig_token.enc`, `th_token.enc`, `tt_token.enc`) are committed to a **public** repository. Using single-iteration un-salted `SHA-256` means offline dictionary and GPU rainbow-table attacks are trivially fast if the passphrase `k` lacks 128+ bits of true cryptographic entropy.
- **Claude's Rule:** When modifying token routines, propose or implement salted PBKDF2 (`hashlib.pbkdf2_hmac` with ≥600,000 iterations) or Argon2id.

### 3.4. Remotion Chromium Headless Resource Limits
*Location:* [`.github/workflows/generate.yml#L22-L25`](file:///Volumes/lebe/Dev/AllSaints/.github/workflows/generate.yml#L22-L25), [`engine/render.py#L66-L68`](file:///Volumes/lebe/Dev/AllSaints/engine/render.py#L66-L68)
- **The Mechanism:** Remotion runs Chrome in headless mode on standard 2-core GitHub Actions runners.
- **The Risk:** High concurrency or complex SVG/canvas blending (like maps and multi-layer icon animations) can trigger Linux OOMs or GPU rasterization hangs.
- **Claude's Rule:** When modifying [`video/src/Episode.jsx`](file:///Volumes/lebe/Dev/AllSaints/video/src/Episode.jsx) or [`video/src/components.jsx`](file:///Volumes/lebe/Dev/AllSaints/video/src/components.jsx), avoid heavy canvas shaders, uncontrolled texture sizes, or unbounded React render loops. Keep render memory deterministic.

---

## 4. Architectural Rules for Claude Code Sessions

When working on this repository, strictly adhere to the following rules:

1. **Protect Secrets and Invariants:**
   - Never print `.env` or echo secret contents.
   - Never remove or alter [`PRIVACY.md`](file:///Volumes/lebe/Dev/AllSaints/PRIVACY.md) or [`TERMS.md`](file:///Volumes/lebe/Dev/AllSaints/TERMS.md) (Google OAuth verification links directly to these).
   - Never bypass the Telegram approval requirement.

2. **Respect `brand/brand.json` as the Single Source of Truth:**
   - Do **not** hardcode writing styles, color hexes, font declarations, or prompt constraints in Python or JavaScript. All prompt instructions must interpolate `brand/brand.json`.

3. **Maintain Episode State Invariants:**
   - Status transitions strictly flow: `generating` ──► `review` ──► `approved` ──► `publishing` ──► `published`.
   - Side states: `redo_requested`, `failed` (capped at 3 attempts).
   - Once an episode is `publishing` or `published`, never revert it to `approved` or `review` (doing so causes duplicate social posts).
   - The Telegram buttons in `EP_BUTTONS` must remain inert for any episode with status `published`.

4. **Preserve External Drive Cleanliness (`/Volumes/lebe`):**
   - The workspace resides on an external drive where macOS generates `._*` AppleDouble resource forks.
   - Always filter `p.name.startswith("._")` when iterating files or globbing directories.

---

## 5. Prioritized Engineering Backlog for Future Sessions

### Priority 1: Schema Safety & Test Harness
- [ ] **Introduce Pydantic v2 Models:** Replace untyped dictionaries in `script.py` and `common.parse_json()` with strict schemas (`EpisodeScript`, `Beat`, `SaintMetadata`).
- [ ] **Build Unit Test Suite (`pytest`):**
  - Add tests for Whisper subtitle token alignment (`_align`).
  - Add tests for URL slug deduplication (`assign_slugs`).
  - Add tests for social caption length truncation and hashtag limits.

### Priority 2: Security & Storage Hardening
- [ ] **Salted Key Derivation for Tokens:** Refactor `_fernet()` in `instagram.py`, `threads.py`, and `tiktok.py` to use PBKDF2-HMAC-SHA256 with an explicit salt.
- [ ] **Cloudflare R2 Asset Storage:** Evaluate migrating video/image hosting from GitHub Releases to a Cloudflare R2 bucket (`media.allholysaints.com`) with permanent public URLs.

### Priority 3: Codebase Modularization
- [ ] **Modularize `pipeline.py`:** Split the 838-line procedural script into dedicated domain packages: `engine/cli.py`, `engine/orchestration/`, and `engine/syndication/`.
- [ ] **Clean Up Inline Imports:** Move dynamic `import ...` calls inside function bodies up to module top-level where possible, avoiding cyclic dependencies via proper interface separation.

---

*This document is maintained in the repository at `docs/architect-report.md` for seamless context injection into Claude coding sessions.*

