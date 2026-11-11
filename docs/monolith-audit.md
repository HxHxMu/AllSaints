# Monolith audit: what to split, and in what order

*2026-11-10. This builds on `docs/architect-report.md` and doesn't repeat it.*

> **Status (2026-11-11):** steps 1–6 shipped on 2026-11-10 (commit 08a63e1) and ran clean in production (poll, generate and the Nov 11 post on all five platforms). Steps 7, 8 and 10 are done in the working tree (stories → `story_music.py` + `o_antiphons.py` + `data/o-antiphons.json`; youtube → `yt_meta.py` + `yt_playlists.py`; dashboard → `src/scripts/dash.ts` + `src/styles/dash.css`). Step 9 (Telegram handler) is deliberately left out.
> - **Moved docs:** the material from `engine/CLAUDE.md` went to `docs/engine/{youtube,meta,tiktok,compilation,cost-dashboard}.md`, not `docs/website.md` or `docs/sung-prayers/` as first planned: those folders hold your work in progress.
> - **ffmpeg calls:** left as they were. Their flags differ per module (`-nostdin`, `check_output`), so a shared wrapper would have changed behaviour. Only `duration` moved to `cards.py`.
> - **Paid render not run:** `generate --date … --no-upload` was skipped. It costs ~$0.40 and writes `state/episodes/<date>.json` locally. `generate.py` is a verbatim move.
> - **Stale references:** `docs/architect-report.md` (§3.2 and the backlog) still names `engine/pipeline.py` for `publish_*` and `build_caption`. It wasn't touched because it has your uncommitted edits.

**Bottom line:** two files are worth splitting now and one doc is worth slimming. That's about 3 hours of work in six steps you can land one at a time. Everything else is small enough to leave alone.

1. **`engine/CLAUDE.md` (22 KB, ~5.6k tokens)** loads into every session that touches `engine/`. About two thirds of it is one-time platform setup notes. Moving those to `docs/engine/*.md` saves ~3.5–4k tokens per engine session and needs no code change. **Do this first.**
2. **`engine/pipeline.py` (845 lines, 41.7 KB, ~10.5k tokens)** is the CLI, the generate loop, the publish flow, the evening check and a library at the same time: `telegram.py`, `youtube.py` and `metrics.py` all import from it. It also holds the "record the post first" logic four times over, copied by hand.
3. **Card/ffmpeg helpers** (`_font`, `_tracked`, `_width`, `_monogram`, `duration`, `ROMAN`) are private functions imported across five modules, with `ROMAN` defined four times.

A note on the architect report's backlog, which lists *"Modularizing `pipeline.py`"* as not recommended ("splitting it creates unnecessary indirection"). I agree with that for a deep package layout. The split proposed here is narrower: `pipeline.py` stays the only entry point, and the code moves into four flat sibling modules, one level deep. Three things justify it, none of which the report weighed:
- other modules import from the CLI file;
- the four duplicated publish blocks are exactly where the never-re-post invariant lives;
- every publish or caption change currently means reading 10k tokens.

---

## Token picture

| File | Lines | Bytes | ≈ tokens | Loaded |
|---|---|---|---|---|
| `engine/CLAUDE.md` | 105 | 22,354 | 5,600 | **every** session working in `engine/` |
| `CLAUDE.md` | 43 | 3,776 | 950 | every session |
| `video/CLAUDE.md` | 9 | 823 | 200 | sessions in `video/` |
| `engine/pipeline.py` | 845 | 41,772 | 10,500 | most engine tasks |
| `engine/youtube.py` | 430 | 22,600 | 5,600 | YouTube tasks |
| `engine/stories.py` | 440 | 21,704 | 5,400 | Stories tasks |
| `engine/metrics.py` | 349 | 19,945 | 5,000 | dashboard tasks |
| `engine/compilation.py` | 394 | 17,796 | 4,400 | compilation **and** every card module (shared helpers) |
| `engine/telegram.py` | 301 | 15,163 | 3,800 | approval-flow tasks |
| `site/src/pages/dash/index.astro` | 311 | 23,009 | 5,700 | dashboard UI tasks |

Breakdown of `pipeline.py` by area (bytes of function bodies):

| Area | Bytes |
|---|---|
| publish | 13.1 KB |
| generate | 11.3 KB |
| CLI `main()` | 9.1 KB |
| captions | 2.5 KB |
| evening check | 2.2 KB |
| cost | 1.3 KB |
| poll | 0.9 KB |

---

## Findings

### F1. `engine/CLAUDE.md`: auto-loaded runbook (105 lines, 22 KB)
- **What's tangled:** this file is meant to orient a session: flow, invariants, state, where things live. It also carries one-time setup and history: TikTok Sandbox/audit details, Threads app id and tester steps, Facebook token exchange, YouTube OAuth/branding notes, compilation design, the dashboard spec and Sonnet-vs-Haiku test results. Lines run up to 1,400 characters. The `Entry:` line hand-copies the argparse command list, which drifts.
- **Proposed split:** keep ~6–7 KB:
  - Entry (point at `pipeline.py -h` instead of the list)
  - Flow
  - Reliability rules
  - State
  - Secret **names**
  - Workflows
  - Captions
  - a "Details" table of pointers

  Move the rest to on-demand docs:

  | New doc | What moves into it |
  |---|---|
  | `docs/engine/youtube.md` | OAuth, channel guard, playlists, covers, titles, localizations |
  | `docs/engine/meta.md` | Facebook Page, Threads, Instagram + FB Stories, carousels, shares |
  | `docs/engine/tiktok.md` | Sandbox, inbox flow, tokens, setup |
  | `docs/engine/compilation.md` | monthly compilation |
  | `docs/engine/cost.md` | prices, Gemini flat rate, model-tier test notes |
  | `docs/website.md` (existing) | the Dashboard section, appended |
  | `docs/sung-prayers/` (existing) | the sung-prayers paragraph, as a README there |

- **Benefit:** ~3.5–4k fewer tokens on **every** engine session, which is the biggest per-session saving available. Details stay one Read away.
- **Risk:** low. The risk is a future session not reading a doc it needs. Mitigate by keeping each moved section's one-line rule in place, e.g. "YouTube uploads refuse any channel but `config.youtube_channel` → details `docs/engine/youtube.md`". Keep the reliability rules verbatim in `engine/CLAUDE.md`.
- **Effort:** S (~30 min). Prose move only.

### F2. Root `CLAUDE.md` and `video/CLAUDE.md`: fine
- **Root `CLAUDE.md` (43 lines, 3.8 KB)** is already lean, with pointers to on-demand docs. No change.
- **`video/CLAUDE.md` (9 lines)** is small. It doesn't mention `src/concept/` or `video/scripts/`, but those are Luis's uncommitted work, so update it when that lands, not now.
- **`DESIGN.md` (13 KB)** is read on demand only. Fine.

### F3. `engine/pipeline.py`: CLI, library and publisher in one file (845 lines, 41.7 KB)

**What's tangled:**

1. **It's a library as well as the CLI.**
   - `telegram.py:290` imports `build_caption` from it.
   - `youtube.py:54` imports `saint_tags` and `CAP`.
   - `metrics.py:23` imports `GEMINI_PER_EPISODE` and `call_cost`.

   So importing `metrics` loads the whole CLI module, and the dependency direction is backwards.
2. **Four copies of one pattern.** `publish_facebook`, `publish_threads`, `publish_tiktok` and `publish_youtube` (lines 412–516) each repeat the same steps:
   - check "configured, not done, attempts < 3, published";
   - try;
   - on failure, bump `attempts`, store `error`, save, and Telegram on attempts 1 and 3;
   - on success, record the result **then** notify.

   That's the never-re-post invariant, written out four times. A fifth platform (Pinterest pins) would be a fifth copy.
3. **`main()` is 180 lines** of argparse plus inline command bodies. `ig-media` does raw Graph HTTP inline; `books`, `backfill-story`, `fb-cover` and `yt-localize` loop inline.
4. **Unrelated concerns sit side by side:** caption building, the generate loop, cost reporting, the evening `check_queue`, Pinterest board announcements, and one-off carousels (`cmd_post`).

**Proposed split.** All new modules sit flat in `engine/`: modules are imported by bare name with `engine/` as the working directory or on the path, so there's no package.

| New module | What moves in | ≈ size |
|---|---|---|
| `captions.py` | `CAP`, `_fold`, `saint_tags`, `ig_hashtags`, `pick_cta`, `build_caption` | 2.5 KB |
| `costs.py` | `PRICES`, `GEMINI_PER_EPISODE`, `call_cost`, `cmd_cost` | 1.5 KB |
| `generate.py` | `MAX_REJECTS`, `GiveUp`, `build_art`, `commons_art`, `generate_one`, `backfill_story`, `dates_needing_work`, `cmd_generate` | 11.5 KB |
| `publish.py` | `publish_due`, `publish_episode`, `_notify`, the four platform publishers built on one helper (below), `youtube_cover`, `youtube_playlists`, `pinterest_boards`, `cmd_post` | ~10 KB (13 → 10 after dedup) |
| `checks.py` | `check_queue` (or fold it into `publish.py`; it's 2 KB) | 2.2 KB |
| `pipeline.py` | argparse, `cmd_poll`, a thin dispatch table; each branch one line calling a module function | ~6 KB |

Small moves that go with it:
- `ig-media` body → `instagram.media_info(media_id)`.
- `fb-cover` loop → `facebook.backfill_covers(ids)`.
- `books` loop → `books.backfill(arg)`.
- `backfill-story` printing → `generate.cmd_backfill_story(arg)`.

**The shared publish helper.** One function holds the invariant:

```python
def publish_once(ep, key, label, post, *, ready, done_field="id", stamp="published_at", note=None):
    """Post ep to one platform at most once. ready(ep) gates it; post() returns the platform's result.
    Records the result and saves BEFORE any notification; failures count attempts (≤3) and never touch ep.status."""
```

Each platform becomes ~6 lines of `ready`/`post`/`note`. Keep the per-platform differences explicit:
- YouTube gates on `assets`, not `status == "published"`, and runs cover and playlists afterwards, each in its own try.
- TikTok uses `publish_id` and `sent_at`, and sends two notes.
- `publish_episode` (the Reel) stays hand-written. It is the one path with the `find_reel` pre-check and the status transition, and folding it into the helper would hide that.

**Compatibility:**
- Re-export the moved names from `pipeline.py` for one release, e.g. `from captions import build_caption, saint_tags, CAP`, so nothing that imports `pipeline` breaks.
- Then point `telegram.py`, `youtube.py` and `metrics.py` at the new modules and drop the shims.

**Benefit:**
- A publish change reads ~10 KB instead of 42 KB (−8k tokens).
- A caption change reads 2.5 KB.
- A CLI change reads 6 KB.
- The invariant lives in one tested function instead of four copies.
- `metrics` and `telegram` stop loading the CLI.

**Risk:** medium, all of it in `publish.py`. A wrong field name such as `attempts` vs `playlist_attempts`, or reordering save/notify, could cause a double post or a silently skipped platform. Mitigations:
- **Keep every `state/episodes/*.json` field name unchanged.** Existing episodes carry `youtube.attempts`, `tiktok.publish_id`, `facebook.id`, and so on.
- Move the code first and dedupe second, as separate commits (steps 3 and 4 below).
- Add an offline test (step 2) that stubs the platform modules and asserts the order: save with the id, then notify. It should also assert that a raising notify or cover leaves the record in place.

**Effort:** M. Moves ~45 min; publish helper ~45 min plus tests.

### F4. Card helpers shared through private imports (compilation, stories, sung_video, music_clips, playlist_cover)

**What's tangled:** PIL drawing primitives live in two "product" modules and are imported privately by others.
- `playlist_cover._font`, `_tracked` and `_width` are imported by `stories`, `sung_video`, `music_clips` and `compilation` (lazily).
- `compilation._monogram` and `compilation.duration` are imported by `stories`, `sung_video` and `music_clips`.
- `ROMAN` is defined four times: a list in `stories.py:32`, `sung_video.py:28` and `music_clips.py:29`; a pairs table plus `roman()` in `compilation.py:23`.
- ffmpeg invocation (`["ffmpeg", "-nostdin", "-y", "-loglevel", "error", …]`) is spelled out in five places.

As a result, every 10 pm `poll` that builds a Story imports `compilation` (and `playlist_cover`, which imports `claude_json`). Reading any card module also means opening two unrelated ones.

**Proposed split:** new `engine/cards.py` holding:
- `FONTS`, `font()`, `tracked()`, `width()`, `wrap()` (merging `stories._lines`, `compilation._wrap` and `sung_video._fit` where their behaviour matches; leave them where it doesn't);
- `monogram()`, `roman()` and the `ROMAN` table;
- `ffmpeg(*args)` and `duration(path)`.

`playlist_cover` and `compilation` then import from `cards` like everyone else.

**Constraint:** `cards.py` may import only `PIL` and `common` at top level. `poll.yml` installs `requests cryptography anthropic pillow`, with **no numpy**. `music_clips`' `import numpy` must stay out of anything `poll` imports.

**Benefit:** ~4 KB less to read per card task, and one place for the brand's typographic primitives.

**Risk:** low. These are pure functions; rendering output can be compared pixel for pixel.

**Effort:** S–M (~40 min).

### F5. `engine/stories.py`: three products in one scheduler (440 lines, 21.7 KB)

**What's tangled:**
- the nightly prayer card plus its Facebook Story mirror (`night_card`, `_night`, `post_night`, `_facebook`);
- seasonal cards (`run_seasonal`);
- the weekly music card with its liturgical calendar (`_easter`, `SOLEMNITIES`, `_music_skip`, `_music_pick`, `music_card`, `run_music`);
- the O Antiphons generator, whose 37 lines of text data sit inline (`O_ANTIPHONS`, `antiphon_card`, `make_o_antiphons`);
- the `run_due` dispatcher and a `__main__` CLI.

**Proposed split:**

| Module | What it holds |
|---|---|
| `stories.py` (stays) | `run_due`, nightly card, `_facebook`, seasonal, CLI |
| `story_music.py` | music rotation plus card |
| `o_antiphons.py` | generator; the antiphon texts move to `data/o-antiphons.json` |

`stories.run_due` imports the other two lazily.

**Benefit:** a nightly-card fix reads ~9 KB instead of 22 KB. The antiphon texts become data, not code.

**Risk:** low–medium:
- `run_due` runs inside every `poll` (wrapped in try/except, so a break doesn't stop the daily post, but Stories would silently stop).
- `state/stories.json` entry shapes and the `stories.py o-antiphons <year>` CLI must stay as they are.

**Effort:** S (~30 min). **Timing:** do it after Dec 23 or well before Dec 17, not during the O Antiphons week.

### F6. `engine/youtube.py`: metadata, API and playlists (430 lines, 22.6 KB)

**What's tangled:**
- pure text building (`build_title`, `build_description`, `localizations`, `_short_title`, `build_tags`, `page_url`, `MESES`);
- upload/thumbnail/privacy API calls;
- playlist management with Claude-generated playlist covers (`continent`, `_playlist_id`, `set_playlist_cover`, `_new_playlist_cover`, `add_to_playlists`);
- OAuth (`authorize`, a local HTTP server).

Line 54 imports `saint_tags` and `CAP` from `pipeline`.

**Proposed split:**

| Module | What it holds | ≈ size |
|---|---|---|
| `yt_meta.py` | pure, unit-testable text functions; imports from `captions` | ~7 KB |
| `yt_playlists.py` | continent, playlists, playlist covers | ~6 KB |
| `youtube.py` (stays) | token, upload, thumbnail, privacy, `me`, `authorize`; re-exports `page_url` (the publish flow calls `youtube.page_url`). Keep `API`, `_access_token`, `upload_video`, `set_privacy`, `add_video_to_playlist` and `CATEGORY_EDUCATION` here too: `shares.py` and `compilation.py` use them | — |

**Benefit:** title/description work reads ~7 KB, and `yt_meta` gets the tests the architect report asks for (captions/hashtags).

**Risk:** low. Keep `youtube.GSC_SCOPE`, `youtube.authorize(..., scopes=, refresh_key=)` and `youtube.me()` where they are: `gsc-auth`, `yt-whoami` and `metrics` use them.

**Effort:** S–M (~40 min). Lower priority than F3/F4.

### F7. `engine/telegram.py` `process_updates` (142-line function)
- **What's tangled:** one loop handles both button callbacks and slash commands, including the compilation publish button, approve/unapprove/redo/new-saint, and pending-reply handling. It also enforces the safety gate (`EP_BUTTONS` inert in `publishing`/`published`).
- **Proposed split:** same file, three functions: `_on_button(cq, cfg, st, actions)`, `_on_command(text, cid, cfg, actions)` and `_on_reply(text, st, actions)`. Keep the `EP_BUTTONS` check as the first line of `_on_button` for episode buttons. No new module; the file is 15 KB.
- **Benefit:** mainly readability: a new command touches a 40-line function. Token gain is small.
- **Risk:** medium, because this is the human approval gate. Don't change callback-data strings (`approve:`, `comppublish:` etc.): buttons on messages already sent in Telegram still carry them.
- **Effort:** S (~30 min). **Optional.**

### F8. `site/src/pages/dash/index.astro` (311 lines, 23 KB)
- **What's tangled:** frontmatter, 57 lines of global `<style>` and a 163-line client `<script>` (fetch, charts, tables) in one page.
- **Proposed split:** `src/pages/dash/dash.css` and `src/scripts/dash.ts`, imported by the page. Astro bundles both.
- **Benefit:** a chart tweak reads the script (~12 KB), not the whole page.
- **Risk:** low. The page is private; `is:global` styles must stay global (import the CSS from the frontmatter or the script).
- **Effort:** S (~20 min). **Optional.**

### Not worth splitting
| File | Why it stays |
|---|---|
| `engine/metrics.py` (349 lines) | Already one collector function per platform; a tidy flat file. Only its `pipeline` import changes (F3). |
| `engine/compilation.py` (after F4) | ~14 KB of one product. |
| `engine/sung_video.py`, `engine/music_clips.py` | One product each, ~13 KB; they lose their private imports in F4. |
| `engine/telegram.py` beyond F7, `instagram.py`, `facebook.py`, `threads.py`, `tiktok.py` | Each a thin platform client of ≤7 KB. |
| `video/src/components.jsx` (247 lines, 13 KB) | Seven scene components that share `C`/`useFade`. Splitting per scene saves little and touches the render path. `Root.jsx` is Luis's uncommitted work: hands off. |
| `site/src/lib/*`, `components/*`, `layouts/Base.astro` | All ≤9 KB, already componentised. |
| `relay/worker.js` (106 lines) | One small Worker. |

---

## What must not break

**CLI entry points called by workflows** (command names and arguments must stay byte-identical):

| Workflow | Calls |
|---|---|
| `generate.yml` | `pipeline.py build-calendar`, `generate --date <d>`, `generate --max <n>` |
| `poll.yml` | `pipeline.py poll` |
| `compilation.yml` | `pipeline.py compilation <month> [--force]` |
| `maintenance.yml` | `pipeline.py $T` (unquoted), where `$T` ∈ `refresh-token`, `build-calendar`, `metrics`, `whoami`, `yt-whoami`, `fb-whoami`, `tt-whoami`, `th-whoami`, `post <id>` |
| `notify-failure.sh`, `site.yml` | `cd engine && python -c "import os, telegram; telegram.send(…)"` |

Keep `telegram.send` importable from `engine/` with only `requests` installed.

**Per-workflow dependencies** (the import chain of each command must fit what the workflow installs):

| Workflow | Installs | Implication |
|---|---|---|
| `maintenance.yml` | `requests cryptography` only | `pipeline.py` and every top-level import of `metrics`, `instagram`, `threads`, `calendar_build`, `costs` must not need anthropic, PIL or numpy. |
| `poll.yml` | adds `anthropic pillow`, no numpy | Nothing `poll` imports may need numpy. |

New modules should keep the current habit: heavy imports inside functions.

**Other invariants:**
- **Workflow filenames:** the relay dispatches `generate.yml` by name (`GH_WORKFLOW`).
- **State field names** in `state/episodes/*.json`, `stories.json`, `compilations/*.json`, `pinterest.json`, `checks.json`, `telegram.json`: unchanged.
- **Telegram callback-data strings:** unchanged.
- **Status transitions and the `find_reel` pre-check** in `publish_episode`: unchanged. The architect report's §4.3 holds.

**Verification constraint:** never run `pipeline.py poll`, `publish` or `post` locally to verify a refactor. They read real Telegram updates and post for real. Verify publish code offline (step 2) and let the next scheduled `poll` run be the live check.

---

## Action plan (each step lands on its own)

| # | Step | Finding | Effort | Verify |
|---|---|---|---|---|
| 1 | Slim `engine/CLAUDE.md` into `docs/engine/*.md` | F1 | S | `wc -c engine/CLAUDE.md` ≤ ~7 KB; grep each moved topic name and confirm it appears in a doc; reliability rules still in `engine/CLAUDE.md` verbatim. |
| 2 | Add offline tests: `engine/test_publish.py` (stdlib `unittest`, platform modules stubbed via `sys.modules`) covering the current four publishers, plus `build_caption` and `call_cost` | F3 prep | S | `cd engine && ../.venv/bin/python -m unittest test_publish` green against **today's** code. These tests are the safety net for steps 3–4 and cover part of the architect backlog. |
| 3 | Move code out of `pipeline.py` with no logic change: `captions.py`, `costs.py`, `generate.py`, `publish.py`, `checks.py`, plus re-export shims in `pipeline.py` | F3 | M | Step 2 tests green; `.venv/bin/python engine/pipeline.py -h` lists the same commands; `cd engine && python -c "import pipeline, metrics, telegram, youtube"`; `.venv/bin/python engine/pipeline.py cost` prints the same totals as before; in a fresh venv with only `requests cryptography`: `python engine/pipeline.py -h` and `python -c "import metrics"` (from `engine/`) both import; one `generate --date 2026-11-24 --no-upload` (spends ~$0.40 of Claude + Gemini; skip if the date already has an episode) renders to `work/`. After merge, watch the next `poll` and `generate` runs in Actions. |
| 4 | Dedupe the four platform publishers into `publish_once` | F3 | M | Step 2 tests extended: save-before-notify order, raising notify keeps the record, attempts cap at 3, `ep.status` untouched by secondary failures. Then a live check on the next day's 7:30 post (all five platforms recorded in the episode JSON, no duplicates). Land on a day Luis is around to watch Telegram. |
| 5 | Point `telegram.py`, `youtube.py`, `metrics.py` at `captions`/`costs`; drop shims; slim `main()` to one-line branches (`ig-media` → `instagram.media_info`, `books`/`fb-cover`/`backfill-story` bodies into their modules) | F3 | S | `grep -rn "from pipeline" engine/` returns nothing; `pipeline.py -h` unchanged; `pipeline.py ig-media <a known media id>` and `pipeline.py whoami` (read-only) print as before; tests green. |
| 6 | `cards.py` for the shared PIL/ffmpeg helpers | F4 | S–M | Before/after renders identical: `stories.py night <ep_id> /tmp/a.jpg` vs `/tmp/b.jpg`, plus a `music` card and `sung_video.py docs/sung-prayers/<spec>.json --frames`, compared with a PIL `ImageChops.difference(...).getbbox() is None`. `poll` import check without numpy. |
| 7 | Split `stories.py` (music, O Antiphons → data file) | F5 | S | Same pixel diff for night/music cards; `stories.py o-antiphons 2026` without `--upload` writes the seven cards to `work/`; `stories.json` untouched. Not between Dec 15 and 24. |
| 8 | Split `youtube.py` metadata/playlists | F6 | S–M | Unit tests for `build_title`/`build_description`/`localizations` on 3 real episodes, snapshotted before the move; `pipeline.py yt-whoami` prints `@allholysaints`. |
| 9 | Optional: `telegram.process_updates` handler split | F7 | S | Offline test feeding recorded update dicts (approve, approve on a published episode → inert, `/status`, redo reply) with `api`/`send` stubbed. |
| 10 | Optional: dashboard script/style out of `dash/index.astro` | F8 | S | `cd site && npm run build` clean; open `/dash/` in `npm run preview` and check the charts render. |

Steps 1, 6, 7, 8 and 10 don't depend on each other or on 3–5. Steps 2 → 3 → 4 → 5 are a chain. Recommended order: **1, 2, 3, 5, 6, 4**, and the rest only if wanted. Step 5 can land before step 4 because it doesn't touch publish logic. Step 4 is the one change that touches the never-re-post path, so it goes last among the core steps, with tests in place and Luis watching.

**Estimated saving per session once 1–6 land:** an engine session that touches publishing loads ~17k tokens today: ~6.5k for the two CLAUDE.md files plus ~10.5k for `pipeline.py`. Afterwards it loads ~6.7k: ~2.7k for the slim CLAUDE.md files, ~2.5k for `publish.py` and ~1.5k for `pipeline.py`. That's roughly 10k tokens less per session, with no change to what the bot does.
