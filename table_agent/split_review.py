"""Qwen review and safe revision for vertical split candidates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.client import VisionClient
from table_agent.config import AgentConfig
from table_agent.splitter import propose_vertical_crops, save_crops


def review_split_candidates(
    config: AgentConfig,
    image_path: str | Path,
    proposed: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    current_cuts = [int(cut) for cut in proposed.get("cuts", [])]
    image_size = proposed.get("image_size", [0, 0])
    iterations = 0
    raw_responses = []
    split_decision = _default_split_decision(current_cuts)
    client = VisionClient(config.qwen)

    for iteration in range(config.max_split_iterations):
        iterations = iteration + 1
        prompt = _build_review_prompt(image_size, current_cuts, config.max_chunks)
        try:
            raw = client.chat_with_image(image_path, prompt, max_tokens=384)
            raw_responses.append(raw)
            content = _extract_content(raw)
            parsed = _parse_review_json(content)
            revised = _validate_cuts(
                parsed.get("cuts", current_cuts), int(image_size[1]), config.max_chunks
            )
            split_decision = _normalize_split_decision(parsed, revised)
            if not split_decision["should_split"]:
                current_cuts = []
                break
            accepted = bool(parsed.get("accepted", revised == current_cuts))
            if revised != current_cuts:
                current_cuts = revised
                continue
            if accepted:
                break
        except Exception as exc:
            warnings.append(f"split_review_failed: {type(exc).__name__}: {exc}")
            break
    else:
        warnings.append("max_split_iterations_reached")

    original_cuts = [int(cut) for cut in proposed.get("cuts", [])]
    if _has_tiny_chunks(int(image_size[1]), current_cuts):
        warnings.append("review_cuts_rejected_tiny_chunks")
        current_cuts = original_cuts
        split_decision = _default_split_decision(current_cuts)

    boxes = _cuts_to_boxes(int(image_size[0]), int(image_size[1]), current_cuts)
    return {
        "image_path": str(image_path),
        "image_size": image_size,
        "original_cuts": proposed.get("cuts", []),
        "cuts": current_cuts,
        "boxes": boxes,
        "split_decision": split_decision,
        "split_iterations": iterations,
        "max_split_iterations": config.max_split_iterations,
        "warnings": warnings,
        "raw_response_count": len(raw_responses),
    }


def run_split_review(
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
        proposed = propose_vertical_crops(image_path, max_chunks=config.max_chunks)
        reviewed = review_split_candidates(config, image_path, proposed)
        stem = f"review_{record_index:05d}_{Path(image_path).stem}"
        reviewed["chunks"] = save_crops(
            image_path, reviewed["boxes"], config.paths.crop_dir, stem=stem
        )
        results.append(reviewed)

    output_path = Path(output_json or "outputs/split_review_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"output_json": str(output_path), "total": len(results)}


def _build_review_prompt(image_size: list[int], cuts: list[int], max_chunks: int) -> str:
    width, height = image_size
    return (
        "You are deciding whether a full-width table image should be vertically split before table recognition. "
        "Use only the image and the proposed horizontal cuts; do not assume access to ground truth or scoring. "
        "Prefer no split for short, simple, or risky tables where cutting could remove context. "
        "Choose split only when the table is visually long or complex enough that chunk recognition is likely to help, and when each cut lies in a clear horizontal whitespace band between rows. "
        "A safe cut must not cross text, borders, formulas, row content, headers, footnotes, or merged cells. "
        "If a proposed cut is unsafe, move it only to the nearest visually safe whitespace band; if no safe nearby band is visible, remove that cut. "
        "Do not add new cuts unless the table has a very clear large whitespace band and the resulting chunk count stays within the limit. "
        'Return only JSON with this schema: {"accepted": true/false, "should_split": true/false, "complexity": "low/medium/high", "risk_factors": ["short strings"], "cuts": [integer_y_values], "reason": "short"}. '
        "If should_split=false, return an empty cuts list. "
        "Keep cuts sorted, unique, strictly between 0 and image height, and keep chunk count <= "
        f"{max_chunks}. Image size is width={width}, height={height}. Proposed cuts: {cuts}."
    )


def _extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return str(content or "")


def _parse_review_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in model response: {content[:200]}")
        text = match.group(0)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Review response must be a JSON object")
    return parsed


def _normalize_split_decision(parsed: dict[str, Any], cuts: list[int]) -> dict[str, Any]:
    should_split = parsed.get("should_split")
    if isinstance(should_split, bool):
        normalized_should_split = should_split and bool(cuts)
    else:
        normalized_should_split = bool(cuts)

    risk_factors = parsed.get("risk_factors", [])
    if not isinstance(risk_factors, list):
        risk_factors = [str(risk_factors)] if risk_factors else []

    complexity = str(parsed.get("complexity", "unknown") or "unknown").lower()
    if complexity not in {"low", "medium", "high", "unknown"}:
        complexity = "unknown"

    return {
        "should_split": normalized_should_split,
        "complexity": complexity,
        "risk_factors": [str(item) for item in risk_factors],
        "cuts": cuts if normalized_should_split else [],
        "reason": str(parsed.get("reason", "") or ""),
    }


def _default_split_decision(cuts: list[int]) -> dict[str, Any]:
    return {
        "should_split": bool(cuts),
        "complexity": "unknown",
        "risk_factors": [],
        "cuts": cuts,
        "reason": "default_from_cv_candidate",
    }


def _validate_cuts(cuts: Any, height: int, max_chunks: int) -> list[int]:
    if not isinstance(cuts, list):
        raise ValueError("cuts must be a list")
    candidates = []
    for cut in cuts:
        if isinstance(cut, bool):
            continue
        value = int(cut)
        if 0 < value < height:
            candidates.append(value)

    min_chunk_height = max(96, height // max(max_chunks, 1))
    valid = []
    previous = 0
    for value in sorted(set(candidates)):
        if value - previous < min_chunk_height:
            continue
        if height - value < min_chunk_height:
            continue
        valid.append(value)
        previous = value
        if len(valid) >= max(0, max_chunks - 1):
            break
    return valid


def _cuts_to_boxes(width: int, height: int, cuts: list[int]) -> list[list[int]]:
    bounds = [0] + sorted(cuts) + [height]
    return [[0, bounds[i], width, bounds[i + 1]] for i in range(len(bounds) - 1)]


def _has_tiny_chunks(height: int, cuts: list[int], min_height: int = 160) -> bool:
    bounds = [0] + sorted(cuts) + [height]
    return any((bounds[i + 1] - bounds[i]) < min_height for i in range(len(bounds) - 1))
