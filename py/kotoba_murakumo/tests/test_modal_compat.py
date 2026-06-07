"""Modal-compat surface — verify import shape + R0 stub semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

import json

import httpx

import kotoba_murakumo.modal_compat as modal
from kotoba_murakumo.exceptions import MurakumoCompatNotImplemented


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def test_modal_compat_surface_present() -> None:
    # Names a Modal app expects at the top level.
    assert hasattr(modal, "App")
    assert hasattr(modal, "Stub")              # legacy alias
    assert modal.Stub is modal.App
    assert hasattr(modal, "Image")
    assert hasattr(modal, "Volume")
    assert hasattr(modal, "Secret")
    assert hasattr(modal, "gpu")
    for name in ("enter", "exit", "method"):
        assert callable(getattr(modal, name))


def test_modal_gpu_strings_map_to_evo_x2() -> None:
    from kotoba_murakumo.gpu import EvoX2

    for fn in (modal.gpu.T4, modal.gpu.L4, modal.gpu.A10G, modal.gpu.H100, modal.gpu.H200):
        assert isinstance(fn(), EvoX2)
    assert isinstance(modal.gpu.A100(memory=80), EvoX2)


def test_modal_function_decorator_registers_and_local_works() -> None:
    fleet_path = _repo_root() / "50-infra/murakumo/fleet.toml"
    app = modal.App("smoke", fleet=fleet_path, did="did:web:test.etzhayyim.com")

    @app.function(gpu="A10G", model="llama3.2:3b")
    def echo(x: str) -> str:
        return f"echo:{x}"

    # Modal compat: .local() runs in-process.
    assert echo.local("hi") == "echo:hi"
    # Direct call also runs locally (Modal semantics inside a remote container).
    assert echo("hi") == "echo:hi"
    # App tracks it.
    assert "echo" in app.registered_functions()


def test_modal_remote_dispatches_via_litellm_gateway(monkeypatch) -> None:
    """R1.1: .remote() actually dispatches to judah :4000 through the LiteLLM gateway."""
    fleet_path = _repo_root() / "50-infra/murakumo/fleet.toml"
    seen_url: dict = {}
    real_cls = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        seen_url["url"] = str(request.url)
        seen_url["model"] = json.loads(request.content.decode())["model"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "Client",
        lambda timeout=None: real_cls(transport=transport, timeout=timeout),
    )

    app = modal.App("smoke", fleet=fleet_path)

    @app.function(model="gemma3:4b")  # gpu=None → LiteLLM gateway
    def f(x: str) -> str: ...

    out = f.remote("hello")
    assert out == "ok"
    assert seen_url["url"] == "http://192.168.1.17:4000/v1/chat/completions"
    assert seen_url["model"] == "gemma3:4b"


def test_modal_unsupported_surfaces_fail_loud() -> None:
    with pytest.raises(MurakumoCompatNotImplemented):
        modal.Image.from_registry("nvidia/cuda:12.4.0-base")
    with pytest.raises(MurakumoCompatNotImplemented):
        modal.web_endpoint()
    with pytest.raises(MurakumoCompatNotImplemented):
        modal.Sandbox()


def test_modal_cls_records_enter_method() -> None:
    fleet_path = _repo_root() / "50-infra/murakumo/fleet.toml"
    app = modal.App("smoke", fleet=fleet_path)

    @app.cls(gpu="A100")
    class Server:
        @modal.enter()
        def load(self) -> None: ...

        @modal.method()
        def generate(self, prompt: str) -> str:
            return prompt

    meta = getattr(Server, "__kotoba_murakumo_meta__")
    assert "load" in meta["enter"]
    assert "generate" in meta["method"]
    assert "Server" in app.registered_classes()
