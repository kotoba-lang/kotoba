# 20-actors/kotoba-kotodama/py/tests/organism/test_embodiment_wadachi.py
import time
import pytest
from pydantic import TypeAdapter

from kotodama.organism.embodiment import (
    Pose,
    TelemetryObservation,
    telemetry_joucho_delta,
    E7mSimTelemetrySource,
)
from kotodama.organism.observation import Observation
from kotodama.organism.joucho_types import JouchoDelta


def test_telemetry_observation_pydantic_roundtrip():
    """
    Ensures the TelemetryObservation can be created and serialized
    without data loss or corruption.
    """
    ts = int(time.time())
    data = {
        "kind": "telemetry",
        "actorDid": "did:example:123",
        "createdAt": ts,
        "tier": "B",
        "vehicle_serial": "WAD-001",
        "lands_parcel_cid": "bafy...",
        "pose": {"lat": 35000000, "lon": 139000000, "heading_deg": 18000, "speed_mps": 1000},
        "battery_soc_pct": 8800,
        "mileage_km": 12345600,
        "runtime_hours": 543 * 3600 + 12 * 60,
        "fault_codes": ["FC001"],
        "provenance_hash": "hash123",
    }
    obs = TelemetryObservation(**data)
    assert obs.kind == "telemetry"
    assert obs.actorDid == "did:example:123"
    assert obs.vehicle_serial == "WAD-001"
    assert obs.pose.lat == 35000000
    assert obs.fault_codes == ["FC001"]

    # Test serialization back to dict
    serialized_obs = obs.model_dump()
    assert serialized_obs["kind"] == data["kind"]
    assert serialized_obs["actorDid"] == data["actorDid"]


def test_observation_tagged_union_compatibility():
    """
    Verifies that the main Observation tagged union can correctly parse
    a TelemetryObservation.
    """
    ts = int(time.time())
    data = {
        "kind": "telemetry",
        "actorDid": "did:example:456",
        "createdAt": ts,
        "tier": "B",
        "vehicle_serial": "WAD-002",
        "lands_parcel_cid": "bafy...",
        "pose": {"lat": 35100000, "lon": 139100000, "heading_deg": 9000, "speed_mps": 500},
        "battery_soc_pct": 7500,
        "mileage_km": 54321000,
        "runtime_hours": 123 * 3600 + 24 * 60,
        "fault_codes": [],
        "provenance_hash": "hash456",
    }

    # Use a TypeAdapter for the tagged union
    adapter = TypeAdapter(Observation)

    parsed_obs = adapter.validate_python(data)
    assert isinstance(parsed_obs, TelemetryObservation)
    assert parsed_obs.kind == "telemetry"
    assert parsed_obs.vehicle_serial == "WAD-002"

    # Check that existing modalities are not broken
    text_data = {
        "kind": "text",
        "actorDid": "did:example:789",
        "createdAt": ts,
        "tier": "A",
        "text": "hello world",
    }
    parsed_text_obs = adapter.validate_python(text_data)
    assert parsed_text_obs.kind == "text"

def test_telemetry_joucho_delta():
    """
    Tests the logic of the telemetry_joucho_delta function.
    """
    ts = int(time.time())
    obs = TelemetryObservation(
        kind="telemetry",
        actorDid="did:example:123",
        createdAt=ts,
        tier="B",
        vehicle_serial="WAD-001",
        lands_parcel_cid="bafy...",
        pose={"lat": 35000000, "lon": 139000000, "heading_deg": 18000, "speed_mps": 1000},
        battery_soc_pct=7000,
        mileage_km=12345600,
        runtime_hours=544 * 3600,
        fault_codes=["FC001", "FC002"],
        provenance_hash="hash123",
    )

    # 1. Test battery drop > 10%
    baseline_battery_drop = {"battery_soc_pct": 8500, "runtime_hours": 544 * 3600}
    delta = telemetry_joucho_delta(obs, baseline_battery_drop)
    assert delta.yokkyu == -15
    assert delta.seimei == -15
    assert delta.kakushin == 20
    assert delta.kanjou == -10
    assert delta.kankaku == 0

    # 2. Test fault codes non-empty
    baseline_faults = {"battery_soc_pct": 7000, "runtime_hours": 544 * 3600}
    delta = telemetry_joucho_delta(obs, baseline_faults)
    assert delta.kakushin == 20
    assert delta.kanjou == -10
    assert delta.yokkyu == 0

    # 3. Test runtime hours increment
    baseline_runtime_inc = {"battery_soc_pct": 7000, "runtime_hours": 543 * 3600}
    delta = telemetry_joucho_delta(obs, baseline_runtime_inc)
    assert delta.kankaku == 1
    assert delta.seimei == 2
    assert delta.yokkyu == 0
    assert delta.kakushin == 20
    assert delta.kanjou == -10

def test_e7m_sim_telemetry_source():
    """
    Tests the E7mSimTelemetrySource stub.
    """
    vehicle_serial = "WAD-SIM-001"
    actor_did = "did:example:sim-actor"
    obs = E7mSimTelemetrySource.fetch(vehicle_serial, actor_did)

    assert isinstance(obs, TelemetryObservation)
    assert obs.vehicle_serial == vehicle_serial
    assert obs.actorDid == actor_did
    assert obs.internal_only is False

    forbidden_methods = ["command", "send", "actuate", "control", "push"]
    for method_name in forbidden_methods:
        assert not hasattr(E7mSimTelemetrySource, method_name), f"E7mSimTelemetrySource MUST be passive-only and not have a '{method_name}' method."
