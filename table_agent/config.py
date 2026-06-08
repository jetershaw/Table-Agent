"""Configuration loading and validation for Table Agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ALLOWED_IMAGE_INPUT_MODES = {"base64", "file_url", "path"}


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    endpoint: str
    model: str


@dataclass(frozen=True)
class PathConfig:
    input_jsonl: str
    image_dir: str
    output_jsonl: str
    raw_response_dir: str
    crop_dir: str


@dataclass(frozen=True)
class AgentConfig:
    mineru: ServiceConfig
    qwen: ServiceConfig
    image_input_mode: str
    max_split_iterations: int
    max_recognition_retries: int
    max_chunks: int
    paths: PathConfig

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(config_path: str | Path) -> AgentConfig:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping.")
    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> AgentConfig:
    mineru = _parse_service(raw.get("mineru"), "mineru")
    qwen = _parse_service(raw.get("qwen"), "qwen")
    paths = _parse_paths(raw.get("paths"))

    image_input_mode = _required_str(raw, "image_input_mode")
    if image_input_mode not in ALLOWED_IMAGE_INPUT_MODES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_INPUT_MODES))
        raise ValueError(f"image_input_mode must be one of: {allowed}")

    return AgentConfig(
        mineru=mineru,
        qwen=qwen,
        image_input_mode=image_input_mode,
        max_split_iterations=_required_positive_int(raw, "max_split_iterations"),
        max_recognition_retries=_required_non_negative_int(
            raw, "max_recognition_retries"
        ),
        max_chunks=_required_positive_int(raw, "max_chunks"),
        paths=paths,
    )


def _parse_service(value: Any, key: str) -> ServiceConfig:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping.")
    return ServiceConfig(
        name=_required_str(value, "name", prefix=key),
        endpoint=_required_str(value, "endpoint", prefix=key),
        model=_required_str(value, "model", prefix=key),
    )


def _parse_paths(value: Any) -> PathConfig:
    if not isinstance(value, dict):
        raise ValueError("paths must be a mapping.")
    return PathConfig(
        input_jsonl=_required_str(value, "input_jsonl", prefix="paths"),
        image_dir=_required_str(value, "image_dir", prefix="paths"),
        output_jsonl=_required_str(value, "output_jsonl", prefix="paths"),
        raw_response_dir=_required_str(value, "raw_response_dir", prefix="paths"),
        crop_dir=_required_str(value, "crop_dir", prefix="paths"),
    )


def _required_str(
    mapping: dict[str, Any], key: str, prefix: str | None = None
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        name = f"{prefix}.{key}" if prefix else key
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _required_positive_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer.")
    return value


def _required_non_negative_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer.")
    return value

