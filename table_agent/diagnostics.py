"""Offline diagnostics for scored Table Agent runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RETRY_WARNING_TAGS = {
    "column_count_inconsistent",
    "empty_crop_otsl",
    "illegal_otsl_tokens",
    "repaired_stray_otsl_angle",
    "review_cuts_rejected_tiny_chunks",
}
FALLBACK_WARNING_TAGS = {
    "empty_crop_otsl",
    "illegal_otsl_tokens",
}
FAILED_STATUSES = {"failed", "partial_success", "error", "timeout"}


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
        "candidate_rule_notes": [
            "retry/fallback candidate labels use only runtime-observable metadata",
            "TEDS/GT-derived scores are included only for offline attribution",
            "runtime pipeline behavior is unchanged by this diagnostic report",
        ],
        "candidate_summary": _candidate_summary(cases),
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
    split_decision = metadata.get("split_decision") or {}
    warning_tags = [_warning_tag(warning) for warning in warnings]
    agent_status = (run_row.get("agent_parse_result") or {}).get("status", "failed")
    crop_estimates = [
        {
            "index": _safe_int(chunk.get("index")),
            "row_count": _safe_int(chunk.get("row_count")),
            "estimated_col_count": _safe_int(chunk.get("estimated_col_count")),
            "status": str(chunk.get("status", "unknown")),
        }
        for chunk in chunks
    ]
    signal_context = {
        "agent_status": agent_status,
        "chunk_count": len(chunks),
        "split_iterations": _safe_int(metadata.get("split_iterations")),
        "warning_tags": warning_tags,
        "crop_row_counts": crop_row_counts,
        "crop_col_counts": crop_col_counts,
        "chunk_statuses": chunk_statuses,
        "split_decision": split_decision,
    }
    retry_reasons = _retry_candidate_reasons(signal_context)
    fallback_reasons = _fallback_candidate_reasons(signal_context, retry_reasons)

    return {
        "index": index,
        "image": run_row.get("image", ""),
        "baseline_teds": baseline_teds,
        "agent_teds": agent_teds,
        "delta_teds": agent_teds - baseline_teds,
        "agent_status": agent_status,
        "chunk_count": len(chunks),
        "split_iterations": _safe_int(metadata.get("split_iterations")),
        "warnings": warnings,
        "warning_tags": warning_tags,
        "split_decision": _compact_split_decision(split_decision),
        "crop_estimates": crop_estimates,
        "crop_row_counts": crop_row_counts,
        "crop_col_counts": crop_col_counts,
        "chunk_statuses": chunk_statuses,
        "runtime_signals": _runtime_signal_summary(signal_context),
        "retry_candidate": bool(retry_reasons),
        "retry_candidate_reasons": retry_reasons,
        "fallback_candidate": bool(fallback_reasons),
        "fallback_candidate_reasons": fallback_reasons,
        "image_size": metadata.get("image_size", []),
    }


def _retry_candidate_reasons(context: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    warning_tags = set(context["warning_tags"])
    chunk_statuses = [str(status) for status in context["chunk_statuses"]]
    chunk_count = int(context["chunk_count"])
    col_spread = _spread(context["crop_col_counts"])
    split_decision = context["split_decision"] or {}
    risk_factors = [str(risk).lower() for risk in split_decision.get("risk_factors", [])]

    for tag in sorted(warning_tags & RETRY_WARNING_TAGS):
        reasons.append(f"warning:{tag}")
    if str(context["agent_status"]) in FAILED_STATUSES:
        reasons.append(f"agent_status:{context['agent_status']}")
    if any(status != "success" for status in chunk_statuses):
        reasons.append("crop_status_not_success")
    if chunk_count > 1 and col_spread >= 2:
        reasons.append(f"crop_col_count_spread:{col_spread}")
    if chunk_count > 2:
        reasons.append(f"many_chunks:{chunk_count}")
    if _has_high_risk_factor(risk_factors):
        reasons.append("split_review_high_risk")

    return _dedupe(reasons)


def _fallback_candidate_reasons(
    context: dict[str, Any], retry_reasons: list[str]
) -> list[str]:
    reasons: list[str] = []
    warning_tags = set(context["warning_tags"])
    col_spread = _spread(context["crop_col_counts"])

    for tag in sorted(warning_tags & FALLBACK_WARNING_TAGS):
        reasons.append(f"warning:{tag}")
    if str(context["agent_status"]) in FAILED_STATUSES:
        reasons.append(f"agent_status:{context['agent_status']}")
    if any(str(status) != "success" for status in context["chunk_statuses"]):
        reasons.append("crop_status_not_success")
    if "warning:column_count_inconsistent" in retry_reasons and col_spread >= 4:
        reasons.append(f"severe_col_count_spread:{col_spread}")

    return _dedupe(reasons)


def _compact_split_decision(split_decision: dict[str, Any]) -> dict[str, Any]:
    if not split_decision:
        return {}
    return {
        "should_split": bool(split_decision.get("should_split", False)),
        "complexity": split_decision.get("complexity", "unknown"),
        "risk_factors": split_decision.get("risk_factors", []),
        "cuts": split_decision.get("cuts", []),
        "reason": split_decision.get("reason", ""),
    }


def _runtime_signal_summary(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "col_count_spread": _spread(context["crop_col_counts"]),
        "row_count_spread": _spread(context["crop_row_counts"]),
        "non_success_chunk_count": len(
            [status for status in context["chunk_statuses"] if status != "success"]
        ),
    }


def _has_high_risk_factor(risk_factors: list[str]) -> bool:
    high_risk_terms = ("risk high", "high risk", "unsafe", "uncertain", "ambiguous")
    return any(any(term in risk for term in high_risk_terms) for risk in risk_factors)


def _candidate_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    retry_cases = [case for case in cases if case["retry_candidate"]]
    fallback_cases = [case for case in cases if case["fallback_candidate"]]
    return {
        "retry_candidates": _summary_for(retry_cases),
        "fallback_candidates": _summary_for(fallback_cases),
        "retry_candidate_reasons": _reason_group(cases, "retry_candidate_reasons"),
        "fallback_candidate_reasons": _reason_group(
            cases, "fallback_candidate_reasons"
        ),
        "retry_candidate_regressions": _summary_for(
            case for case in retry_cases if case["delta_teds"] < 0
        ),
        "fallback_candidate_regressions": _summary_for(
            case for case in fallback_cases if case["delta_teds"] < 0
        ),
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


def _reason_group(cases: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        for reason in case.get(key, []):
            counter[reason] += 1
            grouped[reason].append(case)
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


def _spread(values: list[int]) -> int:
    return max(values) - min(values) if values else 0


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


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
