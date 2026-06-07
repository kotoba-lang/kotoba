"""Foam shredding state machine — ADR-2605261115 L3 (makura).

Mechanical shredding to 8-15 mm crumb. Recycled crumb blend ≥10% by R3 (G13
take-back). No fragrance / oil impregnation (N7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FoamShreddingPhase(Enum):
    INIT = "init"
    SLAB_LOADED = "slab_loaded"
    SHREDDED = "shredded"
    PARTICLE_QC = "particle_qc"
    RECYCLED_BLEND_MIXED = "recycled_blend_mixed"
    CRUMB_READY = "crumb_ready"


@dataclass
class FoamShreddingState:
    phase: FoamShreddingPhase
    batchId: str
    completionPct: int
    slabSource: dict[str, Any] | None = None
    shredTelemetry: dict[str, Any] | None = None
    particleDistribution: dict[str, Any] | None = None
    recycledBlend: dict[str, Any] | None = None
    crumbReady: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_slab_loaded(state: dict[str, Any]) -> dict[str, Any]:
    sh = FoamShreddingState(**state.get("foam_shredding_state", {}))
    mock_slab = {
        "sourceBatchId": "MAKURA-BATCH-0001",
        "foamBatchAttestationCid": "bafkreifoamfinal0001...",
        "cureCompleteHr": 48,
        "totalKg": 1450,
        "dustCollectionVerified": True,
        "workerPpeVerified": True,
    }
    sh.phase = FoamShreddingPhase.SLAB_LOADED
    sh.slabSource = mock_slab
    sh.completionPct = 15
    return {"foam_shredding_state": sh.__dict__, "next_node": "shredded"}


def transition_to_shredded(state: dict[str, Any]) -> dict[str, Any]:
    sh = FoamShreddingState(**state.get("foam_shredding_state", {}))
    mock_shred = {
        "shredderType": "claw-rotor-twin-shaft",
        "rotorRpm": 320,
        "throughputKgPerHr": 180,
        "fragranceImpregnation": False,
        "oilImpregnation": False,
    }
    sh.phase = FoamShreddingPhase.SHREDDED
    sh.shredTelemetry = mock_shred
    sh.completionPct = 40
    return {"foam_shredding_state": sh.__dict__, "next_node": "particle_qc"}


def transition_to_particle_qc(state: dict[str, Any]) -> dict[str, Any]:
    sh = FoamShreddingState(**state.get("foam_shredding_state", {}))
    mock_qc = {
        "samplerMethod": "image-analysis-Mimi-vision",
        "targetMinMm": 8,
        "targetMaxMm": 15,
        "d10Mm": 7.5,
        "d50Mm": 11.2,
        "d90Mm": 14.8,
        "withinSpec": True,
    }
    sh.phase = FoamShreddingPhase.PARTICLE_QC
    sh.particleDistribution = mock_qc
    sh.completionPct = 65
    return {"foam_shredding_state": sh.__dict__, "next_node": "recycled_blend"}


def transition_to_recycled_blend_mixed(state: dict[str, Any]) -> dict[str, Any]:
    """G13 take-back recycled crumb blend (target ≥10% by R3; R0 design 0%)."""
    sh = FoamShreddingState(**state.get("foam_shredding_state", {}))
    mock_blend = {
        "recycledCrumbKg": 0,
        "virginCrumbKg": 1450,
        "recycledMassPct": 0.0,
        "g13TargetPctByR3": 10.0,
        "g13PhaseAtR0": "design-only",
    }
    sh.phase = FoamShreddingPhase.RECYCLED_BLEND_MIXED
    sh.recycledBlend = mock_blend
    sh.completionPct = 85
    return {"foam_shredding_state": sh.__dict__, "next_node": "crumb_ready"}


def transition_to_crumb_ready(state: dict[str, Any]) -> dict[str, Any]:
    sh = FoamShreddingState(**state.get("foam_shredding_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:awa-joseph-unit-1",
            "role": "shredder_witness",
            "timestamp": "2026-05-26T13:00:00Z",
            "signature": "wX1yZ2aB3cD4...",
        },
    ]
    sh.phase = FoamShreddingPhase.CRUMB_READY
    sh.robotSignatures = mock_sigs
    sh.completionPct = 100
    crumb_ready = {
        "batchId": sh.batchId,
        "totalCrumbKg": 1450,
        "particleDistribution": sh.particleDistribution,
        "recycledBlend": sh.recycledBlend,
        "readyForFill": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T13:00:10Z",
    }
    sh.crumbReady = crumb_ready
    return {"foam_shredding_state": sh.__dict__, "crumb_ready": crumb_ready, "next_node": "end"}
