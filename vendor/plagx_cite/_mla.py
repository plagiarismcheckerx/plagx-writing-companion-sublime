"""MLA 9th edition (common reference types)."""
from __future__ import annotations

from typing import Any

from ._formatter import Formatter
from ._names import family_name, name_parts
from ._util import MONTHS_MLA, dot, filled, get_date, is_page_range, link, ordinal, page_range

QUOTED_TYPES = (
    "article-journal", "article-magazine", "article-newspaper", "article",
    "chapter", "paper-conference", "webpage", "entry-encyclopedia", "entry-dictionary", "post", "post-weblog",
)


def _natural(n: dict) -> str:
    if "literal" in n:
        return n["literal"]
    return " ".join(p for p in (n["given"], n["family"]) if p)


def _author_list(names_in: list) -> str:
    names = [name_parts(n) for n in names_in]
    first = names[0]
    lead = first.get("literal") or first["family"]
    if "literal" not in first and first["given"]:
        lead += ", " + first["given"]
    if "literal" not in first and first.get("suffix"):
        lead += ", " + str(first["suffix"])
    if len(names) == 1:
        return lead
    if len(names) == 2:
        return f"{lead}, and {_natural(names[1])}"
    return f"{lead}, et al."


def _editor_list(names_in: list) -> str:
    names = [_natural(name_parts(n)) for n in names_in]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} et al."


def _date_text(ref: dict) -> str:
    d = get_date(ref)
    parts = [d["day"], MONTHS_MLA[d["month"] - 1] if d["month"] else None, d["year"]]
    return " ".join(str(p) for p in parts if filled(p))


def _pages_text(page: Any) -> str:
    return f"{'pp.' if is_page_range(page) else 'p.'} {page_range(page, '-')}"


def reference(ref: dict, f: Formatter) -> str:
    ref_type = ref.get("type") or ""
    parts = []

    if ref.get("author"):
        authors = _author_list(ref["author"])
        parts.append(f.t(authors + dot(authors)))

    title = str(ref.get("title") or "")
    if title:
        parts.append(f.t(f"“{title}{dot(title)}”") if ref_type in QUOTED_TYPES else f.i(title) + f.t(dot(title)))

    # Container elements, separated by commas and closed with a period.
    container = str(ref["container-title"]) if filled(ref.get("container-title")) else ""
    elements = []
    if container:
        elements.append(f.i(container))
    if ref.get("editor"):
        elements.append(f.t("edited by " + _editor_list(ref["editor"])))
    if filled(ref.get("edition")):
        elements.append(f.t(f"{ordinal(ref['edition'])} ed."))
    if filled(ref.get("volume")):
        elements.append(f.t(f"vol. {ref['volume']}"))
    if filled(ref.get("issue")):
        elements.append(f.t(f"no. {ref['issue']}"))
    # Articles name their journal, not the publisher, unless there is no journal (e.g. arXiv preprints).
    if filled(ref.get("publisher")) and (not ref_type.startswith("article") or not container):
        elements.append(f.t(str(ref["publisher"])))
    date = _date_text(ref)
    if date:
        elements.append(f.t(date))
    if filled(ref.get("page")):
        elements.append(f.t(_pages_text(ref["page"])))
    url = link(ref)
    if url:
        elements.append(f.t(url))

    if elements:
        parts.append(f.t(", ").join(elements) + f.t("."))
    return " ".join(parts)


def in_text(ref: dict, page: Any = None, narrative: bool = False) -> str:
    names = [family_name(n) for n in ref.get("author") or []]
    if not names:
        who = f"“{ref['title'] if filled(ref.get('title')) else 'Untitled'}”"
    elif len(names) == 1:
        who = names[0]
    elif len(names) == 2:
        who = f"{names[0]} and {names[1]}"
    else:
        who = f"{names[0]} et al."
    pages = page_range(page, "-") if filled(page) else ""
    if narrative:
        return f"{who} ({pages})" if pages else who
    return f"({who} {pages})" if pages else f"({who})"
