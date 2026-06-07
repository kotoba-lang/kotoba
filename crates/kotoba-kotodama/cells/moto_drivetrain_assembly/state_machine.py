"""Drivetrain assembly state machine — ADR-2605261330 L2b (futawa).

Transmission (4-6 speed manual / CVT / direct-drive electric) + chain/belt drive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DrivetrainPhase(Enum):
    INIT = "init"
    TRANSMISSION_ASSEMBLED = "transmission_assembled"
    FINAL_DRIVE_INSTALLED = "final_drive_installed"
    SHIFT_QA = "shift_qa"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class DrivetrainState:
    phase: DrivetrainPhase
    vehicleId: str
    completionPct: int
    transmission: dict[str, Any] | None = None
    finalDrive: dict[str, Any] | None = None
    shiftQa: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_transmission_assembled(state: dict[str, Any]) -> dict[str, Any]:
    dt = DrivetrainState(**state.get("drivetrain_state", {}))
    mock = {
        "type": "manual-6-speed-constant-mesh",
        "ratios": [2.85, 1.94, 1.50, 1.23, 1.05, 0.92],
        "primaryRatio": 3.06,
        "caseMaterial": "Al-A356",
        "g14ServiceLifeYearsTarget": 30,
    }
    dt.phase = DrivetrainPhase.TRANSMISSION_ASSEMBLED
    dt.transmission = mock
    dt.completionPct = 35
    return {"drivetrain_state": dt.__dict__, "next_node": "final_drive"}


def transition_to_final_drive_installed(state: dict[str, Any]) -> dict[str, Any]:
    dt = DrivetrainState(**state.get("drivetrain_state", {}))
    mock = {
        "type": "chain",
        "size": "520-O-ring",
        "linkCount": 110,
        "frontSprocketTeeth": 15,
        "rearSprocketTeeth": 47,
        "tensionAdjustmentMm": 25,
    }
    dt.phase = DrivetrainPhase.FINAL_DRIVE_INSTALLED
    dt.finalDrive = mock
    dt.completionPct = 65
    return {"drivetrain_state": dt.__dict__, "next_node": "shift_qa"}


def transition_to_shift_qa(state: dict[str, Any]) -> dict[str, Any]:
    dt = DrivetrainState(**state.get("drivetrain_state", {}))
    mock = {
        "shiftCyclesTest": 50,
        "missedShifts": 0,
        "shiftForceN": 22,
        "shiftForceLimitN": 35,
        "neutralFindReliability": "100%",
        "accept": True,
    }
    dt.phase = DrivetrainPhase.SHIFT_QA
    dt.shiftQa = mock
    dt.completionPct = 92
    return {"drivetrain_state": dt.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    dt = DrivetrainState(**state.get("drivetrain_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:otete-zebulun-unit-1", "role": "drivetrain_assembly", "timestamp": "2026-05-27T11:00:00Z", "signature": "qQ1rR2sS3tT4..."},
    ]
    dt.phase = DrivetrainPhase.ATTESTATION_EMITTED
    dt.robotSignatures = mock_sigs
    dt.completionPct = 100
    record = {
        "vehicleId": dt.vehicleId,
        "transmission": dt.transmission,
        "finalDrive": dt.finalDrive,
        "shiftQa": dt.shiftQa,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T11:00:10Z",
    }
    return {"drivetrain_state": dt.__dict__, "drivetrain_record": record, "next_node": "end"}
