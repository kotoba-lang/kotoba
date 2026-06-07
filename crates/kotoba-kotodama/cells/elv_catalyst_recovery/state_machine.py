"""ELV catalyst recovery state machine — ADR-2605261215 L3b (hodoki).

Catalytic converter brick removal + PGM (Pt/Pd/Rh) smelter handoff +
yield audit. G14 ≥95% yield invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CatalystPhase(Enum):
    INIT = "init"
    BRICK_REMOVED = "brick_removed"
    BRICK_WEIGHED = "brick_weighed"
    SMELTER_HANDOFF = "smelter_handoff"
    YIELD_AUDITED = "yield_audited"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class CatalystState:
    phase: CatalystPhase
    vehicleId: str
    completionPct: int
    brickRemoval: dict[str, Any] | None = None
    brickWeight: dict[str, Any] | None = None
    smelterHandoff: dict[str, Any] | None = None
    yieldAudit: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_brick_removed(state: dict[str, Any]) -> dict[str, Any]:
    cr = CatalystState(**state.get("catalyst_state", {}))
    mock_removal = {
        "catalystType": "three-way-catalyst",
        "substrate": "ceramic-cordierite",
        "exhaustPositionsRemoved": ["primary-close-coupled", "secondary-underbody"],
        "intactBrickCount": 2,
        "removalMethod": "thermal-cut-then-pry-out",
        "ipfsPhotoCid": "bafkreicatbrick001...",
    }
    cr.phase = CatalystPhase.BRICK_REMOVED
    cr.brickRemoval = mock_removal
    cr.completionPct = 25
    return {"catalyst_state": cr.__dict__, "next_node": "weigh"}


def transition_to_brick_weighed(state: dict[str, Any]) -> dict[str, Any]:
    cr = CatalystState(**state.get("catalyst_state", {}))
    mock_weight = {
        "brick1MassG": 1280,
        "brick2MassG": 640,
        "totalBrickMassG": 1920,
        "estimatedPtMassG": 1.4,
        "estimatedPdMassG": 3.8,
        "estimatedRhMassG": 0.32,
        "estimationMethod": "XRF-handheld",
        "xrfRunCid": "bafkreixrfcat001...",
    }
    cr.phase = CatalystPhase.BRICK_WEIGHED
    cr.brickWeight = mock_weight
    cr.completionPct = 50
    return {"catalyst_state": cr.__dict__, "next_node": "smelter"}


def transition_to_smelter_handoff(state: dict[str, Any]) -> dict[str, Any]:
    cr = CatalystState(**state.get("catalyst_state", {}))
    mock_handoff = {
        "smelterPartnerDid": "did:web:etzhayyim.com:pgm-smelter-001",
        "kanayamaYokinR2Plus": True,
        "handoffCustodyChainCid": "bafkreicustody001...",
        "shippedAt": "2026-05-26T15:00:00Z",
    }
    cr.phase = CatalystPhase.SMELTER_HANDOFF
    cr.smelterHandoff = mock_handoff
    cr.completionPct = 75
    return {"catalyst_state": cr.__dict__, "next_node": "yield_audit"}


def transition_to_yield_audited(state: dict[str, Any]) -> dict[str, Any]:
    """G14 ≥95% PGM yield invariant."""
    cr = CatalystState(**state.get("catalyst_state", {}))
    mock_audit = {
        "smelterReceiptCid": "bafkreismelterrecv001...",
        "actualPtRecoveredG": 1.34,
        "actualPdRecoveredG": 3.66,
        "actualRhRecoveredG": 0.31,
        "ptYieldPct": 95.7,
        "pdYieldPct": 96.3,
        "rhYieldPct": 96.9,
        "g14MinYieldPct": 95.0,
        "g14Compliant": True,
        "leakToAsrG": 0.0,
    }
    cr.phase = CatalystPhase.YIELD_AUDITED
    cr.yieldAudit = mock_audit
    cr.completionPct = 92
    return {"catalyst_state": cr.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    cr = CatalystState(**state.get("catalyst_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-levi-unit-2",
            "role": "brick_removal_witness",
            "timestamp": "2026-05-26T15:30:00Z",
            "signature": "iI1jJ2kK3lL4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-levi-unit-2",
            "role": "xrf_metrology",
            "timestamp": "2026-05-26T15:30:05Z",
            "signature": "mM5nN6oO7pP8...",
        },
    ]
    cr.phase = CatalystPhase.ATTESTATION_EMITTED
    cr.robotSignatures = mock_sigs
    cr.completionPct = 100
    record = {
        "$type": "com.etzhayyim.hodoki.catalystRecoveryRecord",
        "vehicleId": cr.vehicleId,
        "brickRemoval": cr.brickRemoval,
        "brickWeight": cr.brickWeight,
        "smelterHandoff": cr.smelterHandoff,
        "yieldAudit": cr.yieldAudit,
        "g14Compliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T15:30:10Z",
    }
    return {"catalyst_state": cr.__dict__, "catalyst_recovery_record": record, "next_node": "end"}
