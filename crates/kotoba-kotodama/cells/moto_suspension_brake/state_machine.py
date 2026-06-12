"""Suspension + brake state machine — ADR-2605261330 L3b (futawa).

CONSTITUTIONAL FIRST G7: ABS MANDATORY on all 4-stroke ≥125cc and electric ≥6kW.
No ABS-delete, no track-only carve-out, no cost-down strip; dual-channel hydraulic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SuspensionBrakePhase(Enum):
    INIT = "init"
    FORK_INSTALLED = "fork_installed"
    SHOCK_INSTALLED = "shock_installed"
    BRAKE_INSTALLED = "brake_installed"
    ABS_VERIFIED = "abs_verified"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class SuspensionBrakeState:
    phase: SuspensionBrakePhase
    vehicleId: str
    displacementCc: int
    completionPct: int
    fork: dict[str, Any] | None = None
    shock: dict[str, Any] | None = None
    brake: dict[str, Any] | None = None
    abs: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_fork_installed(state: dict[str, Any]) -> dict[str, Any]:
    sb = SuspensionBrakeState(**state.get("suspension_brake_state", {}))
    mock = {
        "type": "telescopic-USD-37mm",
        "travelMm": 130,
        "preloadAdjustable": True,
        "compressionDampingAdjustable": False,
        "reboundDampingAdjustable": False,
    }
    sb.phase = SuspensionBrakePhase.FORK_INSTALLED
    sb.fork = mock
    sb.completionPct = 25
    return {"suspension_brake_state": sb.__dict__, "next_node": "shock"}


def transition_to_shock_installed(state: dict[str, Any]) -> dict[str, Any]:
    sb = SuspensionBrakeState(**state.get("suspension_brake_state", {}))
    mock = {
        "type": "monoshock-rear",
        "travelMm": 140,
        "preloadAdjustable": True,
        "reservoirSeparate": False,
    }
    sb.phase = SuspensionBrakePhase.SHOCK_INSTALLED
    sb.shock = mock
    sb.completionPct = 45
    return {"suspension_brake_state": sb.__dict__, "next_node": "brake"}


def transition_to_brake_installed(state: dict[str, Any]) -> dict[str, Any]:
    sb = SuspensionBrakeState(**state.get("suspension_brake_state", {}))
    mock = {
        "frontRotorDiameterMm": 300,
        "frontCaliper": "4-piston-radial",
        "rearRotorDiameterMm": 240,
        "rearCaliper": "2-piston",
        "brakePadMaterial": "sintered-metal-non-asbestos",
        "brakeFluid": "DOT-4",
    }
    sb.phase = SuspensionBrakePhase.BRAKE_INSTALLED
    sb.brake = mock
    sb.completionPct = 70
    return {"suspension_brake_state": sb.__dict__, "next_node": "abs"}


def transition_to_abs_verified(state: dict[str, Any]) -> dict[str, Any]:
    """G7 CONSTITUTIONAL FIRST: ABS mandatory ≥125cc / electric ≥6kW."""
    sb = SuspensionBrakeState(**state.get("suspension_brake_state", {}))
    abs_required = sb.displacementCc >= 125
    mock = {
        "absRequiredPerG7": abs_required,
        "displacementCc": sb.displacementCc,
        "absModulePartNumber": "FUTAWA-ABS-DUAL-R0",
        "absInstalled": True,
        "absChannelCount": 2,
        "absDualChannel": True,
        "absDeleteOptionAvailable": False,
        "absCostDownStripVariant": False,
        "absTrackOnlyCarveOut": False,
        "g7Compliant": True,
        "fluidPressureBarTest": 110,
        "wheelSpeedSensorFrontInstalled": True,
        "wheelSpeedSensorRearInstalled": True,
        "ecuFirmwareCid": "bafkreiabsFw001...",
        "g1OpenSourceAbsFirmware": True,
    }
    sb.phase = SuspensionBrakePhase.ABS_VERIFIED
    sb.abs = mock
    sb.completionPct = 92
    return {"suspension_brake_state": sb.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    sb = SuspensionBrakeState(**state.get("suspension_brake_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:otete-dan-unit-1", "role": "brake_torque_witness", "timestamp": "2026-05-27T13:00:00Z", "signature": "cC1dD2eE3fF4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-dan-unit-1", "role": "g7_abs_function_metrology", "timestamp": "2026-05-27T13:00:05Z", "signature": "gG5hH6iI7jJ8..."},
    ]
    sb.phase = SuspensionBrakePhase.ATTESTATION_EMITTED
    sb.robotSignatures = mock_sigs
    sb.completionPct = 100
    record = {
        "vehicleId": sb.vehicleId,
        "fork": sb.fork,
        "shock": sb.shock,
        "brake": sb.brake,
        "abs": sb.abs,
        "g7AbsCompliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T13:00:10Z",
    }
    return {"suspension_brake_state": sb.__dict__, "suspension_brake_record": record, "next_node": "end"}
