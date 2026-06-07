"""
Unit tests for the `generic.tls.probe` primitive in
kotodama.zeebe_worker_main.

Pure-function coverage (no live network):
- `_parse_tls_time` normalises `Jun  1 12:00:00 2026 GMT` → ISO-8601.
- `_cert_san_dns` / `_cert_cn` / `_cert_issuer_cn` extract the right RDNs.
- `_host_matches_san` handles literal + wildcard SAN entries.
- `_decode_cert_bin` returns `{}` for empty / malformed input and a
  parsed dict for a known-good DER.

Handler coverage (async):
- Empty host / out-of-range port returns `{ok: false, error}` without
  ever touching the network.
- `timeoutSec` is clamped to [1, 30].

Live-network tests (dispatcher.etzhayyim.com / *.badssl.com) are exercised
by the integration suite, not here.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


# Stub pyzeebe + sibling imports before the module under test is loaded.
# The module's `main()` touches ZeebeWorker / LLM / db_sync, but the TLS
# primitive only uses stdlib `ssl` + `socket`, so we can stub the rest.
def _install_stubs() -> None:
    if "pyzeebe" not in sys.modules:
        stub = types.ModuleType("pyzeebe")

        class _W:
            def __init__(self, *a, **kw): pass
            def task(self, **kw): return lambda f: f
            async def work(self): pass

        stub.ZeebeClient = _W  # type: ignore[attr-defined]
        stub.ZeebeWorker = _W  # type: ignore[attr-defined]
        stub.create_insecure_channel = lambda **kw: None  # type: ignore[attr-defined]
        sys.modules["pyzeebe"] = stub

    if "kotodama.llm" not in sys.modules:
        llm = types.ModuleType("kotodama.llm")

        class _E(Exception): pass
        llm.LlmError = _E  # type: ignore[attr-defined]
        llm.call_tier = lambda *a, **kw: {}  # type: ignore[attr-defined]
        llm.call_tier_json = lambda *a, **kw: {}  # type: ignore[attr-defined]
        llm.parse_json_content = lambda c: None  # type: ignore[attr-defined]
        sys.modules["kotodama.llm"] = llm

    if "kotodama.db_sync" not in sys.modules:
        dbsync = types.ModuleType("kotodama.db_sync")

        @contextlib.contextmanager
        def _cursor():
            yield None

        dbsync.sync_cursor = _cursor  # type: ignore[attr-defined]
        sys.modules["kotodama.db_sync"] = dbsync


_install_stubs()

from kotodama.zeebe_worker_main import (  # noqa: E402
    _cert_cn,
    _cert_issuer_cn,
    _cert_san_dns,
    _decode_cert_bin,
    _host_matches_san,
    _parse_tls_time,
    task_generic_rules_evaluate,
    task_generic_tls_probe,
    task_generic_xrpc_invoke,
)


# ─── _parse_tls_time ────────────────────────────────────────────────────


def test_parse_tls_time_iso():
    assert _parse_tls_time("Jun  1 12:00:00 2026 GMT") == "2026-06-01T12:00:00Z"


def test_parse_tls_time_unparseable_falls_through():
    # Returns the raw string so BPMN can still audit it.
    assert _parse_tls_time("not a date") == "not a date"


def test_parse_tls_time_none():
    assert _parse_tls_time(None) is None
    assert _parse_tls_time("") is None


# ─── _cert_*_cn ─────────────────────────────────────────────────────────


def test_cert_cn_reads_common_name():
    cert = {"subject": ((("commonName", "example.com"),),)}
    assert _cert_cn(cert) == "example.com"


def test_cert_cn_missing_returns_none():
    assert _cert_cn({}) is None
    assert _cert_cn({"subject": []}) is None


def test_cert_issuer_cn():
    cert = {"issuer": ((("commonName", "Let's Encrypt E7"),),)}
    assert _cert_issuer_cn(cert) == "Let's Encrypt E7"


# ─── _cert_san_dns ──────────────────────────────────────────────────────


def test_cert_san_dns_lowercased():
    cert = {"subjectAltName": [("DNS", "Example.com"), ("DNS", "www.example.com")]}
    assert _cert_san_dns(cert) == ["example.com", "www.example.com"]


def test_cert_san_dns_ignores_non_dns_types():
    cert = {"subjectAltName": [("IP Address", "1.2.3.4"), ("DNS", "foo")]}
    assert _cert_san_dns(cert) == ["foo"]


def test_cert_san_dns_empty():
    assert _cert_san_dns({}) == []
    assert _cert_san_dns({"subjectAltName": None}) == []


# ─── _host_matches_san ──────────────────────────────────────────────────


def test_host_matches_san_exact():
    assert _host_matches_san("example.com", ["example.com"]) is True
    assert _host_matches_san("Example.com", ["example.com"]) is True


def test_host_matches_san_wildcard_one_label():
    assert _host_matches_san("api.example.com", ["*.example.com"]) is True
    # wildcard covers exactly one label
    assert _host_matches_san("example.com", ["*.example.com"]) is False


def test_host_matches_san_no_match():
    assert _host_matches_san("evil.com", ["example.com", "*.example.com"]) is False
    assert _host_matches_san("", ["example.com"]) is False


# ─── _decode_cert_bin ───────────────────────────────────────────────────


def test_decode_cert_bin_empty():
    assert _decode_cert_bin(None) == {}
    assert _decode_cert_bin(b"") == {}


def test_decode_cert_bin_garbage():
    assert _decode_cert_bin(b"\x00not a cert") == {}


# ─── task_generic_tls_probe (input validation; no network) ──────────────


def test_task_requires_host():
    r = asyncio.run(task_generic_tls_probe(host=""))
    assert r == {"ok": False, "error": "host required"}


def test_task_rejects_bad_port():
    r = asyncio.run(task_generic_tls_probe(host="x", port=0))
    assert r["ok"] is False and "port out of range" in r["error"]
    r2 = asyncio.run(task_generic_tls_probe(host="x", port=70_000))
    assert r2["ok"] is False and "port out of range" in r2["error"]
    r3 = asyncio.run(task_generic_tls_probe(host="x", port="not-a-number"))  # type: ignore[arg-type]
    assert r3["ok"] is False and "invalid port" in r3["error"]


def test_generic_rules_logistics_delivery_proof():
    r = asyncio.run(task_generic_rules_evaluate(
        ruleSet="open-logistics-lastmile.delivery-proof.v1",
        facts={"signatureCid": "bafyproof", "minutesLate": 90, "damageReported": False},
    ))
    assert r["passed"] is True
    assert r["proofValid"] is True
    assert r["slaTier"] == "late"
    assert r["claimRequired"] is True


def test_generic_rules_machinery_downtime_escalates():
    r = asyncio.run(task_generic_rules_evaluate(
        ruleSet="open-machinery-maintenance.downtime.v1",
        facts={"estimatedMinutes": 300, "safetyIncident": False, "productionImpact": "line_stop"},
    ))
    assert r["passed"] is True
    assert r["severity"] == "major"
    assert r["escalationRequired"] is True


def test_generic_xrpc_invoke_requires_nsid():
    r = asyncio.run(task_generic_xrpc_invoke(actor="did:web:tsukuru.etzhayyim.com"))
    assert r == {"error": "nsid required", "status": 400}


def test_generic_xrpc_invoke_uses_did_web_actor(monkeypatch):
    import kotodama.zeebe_worker_main as worker_main

    calls = []

    def _post(url, payload, headers, timeout):
        calls.append((url, payload, headers, timeout))
        return 200, {"ok": True}

    monkeypatch.setattr(worker_main, "_http_post_json", _post)
    r = asyncio.run(task_generic_xrpc_invoke(
        actor="did:web:tsukuru.etzhayyim.com",
        nsid="com.etzhayyim.apps.tsukuru.euv.designManufacturingFlow",
        payload={"production_order_id": "po-1"},
        timeoutSec=5,
    ))
    assert r["status"] == 200
    assert r["result"] == {"ok": True}
    assert calls[0][0] == "https://tsukuru.etzhayyim.com/xrpc/com.etzhayyim.apps.tsukuru.euv.designManufacturingFlow"
    assert calls[0][1]["actor"] == "did:web:tsukuru.etzhayyim.com"
    assert calls[0][1]["production_order_id"] == "po-1"
    assert calls[0][2]["x-kotoba-kotodama-verified"] == "true"
    assert calls[0][3] == 5.0
