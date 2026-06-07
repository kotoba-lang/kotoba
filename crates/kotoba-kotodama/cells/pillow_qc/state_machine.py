"""QC state machine — ADR-2605261115 L5b (makura).

Dimensional + weight + ILD + visual defect QC. Otete + Mimi witness quorum (G3).
Reject rate <0.5%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QcPhase(Enum):
    INIT = "init"
    DIMENSIONAL = "dimensional"
    WEIGHT = "weight"
    ILD = "ild"
    VISUAL = "visual"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class QcState:
    phase: QcPhase
    lotId: str
    pillowSerial: str
    completionPct: int
    dimensional: dict[str, Any] | None = None
    weight: dict[str, Any] | None = None
    ild: dict[str, Any] | None = None
    visual: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_dimensional(state: dict[str, Any]) -> dict[str, Any]:
    qc = QcState(**state.get("qc_state", {}))
    mock_dim = {
        "specLengthMm": 500,
        "actualLengthMm": 498,
        "specWidthMm": 350,
        "actualWidthMm": 352,
        "specHeightMm": 120,
        "actualHeightMm": 119,
        "toleranceMm": 5,
        "withinSpec": True,
    }
    qc.phase = QcPhase.DIMENSIONAL
    qc.dimensional = mock_dim
    qc.completionPct = 25
    return {"qc_state": qc.__dict__, "next_node": "weight"}


def transition_to_weight(state: dict[str, Any]) -> dict[str, Any]:
    qc = QcState(**state.get("qc_state", {}))
    mock_weight = {
        "specKg": 0.85,
        "actualKg": 0.853,
        "tolerancePct": 0.35,
        "g11MaxFoamMassKg": 2.0,
        "withinG11Cap": True,
        "withinSpec": True,
    }
    qc.phase = QcPhase.WEIGHT
    qc.weight = mock_weight
    qc.completionPct = 50
    return {"qc_state": qc.__dict__, "next_node": "ild"}


def transition_to_ild(state: dict[str, Any]) -> dict[str, Any]:
    """ILD = Indentation Load Deflection. ASTM D3574 Test B equivalent."""
    qc = QcState(**state.get("qc_state", {}))
    mock_ild = {
        "test": "ASTM-D3574-B",
        "indentationDepthPct": 25,
        "loadN": 75,
        "specMinN": 60,
        "specMaxN": 95,
        "withinSpec": True,
    }
    qc.phase = QcPhase.ILD
    qc.ild = mock_ild
    qc.completionPct = 75
    return {"qc_state": qc.__dict__, "next_node": "visual"}


def transition_to_visual(state: dict[str, Any]) -> dict[str, Any]:
    qc = QcState(**state.get("qc_state", {}))
    mock_visual = {
        "inspector": "Mimi-vision-model-v1",
        "stainsDetected": 0,
        "uncutThreadsDetected": 0,
        "seamDefectsDetected": 0,
        "labelLegibilityCheck": "pass",
        "takeBackQrLegibilityCheck": "pass",
        "rejectPct": 0.2,
        "rejectSpecMaxPct": 0.5,
        "accept": True,
    }
    qc.phase = QcPhase.VISUAL
    qc.visual = mock_visual
    qc.completionPct = 95
    return {"qc_state": qc.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    """G3 Otete + Mimi witness quorum."""
    qc = QcState(**state.get("qc_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-levi-unit-1",
            "role": "qc_handler",
            "timestamp": "2026-05-26T15:00:00Z",
            "signature": "sT1uV2wX3yZ4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-levi-unit-1",
            "role": "qc_metrology",
            "timestamp": "2026-05-26T15:00:05Z",
            "signature": "aB5cD6eF7gH8...",
        },
    ]
    qc.phase = QcPhase.ATTESTATION_EMITTED
    qc.robotSignatures = mock_sigs
    qc.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.qcRecord",
        "lotId": qc.lotId,
        "pillowSerial": qc.pillowSerial,
        "pillowDid": f"did:web:etzhayyim.com:makura:pillow:{qc.pillowSerial}",
        "dimensional": qc.dimensional,
        "weight": qc.weight,
        "ild": qc.ild,
        "visual": qc.visual,
        "overallAccept": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T15:00:10Z",
    }
    return {"qc_state": qc.__dict__, "qc_record": record, "next_node": "end"}
