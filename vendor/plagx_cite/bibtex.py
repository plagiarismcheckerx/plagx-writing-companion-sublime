"""BibTeX export and BibTeX/BibLaTeX import."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Union

from ._names import family_name, name_parts
from ._util import filled, get_date, normalize_text

TO_BIBTEX_TYPE = {
    "article-journal": "article",
    "article-magazine": "article",
    "article-newspaper": "article",
    "article": "article",
    "book": "book",
    "chapter": "incollection",
    "paper-conference": "inproceedings",
    "report": "techreport",
    "thesis": "phdthesis",
}

FROM_BIBTEX_TYPE = {
    "article": "article-journal",
    "book": "book",
    "inbook": "chapter",
    "incollection": "chapter",
    "inproceedings": "paper-conference",
    "conference": "paper-conference",
    "techreport": "report",
    "report": "report",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "thesis": "thesis",
    "online": "webpage",
}

MONTH_NAMES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

ACCENTS = {
    '"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304",
    ".": "\u0307", "c": "\u0327", "v": "\u030C", "u": "\u0306", "H": "\u030B",
}

# ------------------------------------------------------------------ export


def _escape_value(value: str) -> str:
    return re.sub(r"[\\&%$#_{}]", lambda m: "\\textbackslash{}" if m.group(0) == "\\" else "\\" + m.group(0), value)


def _bib_name(name: Any) -> str:
    n = name_parts(name)
    if "literal" in n:
        return "{" + n["literal"] + "}"
    return ", ".join(p for p in (n["family"], n.get("suffix"), n["given"]) if filled(p))


def _base_key(ref: dict) -> str:
    lead = family_name(ref["author"][0]) if ref.get("author") else "anon"
    word = next((w for w in normalize_text(ref.get("title")).split(" ")
                 if len(w) > 3 and w not in ("with", "from", "that", "this")), "")
    year = get_date(ref)["year"] or ""
    return f"{normalize_text(lead).replace(' ', '')}{year}{word}" or "ref"


def _entry(ref: dict, key: str) -> str:
    bib_type = TO_BIBTEX_TYPE.get(ref.get("type") or "", "misc")
    container = ref.get("container-title")
    d = get_date(ref)

    def names(lst: list) -> str:
        return " and ".join(_bib_name(n) for n in lst)

    publisher_field = "school" if bib_type == "phdthesis" else "institution" if bib_type == "techreport" else "publisher"
    fields = [
        ("author", names(ref["author"]) if ref.get("author") else None),
        ("editor", names(ref["editor"]) if ref.get("editor") else None),
        ("title", ref.get("title")),
        ("journal" if bib_type == "article" else "booktitle", container if bib_type in ("article", "incollection", "inproceedings") else None),
        ("howpublished", container if bib_type == "misc" else None),
        ("year", d["year"]),
        ("month", MONTH_NAMES[d["month"] - 1] if d["month"] else None),
        ("volume", ref.get("volume")),
        ("number", ref.get("issue")),
        ("pages", re.sub(r"\s*[-–—]+\s*", "--", str(ref["page"])) if filled(ref.get("page")) else None),
        ("edition", ref.get("edition")),
        (publisher_field, ref.get("publisher")),
        ("address", ref.get("publisher-place")),
        ("isbn", ref.get("ISBN")),
        ("doi", ref.get("DOI")),
        ("url", ref.get("URL")),
    ]
    body = []
    for name, value in fields:
        if not filled(value):
            continue
        raw = name in ("author", "editor", "url", "doi", "month")
        body.append(f"  {name} = {{{value if raw else _escape_value(str(value))}}}")
    return f"@{bib_type}{{{key},\n" + ",\n".join(body) + "\n}"


def to_bibtex(refs: Union[dict, list]) -> str:
    """Converts one CSL-JSON reference or a list of them to BibTeX."""
    items = refs if isinstance(refs, list) else [refs]
    used: set = set()
    out = []
    for ref in items:
        ref_id = str(ref.get("id") or "")
        key = ref_id if ref_id and re.fullmatch(r"[\w:.-]+", ref_id, re.ASCII) else _base_key(ref)
        if key in used:
            n = 0
            while key + chr(97 + n) in used:
                n += 1
            key += chr(97 + n)
        used.add(key)
        out.append(_entry(ref, key))
    return "\n\n".join(out)


# ------------------------------------------------------------------ import


def _clean_latex(value: str) -> str:
    """Converts common LaTeX markup to plain Unicode text."""
    s = re.sub(r"\\([`'^\"~=.])\s*\{?\\?([A-Za-z])\}?", lambda m: m.group(2) + ACCENTS[m.group(1)], value)
    s = re.sub(r"\\([cvuH])\s*\{\\?([A-Za-z])\}", lambda m: m.group(2) + ACCENTS[m.group(1)], s)
    s = s.replace("\\textbackslash{}", "\\")
    s = re.sub(r"\\(?:emph|textit|textbf|textsc|mathrm)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\([&%$#_{}])", r"\1", s)
    s = re.sub(r"(?<!\\)[{}]", "", s)
    s = s.replace("~", " ")
    s = re.sub(r"\s+", " ", s)
    return unicodedata.normalize("NFC", s).strip()


def _split_top_level(value: str, separator: "re.Pattern[str]") -> list:
    parts = []
    depth = 0
    current = ""
    i = 0
    while i < len(value):
        c = value[i]
        if c == "{":
            depth += 1
        if c == "}":
            depth -= 1
        m = separator.match(value, i) if depth == 0 else None
        if m:
            parts.append(current)
            current = ""
            i += len(m.group(0))
            continue
        current += c
        i += 1
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


_AND = re.compile(r"\s+and\s+", re.IGNORECASE)
_COMMA = re.compile(r",")


def _parse_names(value: str) -> list:
    out = []
    for raw in _split_top_level(value, _AND):
        if re.fullmatch(r"\{[^{}]*\}", raw):
            out.append({"literal": _clean_latex(raw[1:-1])})
            continue
        parts = [_clean_latex(p) for p in _split_top_level(raw, _COMMA)]
        if len(parts) == 3:
            out.append({"family": parts[0], "suffix": parts[1], "given": parts[2]})
        elif len(parts) == 2:
            out.append({"family": parts[0], "given": parts[1]})
        else:
            out.append(name_parts(_clean_latex(raw)))
    return out


def _find_close(src: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    for i in range(start, len(src)):
        if src[i] == open_char:
            depth += 1
        elif src[i] == close_char:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _parse_fields(body: str, macros: dict) -> dict:
    fields: dict = {}
    n = len(body)
    i = 0

    def skip_space(k: int) -> int:
        while k < n and body[k].isspace():
            k += 1
        return k

    while i < n:
        while i < n and (body[i] == "," or body[i].isspace()):
            i += 1
        name = re.compile(r"[^\s=,{}]+").match(body, i)
        if not name:
            break
        i = skip_space(name.end())
        if i >= n or body[i] != "=":
            break
        i += 1

        value = ""
        while True:
            i = skip_space(i)
            if i < n and body[i] == "{":
                end = _find_close(body, i, "{", "}")
                if end < 0:
                    return fields
                value += body[i + 1:end]
                i = end + 1
            elif i < n and body[i] == '"':
                depth = 0
                j = i + 1
                while j < n:
                    if body[j] == "{":
                        depth += 1
                    elif body[j] == "}":
                        depth -= 1
                    elif body[j] == '"' and depth == 0 and body[j - 1] != "\\":
                        break
                    j += 1
                value += body[i + 1:j]
                i = j + 1
            else:
                token = re.compile(r"[^\s,#}]+").match(body, i)
                if not token:
                    break
                value += macros.get(token.group(0).lower(), token.group(0))
                i = token.end()
            i = skip_space(i)
            if i >= n or body[i] != "#":
                break
            i += 1
        fields[name.group(0).lower()] = value
    return fields


def _to_csl(bib_type: str, key: str, fields: dict) -> dict:
    ref: dict = {"id": key, "type": FROM_BIBTEX_TYPE.get(bib_type) or ("webpage" if fields.get("url") else "document")}

    def text(name: str):
        return _clean_latex(fields[name]) if fields.get(name) else None

    if fields.get("author"):
        ref["author"] = _parse_names(fields["author"])
    if fields.get("editor"):
        ref["editor"] = _parse_names(fields["editor"])
    if fields.get("title"):
        ref["title"] = text("title")
    container = text("journal") or text("journaltitle") or text("booktitle") or text("howpublished")
    if container:
        ref["container-title"] = container

    date = re.match(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", fields.get("date") or "")
    year_match = re.search(r"\d{4}", fields.get("year") or "")
    year = date.group(1) if date else (year_match.group(0) if year_match else None)
    if year:
        month: Any = (date.group(2) if date else None) or fields.get("month")
        if month and not str(month).isdigit():
            key3 = str(month).strip().lower()[:3]
            month = MONTH_NAMES.index(key3) + 1 if key3 in MONTH_NAMES else 0
        parts = [int(year)]
        if month and int(month) > 0:
            parts.append(int(month))
        if date and date.group(3):
            parts.append(int(date.group(3)))
        ref["issued"] = {"date-parts": [parts]}

    if fields.get("volume"):
        ref["volume"] = text("volume")
    if fields.get("number"):
        ref["issue"] = text("number")
    if fields.get("pages"):
        ref["page"] = re.sub(r"\s*-+\s*", "-", text("pages") or "")
    if fields.get("edition"):
        ref["edition"] = text("edition")
    publisher = text("publisher") or text("school") or text("institution") or text("organization")
    if publisher:
        ref["publisher"] = publisher
    if fields.get("address") or fields.get("location"):
        ref["publisher-place"] = text("address") or text("location")
    if fields.get("isbn"):
        ref["ISBN"] = text("isbn")
    if fields.get("doi"):
        ref["DOI"] = re.sub(r"^https?://(dx\.)?doi\.org/", "", fields["doi"].strip(), flags=re.IGNORECASE)
    if fields.get("url"):
        ref["URL"] = fields["url"].strip()
    if bib_type == "phdthesis":
        ref["genre"] = "Doctoral dissertation"
    if bib_type == "mastersthesis":
        ref["genre"] = "Master’s thesis"
    return ref


_HEAD = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")


def parse_bibtex(source: str) -> list:
    """Parses BibTeX/BibLaTeX text into a list of CSL-JSON references."""
    src = str(source)
    macros = {m: str(i + 1) for i, m in enumerate(MONTH_NAMES)}
    refs = []
    i = 0
    while True:
        at = src.find("@", i)
        if at < 0:
            break
        head = _HEAD.match(src, at)
        if not head:
            i = at + 1
            continue
        bib_type = head.group(1).lower()
        open_index = head.end() - 1
        open_char = head.group(2)
        end = _find_close(src, open_index, open_char, "}" if open_char == "{" else ")")
        if end < 0:
            break
        body = src[open_index + 1:end]
        i = end + 1

        if bib_type in ("comment", "preamble"):
            continue
        if bib_type == "string":
            macros.update(_parse_fields(body, macros))
            continue

        comma = body.find(",")
        key = (body if comma < 0 else body[:comma]).strip()
        fields = {} if comma < 0 else _parse_fields(body[comma + 1:], macros)
        refs.append(_to_csl(bib_type, key, fields))
    return refs
