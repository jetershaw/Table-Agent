"""OpenAI-compatible vision client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from table_agent.config import ServiceConfig
from table_agent.image_io import image_to_data_url


class VisionClient:
    def __init__(self, service: ServiceConfig, timeout: int = 120) -> None:
        self.service = service
        self.timeout = timeout

    def chat_with_image(self, image_path: str | Path, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.service.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_url(image_path)},
                        },
                    ],
                }
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 512,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = requests.post(
            self.service.endpoint,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
