"""Tests for telecom_tsn primitives (Time-Sensitive Networking)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_tsn as TN  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.tsn.domain.register ─────────────────────────────────────────

def test_domain_register_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_domain_register(
        ownerOrgId="org_001", displayName="Factory TSN Domain",
        profileKind="industrial_iec_iet",
        controllerKind="fully_centralized_cnc",
        gptpDomainNumber=0,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_domain_register_rejects_invalid_profile_kind():
    with pytest.raises(ValueError, match="unsupported profileKind"):
        asyncio.run(TN.task_telecom_tsn_domain_register(
            ownerOrgId="org_001", displayName="Bad Domain",
            profileKind="generic_tsn",
            controllerKind="fully_distributed",
            gptpDomainNumber=1,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_domain_register_rejects_invalid_controller_kind():
    with pytest.raises(ValueError, match="unsupported controllerKind"):
        asyncio.run(TN.task_telecom_tsn_domain_register(
            ownerOrgId="org_001", displayName="Bad Domain",
            profileKind="automotive_802_1dg",
            controllerKind="cloud_cnc",
            gptpDomainNumber=2,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.bridge.register ─────────────────────────────────────────

def test_bridge_register_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_bridge_register(
        domainId="tsnd_001", vendor="Cisco", model="IE-3400",
        bridgeKind="endpoint_talker", portCount=8,
        supportedShapers=["cbs", "tas"],
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_bridge_register_rejects_invalid_bridge_kind():
    with pytest.raises(ValueError, match="unsupported bridgeKind"):
        asyncio.run(TN.task_telecom_tsn_bridge_register(
            domainId="tsnd_001", vendor="Siemens", model="SCALANCE",
            bridgeKind="core_switch", portCount=12,
            supportedShapers=["cbs"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_bridge_register_rejects_empty_shapers():
    with pytest.raises(ValueError, match="supportedShapers must be a non-empty list"):
        asyncio.run(TN.task_telecom_tsn_bridge_register(
            domainId="tsnd_001", vendor="Hirschmann", model="RSP",
            bridgeKind="transit_bridge", portCount=4,
            supportedShapers=[],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_bridge_register_rejects_zero_port_count():
    with pytest.raises(ValueError, match="portCount must be > 0"):
        asyncio.run(TN.task_telecom_tsn_bridge_register(
            domainId="tsnd_001", vendor="Belden", model="GigE",
            bridgeKind="endpoint_listener", portCount=0,
            supportedShapers=["strict_priority"],
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.gptp.provision ──────────────────────────────────────────

def test_gptp_provision_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_gptp_provision(
        domainId="tsnd_001", grandmasterBridgeId="bridge_001",
        profileKind="802_1as_2020",
        syncIntervalLog=-3, announceIntervalLog=0,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_gptp_provision_rejects_invalid_profile_kind():
    with pytest.raises(ValueError, match="unsupported profileKind"):
        asyncio.run(TN.task_telecom_tsn_gptp_provision(
            domainId="tsnd_001", grandmasterBridgeId="bridge_001",
            profileKind="ptpv1_legacy",
            syncIntervalLog=-4, announceIntervalLog=0,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.stream.reserve ──────────────────────────────────────────

def test_stream_reserve_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_stream_reserve(
        domainId="tsnd_001", talkerEndpointId="bridge_001",
        listenerEndpointIds=["bridge_002", "bridge_003"],
        trafficClass=6, maxFrameBytes=1500,
        framesPerInterval=1, intervalNs=125_000,
        maxLatencyNs=1_000_000,
        reservationKind="qcc_centralized",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "reserved"


def test_stream_reserve_rejects_invalid_reservation_kind():
    with pytest.raises(ValueError, match="unsupported reservationKind"):
        asyncio.run(TN.task_telecom_tsn_stream_reserve(
            domainId="tsnd_001", talkerEndpointId="bridge_001",
            listenerEndpointIds=["bridge_002"],
            trafficClass=7, maxFrameBytes=200,
            framesPerInterval=4, intervalNs=250_000,
            maxLatencyNs=500_000,
            reservationKind="dynamic_reservation",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_stream_reserve_rejects_zero_frame_bytes():
    with pytest.raises(ValueError, match="must be > 0"):
        asyncio.run(TN.task_telecom_tsn_stream_reserve(
            domainId="tsnd_001", talkerEndpointId="bridge_001",
            listenerEndpointIds=["bridge_002"],
            trafficClass=6, maxFrameBytes=0,
            framesPerInterval=1, intervalNs=125_000,
            maxLatencyNs=1_000_000,
            reservationKind="srp_legacy",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.shaper.apply ────────────────────────────────────────────

def test_shaper_apply_cbs_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_shaper_apply(
        bridgeId="bridge_001", portIndex=0,
        shaperKind="cbs", trafficClass=6,
        action="apply", idleSlopeBps=10_000_000,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "applied"


def test_shaper_apply_delete_status():
    out = asyncio.run(TN.task_telecom_tsn_shaper_apply(
        bridgeId="bridge_001", portIndex=1,
        shaperKind="strict_priority", trafficClass=7,
        action="delete",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["status"] == "deleted"


def test_shaper_apply_cbs_requires_idle_slope():
    with pytest.raises(ValueError, match="idleSlopeBps is required for cbs shaper"):
        asyncio.run(TN.task_telecom_tsn_shaper_apply(
            bridgeId="bridge_001", portIndex=0,
            shaperKind="cbs", trafficClass=6,
            action="apply",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_shaper_apply_tas_requires_gate_schedule():
    with pytest.raises(ValueError, match="gateScheduleHash is required for tas shaper"):
        asyncio.run(TN.task_telecom_tsn_shaper_apply(
            bridgeId="bridge_001", portIndex=0,
            shaperKind="tas", trafficClass=5,
            action="apply",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_shaper_apply_rejects_invalid_shaper_kind():
    with pytest.raises(ValueError, match="unsupported shaperKind"):
        asyncio.run(TN.task_telecom_tsn_shaper_apply(
            bridgeId="bridge_001", portIndex=0,
            shaperKind="leaky_bucket", trafficClass=4,
            action="apply",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.frer.enable ─────────────────────────────────────────────

def test_frer_enable_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_frer_enable(
        streamId="stream_001", replicationKind="disjoint_paths",
        replicationCount=3, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_frer_enable_rejects_invalid_replication_kind():
    with pytest.raises(ValueError, match="unsupported replicationKind"):
        asyncio.run(TN.task_telecom_tsn_frer_enable(
            streamId="stream_001", replicationKind="random_path",
            replicationCount=2, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_frer_enable_rejects_replication_count_less_than_two():
    with pytest.raises(ValueError, match="replicationCount must be >= 2"):
        asyncio.run(TN.task_telecom_tsn_frer_enable(
            streamId="stream_001", replicationKind="max_disjoint",
            replicationCount=1, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.sync.deviation ──────────────────────────────────────────

def test_sync_deviation_no_breach():
    out = asyncio.run(TN.task_telecom_tsn_sync_deviation(
        syncProfileId="sync_001", observedBridgeId="bridge_001",
        deviationKind="offset_drift", offsetNs=10,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"
    assert out["breach"] is False


def test_sync_deviation_breach_on_large_offset():
    out = asyncio.run(TN.task_telecom_tsn_sync_deviation(
        syncProfileId="sync_001", observedBridgeId="bridge_001",
        deviationKind="offset_drift", offsetNs=5000,
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["breach"] is True


def test_sync_deviation_rejects_invalid_deviation_kind():
    with pytest.raises(ValueError, match="unsupported deviationKind"):
        asyncio.run(TN.task_telecom_tsn_sync_deviation(
            syncProfileId="sync_001", observedBridgeId="bridge_001",
            deviationKind="phase_noise", offsetNs=0,
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.tsn.sla.breach ──────────────────────────────────────────────

def test_sla_breach_returns_ok():
    out = asyncio.run(TN.task_telecom_tsn_sla_breach(
        streamId="stream_001", breachKind="latency",
        severity="critical", witnessBridgeId="bridge_001",
        observedAt="2026-04-29T10:00:00Z",
        observedLatencyNs=2_000_000, slaLatencyNs=1_000_000,
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "open"
    assert "ticketId" in out


def test_sla_breach_rejects_invalid_breach_kind():
    with pytest.raises(ValueError, match="unsupported breachKind"):
        asyncio.run(TN.task_telecom_tsn_sla_breach(
            streamId="stream_001", breachKind="bandwidth",
            severity="major", witnessBridgeId="bridge_001",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_sla_breach_rejects_invalid_severity():
    with pytest.raises(ValueError, match="unsupported severity"):
        asyncio.run(TN.task_telecom_tsn_sla_breach(
            streamId="stream_001", breachKind="jitter",
            severity="extreme", witnessBridgeId="bridge_001",
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

    TN.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.tsn.domain.register",
        "telecom.tsn.bridge.register",
        "telecom.tsn.gptp.provision",
        "telecom.tsn.stream.reserve",
        "telecom.tsn.shaper.apply",
        "telecom.tsn.frer.enable",
        "telecom.tsn.sync.deviation",
        "telecom.tsn.sla.breach",
    }


# ─── _require_vault_ref ──────────────────────────────────────────────────────

def test_require_vault_ref_valid_passes() -> None:
    TN._require_vault_ref("vault://my/secret", "field")  # no exception


def test_require_vault_ref_none_passes() -> None:
    TN._require_vault_ref(None, "field")  # None is allowed


def test_require_vault_ref_empty_passes() -> None:
    TN._require_vault_ref("", "field")  # empty is falsy → no check


def test_require_vault_ref_invalid_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="vault://"):
        TN._require_vault_ref("https://not-a-vault", "field")


def test_require_vault_ref_plain_string_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        TN._require_vault_ref("sk_live_abc123", "apiKey")


# ─── _require_hash_prefix ────────────────────────────────────────────────────

def test_require_hash_prefix_sha256_passes() -> None:
    TN._require_hash_prefix("sha256:abc123", "digest")  # no exception


def test_require_hash_prefix_sha384_passes() -> None:
    TN._require_hash_prefix("sha384:abc123", "digest")


def test_require_hash_prefix_sha512_passes() -> None:
    TN._require_hash_prefix("sha512:abc123", "digest")


def test_require_hash_prefix_no_prefix_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        TN._require_hash_prefix("abc123def456", "digest")


def test_require_hash_prefix_md5_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        TN._require_hash_prefix("md5:abc123", "digest")
