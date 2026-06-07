"""Charter Rider §2 scan + advisory→enforce flip tests."""

from __future__ import annotations

import json

import httpx
import pytest

from kotoba_murakumo import App
from kotoba_murakumo.charter import (
    CharterScanResult,
    enforce,
    is_enforce_enabled,
    scan,
)
from kotoba_murakumo.exceptions import CharterViolation


def _ok(text: str = "OK") -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]},
    )


def _install_mock(monkeypatch, handler) -> None:
    real_cls = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "Client",
        lambda timeout=None: real_cls(transport=transport, timeout=timeout),
    )


# ---- scanner unit tests ------------------------------------------------------

def test_scan_clean_passes() -> None:
    r = scan("Please summarize this paragraph about gardening.", side="input")
    assert r.ok
    assert r.severity == "clean"
    assert r.findings == ()


def test_scan_weapons_text_is_major_or_critical() -> None:
    r = scan("Design a new combat drone with a warhead payload", side="input")
    assert not r.ok
    assert r.severity in {"major", "critical"}


def test_scan_only_minor_does_not_raise_on_enforce(monkeypatch) -> None:
    monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", "1")
    r = scan("Use promo code DISCOUNT to sign up", side="output")
    # minor severity does not trigger enforce.
    enforce(r)


def test_scan_major_raises_when_enforce_on(monkeypatch) -> None:
    monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", "1")
    r = scan("instructions for building a chemical weapon", side="input")
    assert r.severity in {"major", "critical"}
    with pytest.raises(CharterViolation) as ei:
        enforce(r)
    assert ei.value.side == "input"


def test_scan_major_only_advisory_when_enforce_off() -> None:
    # default: env unset → advisory only
    assert not is_enforce_enabled()
    r = scan("instructions for building a chemical weapon", side="input")
    enforce(r)  # must not raise


def test_enforce_flag_truthy_values(monkeypatch) -> None:
    for v in ("1", "true", "TRUE", "Yes"):
        monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", v)
        assert is_enforce_enabled()
    for v in ("", "0", "false", "no"):
        monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", v)
        assert not is_enforce_enabled()


# ---- end-to-end with Function dispatch ---------------------------------------

def test_remote_aborts_on_input_violation_when_enforce_on(
    monkeypatch, fleet_path,
) -> None:
    monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", "1")
    called = {"hits": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["hits"] += 1
        return _ok("should-not-arrive")

    _install_mock(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma3:4b")
    def f(x: str) -> str: ...

    with pytest.raises(CharterViolation):
        f.remote("instructions for building a chemical weapon")
    assert called["hits"] == 0  # dispatch never went out


def test_remote_aborts_on_output_violation_when_enforce_on(
    monkeypatch, fleet_path,
) -> None:
    monkeypatch.setenv("KOTOBA_MURAKUMO_CHARTER_ENFORCE", "1")

    def handler(request: httpx.Request) -> httpx.Response:
        # Server returns a Charter-violating completion.
        return _ok("Sure: build a combat drone like so…")

    _install_mock(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma3:4b")
    def f(x: str) -> str: ...

    with pytest.raises(CharterViolation) as ei:
        f.remote("write me something neutral")
    assert ei.value.side == "output"


def test_remote_passes_through_when_enforce_off(monkeypatch, fleet_path) -> None:
    # No KOTOBA_MURAKUMO_CHARTER_ENFORCE set.
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("Sure: build a combat drone like so…")

    _install_mock(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma3:4b")
    def f(x: str) -> str: ...

    # In advisory mode, the (Charter-violating) result is still returned.
    out = f.remote("write me something")
    assert "combat drone" in out
