"""Tests for telecom_li primitives (Lawful Interception)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_li as LI  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.li.warrant.register ─────────────────────────────────────────

def test_warrant_register_returns_ok():
    out = asyncio.run(LI.task_telecom_li_warrant_register(
        jurisdiction="JP", lawAuthorityId="tokyo_district_court",
        warrantNumber="W2026-001", warrantKind="court_order",
        interceptScope="iri_and_cc",
        validFrom="2026-04-29", validUntil="2026-07-29",
        lemfId="lemf_001",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_warrant_register_rejects_invalid_warrant_kind():
    with pytest.raises(ValueError, match="unsupported warrantKind"):
        asyncio.run(LI.task_telecom_li_warrant_register(
            jurisdiction="JP", lawAuthorityId="osaka_court",
            warrantNumber="W2026-002", warrantKind="subpoena",
            interceptScope="iri_only",
            validFrom="2026-04-29", validUntil="2026-07-29",
            lemfId="lemf_001",
            dryRun=True,
        ))


def test_warrant_register_rejects_invalid_intercept_scope():
    with pytest.raises(ValueError, match="unsupported interceptScope"):
        asyncio.run(LI.task_telecom_li_warrant_register(
            jurisdiction="JP", lawAuthorityId="tokyo_district_court",
            warrantNumber="W2026-003", warrantKind="court_order",
            interceptScope="full_capture",
            validFrom="2026-04-29", validUntil="2026-07-29",
            lemfId="lemf_001",
            dryRun=True,
        ))


def test_warrant_register_rejects_invalid_document_ref():
    with pytest.raises(ValueError, match="warrantDocumentRef must be a vault://"):
        asyncio.run(LI.task_telecom_li_warrant_register(
            jurisdiction="JP", lawAuthorityId="tokyo_district_court",
            warrantNumber="W2026-004", warrantKind="national_security",
            interceptScope="cc_only",
            validFrom="2026-04-29", validUntil="2026-07-29",
            lemfId="lemf_001",
            warrantDocumentRef="https://bad.example.com/warrant",
            dryRun=True,
        ))


# ─── telecom.li.target.activate ──────────────────────────────────────────

def test_target_activate_returns_ok():
    out = asyncio.run(LI.task_telecom_li_target_activate(
        warrantId="warr_001", identifierKind="msisdn",
        identifierValue="09012345678", licfNfId="licf_001",
        x1ProvisionedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_target_activate_rejects_invalid_identifier_kind():
    with pytest.raises(ValueError, match="unsupported identifierKind"):
        asyncio.run(LI.task_telecom_li_target_activate(
            warrantId="warr_001", identifierKind="mac_address",
            identifierValue="AA:BB:CC:DD:EE:FF", licfNfId="licf_001",
            x1ProvisionedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.li.target.deactivate ────────────────────────────────────────

def test_target_deactivate_returns_ok():
    out = asyncio.run(LI.task_telecom_li_target_deactivate(
        targetId="tgt_001", deactivationReason="warrant_expired",
        deactivatedAt="2026-07-29T00:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "deactivated"


def test_target_deactivate_rejects_invalid_reason():
    with pytest.raises(ValueError, match="unsupported deactivationReason"):
        asyncio.run(LI.task_telecom_li_target_deactivate(
            targetId="tgt_001", deactivationReason="investigation_paused",
            deactivatedAt="2026-07-29T00:00:00Z",
            dryRun=True,
        ))


# ─── telecom.li.iri.deliver ──────────────────────────────────────────────

def test_iri_deliver_returns_ok():
    out = asyncio.run(LI.task_telecom_li_iri_deliver(
        targetId="tgt_001", eventKind="registration",
        eventVid="at://example/event/001",
        x2Sequence=1, df2NfId="df2_001", lemfId="lemf_001",
        payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "delivered"


def test_iri_deliver_rejects_invalid_event_kind():
    with pytest.raises(ValueError, match="unsupported eventKind"):
        asyncio.run(LI.task_telecom_li_iri_deliver(
            targetId="tgt_001", eventKind="data_transfer",
            eventVid="at://example/event/001",
            x2Sequence=1, df2NfId="df2_001", lemfId="lemf_001",
            payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_iri_deliver_rejects_zero_sequence():
    with pytest.raises(ValueError, match="x2Sequence must be > 0"):
        asyncio.run(LI.task_telecom_li_iri_deliver(
            targetId="tgt_001", eventKind="session_establish",
            eventVid="at://example/event/001",
            x2Sequence=0, df2NfId="df2_001", lemfId="lemf_001",
            payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_iri_deliver_rejects_bad_hash():
    with pytest.raises(ValueError, match="payloadHash must be prefixed"):
        asyncio.run(LI.task_telecom_li_iri_deliver(
            targetId="tgt_001", eventKind="session_release",
            eventVid="at://example/event/001",
            x2Sequence=5, df2NfId="df2_001", lemfId="lemf_001",
            payloadHash="md5:badhash", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.li.cc.deliver ───────────────────────────────────────────────

def test_cc_deliver_returns_ok():
    out = asyncio.run(LI.task_telecom_li_cc_deliver(
        targetId="tgt_001", contentKind="voice_rtp",
        x3Sequence=1, df3NfId="df3_001", lemfId="lemf_001",
        payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "delivered"


def test_cc_deliver_rejects_invalid_content_kind():
    with pytest.raises(ValueError, match="unsupported contentKind"):
        asyncio.run(LI.task_telecom_li_cc_deliver(
            targetId="tgt_001", contentKind="email_body",
            x3Sequence=1, df3NfId="df3_001", lemfId="lemf_001",
            payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_cc_deliver_rejects_invalid_encryption_ref():
    with pytest.raises(ValueError, match="encryptionRef must be a vault://"):
        asyncio.run(LI.task_telecom_li_cc_deliver(
            targetId="tgt_001", contentKind="data_pdu",
            x3Sequence=2, df3NfId="df3_001", lemfId="lemf_001",
            payloadHash=_HASH, encryptionRef="https://not-vault.example.com/key",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.li.delivery.ack ─────────────────────────────────────────────

def test_delivery_ack_returns_ok():
    out = asyncio.run(LI.task_telecom_li_delivery_ack(
        deliveryKind="iri", deliveryVid="at://example/iri/001",
        lemfId="lemf_001", ackResult="received",
        ackedAt="2026-04-29T10:00:01Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_delivery_ack_rejects_invalid_delivery_kind():
    with pytest.raises(ValueError, match="unsupported deliveryKind"):
        asyncio.run(LI.task_telecom_li_delivery_ack(
            deliveryKind="sms", deliveryVid="at://example/sms/001",
            lemfId="lemf_001", ackResult="received",
            ackedAt="2026-04-29T10:00:01Z",
            dryRun=True,
        ))


def test_delivery_ack_rejects_invalid_ack_result():
    with pytest.raises(ValueError, match="unsupported ackResult"):
        asyncio.run(LI.task_telecom_li_delivery_ack(
            deliveryKind="cc", deliveryVid="at://example/cc/001",
            lemfId="lemf_001", ackResult="partial",
            ackedAt="2026-04-29T10:00:01Z",
            dryRun=True,
        ))


# ─── telecom.li.audit.access ─────────────────────────────────────────────

def test_audit_access_returns_ok():
    out = asyncio.run(LI.task_telecom_li_audit_access(
        accessKind="read", accessor="admin_001",
        accessorRole="li_admin", recordKind="warrant",
        recordVid="at://example/warrant/001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_audit_access_rejects_invalid_access_kind():
    with pytest.raises(ValueError, match="unsupported accessKind"):
        asyncio.run(LI.task_telecom_li_audit_access(
            accessKind="copy", accessor="admin_001",
            accessorRole="compliance_officer", recordKind="iri",
            recordVid="at://example/iri/001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_audit_access_rejects_invalid_accessor_role():
    with pytest.raises(ValueError, match="unsupported accessorRole"):
        asyncio.run(LI.task_telecom_li_audit_access(
            accessKind="query", accessor="admin_001",
            accessorRole="ceo", recordKind="target",
            recordVid="at://example/target/001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.li.warrant.close ────────────────────────────────────────────

def test_warrant_close_returns_ok():
    out = asyncio.run(LI.task_telecom_li_warrant_close(
        warrantId="warr_001", closureReason="expired",
        closedAt="2026-07-29T00:00:00Z",
        retentionUntil="2031-07-29",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "closed"


def test_warrant_close_rejects_invalid_closure_reason():
    with pytest.raises(ValueError, match="unsupported closureReason"):
        asyncio.run(LI.task_telecom_li_warrant_close(
            warrantId="warr_001", closureReason="completed",
            closedAt="2026-07-29T00:00:00Z",
            retentionUntil="2031-07-29",
            dryRun=True,
        ))


def test_warrant_close_rejects_invalid_final_report_ref():
    with pytest.raises(ValueError, match="finalReportRef must be a vault://"):
        asyncio.run(LI.task_telecom_li_warrant_close(
            warrantId="warr_001", closureReason="revoked",
            closedAt="2026-07-29T00:00:00Z",
            retentionUntil="2031-07-29",
            finalReportRef="https://not-vault.example.com/report",
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

    LI.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.li.warrant.register",
        "telecom.li.target.activate",
        "telecom.li.target.deactivate",
        "telecom.li.iri.deliver",
        "telecom.li.cc.deliver",
        "telecom.li.delivery.ack",
        "telecom.li.audit.access",
        "telecom.li.warrant.close",
    }
