"""
Plagx Cite: a free academic writing utility by Plagiarism Checker X.
APA 7 and MLA 9 citation generator and reference checker.
https://plagiarismcheckerx.com/ · MIT License

References are CSL-JSON dicts, e.g. json.load() of a Zotero or Crossref export.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from . import _apa, _mla
from ._formatter import Formatter
from ._names import family_name
from ._util import get_year, normalize_text
from .bibtex import parse_bibtex, to_bibtex
from .check import check_references
from .doi import extract_dois, from_crossref, is_doi, lookup_doi, normalize_doi
from .duplicates import find_duplicates

__version__ = "0.2.2"

__all__ = [
    "styles", "format_reference", "format_bibliography", "cite_in_text", "sort_references",
    "to_bibtex", "parse_bibtex", "normalize_doi", "is_doi", "extract_dois", "lookup_doi",
    "from_crossref", "find_duplicates", "check_references", "__version__",
]

_STYLES = {"apa": _apa, "mla": _mla}

#: Names of the built-in citation styles.
styles = list(_STYLES)


def _style(name: str):
    style = _STYLES.get(str(name).lower())
    if style is None:
        raise ValueError(f'Unknown citation style "{name}". Available: {", ".join(styles)}.')
    return style


def format_reference(ref: dict, style: str = "apa", format: str = "text") -> str:  # noqa: A002
    """Formats one CSL-JSON reference as a reference-list entry ("text", "html" or "markdown")."""
    return _style(style).reference(ref, Formatter(format))


def format_bibliography(refs: list, style: str = "apa", format: str = "text") -> list:  # noqa: A002
    """Sorts references and formats each one; returns a list of entries."""
    return [format_reference(ref, style=style, format=format) for ref in sort_references(refs)]


def cite_in_text(ref: dict, style: str = "apa", page: Optional[Any] = None, narrative: bool = False) -> str:
    """In-text citation, e.g. "(Smith & Lee, 2020, p. 4)" or "Smith and Lee (2020)"."""
    return _style(style).in_text(ref, page=page, narrative=narrative)


def _sort_key(ref: dict) -> str:
    lead = family_name(ref["author"][0]) if ref.get("author") else re.sub(r"^(a|an|the)\s+", "", str(ref.get("title") or ""), flags=re.I)
    return f"{normalize_text(lead)} {get_year(ref) or '0000'} {normalize_text(ref.get('title'))}"


def sort_references(refs: list) -> list:
    """Returns a new list sorted by first author (or title), year, then title."""
    return sorted(refs, key=_sort_key)
