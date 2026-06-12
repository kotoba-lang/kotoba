from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3:14b"


@dataclass(frozen=True)
class LocalLlmConfig:
    provider: str = "ollama"
    endpoint: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_MODEL
    timeout_sec: float = 120.0
    num_predict: int = 384

    @classmethod
    def from_env(cls) -> "LocalLlmConfig":
        provider = os.environ.get("LOCAL_LLM_PROVIDER", "ollama").strip().lower() or "ollama"
        endpoint = os.environ.get("LOCAL_LLM_ENDPOINT", DEFAULT_OLLAMA_URL).strip()
        model = os.environ.get("LOCAL_LLM_MODEL", DEFAULT_MODEL).strip()
        try:
            timeout_sec = float(os.environ.get("LOCAL_LLM_TIMEOUT_SEC", "120"))
        except ValueError:
            timeout_sec = 120.0
        try:
            num_predict = int(os.environ.get("LOCAL_LLM_NUM_PREDICT", "384"))
        except ValueError:
            num_predict = 384
        return cls(
            provider=provider,
            endpoint=endpoint or DEFAULT_OLLAMA_URL,
            model=model or DEFAULT_MODEL,
            timeout_sec=max(1.0, timeout_sec),
            num_predict=max(32, num_predict),
        )


def build_chat_request(config: LocalLlmConfig, messages: list[dict[str, str]]) -> dict[str, Any]:
    if config.provider != "ollama":
        raise ValueError(f"unsupported local llm provider: {config.provider}")
    return {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": config.num_predict,
        },
    }


def parse_chat_response(config: LocalLlmConfig, response: dict[str, Any]) -> str:
    if config.provider != "ollama":
        raise ValueError(f"unsupported local llm provider: {config.provider}")
    message = response.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    content = response.get("response")
    return content if isinstance(content, str) else ""


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return {"rawText": stripped}
    try:
        value = json.loads(stripped[start : end + 1])
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        return {"rawText": stripped}


async def chat_json(
    *,
    messages: list[dict[str, str]],
    config: LocalLlmConfig | None = None,
) -> dict[str, Any]:
    cfg = config or LocalLlmConfig.from_env()
    request_body = build_chat_request(cfg, messages)
    async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
        response = await client.post(cfg.endpoint, json=request_body)
        response.raise_for_status()
        body = response.json()
    content = parse_chat_response(cfg, body)
    parsed = extract_json_object(content)
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "endpoint": cfg.endpoint,
        "content": content,
        "json": parsed,
    }


def chat_json_sync(
    *,
    messages: list[dict[str, str]],
    config: LocalLlmConfig | None = None,
) -> dict[str, Any]:
    return asyncio.run(chat_json(messages=messages, config=config))
