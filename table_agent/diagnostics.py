"""Offline diagnostics for scored Table Agent runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def diagnose_run(
    run_jsonl: str | Path,
    baseline_scored_jsonl: str | Path,
    agent_scored_jsonl: str | Path,
    output_json: str | Path,
    *,
    top_k: int = 8,
) -> dict[str, Any]:
    run_rows = _read_jsonl_rows(Path(run_jsonl), skip_summary=False)
    baseline_rows = _read_jsonl_rows(Path(baseline_scored_jsonl), skip_summary=True)
    agent_rows = _read_jsonl_rows(Path(agent_scored_jsonl), skip_summary=True)
    count = min(len(run_rows), len(baseline_rows), len(agent_rows))

    cases = [
        _build_case(index, run_rows[index], baseline_rows[index], agent_rows[index])
        for index in range(count)
    ]
    regressions = [case for case in cases if case["delta_teds"] < 0]

    report = {
        "count": count,
        "run_jsonl": str(Path(run_jsonl)),
        "baseline_scored_jsonl": str(Path(baseline_scored_jsonl)),
        "agent_scored_jsonl": str(Path(agent_scored_jsonl)),
        "baseline_avg_teds": _average(case["baseline_teds"] for case in cases),
        "agent_avg_teds": _average(case["agent_teds"] for case in cases),
        "regression_count": len(regressions),
        "improvement_count": len([case for case in cases if case["delta_teds"] > 0]),
        "unchanged_count": len([case for case in cases if case["delta_teds"] == 0]),
        "worst_regressions": sorted(cases, key=lambda case: case["delta_teds"])[:top_k],
        "largest_improvements": sorted(
            cases, key=lambda case: case["delta_teds"], reverse=True
        )[:top_k],
        "regression_groups": _regression_groups(regressions),
        "cases": cases,
    }

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return report


def _build_case(
    index: int,
    run_row: dict[str, Any],
    baseline_row: dict[str, Any],
    agent_row: dict[str, Any],
) -> dict[str, Any]:
    baseline_teds = float(baseline_row.get("baseline_parse_result-teds", 0.0) or 0.0)
    agent_teds = float(agent_row.get("agent_parse_result-teds", 0.0) or 0.0)
    metadata = run_row.get("agent_metadata") or {}
    chunks = metadata.get("chunks") or []
    warnings = [str(warning) for warning in metadata.get("warnings", [])]

    crop_row_counts = [_safe_int(chunk.get("row_count")) for chunk in chunks]
    crop_col_counts = [_safe_int(chunk.get("estimated_col_count")) for chunk in chunks]
    chunk_statuses = [str(chunk.get("status", "unknown")) for chunk in chunks]

    return {
        "index": index,
        "image": run_row.get("image", ""),
        "baseline_teds": baseline_teds,
        "agent_teds": agent_teds,
        "delta_teds": agent_teds - baseline_teds,
        "agent_status": (run_row.get("agent_parse_result") or {}).get(
            "status", "failed"
        ),
        "chunk_count": len(chunks),
        "split_iterations": _safe_int(metadata.get("split_iterations")),
        "warnings": warnings,
        "warning_tags": [_warning_tag(warning) for warning in warnings],
        "crop_row_counts": crop_row_counts,
        "crop_col_counts": crop_col_counts,
        "chunk_statuses": chunk_statuses,
        "image_size": metadata.get("image_size", []),
    }


def _regression_groups(regressions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "by_chunk_count": _counter_group(regressions, "chunk_count"),
        "by_agent_status": _counter_group(regressions, "agent_status"),
        "by_split_iterations": _counter_group(regressions, "split_iterations"),
        "by_warning_tag": _warning_group(regressions),
        "single_chunk": _summary_for(
            case for case in regressions if case["chunk_count"] == 1
        ),
        "multi_chunk": _summary_for(
            case for case in regressions if case["chunk_count"] > 1
        ),
        "with_warnings": _summary_for(case for case in regressions if case["warnings"]),
        "without_warnings": _summary_for(
            case for case in regressions if not case["warnings"]
        ),
        "column_count_inconsistent": _summary_for(
            case
            for case in regressions
            if "column_count_inconsistent" in case["warning_tags"]
        ),
        "illegal_otsl_tokens": _summary_for(
            case for case in regressions if "illegal_otsl_tokens" in case["warning_tags"]
        ),
    }


def _counter_group(cases: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        groups[str(case.get(key, ""))].append(case)
    return [_named_summary(name, items) for name, items in sorted(groups.items())]


def _warning_group(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        tags = case["warning_tags"] or ["none"]
        for tag in tags:
            counter[tag] += 1
            grouped[tag].append(case)
    return [_named_summary(name, grouped[name]) for name, _ in counter.most_common()]


def _named_summary(name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _summary_for(cases)
    summary["name"] = name
    return summary


def _summary_for(cases: Any) -> dict[str, Any]:
    items = list(cases)
    return {
        "count": len(items),
        "avg_delta_teds": _average(case["delta_teds"] for case in items),
        "min_delta_teds": min((case["delta_teds"] for case in items), default=0.0),
        "indices": [case["index"] for case in items],
    }


def _warning_tag(warning: str) -> str:
    return warning.split(":", 1)[0]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
