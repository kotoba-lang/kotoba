"""Tests for telecom_oran primitives (O-RAN Alliance)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_oran as OR  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.oran.smo.register ───────────────────────────────────────────

def test_smo_register_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_smo_register(
        vendor="Ericsson", releaseVersion="O-RAN.WG1.v04.00",
        plmnId="44010", nonRtRicEndpoint="https://nonrtric.example.com",
        o1Endpoint="https://o1.example.com",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_smo_register_uses_provided_smo_id():
    out = asyncio.run(OR.task_telecom_oran_smo_register(
        vendor="Nokia", releaseVersion="O-RAN.WG1.v05.00",
        plmnId="44020", nonRtRicEndpoint="https://nonrtric.nokia.com",
        o1Endpoint="https://o1.nokia.com",
        observedAt="2026-04-29T10:00:00Z",
        smoId="smo_custom_001",
        dryRun=True,
    ))
    assert out["smoId"] == "smo_custom_001"


# ─── telecom.oran.rapp.onboard ────────────────────────────────────────────

def test_rapp_onboard_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_rapp_onboard(
        smoId="smo_001", vendor="Ericsson", name="qos-optimizer",
        version="1.0.0", packageHash=_HASH,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_rapp_onboard_rejects_bad_package_hash():
    with pytest.raises(ValueError, match="packageHash must be prefixed"):
        asyncio.run(OR.task_telecom_oran_rapp_onboard(
            smoId="smo_001", vendor="Nokia", name="energy-saver",
            version="1.0.0", packageHash="md5:badhash",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_rapp_onboard_rejects_bad_vault_ref():
    with pytest.raises(ValueError, match="vault://"):
        asyncio.run(OR.task_telecom_oran_rapp_onboard(
            smoId="smo_001", vendor="Nokia", name="energy-saver",
            version="1.0.0", packageHash=_HASH,
            packageRef="https://not-vault.example.com/pkg",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.oran.xapp.deploy ────────────────────────────────────────────

def test_xapp_deploy_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_xapp_deploy(
        nearRtRicId="ric_001", vendor="Samsung", name="kpm-monitor",
        version="2.0.0", packageHash=_HASH,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


# ─── telecom.oran.a1.policy ──────────────────────────────────────────────

def test_a1_policy_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_a1_policy(
        rappId="rapp_001", nearRtRicId="ric_001",
        policyTypeId="qos-001", useCase="qos_assurance",
        scopeKind="ueGroup", scopeVid="at://ue-group/1",
        statementHash=_HASH, action="create",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "applied"


def test_a1_policy_delete_status():
    out = asyncio.run(OR.task_telecom_oran_a1_policy(
        rappId="rapp_001", nearRtRicId="ric_001",
        policyTypeId="qos-001", useCase="traffic_steering",
        scopeKind="cellSite", scopeVid="at://cell/1",
        statementHash=_HASH, action="delete",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["status"] == "deleted"


def test_a1_policy_rejects_invalid_use_case():
    with pytest.raises(ValueError, match="unsupported useCase"):
        asyncio.run(OR.task_telecom_oran_a1_policy(
            rappId="rapp_001", nearRtRicId="ric_001",
            policyTypeId="qos-001", useCase="unknown_case",
            scopeKind="ueGroup", scopeVid="at://ue/1",
            statementHash=_HASH, action="create",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_a1_policy_rejects_invalid_scope_kind():
    with pytest.raises(ValueError, match="unsupported scopeKind"):
        asyncio.run(OR.task_telecom_oran_a1_policy(
            rappId="rapp_001", nearRtRicId="ric_001",
            policyTypeId="qos-001", useCase="qos_assurance",
            scopeKind="unknown_scope", scopeVid="at://v/1",
            statementHash=_HASH, action="create",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_a1_policy_rejects_invalid_action():
    with pytest.raises(ValueError, match="unsupported action"):
        asyncio.run(OR.task_telecom_oran_a1_policy(
            rappId="rapp_001", nearRtRicId="ric_001",
            policyTypeId="qos-001", useCase="energy_saving",
            scopeKind="ranNode", scopeVid="at://node/1",
            statementHash=_HASH, action="update",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.oran.e2.subscribe ───────────────────────────────────────────

def test_e2_subscribe_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_e2_subscribe(
        xappId="xapp_001", e2NodeId="gnb_001",
        ranFunctionId="rf_kpm", serviceModel="e2sm-kpm",
        eventTriggerKind="periodic", actionKind="report",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_e2_subscribe_rejects_invalid_service_model():
    with pytest.raises(ValueError, match="unsupported serviceModel"):
        asyncio.run(OR.task_telecom_oran_e2_subscribe(
            xappId="xapp_001", e2NodeId="gnb_001",
            ranFunctionId="rf_kpm", serviceModel="unknown_model",
            eventTriggerKind="periodic", actionKind="report",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.oran.e2.indication ──────────────────────────────────────────

def test_e2_indication_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_e2_indication(
        subscriptionId="sub_001", sequenceNumber=1,
        indicationType="report",
        headerHash=_HASH, messageHash="sha256:" + "b" * 64,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_e2_indication_rejects_zero_sequence():
    with pytest.raises(ValueError, match="sequenceNumber must be > 0"):
        asyncio.run(OR.task_telecom_oran_e2_indication(
            subscriptionId="sub_001", sequenceNumber=0,
            indicationType="report",
            headerHash=_HASH, messageHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_e2_indication_rejects_invalid_type():
    with pytest.raises(ValueError, match="unsupported indicationType"):
        asyncio.run(OR.task_telecom_oran_e2_indication(
            subscriptionId="sub_001", sequenceNumber=1,
            indicationType="unknown_type",
            headerHash=_HASH, messageHash=_HASH,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.oran.o1.config ──────────────────────────────────────────────

def test_o1_config_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_o1_config(
        smoId="smo_001", targetKind="o-du", targetVid="at://odu/1",
        interfaceTransport="netconf", operation="merge",
        configHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "applied"


def test_o1_config_rejects_invalid_target_kind():
    with pytest.raises(ValueError, match="unsupported targetKind"):
        asyncio.run(OR.task_telecom_oran_o1_config(
            smoId="smo_001", targetKind="unknown_target", targetVid="at://v/1",
            interfaceTransport="netconf", operation="merge",
            configHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_o1_config_rejects_invalid_transport():
    with pytest.raises(ValueError, match="unsupported interfaceTransport"):
        asyncio.run(OR.task_telecom_oran_o1_config(
            smoId="smo_001", targetKind="o-ru", targetVid="at://oru/1",
            interfaceTransport="snmp", operation="merge",
            configHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.oran.o2.provision ───────────────────────────────────────────

def test_o2_provision_returns_ok():
    out = asyncio.run(OR.task_telecom_oran_o2_provision(
        smoId="smo_001", oCloudId="cloud_001",
        interfaceKind="o2-ims", resourceKind="compute_node",
        deploymentManager="k8s",
        packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "provisioned"


def test_o2_provision_rejects_invalid_interface_kind():
    with pytest.raises(ValueError, match="unsupported interfaceKind"):
        asyncio.run(OR.task_telecom_oran_o2_provision(
            smoId="smo_001", oCloudId="cloud_001",
            interfaceKind="o2-unknown", resourceKind="compute_node",
            deploymentManager="k8s",
            packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_o2_provision_rejects_invalid_deployment_manager():
    with pytest.raises(ValueError, match="unsupported deploymentManager"):
        asyncio.run(OR.task_telecom_oran_o2_provision(
            smoId="smo_001", oCloudId="cloud_001",
            interfaceKind="o2-dms", resourceKind="deployment",
            deploymentManager="nomad",
            packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
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

    OR.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.oran.smo.register",
        "telecom.oran.rapp.onboard",
        "telecom.oran.xapp.deploy",
        "telecom.oran.a1.policy",
        "telecom.oran.e2.subscribe",
        "telecom.oran.e2.indication",
        "telecom.oran.o1.config",
        "telecom.oran.o2.provision",
    }
