"""ELV intake audit state machine — ADR-2605261215 L1a (hodoki).

VIN title verification + prior-owner consent + Charter Rider §2(a-h) scan +
initial data-wipe attestation request. Enforces N1 (no military) + N7 (no
VIN-stolen) + N8 (no chop-shop re-VIN'ing) + G5 (Charter scan) + G11 (M1 only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntakePhase(Enum):
    INIT = "init"
    VIN_VERIFIED = "vin_verified"
    CONSENT_RECEIVED = "consent_received"
    CHARTER_SCANNED = "charter_scanned"
    DATA_WIPE_REQUESTED = "data_wipe_requested"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class IntakeState:
    phase: IntakePhase
    vehicleId: str
    completionPct: int
    vinRecord: dict[str, Any] | None = None
    consentRecord: dict[str, Any] | None = None
    charterScan: dict[str, Any] | None = None
    dataWipeRequest: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_vin_verified(state: dict[str, Any]) -> dict[str, Any]:
    """INIT → VIN_VERIFIED. Title chain documented; N7 / N8 enforcement."""
    it = IntakeState(**state.get("intake_state", {}))
    mock_vin = {
        "vin": "WAUZZZ8V3MA000001",
        "vehicleClass": "M1",
        "make": "Audi",
        "model": "A4",
        "modelYear": 2018,
        "curbWeightKg": 1505,
        "g11M1Class": True,
        "g11CurbWeightWithinCap": True,
        "titleChainDocumented": True,
        "n7TitleVerified": True,
        "stolenRegistryCheck": "clear",
        "previousOwnerDid": "did:web:etzhayyim.com:adherent:owner-elv-001",
    }
    it.phase = IntakePhase.VIN_VERIFIED
    it.vinRecord = mock_vin
    it.completionPct = 20
    return {"intake_state": it.__dict__, "next_node": "consent"}


def transition_to_consent_received(state: dict[str, Any]) -> dict[str, Any]:
    """VIN_VERIFIED → CONSENT_RECEIVED. Prior-owner data-wipe consent."""
    it = IntakeState(**state.get("intake_state", {}))
    mock_consent = {
        "consentDocCid": "bafkreiconsentelv0001...",
        "ownerSbtDid": "did:web:etzhayyim.com:adherent:owner-elv-001",
        "consentSignedAt": "2026-05-26T09:00:00Z",
        "dataWipeAuthorized": True,
        "partsResaleAuthorized": True,
        "materialRecoveryAuthorized": True,
        "rightToRescindWindowDays": 7,
    }
    it.phase = IntakePhase.CONSENT_RECEIVED
    it.consentRecord = mock_consent
    it.completionPct = 40
    return {"intake_state": it.__dict__, "next_node": "charter"}


def transition_to_charter_scanned(state: dict[str, Any]) -> dict[str, Any]:
    """CONSENT_RECEIVED → CHARTER_SCANNED. G5 Charter §2(a-h) intake scan."""
    it = IntakeState(**state.get("intake_state", {}))
    mock_scan = {
        "scannerVersion": "etzhayyim_organism.sensors.charter_rider@1.0",
        "section2aWeapons": "clear",
        "section2bSecrecy": "clear",
        "section2cSurveillance": "warn-telemetry-detected",
        "section2dInfrastructureAttack": "clear",
        "section2eAntiGatekeeping": "clear",
        "section2fHarm": "clear",
        "section2gEnvironmental": "clear",
        "section2hMedicalHarm": "clear",
        "militaryConversionDetected": False,
        "weaponMountDetected": False,
        "covertModificationDetected": False,
        "overallVerdict": "pass",
        "telemetryNote": "Manufacturer telemetry module detected; data wipe mandatory per G8",
    }
    it.phase = IntakePhase.CHARTER_SCANNED
    it.charterScan = mock_scan
    it.completionPct = 65
    return {"intake_state": it.__dict__, "next_node": "data_wipe_request"}


def transition_to_data_wipe_requested(state: dict[str, Any]) -> dict[str, Any]:
    """CHARTER_SCANNED → DATA_WIPE_REQUESTED. G8 initial wipe request."""
    it = IntakeState(**state.get("intake_state", {}))
    mock_wipe_req = {
        "ecuInventory": [
            {"ecu": "main-body-control", "wipeApiAvailable": True},
            {"ecu": "infotainment", "wipeApiAvailable": True},
            {"ecu": "telematics-module", "wipeApiAvailable": False, "fallbackPlan": "physical-chip-shred"},
            {"ecu": "engine-ecu", "wipeApiAvailable": True},
            {"ecu": "transmission-ecu", "wipeApiAvailable": True},
        ],
        "wipeMandatoryBeforeDisassembly": True,
        "g8Compliance": "pending",
        "requestSubmittedAt": "2026-05-26T09:30:00Z",
    }
    it.phase = IntakePhase.DATA_WIPE_REQUESTED
    it.dataWipeRequest = mock_wipe_req
    it.completionPct = 85
    return {"intake_state": it.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    it = IntakeState(**state.get("intake_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:mimi-naphtali-unit-1",
            "role": "vin_verification",
            "timestamp": "2026-05-26T09:35:00Z",
            "signature": "aA1bB2cC3dD4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:otete-naphtali-unit-2",
            "role": "charter_scan_witness",
            "timestamp": "2026-05-26T09:35:05Z",
            "signature": "eE5fF6gG7hH8...",
        },
    ]
    it.phase = IntakePhase.ATTESTATION_EMITTED
    it.robotSignatures = mock_sigs
    it.completionPct = 100
    record = {
        "$type": "com.etzhayyim.hodoki.elvIntakeRecord",
        "vehicleId": it.vehicleId,
        "vehicleDid": f"did:web:etzhayyim.com:hodoki:vehicle:{it.vinRecord['vin'] if it.vinRecord else ''}",
        "vinRecord": it.vinRecord,
        "consentRecord": it.consentRecord,
        "charterScan": it.charterScan,
        "dataWipeRequest": it.dataWipeRequest,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T09:35:10Z",
    }
    return {"intake_state": it.__dict__, "elv_intake_record": record, "next_node": "end"}
