"""Foam blowing state machine — ADR-2605261115 L2 (makura).

Slabstock one-shot foam blowing. Density 40-60 kg/m³, cell structure 30-80 ppi,
VOC ≤ CertiPUR-US / OEKO-TEX Standard 100 equivalent (G7), batch IPFS-pinned
photo + density (G2). No PBDE / TDCPP / TCEP / Sb₂O₃ FR chemistry (G8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FoamBlowingPhase(Enum):
    INIT = "init"
    STREAMS_VERIFIED = "streams_verified"
    BLOWN = "blown"
    CURED = "cured"
    QC_PASSED = "qc_passed"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class FoamBlowingState:
    phase: FoamBlowingPhase
    batchId: str
    completionPct: int
    streams: dict[str, Any] | None = None
    blownTelemetry: dict[str, Any] | None = None
    cureRecord: dict[str, Any] | None = None
    qc: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_streams_verified(state: dict[str, Any]) -> dict[str, Any]:
    fb = FoamBlowingState(**state.get("foam_blowing_state", {}))
    mock_streams = {
        "polyolStreamKgPerMin": 18.5,
        "isocyanateStreamKgPerMin": 14.2,
        "indexNCO_OH": 105,
        "blowingAgentWaterPph": 4.2,
        "frChemistry": "none",
        "frBaselineFRFreeDeclared": True,
    }
    fb.phase = FoamBlowingPhase.STREAMS_VERIFIED
    fb.streams = mock_streams
    fb.completionPct = 20
    return {"foam_blowing_state": fb.__dict__, "next_node": "blown"}


def transition_to_blown(state: dict[str, Any]) -> dict[str, Any]:
    fb = FoamBlowingState(**state.get("foam_blowing_state", {}))
    mock_blown = {
        "process": "slabstock-one-shot",
        "conveyorSpeedMPerMin": 4.5,
        "slabHeightMm": 1200,
        "slabWidthMm": 2100,
        "totalKg": 1480,
        "creamTimeS": 7,
        "riseTimeS": 65,
        "tackFreeTimeS": 120,
    }
    fb.phase = FoamBlowingPhase.BLOWN
    fb.blownTelemetry = mock_blown
    fb.completionPct = 50
    return {"foam_blowing_state": fb.__dict__, "next_node": "cured"}


def transition_to_cured(state: dict[str, Any]) -> dict[str, Any]:
    fb = FoamBlowingState(**state.get("foam_blowing_state", {}))
    mock_cure = {
        "cureTempC": 21,
        "cureHumidityPct": 50,
        "cureDurationHr": 48,
        "cureFacilityVentilation": "negative-pressure-12-ach",
    }
    fb.phase = FoamBlowingPhase.CURED
    fb.cureRecord = mock_cure
    fb.completionPct = 75
    return {"foam_blowing_state": fb.__dict__, "next_node": "qc"}


def transition_to_qc_passed(state: dict[str, Any]) -> dict[str, Any]:
    fb = FoamBlowingState(**state.get("foam_blowing_state", {}))
    mock_qc = {
        "densityKgPerM3": 47,
        "densitySpecMin": 40,
        "densitySpecMax": 60,
        "cellStructurePpi": 50,
        "cellStructureSpecMin": 30,
        "cellStructureSpecMax": 80,
        "ildN_25Pct": 130,
        "vocFormaldehydePpm": 0.02,
        "vocFormaldehydeLimitPpm": 0.05,
        "vocTotalMgPerM3": 0.30,
        "vocTotalLimitMgPerM3": 0.50,
        "ipfsPhotoCid": "bafkreifoamphoto0142...",
        "accept": True,
    }
    fb.phase = FoamBlowingPhase.QC_PASSED
    fb.qc = mock_qc
    fb.completionPct = 95
    return {"foam_blowing_state": fb.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    fb = FoamBlowingState(**state.get("foam_blowing_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:awa-zebulun-unit-1",
            "role": "blow_line_witness",
            "timestamp": "2026-05-26T10:00:00Z",
            "signature": "gH1iJ2kL3mN4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-zebulun-unit-1",
            "role": "density_voc_metrology",
            "timestamp": "2026-05-26T10:00:05Z",
            "signature": "oP5qR6sT7uV8...",
        },
    ]
    fb.phase = FoamBlowingPhase.ATTESTATION_EMITTED
    fb.robotSignatures = mock_sigs
    fb.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.foamBatchAttestation",
        "section": "final",
        "batchId": fb.batchId,
        "streams": fb.streams,
        "blown": fb.blownTelemetry,
        "cure": fb.cureRecord,
        "qc": fb.qc,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T10:00:10Z",
    }
    return {"foam_blowing_state": fb.__dict__, "foam_batch_attestation": record, "next_node": "end"}
