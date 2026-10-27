"""Plagx Preflight: a draft checker with basic grammar suggestions.

A free academic writing utility by Plagiarism Checker X. Runs fully offline.
Results match the JavaScript reference exactly: start, end and column are
UTF-16 code-unit offsets.
"""
from __future__ import annotations

import math
from itertools import accumulate
from typing import Dict, Iterable, List, Optional

from . import _checks, _citations
from ._text import count_words as _count_words
from ._text import line_index, line_starts, paragraph_sentences, split_sentences as _split_sentences, structure, syllables, words

__version__ = "0.1.3"
VERSION = __version__

#: Check groups. "passive-voice" is off by default.
CHECKS = ("length", "references", "punctuation", "grammar", "passive-voice")
DEFAULT_CHECKS = ("length", "references", "punctuation", "grammar")
STYLES = _citations.STYLES

_RUNNERS = {
    "length": _checks.length,
    "references": _checks.references,
    "punctuation": _checks.punctuation,
    "grammar": _checks.grammar,
    "passive-voice": _checks.passive_voice,
}

__all__ = ["check_draft", "count_words", "split_sentences", "find_citations", "VERSION", "CHECKS", "DEFAULT_CHECKS", "STYLES"]


class _Utf16:
    """Maps string indices (code points) to UTF-16 code-unit offsets."""

    def __init__(self, text: str):
        self._map = [0, *accumulate(2 if ord(c) > 0xFFFF else 1 for c in text)]

    def __call__(self, index: int) -> int:
        return self._map[index]


def _limit(value, name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a whole number")
    return value


def _js_round(v: float) -> float:
    """JavaScript Math.round: halves round up, towards +infinity."""
    r = math.floor(v)
    return r + 1 if v - r >= 0.5 else r


def _stats(text: str, doc: Dict) -> Dict:
    body_words = _count_words(text[: doc["body_end"]])
    sentences = sentence_words = syl = paras = 0
    for p in doc["body"]:
        if p["heading"]:
            continue
        paras += 1
        sentences += len(paragraph_sentences(p))
        for w in words(p["text"]):
            sentence_words += 1
            syl += syllables(w["text"])
    flesch = 0
    if sentences and sentence_words:
        f = _js_round((206.835 - 1.015 * (sentence_words / sentences) - 84.6 * (syl / sentence_words)) * 10) / 10
        # Serialise like JavaScript: whole numbers without ".0", and no negative zero.
        flesch = int(f) if f == int(f) else f
    return {
        "words": body_words,
        "sentences": sentences,
        "paragraphs": paras,
        "characters": len(text),
        "readingTimeMinutes": math.ceil(body_words / 200),
        "fleschReadingEase": flesch,
    }


def check_draft(
    text: str,
    *,
    min_words: Optional[int] = None,
    max_words: Optional[int] = None,
    style: str = "apa",
    checks: Optional[Iterable[str]] = None,
    required_headings: Iterable[str] = (),
) -> Dict:
    """Checks a draft and returns stats plus a sorted list of suggestions.

    Returns ``{"stats", "errors", "warnings", "infos", "issues"}``. Each issue has
    ``level``, ``code``, ``message``, ``start``, ``end``, ``line``, ``column``,
    ``text`` and ``suggestion``.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if style not in STYLES:
        raise ValueError(f'Unknown style "{style}". Use: {", ".join(STYLES)}')
    wanted = list(DEFAULT_CHECKS if checks is None else checks)
    for c in wanted:
        if c not in CHECKS:
            raise ValueError(f'Unknown check "{c}". Use: {", ".join(CHECKS)}')
    opts = {
        "min_words": _limit(min_words, "min_words"),
        "max_words": _limit(max_words, "max_words"),
        "style": style,
        "checks": [c for c in CHECKS if c in wanted],
        "required_headings": [str(h) for h in required_headings],
    }
    doc = structure(text)
    ctx = _checks.Context(text, opts, doc, _stats(text, doc))
    for c in opts["checks"]:
        _RUNNERS[c](ctx)

    u16 = _Utf16(text)
    starts = line_starts(text)
    issues = []
    for x in ctx.issues:
        line = line_index(starts, x["start"])
        issues.append({
            "level": x["level"],
            "code": x["code"],
            "message": x["message"],
            "start": u16(x["start"]),
            "end": u16(x["end"]),
            "line": line + 1,
            "column": u16(x["start"]) - u16(starts[line]) + 1,
            "text": text[x["start"]:x["end"]],
            "suggestion": x["suggestion"],
        })
    issues.sort(key=lambda i: (i["start"], i["code"], i["end"]))
    count = lambda level: sum(1 for i in issues if i["level"] == level)  # noqa: E731
    return {"stats": ctx.stats, "errors": count("error"), "warnings": count("warning"), "infos": count("info"), "issues": issues}


def count_words(text: str) -> int:
    """Number of words in the text."""
    return _count_words(text)


def split_sentences(text: str) -> List[Dict]:
    """Sentences as ``{"text", "start", "end"}`` with UTF-16 offsets. Headings count as one sentence each."""
    u16 = _Utf16(text)
    return [{"text": s["text"], "start": u16(s["start"]), "end": u16(s["end"])} for s in _split_sentences(text)]


def find_citations(text: str, style: str = "apa") -> List[Dict]:
    """In-text citations as ``{"text", "start", "end", "author", "key", "year"}`` with UTF-16 offsets.

    ``key`` is the first word of the author text in lowercase; ``year`` is None for MLA.
    """
    u16 = _Utf16(text)
    return [{**c, "start": u16(c["start"]), "end": u16(c["end"])} for c in _citations.find(text, style)]
