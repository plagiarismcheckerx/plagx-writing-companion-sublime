"""Escapes text and italicises titles for the chosen output format."""
from __future__ import annotations

import re

_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


class Formatter:
    def __init__(self, fmt: str) -> None:
        if fmt not in ("text", "html", "markdown"):
            raise ValueError(f'Unknown output format "{fmt}". Use "text", "html" or "markdown".')
        self.fmt = fmt

    def t(self, s: str) -> str:
        """Plain text in the output format."""
        if self.fmt == "html":
            return "".join(_HTML_ESCAPES.get(c, c) for c in s)
        if self.fmt == "markdown":
            return re.sub(r"([\\*_])", r"\\\1", s)
        return s

    def i(self, s: str) -> str:
        """Italic text in the output format."""
        if self.fmt == "html":
            return f"<i>{self.t(s)}</i>"
        if self.fmt == "markdown":
            return f"*{self.t(s)}*"
        return s
