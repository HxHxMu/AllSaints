# Suno: connection and workflow

**Connected (checked 2026-11-24).** Claude Code reaches Suno through the official Suno MCP (`https://api.suno.com/mcp`), signed in as Luis's account **@hxhxm**, **Pro plan** (commercial use for songs made while subscribed). It renews monthly on the 7th.

- **Credits:** 2,500 song credits a month. On 2026-11-24, 2,050 were left, plus **12 downloads** and 50 visuals credits. Downloads are the tight limit: download only takes Luis has chosen.
- **Models:** v6, v6-mini, v6-wild. Custom lyrics, style, cover, extend, stems, MIDI and voices are available.
- **Interactive sign-in only:** it works from a local Claude Code session, **not from GitHub Actions**. The daily pipeline never calls Suno.
- Don't use unofficial Suno API wrappers (against Suno's terms).

## Workflow for the next scores
1. Claude writes the lyric sheet + style prompt as usual (`bc2-NN-*.md`, section "Lyrics (for Suno or Gemini)"), with the attribution and public-domain checks done first ([catalogue.md](catalogue.md)).
2. Claude generates the takes in Suno directly (custom lyrics + style) and lists them for Luis to listen to in the Suno library. **Ask Luis before spending credits on a batch.**
3. Luis picks a take. Claude downloads only that one to `work/sung/<album>/<NN>/audio.wav` (gitignored) and notes the take, the date and the timing checks in the track's `.md`.
4. Credit stays "composed and produced by Luis E. Bonilla … made with AI tools (Suno)". AI vocals are disclosed plainly.
