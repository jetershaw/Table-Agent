"""Crop-level MinerU recognition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from table_agent.baseline import _write_json
from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.mineru_client import MinerUTableClient
from table_agent.config import AgentConfig
from table_agent.split_review import review_split_candidates
from table_agent.splitter import propose_vertical_crops, save_crops


def recognize_crop(
    client: MinerUTableClient,
    crop_path: str | Path,
    *,
    raw_path: str | Path,
    max_retries: int,
) -> dict[str, Any]:
    attempts = 0
    last_error = ""
    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        try:
            raw = client.recognize_table(crop_path)
            _write_json(Path(raw_path), raw)
            otsl = str(raw.get("otsl", "") or "")
            return {
                "status": "success" if otsl else "failed",
                "otsl": otsl,
                "raw_response": {"path": str(raw_path)},
                "retry_count": attempt,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    return {
        "status": "failed",
        "otsl": "",
        "raw_response": {},
        "retry_count": max(0, attempts - 1),
        "error": last_error,
    }


def run_crop_recognition(
    config: AgentConfig,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
    output_json: str | None = None,
) -> dict[str, Any]:
    raw_dir = Path(config.paths.raw_response_dir) / "crops"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = MinerUTableClient(config.mineru)
    results = []

    for record_index, record in iter_benchmark_records(
        config.paths.input_jsonl, start=start, end=end, limit=limit
    ):
        image_path = resolve_image_path(record, config.paths.image_dir)
        proposed = propose_vertical_crops(image_path, max_chunks=config.max_chunks)
        metadata = review_split_candidates(config, image_path, proposed)
        stem = f"recognize_{record_index:05d}_{Path(image_path).stem}"
        chunks = save_crops(image_path, metadata["boxes"], config.paths.crop_dir, stem=stem)
        for chunk in chunks:
            raw_path = raw_dir / f"{record_index:05d}_{chunk['index']:02d}.json"
            recognition = recognize_crop(
                client,
                chunk["crop_path"],
                raw_path=raw_path,
                max_retries=config.max_recognition_retries,
            )
            chunk.update(recognition)
        metadata["chunks"] = chunks
        metadata["max_recognition_retries"] = config.max_recognition_retries
        metadata["status"] = _sample_status(chunks)
        results.append(metadata)

    output_path = Path(output_json or "outputs/crop_recognition_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"output_json": str(output_path), "total": len(results)}


def _sample_status(chunks: list[dict[str, Any]]) -> str:
    statuses = [chunk.get("status") for chunk in chunks]
    if statuses and all(status == "success" for status in statuses):
        return "success"
    if any(status == "success" for status in statuses):
        return "partial_success"
    return "failed"
