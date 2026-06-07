"""Frame welding state machine — ADR-2605261330 L1 (futawa).

Steel/Al tube + sheet frame welding with Tsugite vision-guided robot.
G13 ≥10% recycled-content from kanayama via hodoki by R3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FramePhase(Enum):
    INIT = "init"
    MATERIAL_VERIFIED = "material_verified"
    JIG_LOADED = "jig_loaded"
    WELDED = "welded"
    DIMENSIONAL_QA = "dimensional_qa"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class FrameState:
    phase: FramePhase
    vehicleId: str
    completionPct: int
    materialLot: dict[str, Any] | None = None
    jigSetup: dict[str, Any] | None = None
    weldPasses: list[dict[str, Any]] = field(default_factory=list)
    dimensionalQa: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_material_verified(state: dict[str, Any]) -> dict[str, Any]:
    fr = FrameState(**state.get("frame_state", {}))
    mock = {
        "alloy": "6061-T6-Al",
        "lotId": "AL6061-2026-05-LOT-0042",
        "sourceActor": "kanayama-wave-1",
        "recycledContentPct": 12,
        "g13MinRecycledPctR3": 10,
        "g13Compliant": True,
        "certCid": "bafkreial001...",
    }
    fr.phase = FramePhase.MATERIAL_VERIFIED
    fr.materialLot = mock
    fr.completionPct = 20
    return {"frame_state": fr.__dict__, "next_node": "jig"}


def transition_to_jig_loaded(state: dict[str, Any]) -> dict[str, Any]:
    fr = FrameState(**state.get("frame_state", {}))
    mock = {
        "jigType": "trellis-frame-fixture-250cc",
        "geometryCadCid": "bafkreiframecad001...",
        "g1OpenSourceCad": True,
        "tubeCount": 14,
        "sheetCount": 4,
    }
    fr.phase = FramePhase.JIG_LOADED
    fr.jigSetup = mock
    fr.completionPct = 40
    return {"frame_state": fr.__dict__, "next_node": "weld"}


def transition_to_welded(state: dict[str, Any]) -> dict[str, Any]:
    fr = FrameState(**state.get("frame_state", {}))
    mock_passes = [
        {"pass": 1, "process": "TIG-AC", "amp": 140, "joint": "headstock-cluster", "ipfsCid": "bafkreiweld1..."},
        {"pass": 2, "process": "TIG-AC", "amp": 140, "joint": "swingarm-pivot-cluster", "ipfsCid": "bafkreiweld2..."},
        {"pass": 3, "process": "TIG-AC", "amp": 140, "joint": "footpeg-mount", "ipfsCid": "bafkreiweld3..."},
        {"pass": 4, "process": "TIG-AC", "amp": 160, "joint": "engine-mount-bridge", "ipfsCid": "bafkreiweld4..."},
    ]
    fr.phase = FramePhase.WELDED
    fr.weldPasses = mock_passes
    fr.completionPct = 70
    return {"frame_state": fr.__dict__, "next_node": "qa"}


def transition_to_dimensional_qa(state: dict[str, Any]) -> dict[str, Any]:
    fr = FrameState(**state.get("frame_state", {}))
    mock = {
        "wheelbaseMm": 1380,
        "wheelbaseTolMm": 2,
        "rakeAngleDeg": 24.5,
        "rakeAngleTolDeg": 0.3,
        "trailMm": 95,
        "trailTolMm": 2,
        "headstockSquareMm": 0.4,
        "accept": True,
    }
    fr.phase = FramePhase.DIMENSIONAL_QA
    fr.dimensionalQa = mock
    fr.completionPct = 90
    return {"frame_state": fr.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    fr = FrameState(**state.get("frame_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:tsugite-naphtali-unit-1", "role": "weld_witness", "timestamp": "2026-05-27T09:00:00Z", "signature": "aA1bB2cC3dD4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-naphtali-unit-1", "role": "dimensional_metrology", "timestamp": "2026-05-27T09:00:05Z", "signature": "eE5fF6gG7hH8..."},
    ]
    fr.phase = FramePhase.ATTESTATION_EMITTED
    fr.robotSignatures = mock_sigs
    fr.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.frameAttestation",
        "vehicleId": fr.vehicleId,
        "materialLot": fr.materialLot,
        "jig": fr.jigSetup,
        "weldPasses": fr.weldPasses,
        "dimensionalQa": fr.dimensionalQa,
        "g13RecycledContentCompliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T09:00:10Z",
    }
    return {"frame_state": fr.__dict__, "frame_attestation": record, "next_node": "end"}
