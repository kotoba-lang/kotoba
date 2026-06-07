"""Tests for telecom_supplier primitives (interconnect, roaming, MNP)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_supplier as SP  # noqa: E402


# ─── telecom.interconnect.register ───────────────────────────────────────

def test_interconnect_register_returns_ok():
    out = asyncio.run(SP.task_telecom_interconnect_register(
        peerOrgId="kddi_001", peerKind="mno",
        jurisdiction="JP", settlementCurrency="JPY",
        validFrom="2026-01-01", validUntil="2027-12-31",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_interconnect_register_rejects_invalid_peer_kind():
    with pytest.raises(ValueError, match="unsupported peerKind"):
        asyncio.run(SP.task_telecom_interconnect_register(
            peerOrgId="kddi_001", peerKind="satellite",
            jurisdiction="JP", settlementCurrency="JPY",
            validFrom="2026-01-01", validUntil="2027-12-31",
            dryRun=True,
        ))


def test_interconnect_register_all_valid_peer_kinds():
    for pk in SP.PEER_KINDS:
        out = asyncio.run(SP.task_telecom_interconnect_register(
            peerOrgId=f"peer_{pk}", peerKind=pk,
            jurisdiction="JP", settlementCurrency="JPY",
            validFrom="2026-01-01", validUntil="2027-12-31",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.roaming.partner ─────────────────────────────────────────────

def test_roaming_partner_returns_ok():
    out = asyncio.run(SP.task_telecom_roaming_partner(
        peerOrgId="kddi_001", tadigCode="JPN01",
        agreementId="agr_001",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


# ─── telecom.roaming.tapFile ─────────────────────────────────────────────

def test_roaming_tap_file_returns_ok():
    out = asyncio.run(SP.task_telecom_roaming_tap_file(
        partnerId="part_001", fileType="tap",
        fileSequence=1, transferDate="2026-04-01",
        totalCharge=1234.56, currency="JPY",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "received"


def test_roaming_tap_file_rejects_invalid_file_type():
    with pytest.raises(ValueError, match="unsupported fileType"):
        asyncio.run(SP.task_telecom_roaming_tap_file(
            partnerId="part_001", fileType="xdr",
            fileSequence=1, transferDate="2026-04-01",
            currency="USD",
            dryRun=True,
        ))


def test_roaming_tap_file_rejects_zero_sequence():
    with pytest.raises(ValueError, match="fileSequence must be > 0"):
        asyncio.run(SP.task_telecom_roaming_tap_file(
            partnerId="part_001", fileType="tap",
            fileSequence=0, transferDate="2026-04-01",
            currency="USD",
            dryRun=True,
        ))


def test_roaming_tap_file_all_valid_types():
    for ft in SP.TAP_FILE_TYPES:
        out = asyncio.run(SP.task_telecom_roaming_tap_file(
            partnerId="part_001", fileType=ft,
            fileSequence=1, transferDate="2026-04-01",
            currency="USD",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.roaming.settle ──────────────────────────────────────────────

def test_roaming_settle_returns_ok():
    out = asyncio.run(SP.task_telecom_roaming_settle(
        partnerId="part_001", periodStart="2026-03-01",
        periodEnd="2026-04-01", direction="receivable",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "issued"


def test_roaming_settle_rejects_invalid_direction():
    with pytest.raises(ValueError, match="unsupported direction"):
        asyncio.run(SP.task_telecom_roaming_settle(
            partnerId="part_001", periodStart="2026-03-01",
            periodEnd="2026-04-01", direction="incoming",
            dryRun=True,
        ))


def test_roaming_settle_rejects_invalid_period():
    with pytest.raises(ValueError, match="periodEnd must be after periodStart"):
        asyncio.run(SP.task_telecom_roaming_settle(
            partnerId="part_001", periodStart="2026-04-01",
            periodEnd="2026-03-01", direction="payable",
            dryRun=True,
        ))


# ─── telecom.interconnect.cdr ────────────────────────────────────────────

def test_interconnect_cdr_returns_ok():
    out = asyncio.run(SP.task_telecom_interconnect_cdr(
        agreementId="agr_001", partnerId="part_001",
        direction="originating", usageType="voice",
        units=120.0, startedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_interconnect_cdr_rejects_invalid_direction():
    with pytest.raises(ValueError, match="unsupported direction"):
        asyncio.run(SP.task_telecom_interconnect_cdr(
            agreementId="agr_001", partnerId="part_001",
            direction="inbound", usageType="voice",
            units=120.0, startedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_interconnect_cdr_rejects_invalid_usage_type():
    with pytest.raises(ValueError, match="unsupported usageType"):
        asyncio.run(SP.task_telecom_interconnect_cdr(
            agreementId="agr_001", partnerId="part_001",
            direction="terminating", usageType="video",
            units=60.0, startedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_interconnect_cdr_rejects_negative_units():
    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(SP.task_telecom_interconnect_cdr(
            agreementId="agr_001", partnerId="part_001",
            direction="transit", usageType="data",
            units=-1.0, startedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.numberRange.register ────────────────────────────────────────

def test_number_range_register_returns_ok():
    out = asyncio.run(SP.task_telecom_number_range_register(
        jurisdiction="JP", countryCode="81",
        startMsisdn="09000000000", endMsisdn="09099999999",
        allocatedAt="2026-01-01",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "allocated"


def test_number_range_register_rejects_invalid_range():
    with pytest.raises(ValueError, match="endMsisdn must be > startMsisdn"):
        asyncio.run(SP.task_telecom_number_range_register(
            jurisdiction="JP", countryCode="81",
            startMsisdn="09099999999", endMsisdn="09000000000",
            allocatedAt="2026-01-01",
            dryRun=True,
        ))


# ─── telecom.mnp.portIn ──────────────────────────────────────────────────

def test_mnp_port_in_returns_ok():
    out = asyncio.run(SP.task_telecom_mnp_port_in(
        msisdn="09012345678", subscriberId="sub_001",
        donorPartnerId="part_001", requestedAt="2026-04-29T10:00:00Z",
        authCode="AUTH123",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "requested"


def test_mnp_port_in_requires_auth_code():
    with pytest.raises(ValueError, match="authCode is required"):
        asyncio.run(SP.task_telecom_mnp_port_in(
            msisdn="09012345678", subscriberId="sub_001",
            donorPartnerId="part_001", requestedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.mnp.portOut ─────────────────────────────────────────────────

def test_mnp_port_out_returns_ok():
    out = asyncio.run(SP.task_telecom_mnp_port_out(
        msisdn="09087654321", subscriberId="sub_002",
        recipientPartnerId="part_002", requestedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "requested"


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    SP.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.interconnect.register",
        "telecom.roaming.partner",
        "telecom.roaming.tapFile",
        "telecom.roaming.settle",
        "telecom.interconnect.cdr",
        "telecom.numberRange.register",
        "telecom.mnp.portIn",
        "telecom.mnp.portOut",
    }


# ─── _mnp_payload ────────────────────────────────────────────────────────────

def test_mnp_payload_returns_ok():
    out = SP._mnp_payload(
        "in", "08012345678", "sub_001", "partner_a",
        "2026-04-29T10:00:00Z", "", "", "auth-123",
        "did:web:telecom.etzhayyim.com", True,
    )
    assert out["ok"] is True
    assert out["status"] == "requested"


def test_mnp_payload_vertex_id_starts_with_at():
    out = SP._mnp_payload(
        "out", "08098765432", "sub_002", "partner_b",
        "2026-04-29T11:00:00Z", "", "", "",
        "did:web:telecom.etzhayyim.com", True,
    )
    assert out["vertexId"].startswith("at://")


def test_mnp_payload_uses_provided_request_id():
    out = SP._mnp_payload(
        "in", "09011112222", "sub_003", "partner_c",
        "2026-04-29T12:00:00Z", "req_custom_001", "", "auth-xyz",
        "did:web:telecom.etzhayyim.com", True,
    )
    assert out["requestId"] == "req_custom_001"


def test_mnp_payload_generates_request_id_when_empty():
    out = SP._mnp_payload(
        "in", "09099999999", "sub_004", "partner_d",
        "2026-04-29T13:00:00Z", "", "", "auth-abc",
        "did:web:telecom.etzhayyim.com", True,
    )
    assert out["requestId"].startswith("mnp_")


def test_mnp_payload_raises_on_missing_msisdn():
    import pytest
    with pytest.raises(ValueError, match="missing"):
        SP._mnp_payload(
            "in", "", "sub_005", "partner_e",
            "2026-04-29T14:00:00Z", "", "", "",
            "did:web:telecom.etzhayyim.com", True,
        )


def test_mnp_payload_in_out_variants_differ():
    common_args = (
        "08012345678", "sub_001", "partner_a", "2026-04-29T10:00:00Z",
        "", "", "", "did:web:telecom.etzhayyim.com", True,
    )
    out_in = SP._mnp_payload("in", *common_args)
    out_out = SP._mnp_payload("out", *common_args)
    assert out_in["vertexId"] != out_out["vertexId"]
