"""Pure-path tests for telecom sub-primitive modules.

Each module uses _require() + dryRun=True to avoid DB writes.
Modules covered: telecom_resource, telecom_oss, telecom_5g_security,
telecom_5gcore, telecom_nfv, telecom_li, telecom_oran, telecom_npn,
telecom_ntn, telecom_optical, telecom_supplier, telecom_mec,
telecom_ims, telecom_wlan, telecom_tsn.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

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


def _load(name: str):
    key = f"_tcm_{name}"
    if key not in sys.modules:
        src = _py_src / "kotodama" / "primitives" / f"{name}.py"
        real_db = sys.modules.get("kotodama.db_sync")
        sys.modules["kotodama.db_sync"] = _db_stub
        try:
            spec = importlib.util.spec_from_file_location(key, src)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[key] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        finally:
            if real_db is not None:
                sys.modules["kotodama.db_sync"] = real_db
    return sys.modules[key]


TR = _load("telecom_resource")
TOSS = _load("telecom_oss")
T5GS = _load("telecom_5g_security")
T5GC = _load("telecom_5gcore")
TNFV = _load("telecom_nfv")
TLI = _load("telecom_li")
TORAN = _load("telecom_oran")
TNPN = _load("telecom_npn")
TNTN = _load("telecom_ntn")
TOPT = _load("telecom_optical")
TSUP = _load("telecom_supplier")
TMEC = _load("telecom_mec")
TIMS = _load("telecom_ims")
TWLAN = _load("telecom_wlan")
TTSN = _load("telecom_tsn")


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_resource
# ═══════════════════════════════════════════════════════════════════════════════

def test_resource_spectrum_register_ok() -> None:
    result = asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="JP", band="700MHz", holderOrgId="org_ntt",
        validFrom="2026-01-01", validUntil="2031-01-01",
        lowMhz=700.0, highMhz=710.0, dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_spectrum_invalid_mhz_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TR.task_telecom_spectrum_register(
            jurisdiction="JP", band="700MHz", holderOrgId="org_ntt",
            validFrom="2026-01-01", validUntil="2031-01-01",
            lowMhz=710.0, highMhz=700.0, dryRun=True,
        ))


def test_resource_spectrum_missing_jurisdiction_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TR.task_telecom_spectrum_register(
            jurisdiction="", band="700MHz", holderOrgId="org_ntt",
            validFrom="2026-01-01", validUntil="2031-01-01",
            lowMhz=700.0, highMhz=710.0, dryRun=True,
        ))


def test_resource_spectrum_returns_dict() -> None:
    assert isinstance(asyncio.run(TR.task_telecom_spectrum_register(
        jurisdiction="JP", band="700MHz", holderOrgId="org_ntt",
        validFrom="2026-01-01", validUntil="2031-01-01",
        lowMhz=700.0, highMhz=710.0, dryRun=True,
    )), dict)


def test_resource_site_register_ok() -> None:
    result = asyncio.run(TR.task_telecom_site_register(
        name="Site Tokyo", jurisdiction="JP", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_site_missing_name_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TR.task_telecom_site_register(
            name="", jurisdiction="JP", dryRun=True,
        ))


def test_resource_ran_node_register_ok() -> None:
    result = asyncio.run(TR.task_telecom_ran_node_register(
        siteId="site_001", nodeType="gnb", generation="5g", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_ran_node_invalid_type_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TR.task_telecom_ran_node_register(
            siteId="site_001", nodeType="gNB_INVALID", generation="5g", dryRun=True,
        ))


def test_resource_asset_register_ok() -> None:
    result = asyncio.run(TR.task_telecom_asset_register(
        serialNumber="SN123456", assetKind="antenna", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_asset_missing_serial_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TR.task_telecom_asset_register(
            serialNumber="", assetKind="antenna", dryRun=True,
        ))


def test_resource_site_incident_ok() -> None:
    result = asyncio.run(TR.task_telecom_site_incident(
        siteId="site_001", incidentKind="power_loss",
        severity="major", detectedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_maintenance_schedule_ok() -> None:
    result = asyncio.run(TR.task_telecom_maintenance_schedule(
        maintenanceKind="preventive",
        plannedStart="2026-06-01T00:00:00Z",
        plannedEnd="2026-06-02T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_rma_request_ok() -> None:
    result = asyncio.run(TR.task_telecom_rma_request(
        assetId="asset_001", vendorOrgId="org_vendor",
        faultCategory="hardware", openedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_resource_kpi_audit_ok() -> None:
    result = asyncio.run(TR.task_telecom_kpi_audit(
        nodeId="node_001", metric="availability",
        sampledAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_oss
# ═══════════════════════════════════════════════════════════════════════════════

def test_oss_alarm_raise_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_raise(
        sourceKind="ranNode", sourceVid="at://node/001",
        alarmType="communications", severity="major",
        raisedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_alarm_raise_missing_source_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TOSS.task_telecom_oss_alarm_raise(
            sourceKind="", sourceVid="at://node/001",
            alarmType="communications", severity="major",
            raisedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_oss_alarm_raise_returns_dict() -> None:
    assert isinstance(asyncio.run(TOSS.task_telecom_oss_alarm_raise(
        sourceKind="ranNode", sourceVid="at://node/001",
        alarmType="equipment", severity="critical",
        raisedAt="2026-01-01T00:00:00Z", dryRun=True,
    )), dict)


def test_oss_alarm_correlate_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_correlate(
        parentAlarmId="alarm_001",
        childAlarmIds=["alarm_002", "alarm_003"],
        correlationKind="root_cause",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_alarm_suppress_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_suppress(
        alarmId="alarm_001", suppressionReason="maintenance",
        suppressUntil="2026-01-02T00:00:00Z", suppressedBy="operator_1",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_alarm_clear_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_alarm_clear(
        alarmId="alarm_001", clearKind="auto",
        clearedBy="system", clearedAt="2026-01-01T01:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_change_submit_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_change_submit(
        requesterId="eng_001", changeKind="normal",
        riskLevel="low", scopeKind="ranNode", scopeVid="at://node/001",
        summary="Upgrade firmware", plannedStart="2026-06-01T02:00:00Z",
        plannedEnd="2026-06-01T04:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_change_approve_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_change_approve(
        changeId="chg_001", decision="approved",
        approverId="mgr_001", approverRole="change_manager",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_config_snapshot_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_config_snapshot(
        scopeKind="ranNode", scopeVid="at://node/001",
        sourceSystem="ems", configHash="sha256:abc123",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oss_capacity_forecast_ok() -> None:
    result = asyncio.run(TOSS.task_telecom_oss_capacity_forecast(
        scopeKind="ranNode", scopeVid="at://node/001",
        metric="throughput", modelKind="arima",
        forecastHorizonDays=30, capacityLimit=1000.0,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_5g_security
# ═══════════════════════════════════════════════════════════════════════════════

def test_5gs_nwdaf_subscribe_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_nwdaf_subscribe(
        consumerNfId="amf_001", nwdafNfId="nwdaf_001",
        analyticsId="LOAD_LEVEL_INFORMATION",
        targetOfAnalyticsKind="nfInstance",
        targetOfAnalyticsVid="at://nf/amf001",
        reportingPeriodSeconds=60,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_nwdaf_subscribe_missing_consumer_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T5GS.task_telecom_nwdaf_subscribe(
            consumerNfId="", nwdafNfId="nwdaf_001",
            analyticsId="LOAD_LEVEL_INFORMATION",
            targetOfAnalyticsKind="nfInstance",
            targetOfAnalyticsVid="at://nf/amf001",
            reportingPeriodSeconds=60,
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_5gs_nwdaf_subscribe_returns_dict() -> None:
    assert isinstance(asyncio.run(T5GS.task_telecom_nwdaf_subscribe(
        consumerNfId="amf_001", nwdafNfId="nwdaf_001",
        analyticsId="LOAD_LEVEL_INFORMATION",
        targetOfAnalyticsKind="nfInstance",
        targetOfAnalyticsVid="at://nf/amf001",
        reportingPeriodSeconds=60,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    )), dict)


def test_5gs_nwdaf_result_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_nwdaf_result(
        subscriptionId="sub_001", analyticsId="LOAD_LEVEL_INFORMATION",
        sequenceNumber=1, payloadHash="sha256:payload123",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_scp_route_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_scp_route(
        scpNfId="scp_001", sourceNfId="amf_001", targetNfId="smf_001",
        targetServiceName="nsmf-pdusession", routingMode="direct_a",
        methodKind="POST", statusCode=200,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_scp_discover_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_scp_discover(
        scpNfId="scp_001", requesterNfId="amf_001",
        targetNfType="SMF", selectedNfId="smf_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_sepp_context_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_context(
        localSeppNfId="sepp_001", remoteSeppFqdn="sepp.remote.example",
        localPlmnId="44010", remotePlmnId="31000",
        agreementId="agr_001",
        n32CipherSuite="TLS_AES_128_GCM_SHA256",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_sepp_message_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_message(
        contextId="ctx_001", direction="inbound",
        n32Channel="n32f", payloadHash="sha256:def456",
        securityResult="verified",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_sepp_key_rotate_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_key_rotate(
        contextId="ctx_001", keyKind="tls_session",
        newKeyHash="sha256:newkey123",
        rotationReason="scheduled",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_sepp_trust_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_trust(
        contextId="ctx_001", negotiationKind="initial",
        outcome="agreed", observedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_5gcore
# ═══════════════════════════════════════════════════════════════════════════════

def test_5gc_nf_register_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_nf_register(
        nfType="AMF", plmnId="44010", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_nf_missing_type_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(T5GC.task_telecom_nf_register(
            nfType="", plmnId="44010", dryRun=True,
        ))


def test_5gc_nf_register_returns_dict() -> None:
    assert isinstance(asyncio.run(T5GC.task_telecom_nf_register(
        nfType="SMF", plmnId="44010", dryRun=True,
    )), dict)


def test_5gc_subscriber_profile_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_subscriber_profile_5g_register(
        subscriberId="sub_001", supi="imsi-440100123456789",
        dnnList=["internet", "ims"], dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_subscriber_authenticate_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_subscriber_authenticate(
        profileId="prof_001", supi="imsi-440100123456789",
        authMethod="5G-AKA", result="success",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_amf_register_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_amf_register(
        profileId="prof_001", registrationType="initial",
        ranNodeId="gnb_001", amfNfId="amf_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_slice_select_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_slice_select(
        registrationId="reg_001", profileId="prof_001",
        selectedSnssai="01:000001", nssfNfId="nssf_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_policy_apply_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_policy_apply(
        profileId="prof_001", snssai="01:000001",
        dnn="internet", chargingMethod="online",
        pcfNfId="pcf_001", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gc_session_establish_ok() -> None:
    result = asyncio.run(T5GC.task_telecom_session_establish(
        registrationId="reg_001", profileId="prof_001",
        snssai="01:000001", dnn="internet", sessionType="IPv4",
        smfNfId="smf_001", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_nfv
# ═══════════════════════════════════════════════════════════════════════════════

def test_nfv_nsd_onboard_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_nsd_onboard(
        vendor="Ericsson", name="NS-Descriptor", version="1.0.0",
        descriptorFormat="tosca",
        constituentVnfdIds=["vnfd_001", "vnfd_002"],
        packageHash="sha256:pkg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_nsd_onboard_missing_vendor_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TNFV.task_telecom_nfv_nsd_onboard(
            vendor="", name="NS-Descriptor", version="1.0.0",
            descriptorFormat="tosca",
            constituentVnfdIds=["vnfd_001"],
            packageHash="sha256:pkg001",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_nfv_vnfd_onboard_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnfd_onboard(
        vendor="Nokia", name="VNF-AMF", version="2.0.0",
        vnfKind="vm_vnf", descriptorFormat="tosca",
        deploymentFlavors=["small", "medium"],
        packageHash="sha256:vnfdpkg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_ns_instantiate_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_ns_instantiate(
        nsdId="nsd_001", nfvoNfId="nfvo_001",
        vimIds=["vim_001"], deploymentFlavor="small",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_vnf_instantiate_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_instantiate(
        nsId="ns_001", vnfdId="vnfd_001", vnfmNfId="vnfm_001",
        vimId="vim_001", deploymentFlavor="small",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_vnf_scale_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_scale(
        vnfId="vnf_001", scaleKind="horizontal",
        scaleDirection="scale_out", triggerKind="manual",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_vnf_heal_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_heal(
        vnfId="vnf_001", healCause="hw_failure",
        healKind="restart", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_sdn_flow_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_sdn_flow(
        sdnControllerId="sdn_001", southboundProtocol="openflow",
        switchDpid="00:11:22:33:44:55", tableId=0, priority=100,
        matchHash="sha256:match001", actionHash="sha256:action001",
        action="install", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_ns_terminate_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_ns_terminate(
        nsId="ns_001", terminationKind="graceful",
        terminatedBy="operator", terminatedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_li (Lawful Intercept)
# ═══════════════════════════════════════════════════════════════════════════════

def test_li_warrant_register_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_warrant_register(
        jurisdiction="JP", lawAuthorityId="auth_001",
        warrantNumber="WN-2026-001", warrantKind="court_order",
        interceptScope="iri_and_cc",
        validFrom="2026-01-01T00:00:00Z", validUntil="2026-12-31T23:59:59Z",
        lemfId="lemf_001", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_warrant_missing_jurisdiction_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TLI.task_telecom_li_warrant_register(
            jurisdiction="", lawAuthorityId="auth_001",
            warrantNumber="WN-2026-001", warrantKind="court_order",
            interceptScope="iri_and_cc",
            validFrom="2026-01-01T00:00:00Z", validUntil="2026-12-31T23:59:59Z",
            lemfId="lemf_001", dryRun=True,
        ))


def test_li_warrant_register_returns_dict() -> None:
    assert isinstance(asyncio.run(TLI.task_telecom_li_warrant_register(
        jurisdiction="JP", lawAuthorityId="auth_001",
        warrantNumber="WN-2026-001", warrantKind="court_order",
        interceptScope="iri_and_cc",
        validFrom="2026-01-01T00:00:00Z", validUntil="2026-12-31T23:59:59Z",
        lemfId="lemf_001", dryRun=True,
    )), dict)


def test_li_target_activate_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_target_activate(
        warrantId="warrant_001", identifierKind="msisdn",
        identifierValue="+819012345678",
        licfNfId="licf_001", x1ProvisionedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_li_target_deactivate_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_target_deactivate(
        targetId="target_001", deactivationReason="warrant_expired",
        deactivatedAt="2026-12-31T23:59:59Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_iri_deliver_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_iri_deliver(
        targetId="target_001", eventKind="session_establish",
        eventVid="at://event/001", x2Sequence=1,
        df2NfId="df2_001", lemfId="lemf_001",
        payloadHash="sha256:iripayload001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_cc_deliver_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_cc_deliver(
        targetId="target_001", contentKind="voice_rtp",
        x3Sequence=1, df3NfId="df3_001",
        lemfId="lemf_001", payloadHash="sha256:ccpayload001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_delivery_ack_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_delivery_ack(
        deliveryKind="iri", deliveryVid="at://delivery/001",
        lemfId="lemf_001", ackResult="received",
        ackedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_audit_access_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_audit_access(
        accessKind="read", accessor="analyst_001",
        accessorRole="li_operator", recordKind="warrant",
        recordVid="at://warrant/001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_warrant_close_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_warrant_close(
        warrantId="warrant_001", closureReason="expired",
        closedAt="2026-12-31T23:59:59Z",
        retentionUntil="2029-12-31", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_oran
# ═══════════════════════════════════════════════════════════════════════════════

def test_oran_smo_register_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_smo_register(
        vendor="Nokia", releaseVersion="7.0", plmnId="44010",
        nonRtRicEndpoint="http://nonrtric.example:8080",
        o1Endpoint="http://o1.example:830",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_smo_missing_vendor_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TORAN.task_telecom_oran_smo_register(
            vendor="", releaseVersion="7.0", plmnId="44010",
            nonRtRicEndpoint="http://nonrtric.example:8080",
            o1Endpoint="http://o1.example:830",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_oran_rapp_onboard_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_rapp_onboard(
        smoId="smo_001", vendor="Nokia", name="O1-Adapter",
        version="1.0.0", packageHash="sha256:pkg123",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_xapp_deploy_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_xapp_deploy(
        nearRtRicId="ric_001", vendor="Samsung",
        name="Near-RT-xApp", version="2.0.0",
        packageHash="sha256:xapppkg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_a1_policy_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_a1_policy(
        rappId="rapp_001", nearRtRicId="ric_001",
        policyTypeId="ORAN_TrafficSteeringPreference_2.0.0",
        useCase="qos_assurance",
        scopeKind="cellSite", scopeVid="at://cell/001",
        statementHash="sha256:stmt001", action="create",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_e2_subscribe_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_e2_subscribe(
        xappId="xapp_001", e2NodeId="e2node_001",
        ranFunctionId="RF001", serviceModel="e2sm-kpm",
        eventTriggerKind="periodic", actionKind="report",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_e2_indication_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_e2_indication(
        subscriptionId="sub_001", sequenceNumber=1,
        indicationType="report",
        headerHash="sha256:header001", messageHash="sha256:msg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_o1_config_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_o1_config(
        smoId="smo_001", targetKind="o-du",
        targetVid="at://odu/001",
        interfaceTransport="netconf",
        operation="merge", configHash="sha256:cfg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_o2_provision_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_o2_provision(
        smoId="smo_001", oCloudId="cloud_001",
        interfaceKind="o2-ims", resourceKind="compute_node",
        deploymentManager="k8s", packageHash="sha256:o2pkg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_npn (Non-Public Networks)
# ═══════════════════════════════════════════════════════════════════════════════

def test_npn_snpn_register_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_snpn_register(
        enterpriseOrgId="org_001", deploymentKind="snpn_isolated",
        plmnId="44010", nidValue="NID-001",
        jurisdiction="JP", validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_cag_register_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_cag_register(
        snpnId="snpn_001", cagValue="0001",
        displayName="Factory CAG", accessKind="cag_only",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_nid_register_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_nid_register(
        snpnId="snpn_001", nidValue="NID-001",
        assignmentKind="self", allocatedAt="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_pni_provision_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_pni_provision(
        enterpriseOrgId="org_001", hostingPlmnId="44010",
        snssai="01:000001", dnn="factory.local",
        isolationKind="dedicated_slice", slaTier="gold",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_id_map_upsert_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_id_map_upsert(
        profileId="prof_001", supi="imsi-440100123456789",
        gpsiKind="msisdn", gpsiValue="+819012345678",
        action="create",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_nsacf_enforce_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_nsacf_enforce(
        nsacfNfId="nsacf_001", snssai="01:000001",
        requesterNfId="amf_001", requestKind="registration",
        decision="admit", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_prose_provision_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_prose_provision(
        snpnId="snpn_001", communicationKind="one_to_one",
        prosePolicyHash="sha256:prosepol001",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_subscriber_register_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_subscriber_register(
        profileId="prof_001", snpnId="snpn_001",
        sponsoredByEnterpriseOrgId="org_001",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_ntn (Non-Terrestrial Networks)
# ═══════════════════════════════════════════════════════════════════════════════

def test_ntn_satellite_register_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_satellite_register(
        operatorOrgId="org_001", displayName="Sat-001",
        orbitClass="leo", frequencyBands=["Ka", "Ku"],
        serviceModes=["broadband_ntn"],
        launchedAt="2024-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_satellite_missing_operator_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TNTN.task_telecom_ntn_satellite_register(
            operatorOrgId="", displayName="Sat-001",
            orbitClass="leo", frequencyBands=["Ka"],
            serviceModes=["broadband_ntn"],
            launchedAt="2024-01-01T00:00:00Z",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_ntn_earth_station_register_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_earth_station_register(
        operatorOrgId="org_001", displayName="GS-Tokyo",
        stationKind="gateway", jurisdiction="JP",
        gatewayKind="ip_gateway",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_cell_provision_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_cell_provision(
        satelliteId="sat_001", ranNodeId="gnb_001",
        cellPattern="moving", plmnId="44010",
        frequencyBand="Ka", payloadKind="transparent",
        beamCount=4,
        validFrom="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_ephemeris_record_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_ephemeris_record(
        satelliteId="sat_001", sourceKind="celestrak",
        epochAt="2026-01-01T00:00:00Z",
        payloadFormat="tle", payloadHash="sha256:eph001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_handover_record_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_handover_record(
        profileId="prof_001", handoverKind="inter_satellite",
        sourceCellId="cell_001", targetCellId="cell_002",
        triggerKind="elevation_min",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_isl_provision_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_isl_provision(
        sourceSatelliteId="sat_001", targetSatelliteId="sat_002",
        linkKind="optical_lct", capacityMbps=100.0,
        validFrom="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_contact_record_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_contact_record(
        stationId="station_001", satelliteId="sat_001",
        contactKind="feeder_uplink",
        aosAt="2026-01-01T00:00:00Z", losAt="2026-01-01T00:10:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_partner_register_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_partner_register(
        operatorOrgId="org_001", agreementId="agr_001",
        constellationKind="leo_broadband", plmnId="44010",
        settlementMode="per_byte", validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_optical
# ═══════════════════════════════════════════════════════════════════════════════

def test_optical_domain_register_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_domain_register(
        ownerOrgId="org_001", displayName="Optical Domain Japan",
        controllerKind="transport_pce", jurisdiction="JP",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_ols_register_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_ols_register(
        domainId="domain_001", vendor="Ciena", model="6500",
        mustSpecVersion="ONF-Transport-API-2.1",
        supportedModulations=["qpsk", "16qam"],
        totalSpectrumGhz=4800.0, channelGridGhz=50.0,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_roadm_register_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_roadm_register(
        olsId="ols_001", displayName="ROADM-001",
        roadmKind="cdc_f", wssVendor="Finisar",
        degreeCount=4, addDropPortCount=8,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_fiber_register_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_fiber_register(
        olsId="ols_001", sourceRoadmId="roadm_001",
        targetRoadmId="roadm_002", fiberType="smf28",
        ownerOrgId="org_001",
        lengthKm=100.0, attenuationDb=0.2,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_alarm_record_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_alarm_record(
        sourceKind="roadm", sourceVid="at://roadm/001",
        alarmKind="los", severity="critical",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_pm_record_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_pm_record(
        sourceKind="roadm", sourceVid="at://roadm/001",
        metric="rx_power_dbm", unit="dBm",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_supplier
# ═══════════════════════════════════════════════════════════════════════════════

def test_supplier_interconnect_register_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_interconnect_register(
        peerOrgId="org_peer", peerKind="mvno",
        jurisdiction="JP", settlementCurrency="JPY",
        validFrom="2026-01-01", validUntil="2027-01-01", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_interconnect_missing_peer_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TSUP.task_telecom_interconnect_register(
            peerOrgId="", peerKind="mvno",
            jurisdiction="JP", settlementCurrency="JPY",
            validFrom="2026-01-01", validUntil="2027-01-01", dryRun=True,
        ))


def test_supplier_roaming_partner_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_partner(
        peerOrgId="org_peer", tadigCode="JPN01",
        agreementId="agr_001", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_roaming_tap_file_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_tap_file(
        partnerId="org_peer", fileType="tap",
        fileSequence=1, transferDate="2026-01-15",
        currency="JPY", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_roaming_settle_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_settle(
        partnerId="org_peer", periodStart="2026-01-01",
        periodEnd="2026-01-31", direction="receivable", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_number_range_register_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_number_range_register(
        jurisdiction="JP", countryCode="81",
        startMsisdn="+819000000000", endMsisdn="+819999999999",
        allocatedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_mnp_port_in_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_mnp_port_in(
        msisdn="+819012345678", subscriberId="sub_001",
        donorPartnerId="org_donor", requestedAt="2026-01-01T00:00:00Z",
        authCode="AUTH001",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_mnp_port_out_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_mnp_port_out(
        msisdn="+819012345678", subscriberId="sub_001",
        recipientPartnerId="org_recipient", requestedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_mec (Multi-access Edge Computing)
# ═══════════════════════════════════════════════════════════════════════════════

def test_mec_host_register_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_host_register(
        oCloudId="cloud_001", vendor="Intel",
        hostFqdn="mec.edge.example", edgeZone="tokyo",
        plmnId="44010",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_host_missing_vendor_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TMEC.task_telecom_mec_host_register(
            oCloudId="cloud_001", vendor="",
            hostFqdn="mec.edge.example", edgeZone="tokyo",
            plmnId="44010",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_mec_app_onboard_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_app_onboard(
        vendor="EdgeApp Co", name="VideoAnalytics",
        version="1.0.0", appDescriptor="{}",
        latencyClass="embb", packageHash="sha256:apppkg001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_eas_instantiate_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_instantiate(
        appPackageId="pkg_001", hostId="host_001",
        easProviderId="provider_001", easFqdn="eas.edge.example",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_eas_discover_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_discover(
        eesId="ees_001", requestingAcId="ac_001",
        ueIdHash="sha256:uehash",
        easProviderId="provider_001",
        requestedAppId="app_001", selectedEasId="eas_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_eas_relocate_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_relocate(
        easId="eas_001", fromHostId="host_001",
        toHostId="host_002", triggerKind="ue_mobility",
        acrMode="stateless",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_service_call_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_service_call(
        easId="eas_001", ueIdHash="sha256:uehash",
        methodKind="GET", statusCode=200,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_federation_register_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_federation_register(
        partnerOperatorId="op_partner", agreementId="agr_001",
        federationKind="bilateral", billingMode="settlement",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_eas_terminate_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_terminate(
        easId="eas_001", terminationKind="graceful",
        terminatedBy="operator", terminatedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_ims (IP Multimedia Subsystem)
# ═══════════════════════════════════════════════════════════════════════════════

def test_ims_subscription_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_ims_subscription(
        profileId="prof_001", subscriberId="sub_001",
        impi="sub@realm.example",
        impuList=["sip:sub@realm.example"],
        sCscfFqdn="scscf.realm.example",
        hssNfId="hss_001", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_subscription_missing_profile_id_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TIMS.task_telecom_ims_subscription(
            profileId="", subscriberId="sub_001",
            impi="sub@realm.example",
            impuList=["sip:sub@realm.example"],
            sCscfFqdn="scscf.realm.example",
            hssNfId="hss_001", dryRun=True,
        ))


def test_ims_sip_register_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_sip_register(
        subscriptionId="sub_001", impi="sub@realm.example",
        impu="sip:sub@realm.example",
        contactUri="sip:sub@192.168.1.1",
        pCscfFqdn="pcscf.realm.example",
        expiresSeconds=3600,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_voice_establish_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_establish(
        subscriberId="sub_001",
        callerImpu="sip:caller@realm.example",
        calleeImpu="sip:callee@realm.example",
        sessionVoltype="volte",
        sCscfNfId="scscf_001", tasNfId="tas_001",
        invitedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_voice_terminate_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_terminate(
        callId="call_001", releaseCause="normal",
        releasedBy="caller", releasedAt="2026-01-01T01:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_voice_supp_service_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_supp_service(
        subscriptionId="sub_001", serviceType="call_forward",
        action="activate", tasNfId="tas_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_voice_emergency_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_emergency(
        callId="call_001", emergencyService="police",
        jurisdiction="JP", psapId="psap_001",
        eCscfNfId="ecscf_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_voice_interconnect_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_interconnect(
        callId="call_001", agreementId="agr_001",
        partnerId="partner_001", gatewayKind="ibcf",
        gatewayNfId="ibcf_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_billing_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_ims_billing(
        callId="call_001", subscriberId="sub_001",
        eventKind="call_complete", ratingGroup=1,
        currency="JPY", chargingMethod="offline",
        startedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_wlan
# ═══════════════════════════════════════════════════════════════════════════════

def test_wlan_rcoi_register_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_rcoi_register(
        oiHex="0x004096", federation="wba_openroaming",
        identityProviderOrgId="org_001",
        profileKind="settled",
        validFrom="2026-01-01T00:00:00Z", validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_rcoi_missing_oi_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(TWLAN.task_telecom_wlan_rcoi_register(
            oiHex="", federation="wba_openroaming",
            identityProviderOrgId="org_001",
            profileKind="settled",
            validFrom="2026-01-01T00:00:00Z", validUntil="2027-01-01T00:00:00Z",
            observedAt="2026-01-01T00:00:00Z", dryRun=True,
        ))


def test_wlan_venue_register_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_venue_register(
        venueName="Tokyo Airport", venueGroup="assembly",
        venueType="airport", jurisdiction="JP",
        ssid="Passpoint-OPEN", advertisedRcoiIds=["rcoi_001"],
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_pps_provision_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_pps_provision(
        subscriberId="sub_001", identityProviderOrgId="org_001",
        eapMethod="EAP-AKA", credentialKind="sim",
        advertisedRcoiIds=["rcoi_001"],
        ppsMoHash="sha256:ppsmo001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_anqp_query_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_anqp_query(
        venueId="venue_001", ueMacHash="sha256:mac",
        gasProtocol="gas_anqp", queryElement="nai_realm",
        responseHash="sha256:resp001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_session_attach_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_session_attach(
        subscriberId="sub_001", ppsMoId="ppsmo_001",
        venueId="venue_001", rcoiId="rcoi_001",
        ueMacHash="sha256:mac001",
        eapMethod="EAP-AKA", attachedAt="2026-01-01T00:00:00Z",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_roaming_exchange_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_roaming_exchange(
        sessionId="sess_001", transportKind="radius",
        peerKind="home_idp", partnerOrgId="org_partner",
        messageKind="access_request",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_andsp_bridge_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_andsp_bridge(
        sessionId="sess_001", profileId="prof_001",
        atsssMode="mptcp", transitionKind="wifi_to_5g",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_roaming_settle_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_roaming_settle(
        partnerOrgId="org_partner", periodStart="2026-01-01",
        periodEnd="2026-01-31", dryRun=True,
    ))
    assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# telecom_tsn (Time-Sensitive Networking)
# ═══════════════════════════════════════════════════════════════════════════════

def test_tsn_domain_register_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_domain_register(
        ownerOrgId="org_001", displayName="TSN Domain A",
        profileKind="industrial_iec_iet",
        controllerKind="fully_centralized_cnc",
        gptpDomainNumber=0,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_bridge_register_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_bridge_register(
        domainId="domain_001", vendor="Cisco", model="IE3400",
        bridgeKind="transit_bridge", portCount=8,
        supportedShapers=["cbs", "tas"],
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_gptp_provision_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_gptp_provision(
        domainId="domain_001", grandmasterBridgeId="bridge_001",
        profileKind="802_1as_2020",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_stream_reserve_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_stream_reserve(
        domainId="domain_001", talkerEndpointId="ep_talker",
        listenerEndpointIds=["ep_listener_1"],
        reservationKind="qcc_centralized",
        maxFrameBytes=1500, framesPerInterval=1,
        intervalNs=250000, maxLatencyNs=2000000,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_shaper_apply_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_shaper_apply(
        bridgeId="bridge_001", shaperKind="cbs",
        action="apply", idleSlopeBps=1000000,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_frer_enable_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_frer_enable(
        streamId="stream_001", replicationKind="disjoint_paths",
        replicationCount=2,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_sync_deviation_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_sync_deviation(
        syncProfileId="sync_001", observedBridgeId="bridge_001",
        deviationKind="offset_drift",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_sla_breach_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_sla_breach(
        streamId="stream_001", breachKind="latency",
        severity="major", witnessBridgeId="bridge_001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True
