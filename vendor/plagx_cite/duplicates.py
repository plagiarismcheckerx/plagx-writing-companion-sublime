"""Duplicate reference detection."""
from __future__ import annotations

from ._names import family_name
from ._util import normalize_text
from .doi import normalize_doi


def _keys_for(ref: dict) -> dict:
    keys = {}
    doi = normalize_doi(ref["DOI"]) if ref.get("DOI") else None
    if doi:
        keys["doi"] = doi.lower()
    title = normalize_text(ref.get("title"))
    if title:
        lead = normalize_text(family_name(ref["author"][0])) if ref.get("author") else ""
        keys["title"] = f"{title}|{lead}"
    return keys


def find_duplicates(refs: list) -> list:
    """
    Finds references that appear more than once, matched by DOI or by
    normalized title + first author.
    Returns [{"indexes": [0, 3], "reasons": ["doi", "title"]}, ...].
    """
    keys = [_keys_for(r) for r in refs]
    parent = list(range(len(refs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first_seen: dict = {}
    for i, k in enumerate(keys):
        for reason, value in k.items():
            key = f"{reason}:{value}"
            if key in first_seen:
                parent[find(i)] = find(first_seen[key])
            else:
                first_seen[key] = i

    groups: dict = {}
    for i in range(len(refs)):
        groups.setdefault(find(i), []).append(i)

    out = []
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        reasons = []
        for reason in ("doi", "title"):
            values = [keys[i][reason] for i in indexes if keys[i].get(reason)]
            if len(values) > len(set(values)):
                reasons.append(reason)
        out.append({"indexes": indexes, "reasons": reasons})
    return out
