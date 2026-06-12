"""Pure-path tests for primitives/telecom.py.

All task_* functions use _require() which raises ValueError for missing fields.
Tests use dryRun=True to skip DB writes.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_db_stub = types.ModuleType("kotodama.db_sync")


def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()


_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

_MOD_NAME = "_telecom_pure"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "telecom.py"
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

T = sys.modules[_MOD_NAME]

import pytest


# ─── task_telecom_subscriber_onboard ─────────────────────────────────────────

def test_subscriber_onboard_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="verified", planId="plan-basic", dryRun=True,
    ))
    assert result["ok"] is True


def test_subscriber_onboard_dry_run_returns_vertex_id() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="verified", planId="plan-basic", dryRun=True,
    ))
    assert "vertexId" in result


def test_subscriber_onboard_verified_kyc_status_active() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="verified", planId="plan-basic", dryRun=True,
    ))
    assert result["status"] == "active"


def test_subscriber_onboard_unverified_kyc_status_pending() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="pending", planId="plan-basic", dryRun=True,
    ))
    assert result["status"] == "pending"


def test_subscriber_onboard_missing_name_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_subscriber_onboard(
            customerName="", msisdn="+819012345678",
            kycStatus="verified", planId="plan-basic", dryRun=True,
        ))


def test_subscriber_onboard_missing_msisdn_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_subscriber_onboard(
            customerName="Test User", msisdn="",
            kycStatus="verified", planId="plan-basic", dryRun=True,
        ))


def test_subscriber_onboard_has_subscriber_id() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="verified", planId="plan-basic", dryRun=True,
    ))
    assert result["subscriberId"]


def test_subscriber_onboard_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_subscriber_onboard(
        customerName="Test User", msisdn="+819012345678",
        kycStatus="verified", planId="plan-basic", dryRun=True,
    ))
    assert isinstance(result, dict)


# ─── task_telecom_sim_activate ────────────────────────────────────────────────

def test_sim_activate_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_sim_activate(
        iccid="89014103211118510720", subscriberId="sub_abc123", dryRun=True,
    ))
    assert result["ok"] is True


def test_sim_activate_returns_sim_id() -> None:
    result = asyncio.run(T.task_telecom_sim_activate(
        iccid="89014103211118510720", subscriberId="sub_abc123", dryRun=True,
    ))
    assert result["simId"]


def test_sim_activate_status_active() -> None:
    result = asyncio.run(T.task_telecom_sim_activate(
        iccid="89014103211118510720", subscriberId="sub_abc123", dryRun=True,
    ))
    assert result["status"] == "active"


def test_sim_activate_missing_iccid_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_sim_activate(
            iccid="", subscriberId="sub_abc123", dryRun=True,
        ))


def test_sim_activate_missing_subscriber_id_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_sim_activate(
            iccid="89014103211118510720", subscriberId="", dryRun=True,
        ))


def test_sim_activate_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_sim_activate(
        iccid="89014103211118510720", subscriberId="sub_abc123", dryRun=True,
    ))
    assert isinstance(result, dict)


# ─── task_telecom_service_provision ──────────────────────────────────────────

def test_service_provision_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_service_provision(
        subscriberId="sub_abc", serviceType="data", planId="plan-basic", dryRun=True,
    ))
    assert result["ok"] is True


def test_service_provision_invalid_service_type_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_service_provision(
            subscriberId="sub_abc", serviceType="invalid_type", planId="plan-basic", dryRun=True,
        ))


def test_service_provision_voice_type() -> None:
    result = asyncio.run(T.task_telecom_service_provision(
        subscriberId="sub_abc", serviceType="voice", planId="plan-voice", dryRun=True,
    ))
    assert result["ok"] is True


def test_service_provision_status_active() -> None:
    result = asyncio.run(T.task_telecom_service_provision(
        subscriberId="sub_abc", serviceType="data", planId="plan-basic", dryRun=True,
    ))
    assert result["status"] == "active"


def test_service_provision_missing_subscriber_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_service_provision(
            subscriberId="", serviceType="data", planId="plan-basic", dryRun=True,
        ))


def test_service_provision_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_service_provision(
        subscriberId="sub_abc", serviceType="data", planId="plan-basic", dryRun=True,
    ))
    assert isinstance(result, dict)


# ─── task_telecom_usage_record ────────────────────────────────────────────────

def test_usage_record_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_usage_record(
        subscriberId="sub_abc", serviceId="svc_xyz", usageType="data",
        units=1024.0, startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_usage_record_invalid_usage_type_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_usage_record(
            subscriberId="sub_abc", serviceId="svc_xyz", usageType="invalid",
            units=1024.0, startedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_usage_record_negative_units_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_usage_record(
            subscriberId="sub_abc", serviceId="svc_xyz", usageType="data",
            units=-1.0, startedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_usage_record_status_recorded() -> None:
    result = asyncio.run(T.task_telecom_usage_record(
        subscriberId="sub_abc", serviceId="svc_xyz", usageType="sms",
        units=1.0, startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["status"] == "recorded"


def test_usage_record_missing_started_at_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_usage_record(
            subscriberId="sub_abc", serviceId="svc_xyz", usageType="data",
            units=1.0, startedAt="", dryRun=True,
        ))


def test_usage_record_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_usage_record(
        subscriberId="sub_abc", serviceId="svc_xyz", usageType="voice",
        units=60.0, startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ─── task_telecom_billing_cycle ───────────────────────────────────────────────

def test_billing_cycle_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_abc", periodStart="2026-01-01",
        periodEnd="2026-01-31", dryRun=True,
    ))
    assert result["ok"] is True


def test_billing_cycle_period_end_before_start_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_billing_cycle(
            subscriberId="sub_abc", periodStart="2026-01-31",
            periodEnd="2026-01-01", dryRun=True,
        ))


def test_billing_cycle_missing_subscriber_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_billing_cycle(
            subscriberId="", periodStart="2026-01-01",
            periodEnd="2026-01-31", dryRun=True,
        ))


def test_billing_cycle_has_invoice_id() -> None:
    result = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_abc", periodStart="2026-01-01",
        periodEnd="2026-01-31", dryRun=True,
    ))
    assert result["invoiceId"]


def test_billing_cycle_status_issued() -> None:
    result = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_abc", periodStart="2026-01-01",
        periodEnd="2026-01-31", dryRun=True,
    ))
    assert result["status"] == "issued"


def test_billing_cycle_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_billing_cycle(
        subscriberId="sub_abc", periodStart="2026-01-01",
        periodEnd="2026-01-31", dryRun=True,
    ))
    assert isinstance(result, dict)


# ─── task_telecom_sla_escalate ────────────────────────────────────────────────

def test_sla_escalate_dry_run_ok() -> None:
    result = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_xyz", breachType="latency", severity="major",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_sla_escalate_invalid_severity_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_sla_escalate(
            serviceId="svc_xyz", breachType="latency", severity="catastrophic",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_sla_escalate_missing_service_id_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T.task_telecom_sla_escalate(
            serviceId="", breachType="latency", severity="major",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_sla_escalate_has_breach_id() -> None:
    result = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_xyz", breachType="latency", severity="critical",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["breachId"]


def test_sla_escalate_minor_severity() -> None:
    result = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_xyz", breachType="packet_loss", severity="minor",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_sla_escalate_status_open() -> None:
    result = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_xyz", breachType="availability", severity="major",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["status"] == "open"


def test_sla_escalate_returns_dict() -> None:
    result = asyncio.run(T.task_telecom_sla_escalate(
        serviceId="svc_xyz", breachType="latency", severity="major",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)
