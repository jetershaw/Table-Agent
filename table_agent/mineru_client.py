"""MinerU table recognition through mineru-vl-utils."""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from typing import Any

from PIL import Image

from table_agent.config import ServiceConfig

try:
    from mineru_vl_utils import MinerUClient
except Exception:  # pragma: no cover - surfaced at runtime with a clear error.
    MinerUClient = None


class MinerUTableClient:
    def __init__(
        self, service: ServiceConfig, transport: str = "http-client", timeout: int = 180
    ) -> None:
        if MinerUClient is None:
            raise RuntimeError("mineru_vl_utils is not installed; run in conda env mineru")
        self.service = service
        self.timeout = timeout
        self.server_url = _endpoint_to_server_url(service.endpoint)
        self.client = MinerUClient(
            model_name=service.model,
            backend=transport,
            server_url=self.server_url,
        )

    def recognize_table(self, image_path: str | Path) -> dict[str, Any]:
        image = Image.open(Path(image_path)).convert("RGB")
        with _timeout(self.timeout):
            raw = asyncio.run(self.client.aio_content_extract(image=image, type="table"))
        return normalize_table_output(raw)


def normalize_table_output(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        otsl = str(raw.get("otsl", "") or "")
        if not otsl and raw.get("table_otsl"):
            otsl = str(raw.get("table_otsl"))
        payload: dict[str, Any] = {
            "status": str(raw.get("status", "success") or "success"),
            "otsl": otsl,
            "html": str(raw.get("html", "") or ""),
            "row_count": int(raw.get("row_count", 0) or 0),
            "col_count": int(raw.get("col_count", 0) or 0),
            "raw": raw,
        }
        if not payload["otsl"] and payload["html"]:
            payload["status"] = "truncated"
            payload["error"] = "mineru returned html but no otsl"
        return payload

    if isinstance(raw, str):
        text = raw.strip()
        return {
            "status": "success" if text else "failed",
            "otsl": text,
            "html": "",
            "row_count": len([line for line in text.splitlines() if line.strip()]),
            "col_count": 0,
            "raw": raw,
        }

    return {
        "status": "failed",
        "otsl": "",
        "html": "",
        "row_count": 0,
        "col_count": 0,
        "raw": raw,
        "error": "unsupported mineru output type",
    }


def _endpoint_to_server_url(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    suffix = "/v1/chat/completions"
    if value.endswith(suffix):
        value = value[: -len(suffix)]
    return value.rstrip("/") + "/"


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
        raise TimeoutError("MinerU table recognition timed out")
