"""Script writing + independent fact-check pass."""
import json
from common import BRAND, claude_json, log, month_day_label

SYSTEM = f"""You write for "All Saints" (A.S.†): one-minute Instagram Reels on lesser-known Catholic saints, narrated by a warm, deep, unhurried male voice over sacred art.
Tagline: {BRAND['tagline']}
Voice: {BRAND['voice']['narrator']}
Writing rules:
- Length: {BRAND['writing']['length']}
- Structure: {' | '.join(BRAND['writing']['structure'])}
- """ + "\n- ".join(BRAND['writing']['rules']) + """
- Write for the ear: short sentences, concrete images, no parentheses, no abbreviations (write "Saint", not "St."), numbers as words when spoken (e.g. "the fourth century").
- Never invent quotes. Only quote the saint if a source gives the quote.
"""


def sources_block(sources):
    return "\n\n".join(f"[{i}] {s['title']} ({s['url']})\n{s['text']}" for i, s in enumerate(sources))


SCHEMA = """{
 "saint": {"name": "Saint Frumentius", "display_name": "St. Frumentius", "dates": "c. 300 – c. 383", "region": "Aksum, Ethiopia", "feast": "October 27", "martyr": false},
 "beats": [
  {"role": "hook", "text": "...", "visual": "art", "scene": "what an icon of this moment shows: figures, action, setting", "art_hint": "the image that fits + 2-4 Wikimedia Commons search terms"},
  {"role": "who", "text": "...", "visual": "map", "lat": 14.13, "lon": 38.72, "place": "Aksum · Ethiopia"},
  {"role": "story", "text": "...", "visual": "art", "scene": "...", "art_hint": "..."},
  {"role": "story", "text": "...", "visual": "art", "scene": "...", "art_hint": "..."},
  {"role": "story", "text": "...", "visual": "art", "scene": "...", "art_hint": "..."},
  {"role": "turn", "text": "...", "visual": "art", "scene": "...", "art_hint": "..."},
  {"role": "close", "text": "Saint Frumentius, pray for us.", "visual": "close"}
 ],
 "pronunciations": {"Aedesius": "Ay-DEE-see-us"},
 "caption_hook": "first line of the Instagram caption (not identical to the spoken hook)",
 "summary": "one-sentence summary for the caption",
 "youtube_title": "YouTube Shorts title, max 60 characters: the saint's name plus what makes the story remarkable, e.g. 'St. Frumentius: The Shipwrecked Boy Who Became a Bishop'; searchable, no clickbait, no emojis",
 "hashtags": ["#saintfrumentius", "#ethiopia", "..."],
 "share_cta": "Know someone named Frumentius? Send them their saint.",
 "claims": [{"claim": "...", "source": 0, "kind": "history|tradition"}]
}"""


def word_count(script):
    return sum(len(b["text"].split()) for b in script["beats"])


def write_script(saint, sources, date, note=None):
    feast = month_day_label(date)
    prompt = f"""Write today's episode.

Saint: {saint['name']} (Wikidata {saint['qid']}); feast day {feast}.
Why chosen: {saint.get('selection_reason', '')}
Catholic veneration: {saint.get('catholic_veneration', '')}
{('Reviewer feedback to apply: ' + note) if note else ''}

SOURCES (use only these facts):
{sources_block(sources)}

Return ONLY JSON in exactly this shape (the example values are placeholders):
{SCHEMA}

Requirements:
- 6 to 8 beats; first is "hook", second is "who" (with map coordinates of where their story mainly happened), last is "close" containing only the prayer line "Saint <Name>, pray for us." (use "Saints ... pray for us." for a pair).
- Total spoken words across all beats: 125-145.
- "martyr": true only if they died as a martyr.
- "dates": use "c." when uncertain; "fl." if only active dates are known.
- pronunciations: map any unusual name to a phonetic respelling (one token, hyphens allowed) so the narrator says it right; leave empty if none.
- Every factual claim must appear in "claims" with its source index; label legendary material kind "tradition" and phrase it that way in the script.
- 8-14 hashtags, lowercase: first the saint's name tag (e.g. #saintfrumentius), next the most specific place or patronage tag, then others.
- "share_cta": one gentle caption line inviting a share, only if it is natural: by name ("Know someone named Winifred? Send them their saint.") when the saint's name is still given today, or by patronage ("Send this to a nurse who could use a patron today.") only if the sources state the patronage. Otherwise "". Never pushy, no "comment Amen".
- "scene" (every art beat): one or two sentences describing a devotional icon of that beat's moment: who is shown, what they are doing, and the setting with period-correct architecture, dress and landscape for the place and era (e.g. Qing-dynasty Chinese buildings and dress for eighteenth-century Fujian). Show the saint as a figure in the scene; never ask for text or lettering. Keep it faithful to the sources: legendary moments only if the beat presents them as tradition."""
    for attempt in range(3):
        s = claude_json(prompt, system=SYSTEM)
        n = word_count(s)
        if 115 <= n <= 155:
            return s
        log(f"Script length {n} words; retrying")
        prompt += f"\n\nYour previous draft had {n} words. Hit 125-145 words."
    return s


def fact_check(script, sources):
    prompt = f"""You are a careful Catholic historian and fact-checker for a reverent saints series. Check this script against the SOURCES only.

SOURCES:
{sources_block(sources)}

SCRIPT JSON:
{json.dumps(script, ensure_ascii=False, indent=1)}

For every sentence: is it supported by the sources? Is legend presented as history? Are dates, places, titles (Saint/Blessed, martyr, bishop, etc.) right? Is anything theologically careless or irreverent? Is the map location right?
Fix problems with the smallest possible edits, keeping the same beats, roles and length (125-145 words).

Return ONLY JSON:
{{"verdict": "pass" | "fixed" | "reject",
 "issues": ["short description of each problem found and how it was fixed"],
 "script": <the full corrected script JSON, same shape as input>,
 "confidence": 0-100,
 "reviewer_note": "one line for the human approver: anything they should double-check"}}
Use "reject" only if the saint is not actually venerated in the Catholic Church or the sources are too thin for an honest minute."""
    res = claude_json(prompt)
    log(f"Fact-check: {res.get('verdict')} ({res.get('confidence')}) issues={len(res.get('issues', []))}")
    return res
