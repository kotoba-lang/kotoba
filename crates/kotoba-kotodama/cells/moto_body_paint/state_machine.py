"""Body paint state machine — ADR-2605261330 L4 (futawa).

Body panel (Al sheet OR injection-molded recycled PP) + 2K acrylic urethane
paint + G5 Charter §2(a-h) artwork scan (no military / licensed-IP / racing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BodyPaintPhase(Enum):
    INIT = "init"
    PANEL_VERIFIED = "panel_verified"
    ARTWORK_CHARTER_SCANNED = "artwork_charter_scanned"
    PAINTED = "painted"
    CURE_QA = "cure_qa"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class BodyPaintState:
    phase: BodyPaintPhase
    vehicleId: str
    completionPct: int
    panel: dict[str, Any] | None = None
    charterScan: dict[str, Any] | None = None
    paintApplication: dict[str, Any] | None = None
    cureQa: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_panel_verified(state: dict[str, Any]) -> dict[str, Any]:
    bp = BodyPaintState(**state.get("body_paint_state", {}))
    mock = {
        "panelMaterial": "Al-5052-sheet",
        "panelSourceActor": "kanayama-wave-1",
        "recycledContentPct": 28,
        "panelCount": 6,
        "totalMassKg": 9.2,
    }
    bp.phase = BodyPaintPhase.PANEL_VERIFIED
    bp.panel = mock
    bp.completionPct = 20
    return {"body_paint_state": bp.__dict__, "next_node": "charter"}


def transition_to_artwork_charter_scanned(state: dict[str, Any]) -> dict[str, Any]:
    """G5 Charter §2(a-h) scan."""
    bp = BodyPaintState(**state.get("body_paint_state", {}))
    mock = {
        "artworkCid": "bafkreiartwork001...",
        "scannerVersion": "etzhayyim_organism.sensors.charter_rider@1.0",
        "section2aWeapons": "clear",
        "section2bSecrecy": "clear",
        "section2cSurveillance": "clear",
        "section2dInfrastructureAttack": "clear",
        "section2eAntiGatekeeping": "clear",
        "section2fHarm": "clear",
        "section2gEnvironmental": "clear",
        "section2hMedicalHarm": "clear",
        "militaryInsigniaDetected": False,
        "licensedIpDetected": False,
        "addictiveThrillImageryDetected": False,
        "racingGlorificationDetected": False,
        "overallVerdict": "pass",
    }
    bp.phase = BodyPaintPhase.ARTWORK_CHARTER_SCANNED
    bp.charterScan = mock
    bp.completionPct = 45
    return {"body_paint_state": bp.__dict__, "next_node": "paint"}


def transition_to_painted(state: dict[str, Any]) -> dict[str, Any]:
    bp = BodyPaintState(**state.get("body_paint_state", {}))
    mock = {
        "paintType": "2K-acrylic-urethane",
        "paintMethod": "electrostatic+HVLP",
        "robotApplicator": "Suri-simeon-unit-1",
        "primerCoatUm": 25,
        "baseCoatUm": 35,
        "clearCoatUm": 50,
        "vocGramPerL": 380,
        "vocLimitGramPerL": 420,
        "g7VocCompliant": True,
    }
    bp.phase = BodyPaintPhase.PAINTED
    bp.paintApplication = mock
    bp.completionPct = 75
    return {"body_paint_state": bp.__dict__, "next_node": "cure"}


def transition_to_cure_qa(state: dict[str, Any]) -> dict[str, Any]:
    bp = BodyPaintState(**state.get("body_paint_state", {}))
    mock = {
        "cureTempC": 80,
        "cureDurationMin": 45,
        "adhesionGritTest": "5B-ASTM-D3359",
        "glossUnits60deg": 88,
        "scratchTestPencil": "2H",
        "accept": True,
    }
    bp.phase = BodyPaintPhase.CURE_QA
    bp.cureQa = mock
    bp.completionPct = 92
    return {"body_paint_state": bp.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    bp = BodyPaintState(**state.get("body_paint_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:suri-simeon-unit-1", "role": "paint_applicator", "timestamp": "2026-05-27T14:00:00Z", "signature": "kK1lL2mM3nN4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-simeon-unit-2", "role": "cure_metrology", "timestamp": "2026-05-27T14:00:05Z", "signature": "oO5pP6qQ7rR8..."},
    ]
    bp.phase = BodyPaintPhase.ATTESTATION_EMITTED
    bp.robotSignatures = mock_sigs
    bp.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.paintAttestation",
        "vehicleId": bp.vehicleId,
        "panel": bp.panel,
        "charterScan": bp.charterScan,
        "paintApplication": bp.paintApplication,
        "cureQa": bp.cureQa,
        "g5CharterPass": True,
        "g7VocCompliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T14:00:10Z",
    }
    return {"body_paint_state": bp.__dict__, "paint_attestation": record, "next_node": "end"}
