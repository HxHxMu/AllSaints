# Monthly compilation (`compilation.py`)

*Moved out of `engine/CLAUDE.md` (2026-11-10) so it loads only when needed. Reliability rules stay in `engine/CLAUDE.md`.*

- On a month's last day (after the 7:30 post) the month's **published** Shorts become one 16:9 video: each Short centred on its own blurred icon, saint name/feast on the left, monogram on the right; a "Saints of <Month>" title card and an end card (tagline + `youtube.footer`) over `assets/music/allsaints-2.mp3`. Chapters per saint, links to each saint's page, the disclosure, Spanish `localizations` when every episode has `es`. Custom thumbnail (five icons + month). No AI, ~1 min of runner time per saint.
- Uploads **private**, then Telegram gets a 📣 Publish button (`comppublish:YYYY-MM`); the tap makes it public and puts it first in "Saints of <Month>". Ignoring it leaves it private.
- State `state/compilations/YYYY-MM.json` (status rendering → review → published | failed, `attempts` ≤ 3; the 1st–3rd runs retry a failed month). Skipped with fewer than 3 published episodes. First month: `config.compilation_from` ("2026-11").
- By hand: `pipeline.py compilation 2026-11 [--no-upload] [--force]` (`--no-upload` renders to `work/compilation-YYYY-MM/` only).

## Sung prayers (`sung_video.py`)
Original music on prayers written by saints (`docs/sung-prayers/`: research catalogue, one lyric master `.md` + video spec `.json` per release). `python engine/sung_video.py docs/sung-prayers/<spec>.json [--frames]` makes a 1920×1080 lyric video from `work/sung/NN/` (audio + icon): icon left, Latin + English per stanza cross-faded on soot, title cards, credits. `--frames` = layout check only. Stanza times come from a faster-whisper pass over the song. Upload is by hand (private first); not part of the daily pipeline.
