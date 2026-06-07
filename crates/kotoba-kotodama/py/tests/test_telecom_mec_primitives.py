"""Tests for telecom_mec primitives (Multi-access Edge Computing)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_mec as ME  # noqa: E402

_HASH = "sha256:" + "a" * 64
_UE_HASH = "sha256:" + "c" * 64


# ─── telecom.mec.host.register ───────────────────────────────────────────

def test_mec_host_register_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_host_register(
        oCloudId="cloud_001", vendor="Ericsson",
        hostFqdn="edge01.example.com",
        edgeZone="tokyo-zone-1", plmnId="44010",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_mec_host_register_uses_provided_host_id():
    out = asyncio.run(ME.task_telecom_mec_host_register(
        oCloudId="cloud_001", vendor="Nokia",
        hostFqdn="edge02.nokia.com",
        edgeZone="osaka-zone-1", plmnId="44020",
        observedAt="2026-04-29T10:00:00Z",
        hostId="mecho_custom_001",
        dryRun=True,
    ))
    assert out["hostId"] == "mecho_custom_001"


# ─── telecom.mec.app.onboard ─────────────────────────────────────────────

def test_mec_app_onboard_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_app_onboard(
        vendor="Samsung", name="video-analytics", version="2.1.0",
        appDescriptor="chart-video-analytics",
        latencyClass="urllc", packageHash=_HASH,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_mec_app_onboard_rejects_invalid_latency_class():
    with pytest.raises(ValueError, match="unsupported latencyClass"):
        asyncio.run(ME.task_telecom_mec_app_onboard(
            vendor="Nokia", name="cache-app", version="1.0.0",
            appDescriptor="chart-cache",
            latencyClass="realtime", packageHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_mec_app_onboard_rejects_bad_hash():
    with pytest.raises(ValueError, match="packageHash must be prefixed"):
        asyncio.run(ME.task_telecom_mec_app_onboard(
            vendor="Nokia", name="cache-app", version="1.0.0",
            appDescriptor="chart-cache",
            latencyClass="embb", packageHash="md5:badhash",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_mec_app_onboard_all_valid_latency_classes():
    for lc in ME.LATENCY_CLASSES:
        out = asyncio.run(ME.task_telecom_mec_app_onboard(
            vendor="Ericsson", name=f"app-{lc}", version="1.0.0",
            appDescriptor=f"chart-{lc}",
            latencyClass=lc, packageHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.mec.eas.instantiate ─────────────────────────────────────────

def test_mec_eas_instantiate_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_eas_instantiate(
        appPackageId="pkg_001", hostId="mecho_001",
        easProviderId="provider_001",
        easFqdn="eas01.edge.example.com",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


# ─── telecom.mec.eas.discover ────────────────────────────────────────────

def test_mec_eas_discover_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_eas_discover(
        eesId="ees_001", requestingAcId="ac_001",
        ueIdHash=_UE_HASH, easProviderId="provider_001",
        requestedAppId="app_001", selectedEasId="eas_001",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


def test_mec_eas_discover_rejects_invalid_strategy():
    with pytest.raises(ValueError, match="unsupported selectionStrategy"):
        asyncio.run(ME.task_telecom_mec_eas_discover(
            eesId="ees_001", requestingAcId="ac_001",
            ueIdHash=_UE_HASH, easProviderId="provider_001",
            requestedAppId="app_001", selectedEasId="eas_001",
            selectionStrategy="random",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_mec_eas_discover_rejects_bad_ue_id_hash():
    with pytest.raises(ValueError, match="ueIdHash must be prefixed"):
        asyncio.run(ME.task_telecom_mec_eas_discover(
            eesId="ees_001", requestingAcId="ac_001",
            ueIdHash="md5:badhash", easProviderId="provider_001",
            requestedAppId="app_001", selectedEasId="eas_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.mec.service.call ────────────────────────────────────────────

def test_mec_service_call_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_service_call(
        easId="eas_001", ueIdHash=_UE_HASH,
        methodKind="POST", statusCode=201,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "served"


def test_mec_service_call_failed_status():
    out = asyncio.run(ME.task_telecom_mec_service_call(
        easId="eas_001", ueIdHash=_UE_HASH,
        methodKind="GET", statusCode=500,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["status"] == "failed"


def test_mec_service_call_rejects_invalid_method():
    with pytest.raises(ValueError, match="unsupported methodKind"):
        asyncio.run(ME.task_telecom_mec_service_call(
            easId="eas_001", ueIdHash=_UE_HASH,
            methodKind="CONNECT", statusCode=200,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.mec.federation.register ─────────────────────────────────────

def test_mec_federation_register_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_federation_register(
        partnerOperatorId="kddi_001", agreementId="agr_001",
        federationKind="bilateral", billingMode="settlement",
        validUntil="2027-04-29T00:00:00Z",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_mec_federation_rejects_invalid_federation_kind():
    with pytest.raises(ValueError, match="unsupported federationKind"):
        asyncio.run(ME.task_telecom_mec_federation_register(
            partnerOperatorId="kddi_001", agreementId="agr_001",
            federationKind="star", billingMode="free",
            validUntil="2027-04-29T00:00:00Z",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_mec_federation_rejects_invalid_billing_mode():
    with pytest.raises(ValueError, match="unsupported billingMode"):
        asyncio.run(ME.task_telecom_mec_federation_register(
            partnerOperatorId="kddi_001", agreementId="agr_001",
            federationKind="mesh", billingMode="flatrate",
            validUntil="2027-04-29T00:00:00Z",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.mec.eas.terminate ───────────────────────────────────────────

def test_mec_eas_terminate_returns_ok():
    out = asyncio.run(ME.task_telecom_mec_eas_terminate(
        easId="eas_001", terminationKind="graceful",
        terminatedBy="operator_001",
        terminatedAt="2026-04-29T12:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "terminated"


def test_mec_eas_terminate_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported terminationKind"):
        asyncio.run(ME.task_telecom_mec_eas_terminate(
            easId="eas_001", terminationKind="unknown_kind",
            terminatedBy="operator_001",
            terminatedAt="2026-04-29T12:00:00Z",
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

    ME.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.mec.host.register",
        "telecom.mec.app.onboard",
        "telecom.mec.eas.instantiate",
        "telecom.mec.eas.discover",
        "telecom.mec.eas.relocate",
        "telecom.mec.service.call",
        "telecom.mec.federation.register",
        "telecom.mec.eas.terminate",
    }
