"""Tests for telecom_resource primitives (spectrum, site, RAN node, asset, etc.)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_resource as TR  # noqa: E402


# ─── telecom.spectrum.register ────────────────────────────────────────────

def test_spectrum_register_returns_ok():
    out = asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="JP", band="n78",
        lowMhz=3600.0, highMhz=3700.0,
        holderOrgId="org_ntt",
        validFrom="2026-01-01", validUntil="2030-12-31",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_spectrum_register_rejects_invalid_hz_range():
    with pytest.raises(ValueError, match="highMhz must be"):
        asyncio.run(TR.task_telecom_spectrum_register(
            jurisdiction="JP", band="n78",
            lowMhz=3700.0, highMhz=3600.0,
            holderOrgId="org_ntt",
            validFrom="2026-01-01", validUntil="2030-12-31",
            dryRun=True,
        ))


def test_spectrum_register_uses_provided_license_id():
    out = asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="US", band="n41",
        lowMhz=2496.0, highMhz=2690.0,
        holderOrgId="org_tmobile",
        validFrom="2026-01-01", validUntil="2035-12-31",
        licenseId="lic_custom_001",
        dryRun=True,
    ))
    assert out["licenseId"] == "lic_custom_001"


# ─── telecom.site.register ────────────────────────────────────────────────

def test_site_register_returns_ok():
    out = asyncio.run(TR.task_telecom_site_register(
        name="Tokyo Tower Site 1",
        latitude=35.6586, longitude=139.7454,
        jurisdiction="JP",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_site_register_raises_on_missing_name():
    with pytest.raises(ValueError, match="missing required field"):
        asyncio.run(TR.task_telecom_site_register(
            name="", jurisdiction="JP", dryRun=True
        ))


def test_site_register_uses_provided_site_id():
    out = asyncio.run(TR.task_telecom_site_register(
        name="Osaka Site",
        jurisdiction="JP",
        siteId="site_custom_001",
        dryRun=True,
    ))
    assert out["siteId"] == "site_custom_001"


# ─── telecom.ranNode.register ─────────────────────────────────────────────

def test_ran_node_register_returns_ok():
    out = asyncio.run(TR.task_telecom_ran_node_register(
        siteId="site_001",
        nodeType="gnb",
        generation="5g",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_ran_node_register_rejects_invalid_node_type():
    with pytest.raises(ValueError, match="unsupported nodeType"):
        asyncio.run(TR.task_telecom_ran_node_register(
            siteId="site_001",
            nodeType="unknown_node",
            generation="5g",
            dryRun=True,
        ))


def test_ran_node_register_rejects_invalid_generation():
    with pytest.raises(ValueError, match="unsupported generation"):
        asyncio.run(TR.task_telecom_ran_node_register(
            siteId="site_001",
            nodeType="gnb",
            generation="6g",
            dryRun=True,
        ))


def test_ran_node_register_all_valid_node_types():
    for nt in TR.NODE_TYPES:
        out = asyncio.run(TR.task_telecom_ran_node_register(
            siteId="site_001",
            nodeType=nt,
            generation="4g",
            dryRun=True,
        ))
        assert out["ok"] is True


def test_ran_node_register_all_valid_generations():
    for gen in TR.GENERATIONS:
        out = asyncio.run(TR.task_telecom_ran_node_register(
            siteId="site_001",
            nodeType="gnb",
            generation=gen,
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.asset.register ───────────────────────────────────────────────

def test_asset_register_returns_ok():
    out = asyncio.run(TR.task_telecom_asset_register(
        serialNumber="SN-ABC123456",
        assetKind="antenna",
        vendor="Ericsson",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "in_service"


def test_asset_register_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported assetKind"):
        asyncio.run(TR.task_telecom_asset_register(
            serialNumber="SN-001",
            assetKind="spaceship",
            dryRun=True,
        ))


def test_asset_register_all_valid_kinds():
    for kind in TR.ASSET_KINDS:
        out = asyncio.run(TR.task_telecom_asset_register(
            serialNumber=f"SN-{kind}-001",
            assetKind=kind,
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.site.incident ────────────────────────────────────────────────

def test_site_incident_returns_open():
    out = asyncio.run(TR.task_telecom_site_incident(
        siteId="site_001",
        incidentKind="outage",
        severity="critical",
        detectedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "open"


def test_site_incident_resolved_when_resolved_at_provided():
    out = asyncio.run(TR.task_telecom_site_incident(
        siteId="site_001",
        incidentKind="power_loss",
        severity="major",
        detectedAt="2026-04-29T10:00:00Z",
        resolvedAt="2026-04-29T12:00:00Z",
        dryRun=True,
    ))
    assert out["status"] == "resolved"


def test_site_incident_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported incidentKind"):
        asyncio.run(TR.task_telecom_site_incident(
            siteId="site_001",
            incidentKind="unknown",
            severity="minor",
            detectedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_site_incident_rejects_invalid_severity():
    with pytest.raises(ValueError, match="unsupported severity"):
        asyncio.run(TR.task_telecom_site_incident(
            siteId="site_001",
            incidentKind="outage",
            severity="extreme",
            detectedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.maintenance.schedule ────────────────────────────────────────

def test_maintenance_schedule_returns_ok():
    out = asyncio.run(TR.task_telecom_maintenance_schedule(
        maintenanceKind="preventive",
        plannedStart="2026-05-01T02:00:00Z",
        plannedEnd="2026-05-01T06:00:00Z",
        siteId="site_001",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "planned"


def test_maintenance_schedule_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported maintenanceKind"):
        asyncio.run(TR.task_telecom_maintenance_schedule(
            maintenanceKind="routine",
            plannedStart="2026-05-01T02:00:00Z",
            plannedEnd="2026-05-01T06:00:00Z",
            dryRun=True,
        ))


def test_maintenance_schedule_all_valid_kinds():
    for kind in TR.MAINT_KINDS:
        out = asyncio.run(TR.task_telecom_maintenance_schedule(
            maintenanceKind=kind,
            plannedStart="2026-05-01T02:00:00Z",
            plannedEnd="2026-05-01T06:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.rma.request ─────────────────────────────────────────────────

def test_rma_request_returns_open():
    out = asyncio.run(TR.task_telecom_rma_request(
        assetId="asset_001",
        vendorOrgId="ericsson",
        faultCategory="hardware",
        openedAt="2026-04-29T09:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "open"


def test_rma_request_rejects_invalid_fault_category():
    with pytest.raises(ValueError, match="unsupported faultCategory"):
        asyncio.run(TR.task_telecom_rma_request(
            assetId="asset_001",
            vendorOrgId="ericsson",
            faultCategory="unknown",
            openedAt="2026-04-29T09:00:00Z",
            dryRun=True,
        ))


def test_rma_request_all_valid_fault_categories():
    for cat in TR.FAULT_CATS:
        out = asyncio.run(TR.task_telecom_rma_request(
            assetId="asset_001",
            vendorOrgId="nokia",
            faultCategory=cat,
            openedAt="2026-04-29T09:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.kpi.audit ───────────────────────────────────────────────────

def test_kpi_audit_returns_ok_no_breach():
    out = asyncio.run(TR.task_telecom_kpi_audit(
        nodeId="node_001",
        metric="prb_utilization",
        value=65.0,
        sampledAt="2026-04-29T10:00:00Z",
        slaThreshold=80.0,
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["breach"] is False
    assert out["status"] == "recorded"


def test_kpi_audit_detects_breach():
    out = asyncio.run(TR.task_telecom_kpi_audit(
        nodeId="node_001",
        metric="latency_ms",
        value=95.0,
        sampledAt="2026-04-29T10:00:00Z",
        slaThreshold=80.0,
        dryRun=True,
    ))
    assert out["breach"] is True


def test_kpi_audit_no_threshold_no_breach():
    out = asyncio.run(TR.task_telecom_kpi_audit(
        nodeId="node_001",
        metric="cpu_utilization",
        value=99.9,
        sampledAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["breach"] is False


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    TR.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.spectrum.register",
        "telecom.site.register",
        "telecom.ranNode.register",
        "telecom.asset.register",
        "telecom.site.incident",
        "telecom.maintenance.schedule",
        "telecom.rma.request",
        "telecom.kpi.audit",
    }
