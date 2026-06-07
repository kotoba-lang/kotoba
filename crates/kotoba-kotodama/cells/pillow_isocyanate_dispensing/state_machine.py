"""Isocyanate dispensing state machine — ADR-2605261115 L1b (makura).

Implements G6 closed-loop isocyanate (MDI preferred over TDI) dispensing
with worker exposure ≤ 5 ppb MDI / ≤ 2 ppb TDI 8h TWA enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IsocyanatePhase(Enum):
    INIT = "init"
    LOT_VERIFIED = "lot_verified"
    EXPOSURE_BASELINE = "exposure_baseline"
    DISPENSED = "dispensed"
    EXPOSURE_FINAL = "exposure_final"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class IsocyanateState:
    phase: IsocyanatePhase
    batchId: str
    completionPct: int
    isocyanateLot: dict[str, Any] | None = None
    exposureBaseline: dict[str, Any] | None = None
    dispenseTelemetry: dict[str, Any] | None = None
    exposureFinal: dict[str, Any] | None = None
    sbtOperatorDid: str = ""
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_lot_verified(state: dict[str, Any]) -> dict[str, Any]:
    """INIT → LOT_VERIFIED. MDI preferred; TDI requires Council attestation."""
    iso = IsocyanateState(**state.get("isocyanate_state", {}))
    mock_iso = {
        "vendorDid": "did:web:vendor.example.com:isocyanates",
        "lotId": "MDI-PURE-2026-05-LOT-0091",
        "type": "MDI",
        "isomerSplit": "4,4'-MDI 98%",
        "ncoContentPct": 33.6,
        "councilAttestation": None,
        "certCid": "bafkreimdi0091...",
    }
    iso.phase = IsocyanatePhase.LOT_VERIFIED
    iso.isocyanateLot = mock_iso
    iso.completionPct = 20
    return {"isocyanate_state": iso.__dict__, "next_node": "exposure_baseline"}


def transition_to_exposure_baseline(state: dict[str, Any]) -> dict[str, Any]:
    """LOT_VERIFIED → EXPOSURE_BASELINE. Pre-dispense G6 worker exposure baseline."""
    iso = IsocyanateState(**state.get("isocyanate_state", {}))
    mock_baseline = {
        "sampler": "personal-passive-NIOSH-5521",
        "measurementMethod": "HPLC-fluorescence",
        "preDispense_ppb_MDI": 0.4,
        "g6Limit_ppb_MDI_8h_TWA": 5.0,
        "withinLimit": True,
    }
    iso.phase = IsocyanatePhase.EXPOSURE_BASELINE
    iso.exposureBaseline = mock_baseline
    iso.sbtOperatorDid = "did:web:etzhayyim.com:adherent:operator-iso-001"
    iso.completionPct = 40
    return {"isocyanate_state": iso.__dict__, "next_node": "dispense"}


def transition_to_dispensed(state: dict[str, Any]) -> dict[str, Any]:
    """EXPOSURE_BASELINE → DISPENSED. Closed-loop dispense."""
    iso = IsocyanateState(**state.get("isocyanate_state", {}))
    mock_dispense = {
        "targetKg": 42.0,
        "actualKg": 42.05,
        "tolerancePct": 0.12,
        "closedLoop": True,
        "dispenseTempC": 25,
        "mixHeadPressureBar": 120,
    }
    iso.phase = IsocyanatePhase.DISPENSED
    iso.dispenseTelemetry = mock_dispense
    iso.completionPct = 70
    return {"isocyanate_state": iso.__dict__, "next_node": "exposure_final"}


def transition_to_exposure_final(state: dict[str, Any]) -> dict[str, Any]:
    """DISPENSED → EXPOSURE_FINAL. Post-dispense G6 worker exposure."""
    iso = IsocyanateState(**state.get("isocyanate_state", {}))
    mock_final = {
        "postDispense_ppb_MDI": 1.2,
        "g6Limit_ppb_MDI_8h_TWA": 5.0,
        "withinLimit": True,
        "twa_8h_ppb_MDI": 0.8,
    }
    iso.phase = IsocyanatePhase.EXPOSURE_FINAL
    iso.exposureFinal = mock_final
    iso.completionPct = 90
    return {"isocyanate_state": iso.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    """EXPOSURE_FINAL → ATTESTATION_EMITTED."""
    iso = IsocyanateState(**state.get("isocyanate_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-naphtali-unit-2",
            "role": "closed_loop_dispense",
            "timestamp": "2026-05-26T08:30:00Z",
            "signature": "qR1sT2uV3wX4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-naphtali-unit-1",
            "role": "exposure_metrology",
            "timestamp": "2026-05-26T08:30:05Z",
            "signature": "yZ5aB6cD7eF8...",
        },
    ]
    iso.phase = IsocyanatePhase.ATTESTATION_EMITTED
    iso.robotSignatures = mock_sigs
    iso.completionPct = 100

    foam_section = {
        "$type": "com.etzhayyim.makura.foamBatchAttestation",
        "section": "isocyanate",
        "batchId": iso.batchId,
        "isocyanate": iso.isocyanateLot,
        "dispense": iso.dispenseTelemetry,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T08:30:10Z",
    }
    worker_record = {
        "$type": "com.etzhayyim.makura.workerExposureRecord",
        "batchId": iso.batchId,
        "operatorSbtDid": iso.sbtOperatorDid,
        "agent": "MDI",
        "baseline": iso.exposureBaseline,
        "final": iso.exposureFinal,
        "g6Compliant": True,
        "recordedAt": "2026-05-26T08:30:12Z",
    }
    return {
        "isocyanate_state": iso.__dict__,
        "foam_batch_isocyanate_attestation": foam_section,
        "worker_exposure_record": worker_record,
        "next_node": "end",
    }
