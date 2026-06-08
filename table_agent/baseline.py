"""Full-image MinerU baseline collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from table_agent.benchmark import iter_benchmark_records, resolve_image_path
from table_agent.client import VisionClient
from table_agent.config import AgentConfig
from table_agent.otsl import otsl_to_html_when_possible
from table_agent.smoke import MINERU_TABLE_PROMPT


def run_baseline_collection(
    config: AgentConfig,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
    output_jsonl: str | None = None,
) -> dict[str, Any]:
    output_path = Path(output_jsonl or config.paths.output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(config.paths.raw_response_dir) / "baseline"
    raw_dir.mkdir(parents=True, exist_ok=True)

    client = VisionClient(config.mineru)
    total = 0
    success = 0
    failed = 0

    with output_path.open("w", encoding="utf-8") as out:
        for record_index, record in iter_benchmark_records(
            config.paths.input_jsonl, start=start, end=end, limit=limit
        ):
            total += 1
            row = dict(record)
            try:
                image_path = resolve_image_path(record, config.paths.image_dir)
                raw_response = client.chat_with_image(image_path, MINERU_TABLE_PROMPT)
                raw_path = raw_dir / f"{record_index:05d}.json"
                _write_json(raw_path, raw_response)
                otsl = extract_message_content(raw_response)
                html = otsl_to_html_when_possible(otsl)
                status = "success" if otsl else "failed"
                if status == "success":
                    success += 1
                else:
                    failed += 1
                row["baseline_parse_result"] = {
                    "status": status,
                    "otsl": otsl,
                    "html": html,
                    "raw_response": {"path": str(raw_path)},
                }
            except Exception as exc:
                failed += 1
                row["baseline_parse_result"] = {
                    "status": "failed",
                    "otsl": "",
                    "html": "",
                    "raw_response": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "output_jsonl": str(output_path),
        "total": total,
        "success": success,
        "failed": failed,
    }


def extract_message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts).strip()
    return str(content or "").strip()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
