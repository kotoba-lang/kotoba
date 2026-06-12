"""ELV depollution state machine — ADR-2605261215 L1b (hodoki).

Fluid drain (fuel / oil / coolant / brake / washer) + MAC refrigerant capture
(R1234yf / R134a / R290) ≥95% (G6) + airbag pyrotechnic neutralization +
battery disconnect. Also executes G8 ECU + infotainment + telematics data wipe
(cryptographic destruction with chip-shred fallback) before any disassembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DepollutionPhase(Enum):
    INIT = "init"
    DATA_WIPE_COMPLETED = "data_wipe_completed"
    FLUIDS_DRAINED = "fluids_drained"
    FGAS_CAPTURED = "fgas_captured"
    AIRBAGS_NEUTRALIZED = "airbags_neutralized"
    BATTERY_DISCONNECTED = "battery_disconnected"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class DepollutionState:
    phase: DepollutionPhase
    vehicleId: str
    completionPct: int
    dataWipe: dict[str, Any] | None = None
    fluidsDrain: dict[str, Any] | None = None
    fgasCapture: dict[str, Any] | None = None
    airbagNeutralization: dict[str, Any] | None = None
    batteryDisconnect: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_data_wipe_completed(state: dict[str, Any]) -> dict[str, Any]:
    """INIT → DATA_WIPE_COMPLETED. G8 cryptographic destruction + chip-shred fallback.

    CONSTITUTIONAL FIRST: §2(c) anti-surveillance applied to consumer vehicles.
    """
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_wipe = {
        "ecuWipes": [
            {"ecu": "main-body-control", "method": "factory-reset-api", "verified": True},
            {"ecu": "infotainment", "method": "cryptographic-destruction", "verified": True},
            {"ecu": "telematics-module", "method": "physical-chip-shred", "verified": True, "shredCertCid": "bafkreichipshred001..."},
            {"ecu": "engine-ecu", "method": "factory-reset-api", "verified": True},
            {"ecu": "transmission-ecu", "method": "factory-reset-api", "verified": True},
        ],
        "g8MandatoryBeforeDisassembly": True,
        "g8CompliantVerified": True,
        "witnessQuorumCount": 2,
        "completedAt": "2026-05-26T10:30:00Z",
    }
    de.phase = DepollutionPhase.DATA_WIPE_COMPLETED
    de.dataWipe = mock_wipe
    de.completionPct = 25
    return {"depollution_state": de.__dict__, "next_node": "fluids"}


def transition_to_fluids_drained(state: dict[str, Any]) -> dict[str, Any]:
    """DATA_WIPE_COMPLETED → FLUIDS_DRAINED."""
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_fluids = {
        "fuel": {"type": "gasoline-95", "drainedLiters": 12.5, "containerCid": "bafkreifuel001..."},
        "engineOil": {"type": "5W-30-synthetic", "drainedLiters": 4.8, "containerCid": "bafkreioil001..."},
        "coolant": {"type": "ethylene-glycol-G12", "drainedLiters": 6.2, "containerCid": "bafkreicool001..."},
        "brakeFluid": {"type": "DOT-4", "drainedLiters": 0.5, "containerCid": "bafkreibrake001..."},
        "washerFluid": {"type": "methanol-water", "drainedLiters": 2.1, "containerCid": "bafkreiwash001..."},
        "transmissionFluid": {"type": "ATF-Dexron-VI", "drainedLiters": 7.8, "containerCid": "bafkreiatf001..."},
        "totalLiters": 33.9,
        "nukuRobotDispense": True,
    }
    de.phase = DepollutionPhase.FLUIDS_DRAINED
    de.fluidsDrain = mock_fluids
    de.completionPct = 50
    return {"depollution_state": de.__dict__, "next_node": "fgas"}


def transition_to_fgas_captured(state: dict[str, Any]) -> dict[str, Any]:
    """FLUIDS_DRAINED → FGAS_CAPTURED. G6 ≥95% F-gas capture; NO atmospheric venting."""
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_fgas = {
        "refrigerantType": "R1234yf",
        "preChargeGramsLabel": 510,
        "recoveredGrams": 491,
        "recoveryRatePct": 96.3,
        "g6Limit_min_pct": 95.0,
        "g6Compliant": True,
        "atmosphericVentingDetected": False,
        "captureStationDid": "did:web:etzhayyim.com:fgas-station-001",
        "leakRateGramsPerHr": 0.0,
        "recoveredContainerCid": "bafkreir1234yf001...",
    }
    de.phase = DepollutionPhase.FGAS_CAPTURED
    de.fgasCapture = mock_fgas
    de.completionPct = 72
    return {"depollution_state": de.__dict__, "next_node": "airbags"}


def transition_to_airbags_neutralized(state: dict[str, Any]) -> dict[str, Any]:
    """FGAS_CAPTURED → AIRBAGS_NEUTRALIZED. G7 pyrotechnic safe-disposal."""
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_airbags = {
        "airbagsLocated": 8,
        "airbagsManualDeploymentMethod": "harness-disconnect-then-electrical-trigger",
        "airbagsDeployedSafely": 8,
        "pyrotechnicResidueCollected": True,
        "g7ThermalEventLog": "none",
        "g10SbtGatedOperator": True,
    }
    de.phase = DepollutionPhase.AIRBAGS_NEUTRALIZED
    de.airbagNeutralization = mock_airbags
    de.completionPct = 87
    return {"depollution_state": de.__dict__, "next_node": "battery"}


def transition_to_battery_disconnected(state: dict[str, Any]) -> dict[str, Any]:
    """AIRBAGS_NEUTRALIZED → BATTERY_DISCONNECTED. Pass-through to L2 elv_battery_handling."""
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_batt = {
        "primaryBattery": {"type": "Li-ion-NMC", "nominalKwh": 12.0, "presentInVehicle": True},
        "auxBattery12V": {"type": "lead-acid-AGM", "ahCap": 80, "presentInVehicle": True},
        "primaryDisconnected": True,
        "auxDisconnected": True,
        "thermalEventLog": "none",
        "removedToBatteryHandlingCell": True,
    }
    de.phase = DepollutionPhase.BATTERY_DISCONNECTED
    de.batteryDisconnect = mock_batt
    de.completionPct = 95
    return {"depollution_state": de.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    de = DepollutionState(**state.get("depollution_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:nuku-joseph-unit-1",
            "role": "fluid_drain_fgas_witness",
            "timestamp": "2026-05-26T11:30:00Z",
            "signature": "iI1jJ2kK3lL4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-joseph-unit-1",
            "role": "fgas_metrology_airbag_witness",
            "timestamp": "2026-05-26T11:30:05Z",
            "signature": "mM5nN6oO7pP8...",
        },
    ]
    de.phase = DepollutionPhase.ATTESTATION_EMITTED
    de.robotSignatures = mock_sigs
    de.completionPct = 100

    wipe_record = {
        "$type": "com.etzhayyim.hodoki.dataWipeAttestation",
        "vehicleId": de.vehicleId,
        "ecuWipes": de.dataWipe["ecuWipes"] if de.dataWipe else [],
        "g8Compliant": True,
        "witnessQuorumCount": 2,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T11:30:10Z",
    }
    depollution_record = {
        "$type": "com.etzhayyim.hodoki.depollutionAttestation",
        "vehicleId": de.vehicleId,
        "fluids": de.fluidsDrain,
        "fgasCapture": de.fgasCapture,
        "airbags": de.airbagNeutralization,
        "batteryDisconnect": de.batteryDisconnect,
        "g6Compliant": True,
        "g7Compliant": True,
        "g8Compliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T11:30:12Z",
    }
    return {
        "depollution_state": de.__dict__,
        "data_wipe_attestation": wipe_record,
        "depollution_attestation": depollution_record,
        "next_node": "end",
    }
