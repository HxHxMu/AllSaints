# video/ — Remotion 4 (JSX)

- `src/Episode.jsx`, `src/components.jsx` (ArtScene, MapScene globe, TitleCard, CloseScene + outro, Captions, Atmosphere, Credit), `src/Cover.jsx`, `src/sample.json`.
- Preview: `npx remotion studio src/index.js` (uses `src/sample.json`). `public/episodes/*` is scratch except `sample/`.
- Look: slow Ken Burns on icon art, globe map zoom, name card, gold captions; colors/fonts/motion from `brand/brand.json`.
- Render ~0.3 s/frame on 2 cores: grain uses PNG tiles and the close-scene blur runs at ¼ res — keep it that way.
- Videos are ~45–70 MB; the Telegram review uses a downscaled `preview.mp4`.
- Known issue: the map place label can collide with captions when the location sits low on the globe.
- Remotion license: free for individuals / ≤3-person companies — fine for now.
