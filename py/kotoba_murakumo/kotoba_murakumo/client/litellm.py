"""LiteLLM (OpenAI-compatible chat-completions) client.

Wire format mirrors ``kotoba-llm::http_infer`` (Rust): POST
``/v1/chat/completions`` with ``Authorization: Bearer <master_key>`` when
``auth_bearer`` is provided.

Sync, async, and streaming variants share the same request body. The endpoint
URL passed in is the base (e.g. ``http://192.168.1.17:4000``); this module
appends ``/v1/chat/completions`` itself so the route resolver in
:mod:`kotoba_murakumo._internal.routing` can keep talking in base-URL terms.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx


def _build_request(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    stream: bool,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    headers = {"Content-Type": "application/json"}
    return endpoint, body, headers


def _add_bearer(headers: dict[str, str], auth_bearer: str | None) -> None:
    if auth_bearer:
        headers["Authorization"] = f"Bearer {auth_bearer}"


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(
            f"missing choices[0].message.content in LiteLLM response: {payload!r}"
        ) from e


def chat_completions(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    auth_bearer: str | None = None,
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
) -> str:
    """Synchronous chat-completions call. Returns assistant text."""
    endpoint, body, headers = _build_request(
        url=url, model=model, messages=messages, max_tokens=max_tokens, stream=False,
    )
    _add_bearer(headers, auth_bearer)
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(endpoint, json=body, headers=headers)
        resp.raise_for_status()
        return _extract_text(resp.json())


async def chat_completions_async(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    auth_bearer: str | None = None,
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
) -> str:
    """Async chat-completions call. Returns assistant text."""
    endpoint, body, headers = _build_request(
        url=url, model=model, messages=messages, max_tokens=max_tokens, stream=False,
    )
    _add_bearer(headers, auth_bearer)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(endpoint, json=body, headers=headers)
        resp.raise_for_status()
        return _extract_text(resp.json())


async def chat_completions_stream(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    auth_bearer: str | None = None,
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
) -> AsyncIterator[str]:
    """Async SSE stream. Yields assistant token strings as they arrive.

    Parses the OpenAI chat-completions SSE format::

        data: {"choices":[{"delta":{"content":"hel"}}]}
        data: {"choices":[{"delta":{"content":"lo"}}]}
        data: [DONE]
    """
    endpoint, body, headers = _build_request(
        url=url, model=model, messages=messages, max_tokens=max_tokens, stream=True,
    )
    _add_bearer(headers, auth_bearer)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        async with client.stream("POST", endpoint, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for raw in resp.aiter_lines():
                line = raw.strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                try:
                    delta = chunk["choices"][0]["delta"]
                except (KeyError, IndexError, TypeError):
                    continue
                tok = delta.get("content") or ""
                if tok:
                    yield tok
