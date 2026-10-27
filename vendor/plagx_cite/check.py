"""Checks a reference list for problems."""
from __future__ import annotations

from typing import Optional

from ._util import get_year
from .doi import HttpGet, lookup_doi, normalize_doi
from .duplicates import find_duplicates


def _label(ref: dict, i: int) -> str:
    return str(ref["id"]) if ref.get("id") else f"#{i + 1}"


def check_references(refs: list, check_dois: bool = False, mailto: Optional[str] = None,
                     http: Optional[HttpGet] = None) -> dict:
    """
    Errors: duplicate references, invalid DOIs, DOIs not found (with check_dois=True).
    Warnings: missing title, author or year.

    Returns {"references", "errors", "warnings", "issues": [{"level", "code", "index", "ref", "message"}]}.
    """
    issues = []

    def add(level: str, code: str, index: int, message: str) -> None:
        issues.append({"level": level, "code": code, "index": index, "ref": _label(refs[index], index), "message": message})

    for group in find_duplicates(refs):
        names = [_label(refs[i], i) for i in group["indexes"]]
        for i in group["indexes"][1:]:
            add("error", "duplicate", i,
                f"Possible duplicate ({' and '.join(group['reasons'])} match) of {names[0]}: {', '.join(names)}")

    for i, ref in enumerate(refs):
        if not ref.get("title"):
            add("warning", "missing-title", i, "No title")
        if not ref.get("author") and not ref.get("editor"):
            add("warning", "missing-author", i, "No author or editor")
        if not get_year(ref):
            add("warning", "missing-year", i, "No year (will show as n.d.)")
        if ref.get("DOI") and not normalize_doi(ref["DOI"]):
            add("error", "invalid-doi", i, f'Invalid DOI "{ref["DOI"]}"')

    if check_dois:
        for i, ref in enumerate(refs):
            doi = normalize_doi(ref["DOI"]) if ref.get("DOI") else None
            if not doi:
                continue
            try:
                lookup_doi(doi, mailto=mailto, http=http)
            except Exception as e:  # noqa: BLE001 - every failure is reported as "not found"
                add("error", "doi-not-found", i, str(e))

    issues.sort(key=lambda x: (x["index"], 0 if x["level"] == "error" else 1))
    errors = sum(1 for x in issues if x["level"] == "error")
    return {"references": len(refs), "errors": errors, "warnings": len(issues) - errors, "issues": issues}
