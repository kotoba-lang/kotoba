"""Tests for telecom_nfv primitives (NFV / SDN control plane)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_nfv as NF  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.nfv.nsd.onboard ─────────────────────────────────────────────

def test_nsd_onboard_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_nsd_onboard(
        vendor="Ericsson", name="mobile-core-ns", version="1.0.0",
        descriptorFormat="tosca",
        constituentVnfdIds=["vnfd-amf-001", "vnfd-smf-001"],
        packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_nsd_onboard_rejects_invalid_format():
    with pytest.raises(ValueError, match="unsupported descriptorFormat"):
        asyncio.run(NF.task_telecom_nfv_nsd_onboard(
            vendor="Nokia", name="ns-001", version="1.0.0",
            descriptorFormat="xml",
            constituentVnfdIds=["vnfd-001"],
            packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_nsd_onboard_rejects_empty_vnfd_list():
    with pytest.raises(ValueError, match="constituentVnfdIds must be a non-empty list"):
        asyncio.run(NF.task_telecom_nfv_nsd_onboard(
            vendor="Nokia", name="ns-001", version="1.0.0",
            descriptorFormat="tosca",
            constituentVnfdIds=[],
            packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_nsd_onboard_rejects_bad_hash():
    with pytest.raises(ValueError, match="packageHash must be prefixed"):
        asyncio.run(NF.task_telecom_nfv_nsd_onboard(
            vendor="Nokia", name="ns-001", version="1.0.0",
            descriptorFormat="helm",
            constituentVnfdIds=["vnfd-001"],
            packageHash="md5:badhash", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.vnfd.onboard ────────────────────────────────────────────

def test_vnfd_onboard_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_vnfd_onboard(
        vendor="Ericsson", name="amf-vnf", version="1.0.0",
        vnfKind="container_cnf", descriptorFormat="helm",
        deploymentFlavors=["basic", "high-perf"],
        packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_vnfd_onboard_rejects_invalid_vnf_kind():
    with pytest.raises(ValueError, match="unsupported vnfKind"):
        asyncio.run(NF.task_telecom_nfv_vnfd_onboard(
            vendor="Nokia", name="smf-vnf", version="1.0.0",
            vnfKind="baremetal_vnf", descriptorFormat="tosca",
            deploymentFlavors=["standard"],
            packageHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.ns.instantiate ──────────────────────────────────────────

def test_ns_instantiate_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_ns_instantiate(
        nsdId="nsd_001", nfvoNfId="nfvo_001",
        vimIds=["vim_001", "vim_002"],
        deploymentFlavor="standard",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_ns_instantiate_rejects_empty_vim_list():
    with pytest.raises(ValueError, match="vimIds must be a non-empty list"):
        asyncio.run(NF.task_telecom_nfv_ns_instantiate(
            nsdId="nsd_001", nfvoNfId="nfvo_001",
            vimIds=[],
            deploymentFlavor="standard",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.vnf.instantiate ─────────────────────────────────────────

def test_vnf_instantiate_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_vnf_instantiate(
        nsId="ns_001", vnfdId="vnfd_001",
        vnfmNfId="vnfm_001", vimId="vim_001",
        deploymentFlavor="basic",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


# ─── telecom.nfv.vnf.scale ───────────────────────────────────────────────

def test_vnf_scale_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_vnf_scale(
        vnfId="vnf_001", scaleKind="horizontal",
        scaleDirection="scale_out",
        fromInstanceCount=2, toInstanceCount=4,
        triggerKind="manual",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["delta"] == 2


def test_vnf_scale_rejects_invalid_scale_kind():
    with pytest.raises(ValueError, match="unsupported scaleKind"):
        asyncio.run(NF.task_telecom_nfv_vnf_scale(
            vnfId="vnf_001", scaleKind="diagonal",
            scaleDirection="scale_out",
            fromInstanceCount=2, toInstanceCount=4,
            triggerKind="manual",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_vnf_scale_rejects_invalid_direction():
    with pytest.raises(ValueError, match="unsupported scaleDirection"):
        asyncio.run(NF.task_telecom_nfv_vnf_scale(
            vnfId="vnf_001", scaleKind="horizontal",
            scaleDirection="scale_sideways",
            fromInstanceCount=2, toInstanceCount=4,
            triggerKind="alarm",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_vnf_scale_rejects_negative_instance_counts():
    with pytest.raises(ValueError, match="non-negative"):
        asyncio.run(NF.task_telecom_nfv_vnf_scale(
            vnfId="vnf_001", scaleKind="vertical",
            scaleDirection="scale_up",
            fromInstanceCount=-1, toInstanceCount=2,
            triggerKind="policy",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.vnf.heal ────────────────────────────────────────────────

def test_vnf_heal_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_vnf_heal(
        vnfId="vnf_001", healCause="sw_failure",
        healKind="restart",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "completed"


def test_vnf_heal_rejects_invalid_heal_cause():
    with pytest.raises(ValueError, match="unsupported healCause"):
        asyncio.run(NF.task_telecom_nfv_vnf_heal(
            vnfId="vnf_001", healCause="cosmic_ray",
            healKind="restart",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_vnf_heal_rejects_invalid_heal_kind():
    with pytest.raises(ValueError, match="unsupported healKind"):
        asyncio.run(NF.task_telecom_nfv_vnf_heal(
            vnfId="vnf_001", healCause="hw_failure",
            healKind="reboot",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.sdn.flow ────────────────────────────────────────────────

def test_sdn_flow_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_sdn_flow(
        sdnControllerId="ctrl_001", southboundProtocol="openflow",
        switchDpid="00:00:00:00:00:00:00:01",
        tableId=0, priority=100,
        matchHash=_HASH, actionHash="sha256:" + "b" * 64,
        action="install",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "installed"


def test_sdn_flow_rejects_invalid_protocol():
    with pytest.raises(ValueError, match="unsupported southboundProtocol"):
        asyncio.run(NF.task_telecom_nfv_sdn_flow(
            sdnControllerId="ctrl_001", southboundProtocol="bgp",
            switchDpid="00:00:00:00:00:00:00:01",
            tableId=0, priority=100,
            matchHash=_HASH, actionHash=_HASH,
            action="install",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_sdn_flow_rejects_invalid_action():
    with pytest.raises(ValueError, match="unsupported action"):
        asyncio.run(NF.task_telecom_nfv_sdn_flow(
            sdnControllerId="ctrl_001", southboundProtocol="p4runtime",
            switchDpid="00:00:00:00:00:00:00:01",
            tableId=0, priority=100,
            matchHash=_HASH, actionHash=_HASH,
            action="activate",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.nfv.ns.terminate ────────────────────────────────────────────

def test_ns_terminate_returns_ok():
    out = asyncio.run(NF.task_telecom_nfv_ns_terminate(
        nsId="ns_001", terminationKind="graceful",
        terminatedBy="operator_001",
        terminatedAt="2026-04-29T11:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "terminated"


def test_ns_terminate_rejects_invalid_kind():
    with pytest.raises(ValueError, match="unsupported terminationKind"):
        asyncio.run(NF.task_telecom_nfv_ns_terminate(
            nsId="ns_001", terminationKind="unknown_kind",
            terminatedBy="operator_001",
            terminatedAt="2026-04-29T11:00:00Z",
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

    NF.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.nfv.nsd.onboard",
        "telecom.nfv.vnfd.onboard",
        "telecom.nfv.ns.instantiate",
        "telecom.nfv.vnf.instantiate",
        "telecom.nfv.vnf.scale",
        "telecom.nfv.vnf.heal",
        "telecom.nfv.sdn.flow",
        "telecom.nfv.ns.terminate",
    }
