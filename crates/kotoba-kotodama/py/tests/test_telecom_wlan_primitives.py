"""Tests for telecom_wlan primitives (WBA OpenRoaming + Hotspot 2.0)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_wlan as WL  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.wlan.rcoi.register ──────────────────────────────────────────

def test_rcoi_register_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_rcoi_register(
        oiHex="001BC5", federation="wba_openroaming",
        identityProviderOrgId="idp_001", profileKind="settled",
        validFrom="2026-04-29", validUntil="2027-04-29",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_rcoi_register_rejects_invalid_federation():
    with pytest.raises(ValueError, match="unsupported federation"):
        asyncio.run(WL.task_telecom_wlan_rcoi_register(
            oiHex="001BC5", federation="mvno_roaming",
            identityProviderOrgId="idp_001", profileKind="settled",
            validFrom="2026-04-29", validUntil="2027-04-29",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_rcoi_register_rejects_invalid_profile_kind():
    with pytest.raises(ValueError, match="unsupported profileKind"):
        asyncio.run(WL.task_telecom_wlan_rcoi_register(
            oiHex="001BC5", federation="eduroam",
            identityProviderOrgId="idp_001", profileKind="premium",
            validFrom="2026-04-29", validUntil="2027-04-29",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.venue.register ─────────────────────────────────────────

def test_venue_register_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_venue_register(
        venueName="Tokyo Station WiFi", venueGroup="business",
        venueType="7", jurisdiction="JP", ssid="openroaming",
        advertisedRcoiIds=["rcoi_001", "rcoi_002"],
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_venue_register_rejects_invalid_venue_group():
    with pytest.raises(ValueError, match="unsupported venueGroup"):
        asyncio.run(WL.task_telecom_wlan_venue_register(
            venueName="Bad Venue", venueGroup="commercial",
            venueType="1", jurisdiction="JP", ssid="openroaming",
            advertisedRcoiIds=["rcoi_001"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_venue_register_rejects_empty_rcoi_ids():
    with pytest.raises(ValueError, match="advertisedRcoiIds must be a non-empty list"):
        asyncio.run(WL.task_telecom_wlan_venue_register(
            venueName="Empty RCOI Venue", venueGroup="outdoor",
            venueType="2", jurisdiction="JP", ssid="openroaming",
            advertisedRcoiIds=[],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_venue_register_rejects_invalid_osu_kind():
    with pytest.raises(ValueError, match="unsupported osuKind"):
        asyncio.run(WL.task_telecom_wlan_venue_register(
            venueName="OSU Venue", venueGroup="mercantile",
            venueType="3", jurisdiction="JP", ssid="openroaming",
            advertisedRcoiIds=["rcoi_001"],
            osuKind="wps_push", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.pps.provision ──────────────────────────────────────────

def test_pps_provision_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_pps_provision(
        subscriberId="sub_001", identityProviderOrgId="idp_001",
        eapMethod="EAP-AKA", credentialKind="sim",
        advertisedRcoiIds=["rcoi_001"],
        ppsMoHash=_HASH,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_pps_provision_rejects_invalid_eap_method():
    with pytest.raises(ValueError, match="unsupported eapMethod"):
        asyncio.run(WL.task_telecom_wlan_pps_provision(
            subscriberId="sub_001", identityProviderOrgId="idp_001",
            eapMethod="EAP-MD5", credentialKind="sim",
            advertisedRcoiIds=["rcoi_001"],
            ppsMoHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_pps_provision_rejects_invalid_credential_kind():
    with pytest.raises(ValueError, match="unsupported credentialKind"):
        asyncio.run(WL.task_telecom_wlan_pps_provision(
            subscriberId="sub_001", identityProviderOrgId="idp_001",
            eapMethod="EAP-TLS", credentialKind="smartcard",
            advertisedRcoiIds=["rcoi_001"],
            ppsMoHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_pps_provision_rejects_bad_pps_mo_hash():
    with pytest.raises(ValueError, match="ppsMoHash must be prefixed"):
        asyncio.run(WL.task_telecom_wlan_pps_provision(
            subscriberId="sub_001", identityProviderOrgId="idp_001",
            eapMethod="EAP-AKA-prime", credentialKind="certificate",
            advertisedRcoiIds=["rcoi_001"],
            ppsMoHash="md5:badhash",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_pps_provision_rejects_bad_credential_ref():
    with pytest.raises(ValueError, match="credentialRef must be a vault://"):
        asyncio.run(WL.task_telecom_wlan_pps_provision(
            subscriberId="sub_001", identityProviderOrgId="idp_001",
            eapMethod="EAP-PEAP", credentialKind="username_password",
            advertisedRcoiIds=["rcoi_001"],
            ppsMoHash=_HASH,
            credentialRef="https://bad.example.com/cred",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.anqp.query ─────────────────────────────────────────────

def test_anqp_query_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_anqp_query(
        venueId="venue_001", ueMacHash=_HASH,
        gasProtocol="gas_anqp", queryElement="nai_realm",
        responseHash=_HASH,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_anqp_query_rejects_invalid_gas_protocol():
    with pytest.raises(ValueError, match="unsupported gasProtocol"):
        asyncio.run(WL.task_telecom_wlan_anqp_query(
            venueId="venue_001", ueMacHash=_HASH,
            gasProtocol="gas_direct", queryElement="venue_name",
            responseHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_anqp_query_rejects_invalid_query_element():
    with pytest.raises(ValueError, match="unsupported queryElement"):
        asyncio.run(WL.task_telecom_wlan_anqp_query(
            venueId="venue_001", ueMacHash=_HASH,
            gasProtocol="gas_h2t", queryElement="terms_of_service",
            responseHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_anqp_query_rejects_bad_ue_mac_hash():
    with pytest.raises(ValueError, match="ueMacHash must be prefixed"):
        asyncio.run(WL.task_telecom_wlan_anqp_query(
            venueId="venue_001", ueMacHash="plain:mac",
            gasProtocol="gas_anqp", queryElement="domain_name",
            responseHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.session.attach ─────────────────────────────────────────

def test_session_attach_returns_active():
    out = asyncio.run(WL.task_telecom_wlan_session_attach(
        subscriberId="sub_001", ppsMoId="pps_001",
        venueId="venue_001", rcoiId="rcoi_001",
        ueMacHash=_HASH, eapMethod="EAP-AKA",
        attachedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_session_attach_released_without_session_id():
    out = asyncio.run(WL.task_telecom_wlan_session_attach(
        subscriberId="sub_001", ppsMoId="pps_001",
        venueId="venue_001", rcoiId="rcoi_001",
        ueMacHash=_HASH, eapMethod="EAP-AKA-prime",
        attachedAt="2026-04-29T10:00:00Z",
        releasedAt="2026-04-29T10:30:00Z",
        dryRun=True,
    ))
    assert out["status"] == "released"


def test_session_attach_rejects_invalid_eap_method():
    with pytest.raises(ValueError, match="unsupported eapMethod"):
        asyncio.run(WL.task_telecom_wlan_session_attach(
            subscriberId="sub_001", ppsMoId="pps_001",
            venueId="venue_001", rcoiId="rcoi_001",
            ueMacHash=_HASH, eapMethod="EAP-PWD",
            attachedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_session_attach_rejects_invalid_ip_assignment():
    with pytest.raises(ValueError, match="unsupported ipAssignment"):
        asyncio.run(WL.task_telecom_wlan_session_attach(
            subscriberId="sub_001", ppsMoId="pps_001",
            venueId="venue_001", rcoiId="rcoi_001",
            ueMacHash=_HASH, eapMethod="EAP-TLS",
            attachedAt="2026-04-29T10:00:00Z",
            ipAssignment="nat64",
            dryRun=True,
        ))


def test_session_attach_rejects_bad_ue_mac_hash():
    with pytest.raises(ValueError, match="ueMacHash must be prefixed"):
        asyncio.run(WL.task_telecom_wlan_session_attach(
            subscriberId="sub_001", ppsMoId="pps_001",
            venueId="venue_001", rcoiId="rcoi_001",
            ueMacHash="plain:mac", eapMethod="EAP-SIM",
            attachedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.roaming.exchange ───────────────────────────────────────

def test_roaming_exchange_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_roaming_exchange(
        sessionId="sess_001", transportKind="radsec",
        peerKind="home_idp", partnerOrgId="partner_001",
        messageKind="accounting_start",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_roaming_exchange_rejects_invalid_transport_kind():
    with pytest.raises(ValueError, match="unsupported transportKind"):
        asyncio.run(WL.task_telecom_wlan_roaming_exchange(
            sessionId="sess_001", transportKind="rest",
            peerKind="drr", partnerOrgId="partner_001",
            messageKind="access_request",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_roaming_exchange_rejects_invalid_peer_kind():
    with pytest.raises(ValueError, match="unsupported peerKind"):
        asyncio.run(WL.task_telecom_wlan_roaming_exchange(
            sessionId="sess_001", transportKind="radius",
            peerKind="nsp_broker", partnerOrgId="partner_001",
            messageKind="access_accept",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_roaming_exchange_rejects_invalid_message_kind():
    with pytest.raises(ValueError, match="unsupported messageKind"):
        asyncio.run(WL.task_telecom_wlan_roaming_exchange(
            sessionId="sess_001", transportKind="diameter",
            peerKind="visited_anp", partnerOrgId="partner_001",
            messageKind="disconnect_request",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.andsp.bridge ───────────────────────────────────────────

def test_andsp_bridge_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_andsp_bridge(
        sessionId="sess_001", profileId="profile_001",
        atsssMode="mptcp", transitionKind="wifi_to_5g",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "bridged"


def test_andsp_bridge_rejects_invalid_atsss_mode():
    with pytest.raises(ValueError, match="unsupported atsssMode"):
        asyncio.run(WL.task_telecom_wlan_andsp_bridge(
            sessionId="sess_001", profileId="profile_001",
            atsssMode="pmip6", transitionKind="concurrent_steering",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_andsp_bridge_rejects_invalid_transition_kind():
    with pytest.raises(ValueError, match="unsupported transitionKind"):
        asyncio.run(WL.task_telecom_wlan_andsp_bridge(
            sessionId="sess_001", profileId="profile_001",
            atsssMode="mpquic", transitionKind="handover_5g_to_lte",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_andsp_bridge_rejects_bad_policy_hash():
    with pytest.raises(ValueError, match="andspPolicyHash must be prefixed"):
        asyncio.run(WL.task_telecom_wlan_andsp_bridge(
            sessionId="sess_001", profileId="profile_001",
            atsssMode="atsss-ll", transitionKind="active_active",
            andspPolicyHash="md5:badhash",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_andsp_bridge_rejects_bad_policy_ref():
    with pytest.raises(ValueError, match="andspPolicyRef must be a vault://"):
        asyncio.run(WL.task_telecom_wlan_andsp_bridge(
            sessionId="sess_001", profileId="profile_001",
            atsssMode="switch_only", transitionKind="5g_to_wifi",
            andspPolicyRef="https://bad.example.com/policy",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.wlan.roaming.settle ─────────────────────────────────────────

def test_roaming_settle_returns_ok():
    out = asyncio.run(WL.task_telecom_wlan_roaming_settle(
        partnerOrgId="partner_001",
        periodStart="2026-04-01", periodEnd="2026-04-30",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "issued"
    assert "netAmount" in out


def test_roaming_settle_rejects_reversed_period():
    with pytest.raises(ValueError, match="periodEnd must be after periodStart"):
        asyncio.run(WL.task_telecom_wlan_roaming_settle(
            partnerOrgId="partner_001",
            periodStart="2026-04-30", periodEnd="2026-04-01",
            dryRun=True,
        ))


def test_roaming_settle_rejects_equal_period():
    with pytest.raises(ValueError, match="periodEnd must be after periodStart"):
        asyncio.run(WL.task_telecom_wlan_roaming_settle(
            partnerOrgId="partner_001",
            periodStart="2026-04-01", periodEnd="2026-04-01",
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

    WL.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.wlan.rcoi.register",
        "telecom.wlan.venue.register",
        "telecom.wlan.pps.provision",
        "telecom.wlan.anqp.query",
        "telecom.wlan.session.attach",
        "telecom.wlan.roaming.exchange",
        "telecom.wlan.andsp.bridge",
        "telecom.wlan.roaming.settle",
    }
