"""Chat text moderation (English, Romanized Nepali, Devanagari Nepali).

The backend is the authoritative enforcement layer. Every user-authored chat
text path (REST send, WebSocket send, WebSocket edit) calls ``moderate_text`` /
``enforce_clean_text`` before anything is saved, broadcast or pushed.

How matching works (no naive substring search, which causes false positives
like "class", "assessment", "therapist", "Scunthorpe"):

1. Normalise the text: Unicode NFKC, case-fold, drop invisible characters,
   map look-alike Cyrillic/Greek letters to Latin, strip Latin accents.
2. Tokenise on whitespace. Inside a token, punctuation is removed
   ("w.o.r.d" -> "word"); a run of single letters is joined ("w o r d" -> "word").
3. Each token is compared **as a whole word** against the dictionary, allowing
   - repeated letters ("wooord" matches "word", but "as" never matches "ass"),
   - leetspeak ("w0rd", "sh1t", "$hit"), with a digits-stripped fallback,
   - a small set of grammatical suffixes ("bitches", "mujiko", "रण्डीको"),
   - Romanized spelling folds (ee->i, oo->u, z->j, w->v, ph->f),
   - Devanagari spelling folds (ी/ि, ू/ु, ँ/ं, ण/न, व/ब, श/ष/स, nukta).
   Only a few terms that never occur inside normal words are matched inside
   longer words ("embedded", e.g. "motherfucking").
4. Multi-word phrases are matched over consecutive tokens.

The result never contains the matched word, so clients cannot use it to
enumerate the dictionary.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

from .moderation_lexicon import (
    DEV_SUFFIXES,
    EN_SUFFIXES,
    LEXICON,
    ROM_SUFFIXES,
    Category,
    Severity,
)

logger = logging.getLogger("duo.moderation")

INAPPROPRIATE_MESSAGE = "This message contains inappropriate language."
INAPPROPRIATE_CODE = "inappropriate_content"

# Categories a receiver may opt in to (chat setting "Filter offensive language").
# Threats, harassment, sexual harassment and hate are never relaxable.
RELAXABLE_CATEGORIES = frozenset({Category.PROFANITY, Category.INSULT})


class InappropriateContent(APIException):
    """400 with the shared error shape: {code, message, detail}."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = INAPPROPRIATE_MESSAGE
    default_code = INAPPROPRIATE_CODE


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

# Cyrillic / Greek letters that look like Latin ones ("fuсk" with Cyrillic с).
_CONFUSABLES = str.maketrans(
    {
        "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h",
        "о": "o", "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "і": "i",
        "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w", "һ": "h",
        "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v",
        "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x", "γ": "y", "ϲ": "c",
        "ℓ": "l", "ƒ": "f", "ı": "i", "ł": "l", "ø": "o", "ß": "ss", "æ": "ae", "œ": "oe",
    }
)

# Leetspeak / symbol substitutions, applied only inside tokens that contain letters.
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g",
     "@": "a", "$": "s", "!": "i", "|": "l", "+": "t", "€": "e", "£": "l"}
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DEV_KEEP = re.compile(r"[^ऀ-ॿ]")
_LATIN_KEEP = re.compile(r"[^a-z0-9]")
_DIGITS = re.compile(r"[0-9]")
_DEV_FOLDS = (
    ("़", ""),   # nukta
    ("ँ", "ं"),        # chandrabindu -> anusvara
    ("ी", "ि"),
    ("ू", "ु"),
    ("ण", "न"),
    ("व", "ब"),
    ("श", "स"),
    ("ष", "स"),
    ("ं", "न्"),
    ("।", ""),
)


def _strip_latin_accents(text: str) -> str:
    """"fúck" -> "fuck". Keeps Devanagari vowel signs (they are combining marks too)."""
    out = []
    for ch in unicodedata.normalize("NFKD", text):
        if unicodedata.category(ch) == "Mn" and out and out[-1].isascii():
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def normalize_text(text: str) -> str:
    """Canonical lowercase text used by the matcher (whitespace preserved)."""
    text = unicodedata.normalize("NFKC", text or "")
    # Drop zero-width / format characters (ZWJ, ZWNJ, soft hyphen, BOM...).
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = text.casefold().translate(_CONFUSABLES)
    return _strip_latin_accents(text)


def _collapse(s: str) -> str:
    """Collapse every run of the same character: "wooord" -> "word"."""
    return re.sub(r"(.)\1+", r"\1", s)


def _rle(s: str) -> list[tuple[str, int]]:
    return [(m.group(1), len(m.group(0))) for m in re.finditer(r"(.)\1*", s)]


def _fold_rom(s: str) -> str:
    """Romanized spelling folds, then collapse repeats: "mujeee" -> "muji"."""
    s = re.sub(r"e{2,}", "i", s)
    s = re.sub(r"o{2,}", "u", s)
    s = s.replace("ph", "f").replace("z", "j").replace("w", "v")
    return _collapse(s)


def _fold_dev(s: str) -> str:
    for a, b in _DEV_FOLDS:
        s = s.replace(a, b)
    return _collapse(s)


@dataclass(frozen=True)
class _Token:
    """One word in several comparable forms (variants cover leet vs digits)."""

    latin: tuple[str, ...]  # raw latin variants (lowercase a-z only)
    dev: str  # folded Devanagari ("" when the token is not Devanagari)
    raw: str = ""


def _token_forms(raw: str) -> _Token:
    if _DEVANAGARI.search(raw):
        return _Token(latin=(), dev=_fold_dev(_DEV_KEEP.sub("", raw)), raw=raw)
    variants = []
    if re.search(r"[a-z]", raw):
        leet = _LATIN_KEEP.sub("", raw.translate(_LEET))
        no_digits = _LATIN_KEEP.sub("", _DIGITS.sub("", raw))
        for v in (leet, no_digits):
            v = _DIGITS.sub("", v)
            if v and v not in variants:
                variants.append(v)
    else:
        v = _LATIN_KEEP.sub("", raw)
        if v:
            variants.append(v)
    return _Token(latin=tuple(variants), dev="", raw=raw)


# English contractions are expanded before punctuation is stripped, otherwise
# "who're" -> "whore" and "she'll" -> "shell" (false positives).
_CONTRACTIONS = (
    (re.compile(r"(?<=[a-z])['’]re\b"), " are"),
    (re.compile(r"(?<=[a-z])['’]ll\b"), " will"),
    (re.compile(r"(?<=[a-z])['’]ve\b"), " have"),
    (re.compile(r"(?<=[a-z])['’]m\b"), " am"),
    (re.compile(r"(?<=[a-z])['’]d\b"), " would"),
    (re.compile(r"(?<=[a-z])['’]s\b"), " is"),
    (re.compile(r"(?<=[a-z])n['’]t\b"), " not"),
)


def _expand_contractions(text: str) -> str:
    for pattern, repl in _CONTRACTIONS:
        text = pattern.sub(repl, text)
    return text


def tokenize(text: str) -> list[_Token]:
    """Tokens with single-letter runs joined: "f u c k" / "f. u. c. k" -> "fuck"."""
    raw_tokens = _expand_contractions(normalize_text(text)).split()
    merged: list[str] = []
    run: list[str] = []

    def flush():
        if len(run) >= 3:
            merged.append("".join(run))
        else:
            merged.extend(run)
        run.clear()

    for raw in raw_tokens:
        core = _LATIN_KEEP.sub("", raw.translate(_LEET)) if not _DEVANAGARI.search(raw) else raw
        if not core:
            continue  # punctuation-only token ("f . u . c . k") must not break a run
        if len(core) == 1 and core.isalpha():
            run.append(core)
            continue
        flush()
        merged.append(raw)
    flush()
    return [t for t in (_token_forms(r) for r in merged) if t.latin or t.dev]


# --------------------------------------------------------------------------- #
# Dictionary compilation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Term:
    words: tuple[str, ...]  # comparable form per word
    lang: str
    category: Category
    severity: Severity
    embedded: bool


def _term_key(word: str, lang: str) -> str:
    word = normalize_text(word)
    if lang == "dev":
        return _fold_dev(_DEV_KEEP.sub("", word))
    word = _LATIN_KEEP.sub("", word)
    return _fold_rom(word) if lang == "rom" else word


@lru_cache(maxsize=1)
def _compiled_terms() -> tuple[_Term, ...]:
    terms = []
    for category, entries in LEXICON.items():
        for entry in entries:
            text, severity, lang = entry[0], entry[1], entry[2]
            flags = entry[3] if len(entry) > 3 else ()
            words = tuple(_term_key(w, lang) for w in text.split())
            if all(words):
                terms.append(_Term(words, lang, category, severity, "embedded" in flags))
    return tuple(terms)


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


def _rle_match(token: str, term: str) -> bool:
    """Same letters in order; each run at least as long as the term's run.

    "wooord" ~ "word" (yes), "as" ~ "ass" (no), "asss" ~ "ass" (yes).
    """
    a, b = _rle(token), _rle(term)
    return len(a) == len(b) and all(ca == cb and na >= nb for (ca, na), (cb, nb) in zip(a, b))


def _en_match(token: str, term: str, allow_suffix: bool, embedded: bool) -> bool:
    if _rle_match(token, term):
        return True
    if allow_suffix:
        for suffix in EN_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix):
                if _rle_match(token[: -len(suffix)], term):
                    return True
    return embedded and _collapse(term) in _collapse(token)


def _rom_match(token: str, term: str, allow_suffix: bool, embedded: bool) -> bool:
    folded = _fold_rom(token)
    if folded == term:
        return True
    if allow_suffix:
        for suffix in ROM_SUFFIXES:
            if folded.endswith(suffix) and folded[: -len(suffix)] == term:
                return True
    return embedded and term in folded


def _dev_match(token: str, term: str, allow_suffix: bool) -> bool:
    if token == term:
        return True
    if allow_suffix:
        for suffix in DEV_SUFFIXES:
            fs = _fold_dev(suffix)
            if token.endswith(fs) and token[: -len(fs)] == term:
                return True
    return False


def _word_matches(tok: _Token, word: str, lang: str, allow_suffix: bool, embedded: bool) -> bool:
    if lang == "dev":
        return bool(tok.dev) and _dev_match(tok.dev, word, allow_suffix)
    for variant in tok.latin:
        if lang == "en" and _en_match(variant, word, allow_suffix, embedded):
            return True
        if lang == "rom" and _rom_match(variant, word, allow_suffix, embedded):
            return True
    return False


def _phrase_at(tokens: list[_Token], i: int, term: _Term) -> bool:
    n = len(term.words)
    if i + n > len(tokens):
        return False
    for k, word in enumerate(term.words):
        last = k == n - 1
        # Nepali particles can attach to any word of a phrase ("kukurko chhora").
        suffix_ok = last or term.lang in ("rom", "dev")
        embedded = term.embedded and n == 1
        if not _word_matches(tokens[i + k], word, term.lang, suffix_ok, embedded):
            return False
    return True


@lru_cache(maxsize=1)
def _term_index() -> tuple[dict[tuple[str, str], tuple[_Term, ...]], tuple[_Term, ...]]:
    """Index terms by (lang, collapsed first word) so each token checks only a few terms."""
    index: dict[tuple[str, str], list[_Term]] = {}
    embedded = []
    for term in _compiled_terms():
        if term.embedded and len(term.words) == 1:
            embedded.append(term)
        index.setdefault((term.lang, _collapse(term.words[0])), []).append(term)
    return {k: tuple(v) for k, v in index.items()}, tuple(embedded)


def _lookup_keys(tok: _Token) -> set[tuple[str, str]]:
    """Possible index keys for a token (with and without a grammatical suffix)."""
    keys: set[tuple[str, str]] = set()
    if tok.dev:
        keys.add(("dev", _collapse(tok.dev)))
        for suffix in DEV_SUFFIXES:
            fs = _fold_dev(suffix)
            if tok.dev.endswith(fs) and len(tok.dev) > len(fs):
                keys.add(("dev", _collapse(tok.dev[: -len(fs)])))
    for variant in tok.latin:
        keys.add(("en", _collapse(variant)))
        for suffix in EN_SUFFIXES:
            if variant.endswith(suffix) and len(variant) > len(suffix):
                keys.add(("en", _collapse(variant[: -len(suffix)])))
        folded = _fold_rom(variant)
        keys.add(("rom", folded))
        for suffix in ROM_SUFFIXES:
            if folded.endswith(suffix) and len(folded) > len(suffix):
                keys.add(("rom", folded[: -len(suffix)]))
    return keys


@dataclass(frozen=True)
class ModerationResult:
    allowed: bool
    category: Category | None = None
    severity: Severity | None = None
    match_count: int = 0

    @property
    def flagged(self) -> bool:
        return self.match_count > 0


def _block_threshold() -> Severity:
    name = str(getattr(settings, "CHAT_MODERATION_BLOCK_SEVERITY", "MEDIUM")).upper()
    return Severity.__members__.get(name, Severity.MEDIUM)


def moderate_text(text: str, ignore: frozenset = frozenset()) -> ModerationResult:
    """Check ``text``; ``allowed`` is False when it must be rejected.

    ``ignore``: categories to skip (only ``RELAXABLE_CATEGORIES`` are honoured).
    """
    ignore = frozenset(ignore) & RELAXABLE_CATEGORIES
    if not getattr(settings, "CHAT_MODERATION_ENABLED", True) or not (text or "").strip():
        return ModerationResult(allowed=True)

    tokens = tokenize(text)
    if not tokens:
        return ModerationResult(allowed=True)

    index, embedded_terms = _term_index()
    worst: _Term | None = None
    count = 0
    for i, tok in enumerate(tokens):
        candidates = {t for key in _lookup_keys(tok) for t in index.get(key, ())}
        candidates.update(embedded_terms)
        for term in candidates:
            if term.category in ignore:
                continue
            if _phrase_at(tokens, i, term):
                count += 1
                if worst is None or term.severity > worst.severity:
                    worst = term
    # A word split in two ("fu ck", "bit ch", "मु जी"). Only single-word English /
    # Devanagari terms at blocking severity, to keep false positives away from
    # ordinary word pairs.
    threshold = _block_threshold()
    for left, right in zip(tokens, tokens[1:]):
        joined = _token_forms(left.raw + right.raw)
        for key in _lookup_keys(joined):
            if key[0] == "rom":
                continue
            for term in index.get(key, ()):
                if len(term.words) != 1 or term.severity < threshold or term.category in ignore:
                    continue
                if _word_matches(joined, term.words[0], term.lang, False, False):
                    count += 1
                    if worst is None or term.severity > worst.severity:
                        worst = term

    if worst is None:
        return ModerationResult(allowed=True)
    allowed = worst.severity < _block_threshold()
    return ModerationResult(
        allowed=allowed,
        category=worst.category,
        severity=worst.severity,
        match_count=count,
    )


def enforce_clean_text(
    text: str, *, user_id=None, source: str = "chat", ignore: frozenset = frozenset()
) -> ModerationResult:
    """Raise ``InappropriateContent`` for blocked text; log hits without the text itself."""
    result = moderate_text(text, ignore=ignore)
    if result.flagged:
        logger.info(
            "moderation %s user=%s source=%s category=%s severity=%s",
            "blocked" if not result.allowed else "flagged",
            user_id,
            source,
            result.category.value if result.category else "",
            result.severity.name if result.severity else "",
        )
    if not result.allowed:
        raise InappropriateContent()
    return result
