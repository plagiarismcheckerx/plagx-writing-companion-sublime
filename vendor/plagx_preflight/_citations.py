"""In-text citations (APA author-date, MLA author-page) and reference list entries."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from ._text import WS, js_lower, js_trim
from ._unicode import L, LU

STYLES = ("apa", "mla")

YEAR = r"(?:[0-9]{4}[a-z]?|n\.d\.)"
NAME = f"[{LU}][{L}'’-]+"
NOT_AUTHORS = {
    "appendix", "chapter", "chapters", "fig", "figure", "figures", "line", "lines", "p", "page", "pages", "part",
    "phase", "pp", "section", "see", "step", "table", "tables", "version", "vol", "volume",
}
# JavaScript "." does not match line terminators.
_DOT = "[^\n\r  ]"

_WORD = re.compile(f"[{L}][{L}'’-]*")
_LEAD = re.compile(f"^[{WS}]+")
_APA_PAREN = re.compile(f"\\(([^()]*?{YEAR}[^()]*)\\)")
_APA_PREFIX = re.compile(f"^(?:e\\.g\\.|see also|see|cf\\.),?[{WS}]+", re.I | re.A)
_APA_AUTHOR = re.compile(f"^({_DOT}*?[{L}]{_DOT}*?),?[{WS}]+({YEAR}(?:,[{WS}]*{YEAR})*)(?=\\Z|,)")
_YEAR_SPLIT = re.compile(f",[{WS}]*")
_UPPER_START = re.compile(f"[{LU}]")
_NARRATIVE = re.compile(
    f"((?:{NAME}[{WS}]+){{0,4}}{NAME}(?:[{WS}]+(?:and|&)[{WS}]+{NAME}|[{WS}]+et\\.?[{WS}]*al\\.*)?)"
    f"[{WS}]+\\(({YEAR})(?:,[^()]*)?\\)"
)
_MLA_PAREN = re.compile(r"\(([^()]+)\)")
_MLA_PART = re.compile(f"^([{LU}][{L}'’.\\- &,]*?),?[{WS}]+([0-9]+(?:[{WS}]*[-–][{WS}]*[0-9]+)?)\\Z")
_FOUR_DIGITS = re.compile("[0-9]{4}\\Z")
_ENTRY_MARKER = re.compile(f"^(?:\\[[0-9]+\\]|[0-9]+\\.|[-*•])[{WS}]+")
_ENTRY_YEAR = re.compile(f"\\(({YEAR})")


def _lower(s: str) -> str:
    return js_lower(s).replace("’", "'")


def _first_word(s: str) -> str:
    m = _WORD.search(s)
    return _lower(m.group()) if m else ""


def _parts(inner: str, offset: int):
    for part in inner.split(";"):
        lead = len(part) - len(_LEAD.sub("", part, count=1))
        yield js_trim(part), offset + lead
        offset += len(part) + 1


def _apa(text: str) -> List[Dict]:
    out = []
    # Parenthetical: (Smith, 2020), (Smith & Lee, 2020, p. 4; Brown, 2018a)
    for m in _APA_PAREN.finditer(text):
        for trimmed, p_start in _parts(m.group(1), m.start(1)):
            px = _APA_PREFIX.match(trimmed)
            skip = px.end() if px else 0
            rest = trimmed[skip:]
            am = _APA_AUTHOR.match(rest)
            if not am:
                continue
            author = am.group(1)
            if not _UPPER_START.match(author) or _first_word(author) in NOT_AUTHORS:
                continue
            for year in _YEAR_SPLIT.split(am.group(2)):
                out.append({"text": rest, "start": p_start + skip, "end": p_start + len(trimmed),
                            "author": author, "key": _first_word(author), "year": year.lower()})
    # Narrative: Smith (2020), Smith and Lee (2020, p. 4), Smith et al. (2020)
    for m in _NARRATIVE.finditer(text):
        out.append({"text": m.group(), "start": m.start(), "end": m.end(),
                    "author": m.group(1), "key": _first_word(m.group(1)), "year": m.group(2).lower()})
    return out


def _mla(text: str) -> List[Dict]:
    out = []
    # (Smith 50), (Smith and Lee 50-52), (Smith et al. 12; Brown 7)
    for m in _MLA_PAREN.finditer(text):
        for trimmed, p_start in _parts(m.group(1), m.start(1)):
            pm = _MLA_PART.match(trimmed)
            if not pm or _first_word(pm.group(1)) in NOT_AUTHORS or _FOUR_DIGITS.match(pm.group(2)):
                continue
            out.append({"text": trimmed, "start": p_start, "end": p_start + len(trimmed),
                        "author": pm.group(1), "key": _first_word(pm.group(1)), "year": None})
    return out


def find(text: str, style: str = "apa") -> List[Dict]:
    if style not in STYLES:
        raise ValueError(f'Unknown style "{style}". Use: {", ".join(STYLES)}')
    found = _apa(text) if style == "apa" else _mla(text)
    return sorted(found, key=lambda c: (c["start"], c["end"]))


def matches(citation: Dict, entry: Dict) -> bool:
    """Whether a citation points at a reference entry."""
    if citation["year"] is not None and citation["year"] != entry["year"]:
        return False
    return entry["key"] in [_lower(w) for w in _WORD.findall(citation["author"])]


def parse_entry(text: str) -> Dict[str, Optional[str]]:
    body = _ENTRY_MARKER.sub("", text, count=1)
    y = _ENTRY_YEAR.search(body)
    return {"key": _first_word(body), "year": y.group(1).lower() if y else None}
