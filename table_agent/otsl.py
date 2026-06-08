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



def split_otsl_rows(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if not looks_like_otsl(stripped):
        return [line.strip() for line in stripped.splitlines() if line.strip()]
    pieces = stripped.split("<nl>")
    rows = []
    for piece in pieces:
        row = piece.strip()
        if row:
            rows.append(row + "<nl>")
    return rows


def validate_otsl_tokens(text: str) -> list[str]:
    warnings: list[str] = []
    if not text or not looks_like_otsl(text):
        return warnings
    import re

    tokens = re.findall(r"<[^>]+>", text)
    illegal = sorted(set(token for token in tokens if token not in OTSL_TOKENS))
    if illegal:
        warnings.append(f"illegal_otsl_tokens: {illegal}")
    return warnings


def estimate_otsl_shape(text: str) -> tuple[int, int]:
    rows = split_otsl_rows(text)
    if not rows:
        return 0, 0
    if not looks_like_otsl(text):
        return len(rows), 0
    col_counts = []
    for row in rows:
        col_counts.append(sum(row.count(token) for token in OTSL_TOKENS if token != "<nl>"))
    return len(rows), max(col_counts) if col_counts else 0


def merge_vertical_otsl(crop_otsls: list[str]) -> dict[str, object]:
    rows: list[str] = []
    warnings: list[str] = []
    row_counts: list[int] = []
    col_counts: list[int] = []
    any_otsl = False

    for index, otsl in enumerate(crop_otsls):
        text = str(otsl or "").strip()
        if not text:
            warnings.append(f"empty_crop_otsl:{index}")
            row_counts.append(0)
            col_counts.append(0)
            continue
        any_otsl = any_otsl or looks_like_otsl(text)
        warnings.extend(validate_otsl_tokens(text))
        crop_rows = split_otsl_rows(text)
        rows.extend(crop_rows)
        row_count, col_count = estimate_otsl_shape(text)
        row_counts.append(row_count)
        col_counts.append(col_count)

    merged = "".join(rows) if any_otsl else "\n".join(rows)
    row_count, col_count = estimate_otsl_shape(merged)
    non_zero_cols = [count for count in col_counts if count]
    if non_zero_cols and max(non_zero_cols) - min(non_zero_cols) > 1:
        warnings.append(f"column_count_inconsistent:{non_zero_cols}")
    html = otsl_to_html_when_possible(merged)
    return {
        "otsl": merged,
        "html": html,
        "row_count": row_count,
        "estimated_col_count": col_count,
        "crop_row_counts": row_counts,
        "crop_col_counts": col_counts,
        "warnings": warnings,
    }
