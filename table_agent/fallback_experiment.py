"""Offline full-image fallback counterfactual experiments."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from table_agent.baseline import _write_json
from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.config import AgentConfig
from table_agent.mineru_client import MinerUTableClient
from table_agent.otsl import otsl_to_html_when_possible


def run_fallback_smoke(
    config: AgentConfig,
    *,
    diagnostics_json: str | Path | None = None,
    indices: list[int] | None = None,
    output_jsonl: str | Path = "outputs/fallback_smoke/fallback.jsonl",
) -> dict[str, Any]:
    selected_indices = indices or _fallback_candidate_indices(diagnostics_json)
    if not selected_indices:
        raise ValueError("No fallback indices provided or found in diagnostics JSON")

    records = _load_records(config, selected_indices)
    output_path = Path(output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(config.paths.raw_response_dir) / "fallback_smoke"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = MinerUTableClient(config.mineru)

    total_started = time.perf_counter()
    rows = []
    with output_path.open("w", encoding="utf-8") as f:
        for record_index in selected_indices:
            record = dict(records[record_index])
            image_path = resolve_image_path(record, config.paths.image_dir)
            raw_path = raw_dir / f"{record_index:05d}.json"
            started = time.perf_counter()
            raw = client.recognize_table(image_path)
            _write_json(raw_path, raw)
            otsl = str(raw.get("otsl", "") or "")
            html = raw.get("html") or otsl_to_html_when_possible(otsl)
            status = "success" if otsl else "failed"
            elapsed = time.perf_counter() - started

            row = dict(record)
            row["agent_parse_result"] = {
                "status": status,
                "otsl": otsl,
                "html": html,
                "raw_response": {"path": str(raw_path)},
            }
            row["agent_metadata"] = {
                "experiment": "third_stage_fallback_smoke",
                "selected_result_source": "agent_full_image_fallback",
                "fallback_triggered": True,
                "fallback_reason": "offline_counterfactual_candidate",
                "fallback_raw_response": {"path": str(raw_path)},
                "extra_mineru_calls": 1,
                "extra_qwen_calls": 0,
                "elapsed_seconds": elapsed,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)

    elapsed_total = time.perf_counter() - total_started
    summary = {
        "output_jsonl": str(output_path),
        "indices": selected_indices,
        "case_count": len(rows),
        "extra_mineru_calls": len(rows),
        "extra_qwen_calls": 0,
        "elapsed_seconds": elapsed_total,
        "avg_elapsed_seconds": elapsed_total / len(rows) if rows else 0.0,
    }
    summary_path = output_path.with_suffix(".summary.json")
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    summary["summary_json"] = str(summary_path)
    return summary


def _fallback_candidate_indices(diagnostics_json: str | Path | None) -> list[int]:
    if diagnostics_json is None:
        return []
    report = json.loads(Path(diagnostics_json).read_text(encoding="utf-8"))
    summary = report.get("candidate_summary") or {}
    fallback = summary.get("fallback_candidate_regressions") or {}
    return [int(index) for index in fallback.get("indices", [])]


def _load_records(config: AgentConfig, indices: list[int]) -> dict[int, dict[str, Any]]:
    wanted = set(indices)
    records = {}
    for index, record in iter_benchmark_records(config.paths.input_jsonl):
        if index in wanted:
            records[index] = record
        if len(records) == len(wanted):
            break
    missing = sorted(wanted - set(records))
    if missing:
        raise ValueError(f"Benchmark indices not found: {missing}")
    return records
