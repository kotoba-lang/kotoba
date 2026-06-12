"""ollama_stream.py — Async streaming Ollama /api/chat client.

`kotodama.local_llm.chat_json` is non-streaming; for the agent loop we
need per-token deltas. This module adds a minimal streaming wrapper
sharing the same env-driven config (`LOCAL_LLM_ENDPOINT`, `LOCAL_LLM_MODEL`,
`LOCAL_LLM_TIMEOUT_SEC`).

Authoritative ADR: 90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable

import httpx

from kotodama.local_llm import LocalLlmConfig


@dataclass
class GenerationStats:
    duration_ms: float
    total_tokens: int
    tokens_per_second: float
    rag_active: bool = False


def _config_for_endpoint(cfg: LocalLlmConfig) -> str:
    """Convert /api/chat or /api/generate endpoint to /api/chat (streaming)."""
    if cfg.endpoint.endswith("/api/chat"):
        return cfg.endpoint
    base = cfg.endpoint.rstrip("/").rsplit("/api/", 1)[0]
    return f"{base}/api/chat"


async def runtime_generate(
    messages: list[dict[str, str]],
    on_token: Callable[[str], None | Awaitable[None]],
    *,
    config: LocalLlmConfig | None = None,
    temperature: float = 0.7,
    top_k: int = 40,
    max_tokens: int | None = None,
) -> GenerationStats:
    """Stream a chat completion from Ollama, calling `on_token` per delta.

    Returns aggregated stats derived from Ollama's final `done` line when
    available, falling back to wall-clock + emitted-chunk count.
    """
    cfg = config or LocalLlmConfig.from_env()
    if cfg.provider != "ollama":
        raise ValueError(f"unsupported local llm provider: {cfg.provider}")

    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages],
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_k": top_k,
            "num_predict": max_tokens if max_tokens is not None else cfg.num_predict,
        },
    }

    endpoint = _config_for_endpoint(cfg)
    started = time.perf_counter()
    token_count = 0
    eval_count = 0
    eval_duration_ns = 0
    total_duration_ns = 0

    async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
        async with client.stream("POST", endpoint, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                msg = obj.get("message")
                content: str = ""
                if isinstance(msg, dict):
                    raw = msg.get("content")
                    if isinstance(raw, str):
                        content = raw
                if content:
                    token_count += 1
                    res = on_token(content)
                    if hasattr(res, "__await__"):
                        await res  # type: ignore[func-returns-value]
                if obj.get("done"):
                    if isinstance(obj.get("eval_count"), int):
                        eval_count = obj["eval_count"]
                    if isinstance(obj.get("eval_duration"), int):
                        eval_duration_ns = obj["eval_duration"]
                    if isinstance(obj.get("total_duration"), int):
                        total_duration_ns = obj["total_duration"]

    wall_ms = (time.perf_counter() - started) * 1000.0
    decode_ms = (eval_duration_ns / 1_000_000.0) if eval_duration_ns > 0 else wall_ms
    decoded = eval_count if eval_count > 0 else token_count
    tps = (decoded * 1000.0 / decode_ms) if decoded > 0 and decode_ms > 0 else 0.0
    return GenerationStats(
        duration_ms=(total_duration_ns / 1_000_000.0) if total_duration_ns > 0 else wall_ms,
        total_tokens=decoded,
        tokens_per_second=tps,
    )


async def check_ollama_ready(model: str | None = None) -> dict[str, bool]:
    """GET /api/tags probe. Mirrors the TS daemon's checkOllamaReady."""
    cfg = LocalLlmConfig.from_env()
    target_model = model or cfg.model
    base = cfg.endpoint.rstrip("/").rsplit("/api/", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/api/tags")
            r.raise_for_status()
            data = r.json()
            installed = any(
                isinstance(m, dict) and isinstance(m.get("name"), str) and m["name"].startswith(target_model)
                for m in (data.get("models") or [])
            )
            return {"reachable": True, "modelInstalled": installed}
    except Exception:
        return {"reachable": False, "modelInstalled": False}
