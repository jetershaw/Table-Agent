"""End-to-end Table Agent batch runner."""

from __future__ import annotations

import json
import signal
from pathlib import Path
from typing import Any

from table_agent.baseline import _write_json
from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.mineru_client import MinerUTableClient
from table_agent.config import AgentConfig
from table_agent.otsl import merge_vertical_otsl, otsl_to_html_when_possible
from table_agent.recognition import recognize_crop
from table_agent.split_review import review_split_candidates
from table_agent.splitter import propose_vertical_crops, save_crops


def run_end_to_end(
    config: AgentConfig,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
    output_jsonl: str | None = None,
    sample_timeout: int = 120,
) -> dict[str, Any]:
    output_path = Path(output_jsonl or config.paths.output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_raw_dir = Path(config.paths.raw_response_dir) / "e2e_baseline"
    crop_raw_dir = Path(config.paths.raw_response_dir) / "e2e_crops"
    baseline_raw_dir.mkdir(parents=True, exist_ok=True)
    crop_raw_dir.mkdir(parents=True, exist_ok=True)

    mineru_client = MinerUTableClient(config.mineru, timeout=60)
    total = 0
    success = 0
    partial_success = 0
    failed = 0

    with output_path.open("w", encoding="utf-8") as out:
        for record_index, record in iter_benchmark_records(
            config.paths.input_jsonl, start=start, end=end, limit=limit
        ):
            total += 1
            row = dict(record)
            try:
                with _timeout(sample_timeout):
                    image_path = resolve_image_path(record, config.paths.image_dir)
                    row["baseline_parse_result"] = _run_baseline(
                        mineru_client, image_path, baseline_raw_dir / f"{record_index:05d}.json"
                    )
                    metadata = _run_agent(config, mineru_client, image_path, record_index, crop_raw_dir)
                    row["agent_metadata"] = metadata
                    row["agent_parse_result"] = metadata.pop("agent_parse_result")
                    status = row["agent_parse_result"].get("status", "failed")
            except Exception as exc:
                status = "failed"
                row.setdefault(
                    "baseline_parse_result",
                    {"status": "failed", "otsl": "", "html": "", "raw_response": {}},
                )
                row["agent_parse_result"] = {"status": "failed", "otsl": "", "html": ""}
                row["agent_metadata"] = {
                    "warnings": [f"sample_failed: {type(exc).__name__}: {exc}"],
                    "chunks": [],
                }

            if status == "success":
                success += 1
            elif status == "partial_success":
                partial_success += 1
            else:
                failed += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()

    return {
        "output_jsonl": str(output_path),
        "total": total,
        "success": success,
        "partial_success": partial_success,
        "failed": failed,
        "sample_timeout": sample_timeout,
    }


def _run_baseline(client: MinerUTableClient, image_path: Path, raw_path: Path) -> dict[str, Any]:
    raw = client.recognize_table(image_path)
    _write_json(raw_path, raw)
    otsl = str(raw.get("otsl", "") or "")
    return {
        "status": "success" if otsl else "failed",
        "otsl": otsl,
        "html": raw.get("html") or otsl_to_html_when_possible(otsl),
        "raw_response": {"path": str(raw_path)},
    }


def _run_agent(
    config: AgentConfig,
    client: MinerUTableClient,
    image_path: Path,
    record_index: int,
    raw_dir: Path,
) -> dict[str, Any]:
    proposed = propose_vertical_crops(image_path, max_chunks=config.max_chunks)
    reviewed = review_split_candidates(config, image_path, proposed)
    stem = f"e2e_{record_index:05d}_{image_path.stem}"
    chunks = save_crops(image_path, reviewed["boxes"], config.paths.crop_dir, stem=stem)
    warnings = list(reviewed.get("warnings", []))

    for chunk in chunks:
        raw_path = raw_dir / f"{record_index:05d}_{chunk['index']:02d}.json"
        recognition = recognize_crop(
            client,
            chunk["crop_path"],
            raw_path=raw_path,
            max_retries=config.max_recognition_retries,
        )
        chunk.update(recognition)

    merged = merge_vertical_otsl([str(chunk.get("otsl", "") or "") for chunk in chunks])
    for chunk, row_count, col_count in zip(
        chunks, merged["crop_row_counts"], merged["crop_col_counts"]
    ):
        chunk["row_count"] = row_count
        chunk["estimated_col_count"] = col_count
    warnings.extend(merged["warnings"])
    status = _sample_status(chunks)

    return {
        "image_path": str(image_path),
        "image_size": reviewed.get("image_size", proposed.get("image_size", [])),
        "split_iterations": reviewed.get("split_iterations", 0),
        "max_split_iterations": config.max_split_iterations,
        "max_recognition_retries": config.max_recognition_retries,
        "max_chunks": config.max_chunks,
        "chunks": chunks,
        "warnings": warnings,
        "agent_parse_result": {
            "status": status,
            "otsl": merged["otsl"],
            "html": merged["html"],
        },
    }


def _sample_status(chunks: list[dict[str, Any]]) -> str:
    statuses = [chunk.get("status") for chunk in chunks]
    if statuses and all(status == "success" for status in statuses):
        return "success"
    if any(status == "success" for status in statuses):
        return "partial_success"
    return "failed"


class _timeout:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.previous_handler = None

    def __enter__(self) -> None:
        self.previous_handler = signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, exc_type, exc, tb) -> None:
        signal.alarm(0)
        if self.previous_handler is not None:
            signal.signal(signal.SIGALRM, self.previous_handler)

    @staticmethod
    def _handle_timeout(signum, frame) -> None:
        raise TimeoutError("sample timed out")
