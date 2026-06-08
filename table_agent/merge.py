"""Merge crop recognition outputs into an agent parse result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from table_agent.otsl import merge_vertical_otsl


def merge_crop_recognition_output(input_json: str | Path, output_json: str | Path) -> dict[str, Any]:
    data = json.loads(Path(input_json).read_text(encoding="utf-8"))
    results = []
    for sample in data.get("results", []):
        chunks = sorted(sample.get("chunks", []), key=lambda item: int(item.get("index", 0)))
        crop_otsls = [str(chunk.get("otsl", "") or "") for chunk in chunks]
        merged = merge_vertical_otsl(crop_otsls)
        for chunk, row_count, col_count in zip(
            chunks, merged["crop_row_counts"], merged["crop_col_counts"]
        ):
            chunk["row_count"] = row_count
            chunk["estimated_col_count"] = col_count
        status = sample.get("status", "success")
        sample["agent_parse_result"] = {
            "status": status,
            "otsl": merged["otsl"],
            "html": merged["html"],
        }
        sample["warnings"] = list(sample.get("warnings", [])) + list(merged["warnings"])
        sample["chunks"] = chunks
        sample["row_count"] = merged["row_count"]
        sample["estimated_col_count"] = merged["estimated_col_count"]
        results.append(sample)

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"output_json": str(output_path), "total": len(results)}
