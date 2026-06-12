"""Tests for telecom Phase 1 primitives (subscriber, SIM, service, CDR, billing, SLA)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom as T  # noqa: E402


# ─── pure helper tests ────────────────────────────────────────────────────

def test_hash_id_returns_sha256_prefixed():
    h = T._hash_id("08012345678")
    assert h is not None
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_id_none_returns_none():
    assert T._hash_id(None) is None


def test_hash_id_empty_returns_none():
    assert T._hash_id("") is None
    assert T._hash_id("   ") is None


def test_new_id_with_parts_is_deterministic():
    a = T._new_id("sub", "08012345678")
    b = T._new_id("sub", "08012345678")
    assert a == b
    assert a.startswith("sub_")


def test_new_id_without_parts_is_random():
    a = T._new_id("sub")
    b = T._new_id("sub")
    assert a != b
    assert a.startswith("sub_")


def test_parse_date_accepts_iso_string():
    from datetime import date
    d = T._parse_date("2026-01-15", "field")
    assert d == date(2026, 1, 15)


def test_parse_date_accepts_date_object():
    from datetime import date
    d0 = date(2026, 1, 15)
    assert T._parse_date(d0, "field") is d0


def test_parse_date_raises_on_empty():
    import pytest
    with pytest.raises(ValueError, match="required"):
        T._parse_date("", "myField")


def test_require_raises_on_missing_field():
    import pytest
    with pytest.raises(ValueError, match="missing required field"):
        T._require({"a": "hello"}, ["a", "b"])


def test_require_passes_when_all_present():
    T._require({"a": "x", "b": "y"}, ["a", "b"])


def test_caller_returns_custom_did():
    assert T._caller({"callerDid": "did:web:custom.etzhayyim.com"}) == "did:web:custom.etzhayyim.com"


def test_caller_defaults_to_telecom_did():
    assert T._caller({}) == T.TELECOM_DID


def test_vid_subscriber_format():
    vid = T._vid_subscriber("sub_abc123")
    assert vid.startswith("at://did:web:telecom.etzhayyim.com/")
    assert "sub_abc123" in vid


def test_vid_sim_format():
    vid = T._vid_sim("sim_xyz")
    assert "sim_xyz" in vid


def test_vid_service_format():
    vid = T._vid_service("svc_001")
    assert "svc_001" in vid


def test_insert_dry_run_skips_db():
    # Should not raise — no DB connection exists
    T._insert("vertex_telecom_subscriber", {"vertex_id": "test", "col": "val"}, dry_run=True)


# ─── task tests (dryRun=True) ────────────────────────────────────────────

def test_subscriber_onboard_returns_ok():
    out = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="田中 太郎",
        msisdn="08012345678",
        kycStatus="verified",
        planId="plan_basic",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_subscriber_onboard_pending_when_not_verified():
    out = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="John Doe",
        msisdn="09099999999",
        kycStatus="pending",
        planId="plan_lite",
        dryRun=True,
    ))
    assert out["status"] == "pending"


def test_subscriber_onboard_uses_provided_id():
    out = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Jane",
        msisdn="08011112222",
        kycStatus="verified",
        planId="plan_a",
        subscriberId="sub_custom_001",
        dryRun=True,
    ))
    assert out["subscriberId"] == "sub_custom_001"


def test_subscriber_onboard_raises_on_missing_fields():
    import pytest
    with pytest.raises(ValueError, match="missing"):
        asyncio.run(T.task_telecom_subscriber_onboard(dryRun=True))


def test_sim_activate_returns_ok():
    out = asyncio.run(T.task_telecom_sim_activate(
        iccid="8981100021234567890",
        subscriberId="sub_abc",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_sim_activate_uses_provided_sim_id():
    out = asyncio.run(T.task_telecom_sim_activate(
        iccid="8981100021234567891",
        subscriberId="sub_001",
        simId="sim_custom",
        dryRun=True,
    ))
    assert out["simId"] == "sim_custom"


def test_sim_activate_raises_on_missing_iccid():
    import pytest
    with pytest.raises(ValueError, match="missing"):
        asyncio.run(T.task_telecom_sim_activate(subscriberId="sub_001", dryRun=True))


def test_service_provision_returns_ok():
    out = asyncio.run(T.task_telecom_service_provision(
        subscriberId="sub_001",
        serviceType="data",
        planId="plan_data_5g",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_service_provision_rejects_invalid_type():
    import pytest
    with pytest.raises(ValueError, match="unsupported serviceType"):
        asyncio.run(T.task_telecom_service_provision(
            subscriberId="sub_001",
            serviceType="invalid_xyz",
            planId="plan_a",
            dryRun=True,
        ))


def test_service_provision_all_valid_types():
    for stype in T.SERVICE_TYPES:
        out = asyncio.run(T.task_telecom_service_provision(
            subscriberId="sub_001",
            serviceType=stype,
            planId="plan_a",
            dryRun=True,
        ))
        assert out["ok"] is True


def test_usage_record_returns_ok():
    out = asyncio.run(T.task_telecom_usage_record(
        subscriberId="sub_001",
        serviceId="svc_001",
        usageType="data",
        units=1024.0,
        startedAt="2026-04-01T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_usage_record_rejects_negative_units():
    import pytest
    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(T.task_telecom_usage_record(
            subscriberId="sub_001",
            serviceId="svc_001",
            usageType="sms",
            units=-1.0,
            startedAt="2026-04-01T10:00:00Z",
            dryRun=True,
        ))


def test_usage_record_rejects_invalid_type():
    import pytest
    with pytest.raises(ValueError, match="unsupported usageType"):
        asyncio.run(T.task_telecom_usage_record(
            subscriberId="sub_001",
            serviceId="svc_001",
            usageType="fax",
            units=1.0,
            startedAt="2026-04-01T10:00:00Z",
            dryRun=True,
        ))


def test_billing_cycle_dry_run_returns_zero_amount():
    out = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_001",
        periodStart="2026-04-01",
        periodEnd="2026-04-30",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["totalAmount"] == 0.0
    assert out["status"] == "issued"


def test_billing_cycle_rejects_invalid_period():
    import pytest
    with pytest.raises(ValueError, match="after periodStart"):
        asyncio.run(T.task_telecom_billing_cycle(
            subscriberId="sub_001",
            periodStart="2026-04-30",
            periodEnd="2026-04-01",
            dryRun=True,
        ))


def test_billing_cycle_uses_provided_ids():
    out = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_001",
        periodStart="2026-03-01",
        periodEnd="2026-03-31",
        cycleId="cycle_mar",
        invoiceId="inv_mar_001",
        dryRun=True,
    ))
    assert out["invoiceId"] == "inv_mar_001"


def test_sla_escalate_returns_ok():
    out = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_001",
        breachType="latency",
        severity="major",
        observedAt="2026-04-29T12:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "open"
    assert out["vertexId"].startswith("at://")


def test_sla_escalate_rejects_invalid_severity():
    import pytest
    with pytest.raises(ValueError, match="unsupported severity"):
        asyncio.run(T.task_telecom_sla_escalate(
            serviceId="svc_001",
            breachType="latency",
            severity="extreme",
            observedAt="2026-04-29T12:00:00Z",
            dryRun=True,
        ))


def test_sla_escalate_all_valid_severities():
    for sev in T.SEVERITIES:
        out = asyncio.run(T.task_telecom_sla_escalate(
            serviceId="svc_001",
            breachType="packet_loss",
            severity=sev,
            observedAt="2026-04-29T09:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


def test_sla_escalate_numeric_fields():
    out = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_001",
        breachType="latency",
        severity="critical",
        observedAt="2026-04-29T10:00:00Z",
        metric="rtt_ms",
        observedValue=250.5,
        slaThreshold=100.0,
        dryRun=True,
    ))
    assert out["ok"] is True


def test_register_exposes_six_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    T.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.subscriber.onboard",
        "telecom.sim.activate",
        "telecom.service.provision",
        "telecom.usage.record",
        "telecom.billing.cycle",
        "telecom.sla.escalate",
    }


# ─── _today_iso ──────────────────────────────────────────────────────────────

def test_today_iso_returns_string() -> None:
    assert isinstance(T._today_iso(), str)


def test_today_iso_format() -> None:
    import re
    result = T._today_iso()
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", result)


def test_today_iso_consistent_within_call() -> None:
    a = T._today_iso()
    b = T._today_iso()
    # May differ at midnight but length always 10
    assert len(a) == 10
    assert len(b) == 10
