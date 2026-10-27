"""APA 7th edition (common reference types)."""
from __future__ import annotations

from typing import Any

from ._formatter import Formatter
from ._names import family_name, initials, name_parts
from ._util import MONTHS, dot, filled, get_date, get_year, is_page_range, link, ordinal, page_range

JOURNAL_TYPES = ("article-journal", "article-magazine", "article-newspaper", "article")
CONTAINER_TYPES = ("chapter", "paper-conference", "entry-encyclopedia", "entry-dictionary")
DATED_TYPES = ("webpage", "article-newspaper", "article-magazine", "post", "post-weblog")


def _author_name(name: Any) -> str:
    n = name_parts(name)
    if "literal" in n:
        return n["literal"]
    s = n["family"]
    if n["given"]:
        s += ", " + initials(n["given"])
    if n.get("suffix"):
        s += ", " + str(n["suffix"])
    return s


def _author_list(names_in: list) -> str:
    names = [_author_name(n) for n in names_in]
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def _editor_list(names_in: list) -> str:
    names = []
    for name in names_in:
        n = name_parts(name)
        if "literal" in n:
            names.append(n["literal"])
        else:
            names.append(f"{initials(n['given'])} {n['family']}" if n["given"] else n["family"])
    if len(names) == 1:
        s = names[0]
    elif len(names) == 2:
        s = " & ".join(names)
    else:
        s = ", ".join(names[:-1]) + ", & " + names[-1]
    return f"{s} ({'Eds.' if len(names) > 1 else 'Ed.'})"


def _date_text(ref: dict) -> str:
    d = get_date(ref)
    if not d["year"]:
        return "n.d."
    s = str(d["year"])
    if ref.get("type") in DATED_TYPES and d["month"]:
        s += ", " + MONTHS[d["month"] - 1]
        if d["day"]:
            s += f" {d['day']}"
    return s


def _title_text(ref: dict, f: Formatter) -> str:
    title = str(ref.get("title") or "")
    if not title:
        return ""
    ref_type = ref.get("type") or ""
    italic = ref_type not in JOURNAL_TYPES and ref_type not in CONTAINER_TYPES
    s = f.i(title) if italic else f.t(title)
    note = ""
    if filled(ref.get("edition")):
        note = f" ({ordinal(ref['edition'])} ed.)"
    if ref_type == "thesis":
        publisher = f", {ref['publisher']}" if filled(ref.get("publisher")) else ""
        note = f" [{ref['genre'] if filled(ref.get('genre')) else 'Thesis'}{publisher}]"
    if note:
        return s + f.t(note + ".")
    return s + f.t(dot(title))


def _source_text(ref: dict, f: Formatter, authors: str) -> str:
    ref_type = ref.get("type") or ""
    container = str(ref["container-title"]) if filled(ref.get("container-title")) else ""
    publisher = str(ref["publisher"]) if filled(ref.get("publisher")) else ""

    if ref_type in JOURNAL_TYPES:
        # Preprints and similar have no journal; name the repository instead (e.g. arXiv).
        if not container:
            return f.t(publisher + dot(publisher)) if publisher and publisher != authors else ""
        s = f.i(container)
        if filled(ref.get("volume")):
            s += f.t(", ") + f.i(str(ref["volume"]))
        if filled(ref.get("issue")):
            s += f.t(f"({ref['issue']})")
        if filled(ref.get("page")):
            s += f.t(", " + page_range(ref["page"]))
        return s + f.t(".")

    if ref_type in CONTAINER_TYPES:
        s = f.t("In ")
        if ref.get("editor"):
            s += f.t(_editor_list(ref["editor"]) + ", ")
        if container:
            s += f.i(container)
        if filled(ref.get("page")):
            s += f.t(f" ({'pp.' if is_page_range(ref['page']) else 'p.'} {page_range(ref['page'])})")
        s += f.t(".")
        if publisher:
            s += f.t(" " + publisher + dot(publisher))
        return s

    if ref_type == "thesis":
        return ""

    # Webpage: site name; book, report and others: publisher. Omitted when it repeats the author.
    source = container if ref_type == "webpage" else publisher
    if not source or source == authors:
        return ""
    return f.t(source + dot(source))


def reference(ref: dict, f: Formatter) -> str:
    authors = _author_list(ref["author"]) if ref.get("author") else ""
    date = f.t(f"({_date_text(ref)}).")
    title = _title_text(ref, f)
    parts = [f.t(authors + dot(authors)), date, title] if authors else [title, date]
    parts += [_source_text(ref, f, authors), f.t(link(ref))]
    return " ".join(p for p in parts if p)


def in_text(ref: dict, page: Any = None, narrative: bool = False) -> str:
    names = [family_name(n) for n in ref.get("author") or []]
    conj = "and" if narrative else "&"

    detail = get_year(ref) or "n.d."
    if filled(page):
        detail += f", {'pp.' if is_page_range(page) else 'p.'} {page_range(page)}"

    # No author: the title stands in, and APA puts the comma inside the quotation marks.
    if not names:
        title = ref["title"] if filled(ref.get("title")) else "Untitled"
        return f"“{title}” ({detail})" if narrative else f"(“{title},” {detail})"

    if len(names) == 1:
        who = names[0]
    elif len(names) == 2:
        who = f"{names[0]} {conj} {names[1]}"
    else:
        who = f"{names[0]} et al."
    return f"{who} ({detail})" if narrative else f"({who}, {detail})"
