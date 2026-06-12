"""Filling + close state machine — ADR-2605261115 L5a (makura).

Pneumatic crumb fill ±2% target weight + final stitch + bilingual care label
(G4) + full BoM disclosure tag (G12) + take-back QR (G13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FillClosePhase(Enum):
    INIT = "init"
    SHELL_RECEIVED = "shell_received"
    CRUMB_DISPENSED = "crumb_dispensed"
    CLOSE_STITCHED = "close_stitched"
    LABEL_ATTACHED = "label_attached"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class FillCloseState:
    phase: FillClosePhase
    lotId: str
    pillowSerial: str
    completionPct: int
    shellReady: dict[str, Any] | None = None
    fillTelemetry: dict[str, Any] | None = None
    closeStitch: dict[str, Any] | None = None
    label: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_shell_received(state: dict[str, Any]) -> dict[str, Any]:
    fc = FillCloseState(**state.get("fill_close_state", {}))
    mock_shell = {
        "lotId": fc.lotId,
        "shellSize": "standard-50x35",
        "openSeamReady": True,
        "shellAttestationCid": "bafkreishell0001...",
    }
    fc.phase = FillClosePhase.SHELL_RECEIVED
    fc.shellReady = mock_shell
    fc.completionPct = 15
    return {"fill_close_state": fc.__dict__, "next_node": "fill"}


def transition_to_crumb_dispensed(state: dict[str, Any]) -> dict[str, Any]:
    fc = FillCloseState(**state.get("fill_close_state", {}))
    mock_fill = {
        "targetKg": 0.85,
        "actualKg": 0.853,
        "tolerancePct": 0.35,
        "g11MaxFoamMassKg": 2.0,
        "withinG11Cap": True,
        "pneumaticPressureBar": 1.8,
        "fillTimeS": 6.2,
    }
    fc.phase = FillClosePhase.CRUMB_DISPENSED
    fc.fillTelemetry = mock_fill
    fc.completionPct = 45
    return {"fill_close_state": fc.__dict__, "next_node": "close"}


def transition_to_close_stitched(state: dict[str, Any]) -> dict[str, Any]:
    fc = FillCloseState(**state.get("fill_close_state", {}))
    mock_close = {
        "stitchType": "blind-stitch-overlock",
        "stitchesPerCm": 4.5,
        "seamPullTestN": 62,
        "needleVisionCheck": "pass",
    }
    fc.phase = FillClosePhase.CLOSE_STITCHED
    fc.closeStitch = mock_close
    fc.completionPct = 70
    return {"fill_close_state": fc.__dict__, "next_node": "label"}


def transition_to_label_attached(state: dict[str, Any]) -> dict[str, Any]:
    """G4 bilingual + G12 BoM disclosure + G13 take-back QR."""
    fc = FillCloseState(**state.get("fill_close_state", {}))
    mock_label = {
        "languagesPresent": ["ja", "en"],
        "g4BilingualMinimumMet": True,
        "bom": {
            "polyolType": "polyether-triol",
            "polyolBiocontentPct": 23,
            "blowingAgent": "water",
            "fabricBlend": [
                {"fiber": "recycled-polyester-rPET", "massPct": 80},
                {"fiber": "organic-cotton-GOTS", "massPct": 20},
            ],
            "fillWeightKg": 0.853,
            "fillForm": "shred",
            "fireRetardant": "none",
            "originCountry": "JP",
        },
        "g12FullBomDisclosed": True,
        "takeBackQrCid": "bafkreitakeback0001...",
        "pillowDid": f"did:web:etzhayyim.com:makura:pillow:{fc.pillowSerial}",
        "g13TakeBackQrPresent": True,
        "embeddedElectronics": "none",
        "g14NoEmbeddedElectronics": True,
    }
    fc.phase = FillClosePhase.LABEL_ATTACHED
    fc.label = mock_label
    fc.completionPct = 90
    return {"fill_close_state": fc.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    fc = FillCloseState(**state.get("fill_close_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-dan-unit-1",
            "role": "fill_dispense_witness",
            "timestamp": "2026-05-26T14:00:00Z",
            "signature": "cD1eF2gH3iJ4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:watari-dan-unit-1",
            "role": "close_stitch_witness",
            "timestamp": "2026-05-26T14:00:05Z",
            "signature": "kL5mN6oP7qR8...",
        },
    ]
    fc.phase = FillClosePhase.ATTESTATION_EMITTED
    fc.robotSignatures = mock_sigs
    fc.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.pillowLotAttestation",
        "lotId": fc.lotId,
        "pillowSerial": fc.pillowSerial,
        "pillowDid": f"did:web:etzhayyim.com:makura:pillow:{fc.pillowSerial}",
        "shellReady": fc.shellReady,
        "fill": fc.fillTelemetry,
        "closeStitch": fc.closeStitch,
        "label": fc.label,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T14:00:10Z",
    }
    return {"fill_close_state": fc.__dict__, "pillow_lot_attestation": record, "next_node": "end"}
