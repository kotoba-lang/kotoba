"""Tests for telecom_oss primitives (OSS alarm, change, config, capacity)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_oss as OSS  # noqa: E402


# ─── alarm.raise ─────────────────────────────────────────────────────────

def test_alarm_raise_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_alarm_raise(
        sourceKind="cellSite", sourceVid="at://site/1",
        alarmType="equipment", severity="major",
        raisedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_alarm_raise_rejects_invalid_source_kind():
    with pytest.raises(ValueError, match="unsupported sourceKind"):
        asyncio.run(OSS.task_telecom_oss_alarm_raise(
            sourceKind="rocket", sourceVid="at://v1",
            alarmType="equipment", severity="major",
            raisedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_raise_rejects_invalid_alarm_type():
    with pytest.raises(ValueError, match="unsupported alarmType"):
        asyncio.run(OSS.task_telecom_oss_alarm_raise(
            sourceKind="cellSite", sourceVid="at://v1",
            alarmType="unknown_type", severity="minor",
            raisedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_raise_rejects_invalid_severity():
    with pytest.raises(ValueError, match="unsupported severity"):
        asyncio.run(OSS.task_telecom_oss_alarm_raise(
            sourceKind="ranNode", sourceVid="at://v1",
            alarmType="communications", severity="extreme",
            raisedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_raise_all_valid_source_kinds():
    for kind in OSS.SOURCE_KINDS:
        out = asyncio.run(OSS.task_telecom_oss_alarm_raise(
            sourceKind=kind, sourceVid="at://v1",
            alarmType="equipment", severity="info",
            raisedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


def test_alarm_raise_all_valid_alarm_types():
    for at in OSS.ALARM_TYPES:
        out = asyncio.run(OSS.task_telecom_oss_alarm_raise(
            sourceKind="cellSite", sourceVid="at://v1",
            alarmType=at, severity="warning",
            raisedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


def test_alarm_raise_uses_provided_alarm_id():
    out = asyncio.run(OSS.task_telecom_oss_alarm_raise(
        sourceKind="service", sourceVid="at://svc/1",
        alarmType="communications", severity="critical",
        raisedAt="2026-04-29T10:00:00Z",
        alarmId="alm_custom_001",
        dryRun=True,
    ))
    assert out["alarmId"] == "alm_custom_001"


# ─── alarm.correlate ─────────────────────────────────────────────────────

def test_alarm_correlate_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_alarm_correlate(
        parentAlarmId="alm_001",
        childAlarmIds=["alm_002", "alm_003"],
        correlationKind="root_cause",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["childCount"] == 2


def test_alarm_correlate_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported correlationKind"):
        asyncio.run(OSS.task_telecom_oss_alarm_correlate(
            parentAlarmId="alm_001",
            childAlarmIds=["alm_002"],
            correlationKind="magic",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_correlate_rejects_empty_children():
    with pytest.raises(ValueError, match="non-empty list"):
        asyncio.run(OSS.task_telecom_oss_alarm_correlate(
            parentAlarmId="alm_001",
            childAlarmIds=[],
            correlationKind="root_cause",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── alarm.suppress ──────────────────────────────────────────────────────

def test_alarm_suppress_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_alarm_suppress(
        alarmId="alm_001",
        suppressionReason="maintenance",
        suppressUntil="2026-04-30T00:00:00Z",
        suppressedBy="ops-team",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "suppressed"


def test_alarm_suppress_rejects_invalid_reason():
    with pytest.raises(ValueError, match="unsupported suppressionReason"):
        asyncio.run(OSS.task_telecom_oss_alarm_suppress(
            alarmId="alm_001",
            suppressionReason="invalid_reason",
            suppressUntil="2026-04-30T00:00:00Z",
            suppressedBy="ops-team",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── alarm.clear ─────────────────────────────────────────────────────────

def test_alarm_clear_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_alarm_clear(
        alarmId="alm_001",
        clearKind="auto",
        clearedBy="nms-system",
        clearedAt="2026-04-29T12:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "cleared"


def test_alarm_clear_rejects_invalid_clear_kind():
    with pytest.raises(ValueError, match="unsupported clearKind"):
        asyncio.run(OSS.task_telecom_oss_alarm_clear(
            alarmId="alm_001",
            clearKind="unknown_kind",
            clearedBy="ops",
            clearedAt="2026-04-29T12:00:00Z",
            dryRun=True,
        ))


# ─── change.submit ───────────────────────────────────────────────────────

def test_change_submit_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_change_submit(
        requesterId="ops-team",
        changeKind="normal",
        riskLevel="low",
        scopeKind="ranNode",
        scopeVid="at://node/1",
        summary="Firmware upgrade for eNodeB",
        plannedStart="2026-04-30T02:00:00Z",
        plannedEnd="2026-04-30T04:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "submitted"


def test_change_submit_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported changeKind"):
        asyncio.run(OSS.task_telecom_oss_change_submit(
            requesterId="ops",
            changeKind="unknown",
            riskLevel="low",
            scopeKind="ranNode",
            scopeVid="at://v1",
            summary="Test",
            plannedStart="2026-04-30T02:00:00Z",
            plannedEnd="2026-04-30T04:00:00Z",
            dryRun=True,
        ))


def test_change_submit_all_valid_kinds():
    for kind in OSS.CHANGE_KINDS:
        out = asyncio.run(OSS.task_telecom_oss_change_submit(
            requesterId="ops",
            changeKind=kind,
            riskLevel="medium",
            scopeKind="cellSite",
            scopeVid="at://site/1",
            summary=f"Change {kind}",
            plannedStart="2026-04-30T02:00:00Z",
            plannedEnd="2026-04-30T04:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── change.approve ──────────────────────────────────────────────────────

def test_change_approve_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_change_approve(
        changeId="chg_001",
        decision="approved",
        approverId="mgr-001",
        approverRole="change_manager",
        observedAt="2026-04-29T15:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["changeStatus"] == "approved"


def test_change_approve_rejects_invalid_decision():
    with pytest.raises(ValueError, match="unsupported decision"):
        asyncio.run(OSS.task_telecom_oss_change_approve(
            changeId="chg_001",
            decision="pending",
            approverId="mgr-001",
            approverRole="change_manager",
            observedAt="2026-04-29T15:00:00Z",
            dryRun=True,
        ))


# ─── config.snapshot ─────────────────────────────────────────────────────

def test_config_snapshot_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_config_snapshot(
        scopeKind="ranNode",
        scopeVid="at://node/1",
        sourceSystem="netconf",
        configHash="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "captured"


def test_config_snapshot_rejects_invalid_hash_prefix():
    with pytest.raises(ValueError, match="configHash must be prefixed"):
        asyncio.run(OSS.task_telecom_oss_config_snapshot(
            scopeKind="ranNode",
            scopeVid="at://node/1",
            sourceSystem="netconf",
            configHash="md5:badprefix",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── capacity.forecast ───────────────────────────────────────────────────

def test_capacity_forecast_returns_ok():
    out = asyncio.run(OSS.task_telecom_oss_capacity_forecast(
        scopeKind="ranNode",
        scopeVid="at://node/1",
        metric="prb_utilization",
        currentValue=72.5,
        forecastValue=85.0,
        forecastHorizonDays=30,
        capacityLimit=90.0,
        modelKind="linear",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["breachPredicted"] is False


def test_capacity_forecast_detects_breach():
    out = asyncio.run(OSS.task_telecom_oss_capacity_forecast(
        scopeKind="cellSite",
        scopeVid="at://site/1",
        metric="traffic_load",
        currentValue=88.0,
        forecastValue=95.0,
        forecastHorizonDays=14,
        capacityLimit=90.0,
        modelKind="arima",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["breachPredicted"] is True


def test_capacity_forecast_rejects_invalid_model_kind():
    with pytest.raises(ValueError, match="unsupported modelKind"):
        asyncio.run(OSS.task_telecom_oss_capacity_forecast(
            scopeKind="ranNode",
            scopeVid="at://node/1",
            metric="throughput",
            currentValue=50.0,
            forecastValue=60.0,
            forecastHorizonDays=7,
            capacityLimit=100.0,
            modelKind="quantum",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    OSS.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.oss.alarm.raise",
        "telecom.oss.alarm.correlate",
        "telecom.oss.alarm.suppress",
        "telecom.oss.alarm.clear",
        "telecom.oss.change.submit",
        "telecom.oss.change.approve",
        "telecom.oss.config.snapshot",
        "telecom.oss.capacity.forecast",
    }
