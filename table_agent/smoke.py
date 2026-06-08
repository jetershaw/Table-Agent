"""Smoke tests for model service message formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from table_agent.client import VisionClient
from table_agent.config import AgentConfig


MINERU_TABLE_PROMPT = "Table Recognition:"
QWEN_VISUAL_PROMPT = (
    "Inspect this table image briefly. Answer whether the image is readable and "
    "whether horizontal split lines should avoid cutting through text."
)


def resolve_smoke_image(config: AgentConfig, image_path: str | None = None) -> Path:
    if image_path:
        return Path(image_path)

    input_jsonl = Path(config.paths.input_jsonl)
    image_dir = Path(config.paths.image_dir)
    with input_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            image_name = record.get("image")
            if not isinstance(image_name, str) or not image_name:
                raise ValueError("First benchmark record has no valid image field.")
            return image_dir / image_name
    raise ValueError(f"No records found in {input_jsonl}")


def run_vision_smoke(
    config: AgentConfig,
    image_path: str | None = None,
    service: str = "both",
) -> dict[str, Any]:
    image = resolve_smoke_image(config, image_path)
    if not image.exists():
        raise FileNotFoundError(f"Smoke image not found: {image}")

    raw_dir = Path(config.paths.raw_response_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    if service not in {"both", "mineru", "qwen"}:
        raise ValueError("service must be one of: both, mineru, qwen")

    result = {"image_path": str(image)}

    if service in {"both", "mineru"}:
        mineru_response = VisionClient(config.mineru).chat_with_image(
            image, MINERU_TABLE_PROMPT
        )
        mineru_path = raw_dir / "smoke_mineru.json"
        _write_json(mineru_path, mineru_response)
        result.update(
            {
                "mineru_raw_response": str(mineru_path),
                "mineru_status": "success",
            }
        )

    if service in {"both", "qwen"}:
        qwen_response = VisionClient(config.qwen).chat_with_image(image, QWEN_VISUAL_PROMPT)
        qwen_path = raw_dir / "smoke_qwen.json"
        _write_json(qwen_path, qwen_response)
        result.update(
            {
                "qwen_raw_response": str(qwen_path),
                "qwen_status": "success",
            }
        )

    return result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
