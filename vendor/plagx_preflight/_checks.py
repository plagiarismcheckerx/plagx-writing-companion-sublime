"""The individual check groups. Each reports issues through Context.add()."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from . import _citations as citations
from ._text import WS, count_words, js_lower, normalize_heading, paragraph_sentences, words
from ._unicode import L, LL, LU

LONG_SENTENCE_WORDS = 40
LONG_PARAGRAPH_WORDS = 250

# Codes inside URLs, email addresses and `code` are skipped.
_MASKED = re.compile(
    "(?:unmatched-|double-space|space-before|missing-space|repeated-|mixed-quote|a-an|sentence-capital"
    "|lowercase-i|common-confusion|passive-voice)"
)
_MASK_RE = re.compile(
    f"\\bhttps?://[^{WS}<>()]+|\\bwww\\.[^{WS}<>()]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+|`[^`\\n]*`",
    re.A,
)


class Context:
    def __init__(self, text: str, opts: Dict, doc: Dict, stats: Dict):
        self.text = text
        self.opts = opts
        self.doc = doc
        self.stats = stats
        self.body = doc["body"]
        self.body_text = text[: doc["body_end"]]
        self.masks = [(m.start(), m.end()) for m in _MASK_RE.finditer(text)]
        self.seen = set()
        self.issues: List[Dict] = []

    def add(self, level: str, code: str, start: int, end: int, message: str, suggestion: Optional[str] = None):
        if _MASKED.match(code) and any(start < b and end > a for a, b in self.masks):
            return
        key = (code, start, end, message)
        if key in self.seen:
            return
        self.seen.add(key)
        self.issues.append({"level": level, "code": code, "message": message, "start": start, "end": end,
                            "suggestion": suggestion})

    def add_doc(self, level: str, code: str, message: str):
        self.add(level, code, 0, 0, message)


def _upper_first(s: str) -> str:
    # JavaScript upper-cases the first UTF-16 unit, which leaves astral characters unchanged.
    if not s or ord(s[0]) > 0xFFFF:
        return s
    return s[0].upper() + s[1:]


_UPPER_START = re.compile(f"[{LU}]")


def _match_case(fix: str, original: str) -> str:
    return _upper_first(fix) if _UPPER_START.match(original) else fix


def _starts_with_any(w: str, prefixes) -> bool:
    return any(w.startswith(p) for p in prefixes)


def _u16_len(s: str) -> int:
    return len(s) + sum(1 for c in s if ord(c) > 0xFFFF)


# ---------------------------------------------------------------- length

_LIST_ITEM = re.compile(f"(?:[-*+\u2022]|[0-9]+[.)])[{WS}]")


def length(ctx: Context):
    w = ctx.stats["words"]
    o = ctx.opts
    if o["min_words"] is not None and w < o["min_words"]:
        ctx.add_doc("warning", "word-count-low", f"Suggestion: the draft has {w} words; the minimum is {o['min_words']}.")
    if o["max_words"] is not None and w > o["max_words"]:
        ctx.add_doc("warning", "word-count-high", f"Suggestion: the draft has {w} words; the maximum is {o['max_words']}.")
    for p in ctx.body:
        if p["heading"]:
            continue
        sentences = paragraph_sentences(p)
        for s in sentences:
            n = count_words(s["text"])
            if n > LONG_SENTENCE_WORDS:
                ctx.add("warning", "long-sentence", s["start"], s["end"],
                        f"Suggestion: this sentence has {n} words; consider splitting it (over {LONG_SENTENCE_WORDS}).")
        n = count_words(p["text"])
        if n > LONG_PARAGRAPH_WORDS:
            ctx.add("info", "long-paragraph", p["start"], p["end"],
                    f"Suggestion: this paragraph has {n} words; consider splitting it (over {LONG_PARAGRAPH_WORDS}).")
        if len(sentences) == 1 and not _LIST_ITEM.match(p["text"]):
            ctx.add("info", "single-sentence-paragraph", p["start"], p["end"], "Suggestion: this paragraph has only one sentence.")
    headings = {normalize_heading(p["text"]) for p in ctx.doc["paragraphs"] if p["heading"]}
    for h in o["required_headings"]:
        if normalize_heading(h) not in headings:
            ctx.add_doc("warning", "missing-heading", f'Suggestion: add a "{h}" heading.')


# ---------------------------------------------------------------- references

_ET_AL = re.compile(f"\\bet\\.?[{WS}]*al\\b\\.*", re.I | re.A)


def references(ctx: Context):
    doc = ctx.doc
    cites = citations.find(ctx.body_text, ctx.opts["style"])
    if cites and doc["reference_heading"] is None:
        ctx.add_doc("error", "missing-reference-section",
                    "Suggestion: the draft has citations but no reference list heading (References or Works Cited).")
    entries = [{**e, **citations.parse_entry(e["text"])} for e in doc["entries"]]
    if doc["reference_heading"] is not None:
        for c in cites:
            if not any(citations.matches(c, e) for e in entries):
                ctx.add("error", "citation-no-reference", c["start"], c["end"],
                        f'Suggestion: "{c["text"]}" has no matching entry in the reference list.')
        for e in entries:
            if not any(citations.matches(c, e) for c in cites):
                ctx.add("warning", "reference-not-cited", e["start"], e["end"], "Suggestion: this reference is never cited in the text.")
    for m in _ET_AL.finditer(ctx.body_text):
        if js_lower(m.group()) != "et al.":
            ctx.add("warning", "et-al-format", m.start(), m.end(), 'Suggestion: write "et al." with one period.', "et al.")


# ---------------------------------------------------------------- punctuation

_PAIRS = {")": "(", "]": "[", "}": "{"}
_LIST_MARKER_BEFORE = re.compile(f"(?:^|[{WS}])[A-Za-z0-9]{{1,3}}\\Z")
_DOUBLE_SPACE = re.compile(f"(?<=[^{WS}]) {{2,}}(?=[^{WS}])")
_SPACE_BEFORE = re.compile(f"(?<=[{L}0-9)\\]\"\u201d]) +([,;:!?.])(?=[{WS}]|\\Z)")
_MISSING_SPACE = re.compile("[,;:!?](?=[A-Za-z])|(?<=[a-z]{2})\\.(?=[A-Z][a-z])")
_REPEATED = re.compile(r"([!?,;:])\1+|(?<!\.)\.\.(?!\.)")
_UNMATCHED = "Suggestion: this quotation mark has no matching pair."


def punctuation(ctx: Context):
    straight = -1
    curly = -1
    for p in ctx.body:
        t = p["text"]
        at = p["start"]

        # Quotation marks
        quotes = [i for i, c in enumerate(t) if c == '"']
        if quotes and straight < 0:
            straight = at + quotes[0]
        if len(quotes) % 2 == 1:
            i = quotes[-1]
            ctx.add("warning", "unmatched-quote", at + i, at + i + 1, _UNMATCHED)
        opened = []
        for i, c in enumerate(t):
            if c in "\u201c\u201d" and curly < 0:
                curly = at + i
            if c == "\u201c":
                opened.append(i)
            elif c == "\u201d":
                if opened:
                    opened.pop()
                else:
                    ctx.add("warning", "unmatched-quote", at + i, at + i + 1, _UNMATCHED)
        for i in opened:
            ctx.add("warning", "unmatched-quote", at + i, at + i + 1, _UNMATCHED)

        # Brackets
        stack = []
        for i, c in enumerate(t):
            if c in "([{":
                stack.append(i)
            elif c in _PAIRS:
                if stack and t[stack[-1]] == _PAIRS[c]:
                    stack.pop()
                else:
                    # List markers such as "a)", "ii)" or "1)".
                    if c == ")" and _LIST_MARKER_BEFORE.search(t, 0, i):
                        continue
                    ctx.add("warning", "unmatched-bracket", at + i, at + i + 1, f'Suggestion: "{c}" has no matching bracket.')
        for i in stack:
            ctx.add("warning", "unmatched-bracket", at + i, at + i + 1, f'Suggestion: "{t[i]}" has no matching bracket.')

        for m in _DOUBLE_SPACE.finditer(t):
            ctx.add("info", "double-space", at + m.start(), at + m.end(), "Suggestion: use a single space.", " ")
        for m in _SPACE_BEFORE.finditer(t):
            ctx.add("warning", "space-before-punctuation", at + m.start(), at + m.end(),
                    f'Suggestion: remove the space before "{m.group(1)}".', m.group(1))
        for m in _MISSING_SPACE.finditer(t):
            ctx.add("warning", "missing-space-after-punctuation", at + m.start(), at + m.start() + 1,
                    f'Suggestion: add a space after "{m.group()}".', f"{m.group()} ")
        for m in _REPEATED.finditer(t):
            ctx.add("warning", "repeated-punctuation", at + m.start(), at + m.end(),
                    f'Suggestion: "{m.group()}" repeats punctuation.', m.group()[0])
    if straight >= 0 and curly >= 0:
        i = max(straight, curly)
        ctx.add("info", "mixed-quote-styles", i, i + 1, "Suggestion: the draft mixes straight and curly quotation marks.")


# ---------------------------------------------------------------- grammar

_SILENT_H = ("hour", "honest", "honor", "honour", "heir")
_CONSONANT_SOUND = ("uni", "use", "usa", "usu", "uti", "ure", "uro", "urani", "eu", "ewe", "one", "once", "ubiq", "unanim")
_UNCERTAIN = ("herb", "histor", "hotel", "unin", "unim", "unid", "oner")

_I = re.I | re.A
_CONFUSIONS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(could|would|should|must|might) of\b", _I), "{0} have"),
    (re.compile(r"\bits (a|an|been|not|going)\b", _I), "it's {0}"),
    (re.compile("\\bit['\u2019]s own\\b", _I), "its own"),
    (re.compile(r"\b(more|less|better|worse|rather|greater|fewer|larger|smaller|higher|lower|faster|slower|easier|harder) then\b", _I), "{0} than"),
    (re.compile(r"\btheir (is|are|was|were)\b", _I), "there {0}"),
    (re.compile(r"\bthere own\b", _I), "their own"),
    (re.compile(r"\b(the|an) affect\b", _I), "{0} effect"),
    (re.compile(r"\b(may|might|will|can|could|would|should|negatively|positively|greatly|significantly) effect\b", _I), "{0} affect"),
    (re.compile(r"\bloose (weight|track|control)\b", _I), "lose {0}"),
    (re.compile(r"\balot\b", _I), "a lot"),
]
_PASSIVE = re.compile(
    f"\\b(?:am|is|are|was|were|be|been|being)[{WS}]+(?:[a-z]+ly[{WS}]+)?(?:[a-z]{{3,}}ed|written|done|made|given|taken"
    "|shown|seen|known|found|held|chosen|built|drawn|taught|thought|brought|said|told|sent|kept|paid|begun|broken"
    "|driven|eaten|forgotten|hidden|spoken|stolen|worn)\\b",
    _I,
)
_I_FORM = re.compile("i(['\u2019](?:m|ve|ll|d))?\\Z")
_GAP = re.compile(f"[{WS}]+\\Z")
_HAS_LETTER = re.compile(f"[{L}]")
_LOWER_START = re.compile(f"[{LL}]")
_HAS_UPPER = re.compile(f"[{LU}]")


def grammar(ctx: Context):
    for p in ctx.body:
        t = p["text"]
        toks = words(t)
        for i, tok in enumerate(toks):
            low = js_lower(tok["text"])
            nxt = None
            if i + 1 < len(toks) and _GAP.match(t, tok["end"], toks[i + 1]["start"]):
                nxt = toks[i + 1]

            if nxt and js_lower(nxt["text"]) == low and _HAS_LETTER.search(low) and low not in ("had", "that"):
                ctx.add("warning", "repeated-word", p["start"] + tok["start"], p["start"] + nxt["end"],
                        f'Suggestion: "{tok["text"]} {nxt["text"]}" looks like a repeated word.', tok["text"])

            if nxt and low in ("a", "an"):
                nw = nxt["text"].split("-")[0]
                nl = js_lower(nw)
                nw_len = _u16_len(nw)
                acronym = nw_len > 1 and nw == nw.upper()
                if (nw_len > 1 and not re.search("[0-9]", nw) and not acronym and re.match("[a-z]", nl)
                        and not _starts_with_any(nl, _UNCERTAIN)):
                    vowel = _starts_with_any(nl, _SILENT_H) or (bool(re.match("[aeiou]", nl)) and not _starts_with_any(nl, _CONSONANT_SOUND))
                    expected = "an" if vowel else "a"
                    if low != expected:
                        ctx.add("warning", "a-an", p["start"] + tok["start"], p["start"] + tok["end"],
                                f'Suggestion: use "{expected}" before "{nxt["text"]}".', _match_case(expected, tok["text"]))

            im = _I_FORM.match(tok["text"])
            if im:
                before = t[tok["start"] - 1] if tok["start"] > 0 else ""
                after = t[tok["end"]] if tok["end"] < len(t) else ""
                if im.group(1) or (after not in (".", ")") and before != "."):
                    fix = _upper_first(tok["text"])
                    ctx.add("warning", "lowercase-i", p["start"] + tok["start"], p["start"] + tok["end"],
                            f'Suggestion: use "{fix}" instead of "{tok["text"]}".', fix)

        if not p["heading"]:
            for s in paragraph_sentences(p):
                ws = words(s["text"])
                first = ws[0] if ws else None
                if (first and first["start"] == 0 and _LOWER_START.match(first["text"]) and not _HAS_UPPER.search(first["text"])
                        and not _I_FORM.match(first["text"]) and s["text"][first["end"]:first["end"] + 1] != ")"):
                    ctx.add("warning", "sentence-capital", s["start"], s["start"] + first["end"],
                            "Suggestion: start the sentence with a capital letter.", _upper_first(first["text"]))

        for pattern, fix in _CONFUSIONS:
            for m in pattern.finditer(t):
                suggestion = _match_case(fix.format(m.group(1) if m.lastindex else ""), m.group())
                ctx.add("warning", "common-confusion", p["start"] + m.start(), p["start"] + m.end(),
                        f'Suggestion: "{m.group()}" may be "{suggestion}".', suggestion)


def passive_voice(ctx: Context):
    for p in ctx.body:
        for m in _PASSIVE.finditer(p["text"]):
            ctx.add("info", "passive-voice", p["start"] + m.start(), p["start"] + m.end(),
                    f'Suggestion: "{m.group()}" may be passive voice.')
