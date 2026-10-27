"""Name parsing and initials."""
from __future__ import annotations

import re
from typing import Any


def name_parts(name: Any) -> dict:
    """
    Accepts a CSL name ({"family", "given", "suffix"} or {"literal"}) or a string
    ("Smith, John" / "John Smith") and returns a CSL name dict.
    """
    if isinstance(name, str):
        return _parse_name_string(name)
    if not isinstance(name, dict):
        return {"family": "", "given": ""}
    if name.get("literal"):
        return {"literal": str(name["literal"])}
    return {
        "family": str(name.get("family") or ""),
        "given": str(name.get("given") or ""),
        "suffix": name.get("suffix"),
    }


def _parse_name_string(value: str) -> dict:
    s = value.strip()
    if "," in s:
        family, _, given = s.partition(",")
        return {"family": family.strip(), "given": given.strip()}
    parts = s.split()
    if len(parts) <= 1:
        return {"family": s, "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def initials(given: str) -> str:
    """"John Ronald" -> "J. R.", "J.R.R." -> "J. R. R.", "Jean-Paul" -> "J.-P." """
    out = []
    for part in str(given).split():
        dotted = re.findall(r"[^\W\d_]\.", part)
        if dotted and "".join(dotted) == part:
            out.append(" ".join(d.upper() for d in dotted))
            continue
        out.append("-".join(seg[0].upper() + "." for seg in part.split("-") if seg))
    return " ".join(out)


def family_name(name: Any) -> str:
    """Family name (or literal) used for in-text citations and sorting."""
    n = name_parts(name)
    return n.get("literal") or n["family"]
