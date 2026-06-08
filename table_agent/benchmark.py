"""Benchmark JSONL helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def iter_benchmark_records(
    input_jsonl: str | Path,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
) -> Iterable[tuple[int, dict[str, Any]]]:
    emitted = 0
    with Path(input_jsonl).open("r", encoding="utf-8") as f:
        for index, line in enumerate(f):
            if index < start:
                continue
            if end is not None and index >= end:
                break
            if not line.strip():
                continue
            if limit is not None and emitted >= limit:
                break
            emitted += 1
            yield index, json.loads(line)


def resolve_image_path(record: dict[str, Any], image_dir: str | Path) -> Path:
    image = record.get("image")
    if not isinstance(image, str) or not image:
        raise ValueError("record image field must be a non-empty string")
    path = Path(image)
    if path.is_absolute():
        return path
    return Path(image_dir) / path
