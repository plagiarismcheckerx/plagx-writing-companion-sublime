"""Editor-independent glue between Sublime settings and the Plagx Cite / Preflight cores."""
import re

from ..vendor.plagx_cite import check_references, format_bibliography, parse_bibtex
from ..vendor.plagx_preflight import CHECKS, check_draft


def draft_options(settings):
    """Turns plugin settings into plagx_preflight.check_draft keyword arguments."""
    options = {"style": settings.get("style") or "apa"}
    for name in ("min_words", "max_words"):
        value = settings.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            options[name] = int(value)
    checks = [c for c in (settings.get("checks") or []) if c in CHECKS]
    if checks:
        options["checks"] = checks
    headings = settings.get("required_headings") or []
    if headings:
        options["required_headings"] = [str(h) for h in headings]
    return options


def utf16_to_index(text):
    """Maps UTF-16 code-unit offsets (used by Preflight) to string indices (used by Sublime)."""
    table = []
    for i, ch in enumerate(text):
        table.append(i)
        if ord(ch) > 0xFFFF:
            table.append(i)
    table.append(len(text))
    return lambda offset: table[min(max(offset, 0), len(table) - 1)]


def run_draft(text, settings):
    """Checks a draft; issue start/end are converted to string indices."""
    result = check_draft(text, **draft_options(settings))
    to_index = utf16_to_index(text)
    for issue in result["issues"]:
        issue["start"] = to_index(issue["start"])
        issue["end"] = to_index(issue["end"])
    return result


def readiness(result):
    """Ready when there are no errors; warnings are listed but don't block."""
    stats = result["stats"]
    errors, warnings = result["errors"], result["warnings"]
    ready = errors == 0
    return {
        "ready": ready,
        "label": ("Ready with suggestions" if warnings else "Ready") if ready else "Not ready",
        "words": stats["words"],
        "minutes": max(1, int(round(stats["readingTimeMinutes"]))),
        "errors": errors,
        "warnings": warnings,
        "infos": result["infos"],
        "flesch": int(round(stats["fleschReadingEase"])),
    }


def bibliography(source, style="apa"):
    refs = parse_bibtex(source)
    return refs, format_bibliography(refs, style=style, format="text")


def bib_key_line(source, key):
    """Zero-based line where a BibTeX entry key is defined (0 when not found)."""
    if not key or key.startswith("#"):
        return 0
    pattern = re.compile(r"^\s*@\w+\s*\{\s*" + re.escape(key) + r"\s*,")
    for i, line in enumerate(source.splitlines()):
        if pattern.match(line):
            return i
    return 0


def check_bib(source, check_dois=False):
    result = check_references(parse_bibtex(source), check_dois=check_dois)
    for issue in result["issues"]:
        issue["line"] = bib_key_line(source, issue["ref"])
    return result
