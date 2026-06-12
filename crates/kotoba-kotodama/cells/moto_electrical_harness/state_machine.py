"""Electrical harness state machine — ADR-2605261330 L3a (futawa).

CONSTITUTIONAL FIRST G8: build-time anti-surveillance.
NO GPS tracker / NO connected-app / NO always-on telematics / NO V2X / NO
proprietary diagnostic-DRM built-in. Only passive odometer + safety ECU.
§2(c) anti-surveillance at vehicle BUILD time; companion to hodoki G8 EOL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HarnessPhase(Enum):
    INIT = "init"
    SCHEMATIC_VERIFIED = "schematic_verified"
    HARNESS_ROUTED = "harness_routed"
    ECU_FLASHED = "ecu_flashed"
    SURVEILLANCE_NEGATIVE_AUDIT = "surveillance_negative_audit"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class HarnessState:
    phase: HarnessPhase
    vehicleId: str
    completionPct: int
    schematic: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    ecuFlash: dict[str, Any] | None = None
    surveillanceAudit: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_schematic_verified(state: dict[str, Any]) -> dict[str, Any]:
    ha = HarnessState(**state.get("harness_state", {}))
    mock = {
        "schematicCadCid": "bafkreischematic001...",
        "g1OpenSourceCad": True,
        "circuitCount": 38,
        "fuseCount": 12,
        "harnessLengthMm": 4800,
    }
    ha.phase = HarnessPhase.SCHEMATIC_VERIFIED
    ha.schematic = mock
    ha.completionPct = 20
    return {"harness_state": ha.__dict__, "next_node": "routing"}


def transition_to_harness_routed(state: dict[str, Any]) -> dict[str, Any]:
    ha = HarnessState(**state.get("harness_state", {}))
    mock = {
        "routingMethod": "Otete-vision-guided",
        "wireSourceActor": "kanayama-wave-3",
        "cuRecycledContentPct": 35,
        "g13RecycledCompliant": True,
        "tieDownPointsCount": 22,
    }
    ha.phase = HarnessPhase.HARNESS_ROUTED
    ha.routing = mock
    ha.completionPct = 45
    return {"harness_state": ha.__dict__, "next_node": "ecu"}


def transition_to_ecu_flashed(state: dict[str, Any]) -> dict[str, Any]:
    ha = HarnessState(**state.get("harness_state", {}))
    mock = {
        "ecuPartNumber": "FUTAWA-ECU-250-R0",
        "firmwareCid": "bafkreifutawaecuFw...",
        "g1OpenSourceFirmware": True,
        "firmwareSourceCid": "bafkreifutawaecuFwsrc...",
        "diagnosticProtocol": "open-OBD-II-CAN",
        "g12OpenDiagnosticProtocol": True,
        "antiDrmFlag": False,
    }
    ha.phase = HarnessPhase.ECU_FLASHED
    ha.ecuFlash = mock
    ha.completionPct = 70
    return {"harness_state": ha.__dict__, "next_node": "surveillance_audit"}


def transition_to_surveillance_negative_audit(state: dict[str, Any]) -> dict[str, Any]:
    """G8 NEGATIVE AUDIT — verify ABSENCE of surveillance features."""
    ha = HarnessState(**state.get("harness_state", {}))
    mock = {
        "gpsTrackerInstalled": False,
        "cellularModemInstalled": False,
        "wifiModuleInstalled": False,
        "bluetoothModuleInstalled": False,
        "alwaysOnTelematicsInstalled": False,
        "v2xRadioInstalled": False,
        "pairedPhoneIntegrationInstalled": False,
        "cloudConnectedEcuInstalled": False,
        "proprietaryDiagnosticDrmInstalled": False,
        "g8AllAbsent": True,
        "g8Compliant": True,
        "permittedElectronicsListed": [
            "passive-odometer",
            "safety-ecu-engine-abs-lighting",
            "optional-user-installed-after-purchase-open-source-gps-module",
        ],
        "auditMethod": "Mimi-vision-inventory + harness-physical-trace + ECU-firmware-static-analysis",
        "auditIpfsCid": "bafkreig8audit001...",
    }
    ha.phase = HarnessPhase.SURVEILLANCE_NEGATIVE_AUDIT
    ha.surveillanceAudit = mock
    ha.completionPct = 92
    return {"harness_state": ha.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    ha = HarnessState(**state.get("harness_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:otete-simeon-unit-1", "role": "harness_routing", "timestamp": "2026-05-27T12:00:00Z", "signature": "uU1vV2wW3xX4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-simeon-unit-1", "role": "g8_surveillance_negative_audit", "timestamp": "2026-05-27T12:00:05Z", "signature": "yY5zZ6aA7bB8..."},
    ]
    ha.phase = HarnessPhase.ATTESTATION_EMITTED
    ha.robotSignatures = mock_sigs
    ha.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.electricalAttestation",
        "vehicleId": ha.vehicleId,
        "schematic": ha.schematic,
        "routing": ha.routing,
        "ecuFlash": ha.ecuFlash,
        "surveillanceAudit": ha.surveillanceAudit,
        "g8Compliant": True,
        "g12OpenDiagnostic": True,
        "g13RecycledCuCompliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T12:00:10Z",
    }
    return {"harness_state": ha.__dict__, "electrical_attestation": record, "next_node": "end"}
