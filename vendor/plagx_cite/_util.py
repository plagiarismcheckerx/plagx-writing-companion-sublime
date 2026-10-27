"""Date, text and page helpers shared by the styles."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

MONTHS_MLA = [
    "Jan.", "Feb.", "Mar.", "Apr.", "May", "June",
    "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.",
]


def filled(value: Any) -> bool:
    """JavaScript-style truthiness for optional fields (the string "0" counts as filled)."""
    return value is not None and value is not False and value != "" and value != 0 and value != []


def get_date(ref: dict) -> dict:
    """Returns {year, month, day} from a CSL `issued` date or a plain `year` field."""
    issued = ref.get("issued")
    parts = None
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            parts = date_parts[0]
    if parts and filled(parts[0]):
        def part(i: int) -> Optional[int]:
            return int(parts[i]) if len(parts) > i and filled(parts[i]) else None
        return {"year": int(parts[0]), "month": part(1), "day": part(2)}
    if filled(ref.get("year")):
        return {"year": int(ref["year"]), "month": None, "day": None}
    return {"year": None, "month": None, "day": None}


def get_year(ref: dict) -> Optional[str]:
    year = get_date(ref)["year"]
    return str(year) if year else None


def normalize_text(value: Any) -> str:
    """Lowercase, strip accents and punctuation; used for comparisons and keys."""
    s = unicodedata.normalize("NFKD", "" if value is None else str(value))
    s = re.sub("[̀-ͯ]", "", s).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def ends_with_terminal(value: str) -> bool:
    return bool(re.search(r"[.?!][\"”’]?$", str(value).strip()))


def dot(value: str) -> str:
    """Period to append unless the text already ends with terminal punctuation."""
    return "" if ends_with_terminal(value) else "."


def page_range(page: Any, dash: str = "–") -> str:
    return re.sub(r"\s*[-–—]+\s*", dash, str(page).strip())


def is_page_range(page: Any) -> bool:
    return bool(re.search(r"[-–—]", str(page)))


def ordinal(value: Any) -> str:
    if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit())):
        return str(value)
    n = int(value)
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}"


def link(ref: dict) -> str:
    """Preferred link for a reference: a valid DOI first, then URL."""
    from .doi import normalize_doi

    doi = normalize_doi(ref["DOI"]) if filled(ref.get("DOI")) else None
    if doi:
        return doi_url(doi)
    return str(ref.get("URL") or "")
