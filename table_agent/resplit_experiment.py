"""Offline re-split smoke experiments for third-stage optimization."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.config import AgentConfig
from table_agent.mineru_client import MinerUTableClient
from table_agent.otsl import merge_vertical_otsl, split_otsl_rows
from table_agent.recognition import recognize_crop
from table_agent.split_review import (
    _extract_content,
    _normalize_split_decision,
    _parse_review_json,
    _validate_cuts,
)
from table_agent.client import VisionClient
from table_agent.splitter import _choose_safe_cuts, _cuts_to_boxes, save_crops


STRATEGIES = (
    "shift_cuts",
    "chunk_count",
    "header_overlap",
    "header_repeat",
    "qwen_header",
)


def run_resplit_smoke(
    config: AgentConfig,
    *,
    run_jsonl: str | Path,
    diagnostics_json: str | Path | None = None,
    indices: list[int] | None = None,
    strategies: list[str] | None = None,
    output_dir: str | Path = "outputs/resplit_smoke",
    shift_px: int = 48,
    header_overlap_px: int = 96,
) -> dict[str, Any]:
    selected_strategies = strategies or list(STRATEGIES)
    _validate_strategies(selected_strategies)
    selected_indices = indices or _candidate_regression_indices(diagnostics_json)
    if not selected_indices:
        raise ValueError("No smoke indices provided or found in diagnostics JSON")

    records = _load_records(config, selected_indices)
    run_rows = _load_run_rows(run_jsonl)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(config.paths.raw_response_dir) / "resplit_smoke"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = MinerUTableClient(config.mineru)

    summary = {
        "indices": selected_indices,
        "strategies": selected_strategies,
        "outputs": {},
        "shift_px": shift_px,
        "header_overlap_px": header_overlap_px,
    }

    for strategy in selected_strategies:
        strategy_rows = []
        strategy_started = time.perf_counter()
        mineru_calls = 0
        qwen_calls = 0
        strategy_raw_dir = raw_dir / strategy
        strategy_raw_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = output_path / f"{strategy}.jsonl"

        with jsonl_path.open("w", encoding="utf-8") as f:
            for record_index in selected_indices:
                record = dict(records[record_index])
                image_path = resolve_image_path(record, config.paths.image_dir)
                original_metadata = (run_rows[record_index].get("agent_metadata") or {})
                original_cuts = _original_cuts(original_metadata)
                started = time.perf_counter()
                plan = _build_strategy_plan(
                    config,
                    strategy,
                    image_path,
                    original_metadata,
                    original_cuts,
                    shift_px=shift_px,
                    header_overlap_px=header_overlap_px,
                )
                qwen_calls += int(plan.get("extra_qwen_calls", 0))
                stem = f"resplit_{strategy}_{record_index:05d}_{Path(image_path).stem}"
                header_probe = None
                header_row_count = 0
                if strategy == "header_repeat":
                    header_probe = _save_header_probe_crop(
                        image_path, plan, config.paths.crop_dir, stem=stem
                    )
                    header_raw_path = strategy_raw_dir / f"{record_index:05d}_header.json"
                    header_recognition = recognize_crop(
                        client,
                        header_probe["crop_path"],
                        raw_path=header_raw_path,
                        max_retries=config.max_recognition_retries,
                    )
                    mineru_calls += 1 + int(header_recognition.get("retry_count", 0) or 0)
                    header_probe.update(header_recognition)
                    header_row_count = _header_row_count(
                        str(header_recognition.get("otsl", "") or ""),
                        int(plan.get("estimated_header_row_count", 1) or 1),
                    )
                    chunks = _save_header_repeat_crops(
                        image_path, plan, config.paths.crop_dir, stem=stem
                    )
                else:
                    chunks = save_crops(
                        image_path, plan["boxes"], config.paths.crop_dir, stem=stem
                    )

                for chunk in chunks:
                    raw_path = strategy_raw_dir / f"{record_index:05d}_{chunk['index']:02d}.json"
                    recognition = recognize_crop(
                        client,
                        chunk["crop_path"],
                        raw_path=raw_path,
                        max_retries=config.max_recognition_retries,
                    )
                    mineru_calls += 1 + int(recognition.get("retry_count", 0) or 0)
                    chunk.update(recognition)

                if strategy == "header_repeat":
                    _strip_repeated_header_rows(chunks, header_row_count)

                merged = merge_vertical_otsl(
                    [str(chunk.get("otsl", "") or "") for chunk in chunks]
                )
                for chunk, row_count, col_count in zip(
                    chunks, merged["crop_row_counts"], merged["crop_col_counts"]
                ):
                    chunk["row_count"] = row_count
                    chunk["estimated_col_count"] = col_count

                status = _sample_status(chunks)
                elapsed = time.perf_counter() - started
                row = dict(record)
                row["agent_parse_result"] = {
                    "status": status,
                    "otsl": merged["otsl"],
                    "html": merged["html"],
                }
                row["agent_metadata"] = {
                    "experiment": "third_stage_resplit_smoke",
                    "strategy": strategy,
                    "image_path": str(image_path),
                    "original_cuts": original_cuts,
                    "strategy_cuts": plan["cuts"],
                    "strategy_boxes": plan["boxes"],
                    "split_decision": plan.get("split_decision", {}),
                    "header_band": plan.get("header_band", {}),
                    "header_probe": header_probe,
                    "header_row_count": header_row_count,
                    "chunks": chunks,
                    "warnings": list(plan.get("warnings", [])) + merged["warnings"],
                    "extra_mineru_calls": len(chunks) + (1 if header_probe else 0),
                    "extra_qwen_calls": int(plan.get("extra_qwen_calls", 0)),
                    "elapsed_seconds": elapsed,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                strategy_rows.append(row)

        summary["outputs"][strategy] = {
            "jsonl": str(jsonl_path),
            "case_count": len(strategy_rows),
            "extra_mineru_calls": mineru_calls,
            "extra_qwen_calls": qwen_calls,
            "elapsed_seconds": time.perf_counter() - strategy_started,
            "avg_elapsed_seconds": (
                (time.perf_counter() - strategy_started) / len(strategy_rows)
                if strategy_rows
                else 0.0
            ),
        }

    summary_path = output_path / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    summary["summary_json"] = str(summary_path)
    return summary


def _build_strategy_plan(
    config: AgentConfig,
    strategy: str,
    image_path: Path,
    original_metadata: dict[str, Any],
    original_cuts: list[int],
    *,
    shift_px: int,
    header_overlap_px: int,
) -> dict[str, Any]:
    width, height = Image.open(image_path).size
    if strategy == "shift_cuts":
        cuts = _shift_cuts(original_cuts, height, shift_px)
        boxes = [box.to_list() for box in _cuts_to_boxes(width, height, cuts)]
        return {
            "cuts": cuts,
            "boxes": boxes,
            "split_decision": {"strategy": strategy, "shift_px": shift_px},
            "warnings": [],
            "extra_qwen_calls": 0,
        }
    if strategy == "chunk_count":
        original_chunks = max(1, len(original_cuts) + 1)
        chunk_count = min(config.max_chunks, max(original_chunks + 1, 2))
        cuts = _choose_safe_cuts(Image.open(image_path).convert("RGB"), chunk_count)
        boxes = [box.to_list() for box in _cuts_to_boxes(width, height, cuts)]
        return {
            "cuts": cuts,
            "boxes": boxes,
            "split_decision": {"strategy": strategy, "chunk_count": chunk_count},
            "warnings": [],
            "extra_qwen_calls": 0,
        }
    if strategy == "header_overlap":
        cuts = original_cuts
        boxes = _overlap_boxes(width, height, cuts, header_overlap_px)
        return {
            "cuts": cuts,
            "boxes": boxes,
            "split_decision": {
                "strategy": strategy,
                "header_overlap_px": header_overlap_px,
            },
            "warnings": [],
            "extra_qwen_calls": 0,
        }
    if strategy == "header_repeat":
        cuts = original_cuts
        boxes = [box.to_list() for box in _cuts_to_boxes(width, height, cuts)]
        header_bottom = _detect_header_bottom(image_path, cuts, height)
        return {
            "cuts": cuts,
            "boxes": boxes,
            "header_band": {"box": [0, 0, width, header_bottom]},
            "estimated_header_row_count": max(1, min(4, round(header_bottom / 44))),
            "split_decision": {
                "strategy": strategy,
                "header_bottom": header_bottom,
                "header_repeat": True,
                "strip_repeated_header_rows": True,
            },
            "warnings": [],
            "extra_qwen_calls": 0,
        }
    if strategy == "qwen_header":
        return _qwen_header_plan(config, image_path, width, height, original_metadata)
    raise ValueError(f"Unknown strategy: {strategy}")


def _detect_header_bottom(image_path: Path, cuts: list[int], height: int) -> int:
    first_body_limit = cuts[0] if cuts else height
    search_high = min(first_body_limit - 24, max(96, int(height * 0.28)), 420)
    if search_high <= 72:
        return max(48, min(first_body_limit, height, 96))

    image = Image.open(image_path).convert("L")
    gray = np.asarray(image, dtype=np.float32) / 255.0
    ink_density = 1.0 - gray.mean(axis=1)
    smooth = _smooth_1d(ink_density, radius=8)
    low = min(72, search_high - 1)
    candidates = range(low, search_high)
    best = min(candidates, key=lambda y: (smooth[y], -y))
    return int(max(48, min(best, first_body_limit - 8, height)))


def _smooth_1d(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values
    kernel = np.ones(radius * 2 + 1, dtype=np.float32)
    kernel /= kernel.sum()
    return np.convolve(values, kernel, mode="same")


def _save_header_probe_crop(
    image_path: str | Path, plan: dict[str, Any], output_dir: str | Path, *, stem: str
) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    header_box = plan["header_band"]["box"]
    crop_path = out_dir / f"{stem}.header.jpg"
    image.crop(tuple(header_box)).save(crop_path, quality=95)
    return {
        "index": "header",
        "box": header_box,
        "crop_path": str(crop_path),
        "status": "pending",
    }


def _save_header_repeat_crops(
    image_path: str | Path, plan: dict[str, Any], output_dir: str | Path, *, stem: str
) -> list[dict[str, Any]]:
    image = Image.open(image_path).convert("RGB")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    header_box = plan["header_band"]["box"]
    header = image.crop(tuple(header_box))
    chunks = []
    for index, body_box in enumerate(plan["boxes"]):
        if index == 0:
            crop = image.crop(tuple(body_box))
            synthetic_header = False
        else:
            body = image.crop(tuple(body_box))
            crop = Image.new("RGB", (image.width, header.height + body.height), "white")
            crop.paste(header, (0, 0))
            crop.paste(body, (0, header.height))
            synthetic_header = True
        crop_path = out_dir / f"{stem}.crop-{index:02d}.jpg"
        crop.save(crop_path, quality=95)
        chunks.append(
            {
                "index": index,
                "box": [0, 0, crop.width, crop.height] if synthetic_header else body_box,
                "body_box": body_box,
                "header_box": header_box if synthetic_header else None,
                "synthetic_header_repeated": synthetic_header,
                "crop_path": str(crop_path),
                "status": "pending",
            }
        )
    return chunks


def _header_row_count(header_otsl: str, fallback: int) -> int:
    rows = split_otsl_rows(header_otsl)
    if rows:
        return max(1, min(6, len(rows)))
    return max(1, min(6, fallback))


def _strip_repeated_header_rows(
    chunks: list[dict[str, Any]], header_row_count: int
) -> None:
    for chunk in chunks:
        if not chunk.get("synthetic_header_repeated"):
            chunk["removed_header_rows"] = 0
            continue
        rows = split_otsl_rows(str(chunk.get("otsl", "") or ""))
        remove_count = min(header_row_count, max(0, len(rows) - 1))
        if remove_count <= 0:
            chunk["removed_header_rows"] = 0
            continue
        chunk["otsl_before_header_strip"] = chunk.get("otsl", "")
        chunk["removed_header_rows"] = remove_count
        chunk["removed_header_otsl_rows"] = rows[:remove_count]
        chunk["otsl"] = "".join(rows[remove_count:])


def _qwen_header_plan(
    config: AgentConfig,
    image_path: Path,
    width: int,
    height: int,
    original_metadata: dict[str, Any],
) -> dict[str, Any]:
    original_decision = original_metadata.get("split_decision") or {}
    original_cuts = _original_cuts(original_metadata)
    prompt = (
        "You are reviewing vertical split cuts for a table recognition retry. "
        "Prefer cuts that preserve header context and avoid splitting through repeated "
        "headers, section labels, totals, footnotes, or merged cells. If the current "
        "cut would make lower chunks lose necessary header context, move it to a safer "
        "nearby whitespace band or return no split. Do not use ground truth or scores. "
        'Return only JSON: {"accepted": true/false, "should_split": true/false, '
        '"complexity": "low/medium/high", "risk_factors": ["header risk"], '
        '"cuts": [integer_y_values], "reason": "short"}. '
        f"Image size width={width}, height={height}. Current cuts: {original_cuts}. "
        f"Current split decision: {json.dumps(original_decision, ensure_ascii=False)}"
    )
    warnings: list[str] = []
    try:
        raw = VisionClient(config.qwen).chat_with_image(image_path, prompt, max_tokens=384)
        parsed = _parse_review_json(_extract_content(raw))
        cuts = _validate_cuts(parsed.get("cuts", original_cuts), height, config.max_chunks)
        split_decision = _normalize_split_decision(parsed, cuts)
        if not split_decision["should_split"]:
            cuts = []
        boxes = [box.to_list() for box in _cuts_to_boxes(width, height, cuts)]
        return {
            "cuts": cuts,
            "boxes": boxes,
            "split_decision": split_decision,
            "warnings": warnings,
            "extra_qwen_calls": 1,
        }
    except Exception as exc:
        warnings.append(f"qwen_header_failed:{type(exc).__name__}:{exc}")
        boxes = [box.to_list() for box in _cuts_to_boxes(width, height, original_cuts)]
        return {
            "cuts": original_cuts,
            "boxes": boxes,
            "split_decision": {"strategy": "qwen_header", "fallback": "original_cuts"},
            "warnings": warnings,
            "extra_qwen_calls": 1,
        }


def _candidate_regression_indices(diagnostics_json: str | Path | None) -> list[int]:
    if diagnostics_json is None:
        return []
    report = json.loads(Path(diagnostics_json).read_text(encoding="utf-8"))
    summary = report.get("candidate_summary") or {}
    fallback = summary.get("fallback_candidate_regressions") or {}
    retry = summary.get("retry_candidate_regressions") or {}
    return [int(index) for index in (fallback.get("indices") or retry.get("indices") or [])]


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


def _load_run_rows(run_jsonl: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(run_jsonl).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _original_cuts(metadata: dict[str, Any]) -> list[int]:
    decision = metadata.get("split_decision") or {}
    cuts = decision.get("cuts") or []
    if cuts:
        return [int(cut) for cut in cuts]
    chunks = metadata.get("chunks") or []
    if len(chunks) <= 1:
        return []
    return [int(chunk["box"][3]) for chunk in chunks[:-1] if chunk.get("box")]


def _shift_cuts(cuts: list[int], height: int, shift_px: int) -> list[int]:
    shifted = []
    for cut in cuts:
        value = cut + shift_px
        if not 8 < value < height - 8:
            value = cut - shift_px
        if 8 < value < height - 8:
            shifted.append(value)
    return sorted(set(shifted))


def _overlap_boxes(
    width: int, height: int, cuts: list[int], header_overlap_px: int
) -> list[list[int]]:
    bounds = [0] + sorted(cuts) + [height]
    boxes = []
    for index in range(len(bounds) - 1):
        top = bounds[index]
        if index > 0:
            top = max(0, top - header_overlap_px)
        boxes.append([0, top, width, bounds[index + 1]])
    return boxes


def _sample_status(chunks: list[dict[str, Any]]) -> str:
    statuses = [chunk.get("status") for chunk in chunks]
    if statuses and all(status == "success" for status in statuses):
        return "success"
    if any(status == "success" for status in statuses):
        return "partial_success"
    return "failed"


def _validate_strategies(strategies: list[str]) -> None:
    invalid = sorted(set(strategies) - set(STRATEGIES))
    if invalid:
        allowed = ", ".join(STRATEGIES)
        raise ValueError(f"Unknown strategies {invalid}; allowed: {allowed}")
