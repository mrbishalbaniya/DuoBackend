from __future__ import annotations

import re


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


class GrammarEngine:
    """Normalize capitalization, punctuation, and connector flow."""

    CONNECTOR_FALLBACKS = [
        "In my free time, ",
        "Outside of work, ",
        "On weekends, ",
        "Additionally, ",
        "I also enjoy ",
        "As someone who values balance, ",
    ]

    def fill_placeholders(self, text: str, values: dict[str, str]) -> str:
        """Replace {placeholders}; drop any sentence fragments that still contain braces."""
        if not text:
            return ""

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            value = (values.get(key) or "").strip()
            return value

        filled = _PLACEHOLDER_RE.sub(repl, text)
        # If any placeholders remain unresolved, drop that template text entirely.
        if "{" in filled and "}" in filled:
            return ""
        # Clean doubled spaces / empty "as a  and" artifacts
        filled = re.sub(r"\s{2,}", " ", filled).strip()
        filled = re.sub(r"\bas a\s+and\b", "and", filled, flags=re.IGNORECASE)
        filled = re.sub(r"\bin\s+,", ",", filled)
        return filled

    def clean_sentence(self, text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())
        if not text:
            return ""
        # Avoid double trailing punctuation
        text = text.rstrip(" .") + "."
        # Capitalize first alpha char
        chars = list(text)
        for i, ch in enumerate(chars):
            if ch.isalpha():
                chars[i] = ch.upper()
                break
        return "".join(chars)

    def with_connector(self, connector: str | None, sentence: str, *, index: int = 0) -> str:
        sentence = (sentence or "").strip()
        if not sentence:
            return ""
        # Strip leading capital for mid-paragraph connectors that expect lowercase continuation
        body = sentence[0].lower() + sentence[1:] if sentence and sentence[0].isupper() else sentence
        body = body.rstrip(".")

        conn = (connector or "").strip()
        if not conn:
            conn = self.CONNECTOR_FALLBACKS[index % len(self.CONNECTOR_FALLBACKS)]

        if not conn.endswith((" ", ",")):
            if conn.lower().endswith(("additionally", "overall")):
                conn = f"{conn}, "
            elif conn.lower().startswith(("i also", "as someone")):
                conn = f"{conn} "
            else:
                conn = f"{conn} "

        # Connectors that already include "I" should keep sentence without leading "i "
        if conn.lower().startswith("i also"):
            if body.lower().startswith("i "):
                body = body[2:]
            merged = f"{conn}{body}."
        elif conn.rstrip().endswith(","):
            merged = f"{conn}{body}."
        else:
            merged = f"{conn}{body}."
        return self.clean_sentence(merged)

    def _normalize_key(self, sentence: str) -> str:
        return re.sub(r"[^a-z0-9]", "", sentence.lower())

    def join_paragraph(self, sentences: list[str], *, target_min: int = 80, target_max: int = 120) -> str:
        cleaned = [self.clean_sentence(s) for s in sentences if s and s.strip()]
        unique: list[str] = []
        seen: set[str] = set()
        for sentence in cleaned:
            key = self._normalize_key(sentence)
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(sentence)

        return self.fit_sentences(unique, maximum_words=target_max)

    def fit_sentences(self, sentences: list[str], *, maximum_words: int) -> str:
        """Keep whole sentences under a word budget — never cut mid-sentence."""
        kept: list[str] = []
        total = 0
        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue
            if kept and total + len(words) > maximum_words:
                break
            if not kept and len(words) > maximum_words:
                # Extreme edge: keep first sentence trimmed only if unavoidable
                kept.append(" ".join(words[:maximum_words]).rstrip(",;") + ".")
                break
            kept.append(sentence if sentence.endswith((".", "!", "?")) else f"{sentence}.")
            total += len(words)
        return " ".join(kept).strip()

    def ensure_word_range(self, text: str, *, minimum: int, maximum: int, pad_sentences: list[str]) -> str:
        existing = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        seen = {self._normalize_key(s) for s in existing}

        for sentence in pad_sentences:
            cleaned = self.clean_sentence(sentence)
            key = self._normalize_key(cleaned)
            if not cleaned or not key or key in seen:
                continue
            candidate = existing + [cleaned]
            fitted = self.fit_sentences(candidate, maximum_words=maximum)
            if len(fitted.split()) >= minimum or len(fitted.split()) > len(text.split()):
                existing = [s.strip() for s in re.split(r"(?<=[.!?])\s+", fitted) if s.strip()]
                seen.add(key)
            if len(" ".join(existing).split()) >= minimum:
                break

        return self.fit_sentences(existing, maximum_words=maximum)

    def hard_char_limit(self, text: str, maximum_chars: int) -> str:
        """Trim on sentence boundaries for frontend field max lengths."""
        text = (text or "").strip()
        if len(text) <= maximum_chars:
            return text
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        kept: list[str] = []
        for part in parts:
            trial = " ".join([*kept, part]).strip()
            if kept and len(trial) > maximum_chars:
                break
            if not kept and len(part) > maximum_chars:
                # Last resort: end on last space before limit
                clipped = part[: maximum_chars - 1].rsplit(" ", 1)[0].rstrip(",;.") + "."
                return clipped
            kept.append(part)
        return " ".join(kept).strip()
