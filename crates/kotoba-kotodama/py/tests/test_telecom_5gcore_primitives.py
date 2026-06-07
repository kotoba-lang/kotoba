"""Tests for telecom_5gcore primitives (5G Core SBA control plane)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_5gcore as FG  # noqa: E402


# ─── telecom.nf.register ─────────────────────────────────────────────────

def test_nf_register_returns_ok():
    out = asyncio.run(FG.task_telecom_nf_register(
        nfType="AMF", plmnId="44010",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "registered"
    assert out["vertexId"].startswith("at://")


def test_nf_register_rejects_invalid_nf_type():
    with pytest.raises(ValueError, match="unsupported nfType"):
        asyncio.run(FG.task_telecom_nf_register(
            nfType="UNKNOWN_NF", plmnId="44010",
            dryRun=True,
        ))


def test_nf_register_all_valid_nf_types():
    for nf_type in FG.NF_TYPES:
        out = asyncio.run(FG.task_telecom_nf_register(
            nfType=nf_type, plmnId="44010",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.subscriberProfile5g.register ────────────────────────────────

def test_subscriber_profile_5g_register_returns_ok():
    out = asyncio.run(FG.task_telecom_subscriber_profile_5g_register(
        subscriberId="sub_001",
        supi="imsi-440100000000001",
        dnnList=["internet", "ims"],
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_subscriber_profile_5g_rejects_bad_vault_ref():
    with pytest.raises(ValueError, match="vault://"):
        asyncio.run(FG.task_telecom_subscriber_profile_5g_register(
            subscriberId="sub_001",
            supi="imsi-440100000000001",
            dnnList=["internet"],
            akaCredentialRef="https://not-vault.example.com/key",
            dryRun=True,
        ))


def test_subscriber_profile_5g_accepts_vault_ref():
    out = asyncio.run(FG.task_telecom_subscriber_profile_5g_register(
        subscriberId="sub_001",
        supi="imsi-440100000000001",
        dnnList=["internet"],
        akaCredentialRef="vault://org/subscriber/001/aka-key",
        dryRun=True,
    ))
    assert out["ok"] is True


# ─── telecom.subscriber.authenticate ─────────────────────────────────────

def test_subscriber_authenticate_returns_ok():
    out = asyncio.run(FG.task_telecom_subscriber_authenticate(
        profileId="p5g_001",
        supi="imsi-440100000000001",
        authMethod="5G-AKA",
        result="success",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["success"] is True
    assert out["status"] == "recorded"


def test_subscriber_authenticate_failure():
    out = asyncio.run(FG.task_telecom_subscriber_authenticate(
        profileId="p5g_001",
        supi="imsi-440100000000001",
        authMethod="EAP-AKA-prime",
        result="failure",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["success"] is False


def test_subscriber_authenticate_rejects_invalid_method():
    with pytest.raises(ValueError, match="unsupported authMethod"):
        asyncio.run(FG.task_telecom_subscriber_authenticate(
            profileId="p5g_001",
            supi="imsi-440100000000001",
            authMethod="PASSWORD",
            result="success",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_subscriber_authenticate_rejects_invalid_result():
    with pytest.raises(ValueError, match="unsupported result"):
        asyncio.run(FG.task_telecom_subscriber_authenticate(
            profileId="p5g_001",
            supi="imsi-440100000000001",
            authMethod="5G-AKA",
            result="unknown_result",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.amf.register ────────────────────────────────────────────────

def test_amf_register_returns_ok():
    out = asyncio.run(FG.task_telecom_amf_register(
        profileId="p5g_001", registrationType="initial",
        ranNodeId="gnb_001", amfNfId="amf_nf_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "registered"


def test_amf_register_rejects_invalid_registration_type():
    with pytest.raises(ValueError, match="unsupported registrationType"):
        asyncio.run(FG.task_telecom_amf_register(
            profileId="p5g_001", registrationType="unknown_type",
            ranNodeId="gnb_001", amfNfId="amf_nf_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.slice.select ────────────────────────────────────────────────

def test_slice_select_returns_ok():
    out = asyncio.run(FG.task_telecom_slice_select(
        registrationId="reg_001", profileId="p5g_001",
        selectedSnssai="1-000001", nssfNfId="nssf_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "selected"


# ─── telecom.policy.apply ────────────────────────────────────────────────

def test_policy_apply_returns_ok():
    out = asyncio.run(FG.task_telecom_policy_apply(
        profileId="p5g_001", snssai="1-000001", dnn="internet",
        chargingMethod="online", pcfNfId="pcf_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "applied"


def test_policy_apply_rejects_invalid_charging_method():
    with pytest.raises(ValueError, match="unsupported chargingMethod"):
        asyncio.run(FG.task_telecom_policy_apply(
            profileId="p5g_001", snssai="1-000001", dnn="internet",
            chargingMethod="prepaid", pcfNfId="pcf_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.session.establish ───────────────────────────────────────────

def test_session_establish_returns_ok():
    out = asyncio.run(FG.task_telecom_session_establish(
        registrationId="reg_001", profileId="p5g_001",
        snssai="1-000001", dnn="internet",
        sessionType="IPv4", smfNfId="smf_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_session_establish_rejects_invalid_session_type():
    with pytest.raises(ValueError, match="unsupported sessionType"):
        asyncio.run(FG.task_telecom_session_establish(
            registrationId="reg_001", profileId="p5g_001",
            snssai="1-000001", dnn="internet",
            sessionType="IPvX", smfNfId="smf_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_session_establish_all_valid_session_types():
    for stype in FG.SESSION_TYPES:
        out = asyncio.run(FG.task_telecom_session_establish(
            registrationId="reg_001", profileId="p5g_001",
            snssai="1-000001", dnn="internet",
            sessionType=stype, smfNfId="smf_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.charging.emit ───────────────────────────────────────────────

def test_charging_emit_returns_ok():
    out = asyncio.run(FG.task_telecom_charging_emit(
        sessionId="sess_001", profileId="p5g_001",
        subscriberId="sub_001", ratingGroup="rg_001",
        currency="JPY", chargingMethod="offline",
        startedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "emitted"


def test_charging_emit_rejects_negative_units():
    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(FG.task_telecom_charging_emit(
            sessionId="sess_001", profileId="p5g_001",
            subscriberId="sub_001", ratingGroup="rg_001",
            currency="JPY", chargingMethod="online",
            units=-1.0, startedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_charging_emit_rejects_invalid_unit_of_measure():
    with pytest.raises(ValueError, match="unsupported unitOfMeasure"):
        asyncio.run(FG.task_telecom_charging_emit(
            sessionId="sess_001", profileId="p5g_001",
            subscriberId="sub_001", ratingGroup="rg_001",
            currency="JPY", chargingMethod="converged",
            unitOfMeasure="kilograms",
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

    FG.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.nf.register",
        "telecom.subscriberProfile5g.register",
        "telecom.subscriber.authenticate",
        "telecom.amf.register",
        "telecom.slice.select",
        "telecom.policy.apply",
        "telecom.session.establish",
        "telecom.charging.emit",
    }
