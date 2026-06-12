"""mKOTO economy + Modal billing-parity tests (R1.3b)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from kotoba_murakumo import App, gpu
from kotoba_murakumo.economy import (
    MKOTO_PER_KOTO,
    BudgetExceeded,
    InsufficientCredit,
    Tariff,
    TariffRow,
    UsageActual,
    UsageEstimate,
    actual,
    default_tariff,
    estimate,
    row_for_route,
)


def _ok(text: str = "OK") -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]},
    )


def _install_mock(monkeypatch, handler) -> None:
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


# ---- unit tests --------------------------------------------------------------

def test_mkoto_per_koto_unit() -> None:
    assert MKOTO_PER_KOTO == 1_000_000


def test_default_tariff_has_three_rows() -> None:
    t = default_tariff()
    assert t.version.endswith("-dev")
    backends = {r.backend for r in t.rows}
    assert {"litellm-gateway", "evo-x2", "mac-mini/judah"} <= backends


def test_tariff_for_backend_lookup() -> None:
    t = default_tariff()
    row = t.for_backend("evo-x2")
    assert row.gpu_second_mkoto == 250
    assert row.egress_mb_mkoto == 10
    with pytest.raises(KeyError):
        t.for_backend("nonexistent-backend")


def test_row_for_route_fallback_for_unknown_mac_mini_tribe() -> None:
    t = default_tariff()
    # Specific tribe not enumerated → falls back to judah row.
    r = row_for_route(t, "mac-mini/simeon")
    assert r.backend == "mac-mini/judah"
    assert r.gpu_second_mkoto == 30


def test_tariff_from_and_to_json_roundtrip() -> None:
    payload = {
        "version": "2026-05-28-test",
        "rows": [
            {"backend": "x", "gpu_second_mkoto": 5, "egress_mb_mkoto": 2},
        ],
        "signed_by": ["did:web:a", "did:web:b"],
        "signed_at": "2026-05-28T20:00:00Z",
    }
    t = Tariff.from_json(payload)
    assert t.version == "2026-05-28-test"
    assert t.signed_by == ("did:web:a", "did:web:b")
    assert t.for_backend("x").gpu_second_mkoto == 5


def test_tariff_load_from_file(tmp_path) -> None:
    p = tmp_path / "tariff.json"
    p.write_text(json.dumps({
        "version": "2026-05-28-file",
        "rows": [{"backend": "y", "gpu_second_mkoto": 7}],
    }), encoding="utf-8")
    t = Tariff.load(p)
    assert t.version == "2026-05-28-file"
    assert t.for_backend("y").gpu_second_mkoto == 7


def test_estimate_safe_overestimates() -> None:
    t = default_tariff()
    # 100 chars prompt, expected_completion_tokens=256 default.
    est_ = estimate(
        tariff=t, backend="litellm-gateway",
        prompt_chars=100,
    )
    assert est_.cost_mkoto_est > 0
    assert est_.gpu_seconds_est > 0
    assert est_.tariff_version == t.version
    assert est_.backend == "litellm-gateway"


def test_estimate_evo_x2_more_expensive_than_mac_mini() -> None:
    t = default_tariff()
    e_evo = estimate(tariff=t, backend="evo-x2", prompt_chars=100)
    e_mac = estimate(tariff=t, backend="mac-mini/judah", prompt_chars=100)
    assert e_evo.cost_mkoto_est > e_mac.cost_mkoto_est


def test_actual_uses_latency_for_gpu_seconds() -> None:
    t = default_tariff()
    a = actual(
        tariff=t, backend="litellm-gateway",
        prompt_chars=10, completion_chars=20, latency_ms=2500,
    )
    assert a.gpu_seconds == 2.5
    assert a.cost_mkoto > 0
    assert isinstance(a.to_jsonable(), dict)


# ---- integration: pre-dispatch budget check ----------------------------------

def test_budget_exceeded_raises_before_http(monkeypatch, fleet_path) -> None:
    dispatched = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        dispatched["count"] += 1
        return _ok("should-not-arrive")

    _install_mock(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)

    @app.function(model="gemma4:e4b", max_cost_mkoto=1)  # cap 1 mKOTO
    def f(x: str) -> str: ...

    with pytest.raises(BudgetExceeded) as ei:
        f.remote("hello world this is a longer prompt")
    assert ei.value.cap_mkoto == 1
    assert ei.value.estimated_mkoto > 1
    assert ei.value.fn_name == "f"
    assert dispatched["count"] == 0


def test_insufficient_credit_raises_before_http(monkeypatch, fleet_path) -> None:
    dispatched = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        dispatched["count"] += 1
        return _ok("should-not-arrive")

    _install_mock(monkeypatch, handler)

    # Inject a balance_lookup that returns 1 mKOTO for any DID.
    app = App(
        "smoke",
        fleet=fleet_path,
        did="did:web:poor.etzhayyim.com",
        balance_lookup=lambda did: 1,
    )

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    with pytest.raises(InsufficientCredit) as ei:
        f.remote("hello world")
    assert ei.value.did == "did:web:poor.etzhayyim.com"
    assert ei.value.balance_mkoto == 1
    assert ei.value.required_mkoto > 1
    assert dispatched["count"] == 0


def test_unlimited_balance_default_does_not_raise(monkeypatch, fleet_path) -> None:
    """When no balance_lookup is wired, the App acts as unlimited (sentinel)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("fine")

    _install_mock(monkeypatch, handler)
    app = App("smoke", fleet=fleet_path)  # no balance_lookup

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    assert f.remote("anything") == "fine"


def test_function_estimate_returns_usage_estimate(fleet_path) -> None:
    app = App("smoke", fleet=fleet_path)

    @app.function(gpu=gpu.EvoX2(), model="llama3.3:70b", max_cost_mkoto=1_000_000)
    def heavy(x: str) -> str: ...

    est_ = heavy.estimate("hello")
    assert isinstance(est_, UsageEstimate)
    assert est_.backend == "evo-x2"
    assert est_.cost_mkoto_est > 0
    assert est_.tariff_version.endswith("-dev")


def test_remote_ndjson_carries_cost_and_tariff(monkeypatch, fleet_path, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok("RESULT-OK")

    _install_mock(monkeypatch, handler)
    log = tmp_path / "log.ndjson"
    from kotoba_murakumo._internal import ndjson as nd
    monkeypatch.setattr(nd, "_DEFAULT_PATH", log)

    app = App("smoke", fleet=fleet_path, did="did:web:c.etzhayyim.com")

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    f.remote("PROMPT")
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert "cost_mkoto" in rec
    assert "cost_estimated_mkoto" in rec
    assert "tariff_version" in rec
    assert rec["cost_mkoto"] >= 0
    assert rec["tariff_version"].endswith("-dev")


def test_app_balance_and_tariff_accessors(fleet_path) -> None:
    app = App(
        "smoke", fleet=fleet_path, did="did:web:a.etzhayyim.com",
        balance_lookup=lambda did: 42_000 if did == "did:web:a.etzhayyim.com" else 0,
    )
    assert app.balance() == 42_000
    assert app.balance("did:web:other.etzhayyim.com") == 0

    t = app.get_tariff()
    assert isinstance(t, Tariff)
    assert t.for_backend("litellm-gateway").gpu_second_mkoto == 100


def test_app_balance_unlimited_when_no_lookup(fleet_path) -> None:
    app = App("smoke", fleet=fleet_path)
    assert app.balance() == 2 ** 62


def test_custom_tariff_injected_at_app_level(fleet_path) -> None:
    custom = Tariff(
        version="custom-v1",
        rows=(
            TariffRow("litellm-gateway", gpu_second_mkoto=999, egress_mb_mkoto=999),
        ),
    )
    app = App("smoke", fleet=fleet_path, tariff=custom)

    @app.function(model="gemma4:e4b")
    def f(x: str) -> str: ...

    est_ = f.estimate("x")
    assert est_.tariff_version == "custom-v1"
    # Way more expensive than default
    assert est_.cost_mkoto_est > 1000
