"""Text structure helpers: words, lines, paragraphs, headings, sentences, syllables.

Offsets here are Python string indices (code points); the public API converts
them to UTF-16 code units, the unit the JavaScript reference reports.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from typing import Dict, List

from ._unicode import L, LU, M

# JavaScript's \s. Python's \s is different, so every pattern uses this class instead.
WS = "\t\n\x0b\f\r    -     　﻿"

WORD_RE = re.compile(f"[{L}{M}0-9]+(?:['’-][{L}{M}0-9]+)*")

ABBREVIATIONS = {
    "al", "approx", "cf", "co", "dept", "dr", "ed", "eds", "eg", "et", "etc", "fig", "figs", "ie",
    "inc", "jr", "ltd", "mr", "mrs", "ms", "no", "nos", "p", "pp", "prof", "sr", "st", "vol", "vols", "vs",
}

REFERENCE_HEADINGS = {
    "references", "reference list", "bibliography", "works cited", "work cited", "sources", "literature cited",
}

# The characters text.js treats as space when trimming.
_SPACE = set(" \t\r\n\f\v ")

_TRIM_RE = re.compile(f"^[{WS}]+|[{WS}]+\\Z")
_BLANK_LINE = re.compile("[ \t\r\f\v ]*\\Z")
_HASHES = re.compile(f"^#+[{WS}]*")
_NUMBERING = re.compile(f"^(?:[0-9]+(?:\\.[0-9]+)*\\.?|[ivxlc]+\\.)[{WS}]+", re.I | re.A)
_COLON = re.compile(f"[{WS}]*:\\Z")
_SPACES = re.compile(f"[{WS}]+")
_HEADING_END = re.compile("[.!?,;\"'”’)\\]]\\Z")
_HEADING_START = re.compile(f"[{LU}0-9]")
_TERMINATOR = re.compile(f"[.!?]+[\"'”’)\\]]*(?=[{WS}]|\\Z)")
_CLOSERS = re.compile("[\"'”’)\\]]+\\Z")
_BEFORE = re.compile(f"(?:^|[{WS}(])([{L}.]+)\\Z")
_ONE_LETTER = re.compile(f"[{L}]\\Z")


def js_trim(s: str) -> str:
    """JavaScript String.prototype.trim()."""
    return _TRIM_RE.sub("", s)


def js_lower(s: str) -> str:
    return s.lower()


def words(text: str) -> List[Dict]:
    return [{"text": m.group(), "start": m.start(), "end": m.end()} for m in WORD_RE.finditer(text)]


def count_words(text: str) -> int:
    return sum(1 for _ in WORD_RE.finditer(text))


def line_starts(text: str) -> List[int]:
    starts = [0]
    at = text.find("\n")
    while at >= 0:
        starts.append(at + 1)
        at = text.find("\n", at + 1)
    return starts


def line_index(starts: List[int], offset: int) -> int:
    return bisect_right(starts, offset) - 1


def _trim_range(text: str, s: int, e: int):
    while s < e and text[s] in _SPACE:
        s += 1
    while e > s and text[e - 1] in _SPACE:
        e -= 1
    return s, e


def normalize_heading(s: str) -> str:
    s = js_trim(s)
    s = _HASHES.sub("", s, count=1)
    s = _NUMBERING.sub("", s, count=1)
    s = _COLON.sub("", s, count=1)
    s = _SPACES.sub(" ", s)
    return js_lower(s)


def _is_heading(t: str) -> bool:
    if "\n" in t:
        return False
    if t.startswith("#"):
        return True
    if normalize_heading(t) in REFERENCE_HEADINGS:
        return True
    n = count_words(t)
    if n < 1 or n > 10:
        return False
    if _HEADING_END.search(t):
        return False
    return bool(_HEADING_START.match(t))


def paragraphs(text: str) -> List[Dict]:
    out = []
    starts = line_starts(text)
    block = [-1, -1]

    def flush():
        if block[0] < 0:
            return
        s, e = _trim_range(text, block[0], block[1])
        t = text[s:e]
        out.append({"text": t, "start": s, "end": e, "heading": _is_heading(t)})
        block[0] = -1

    for i, ls in enumerate(starts):
        le = starts[i + 1] - 1 if i + 1 < len(starts) else len(text)
        if _BLANK_LINE.match(text, ls, le):
            flush()
        else:
            if block[0] < 0:
                block[0] = ls
            block[1] = le
    flush()
    return out


def structure(text: str) -> Dict:
    paras = paragraphs(text)
    idx = next((i for i, p in enumerate(paras) if p["heading"] and normalize_heading(p["text"]) in REFERENCE_HEADINGS), -1)
    body = paras if idx < 0 else paras[:idx]
    heading = None if idx < 0 else paras[idx]
    entries = []
    if heading is not None:
        starts = line_starts(text)
        for i, ls in enumerate(starts):
            if ls <= heading["end"]:
                continue
            le = starts[i + 1] - 1 if i + 1 < len(starts) else len(text)
            s, e = _trim_range(text, ls, le)
            if e > s:
                entries.append({"text": text[s:e], "start": s, "end": e})
    return {
        "paragraphs": paras,
        "body": body,
        "body_end": len(text) if heading is None else heading["start"],
        "reference_heading": heading,
        "entries": entries,
    }


def _sentences_in(s: str, base: int) -> List[Dict]:
    out = []
    start = 0

    def push(end: int):
        nonlocal start
        a, b = _trim_range(s, start, end)
        if b > a:
            out.append({"text": s[a:b], "start": base + a, "end": base + b})
        start = end

    for m in _TERMINATOR.finditer(s):
        marks = _CLOSERS.sub("", m.group())
        if marks.startswith(".."):
            continue  # an ellipsis
        if marks == ".":
            # A lone period after an abbreviation, an initial or a dotted form (U.S.) does not end a sentence.
            b = _BEFORE.search(s, 0, m.start())
            if b:
                w = js_lower(b.group(1))
                if w in ABBREVIATIONS or _ONE_LETTER.match(w) or "." in w:
                    continue
        push(m.end())
    push(len(s))
    return out


def split_sentences(text: str) -> List[Dict]:
    out = []
    for p in paragraphs(text):
        if p["heading"]:
            out.append({"text": p["text"], "start": p["start"], "end": p["end"]})
        else:
            out.extend(_sentences_in(p["text"], p["start"]))
    return out


def paragraph_sentences(p: Dict) -> List[Dict]:
    return _sentences_in(p["text"], p["start"])


_NOT_AZ = re.compile("[^a-z]")
_ENDING = re.compile("(?:[^laeiouy]es|ed|[^laeiouy]e)\\Z")
_VOWELS = re.compile("[aeiouy]+")


def syllables(word: str) -> int:
    w = _NOT_AZ.sub("", js_lower(word))
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = _ENDING.sub("", w, count=1)
    if w.startswith("y"):
        w = w[1:]
    n = len(_VOWELS.findall(w))
    return n if n else 1
