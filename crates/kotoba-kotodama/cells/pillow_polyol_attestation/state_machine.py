"""Polyol attestation state machine — ADR-2605261115 L1a (makura)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PolyolPhase(Enum):
    INIT = "init"
    POLYOL_VERIFIED = "polyol_verified"
    CATALYST_VERIFIED = "catalyst_verified"
    SURFACTANT_VERIFIED = "surfactant_verified"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class PolyolState:
    phase: PolyolPhase
    batchId: str
    completionPct: int
    polyolLot: dict[str, Any] | None = None
    catalystLot: dict[str, Any] | None = None
    surfactantLot: dict[str, Any] | None = None
    blowingAgentLot: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_polyol_verified(state: dict[str, Any]) -> dict[str, Any]:
    """INIT → POLYOL_VERIFIED. Verify polyol lot (OH number, viscosity, bio-content %)."""
    ps = PolyolState(**state.get("polyol_state", {}))
    mock_polyol = {
        "vendorDid": "did:web:vendor.example.com:polyols",
        "lotId": "POLYOL-PE-2026-05-LOT-0142",
        "polyolType": "polyether-triol",
        "ohNumberMgKohPerG": 56,
        "viscosityCps25C": 480,
        "bioContentPct": 23,
        "certCid": "bafkreipolyol0142...",
    }
    ps.phase = PolyolPhase.POLYOL_VERIFIED
    ps.polyolLot = mock_polyol
    ps.completionPct = 25
    return {"polyol_state": ps.__dict__, "next_node": "catalyst"}


def transition_to_catalyst_verified(state: dict[str, Any]) -> dict[str, Any]:
    """POLYOL_VERIFIED → CATALYST_VERIFIED. No Hg / Sn-based catalysts per G6."""
    ps = PolyolState(**state.get("polyol_state", {}))
    mock_catalyst = {
        "lotId": "DABCO-33LV-2026-05-LOT-0008",
        "type": "DABCO-33LV",
        "activeAmineWeightPct": 33,
        "mercuryFree": True,
        "tinFree": True,
        "certCid": "bafkreicat0008...",
    }
    ps.phase = PolyolPhase.CATALYST_VERIFIED
    ps.catalystLot = mock_catalyst
    ps.completionPct = 50
    return {"polyol_state": ps.__dict__, "next_node": "surfactant"}


def transition_to_surfactant_verified(state: dict[str, Any]) -> dict[str, Any]:
    """CATALYST_VERIFIED → SURFACTANT_VERIFIED."""
    ps = PolyolState(**state.get("polyol_state", {}))
    mock_surfactant = {
        "lotId": "SI-SURF-L580-2026-05-LOT-0033",
        "type": "silicone-polyether-copolymer",
        "molecularWeight": 5800,
        "certCid": "bafkreisurf0033...",
    }
    mock_blowing = {
        "type": "water",
        "partsPerHundredPolyol": 4.2,
        "hfcUsed": False,
        "councilAttestationRequired": False,
    }
    ps.phase = PolyolPhase.SURFACTANT_VERIFIED
    ps.surfactantLot = mock_surfactant
    ps.blowingAgentLot = mock_blowing
    ps.completionPct = 80
    return {"polyol_state": ps.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    """SURFACTANT_VERIFIED → ATTESTATION_EMITTED."""
    ps = PolyolState(**state.get("polyol_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-naphtali-unit-1",
            "role": "dispense_verify",
            "timestamp": "2026-05-26T08:00:00Z",
            "signature": "aB1cD2eF3gH4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-naphtali-unit-1",
            "role": "metrology_witness",
            "timestamp": "2026-05-26T08:00:05Z",
            "signature": "iJ5kL6mN7oP8...",
        },
    ]
    ps.phase = PolyolPhase.ATTESTATION_EMITTED
    ps.robotSignatures = mock_sigs
    ps.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.foamBatchAttestation",
        "section": "precursors",
        "batchId": ps.batchId,
        "polyol": ps.polyolLot,
        "catalyst": ps.catalystLot,
        "surfactant": ps.surfactantLot,
        "blowingAgent": ps.blowingAgentLot,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T08:00:10Z",
    }
    return {"polyol_state": ps.__dict__, "foam_batch_precursor_attestation": record, "next_node": "end"}
