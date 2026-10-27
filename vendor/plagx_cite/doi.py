"""DOI normalising, extraction and lookup (Crossref, with a doi.org fallback)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Optional, Tuple
from urllib.parse import quote, unquote

HttpGet = Callable[[str, dict], Tuple[int, str]]

_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)

CROSSREF_TYPES = {
    "journal-article": "article-journal",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "book-chapter": "chapter",
    "book-section": "chapter",
    "book-part": "chapter",
    "reference-entry": "entry-encyclopedia",
    "proceedings-article": "paper-conference",
    "report": "report",
    "dissertation": "thesis",
    "posted-content": "article",
    "dataset": "dataset",
}

_ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}


def _trim_trailing(doi: str) -> str:
    s = re.sub(r"[.,;:]+$", "", doi)
    # Drop a closing bracket that has no opening partner inside the DOI.
    while s and s[-1] in ")]":
        close = s[-1]
        opening = "(" if close == ")" else "["
        if s.count(opening) >= s.count(close):
            break
        s = re.sub(r"[.,;:]+$", "", s[:-1])
    return s


def normalize_doi(value: Optional[str]) -> Optional[str]:
    """Returns a bare DOI ("10.xxxx/...") from a DOI, doi: string or doi.org URL, or None if invalid."""
    s = unquote(_PREFIX.sub("", str(value if value is not None else "").strip()))
    return _trim_trailing(s) if re.fullmatch(r"10\.\d{4,9}/\S+", s) else None


def is_doi(value: Optional[str]) -> bool:
    return normalize_doi(value) is not None


def extract_dois(text: Optional[str]) -> list:
    """Finds every DOI in a block of text (unique, in order of appearance)."""
    found: dict = {}
    for m in _PATTERN.finditer(str(text or "")):
        doi = _trim_trailing(m.group(0))
        found.setdefault(doi.lower(), doi)
    return list(found.values())


def _clean_text(value: Any) -> Optional[str]:
    """Metadata often contains HTML/JATS markup and entities; returns plain text."""
    if value is None or value == "":
        return None
    s = re.sub(r"<[^>]+>", "", str(value))

    def entity(m: "re.Match[str]") -> str:
        e = m.group(1)
        if e[0] == "#":
            return chr(int(e[2:], 16) if e[1].lower() == "x" else int(e[1:]))
        return _ENTITIES.get(e.lower(), m.group(0))

    s = re.sub(r"&(#x[0-9a-f]+|#\d+|[a-z]+);", entity, s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _clean_names(names: Any) -> Optional[list]:
    if not isinstance(names, list) or not names:
        return None
    out = []
    for a in names:
        if a.get("family"):
            out.append({"family": _clean_text(a["family"]), "given": _clean_text(a.get("given")) or ""})
        else:
            out.append({"literal": _clean_text(a.get("name") or a.get("literal")) or ""})
    return out


def _texts(value: Any) -> list:
    values = value if isinstance(value, list) else [value]
    return [t for t in (_clean_text(v) for v in values) if t]


def _with_subtitle(title: Optional[str], subtitle: Optional[str]) -> Optional[str]:
    if not title or not subtitle or subtitle.lower() in title.lower():
        return title
    return f"{title} {subtitle}" if re.search(r"[:?!]$", title) else f"{title}: {subtitle}"


def _date_parts(issued: Any) -> Optional[dict]:
    try:
        parts = issued["date-parts"][0]
    except (KeyError, IndexError, TypeError):
        return None
    return {"date-parts": [[n for n in parts if n is not None]]} if isinstance(parts, list) else None


def _compact(ref: dict) -> dict:
    return {k: v for k, v in ref.items() if v is not None and v != ""}


def _first(values: list) -> Optional[str]:
    return values[0] if values else None


def from_crossref(work: dict) -> dict:
    """Maps a Crossref "work" record to CSL-JSON."""
    ref_type = CROSSREF_TYPES.get(work.get("type") or "", "article")
    issued = work.get("issued")
    try:
        has_issued = bool(issued["date-parts"][0][0])
    except (KeyError, IndexError, TypeError):
        has_issued = False
    if not has_issued:
        issued = work.get("published-print") or work.get("published-online") or work.get("created")
    # For chapters and proceedings Crossref may list [series, book]; the book is last.
    containers = _texts(work.get("container-title"))
    ref = {
        "id": work.get("DOI"),
        "type": ref_type,
        "title": _with_subtitle(_first(_texts(work.get("title"))), _first(_texts(work.get("subtitle")))),
        "author": _clean_names(work.get("author")),
        "editor": _clean_names(work.get("editor")),
        "container-title": (containers[-1] if containers else None) if ref_type in ("chapter", "paper-conference") else _first(containers),
        "issued": _date_parts(issued),
        "volume": work.get("volume"),
        "issue": work.get("issue"),
        "page": work.get("page"),
        "publisher": _clean_text(work.get("publisher")),
        "publisher-place": _clean_text(work.get("publisher-location")),
        "ISBN": _first(_texts(work.get("ISBN"))),
        "DOI": work.get("DOI"),
        "URL": work.get("URL"),
    }
    institution = work.get("institution")
    if ref_type == "thesis" and isinstance(institution, list) and institution and institution[0].get("name"):
        ref["publisher"] = _clean_text(institution[0]["name"])
    return _compact(ref)


def _from_csl(data: dict) -> dict:
    """Keeps the CSL-JSON fields Plagx Cite uses from doi.org content negotiation (DataCite, arXiv, mEDRA…)."""
    return _compact({
        "id": data.get("DOI"),
        "type": data.get("type") or "article",
        "title": _first(_texts(data.get("title"))),
        "author": _clean_names(data.get("author")),
        "editor": _clean_names(data.get("editor")),
        "container-title": _first(_texts(data.get("container-title"))),
        "issued": _date_parts(data.get("issued")),
        "volume": data.get("volume"),
        "issue": data.get("issue"),
        "page": data.get("page"),
        "publisher": _clean_text(data.get("publisher")),
        "DOI": data.get("DOI"),
        "URL": data.get("URL"),
    })


def http_get(url: str, headers: dict) -> Tuple[int, str]:
    """Default HTTP GET using the standard library; follows redirects."""
    request = urllib.request.Request(url, headers={
        **headers, "User-Agent": "plagx-cite-python (+https://github.com/plagiarismcheckerx/plagx-cite-python)",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def lookup_doi(value: str, mailto: Optional[str] = None, http: Optional[HttpGet] = None) -> dict:
    """
    Looks up a DOI and returns CSL-JSON. Tries the public Crossref API first, then
    doi.org content negotiation (covers DataCite DOIs such as arXiv and Zenodo).

    `mailto` (optional) uses Crossref's polite pool. `http(url, headers) -> (status, body)`
    replaces the built-in HTTP client.

    Raises ValueError for an invalid DOI and LookupError when the DOI can't be found.
    """
    doi = normalize_doi(value)
    if doi is None:
        raise ValueError(f'Not a valid DOI: "{value}"')
    get = http or http_get

    url = "https://api.crossref.org/works/" + quote(doi, safe="-_.!~*'()")
    if mailto:
        url += "?mailto=" + quote(mailto, safe="-_.!~*'()")
    status, body = get(url, {"Accept": "application/json"})
    if 200 <= status < 300:
        return from_crossref(json.loads(body).get("message") or {})
    if status != 404:
        raise LookupError(f"DOI lookup failed ({status}) for {doi}")

    status, body = get("https://doi.org/" + quote(doi, safe=";,/?:@&=+$-_.!~*'()#"),
                       {"Accept": "application/vnd.citationstyles.csl+json"})
    if status == 404:
        raise LookupError(f"DOI not found: {doi}")
    if not 200 <= status < 300:
        raise LookupError(f"DOI lookup failed ({status}) for {doi}")
    return _from_csl(json.loads(body) or {})
