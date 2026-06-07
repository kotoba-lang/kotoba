"""Tests for telecom_optical primitives (Optical Transport Network)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_optical as OP  # noqa: E402


# ─── telecom.opt.domain.register ─────────────────────────────────────────

def test_domain_register_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_domain_register(
        ownerOrgId="org_001", displayName="Tokyo Optical Domain",
        controllerKind="transport_pce", jurisdiction="JP",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_domain_register_rejects_invalid_controller_kind():
    with pytest.raises(ValueError, match="unsupported controllerKind"):
        asyncio.run(OP.task_telecom_opt_domain_register(
            ownerOrgId="org_001", displayName="Bad Domain",
            controllerKind="custom_sdn", jurisdiction="JP",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_domain_register_rejects_invalid_southbound_protocol():
    with pytest.raises(ValueError, match="unsupported southbound protocol"):
        asyncio.run(OP.task_telecom_opt_domain_register(
            ownerOrgId="org_001", displayName="Bad Domain",
            controllerKind="goldstone", jurisdiction="JP",
            southboundProtocols=["grpc_openconfig"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_domain_register_with_valid_southbound_protocols():
    out = asyncio.run(OP.task_telecom_opt_domain_register(
        ownerOrgId="org_001", displayName="Full Domain",
        controllerKind="ietf_actn", jurisdiction="JP",
        southboundProtocols=["netconf_openconfig", "tapi"],
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True


# ─── telecom.opt.ols.register ─────────────────────────────────────────────

def test_ols_register_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_ols_register(
        domainId="optd_001", vendor="Ciena", model="6500",
        mustSpecVersion="1.0", totalSpectrumGhz=4800.0,
        channelGridGhz=100.0, supportedModulations=["qpsk", "16qam"],
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_ols_register_rejects_invalid_modulation():
    with pytest.raises(ValueError, match="unsupported modulation"):
        asyncio.run(OP.task_telecom_opt_ols_register(
            domainId="optd_001", vendor="Nokia", model="1830",
            mustSpecVersion="2.0", totalSpectrumGhz=4800.0,
            channelGridGhz=50.0, supportedModulations=["256qam"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ols_register_rejects_empty_modulations():
    with pytest.raises(ValueError, match="supportedModulations must be a non-empty list"):
        asyncio.run(OP.task_telecom_opt_ols_register(
            domainId="optd_001", vendor="Fujitsu", model="1FINITY",
            mustSpecVersion="1.0", totalSpectrumGhz=4800.0,
            channelGridGhz=50.0, supportedModulations=[],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ols_register_rejects_zero_spectrum():
    with pytest.raises(ValueError, match="totalSpectrumGhz / channelGridGhz must be > 0"):
        asyncio.run(OP.task_telecom_opt_ols_register(
            domainId="optd_001", vendor="Ciena", model="6500",
            mustSpecVersion="1.0", totalSpectrumGhz=0.0,
            channelGridGhz=50.0, supportedModulations=["bpsk"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.roadm.register ──────────────────────────────────────────

def test_roadm_register_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_roadm_register(
        olsId="ols_001", displayName="Tokyo ROADM-1",
        roadmKind="cdc_f", degreeCount=4, addDropPortCount=16,
        wssVendor="II-VI", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_roadm_register_rejects_invalid_roadm_kind():
    with pytest.raises(ValueError, match="unsupported roadmKind"):
        asyncio.run(OP.task_telecom_opt_roadm_register(
            olsId="ols_001", displayName="Bad ROADM",
            roadmKind="full_flex", degreeCount=4, addDropPortCount=8,
            wssVendor="Lumentum", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_roadm_register_rejects_zero_degree_count():
    with pytest.raises(ValueError, match="degreeCount must be > 0"):
        asyncio.run(OP.task_telecom_opt_roadm_register(
            olsId="ols_001", displayName="Zero ROADM",
            roadmKind="cd_f", degreeCount=0, addDropPortCount=4,
            wssVendor="Lumentum", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.fiber.register ──────────────────────────────────────────

def test_fiber_register_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_fiber_register(
        olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
        fiberType="smf28", lengthKm=80.0, attenuationDb=16.0,
        ownerOrgId="org_001", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_fiber_register_rejects_invalid_fiber_type():
    with pytest.raises(ValueError, match="unsupported fiberType"):
        asyncio.run(OP.task_telecom_opt_fiber_register(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            fiberType="smf99", lengthKm=50.0, attenuationDb=10.0,
            ownerOrgId="org_001", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_fiber_register_rejects_zero_length():
    with pytest.raises(ValueError, match="lengthKm must be > 0"):
        asyncio.run(OP.task_telecom_opt_fiber_register(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            fiberType="nzdsf", lengthKm=0.0, attenuationDb=0.0,
            ownerOrgId="org_001", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_fiber_register_rejects_invalid_amplifier_kind():
    with pytest.raises(ValueError, match="unsupported amplifierKind"):
        asyncio.run(OP.task_telecom_opt_fiber_register(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            fiberType="g655", lengthKm=100.0, attenuationDb=20.0,
            amplifierKind="soa_amp",
            ownerOrgId="org_001", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.dwdm.provision ──────────────────────────────────────────

def test_dwdm_provision_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_dwdm_provision(
        olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
        centerFrequencyGhz=193100.0, bandwidthGhz=50.0,
        modulation="16qam", lineRateGbps=100.0,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_dwdm_provision_rejects_invalid_modulation():
    with pytest.raises(ValueError, match="unsupported modulation"):
        asyncio.run(OP.task_telecom_opt_dwdm_provision(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            centerFrequencyGhz=193000.0, bandwidthGhz=50.0,
            modulation="256qam", lineRateGbps=400.0,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_dwdm_provision_rejects_invalid_fec():
    with pytest.raises(ValueError, match="unsupported fec"):
        asyncio.run(OP.task_telecom_opt_dwdm_provision(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            centerFrequencyGhz=193000.0, bandwidthGhz=50.0,
            modulation="qpsk", lineRateGbps=100.0,
            fec="turbo_fec",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_dwdm_provision_rejects_zero_frequency():
    with pytest.raises(ValueError, match="centerFrequencyGhz"):
        asyncio.run(OP.task_telecom_opt_dwdm_provision(
            olsId="ols_001", sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            centerFrequencyGhz=0.0, bandwidthGhz=50.0,
            modulation="8qam", lineRateGbps=200.0,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.otn.provision ───────────────────────────────────────────

def test_otn_provision_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_otn_provision(
        channelId="ch_001", oduKind="odu4", oduRate="100G",
        sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
        clientServiceKind="service", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_otn_provision_rejects_invalid_odu_kind():
    with pytest.raises(ValueError, match="unsupported oduKind"):
        asyncio.run(OP.task_telecom_opt_otn_provision(
            channelId="ch_001", oduKind="odu5", oduRate="400G",
            sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            clientServiceKind="service", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_otn_provision_rejects_invalid_client_service_kind():
    with pytest.raises(ValueError, match="unsupported clientServiceKind"):
        asyncio.run(OP.task_telecom_opt_otn_provision(
            channelId="ch_001", oduKind="odu2", oduRate="10G",
            sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            clientServiceKind="generic_ip", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_otn_provision_rejects_invalid_protection_kind():
    with pytest.raises(ValueError, match="unsupported protectionKind"):
        asyncio.run(OP.task_telecom_opt_otn_provision(
            channelId="ch_001", oduKind="odu0", oduRate="1.25G",
            sourceRoadmId="roadm_001", targetRoadmId="roadm_002",
            clientServiceKind="ranxhaul", protectionKind="2plus2",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.alarm.record ────────────────────────────────────────────

def test_alarm_record_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_alarm_record(
        sourceKind="roadm", sourceVid="at://example/roadm/001",
        alarmKind="los", severity="critical",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "open"
    assert "alarmId" in out
    assert "ticketId" in out


def test_alarm_record_rejects_invalid_source_kind():
    with pytest.raises(ValueError, match="unsupported sourceKind"):
        asyncio.run(OP.task_telecom_opt_alarm_record(
            sourceKind="switch", sourceVid="at://example/switch/001",
            alarmKind="bdi", severity="major",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_record_rejects_invalid_alarm_kind():
    with pytest.raises(ValueError, match="unsupported alarmKind"):
        asyncio.run(OP.task_telecom_opt_alarm_record(
            sourceKind="fiber_span", sourceVid="at://example/fiber/001",
            alarmKind="fiber_cut", severity="critical",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_alarm_record_rejects_invalid_severity():
    with pytest.raises(ValueError, match="unsupported severity"):
        asyncio.run(OP.task_telecom_opt_alarm_record(
            sourceKind="dwdm_channel", sourceVid="at://example/dwdm/001",
            alarmKind="osnr_min", severity="extreme",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.opt.pm.record ───────────────────────────────────────────────

def test_pm_record_returns_ok():
    out = asyncio.run(OP.task_telecom_opt_pm_record(
        sourceKind="roadm", sourceVid="at://example/roadm/001",
        metric="rx_power_dbm", value=-5.0, unit="dBm",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"
    assert out["breach"] is False


def test_pm_record_detects_sla_breach():
    out = asyncio.run(OP.task_telecom_opt_pm_record(
        sourceKind="dwdm_channel", sourceVid="at://example/dwdm/001",
        metric="pre_fec_ber", value=0.05, unit="ratio",
        slaThreshold=0.01,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["breach"] is True


def test_pm_record_rejects_invalid_source_kind():
    with pytest.raises(ValueError, match="unsupported sourceKind"):
        asyncio.run(OP.task_telecom_opt_pm_record(
            sourceKind="switch_port", sourceVid="at://example/sw/001",
            metric="rx_power_dbm", value=-3.0, unit="dBm",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_pm_record_rejects_invalid_metric():
    with pytest.raises(ValueError, match="unsupported metric"):
        asyncio.run(OP.task_telecom_opt_pm_record(
            sourceKind="amplifier", sourceVid="at://example/amp/001",
            metric="packet_loss", value=0.001, unit="ratio",
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

    OP.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.opt.domain.register",
        "telecom.opt.ols.register",
        "telecom.opt.roadm.register",
        "telecom.opt.fiber.register",
        "telecom.opt.dwdm.provision",
        "telecom.opt.otn.provision",
        "telecom.opt.alarm.record",
        "telecom.opt.pm.record",
    }
