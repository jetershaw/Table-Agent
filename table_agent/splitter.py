"""Vertical split candidate generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.config import AgentConfig


@dataclass(frozen=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int

    def to_list(self) -> list[int]:
        return [self.left, self.top, self.right, self.bottom]


def propose_vertical_crops(
    image_path: str | Path,
    *,
    max_chunks: int,
    target_chunk_height: int = 1200,
) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    chunk_count = _choose_chunk_count(height, max_chunks, target_chunk_height)
    cuts = _choose_safe_cuts(image, chunk_count)
    boxes = _cuts_to_boxes(width, height, cuts)
    return {
        "image_path": str(image_path),
        "image_size": [width, height],
        "cuts": cuts,
        "boxes": [box.to_list() for box in boxes],
        "chunk_count": len(boxes),
    }


def save_crops(
    image_path: str | Path,
    boxes: list[list[int]],
    output_dir: str | Path,
    *,
    stem: str | None = None,
) -> list[dict[str, Any]]:
    image = Image.open(image_path).convert("RGB")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = stem or Path(image_path).stem
    chunks = []
    for index, box in enumerate(boxes):
        crop = image.crop(tuple(box))
        crop_path = out_dir / f"{base}.crop-{index:02d}.jpg"
        crop.save(crop_path, quality=95)
        chunks.append(
            {
                "index": index,
                "box": box,
                "crop_path": str(crop_path),
                "status": "pending",
            }
        )
    return chunks


def run_split_generation(
    config: AgentConfig,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
    output_json: str | None = None,
) -> dict[str, Any]:
    results = []
    for record_index, record in iter_benchmark_records(
        config.paths.input_jsonl, start=start, end=end, limit=limit
    ):
        image_path = resolve_image_path(record, config.paths.image_dir)
        metadata = propose_vertical_crops(image_path, max_chunks=config.max_chunks)
        stem = f"{record_index:05d}_{Path(image_path).stem}"
        metadata["chunks"] = save_crops(
            image_path, metadata["boxes"], config.paths.crop_dir, stem=stem
        )
        results.append(metadata)

    output_path = Path(output_json or "outputs/split_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"output_json": str(output_path), "total": len(results)}


def _choose_chunk_count(height: int, max_chunks: int, target_chunk_height: int) -> int:
    if height <= target_chunk_height:
        return 1
    estimated = int(np.ceil(height / target_chunk_height))
    return max(1, min(max_chunks, estimated))


def _choose_safe_cuts(image: Image.Image, chunk_count: int) -> list[int]:
    if chunk_count <= 1:
        return []
    _, height = image.size
    scores = _horizontal_safety_scores(image)
    cuts = []
    min_gap = max(24, height // (chunk_count * 4))
    for i in range(1, chunk_count):
        target = round(height * i / chunk_count)
        window = max(40, height // (chunk_count * 4))
        low = max(8, target - window)
        high = min(height - 8, target + window)
        candidates = np.arange(low, high)
        if candidates.size == 0:
            cut = target
        else:
            ranked = sorted(candidates, key=lambda y: (scores[y], abs(int(y) - target)))
            cut = int(ranked[0])
        cut = _avoid_nearby_cuts(cut, cuts, min_gap, height)
        cuts.append(cut)
    return sorted(cuts)


def _horizontal_safety_scores(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    ink = 1.0 - gray
    density = ink.mean(axis=1)
    grad = np.abs(np.diff(gray, axis=0, prepend=gray[:1])).mean(axis=1)
    density = _smooth(density, radius=8)
    grad = _smooth(grad, radius=4)
    band = _smooth(density, radius=20)
    return (density * 0.60) + (grad * 0.25) + (band * 0.15)


def _smooth(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values
    kernel = np.ones(radius * 2 + 1, dtype=np.float32)
    kernel /= kernel.sum()
    return np.convolve(values, kernel, mode="same")


def _avoid_nearby_cuts(cut: int, existing: list[int], min_gap: int, height: int) -> int:
    adjusted = cut
    for other in existing:
        if abs(adjusted - other) < min_gap:
            if adjusted <= other:
                adjusted = max(8, other - min_gap)
            else:
                adjusted = min(height - 8, other + min_gap)
    return adjusted


def _cuts_to_boxes(width: int, height: int, cuts: list[int]) -> list[CropBox]:
    bounds = [0] + sorted(cuts) + [height]
    return [CropBox(0, bounds[i], width, bounds[i + 1]) for i in range(len(bounds) - 1)]
