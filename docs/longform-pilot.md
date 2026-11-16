# Long-form pilot — St. Théophane Vénard

Format: 6–10 min, 16:9 YouTube. The icon opens into the story world, the story is told with parallax camera moves and
effects (minimal puppet motion: breathing, blinks), a few image-to-video hero shots for key moments, and the icon closes
it. The narrator tells the story; saints never get invented dialogue, and their own words appear as quoted text with the
source given. Luis scores each episode.

## 30 s concept (`video/src/concept/`)
- Composition `ConceptVenard` (1920×1080, 30 s). Preview: `npx remotion studio src/index.js`.
- Shots: icon + name → icon opens onto the village (5 s) → Tonkin village at night, rain, lantern → Vénard writing in
  his cage by candlelight, quote from his letter → back to the icon, "pray for us."
- Runs on flat stand-in art until the real art exists. Drop the PNGs below into `video/public/concept/venard/` and set
  `"useArt": true` in `venard.json`.
- Quote: letter to his father, 20 Jan 1861 (English wording varies by translation; check against Walsh's *A Modern
  Martyr* before publishing).

## Art (Nano Banana)

Keep the Jonny Quest idea for the *motion* (held paintings, camera moves, few moving parts), not for the drawing.
Comic-book ink lines made the first test read as a cartoon (Nov 2026), so the art now uses two painted styles:

**Icon (bookends):** traditional egg-tempera icon, not a portrait.
> Style: a traditional Byzantine icon in egg tempera on a gessoed wooden panel. Burnished gold-leaf ground with fine
> craquelure and worn edges. Stylized, not realistic: elongated face, long thin nose, almond eyes, small closed mouth,
> calm frontal gaze; flesh built up in layered ochre with fine white highlight strokes; garment folds drawn as rhythmic
> gold and dark lines. Flat, timeless, still. No outlines like a comic, no cartoon, no text or lettering.

**Story scenes:** candlelit oil painting, like Georges de La Tour or Rembrandt.
> Style: a reverent 19th-century oil painting with deep tenebrism, in the manner of Georges de La Tour and Rembrandt:
> near-black shadows, one warm light source, soft painted edges, visible brushwork and canvas texture, muted earth
> palette (umber, ochre, deep lapis, a touch of cinnabar), quiet and still like a devotional painting. Not a cartoon,
> no ink outlines, no comic shading, no text, no watermark.

Vénard's look (keep identical in every scene): slight French priest, 31, gentle oval face, clean-shaven, short dark
hair, calm downcast eyes; simple dark Vietnamese-style tunic (missionaries in hiding dressed locally), thin iron chain at
the ankle in the cage scenes.

**Generate painted scenes as whole paintings, not green-screen layers.** In the oil style Nano Banana paints the
"green" as dark painterly green and adds its own backdrop, so it won't key cleanly (first test, Nov 2026). Whole
paintings move by slow push-in, candle and lantern light, rain and fog in Remotion, and emerge from the dark with
feathered edges. Ask for the subject centered with dark margins all round. Download at full resolution (the previews
are ~1024 px wide).

| File | Style | Status | Prompt |
|---|---|---|---|
| `icon.png` (3:4) | Icon | ✅ done | Icon of a young martyr priest, Saint Théophane Vénard, frontal, half-length, in a dark tunic. Gold halo outlined in thin cinnabar. In his right hand he holds a small plain wooden hand-cross upright before his chest; his left hand is open, palm outward at the chest, in the gesture of a witness. Wide cinnabar border around the panel. Fill the frame with the panel only. |
| `cage-scene.png` | Scene | ✅ done | Saint Théophane Vénard seated cross-legged inside a small bamboo cage in a dark wooden guardhouse, writing a letter on a board on his knees, a thin chain at his ankle, a single candle beside him the only light, warm on his face and hands, everything else falling into shadow; eyes open, looking down at the letter, a peaceful face. Subject centered, deep dark margins all round. |
| `village-scene.png` | Scene | to do | Wide night landscape, northern Vietnam 1860, in the rain: three wooden stilt houses with thatched roofs among areca palms and banana leaves, one window glowing with a single warm lantern, flooded rice paddies faintly catching a veiled moon, dark lapis sky, far hills in rain haze. Houses centered, dark margins all round. 21:9 if possible, for a slow pan. |

## Hero shots (image-to-video, later)
Pick 2–4 per episode where motion carries meaning (the arrest at night, the ship leaving France). Keep each 4–6 s and
plan to spend roughly $5–20 per episode. Everything else stays in Remotion.
