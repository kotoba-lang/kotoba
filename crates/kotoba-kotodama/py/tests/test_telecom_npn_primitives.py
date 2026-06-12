"""Tests for telecom_npn primitives (Non-Public Networks: SNPN, CAG, NID)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_npn as NP  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.npn.snpn.register ───────────────────────────────────────────

def test_snpn_register_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_snpn_register(
        enterpriseOrgId="corp_001", deploymentKind="snpn_isolated",
        plmnId="44910", nidValue="A12345678",
        jurisdiction="JP", validUntil="2030-12-31",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_snpn_register_rejects_invalid_deployment_kind():
    with pytest.raises(ValueError, match="unsupported deploymentKind"):
        asyncio.run(NP.task_telecom_npn_snpn_register(
            enterpriseOrgId="corp_001", deploymentKind="standalone",
            plmnId="44910", nidValue="A12345678",
            jurisdiction="JP", validUntil="2030-12-31",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_snpn_register_all_valid_deployment_kinds():
    for dk in NP.DEPLOYMENT_KINDS:
        out = asyncio.run(NP.task_telecom_npn_snpn_register(
            enterpriseOrgId="corp_001", deploymentKind=dk,
            plmnId="44910", nidValue="A12345678",
            jurisdiction="JP", validUntil="2030-12-31",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.npn.cag.register ────────────────────────────────────────────

def test_cag_register_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_cag_register(
        snpnId="snpn_001", cagValue="CAG001",
        displayName="Factory Zone A",
        accessKind="cag_only",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_cag_register_rejects_invalid_access_kind():
    with pytest.raises(ValueError, match="unsupported accessKind"):
        asyncio.run(NP.task_telecom_npn_cag_register(
            snpnId="snpn_001", cagValue="CAG001",
            displayName="Factory Zone A",
            accessKind="open",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.npn.nid.register ────────────────────────────────────────────

def test_nid_register_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_nid_register(
        snpnId="snpn_001", nidValue="A12345678",
        assignmentKind="self",
        allocatedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_nid_register_coordinated_requires_oui():
    with pytest.raises(ValueError, match="ouiPrefix is required"):
        asyncio.run(NP.task_telecom_npn_nid_register(
            snpnId="snpn_001", nidValue="A12345678",
            assignmentKind="coordinated",
            allocatedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_nid_register_coordinated_with_oui():
    out = asyncio.run(NP.task_telecom_npn_nid_register(
        snpnId="snpn_001", nidValue="A12345678",
        assignmentKind="coordinated", ouiPrefix="AA-BB-CC",
        allocatedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


# ─── telecom.npn.idMap.upsert ────────────────────────────────────────────

def test_id_map_upsert_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_id_map_upsert(
        profileId="p5g_001", supi="imsi-440100000000001",
        gpsiKind="msisdn", gpsiValue="09012345678",
        action="create", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_id_map_upsert_delete_status():
    out = asyncio.run(NP.task_telecom_npn_id_map_upsert(
        profileId="p5g_001", supi="imsi-440100000000001",
        gpsiKind="external_id", gpsiValue="user@example.com",
        action="delete", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["status"] == "deleted"


def test_id_map_upsert_rejects_invalid_gpsi_kind():
    with pytest.raises(ValueError, match="unsupported gpsiKind"):
        asyncio.run(NP.task_telecom_npn_id_map_upsert(
            profileId="p5g_001", supi="imsi-440100000000001",
            gpsiKind="email", gpsiValue="user@example.com",
            action="create", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.npn.nsacf.enforce ───────────────────────────────────────────

def test_nsacf_enforce_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_nsacf_enforce(
        nsacfNfId="nsacf_001", snssai="1-000001",
        requesterNfId="amf_001", requestKind="registration",
        decision="admit", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["admit"] is True
    assert out["status"] == "recorded"


def test_nsacf_enforce_reject_decision():
    out = asyncio.run(NP.task_telecom_npn_nsacf_enforce(
        nsacfNfId="nsacf_001", snssai="1-000001",
        requesterNfId="amf_001", requestKind="pdu_session_establishment",
        decision="reject", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["admit"] is False


def test_nsacf_enforce_rejects_invalid_request_kind():
    with pytest.raises(ValueError, match="unsupported requestKind"):
        asyncio.run(NP.task_telecom_npn_nsacf_enforce(
            nsacfNfId="nsacf_001", snssai="1-000001",
            requesterNfId="amf_001", requestKind="unknown_kind",
            decision="admit", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.npn.prose.provision ─────────────────────────────────────────

def test_prose_provision_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_prose_provision(
        snpnId="snpn_001", communicationKind="one_to_one",
        prosePolicyHash=_HASH,
        validUntil="2027-04-29T00:00:00Z",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_prose_provision_rejects_invalid_comm_kind():
    with pytest.raises(ValueError, match="unsupported communicationKind"):
        asyncio.run(NP.task_telecom_npn_prose_provision(
            snpnId="snpn_001", communicationKind="broadcast",
            prosePolicyHash=_HASH,
            validUntil="2027-04-29T00:00:00Z",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.npn.subscriber.register ─────────────────────────────────────

def test_subscriber_register_returns_ok():
    out = asyncio.run(NP.task_telecom_npn_subscriber_register(
        profileId="p5g_001", sponsoredByEnterpriseOrgId="corp_001",
        validUntil="2027-04-29T00:00:00Z",
        observedAt="2026-04-29T10:00:00Z",
        snpnId="snpn_001",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_subscriber_register_requires_snpn_or_pni():
    with pytest.raises(ValueError, match="either snpnId or pniId must be provided"):
        asyncio.run(NP.task_telecom_npn_subscriber_register(
            profileId="p5g_001", sponsoredByEnterpriseOrgId="corp_001",
            validUntil="2027-04-29T00:00:00Z",
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

    NP.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.npn.snpn.register",
        "telecom.npn.cag.register",
        "telecom.npn.nid.register",
        "telecom.npn.pni.provision",
        "telecom.npn.idMap.upsert",
        "telecom.npn.nsacf.enforce",
        "telecom.npn.prose.provision",
        "telecom.npn.subscriber.register",
    }
