"""Evaluation summary helpers for scored Table Agent runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summarize_evaluation(
    run_jsonl: str | Path,
    baseline_scored_jsonl: str | Path,
    agent_scored_jsonl: str | Path,
    output_json: str | Path,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    run_rows = _read_jsonl_rows(Path(run_jsonl), skip_summary=False)
    baseline_rows = _read_jsonl_rows(Path(baseline_scored_jsonl), skip_summary=True)
    agent_rows = _read_jsonl_rows(Path(agent_scored_jsonl), skip_summary=True)
    count = min(len(run_rows), len(baseline_rows), len(agent_rows))

    paired = []
    for idx in range(count):
        run_row = run_rows[idx]
        baseline_row = baseline_rows[idx]
        agent_row = agent_rows[idx]
        baseline_teds = float(baseline_row.get("baseline_parse_result-teds", 0.0) or 0.0)
        agent_teds = float(agent_row.get("agent_parse_result-teds", 0.0) or 0.0)
        metadata = run_row.get("agent_metadata") or {}
        paired.append(
            {
                "index": idx,
                "image": run_row.get("image", ""),
                "baseline_teds": baseline_teds,
                "agent_teds": agent_teds,
                "delta_teds": agent_teds - baseline_teds,
                "agent_status": (run_row.get("agent_parse_result") or {}).get("status", "failed"),
                "chunk_count": len(metadata.get("chunks", [])),
                "split_iterations": int(metadata.get("split_iterations", 0) or 0),
                "warnings": metadata.get("warnings", []),
            }
        )

    status_counts = {"success": 0, "partial_success": 0, "failed": 0}
    for item in paired:
        status = str(item["agent_status"])
        status_counts[status if status in status_counts else "failed"] += 1

    baseline_avg = _average(item["baseline_teds"] for item in paired)
    agent_avg = _average(item["agent_teds"] for item in paired)
    absolute_improvement = agent_avg - baseline_avg
    relative_improvement = absolute_improvement / baseline_avg if baseline_avg else 0.0

    summary = {
        "count": count,
        "run_jsonl": str(Path(run_jsonl)),
        "baseline_scored_jsonl": str(Path(baseline_scored_jsonl)),
        "agent_scored_jsonl": str(Path(agent_scored_jsonl)),
        "baseline_avg_teds": baseline_avg,
        "agent_avg_teds": agent_avg,
        "absolute_improvement": absolute_improvement,
        "relative_improvement": relative_improvement,
        "success_count": status_counts["success"],
        "partial_success_count": status_counts["partial_success"],
        "failure_count": status_counts["failed"],
        "avg_chunk_count": _average(item["chunk_count"] for item in paired),
        "avg_split_iterations": _average(item["split_iterations"] for item in paired),
        "most_improved": sorted(paired, key=lambda item: item["delta_teds"], reverse=True)[:top_k],
        "most_regressed": sorted(paired, key=lambda item: item["delta_teds"])[:top_k],
    }

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return summary


def _read_jsonl_rows(path: Path, *, skip_summary: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            if skip_summary and "__summary__" in row:
                continue
            rows.append(row)
    return rows


def _average(values: Any) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0
