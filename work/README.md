# work/: local scratch

`work/` is gitignored and syncs to Luis's Google Drive. GitHub Actions never reads it, and the daily pipeline only writes throwaway files here (`work/music/`, `work/compilation-YYYY-MM/`, downloads). Scripts and notes worth keeping are force-added (`git add -f`). Large media stay local only.

## lives/: Lives of the Saints (silent-film series)
One folder per saint, all in the same layout and built by the shared scripts:

```
lives/
  build.py                art | voice | video | trim   --saint <slug> --part partN [--live]
  startframes.py          <slug> partN 2 4 5 [--variants a,b]   (Gemini start frames for the clips)
  UnifrakturMaguntia-Book.ttf
  <slug>/
    series.json           saint, title card, setting, look, refs, "same person" line, score notes
    score.wav             Luis's Suno score for the series
    outline.md / notes
    partN/                episode.json, start/ (frames + motion.md), live/N.mp4 (clips), art/, voice/, build/,
                          lives-<slug>-partN-live-approved.mp4
    teaser/  tomorrow/    promo episodes (episode.json + voice)
    promo/                teaser.py, covers.py, covers/ (Ember covers + release copies opening on the cover)
    release/              the files uploaded to the GitHub release `series-<slug>`
```

- **margaret-of-cortona/**: Series 1 (was `work/nocturnes/` until 2026-11-25). Her approved masters keep their old names (`partN/nocturnes-margaret-partN-live-approved.mp4`); a new render from `build.py` writes `lives-margaret-of-cortona-partN…`. Part I shot 4 stays black and white through `"mono": [3]` in `part1/episode.json`.
- **john-of-god/**: Series 2.
- **marguerite-bourgeoys/**: started.

Posts are scheduled in `state/shares.json` / `state/stories.json` with GitHub release URLs, so moving files here never breaks a scheduled post.

## Music
- `blue-chant/`: album cover and long-form video scripts.
- `music-stories/`: weekly music Story images.
- `sung/<album>/<NN>/`: Suno takes (see `docs/sung-prayers/suno.md`).
