"""Builds the queue entries for the John of God series (Margaret's format) into promo/queue-entries.json.
Merge into state/shares.json and state/stories.json only after the media are on the GitHub release `series-john-of-god`."""
import json
from pathlib import Path
REL = "https://github.com/HxHxMu/AllSaints/releases/download/series-john-of-god/"
DISC = ("Narration is an AI voice; film and stills are AI-generated (Meta AI, Google Gemini). "
        "Score by Luis E. Bonilla, made with AI tools (Suno).")
TRUTH = "Every line comes from the record of his life; what comes from tradition is told as tradition."
TAGS = ["St. John of God", "Lives of the Saints", "Catholic saints", "Advent", "silent film", "vertical drama"]
HASH = "#StJohnOfGod #LivesOfTheSaints #CatholicSaints #Advent #AllHolySaints"
PARTS = [  # (title, hook, date)
    ("The Runaway", "At eight, he followed a traveling priest away from home.", "2026-12-14"),
    ("The Gallows", "A soldier stood under the gallows, condemned to hang. An officer spoke, and he was spared.", "2026-12-15"),
    ("The Crossing", "He carried holy books and pictures from town to town, and sold them for almost nothing.", "2026-12-16"),
    ("The Madman", "He ran through Granada crying for mercy, and the city called him mad.", "2026-12-17"),
    ("The House", "He gave his cloak to every beggar, until a bishop gave him a habit, and a name.", "2026-12-18"),
    ("The River", "The hospital was burning, and John went in.", "2026-12-19"),
]
HOOK_TEASER = "At eight, he followed a stranger away from home. This Advent, his story."
shares, stories = [], []


def at(d, hm="19:30"): return f"{d}T{hm}:00-05:00"


def trio(id_, when, title, msg, video, cover=None, tiktok=None, tiktok_note=None, tiktok_when=None, yt=True):
    if yt:
        shares.append({"id": f"{id_}-youtube", "at": when, "platform": "youtube", "title": title, "message": msg,
                       "tags": TAGS, "synthetic": True, "video": video, "status": "pending"})
    for plat in ("instagram", "facebook_reel"):
        e = {"id": f"{id_}-{'facebook' if plat == 'facebook_reel' else plat}", "at": when, "platform": plat, "message": msg,
             "video": video, "status": "pending"}
        if cover: e["cover"] = cover
        shares.append(e)
    if tiktok:
        shares.append({"id": f"{id_}-tiktok", "at": tiktok_when or when.replace("19:30", "19:15"), "platform": "tiktok",
                       "message": tiktok, "video": video, "status": "pending",
                       "note": "Inbox draft; Luis posts it at 7:30 PM with this caption and TikTok's AI label on."})


names = ["I", "II", "III", "IV", "V", "VI"]
# teaser Thu Dec 10, Story Sat Dec 12, reminder Sun Dec 13 8:30 PM
trio("lots-john-teaser", at("2026-12-10"), "Lives of the Saints · St. John of God · Teaser",
     f"{HOOK_TEASER}\n\nLives of the Saints · St. John of God\nA vertical drama in six parts. Part I, Monday, December 14, 7:30 PM ET; one part each evening through Saturday.\n\n{TRUTH}\n\n{DISC}\n\n{HASH}",
     REL + "teaser.mp4", REL + "teaser-cover.jpg",
     "At eight, he followed a stranger away from home. Lives of the Saints, a vertical drama in six parts, begins Mon Dec 14. #StJohnOfGod #CatholicSaints #Advent")
stories.append({"id": "lots-john-teaser-story", "at": at("2026-12-12"), "video": REL + "teaser-story.mp4", "facebook_video": True,
                "status": "pending", "note": "Series teaser as a Story. Luis adds Instagram's countdown sticker (Mon Dec 14, 7:30 PM) by hand."})
shares.append({"id": "lots-john-tomorrow-youtube", "at": at("2026-12-13", "20:30"), "platform": "youtube",
               "title": "Lives of the Saints begins tomorrow · St. John of God",
               "message": f"Lives of the Saints begins tomorrow evening: Part I of St. John of God, 7:30 PM ET.\n\n{DISC}\n\n#StJohnOfGod #LivesOfTheSaints #Advent",
               "tags": TAGS, "synthetic": True, "video": REL + "tomorrow.mp4", "status": "pending"})
stories.append({"id": "lots-john-tomorrow-story", "at": at("2026-12-13", "20:30"), "video": REL + "tomorrow-story.mp4",
                "facebook_video": True, "status": "pending", "note": "Reminder: Lives of the Saints begins tomorrow evening."})
for i, (t, hook, d) in enumerate(PARTS, 1):
    nxt = ("The full film premieres on YouTube Monday, December 21, 7:30 PM ET." if i == 6 else "Next part tomorrow, 7:30 PM ET.")
    msg = (f"{hook}\n\nLives of the Saints · St. John of God · Part {names[i-1]} of VI: {t}\n{nxt}\n\n{TRUTH}\n\n{DISC}\n\n{HASH}")
    trio(f"lots-john-part{i}", at(d), f"Lives of the Saints · St. John of God · Part {names[i-1]}: {t}", msg,
         REL + f"part{i}.mp4", REL + f"part{i}-cover.jpg",
         f"{hook} Part {names[i-1]} of VI. #StJohnOfGod #CatholicSaints #Advent")
shares.append({"id": "lots-john-film-youtube", "at": at("2026-12-21"), "platform": "youtube",
               "title": "Lives of the Saints · St. John of God · The Full Film (6 parts)",
               "message": f"The full film: Parts I–VI of St. John of God, one continuous story.\n\nI The Runaway · II The Gallows · III The Crossing · IV The Madman · V The House · VI The River\n\n{TRUTH}\n\n{DISC}\n\n{HASH}",
               "tags": TAGS, "synthetic": True, "video": REL + "film.mp4", "status": "pending",
               "note": "16:9, vertical frame centred; YouTube, Facebook and the website (not Instagram or TikTok)."})
Path(__file__).with_name("queue-entries.json").write_text(json.dumps({"shares": shares, "stories": stories}, indent=1, ensure_ascii=False))
print(len(shares), "shares,", len(stories), "stories")
