"""Tests for telecom_ims primitives (IMS voice and supplementary services)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_ims as IM  # noqa: E402


# ─── telecom.ims.subscription ────────────────────────────────────────────

def test_ims_subscription_returns_ok():
    out = asyncio.run(IM.task_telecom_ims_subscription(
        profileId="p5g_001", subscriberId="sub_001",
        impi="user@ims.example.com",
        impuList=["sip:user@ims.example.com", "tel:+819012345678"],
        sCscfFqdn="scscf1.ims.example.com", hssNfId="hss_001",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_ims_subscription_rejects_empty_impu_list():
    with pytest.raises(ValueError, match="impuList must be a non-empty list"):
        asyncio.run(IM.task_telecom_ims_subscription(
            profileId="p5g_001", subscriberId="sub_001",
            impi="user@ims.example.com", impuList=[],
            sCscfFqdn="scscf1.ims.example.com", hssNfId="hss_001",
            dryRun=True,
        ))


# ─── telecom.sip.register ────────────────────────────────────────────────

def test_sip_register_returns_ok():
    out = asyncio.run(IM.task_telecom_sip_register(
        subscriptionId="sub_001", impi="user@ims.example.com",
        impu="sip:user@ims.example.com",
        contactUri="sip:user@192.168.0.1:5060",
        pCscfFqdn="pcscf1.ims.example.com",
        expiresSeconds=3600, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_sip_register_rejects_zero_expires():
    with pytest.raises(ValueError, match="expiresSeconds must be > 0"):
        asyncio.run(IM.task_telecom_sip_register(
            subscriptionId="sub_001", impi="user@ims.example.com",
            impu="sip:user@ims.example.com",
            contactUri="sip:user@192.168.0.1:5060",
            pCscfFqdn="pcscf1.ims.example.com",
            expiresSeconds=0, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_sip_register_rejects_invalid_access_network():
    with pytest.raises(ValueError, match="unsupported accessNetwork"):
        asyncio.run(IM.task_telecom_sip_register(
            subscriptionId="sub_001", impi="user@ims.example.com",
            impu="sip:user@ims.example.com",
            contactUri="sip:user@192.168.0.1:5060",
            pCscfFqdn="pcscf1.ims.example.com",
            expiresSeconds=3600, accessNetwork="satellite",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.voice.establish ─────────────────────────────────────────────

def test_voice_establish_returns_ringing():
    out = asyncio.run(IM.task_telecom_voice_establish(
        subscriberId="sub_001",
        callerImpu="sip:caller@ims.example.com",
        calleeImpu="sip:callee@ims.example.com",
        sessionVoltype="volte", sCscfNfId="scscf_001",
        tasNfId="tas_001", invitedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "ringing"


def test_voice_establish_with_answer_is_active():
    out = asyncio.run(IM.task_telecom_voice_establish(
        subscriberId="sub_001",
        callerImpu="sip:caller@ims.example.com",
        calleeImpu="sip:callee@ims.example.com",
        sessionVoltype="vonr", sCscfNfId="scscf_001",
        tasNfId="tas_001", invitedAt="2026-04-29T10:00:00Z",
        answeredAt="2026-04-29T10:00:03Z",
        dryRun=True,
    ))
    assert out["status"] == "active"


def test_voice_establish_rejects_invalid_session_voltype():
    with pytest.raises(ValueError, match="unsupported sessionVoltype"):
        asyncio.run(IM.task_telecom_voice_establish(
            subscriberId="sub_001",
            callerImpu="sip:caller@ims.example.com",
            calleeImpu="sip:callee@ims.example.com",
            sessionVoltype="volte_hd", sCscfNfId="scscf_001",
            tasNfId="tas_001", invitedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_voice_establish_rejects_invalid_codec():
    with pytest.raises(ValueError, match="unsupported codec"):
        asyncio.run(IM.task_telecom_voice_establish(
            subscriberId="sub_001",
            callerImpu="sip:caller@ims.example.com",
            calleeImpu="sip:callee@ims.example.com",
            sessionVoltype="volte", sCscfNfId="scscf_001",
            tasNfId="tas_001", invitedAt="2026-04-29T10:00:00Z",
            codec="Opus",
            dryRun=True,
        ))


# ─── telecom.voice.terminate ─────────────────────────────────────────────

def test_voice_terminate_normal():
    out = asyncio.run(IM.task_telecom_voice_terminate(
        callId="call_001", releaseCause="normal",
        releasedBy="caller", releasedAt="2026-04-29T10:05:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "released"
    assert out["durationSeconds"] is None  # dryRun


def test_voice_terminate_failure_status():
    out = asyncio.run(IM.task_telecom_voice_terminate(
        callId="call_001", releaseCause="no_answer",
        releasedBy="network", releasedAt="2026-04-29T10:00:30Z",
        dryRun=True,
    ))
    assert out["status"] == "failed"


def test_voice_terminate_rejects_invalid_release_cause():
    with pytest.raises(ValueError, match="unsupported releaseCause"):
        asyncio.run(IM.task_telecom_voice_terminate(
            callId="call_001", releaseCause="dropped",
            releasedBy="caller", releasedAt="2026-04-29T10:05:00Z",
            dryRun=True,
        ))


# ─── telecom.voice.suppService ───────────────────────────────────────────

def test_supp_service_returns_ok():
    out = asyncio.run(IM.task_telecom_voice_supp_service(
        subscriptionId="sub_001", serviceType="call_hold",
        action="invoke", tasNfId="tas_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "applied"


def test_supp_service_rejects_invalid_service_type():
    with pytest.raises(ValueError, match="unsupported serviceType"):
        asyncio.run(IM.task_telecom_voice_supp_service(
            subscriptionId="sub_001", serviceType="call_park",
            action="activate", tasNfId="tas_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.voice.emergency ─────────────────────────────────────────────

def test_voice_emergency_returns_ok():
    out = asyncio.run(IM.task_telecom_voice_emergency(
        callId="call_001", emergencyService="police",
        jurisdiction="JP", psapId="psap_jp_001",
        eCscfNfId="ecscf_001", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "routed"


def test_voice_emergency_rejects_invalid_service():
    with pytest.raises(ValueError, match="unsupported emergencyService"):
        asyncio.run(IM.task_telecom_voice_emergency(
            callId="call_001", emergencyService="mountain_rescue",
            jurisdiction="JP", psapId="psap_jp_001",
            eCscfNfId="ecscf_001", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.voice.interconnect ──────────────────────────────────────────

def test_voice_interconnect_returns_ok():
    out = asyncio.run(IM.task_telecom_voice_interconnect(
        callId="call_001", agreementId="agr_001", partnerId="partner_001",
        gatewayKind="ibcf", gatewayNfId="gw_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "bridged"


def test_voice_interconnect_rejects_invalid_gateway_kind():
    with pytest.raises(ValueError, match="unsupported gatewayKind"):
        asyncio.run(IM.task_telecom_voice_interconnect(
            callId="call_001", agreementId="agr_001", partnerId="partner_001",
            gatewayKind="sbc_ha", gatewayNfId="gw_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ims.billing ─────────────────────────────────────────────────

def test_ims_billing_returns_ok():
    out = asyncio.run(IM.task_telecom_ims_billing(
        callId="call_001", subscriberId="sub_001",
        eventKind="call_complete", ratingGroup="rg_voice",
        currency="JPY", chargingMethod="offline",
        startedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "emitted"


def test_ims_billing_rejects_negative_units():
    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(IM.task_telecom_ims_billing(
            callId="call_001", subscriberId="sub_001",
            eventKind="call_complete", ratingGroup="rg_voice",
            currency="JPY", chargingMethod="online",
            units=-1.0, startedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ims_billing_rejects_invalid_event_kind():
    with pytest.raises(ValueError, match="unsupported eventKind"):
        asyncio.run(IM.task_telecom_ims_billing(
            callId="call_001", subscriberId="sub_001",
            eventKind="data_usage", ratingGroup="rg_data",
            currency="JPY", chargingMethod="converged",
            startedAt="2026-04-29T10:00:00Z",
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

    IM.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.ims.subscription",
        "telecom.sip.register",
        "telecom.voice.establish",
        "telecom.voice.terminate",
        "telecom.voice.suppService",
        "telecom.voice.emergency",
        "telecom.voice.interconnect",
        "telecom.ims.billing",
    }


# ─── _epoch_seconds ──────────────────────────────────────────────────────────

def test_epoch_seconds_valid_utc_iso() -> None:
    result = IM._epoch_seconds("2024-01-01T00:00:00Z")
    assert isinstance(result, int)
    assert result > 0


def test_epoch_seconds_valid_offset_iso() -> None:
    result = IM._epoch_seconds("2024-01-01T09:00:00+09:00")
    assert isinstance(result, int)


def test_epoch_seconds_empty_returns_none() -> None:
    assert IM._epoch_seconds("") is None


def test_epoch_seconds_none_returns_none() -> None:
    assert IM._epoch_seconds(None) is None  # type: ignore[arg-type]


def test_epoch_seconds_invalid_returns_none() -> None:
    assert IM._epoch_seconds("not-a-date") is None


def test_epoch_seconds_deterministic() -> None:
    a = IM._epoch_seconds("2024-06-15T12:00:00Z")
    b = IM._epoch_seconds("2024-06-15T12:00:00Z")
    assert a == b


def test_epoch_seconds_different_times_differ() -> None:
    a = IM._epoch_seconds("2024-01-01T00:00:00Z")
    b = IM._epoch_seconds("2024-01-02T00:00:00Z")
    assert a != b
    assert b > a  # type: ignore[operator]
