"""Fabric attestation state machine — ADR-2605261115 L4a (makura).

Recycled poly / organic cotton preferred. Charter Rider §2(a-h) scan on every
print artwork (G5). No licensed IP / brand co-branding (N8). Dye safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FabricPhase(Enum):
    INIT = "init"
    SOURCE_VERIFIED = "source_verified"
    DYE_VERIFIED = "dye_verified"
    CHARTER_SCANNED = "charter_scanned"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class FabricState:
    phase: FabricPhase
    lotId: str
    completionPct: int
    fabricRoll: dict[str, Any] | None = None
    dyeReport: dict[str, Any] | None = None
    charterScan: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_source_verified(state: dict[str, Any]) -> dict[str, Any]:
    fa = FabricState(**state.get("fabric_state", {}))
    mock_roll = {
        "vendorDid": "did:web:vendor.example.com:textiles",
        "lotId": "FABRIC-RECYP-2026-05-LOT-0237",
        "blend": [
            {"fiber": "recycled-polyester-rPET", "massPct": 80},
            {"fiber": "organic-cotton-GOTS", "massPct": 20},
        ],
        "weightGsm": 180,
        "weaveType": "knit-jersey",
        "certCid": "bafkreifabric0237...",
        "originCountry": "JP",
    }
    fa.phase = FabricPhase.SOURCE_VERIFIED
    fa.fabricRoll = mock_roll
    fa.completionPct = 30
    return {"fabric_state": fa.__dict__, "next_node": "dye"}


def transition_to_dye_verified(state: dict[str, Any]) -> dict[str, Any]:
    """G5 / G7 — dye safety. No AZO restricted amines, no formaldehyde release."""
    fa = FabricState(**state.get("fabric_state", {}))
    mock_dye = {
        "dyeClass": "reactive-dye",
        "azoRestrictedAminesPresent": False,
        "formaldehydeReleasePpm": 12,
        "formaldehydeLimitPpm": 75,
        "oekoTexClass": "Class-I-baby",
    }
    fa.phase = FabricPhase.DYE_VERIFIED
    fa.dyeReport = mock_dye
    fa.completionPct = 60
    return {"fabric_state": fa.__dict__, "next_node": "charter"}


def transition_to_charter_scanned(state: dict[str, Any]) -> dict[str, Any]:
    """G5 Charter Rider §2(a-h) scan on print artwork. N8 no licensed IP."""
    fa = FabricState(**state.get("fabric_state", {}))
    mock_scan = {
        "artworkCid": "bafkreiartwork0237...",
        "scannerVersion": "etzhayyim_organism.sensors.charter_rider@1.0",
        "section2aWeapons": "clear",
        "section2bSecrecy": "clear",
        "section2cSurveillance": "clear",
        "section2dInfrastructureAttack": "clear",
        "section2eAntiGatekeeping": "clear",
        "section2fHarm": "clear",
        "section2gEnvironmental": "clear",
        "section2hMedicalHarm": "clear",
        "licensedIpDetected": False,
        "eschatologyDetected": False,
        "overallVerdict": "pass",
    }
    fa.phase = FabricPhase.CHARTER_SCANNED
    fa.charterScan = mock_scan
    fa.completionPct = 85
    return {"fabric_state": fa.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    fa = FabricState(**state.get("fabric_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:watari-simeon-unit-1",
            "role": "fabric_witness",
            "timestamp": "2026-05-26T11:00:00Z",
            "signature": "eF1gH2iJ3kL4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-simeon-unit-1",
            "role": "dye_metrology",
            "timestamp": "2026-05-26T11:00:05Z",
            "signature": "mN5oP6qR7sT8...",
        },
    ]
    fa.phase = FabricPhase.ATTESTATION_EMITTED
    fa.robotSignatures = mock_sigs
    fa.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.fabricAttestation",
        "lotId": fa.lotId,
        "fabricRoll": fa.fabricRoll,
        "dyeReport": fa.dyeReport,
        "charterScan": fa.charterScan,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T11:00:10Z",
    }
    return {"fabric_state": fa.__dict__, "fabric_attestation": record, "next_node": "end"}
