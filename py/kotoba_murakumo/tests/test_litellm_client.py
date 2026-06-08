"""LiteLLM client — unit tests via httpx.MockTransport."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from kotoba_murakumo.client import litellm as litellm_client


def _ok_response(text: str = "hello world") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        },
    )


def _patch_sync(monkeypatch, handler) -> None:
    real_cls = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "Client",
        lambda timeout=None: real_cls(transport=transport, timeout=timeout),
    )


def _patch_async(monkeypatch, handler) -> None:
    real_cls = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda timeout=None: real_cls(transport=transport, timeout=timeout),
    )


def test_chat_completions_sends_openai_shape(monkeypatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content.decode())
        return _ok_response("hi back")

    _patch_sync(monkeypatch, handler)

    out = litellm_client.chat_completions(
        url="http://100.113.200.45:4000",
        model="gemma4:e4b",
        messages=[{"role": "user", "content": "hi"}],
        auth_bearer="secret-key",
    )

    assert out == "hi back"
    assert seen["url"] == "http://100.113.200.45:4000/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer secret-key"
    assert seen["body"]["model"] == "gemma4:e4b"
    assert seen["body"]["stream"] is False


def test_chat_completions_omits_bearer_when_none(monkeypatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        return _ok_response()

    _patch_sync(monkeypatch, handler)

    litellm_client.chat_completions(
        url="http://100.75.169.8:11434",
        model="gemma4:e4b",
        messages=[{"role": "user", "content": "hi"}],
        auth_bearer=None,
    )
    assert "authorization" not in seen["headers"]


def test_chat_completions_async(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response("async-out")

    _patch_async(monkeypatch, handler)

    out = asyncio.run(litellm_client.chat_completions_async(
        url="http://100.113.200.45:4000",
        model="gemma4:e4b",
        messages=[{"role": "user", "content": "x"}],
    ))
    assert out == "async-out"


def test_chat_completions_stream_yields_tokens(monkeypatch) -> None:
    chunks = [
        b'data: {"choices":[{"delta":{"content":"hel"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"lo "}}]}\n',
        b'data: {"choices":[{"delta":{"content":"world"}}]}\n',
        b"data: [DONE]\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"".join(chunks))

    _patch_async(monkeypatch, handler)

    async def collect() -> list[str]:
        out: list[str] = []
        async for tok in litellm_client.chat_completions_stream(
            url="http://100.113.200.45:4000",
            model="gemma4:e4b",
            messages=[{"role": "user", "content": "x"}],
        ):
            out.append(tok)
        return out

    out = asyncio.run(collect())
    assert out == ["hel", "lo ", "world"]


def test_chat_completions_raises_on_500(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    _patch_sync(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        litellm_client.chat_completions(
            url="http://100.113.200.45:4000",
            model="gemma4:e4b",
            messages=[{"role": "user", "content": "x"}],
        )


def test_chat_completions_raises_on_malformed_response(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    _patch_sync(monkeypatch, handler)

    with pytest.raises(ValueError, match="missing choices"):
        litellm_client.chat_completions(
            url="http://100.113.200.45:4000",
            model="gemma4:e4b",
            messages=[{"role": "user", "content": "x"}],
        )
