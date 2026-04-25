import json
import logging
import time
from dataclasses import dataclass
from enum import Enum

import httpx

from config import settings

logger = logging.getLogger(__name__)


class ModelBackend(Enum):
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


@dataclass
class ModelConfig:
    backend: ModelBackend
    model_id: str
    base_url: str
    api_key: str | None


@dataclass
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    backend: str


class ModelClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    async def complete(
        self, messages: list[dict], json_mode: bool = False
    ) -> ModelResponse:
        logger.debug(
            "Calling %s model=%s", self.config.backend.value, self.config.model_id
        )
        start = time.time()
        try:
            if self.config.backend == ModelBackend.OPENROUTER:
                resp = await self._call_openrouter(messages, json_mode)
            else:
                resp = await self._call_ollama(messages, json_mode)
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"{self.config.backend.value} request failed: {exc}"
            ) from exc
        resp.latency_ms = int((time.time() - start) * 1000)
        return resp

    async def _call_openrouter(
        self, messages: list[dict], json_mode: bool
    ) -> ModelResponse:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "HTTP-Referer": settings.APP_SITE_URL,
            "X-Title": "AI Fitness Coach",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model": self.config.model_id,
            "messages": messages,
            "max_tokens": settings.DEFAULT_MAX_TOKENS,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            r = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            r.raise_for_status()
            data = r.json()

        if "error" in data:
            raise ValueError(f"OpenRouter error: {data['error']}")

        usage = data.get("usage", {})
        return ModelResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", self.config.model_id),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=0,
            backend="openrouter",
        )

    async def _call_ollama(
        self, messages: list[dict], json_mode: bool
    ) -> ModelResponse:
        body: dict = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            body["format"] = "json"

        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            r = await client.post(
                f"{self.config.base_url}/api/chat",
                json=body,
            )
            r.raise_for_status()
            data = r.json()

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        return ModelResponse(
            content=data["message"]["content"],
            model=data.get("model", self.config.model_id),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=0,
            backend="ollama",
        )


def get_model_client(model_str: str) -> ModelClient:
    parts = model_str.split("/", maxsplit=1)
    if len(parts) != 2:
        raise ValueError(
            "Unknown backend prefix. Use 'openrouter/...' or 'ollama/...'"
        )
    prefix, model_id = parts

    if prefix == "openrouter":
        return ModelClient(
            ModelConfig(
                backend=ModelBackend.OPENROUTER,
                model_id=model_id,
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
            )
        )
    if prefix == "ollama":
        return ModelClient(
            ModelConfig(
                backend=ModelBackend.OLLAMA,
                model_id=model_id,
                base_url=settings.OLLAMA_BASE_URL,
                api_key=None,
            )
        )
    raise ValueError(
        "Unknown backend prefix. Use 'openrouter/...' or 'ollama/...'"
    )
