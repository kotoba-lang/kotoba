"""End-to-end ``Function.remote/.remote_async/.spawn/.map/.stream`` via mock HTTP."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from kotoba_murakumo import App, gpu
from kotoba_murakumo.exceptions import FleetUnreachable


def _ok(text: str = "OK") -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]},
    )


def _install_mock_clients(monkeypatch, handler) -> None:
    real_sync = httpx.Client
    real_async = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "Client",
        lambda timeout=None: real_sync(transport=transport, timeout=timeout),
    )
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda timeout=None: real_async(transport=transport, timeout=timeout),
    )


def test_remote_returns_string_through_litellm_gateway(monkeypatch, fleet_path) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return _ok(f"echo:{captured['body']['messages'][0]['content']}")

    _install_mock_clients(monkeypatch, handler)

    app = App("smoke", fleet=fleet_path, did="did:web:test.etzhayyim.com")

    @app.function(model="gemma4:e4b")  # gpu=None → litellm-gateway
    def reply(text: str) -> str: ...

    out = reply.remote("hello")
    assert out == "echo:hello"
    assert captured["url"] == "http://100.113.200.45:4000/v1/chat/completions"
    assert captured["body"]["model"] == "gemma4:e4b"


def test_remote_through_mac_mini_node_ollama(monkeypatch, fleet_path) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return _ok("own-node")

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(gpu=gpu.MacMini(node="benjamin"), model="gemma4:e4b-it-qat")
    def f(x: str) -> str: ...

    assert f.remote("ping") == "own-node"
    assert seen_urls[0] == "http://100.75.169.8:11434/v1/chat/completions"


def test_remote_through_evo_x2_litellm_uses_bearer(monkeypatch, fleet_path) -> None:
    seen_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return _ok("evo")

    _install_mock_clients(monkeypatch, handler)
    monkeypatch.setenv("LITELLM_MASTER_KEY", "shh-secret")
    app = App("smoke", fleet=fleet_path)

    @app.function(gpu=gpu.EvoX2(), model="llama3.3:70b")
    def heavy(x: str) -> str: ...

    heavy.remote("analyze this")
    assert seen_headers.get("authorization") == "Bearer shh-secret"


def test_remote_async_returns_string(monkeypatch, fleet_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("async-result")

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    out = asyncio.run(f.remote_async("hi"))
    assert out == "async-result"


def test_spawn_returns_handle_and_get_blocks_for_result(monkeypatch, fleet_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("spawned")

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    handle = f.spawn("hi")
    assert isinstance(handle.call_id, str) and len(handle.call_id) == 32
    assert handle.get(timeout=5) == "spawned"
    assert handle.done()


def test_map_returns_results_in_input_order(monkeypatch, fleet_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        prompt = body["messages"][0]["content"]
        return _ok(f"r:{prompt}")

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    out = list(f.map(["a", "b", "c", "d"], concurrency=4, order_outputs=True))
    assert out == ["r:a", "r:b", "r:c", "r:d"]


def test_stream_yields_tokens(monkeypatch, fleet_path) -> None:
    chunks = [
        b'data: {"choices":[{"delta":{"content":"to"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"ken"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"-stream"}}]}\n',
        b"data: [DONE]\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"".join(chunks))

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    async def collect() -> list[str]:
        out: list[str] = []
        async for tok in f.stream("hi"):
            out.append(tok)
        return out

    tokens = asyncio.run(collect())
    assert tokens == ["to", "ken", "-stream"]


def test_remote_writes_invocation_ndjson(monkeypatch, fleet_path, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("RESULT")

    _install_mock_clients(monkeypatch, handler)
    log = tmp_path / "log.ndjson"
    monkeypatch.setenv("KOTOBA_MURAKUMO_LOG", str(log))
    from kotoba_murakumo._internal import ndjson as nd
    monkeypatch.setattr(nd, "_DEFAULT_PATH", log)

    app = App("smoke", fleet=fleet_path, did="did:web:caller.etzhayyim.com")

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    f.remote("PROMPT")
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["app"] == "smoke"
    assert rec["fn"] == "f"
    assert rec["caller_did"] == "did:web:caller.etzhayyim.com"
    assert rec["model"] == "gemma4:e4b"
    assert rec["endpoint"] == "http://100.113.200.45:4000"
    assert rec["result_chars"] == len("RESULT")
    assert rec["phase"] == "sync"
    assert rec["charter_in"] == "clean"
    assert rec["charter_out"] == "clean"


def test_remote_http_error_becomes_fleet_unreachable(monkeypatch, fleet_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    _install_mock_clients(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    with pytest.raises(FleetUnreachable):
        f.remote("hi")
