"""Dyno + road test state machine — ADR-2605261330 L5b (futawa).

Dynamometer + emissions + G6 sound ≤80 dB @ 7.5m + ABS function test + road test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestPhase(Enum):
    INIT = "init"
    DYNO_RUN = "dyno_run"
    EMISSIONS_TEST = "emissions_test"
    SOUND_TEST = "sound_test"
    ABS_FUNCTION_TEST = "abs_function_test"
    ROAD_TEST = "road_test"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class TestState:
    phase: TestPhase
    vehicleId: str
    completionPct: int
    dyno: dict[str, Any] | None = None
    emissions: dict[str, Any] | None = None
    sound: dict[str, Any] | None = None
    absFunction: dict[str, Any] | None = None
    roadTest: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_dyno_run(state: dict[str, Any]) -> dict[str, Any]:
    ts = TestState(**state.get("test_state", {}))
    mock = {
        "peakPowerKw": 18.2,
        "peakPowerRpm": 9500,
        "peakTorqueNm": 22.4,
        "peakTorqueRpm": 7250,
        "topSpeedKmh": 138,
        "g11WithinDeclaredCap": True,
    }
    ts.phase = TestPhase.DYNO_RUN
    ts.dyno = mock
    ts.completionPct = 20
    return {"test_state": ts.__dict__, "next_node": "emissions"}


def transition_to_emissions_test(state: dict[str, Any]) -> dict[str, Any]:
    ts = TestState(**state.get("test_state", {}))
    mock = {
        "testCycle": "WMTC-class-2-2-equivalent",
        "coGramPerKm": 0.85,
        "coLimitGramPerKm": 1.14,
        "hcGramPerKm": 0.085,
        "hcLimitGramPerKm": 0.17,
        "noxGramPerKm": 0.040,
        "noxLimitGramPerKm": 0.09,
        "euro5Compliant": True,
        "co2GramPerKm": 64,
    }
    ts.phase = TestPhase.EMISSIONS_TEST
    ts.emissions = mock
    ts.completionPct = 40
    return {"test_state": ts.__dict__, "next_node": "sound"}


def transition_to_sound_test(state: dict[str, Any]) -> dict[str, Any]:
    """G6 ≤80 dB @ 7.5m UN-ECE R41."""
    ts = TestState(**state.get("test_state", {}))
    mock = {
        "testStandard": "UN-ECE-R41-rev04",
        "soundLevelDb7m5": 76,
        "g6LimitDb": 80,
        "g6Compliant": True,
        "stationaryIdleDb": 82,
        "stationaryAcceleratedDb": 89,
    }
    ts.phase = TestPhase.SOUND_TEST
    ts.sound = mock
    ts.completionPct = 60
    return {"test_state": ts.__dict__, "next_node": "abs"}


def transition_to_abs_function_test(state: dict[str, Any]) -> dict[str, Any]:
    """G7 ABS function verification."""
    ts = TestState(**state.get("test_state", {}))
    mock = {
        "absActivationTest": "pass",
        "absInterventionStartKmh": 50,
        "stoppingDistanceFromSpeed60KmhMeters": 18.5,
        "limitStoppingDistanceMeters": 22.0,
        "wheelSpeedSensorFrontFunctional": True,
        "wheelSpeedSensorRearFunctional": True,
        "ecuFaultCodeCount": 0,
        "g7Compliant": True,
    }
    ts.phase = TestPhase.ABS_FUNCTION_TEST
    ts.absFunction = mock
    ts.completionPct = 80
    return {"test_state": ts.__dict__, "next_node": "road"}


def transition_to_road_test(state: dict[str, Any]) -> dict[str, Any]:
    ts = TestState(**state.get("test_state", {}))
    mock = {
        "testRouteLengthKm": 12,
        "testRouteCid": "bafkreitestroute001...",
        "shiftCount": 38,
        "brakeApplications": 22,
        "absInterventionCount": 2,
        "vibrationAnomaliesDetected": 0,
        "fluidLeaksDetected": 0,
        "accept": True,
    }
    ts.phase = TestPhase.ROAD_TEST
    ts.roadTest = mock
    ts.completionPct = 95
    return {"test_state": ts.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    ts = TestState(**state.get("test_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:mimi-levi-unit-1", "role": "dyno_emissions_sound_metrology", "timestamp": "2026-05-27T17:00:00Z", "signature": "aA1bB2cC3dD4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-levi-unit-2", "role": "abs_function_metrology", "timestamp": "2026-05-27T17:00:05Z", "signature": "eE5fF6gG7hH8..."},
    ]
    ts.phase = TestPhase.ATTESTATION_EMITTED
    ts.robotSignatures = mock_sigs
    ts.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.testRecord",
        "vehicleId": ts.vehicleId,
        "dyno": ts.dyno,
        "emissions": ts.emissions,
        "sound": ts.sound,
        "absFunction": ts.absFunction,
        "roadTest": ts.roadTest,
        "g6SoundCompliant": True,
        "g7AbsFunctionCompliant": True,
        "overallAccept": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T17:00:10Z",
    }
    return {"test_state": ts.__dict__, "test_record": record, "next_node": "end"}
