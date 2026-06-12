"""Pure-path tests for remaining telecom_* modules using dryRun=True.

Covers:
- telecom_5g_security.py: NWDAF, SCP, SEPP tasks
- telecom_esim.py: handle_* functions patched via noop cursor
- telecom_ims.py: IMS/VoLTE/VoNR tasks
- telecom_li.py: Lawful Intercept tasks
- telecom_mec.py: MEC host/edge tasks
- telecom_nfv.py: NFV/SDN tasks
- telecom_npn.py: Non-Public Network tasks
- telecom_ntn.py: Satellite NTN tasks
- telecom_optical.py: Optical network tasks
- telecom_oran.py: Open RAN tasks
- telecom_supplier.py: Supplier/Partner tasks
- telecom_tmf.py: TM Forum handle_* functions patched via noop cursor
- telecom_tsn.py: TSN tasks
- telecom_wlan.py: WLAN tasks
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_5g_security as T5GS
from kotodama.primitives import telecom_esim as TESIM
from kotodama.primitives import telecom_ims as TIMS
from kotodama.primitives import telecom_li as TLI
from kotodama.primitives import telecom_mec as TMEC
from kotodama.primitives import telecom_nfv as TNFV
from kotodama.primitives import telecom_npn as TNPN
from kotodama.primitives import telecom_ntn as TNTN
from kotodama.primitives import telecom_optical as TOPT
from kotodama.primitives import telecom_oran as TORAN
from kotodama.primitives import telecom_supplier as TSUP
from kotodama.primitives import telecom_tmf as TTMF
from kotodama.primitives import telecom_tsn as TTSN
from kotodama.primitives import telecom_wlan as TWLAN


def _noop_cursor_mock() -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cur.rowcount = 0
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


# ══════════════════════════════════════════════════════════════════════════════
# telecom_5g_security — NWDAF / SCP / SEPP
# ══════════════════════════════════════════════════════════════════════════════

def test_5gs_nwdaf_subscribe_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_nwdaf_subscribe(
        consumerNfId="amf-001", nwdafNfId="nwdaf-001",
        analyticsId="LOAD_LEVEL_INFORMATION",
        targetOfAnalyticsKind="nfInstance",
        targetOfAnalyticsVid="at://nf/001",
        reportingPeriodSeconds=60,
        accuracyRequirement="medium",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_nwdaf_subscribe_dry_run_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_nwdaf_subscribe(
        consumerNfId="amf-001", nwdafNfId="nwdaf-001",
        analyticsId="NETWORK_PERFORMANCE",
        targetOfAnalyticsKind="ranNode",
        targetOfAnalyticsVid="at://ran/001",
        reportingPeriodSeconds=30,
        accuracyRequirement="high",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_scp_route_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_scp_route(
        scpNfId="scp-001", sourceNfId="amf-001", targetNfId="udm-001",
        targetServiceName="nudm-sdm", routingMode="indirect_c",
        methodKind="GET", statusCode=200,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_scp_route_dry_run_ok() -> None:
    result = asyncio.run(T5GS.task_telecom_scp_route(
        scpNfId="scp-001", sourceNfId="smf-001", targetNfId="pcf-001",
        targetServiceName="npcf-smpolicycontrol", routingMode="direct_a",
        methodKind="POST", statusCode=201,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_5gs_scp_discover_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_scp_discover(
        scpNfId="scp-001", requesterNfId="amf-001",
        targetNfType="UDM", selectedNfId="udm-001",
        selectionStrategy="least_load",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_sepp_context_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_context(
        localSeppNfId="sepp-001", remoteSeppFqdn="sepp.partner.com",
        localPlmnId="44010", remotePlmnId="31000",
        agreementId="agree-001", n32CipherSuite="TLS_AES_128_GCM_SHA256",
        validUntil="2026-12-31T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_sepp_message_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_message(
        contextId="ctx-001", direction="outbound",
        n32Channel="n32f", payloadHash="sha256:abc123",
        securityResult="verified",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_sepp_key_rotate_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_key_rotate(
        contextId="ctx-001", keyKind="tls_session",
        newKeyHash="sha256:newkey", rotationReason="scheduled",
        validUntil="2026-12-31T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_5gs_sepp_trust_dry_run_returns_dict() -> None:
    result = asyncio.run(T5GS.task_telecom_sepp_trust(
        contextId="ctx-001", negotiationKind="initial",
        outcome="agreed", agreedCipherSuite="TLS_AES_128_GCM_SHA256",
        modificationPolicy="none",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_esim — patched sync cursor (handle_* pattern)
# ══════════════════════════════════════════════════════════════════════════════

def test_esim_handle_provision_euicc_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_provision_euicc({
            "euiccId": "euicc-001", "eid": "89044045125200000000000000",
            "smdsAddress": "smds.operator.com", "deviceKind": "smartphone",
            "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


def test_esim_handle_download_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_download_esim_profile({
            "downloadId": "dl-001", "eid": "89044045125200000000000000",
            "iccid": "8901001234567890000", "smdpAddress": "smdp.operator.com",
            "profileType": "telecom", "matchingId": "LPA:1$smdp$match-001",
            "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


def test_esim_handle_enable_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_enable_esim_profile({
            "operationId": "op-001", "eid": "89044045125200000000000000",
            "iccid": "8901001234567890000", "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


def test_esim_handle_disable_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_disable_esim_profile({
            "operationId": "op-001", "eid": "89044045125200000000000000",
            "iccid": "8901001234567890000", "disableReason": "userRequest",
            "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


def test_esim_handle_delete_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_delete_esim_profile({
            "operationId": "op-001", "eid": "89044045125200000000000000",
            "iccid": "8901001234567890000", "deleteReason": "contractTerminated",
            "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


def test_esim_handle_audit_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TESIM.sync_cursor = _noop_cursor_mock()
    try:
        result = TESIM.handle_audit_euicc_state({
            "auditId": "audit-001", "eid": "89044045125200000000000000",
            "profileCount": 2, "observedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TESIM.sync_cursor = _real


# ══════════════════════════════════════════════════════════════════════════════
# telecom_ims — IMS/VoLTE voice control plane
# ══════════════════════════════════════════════════════════════════════════════

def test_ims_subscription_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_ims_subscription(
        profileId="prof-001", subscriberId="sub-001",
        impi="user@ims.example.com",
        impuList=["sip:user@ims.example.com"],
        sCscfFqdn="scscf.ims.example.com", hssNfId="hss-001",
        dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_subscription_dry_run_ok() -> None:
    result = asyncio.run(TIMS.task_telecom_ims_subscription(
        profileId="prof-001", subscriberId="sub-001",
        impi="user@ims.example.com",
        impuList=["sip:user@ims.example.com"],
        sCscfFqdn="scscf.ims.example.com", hssNfId="hss-001",
        dryRun=True,
    ))
    assert result["ok"] is True


def test_ims_sip_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_sip_register(
        subscriptionId="sub-001", impi="user@ims.example.com",
        impu="sip:user@ims.example.com", contactUri="sip:user@192.168.0.1",
        pCscfFqdn="pcscf.ims.example.com", expiresSeconds=3600,
        accessNetwork="volte", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_voice_establish_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_establish(
        subscriberId="sub-001", callerImpu="sip:caller@ims.example.com",
        calleeImpu="sip:callee@ims.example.com",
        sessionVoltype="volte", sCscfNfId="scscf-001",
        tasNfId="tas-001", invitedAt="2026-01-01T00:00:00Z",
        codec="AMR-WB", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_voice_terminate_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_terminate(
        callId="call-001", releaseCause="normal",
        releasedBy="caller", releasedAt="2026-01-01T00:01:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_voice_supp_service_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_supp_service(
        subscriptionId="sub-001", serviceType="call_hold",
        action="activate", tasNfId="tas-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_voice_emergency_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_voice_emergency(
        callId="call-001", emergencyService="police",
        jurisdiction="JP", psapId="psap-001",
        eCscfNfId="ecscf-001", observedAt="2026-01-01T00:00:00Z",
        locationMethod="gps", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ims_billing_dry_run_returns_dict() -> None:
    result = asyncio.run(TIMS.task_telecom_ims_billing(
        callId="call-001", subscriberId="sub-001",
        eventKind="call_complete", ratingGroup="1",
        units=60.0, currency="JPY", amount=100.0,
        chargingMethod="online", startedAt="2026-01-01T00:00:00Z",
        unitOfMeasure="seconds", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_li — Lawful Intercept
# ══════════════════════════════════════════════════════════════════════════════

def test_li_warrant_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_warrant_register(
        jurisdiction="JP", lawAuthorityId="auth-001",
        warrantNumber="WR-2026-001", warrantKind="court_order",
        interceptScope="iri_only",
        validFrom="2026-01-01T00:00:00Z", validUntil="2026-06-01T00:00:00Z",
        lemfId="lemf-001", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_warrant_register_dry_run_ok() -> None:
    result = asyncio.run(TLI.task_telecom_li_warrant_register(
        jurisdiction="JP", lawAuthorityId="auth-001",
        warrantNumber="WR-2026-001", warrantKind="court_order",
        interceptScope="iri_only",
        validFrom="2026-01-01T00:00:00Z", validUntil="2026-06-01T00:00:00Z",
        lemfId="lemf-001", dryRun=True,
    ))
    assert result["ok"] is True


def test_li_target_activate_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_target_activate(
        warrantId="warrant-001", identifierKind="msisdn",
        identifierValue="09012345678", licfNfId="licf-001",
        x1ProvisionedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_target_deactivate_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_target_deactivate(
        targetId="target-001", deactivationReason="warrant_expired",
        deactivatedAt="2026-06-01T00:00:00Z", licfNfId="licf-001", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_iri_deliver_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_iri_deliver(
        targetId="target-001", eventKind="registration",
        eventVid="at://event/001", x2Sequence=1,
        df2NfId="df2-001", lemfId="lemf-001",
        payloadHash="sha256:abc123", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_cc_deliver_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_cc_deliver(
        targetId="target-001", contentKind="voice_rtp",
        x3Sequence=1, df3NfId="df3-001", lemfId="lemf-001",
        payloadHash="sha256:abc123", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_delivery_ack_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_delivery_ack(
        deliveryKind="iri", deliveryVid="at://iri/001",
        lemfId="lemf-001", ackResult="received",
        ackedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_audit_access_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_audit_access(
        accessKind="read", accessor="ops-001",
        accessorRole="li_operator", recordKind="warrant",
        recordVid="at://warrant/001", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_li_warrant_close_dry_run_returns_dict() -> None:
    result = asyncio.run(TLI.task_telecom_li_warrant_close(
        warrantId="warrant-001", closureReason="expired",
        closedAt="2026-06-01T00:00:00Z",
        retentionUntil="2028-06-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_mec — MEC host / edge
# ══════════════════════════════════════════════════════════════════════════════

def test_mec_host_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_host_register(
        oCloudId="ocloud-001", vendor="etzhayyim", hostFqdn="mec.host.example.com",
        edgeZone="tokyo-east", plmnId="44010",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_host_register_dry_run_ok() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_host_register(
        oCloudId="ocloud-001", vendor="etzhayyim", hostFqdn="mec.host.example.com",
        edgeZone="tokyo-east", plmnId="44010",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_mec_app_onboard_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_app_onboard(
        vendor="etzhayyim", name="VideoAnalytics", version="1.0.0",
        appDescriptor="tosca", latencyClass="urllc",
        packageHash="sha256:pkghash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_eas_instantiate_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_instantiate(
        hostId="mec-host-001", appPackageId="pkg-001",
        easProviderId="prov-001", easFqdn="eas.example.com",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_eas_discover_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_discover(
        eesId="ees-001", requestingAcId="ac-001",
        ueIdHash="sha256:uehash001",
        easProviderId="prov-001", requestedAppId="app-001",
        selectedEasId="eas-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_eas_relocate_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_relocate(
        easId="eas-001", fromHostId="host-001",
        toHostId="host-002",
        triggerKind="ue_mobility", acrMode="stateless",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_service_call_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_service_call(
        easId="eas-001", ueIdHash="sha256:uehash001",
        methodKind="GET", statusCode=200,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_federation_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_federation_register(
        partnerOperatorId="oper-001", agreementId="agr-001",
        federationKind="bilateral", billingMode="settlement",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_mec_eas_terminate_dry_run_returns_dict() -> None:
    result = asyncio.run(TMEC.task_telecom_mec_eas_terminate(
        easId="eas-001", terminationKind="graceful",
        terminatedBy="ops-001",
        terminatedAt="2026-01-01T01:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_nfv — NFV/SDN
# ══════════════════════════════════════════════════════════════════════════════

def test_nfv_nsd_onboard_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_nsd_onboard(
        vendor="etzhayyim", name="5G-Core-NS", version="1.0.0",
        descriptorFormat="tosca", constituentVnfdIds=["vnfd-001"],
        packageHash="sha256:pkghash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_nsd_onboard_dry_run_ok() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_nsd_onboard(
        vendor="etzhayyim", name="5G-Core-NS", version="1.0.0",
        descriptorFormat="tosca", constituentVnfdIds=["vnfd-001"],
        packageHash="sha256:pkghash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_nfv_vnfd_onboard_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnfd_onboard(
        vendor="etzhayyim", name="UPF-VNF", version="1.0.0",
        vnfKind="container_cnf", descriptorFormat="helm",
        deploymentFlavors=["small"],
        packageHash="sha256:vnfdhash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_ns_instantiate_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_ns_instantiate(
        nsdId="nsd-001", nfvoNfId="nfvo-001", vimIds=["vim-001"],
        deploymentFlavor="basic",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_vnf_instantiate_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_instantiate(
        nsId="ns-001", vnfdId="vnfd-001", vnfmNfId="vnfm-001",
        vimId="vim-001", deploymentFlavor="basic",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_vnf_scale_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_scale(
        vnfId="vnf-001", scaleKind="horizontal",
        scaleDirection="scale_out", triggerKind="manual",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_vnf_heal_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_vnf_heal(
        vnfId="vnf-001", healCause="sw_failure",
        healKind="restart", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_sdn_flow_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_sdn_flow(
        sdnControllerId="ctrl-001", southboundProtocol="openflow",
        switchDpid="dp-001",
        matchHash="sha256:matchhash01", actionHash="sha256:actionhash1",
        action="install", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_nfv_ns_terminate_dry_run_returns_dict() -> None:
    result = asyncio.run(TNFV.task_telecom_nfv_ns_terminate(
        nsId="ns-001", terminationKind="graceful",
        terminatedBy="ops-001",
        terminatedAt="2026-01-01T01:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_npn — Non-Public Networks
# ══════════════════════════════════════════════════════════════════════════════

def test_npn_snpn_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_snpn_register(
        enterpriseOrgId="org-001", deploymentKind="snpn_isolated",
        plmnId="44010", nidValue="NID001", jurisdiction="JP",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_npn_snpn_register_dry_run_ok() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_snpn_register(
        enterpriseOrgId="org-001", deploymentKind="snpn_isolated",
        plmnId="44010", nidValue="NID001", jurisdiction="JP",
        validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_npn_cag_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_cag_register(
        snpnId="snpn-001", cagValue="CAG001", displayName="Factory Floor",
        accessKind="cag_only", observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_npn_nid_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_nid_register(
        snpnId="snpn-001", nidValue="NID002",
        assignmentKind="self",
        allocatedAt="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_npn_pni_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TNPN.task_telecom_npn_pni_provision(
        enterpriseOrgId="org-001", hostingPlmnId="44010",
        snssai="01:000001", dnn="internet", isolationKind="dedicated_dnn",
        slaTier="gold", validUntil="2027-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_ntn — Satellite NTN
# ══════════════════════════════════════════════════════════════════════════════

def test_ntn_satellite_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_satellite_register(
        operatorOrgId="op-001", displayName="etzhayyim-SAT-1",
        orbitClass="leo", frequencyBands=["Ka"],
        serviceModes=["broadband_ntn"],
        launchedAt="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ntn_satellite_register_dry_run_ok() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_satellite_register(
        operatorOrgId="op-001", displayName="etzhayyim-SAT-1",
        orbitClass="leo", frequencyBands=["Ka"],
        serviceModes=["broadband_ntn"],
        launchedAt="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_ntn_earth_station_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_earth_station_register(
        operatorOrgId="op-001", displayName="Tokyo Gateway",
        stationKind="gateway", latitude=35.0, longitude=139.0,
        jurisdiction="JP", gatewayKind="ip_gateway",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ntn_cell_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_cell_provision(
        satelliteId="sat-001", ranNodeId="gnb-001",
        cellPattern="earth_fixed", plmnId="44010",
        frequencyBand="S-band", payloadKind="transparent",
        beamCount=4, validFrom="2026-01-01T00:00:00Z",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_ntn_ephemeris_record_dry_run_returns_dict() -> None:
    result = asyncio.run(TNTN.task_telecom_ntn_ephemeris_record(
        satelliteId="sat-001", sourceKind="spacetrack",
        epochAt="2026-01-01T00:00:00Z", payloadFormat="tle",
        payloadHash="sha256:ephhash001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_optical — Optical network
# ══════════════════════════════════════════════════════════════════════════════

def test_optical_domain_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_domain_register(
        ownerOrgId="org-001", displayName="Tokyo Optical Domain",
        controllerKind="transport_pce", jurisdiction="JP",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_optical_domain_register_dry_run_ok() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_domain_register(
        ownerOrgId="org-001", displayName="Tokyo Optical Domain",
        controllerKind="transport_pce", jurisdiction="JP",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_optical_ols_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_ols_register(
        domainId="domain-001", vendor="Ciena", model="WaveServer 5",
        mustSpecVersion="1.0", totalSpectrumGhz=4800.0,
        channelGridGhz=50.0, supportedModulations=["qpsk", "16qam"],
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_optical_roadm_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_roadm_register(
        olsId="ols-001", displayName="Tokyo ROADM-1",
        roadmKind="cdc_f", wssVendor="Finisar",
        degreeCount=8, addDropPortCount=16,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_optical_fiber_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_fiber_register(
        olsId="ols-001", sourceRoadmId="roadm-001", targetRoadmId="roadm-002",
        fiberType="smf28", lengthKm=100.0, attenuationDb=0.2,
        ownerOrgId="org-001",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_optical_dwdm_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_dwdm_provision(
        olsId="ols-001", sourceRoadmId="roadm-001", targetRoadmId="roadm-002",
        centerFrequencyGhz=193100.0, bandwidthGhz=50.0,
        modulation="qpsk", lineRateGbps=100.0,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_optical_alarm_record_dry_run_returns_dict() -> None:
    result = asyncio.run(TOPT.task_telecom_opt_alarm_record(
        sourceKind="ols", sourceVid="at://ols/001",
        alarmKind="los", severity="major",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_oran — Open RAN
# ══════════════════════════════════════════════════════════════════════════════

def test_oran_smo_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_smo_register(
        vendor="etzhayyim", releaseVersion="O-RAN 1.0",
        plmnId="44010", nonRtRicEndpoint="https://nonrtric.example.com",
        o1Endpoint="https://o1.example.com",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_smo_register_dry_run_ok() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_smo_register(
        vendor="etzhayyim", releaseVersion="O-RAN 1.0",
        plmnId="44010", nonRtRicEndpoint="https://nonrtric.example.com",
        o1Endpoint="https://o1.example.com",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_oran_rapp_onboard_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_rapp_onboard(
        smoId="smo-001", vendor="etzhayyim", name="QoS-rApp", version="1.0.0",
        packageHash="sha256:rapphash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_xapp_deploy_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_xapp_deploy(
        nearRtRicId="ric-001", vendor="etzhayyim", name="TS-xApp", version="1.0.0",
        packageHash="sha256:xapphash",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_a1_policy_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_a1_policy(
        rappId="rapp-001", nearRtRicId="ric-001",
        policyTypeId="qos_type_1", useCase="qos_assurance",
        scopeKind="snssai", scopeVid="at://snssai/001",
        statementHash="sha256:stmthash1", action="create",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_e2_subscribe_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_e2_subscribe(
        xappId="xapp-001", e2NodeId="gnb-001",
        ranFunctionId="rf-001", serviceModel="e2sm-kpm",
        eventTriggerKind="periodic", actionKind="report",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_o1_config_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_o1_config(
        smoId="smo-001", targetKind="o-du",
        targetVid="at://o-du/001", interfaceTransport="netconf",
        operation="merge", configHash="sha256:cfghash01",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_oran_o2_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TORAN.task_telecom_oran_o2_provision(
        smoId="smo-001", oCloudId="ocloud-001",
        interfaceKind="o2-ims", resourceKind="compute_node",
        deploymentManager="k8s",
        packageHash="sha256:pkghash01",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_supplier — Supplier/Partner
# ══════════════════════════════════════════════════════════════════════════════

def test_supplier_interconnect_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_interconnect_register(
        peerOrgId="peer-001", peerKind="mno",
        jurisdiction="JP", settlementCurrency="JPY",
        validFrom="2026-01-01", validUntil="2027-01-01", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_supplier_interconnect_register_dry_run_ok() -> None:
    result = asyncio.run(TSUP.task_telecom_interconnect_register(
        peerOrgId="peer-001", peerKind="mno",
        jurisdiction="JP", settlementCurrency="JPY",
        validFrom="2026-01-01", validUntil="2027-01-01", dryRun=True,
    ))
    assert result["ok"] is True


def test_supplier_roaming_partner_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_partner(
        peerOrgId="partner-001", tadigCode="JPNKT",
        agreementId="agree-001", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_supplier_tap_file_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_tap_file(
        partnerId="partner-001", fileType="tap",
        fileSequence=1, transferDate="2026-01-01",
        currency="JPY", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_supplier_roaming_settle_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_roaming_settle(
        partnerId="partner-001", periodStart="2026-01-01",
        periodEnd="2026-01-31", direction="payable",
        currency="JPY", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_supplier_mnp_port_in_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_mnp_port_in(
        msisdn="09012345678", subscriberId="sub-001",
        donorPartnerId="op-001",
        requestedAt="2026-01-01T00:00:00Z",
        authCode="AUTH-ABC-123", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_supplier_mnp_port_out_dry_run_returns_dict() -> None:
    result = asyncio.run(TSUP.task_telecom_mnp_port_out(
        msisdn="09012345678", subscriberId="sub-001",
        recipientPartnerId="op-002",
        requestedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_tmf — TM Forum (handle_* sync pattern, patched)
# ══════════════════════════════════════════════════════════════════════════════

def test_tmf_handle_product_offering_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TTMF.sync_cursor = _noop_cursor_mock()
    try:
        result = TTMF.handle_publish_product_offering({
            "offeringId": "offer-001", "catalogId": "cat-001",
            "name": "5G Plan S", "lifecycleStatus": "Active",
            "validFrom": "2026-01-01",
        })
        assert isinstance(result, dict)
    finally:
        TTMF.sync_cursor = _real


def test_tmf_handle_product_order_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TTMF.sync_cursor = _noop_cursor_mock()
    try:
        result = TTMF.handle_submit_product_order({
            "productOrderId": "order-001", "accountId": "acct-001",
            "orderKind": "add",
        })
        assert isinstance(result, dict)
    finally:
        TTMF.sync_cursor = _real


def test_tmf_handle_customer_account_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TTMF.sync_cursor = _noop_cursor_mock()
    try:
        result = TTMF.handle_register_customer_account({
            "accountId": "acct-001",
            "customerKind": "individual", "accountKind": "postpaid",
        })
        assert isinstance(result, dict)
    finally:
        TTMF.sync_cursor = _real


def test_tmf_handle_service_order_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TTMF.sync_cursor = _noop_cursor_mock()
    try:
        result = TTMF.handle_submit_service_order({
            "serviceOrderId": "svc-order-001", "productOrderId": "order-001",
            "serviceType": "connectivity", "orderKind": "add",
            "lifecycleStatus": "acknowledged",
            "orderedAt": "2026-01-01T00:00:00Z",
        })
        assert isinstance(result, dict)
    finally:
        TTMF.sync_cursor = _real


def test_tmf_handle_service_activation_patched() -> None:
    from kotodama.db_sync import sync_cursor as _real
    TTMF.sync_cursor = _noop_cursor_mock()
    try:
        result = TTMF.handle_activate_service_instance({
            "activationId": "act-001", "serviceOrderId": "svc-order-001",
            "serviceInstanceKind": "connectivity", "action": "activate",
        })
        assert isinstance(result, dict)
    finally:
        TTMF.sync_cursor = _real


# ══════════════════════════════════════════════════════════════════════════════
# telecom_tsn — TSN
# ══════════════════════════════════════════════════════════════════════════════

def test_tsn_domain_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_domain_register(
        ownerOrgId="org-001", displayName="Factory TSN Domain",
        profileKind="industrial_iec_iet",
        controllerKind="fully_centralized_cnc",
        gptpDomainNumber=0, observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_tsn_domain_register_dry_run_ok() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_domain_register(
        ownerOrgId="org-001", displayName="Factory TSN Domain",
        profileKind="industrial_iec_iet",
        controllerKind="fully_centralized_cnc",
        gptpDomainNumber=0, observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_tsn_bridge_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_bridge_register(
        domainId="domain-001", vendor="Cisco", model="TSN-5000",
        bridgeKind="transit_bridge", portCount=8,
        supportedShapers=["tas"],
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_tsn_gptp_provision_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_gptp_provision(
        domainId="domain-001", grandmasterBridgeId="bridge-001",
        profileKind="802_1as_2020",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_tsn_stream_reserve_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_stream_reserve(
        domainId="domain-001", talkerEndpointId="bridge-001",
        listenerEndpointIds=["bridge-002"],
        reservationKind="srp_legacy",
        maxFrameBytes=1500, framesPerInterval=1,
        intervalNs=1000000, maxLatencyNs=1000000,
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_tsn_shaper_apply_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_shaper_apply(
        bridgeId="bridge-001", shaperKind="strict_priority",
        action="apply",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_tsn_sync_deviation_dry_run_returns_dict() -> None:
    result = asyncio.run(TTSN.task_telecom_tsn_sync_deviation(
        syncProfileId="sync-prof-001", observedBridgeId="bridge-001",
        deviationKind="offset_drift",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# telecom_wlan — WBA OpenRoaming / Hotspot 2.0
# ══════════════════════════════════════════════════════════════════════════════

def test_wlan_rcoi_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_rcoi_register(
        oiHex="AABBCC", federation="wba_openroaming",
        identityProviderOrgId="org-001", profileKind="settled",
        validFrom="2026-01-01", validUntil="2027-01-01",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_wlan_rcoi_register_dry_run_ok() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_rcoi_register(
        oiHex="AABBCC", federation="wba_openroaming",
        identityProviderOrgId="org-001", profileKind="settled",
        validFrom="2026-01-01", validUntil="2027-01-01",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert result["ok"] is True


def test_wlan_venue_register_dry_run_returns_dict() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_venue_register(
        venueName="Tokyo Station", venueGroup="business",
        venueType="office", jurisdiction="JP", ssid="etzhayyim-WIFI",
        advertisedRcoiIds=["rcoi-001"], osuKind="none",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_wlan_anqp_query_dry_run_returns_dict() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_anqp_query(
        venueId="venue-001", ueMacHash="sha256:uemac001",
        gasProtocol="gas_anqp", queryElement="nai_realm",
        responseHash="sha256:resphash1",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_wlan_session_attach_dry_run_returns_dict() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_session_attach(
        subscriberId="sub-001", ppsMoId="pps-001",
        venueId="venue-001", rcoiId="rcoi-001",
        ueMacHash="sha256:uemac001", eapMethod="EAP-AKA",
        attachedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)


def test_wlan_roaming_exchange_dry_run_returns_dict() -> None:
    result = asyncio.run(TWLAN.task_telecom_wlan_roaming_exchange(
        sessionId="sess-001", transportKind="radius",
        peerKind="home_idp", partnerOrgId="org-001",
        messageKind="access_request",
        observedAt="2026-01-01T00:00:00Z", dryRun=True,
    ))
    assert isinstance(result, dict)
