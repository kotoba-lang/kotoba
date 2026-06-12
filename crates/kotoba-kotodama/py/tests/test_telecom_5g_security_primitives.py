"""Tests for telecom_5g_security primitives (NWDAF, SCP, SEPP)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_5g_security as SEC  # noqa: E402


# ─── telecom.nwdaf.subscribe ─────────────────────────────────────────────

def test_nwdaf_subscribe_returns_ok():
    out = asyncio.run(SEC.task_telecom_nwdaf_subscribe(
        consumerNfId="amf_001",
        nwdafNfId="nwdaf_001",
        analyticsId="LOAD_LEVEL_INFORMATION",
        targetOfAnalyticsKind="ranNode",
        targetOfAnalyticsVid="at://ran/1",
        reportingPeriodSeconds=60,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_nwdaf_subscribe_rejects_invalid_analytics_id():
    with pytest.raises(ValueError, match="unsupported analyticsId"):
        asyncio.run(SEC.task_telecom_nwdaf_subscribe(
            consumerNfId="amf_001",
            nwdafNfId="nwdaf_001",
            analyticsId="UNKNOWN_ANALYTICS",
            targetOfAnalyticsKind="ranNode",
            targetOfAnalyticsVid="at://ran/1",
            reportingPeriodSeconds=60,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_nwdaf_subscribe_rejects_invalid_target_kind():
    with pytest.raises(ValueError, match="unsupported targetOfAnalyticsKind"):
        asyncio.run(SEC.task_telecom_nwdaf_subscribe(
            consumerNfId="amf_001",
            nwdafNfId="nwdaf_001",
            analyticsId="LOAD_LEVEL_INFORMATION",
            targetOfAnalyticsKind="unknown_kind",
            targetOfAnalyticsVid="at://ran/1",
            reportingPeriodSeconds=60,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_nwdaf_subscribe_rejects_zero_period():
    with pytest.raises(ValueError, match="reportingPeriodSeconds"):
        asyncio.run(SEC.task_telecom_nwdaf_subscribe(
            consumerNfId="amf_001",
            nwdafNfId="nwdaf_001",
            analyticsId="LOAD_LEVEL_INFORMATION",
            targetOfAnalyticsKind="ranNode",
            targetOfAnalyticsVid="at://ran/1",
            reportingPeriodSeconds=0,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nwdaf.result ────────────────────────────────────────────────

def test_nwdaf_result_returns_ok():
    out = asyncio.run(SEC.task_telecom_nwdaf_result(
        subscriptionId="sub_001",
        analyticsId="NETWORK_PERFORMANCE",
        sequenceNumber=1,
        payloadHash="sha256:" + "a" * 64,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "emitted"


def test_nwdaf_result_rejects_invalid_hash_prefix():
    with pytest.raises(ValueError):
        asyncio.run(SEC.task_telecom_nwdaf_result(
            subscriptionId="sub_001",
            analyticsId="NF_LOAD",
            sequenceNumber=1,
            payloadHash="md5:badhash",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.scp.route ───────────────────────────────────────────────────

def test_scp_route_returns_ok():
    out = asyncio.run(SEC.task_telecom_scp_route(
        scpNfId="scp_001",
        sourceNfId="amf_001",
        targetNfId="smf_001",
        targetServiceName="nsmf-pdusession",
        routingMode="indirect_c",
        methodKind="POST",
        statusCode=201,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


def test_scp_route_rejects_invalid_routing_mode():
    with pytest.raises(ValueError, match="unsupported routingMode"):
        asyncio.run(SEC.task_telecom_scp_route(
            scpNfId="scp_001",
            sourceNfId="amf_001",
            targetNfId="smf_001",
            targetServiceName="nsmf",
            routingMode="unknown_mode",
            methodKind="POST",
            statusCode=200,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_scp_route_rejects_invalid_method_kind():
    with pytest.raises(ValueError, match="unsupported methodKind"):
        asyncio.run(SEC.task_telecom_scp_route(
            scpNfId="scp_001",
            sourceNfId="amf_001",
            targetNfId="smf_001",
            targetServiceName="nsmf",
            routingMode="direct_a",
            methodKind="CONNECT",
            statusCode=200,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.scp.discover ────────────────────────────────────────────────

def test_scp_discover_returns_ok():
    out = asyncio.run(SEC.task_telecom_scp_discover(
        scpNfId="scp_001",
        requesterNfId="amf_001",
        targetNfType="SMF",
        selectedNfId="smf_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


def test_scp_discover_rejects_invalid_nf_type():
    with pytest.raises(ValueError, match="unsupported targetNfType"):
        asyncio.run(SEC.task_telecom_scp_discover(
            scpNfId="scp_001",
            requesterNfId="amf_001",
            targetNfType="UNKNOWN_NF",
            selectedNfId="smf_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.sepp.context ────────────────────────────────────────────────

def test_sepp_context_returns_ok():
    out = asyncio.run(SEC.task_telecom_sepp_context(
        localSeppNfId="sepp_001",
        remoteSeppFqdn="sepp.partner.com",
        localPlmnId="44010",
        remotePlmnId="44020",
        agreementId="agreement_001",
        n32CipherSuite="TLS_AES_256_GCM_SHA384",
        validUntil="2027-04-29T10:00:00Z",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


# ─── telecom.sepp.message ────────────────────────────────────────────────

def test_sepp_message_returns_ok():
    out = asyncio.run(SEC.task_telecom_sepp_message(
        contextId="ctx_001",
        direction="inbound",
        n32Channel="n32c",
        payloadHash="sha256:" + "a" * 64,
        securityResult="verified",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


def test_sepp_message_rejects_invalid_direction():
    with pytest.raises(ValueError, match="unsupported direction"):
        asyncio.run(SEC.task_telecom_sepp_message(
            contextId="ctx_001",
            direction="sideways",
            n32Channel="n32c",
            payloadHash="sha256:" + "a" * 64,
            securityResult="verified",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.sepp.keyRotate ──────────────────────────────────────────────

def test_sepp_key_rotate_returns_ok():
    out = asyncio.run(SEC.task_telecom_sepp_key_rotate(
        contextId="ctx_001",
        keyKind="tls_session",
        newKeyHash="sha256:" + "b" * 64,
        rotationReason="scheduled",
        validUntil="2027-04-29T10:00:00Z",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "rotated"


# ─── telecom.sepp.trust ──────────────────────────────────────────────────

def test_sepp_trust_returns_ok():
    out = asyncio.run(SEC.task_telecom_sepp_trust(
        contextId="ctx_001",
        negotiationKind="initial",
        outcome="agreed",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["outcome"] == "agreed"


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    SEC.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.nwdaf.subscribe",
        "telecom.nwdaf.result",
        "telecom.scp.route",
        "telecom.scp.discover",
        "telecom.sepp.context",
        "telecom.sepp.message",
        "telecom.sepp.keyRotate",
        "telecom.sepp.trust",
    }
