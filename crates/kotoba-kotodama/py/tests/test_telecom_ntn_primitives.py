"""Tests for telecom_ntn primitives (Non-Terrestrial Networks)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_ntn as NT  # noqa: E402

_HASH = "sha256:" + "a" * 64


# ─── telecom.ntn.satellite.register ─────────────────────────────────────

def test_satellite_register_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_satellite_register(
        operatorOrgId="op_001", displayName="StarSat-1",
        orbitClass="leo", frequencyBands=["ku_band", "ka_band"],
        serviceModes=["broadband_ntn"],
        launchedAt="2026-01-15", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "operational"
    assert out["vertexId"].startswith("at://")


def test_satellite_register_rejects_invalid_orbit_class():
    with pytest.raises(ValueError, match="unsupported orbitClass"):
        asyncio.run(NT.task_telecom_ntn_satellite_register(
            operatorOrgId="op_001", displayName="BadSat",
            orbitClass="vleo", frequencyBands=["ku_band"],
            serviceModes=["transparent"],
            launchedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_satellite_register_rejects_empty_frequency_bands():
    with pytest.raises(ValueError, match="frequencyBands must be a non-empty list"):
        asyncio.run(NT.task_telecom_ntn_satellite_register(
            operatorOrgId="op_001", displayName="BadSat",
            orbitClass="geo", frequencyBands=[],
            serviceModes=["transparent"],
            launchedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_satellite_register_rejects_invalid_service_mode():
    with pytest.raises(ValueError, match="unsupported serviceMode"):
        asyncio.run(NT.task_telecom_ntn_satellite_register(
            operatorOrgId="op_001", displayName="BadSat",
            orbitClass="meo", frequencyBands=["l_band"],
            serviceModes=["invalid_mode"],
            launchedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_satellite_register_all_valid_orbit_classes():
    for oc in NT.ORBIT_CLASSES:
        out = asyncio.run(NT.task_telecom_ntn_satellite_register(
            operatorOrgId="op_001", displayName=f"Sat-{oc}",
            orbitClass=oc, frequencyBands=["ku_band"],
            serviceModes=["transparent"],
            launchedAt="2026-01-01", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))
        assert out["ok"] is True


# ─── telecom.ntn.earthStation.register ──────────────────────────────────

def test_earth_station_register_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_earth_station_register(
        operatorOrgId="op_001", displayName="Tokyo Gateway",
        stationKind="gateway", latitude=35.6762, longitude=139.6503,
        jurisdiction="JP", gatewayKind="ip_gateway",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_earth_station_register_rejects_invalid_station_kind():
    with pytest.raises(ValueError, match="unsupported stationKind"):
        asyncio.run(NT.task_telecom_ntn_earth_station_register(
            operatorOrgId="op_001", displayName="Bad Station",
            stationKind="hub_station", latitude=0.0, longitude=0.0,
            jurisdiction="JP", gatewayKind="ip_gateway",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_earth_station_register_rejects_invalid_gateway_kind():
    with pytest.raises(ValueError, match="unsupported gatewayKind"):
        asyncio.run(NT.task_telecom_ntn_earth_station_register(
            operatorOrgId="op_001", displayName="Bad Station",
            stationKind="gateway", latitude=0.0, longitude=0.0,
            jurisdiction="JP", gatewayKind="generic_gateway",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.cell.provision ─────────────────────────────────────────

def test_ntn_cell_provision_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_cell_provision(
        satelliteId="sat_001", ranNodeId="gnb_001",
        cellPattern="moving", beamCount=4, plmnId="44010",
        frequencyBand="n256", payloadKind="transparent",
        validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_ntn_cell_provision_rejects_invalid_cell_pattern():
    with pytest.raises(ValueError, match="unsupported cellPattern"):
        asyncio.run(NT.task_telecom_ntn_cell_provision(
            satelliteId="sat_001", ranNodeId="gnb_001",
            cellPattern="dynamic", beamCount=2, plmnId="44010",
            frequencyBand="n256", payloadKind="transparent",
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ntn_cell_provision_rejects_zero_beam_count():
    with pytest.raises(ValueError, match="beamCount must be > 0"):
        asyncio.run(NT.task_telecom_ntn_cell_provision(
            satelliteId="sat_001", ranNodeId="gnb_001",
            cellPattern="earth_fixed", beamCount=0, plmnId="44010",
            frequencyBand="n256", payloadKind="regenerative_gnb",
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ntn_cell_provision_rejects_invalid_payload_kind():
    with pytest.raises(ValueError, match="unsupported payloadKind"):
        asyncio.run(NT.task_telecom_ntn_cell_provision(
            satelliteId="sat_001", ranNodeId="gnb_001",
            cellPattern="quasi_earth_fixed", beamCount=8, plmnId="44010",
            frequencyBand="n256", payloadKind="passive",
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.ephemeris.record ────────────────────────────────────────

def test_ephemeris_record_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_ephemeris_record(
        satelliteId="sat_001", sourceKind="celestrak",
        epochAt="2026-04-29T00:00:00Z", payloadFormat="tle",
        payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "recorded"


def test_ephemeris_record_rejects_invalid_source_kind():
    with pytest.raises(ValueError, match="unsupported sourceKind"):
        asyncio.run(NT.task_telecom_ntn_ephemeris_record(
            satelliteId="sat_001", sourceKind="unknown_agency",
            epochAt="2026-04-29T00:00:00Z", payloadFormat="tle",
            payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ephemeris_record_rejects_bad_hash():
    with pytest.raises(ValueError, match="payloadHash must be prefixed"):
        asyncio.run(NT.task_telecom_ntn_ephemeris_record(
            satelliteId="sat_001", sourceKind="operator",
            epochAt="2026-04-29T00:00:00Z", payloadFormat="omm_xml",
            payloadHash="md5:badhash", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ephemeris_record_rejects_invalid_payload_format():
    with pytest.raises(ValueError, match="unsupported payloadFormat"):
        asyncio.run(NT.task_telecom_ntn_ephemeris_record(
            satelliteId="sat_001", sourceKind="norad",
            epochAt="2026-04-29T00:00:00Z", payloadFormat="json_eph",
            payloadHash=_HASH, observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_ephemeris_record_rejects_invalid_vault_ref():
    with pytest.raises(ValueError, match="payloadRef must be a vault://"):
        asyncio.run(NT.task_telecom_ntn_ephemeris_record(
            satelliteId="sat_001", sourceKind="spacetrack",
            epochAt="2026-04-29T00:00:00Z", payloadFormat="sp3",
            payloadHash=_HASH, payloadRef="https://not-vault.example.com/ref",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.handover.record ─────────────────────────────────────────

def test_handover_record_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_handover_record(
        profileId="p5g_001", handoverKind="inter_satellite",
        sourceCellId="cell_001", targetCellId="cell_002",
        triggerKind="beam_sweep", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "completed"


def test_handover_record_rejects_invalid_handover_kind():
    with pytest.raises(ValueError, match="unsupported handoverKind"):
        asyncio.run(NT.task_telecom_ntn_handover_record(
            profileId="p5g_001", handoverKind="cross_orbit",
            sourceCellId="cell_001", targetCellId="cell_002",
            triggerKind="elevation_min", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_handover_record_rejects_invalid_trigger_kind():
    with pytest.raises(ValueError, match="unsupported triggerKind"):
        asyncio.run(NT.task_telecom_ntn_handover_record(
            profileId="p5g_001", handoverKind="ntn_to_tn",
            sourceCellId="cell_001", targetCellId="cell_002",
            triggerKind="random_trigger", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.isl.provision ───────────────────────────────────────────

def test_isl_provision_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_isl_provision(
        sourceSatelliteId="sat_001", targetSatelliteId="sat_002",
        linkKind="optical_lct", capacityMbps=1000.0,
        validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"


def test_isl_provision_rejects_invalid_link_kind():
    with pytest.raises(ValueError, match="unsupported linkKind"):
        asyncio.run(NT.task_telecom_ntn_isl_provision(
            sourceSatelliteId="sat_001", targetSatelliteId="sat_002",
            linkKind="microwave", capacityMbps=500.0,
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_isl_provision_rejects_zero_capacity():
    with pytest.raises(ValueError, match="capacityMbps must be > 0"):
        asyncio.run(NT.task_telecom_ntn_isl_provision(
            sourceSatelliteId="sat_001", targetSatelliteId="sat_002",
            linkKind="rf_ka", capacityMbps=0.0,
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_isl_provision_rejects_invalid_encryption_ref():
    with pytest.raises(ValueError, match="encryptionRef must be a vault://"):
        asyncio.run(NT.task_telecom_ntn_isl_provision(
            sourceSatelliteId="sat_001", targetSatelliteId="sat_002",
            linkKind="rf_v_band", capacityMbps=250.0,
            encryptionRef="https://bad.example.com/key",
            validFrom="2026-04-29", observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.contact.record ──────────────────────────────────────────

def test_contact_record_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_contact_record(
        stationId="es_001", satelliteId="sat_001",
        contactKind="feeder_uplink",
        aosAt="2026-04-29T10:00:00Z", losAt="2026-04-29T10:10:00Z",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["durationSeconds"] is None  # dryRun skips DB update


def test_contact_record_rejects_invalid_contact_kind():
    with pytest.raises(ValueError, match="unsupported contactKind"):
        asyncio.run(NT.task_telecom_ntn_contact_record(
            stationId="es_001", satelliteId="sat_001",
            contactKind="data_relay",
            aosAt="2026-04-29T10:00:00Z", losAt="2026-04-29T10:10:00Z",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


# ─── telecom.ntn.partner.register ────────────────────────────────────────

def test_partner_register_returns_ok():
    out = asyncio.run(NT.task_telecom_ntn_partner_register(
        operatorOrgId="op_001", agreementId="agr_001",
        constellationKind="leo_broadband", plmnId="44010",
        settlementMode="per_byte", validUntil="2027-12-31",
        observedAt="2026-04-29T10:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["status"] == "active"
    assert out["vertexId"].startswith("at://")


def test_partner_register_rejects_invalid_constellation_kind():
    with pytest.raises(ValueError, match="unsupported constellationKind"):
        asyncio.run(NT.task_telecom_ntn_partner_register(
            operatorOrgId="op_001", agreementId="agr_001",
            constellationKind="vleo_iot", plmnId="44010",
            settlementMode="flat_fee", validUntil="2027-12-31",
            observedAt="2026-04-29T10:00:00Z",
            dryRun=True,
        ))


def test_partner_register_rejects_invalid_settlement_mode():
    with pytest.raises(ValueError, match="unsupported settlementMode"):
        asyncio.run(NT.task_telecom_ntn_partner_register(
            operatorOrgId="op_001", agreementId="agr_001",
            constellationKind="geo_broadband", plmnId="44010",
            settlementMode="credit", validUntil="2027-12-31",
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

    NT.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.ntn.satellite.register",
        "telecom.ntn.earthStation.register",
        "telecom.ntn.cell.provision",
        "telecom.ntn.ephemeris.record",
        "telecom.ntn.handover.record",
        "telecom.ntn.isl.provision",
        "telecom.ntn.contact.record",
        "telecom.ntn.partner.register",
    }
