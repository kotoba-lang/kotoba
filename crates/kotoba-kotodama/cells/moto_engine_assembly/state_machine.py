"""Engine/motor assembly state machine — ADR-2605261330 L2a (futawa).

≤250cc 4-stroke single-cylinder gasoline OR ≤15kW peak electric.
G11 cap enforced. G14 30-year service life design target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EnginePhase(Enum):
    INIT = "init"
    POWERPLANT_VERIFIED = "powerplant_verified"
    CASE_BLOCK_ASSEMBLED = "case_block_assembled"
    INTERNALS_ASSEMBLED = "internals_assembled"
    TORQUE_QA = "torque_qa"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class EngineState:
    phase: EnginePhase
    vehicleId: str
    completionPct: int
    powerplant: dict[str, Any] | None = None
    caseBlock: dict[str, Any] | None = None
    internals: dict[str, Any] | None = None
    torqueQa: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_powerplant_verified(state: dict[str, Any]) -> dict[str, Any]:
    en = EngineState(**state.get("engine_state", {}))
    mock = {
        "powerplantType": "ICE-4-stroke-single",
        "displacementCc": 248,
        "maxPowerKw": 18.5,
        "g11MaxDisplacementCc": 250,
        "g11WithinCap": True,
        "fuelType": "RON95-unleaded",
        "serviceLifeYearsTarget": 30,
        "g14ServiceLifeCompliant": True,
    }
    en.phase = EnginePhase.POWERPLANT_VERIFIED
    en.powerplant = mock
    en.completionPct = 20
    return {"engine_state": en.__dict__, "next_node": "case"}


def transition_to_case_block_assembled(state: dict[str, Any]) -> dict[str, Any]:
    en = EngineState(**state.get("engine_state", {}))
    mock = {
        "blockMaterial": "Al-A356",
        "blockSourceActor": "kanayama-wave-1",
        "yokinRobotPour": True,
        "caseHalvesBolted": True,
        "boltTorqueNm": 25,
        "g3WitnessCount": 2,
    }
    en.phase = EnginePhase.CASE_BLOCK_ASSEMBLED
    en.caseBlock = mock
    en.completionPct = 45
    return {"engine_state": en.__dict__, "next_node": "internals"}


def transition_to_internals_assembled(state: dict[str, Any]) -> dict[str, Any]:
    en = EngineState(**state.get("engine_state", {}))
    mock = {
        "crankshaft": {"material": "forged-steel", "balanceShaft": True},
        "piston": {"material": "Al-forged", "compressionRatio": 11.0},
        "valvetrain": "DOHC-4-valve",
        "lubricationType": "wet-sump",
        "coolingType": "liquid",
    }
    en.phase = EnginePhase.INTERNALS_ASSEMBLED
    en.internals = mock
    en.completionPct = 75
    return {"engine_state": en.__dict__, "next_node": "torque"}


def transition_to_torque_qa(state: dict[str, Any]) -> dict[str, Any]:
    en = EngineState(**state.get("engine_state", {}))
    mock = {
        "cylinderHeadBoltTorqueNm": 45,
        "cylinderHeadBoltTolNm": 1,
        "crankcaseBoltTorqueNm": 25,
        "rotationalTestRpm": 200,
        "rotationalDragNm": 1.8,
        "accept": True,
    }
    en.phase = EnginePhase.TORQUE_QA
    en.torqueQa = mock
    en.completionPct = 92
    return {"engine_state": en.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    en = EngineState(**state.get("engine_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:otete-joseph-unit-1", "role": "engine_assembly", "timestamp": "2026-05-27T10:00:00Z", "signature": "iI1jJ2kK3lL4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-joseph-unit-1", "role": "torque_metrology", "timestamp": "2026-05-27T10:00:05Z", "signature": "mM5nN6oO7pP8..."},
    ]
    en.phase = EnginePhase.ATTESTATION_EMITTED
    en.robotSignatures = mock_sigs
    en.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.engineAttestation",
        "vehicleId": en.vehicleId,
        "powerplant": en.powerplant,
        "caseBlock": en.caseBlock,
        "internals": en.internals,
        "torqueQa": en.torqueQa,
        "g11Compliant": True,
        "g14ServiceLifeYearsTarget": 30,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T10:00:10Z",
    }
    return {"engine_state": en.__dict__, "engine_attestation": record, "next_node": "end"}
