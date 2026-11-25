"""Builds the queue entries for the Marguerite Bourgeoys series (Margaret's format) into promo/queue-entries.json.
Merge into state/shares.json and state/stories.json only after the media are on the GitHub release `series-marguerite-bourgeoys`."""
import json
from pathlib import Path
REL = "https://github.com/HxHxMu/AllSaints/releases/download/series-marguerite-bourgeoys/"
DISC = ("Narration is an AI voice; film and stills are AI-generated (Meta AI, Google Gemini). "
        "Score by Luis E. Bonilla, made with AI tools (Suno).")
TRUTH = "Every line comes from the record of her life; what comes from tradition is told as tradition."
TAGS = ["St. Marguerite Bourgeoys", "Lives of the Saints", "Catholic saints", "Montreal", "Canada", "silent film", "vertical drama"]
HASH = "#StMargueriteBourgeoys #LivesOfTheSaints #CatholicSaints #AllHolySaints"
PARTS = [  # (title, hook, date)
    ("The Procession", "At twenty, a girl walked in a Rosary procession, and her life changed.", "2027-01-11"),
    ("The Call", "A governor asked her to cross the ocean and teach. Today is her feast day.", "2027-01-12"),
    ("The Crossing", "In 1653, she crossed the Atlantic, bound for a colony with no school.", "2027-01-13"),
    ("The Stable", "The governor gave her an old stone stable. She made it the first school in Montreal.", "2027-01-14"),
    ("The Daughters", "Ships kept bringing young women to the colony, and she took them in.", "2027-01-15"),
    ("The Rule", "At seventy-eight, she saw her community's rule accepted.", "2027-01-16"),
]
HOOK_TEASER = "At twenty, a girl walked in a procession, and her life changed. This January, her story."
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
# teaser Thu Jan 7, Story Sat Jan 9, reminder Sun Jan 10 8:30 PM
trio("lots-marguerite-teaser", at("2027-01-07"), "Lives of the Saints · St. Marguerite Bourgeoys · Teaser",
     f"{HOOK_TEASER}\n\nLives of the Saints · St. Marguerite Bourgeoys\nA vertical drama in six parts. Part I, Monday, January 11, 7:30 PM ET; one part each evening through Saturday.\n\n{TRUTH}\n\n{DISC}\n\n{HASH}",
     REL + "teaser.mp4", REL + "teaser-cover.jpg",
     "At twenty, a girl walked in a procession, and her life changed. Lives of the Saints, a vertical drama in six parts, begins Mon Jan 11. #StMargueriteBourgeoys #CatholicSaints")
stories.append({"id": "lots-marguerite-teaser-story", "at": at("2027-01-09"), "video": REL + "teaser-story.mp4", "facebook_video": True,
                "status": "pending", "note": "Series teaser as a Story. Luis adds Instagram's countdown sticker (Mon Jan 11, 7:30 PM) by hand."})
shares.append({"id": "lots-marguerite-tomorrow-youtube", "at": at("2027-01-10", "20:30"), "platform": "youtube",
               "title": "Lives of the Saints begins tomorrow · St. Marguerite Bourgeoys",
               "message": f"Lives of the Saints begins tomorrow evening: Part I of St. Marguerite Bourgeoys, 7:30 PM ET.\n\n{DISC}\n\n#StMargueriteBourgeoys #LivesOfTheSaints",
               "tags": TAGS, "synthetic": True, "video": REL + "tomorrow.mp4", "status": "pending"})
stories.append({"id": "lots-marguerite-tomorrow-story", "at": at("2027-01-10", "20:30"), "video": REL + "tomorrow-story.mp4",
                "facebook_video": True, "status": "pending", "note": "Reminder: Lives of the Saints begins tomorrow evening."})
for i, (t, hook, d) in enumerate(PARTS, 1):
    nxt = ("The full film premieres on YouTube Monday, January 18, 7:30 PM ET." if i == 6 else "Next part tomorrow, 7:30 PM ET.")
    msg = (f"{hook}\n\nLives of the Saints · St. Marguerite Bourgeoys · Part {names[i-1]} of VI: {t}\n{nxt}\n\n{TRUTH}\n\n{DISC}\n\n{HASH}")
    trio(f"lots-marguerite-part{i}", at(d), f"Lives of the Saints · St. Marguerite Bourgeoys · Part {names[i-1]}: {t}", msg,
         REL + f"part{i}.mp4", REL + f"part{i}-cover.jpg",
         f"{hook} Part {names[i-1]} of VI. #StMargueriteBourgeoys #CatholicSaints")
shares.append({"id": "lots-marguerite-film-youtube", "at": at("2027-01-18"), "platform": "youtube",
               "title": "Lives of the Saints · St. Marguerite Bourgeoys · The Full Film (6 parts)",
               "message": f"The full film: Parts I–VI of St. Marguerite Bourgeoys, one continuous story.\n\nI The Procession · II The Call · III The Crossing · IV The Stable · V The Daughters · VI The Rule\n\n{TRUTH}\n\n{DISC}\n\n{HASH}",
               "tags": TAGS, "synthetic": True, "video": REL + "film.mp4", "status": "pending",
               "note": "16:9, vertical frame centred; YouTube, Facebook and the website (not Instagram or TikTok)."})
Path(__file__).with_name("queue-entries.json").write_text(json.dumps({"shares": shares, "stories": stories}, indent=1, ensure_ascii=False))
print(len(shares), "shares,", len(stories), "stories")
