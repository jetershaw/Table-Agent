"""OTSL parsing and conversion helpers."""

from __future__ import annotations

import sys
from pathlib import Path

OTSL_TOKENS = ("<fcel>", "<ecel>", "<lcel>", "<ucel>", "<xcel>", "<nl>")
UTILS_DIR = Path(__file__).resolve().parents[2] / "utils"


def looks_like_otsl(text: str) -> bool:
    return any(token in text for token in OTSL_TOKENS)


def otsl_to_html_when_possible(text: str) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if stripped.startswith("<table") and stripped.endswith("</table>"):
        return stripped
    if not looks_like_otsl(stripped):
        return ""
    if str(UTILS_DIR) not in sys.path:
        sys.path.insert(0, str(UTILS_DIR))
    from otsl2html import convert_otsl_to_html

    return convert_otsl_to_html(stripped)
