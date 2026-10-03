"""Server-only moderation dictionary for chat text.

Never serialise this module to clients: keeping the list on the server stops
users from downloading the full blocklist to work around it.

Each entry: (term, severity, lang[, flags])

* term      - a word or a space-separated phrase, written plainly. Variants with
              repeated letters, spacing, punctuation, case, leetspeak and
              look-alike Unicode are handled by the matcher, so only list real
              spelling variants here.
* severity  - LOW is detected and logged but not blocked (too ambiguous: names,
              animals, mild everyday words). MEDIUM / HIGH are blocked by default
              (threshold: settings.CHAT_MODERATION_BLOCK_SEVERITY).
* lang      - "en" English, "rom" Romanized Nepali/Hindi, "dev" Devanagari.
* flags     - "embedded": also match inside a longer word (only for terms that
              never appear inside normal words, e.g. "fuck" in "motherfucking").

Deliberately NOT listed (dating app): ordinary romantic or consensual sexual
words (sex, sexy, kiss, horny, nude, boobs, etc.). Only degrading slurs,
unsolicited demands for nudes, and explicit sexual harassment phrases are listed.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Category(str, Enum):
    PROFANITY = "profanity"
    INSULT = "insult"
    HARASSMENT = "harassment"
    SEXUAL_HARASSMENT = "sexual_harassment"
    THREAT = "threat"
    HATE = "hate"
    SPAM_SCAM = "spam_scam"


L, M, H = Severity.LOW, Severity.MEDIUM, Severity.HIGH
EMBED = ("embedded",)

LEXICON: dict[Category, list[tuple]] = {
    Category.PROFANITY: [
        # English
        ("fuck", M, "en", EMBED),
        ("fck", M, "en"),
        ("fuk", M, "en"),
        ("fuq", M, "en"),
        ("phuck", M, "en", EMBED),
        ("fvck", M, "en", EMBED),
        ("fcuk", M, "en"),
        ("fking", M, "en"),
        ("fkn", M, "en"),
        ("wtf", L, "en"),
        ("stfu", M, "en"),
        ("shit", M, "en"),
        ("bullshit", M, "en"),
        ("shithead", M, "en"),
        ("bitch", M, "en"),
        ("biatch", M, "en"),
        ("bastard", M, "en"),
        ("asshole", M, "en"),
        ("arsehole", M, "en"),
        ("dickhead", M, "en"),
        ("cunt", H, "en"),
        ("wanker", M, "en"),
        ("twat", M, "en"),
        ("ass", L, "en"),
        ("dick", L, "en"),
        ("piss", L, "en"),
        ("piss off", M, "en"),
        # Romanized Nepali / Hindi
        ("muji", M, "rom"),
        ("mujhi", M, "rom"),
        ("machikne", M, "rom"),
        ("machikney", M, "rom"),
        ("mchikne", M, "rom"),
        ("chikne", M, "rom"),
        ("chikney", M, "rom"),
        ("chikchu", M, "rom"),
        ("chikdinchu", M, "rom"),
        ("chikidinchu", M, "rom"),
        ("chikaula", M, "rom"),
        ("chik", L, "rom"),
        ("lado", M, "rom"),
        ("puti", M, "rom"),
        ("geda", L, "rom"),
        ("gu", L, "rom"),
        ("gu kha", M, "rom"),
        ("gu khana", M, "rom"),
        ("madarchod", H, "rom", EMBED),
        ("maderchod", H, "rom", EMBED),
        ("madarchood", H, "rom", EMBED),
        ("bhenchod", H, "rom", EMBED),
        ("behenchod", H, "rom", EMBED),
        ("bhosdike", M, "rom"),
        ("bhosdi", M, "rom"),
        ("bhosda", M, "rom"),
        ("chutiya", M, "rom"),
        ("chutiye", M, "rom"),
        ("chutia", M, "rom"),
        ("gandu", M, "rom"),
        ("lund", L, "rom"),  # also a place name (Lund)
        ("lauda", M, "rom"),
        ("laude", M, "rom"),
        ("mkc", M, "rom"),
        ("bsdk", M, "rom"),
        ("bc", L, "rom"),
        ("mc", L, "rom"),
        # Devanagari
        ("मुजी", M, "dev"),
        ("मचिक्ने", M, "dev"),
        ("चिक्ने", M, "dev"),
        ("चिक्छु", M, "dev"),
        ("चिकिदिन्छु", M, "dev"),
        ("लाडो", M, "dev"),
        ("पुती", M, "dev"),
        ("गु खा", M, "dev"),
        ("मादरचोद", H, "dev"),
        ("चूतिया", M, "dev"),
        ("भोसडी", M, "dev"),
        ("गाँडु", M, "dev"),
        ("लौडा", M, "dev"),

        # --- more English ---
        ("fuckface", M, "en", EMBED),
        ("cocksucker", M, "en"),
        ("dipshit", M, "en"),
        ("shitface", M, "en"),
        ("bellend", M, "en"),
        ("mofo", M, "en"),
        ("piece of shit", M, "en"),
        ("eat shit", M, "en"),
        ("gtfo", L, "en"),
        ("cock", L, "en"),
        ("pussy", L, "en"),
        ("tits", L, "en"),
        # --- Hindi (Romanized) ---
        ("madarjaat", H, "rom"),
        ("bahinchod", H, "rom", EMBED),
        ("bahanchod", H, "rom", EMBED),
        ("bhenchodd", H, "rom"),
        ("chut", L, "rom"),  # also "chhoot" (discount) after folding
        ("chodu", M, "rom"),
        ("chudai", M, "rom"),
        ("gaand", M, "rom"),
        ("gaandu", M, "rom"),
        ("jhaat", L, "rom"),  # "jhatka" (jolt) folds onto it
        ("jhaatu", M, "rom"),
        ("jhantu", M, "rom"),
        ("lavde", M, "rom"),
        ("lode", L, "rom"),  # also English "lode"
        ("loda", M, "rom"),
        ("lodu", M, "rom"),
        ("bhosadi", M, "rom"),
        ("bhosdiwala", M, "rom"),
        ("bhosdiwale", M, "rom"),
        ("maa chod", H, "rom"),
        ("maa ki chut", H, "rom"),
        ("teri maa ki", M, "rom"),
        ("teri behen ki", M, "rom"),
        ("behen ke lode", H, "rom"),
        ("tatti", L, "rom"),
        ("bakchod", L, "rom"),
        # --- Bhojpuri / Maithili (Romanized) ---
        ("lundwa", M, "rom"),
        ("maai chod", H, "rom"),
        ("maiya chod", H, "rom"),
        ("tohar maai ke", M, "rom"),
        ("tor maai ke", M, "rom"),
        ("tohar bahin ke", M, "rom"),
        # --- more Nepali (Romanized) ---
        ("chikauna", M, "rom"),
        ("chikaune", M, "rom"),
        ("chikeko", M, "rom"),
        ("lado kha", M, "rom"),
        ("puti kha", M, "rom"),
        # --- Devanagari: Nepali / Hindi / Bhojpuri ---
        ("चिकाउने", M, "dev"),
        ("चिकेको", M, "dev"),
        ("लाडो खा", M, "dev"),
        ("गु", L, "dev"),
        ("बहनचोद", H, "dev"),
        ("भेनचोद", H, "dev"),
        ("बहिनचोद", H, "dev"),
        ("भोसड़ीके", M, "dev"),
        ("चूत", M, "dev"),
        ("चुदाई", M, "dev"),
        ("लंड", M, "dev"),
        ("झाटू", M, "dev"),
        ("गांड", M, "dev"),
        ("माई चोद", H, "dev"),
        ("तोहार माई के", M, "dev"),
        ("तेरी माँ की", M, "dev"),
    ],
    Category.INSULT: [
        ("idiot", L, "en"),
        ("stupid", L, "en"),
        ("moron", L, "en"),
        ("loser", L, "en"),
        ("dumbass", M, "en"),
        ("jackass", M, "en"),
        ("harami", M, "rom"),
        ("haramkhor", M, "rom"),
        ("jatha", M, "rom"),
        ("jaatha", M, "rom"),
        ("kuttiya", M, "rom"),
        ("kutta", L, "rom"),
        ("gadha", L, "rom"),
        ("kukur ko chhora", M, "rom"),
        ("kukur ko chhoro", M, "rom"),
        ("kukur ko chora", M, "rom"),
        ("kukur ko choro", M, "rom"),
        ("हरामी", M, "dev"),
        ("हरामखोर", M, "dev"),
        ("जाठा", M, "dev"),
        ("कुकुर छोरा", M, "dev"),
        ("कुकुर छोरो", M, "dev"),

        # --- more English ---
        ("douchebag", M, "en"),
        ("scumbag", M, "en"),
        ("douche", L, "en"),
        ("pedo", M, "en"),
        ("pedophile", M, "en"),
        ("rapist", L, "en"),
        # --- Hindi / Bhojpuri (Romanized) ---
        ("kamina", M, "rom"),
        ("kamine", M, "rom"),
        ("kamini", M, "rom"),
        ("haramzada", M, "rom"),
        ("haramzadi", M, "rom"),
        ("haraamzaada", M, "rom"),
        ("bhadwa", M, "rom"),
        ("bhadwe", M, "rom"),
        ("dalla", M, "rom"),
        ("suar ki aulad", M, "rom"),
        ("kutte ki aulad", M, "rom"),
        ("kutte", L, "rom"),
        ("kutti", L, "rom"),
        ("suar", L, "rom"),
        ("ullu ka pattha", L, "rom"),
        # --- more Nepali (Romanized) ---
        ("boka", L, "rom"),
        ("bhalu", L, "rom"),
        ("gadha ko chhora", M, "rom"),
        ("suar ko chhora", M, "rom"),
        # --- Devanagari ---
        ("कमीना", M, "dev"),
        ("कमीने", M, "dev"),
        ("हरामज़ादा", M, "dev"),
        ("हरामजादी", M, "dev"),
        ("भड़वा", M, "dev"),
        ("कुत्ता", L, "dev"),
        ("कुत्ती", L, "dev"),
        ("सूअर", L, "dev"),
        ("बोका", L, "dev"),
        ("भालु", L, "dev"),
    ],
    Category.HARASSMENT: [
        ("kill yourself", H, "en"),
        ("go kill yourself", H, "en"),
        ("killyourself", H, "en"),
        ("kys", H, "en"),
        ("go die", M, "en"),
        ("die bitch", H, "en"),
        ("nobody will ever love you", L, "en"),
        ("mar ja", M, "rom"),
        ("marija", M, "rom"),
        ("मरिजा", M, "dev"),

        ("nobody loves you", L, "en"),
        ("you should die", H, "en"),
        ("hope you die", H, "en"),
        ("mar ja", M, "rom"),
        ("mar jao", M, "rom"),
        ("mar jaa", M, "rom"),
        ("मर जा", M, "dev"),
    ],
    Category.SEXUAL_HARASSMENT: [
        ("whore", M, "en"),
        ("slut", M, "en"),
        ("skank", M, "en"),
        ("hoe", L, "en"),
        ("send nudes", M, "en"),
        ("send nude", M, "en"),
        ("send me nudes", M, "en"),
        ("send me nude", M, "en"),
        ("send me your nudes", M, "en"),
        ("suck my dick", M, "en"),
        ("suck my cock", M, "en"),
        ("show me your tits", M, "en"),
        ("randi", M, "rom"),
        ("rendi", M, "rom"),
        ("besya", M, "rom"),
        ("beshya", M, "rom"),
        ("bheshya", M, "rom"),
        ("khate", L, "rom"),
        ("रण्डी", M, "dev"),
        ("रन्डी", M, "dev"),
        ("वेश्या", M, "dev"),

        ("thot", M, "en"),
        ("hooker", L, "en"),
        ("send pics", L, "en"),
        ("leak your nudes", H, "en"),
        ("leak your photos", H, "en"),
        ("i will leak your", H, "en"),
        ("i will post your nudes", H, "en"),
        ("randibaaz", M, "rom"),
        ("randwa", M, "rom"),
        ("chinal", M, "rom"),
        ("chhinal", M, "rom"),
        ("chhinar", M, "rom"),
        ("chhinaar", M, "rom"),
        ("छिनाल", M, "dev"),
        ("छिनार", M, "dev"),
        ("रंडीबाज", M, "dev"),
    ],
    Category.THREAT: [
        ("i will kill you", H, "en"),
        ("ill kill you", H, "en"),
        ("i am going to kill you", H, "en"),
        ("im going to kill you", H, "en"),
        ("gonna kill you", H, "en"),
        ("i will rape you", H, "en"),
        ("ill rape you", H, "en"),
        ("rape you", H, "en"),
        ("i know where you live", M, "en"),
        ("throw acid", H, "en"),
        ("acid attack", M, "en"),
        ("maar dinchu", H, "rom"),
        ("mardinchu", H, "rom"),
        ("maardinchu", H, "rom"),
        ("maaridinchu", H, "rom"),
        ("kaat dinchu", H, "rom"),
        ("kaatdinchu", H, "rom"),
        ("katidinchu", H, "rom"),
        ("jyan lindinchu", H, "rom"),
        ("jyan linchu", H, "rom"),
        ("मारिदिन्छु", H, "dev"),
        ("मार्दिन्छु", H, "dev"),
        ("मार्छु", M, "dev"),
        ("काटिदिन्छु", H, "dev"),
        ("ज्यान लिन्छु", H, "dev"),
        ("ज्यान लिदिन्छु", H, "dev"),

        ("i will stab you", H, "en"),
        ("i will shoot you", H, "en"),
        ("i will beat you", M, "en"),
        ("i will hurt you", M, "en"),
        ("i will find you", L, "en"),
        ("you are dead", L, "en"),
        # Hindi
        ("maar dunga", M, "rom"),
        ("maar daalunga", H, "rom"),
        ("maar dalunga", H, "rom"),
        ("jaan se maar dunga", H, "rom"),
        ("tujhe maar dunga", H, "rom"),
        ("kaat dunga", H, "rom"),
        ("acid phek dunga", H, "rom"),
        ("rape kar dunga", H, "rom"),
        # Bhojpuri / Maithili
        ("maar deb", M, "rom"),
        ("jaan maar deb", H, "rom"),
        ("kaat deb", H, "rom"),
        # Nepali
        ("khattam garidinchu", H, "rom"),
        ("thokdinchu", M, "rom"),
        ("thokidinchu", M, "rom"),
        ("sakidinchu", L, "rom"),
        ("acid hanidinchu", H, "rom"),
        # Devanagari
        ("मार दूंगा", M, "dev"),
        ("मार डालूंगा", H, "dev"),
        ("जान से मार दूंगा", H, "dev"),
        ("काट दूंगा", H, "dev"),
        ("जान मार देब", H, "dev"),
        ("मार देब", M, "dev"),
        ("खत्तम गरिदिन्छु", H, "dev"),
        ("थोकिदिन्छु", M, "dev"),
    ],
    Category.HATE: [
        ("nigger", H, "en", EMBED),
        ("nigga", M, "en"),
        ("faggot", H, "en", EMBED),
        ("fag", M, "en"),
        ("tranny", M, "en"),
        ("retard", M, "en"),
        ("chink", M, "en"),
        ("kike", H, "en"),
        ("paki", M, "en"),
        ("hijada", M, "rom"),
        ("hijra", L, "rom"),
        ("achhut", M, "rom"),
        ("achut", M, "rom"),
        ("हिजडा", M, "dev"),
        ("अछुत", M, "dev"),

        ("dyke", M, "en"),
        ("gook", H, "en"),
        ("wetback", H, "en"),
        ("chakka", L, "rom"),
        ("madise", M, "rom"),
        ("madhise", M, "rom"),
        ("bhote", L, "rom"),
        ("dhoti", L, "rom"),
        ("मधिसे", M, "dev"),
        ("मदिसे", M, "dev"),
        ("भोटे", L, "dev"),
        ("धोती", L, "dev"),
        ("छक्का", L, "dev"),
    ],
    # Scam phrases are detected and logged (LOW) but not blocked by default:
    # some overlap with normal talk. Raise to MEDIUM here to start blocking.
    Category.SPAM_SCAM: [
        ("western union", L, "en"),
        ("send me money", L, "en"),
        ("bitcoin investment", L, "en"),
        ("crypto investment", L, "en"),
        ("guaranteed profit", L, "en"),
        ("double your money", L, "en"),
        ("gift card code", L, "en"),
    ],
}

# Suffixes a matched word may carry ("bitches", "fucking", "mujiko", "रण्डीको").
EN_SUFFIXES = ("s", "es", "ed", "er", "ers", "ing", "in", "y", "ies")
ROM_SUFFIXES = ("ko", "ki", "ka", "ke", "le", "lai", "haru", "harulai", "ho", "hos", "wa", "va")
DEV_SUFFIXES = ("को", "की", "का", "के", "ले", "लाई", "हरु", "हरू", "हरुलाई", "हरूलाई", "हो", "वा")
