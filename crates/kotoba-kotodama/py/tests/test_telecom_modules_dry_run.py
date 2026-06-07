"""Pure-path tests for telecom_* module task functions using dryRun=True.

Each task's _insert() helper checks `if dry_run: return` before DB write,
making the tasks pure when dryRun=True is passed with valid required fields.

Covers:
- telecom_5gcore.py: 8 tasks (nf_register, subscriber_profile_5g_register, etc.)
- telecom_resource.py: 8 tasks (spectrum_register, site_register, etc.)
- telecom_oss.py: 8 tasks (alarm_raise, alarm_correlate, etc.)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_5gcore as TC5
from kotodama.primitives import telecom_resource as TR
from kotodama.primitives import telecom_oss as TOSS


# ══════════════════════════════════════════════════════════════════════════════
# telecom_5gcore — dryRun=True
# ══════════════════════════════════════════════════════════════════════════════

def test_5gcore_nf_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_nf_register(nfType="AMF", plmnId="44010", dryRun=True))
    assert isinstance(result, dict)


def test_5gcore_nf_register_dry_run_ok() -> None:
    result = asyncio.run(TC5.task_telecom_nf_register(nfType="AMF", plmnId="44010", dryRun=True))
    assert result["ok"] is True


def test_5gcore_nf_register_dry_run_has_vertex_id() -> None:
    result = asyncio.run(TC5.task_telecom_nf_register(nfType="AMF", plmnId="44010", dryRun=True))
    assert "vertexId" in result


def test_5gcore_subscriber_profile_5g_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_subscriber_profile_5g_register(
        subscriberId="sub-001", supi="imsi-44010-001", dnnList=["internet"], dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_subscriber_profile_5g_register_dry_run_ok() -> None:
    result = asyncio.run(TC5.task_telecom_subscriber_profile_5g_register(
        subscriberId="sub-001", supi="imsi-44010-001", dnnList=["internet"], dryRun=True,
    ))
    assert result["ok"] is True


def test_5gcore_subscriber_authenticate_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_subscriber_authenticate(
        profileId="prof-001", supi="imsi-44010-001", authMethod="5G-AKA",
        result="success", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_amf_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_amf_register(
        profileId="prof-001", registrationType="initial",
        ranNodeId="gnb-001", amfNfId="amf-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_amf_register_dry_run_ok() -> None:
    result = asyncio.run(TC5.task_telecom_amf_register(
        profileId="prof-001", registrationType="initial",
        ranNodeId="gnb-001", amfNfId="amf-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gcore_slice_select_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_slice_select(
        registrationId="reg-001", profileId="prof-001",
        selectedSnssai="01:000001", nssfNfId="nssf-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_policy_apply_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_policy_apply(
        profileId="prof-001", snssai="01:000001", dnn="internet",
        chargingMethod="online", pcfNfId="pcf-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_session_establish_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_session_establish(
        registrationId="reg-001", profileId="prof-001",
        snssai="01:000001", dnn="internet", sessionType="IPv4",
        smfNfId="smf-001", observedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_charging_emit_dry_run_returns_dict() -> None:
    result = asyncio.run(TC5.task_telecom_charging_emit(
        sessionId="sess-001", profileId="prof-001",
        subscriberId="sub-001", ratingGroup="1",
        currency="JPY", chargingMethod="online",
        startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gcore_charging_emit_dry_run_ok() -> None:
    result = asyncio.run(TC5.task_telecom_charging_emit(
        sessionId="sess-001", profileId="prof-001",
        subscriberId="sub-001", ratingGroup="1",
        currency="JPY", chargingMethod="online",
        startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ══════════════════════════════════════════════════════════════════════════════
# telecom_resource — dryRun=True
# ══════════════════════════════════════════════════════════════════════════════

def test_resource_spectrum_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="JP", band="700MHz", holderOrgId="org-001",
        lowMhz=700.0, highMhz=750.0,
        validFrom="2026-01-01", validUntil="2031-01-01", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_spectrum_register_dry_run_ok() -> None:
    result = asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="JP", band="700MHz", holderOrgId="org-001",
        lowMhz=700.0, highMhz=750.0,
        validFrom="2026-01-01", validUntil="2031-01-01", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_site_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_site_register(
        name="Site Tokyo-01", jurisdiction="JP", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_site_register_dry_run_ok() -> None:
    result = asyncio.run(TR.task_telecom_site_register(
        name="Site Tokyo-01", jurisdiction="JP", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_ran_node_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_ran_node_register(
        siteId="site-001", nodeType="gnb", generation="5g", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_ran_node_register_dry_run_ok() -> None:
    result = asyncio.run(TR.task_telecom_ran_node_register(
        siteId="site-001", nodeType="gnb", generation="5g", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_asset_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_asset_register(
        serialNumber="SN-12345", assetKind="router", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_asset_register_dry_run_ok() -> None:
    result = asyncio.run(TR.task_telecom_asset_register(
        serialNumber="SN-12345", assetKind="router", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_site_incident_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_site_incident(
        siteId="site-001", incidentKind="outage", severity="major",
        detectedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_maintenance_schedule_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_maintenance_schedule(
        maintenanceKind="preventive", plannedStart="2026-01-01T00:00:00Z",
        plannedEnd="2026-01-01T06:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_rma_request_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_rma_request(
        assetId="asset-001", vendorOrgId="vendor-001",
        faultCategory="hardware", openedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_resource_kpi_audit_dry_run_returns_dict() -> None:
    result = asyncio.run(TR.task_telecom_kpi_audit(
        nodeId="node-001", metric="availability_pct",
        sampledAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_oss — dryRun=True
# ══════════════════════════════════════════════════════════════════════════════

def test_oss_alarm_raise_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_raise(
        sourceKind="ranNode", sourceVid="at://site/node/001",
        alarmType="equipment", severity="major",
        raisedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_alarm_raise_dry_run_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_raise(
        sourceKind="ranNode", sourceVid="at://site/node/001",
        alarmType="equipment", severity="major",
        raisedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_alarm_correlate_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_correlate(
        parentAlarmId="alarm-001",
        childAlarmIds=["alarm-002", "alarm-003"],
        correlationKind="root_cause",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_alarm_suppress_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_suppress(
        alarmId="alarm-001", suppressionReason="maintenance",
        suppressUntil="2026-01-01T06:00:00Z", suppressedBy="ops-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_alarm_clear_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_clear(
        alarmId="alarm-001", clearKind="operator",
        clearedBy="ops-001", clearedAt="2026-01-01T06:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_change_submit_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_change_submit(
        requesterId="ops-001", changeKind="normal",
        riskLevel="low", scopeKind="ranNode",
        scopeVid="at://site/node/001", summary="patch config",
        plannedStart="2026-01-02T00:00:00Z",
        plannedEnd="2026-01-02T02:00:00Z",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_change_approve_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_change_approve(
        changeId="change-001", decision="approved",
        approverId="mgr-001", approverRole="change_manager",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_config_snapshot_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_config_snapshot(
        scopeKind="ranNode", scopeVid="at://site/node/001",
        sourceSystem="ems-v1", configHash="sha256:abc123",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oss_capacity_forecast_dry_run_returns_dict() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_capacity_forecast(
        scopeKind="ranNode", scopeVid="at://site/001",
        metric="prb_utilization", modelKind="linear",
        currentValue=60.0, forecastValue=80.0,
        forecastHorizonDays=30, capacityLimit=100.0,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)
