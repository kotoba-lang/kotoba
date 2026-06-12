"""Packaging state machine — ADR-2605261115 L5c (makura).

Vacuum compression ≤40% original volume + carton + pallet + IPFS-pinned
take-back QR (G13). Quad (R2+) palletizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PackagingPhase(Enum):
    INIT = "init"
    VACUUM_COMPRESSED = "vacuum_compressed"
    CARTONED = "cartoned"
    PALLETIZED = "palletized"
    QR_PINNED = "qr_pinned"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class PackagingState:
    phase: PackagingPhase
    lotId: str
    pillowSerial: str
    completionPct: int
    vacuumCompression: dict[str, Any] | None = None
    carton: dict[str, Any] | None = None
    pallet: dict[str, Any] | None = None
    qrPin: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_vacuum_compressed(state: dict[str, Any]) -> dict[str, Any]:
    pk = PackagingState(**state.get("packaging_state", {}))
    mock_vacuum = {
        "originalVolumeL": 21.0,
        "compressedVolumeL": 7.5,
        "compressionRatio": 0.36,
        "specMaxRatio": 0.40,
        "withinSpec": True,
        "vacuumBagMaterial": "recycled-polyethylene",
        "vacuumBagBiocontentPct": 60,
    }
    pk.phase = PackagingPhase.VACUUM_COMPRESSED
    pk.vacuumCompression = mock_vacuum
    pk.completionPct = 30
    return {"packaging_state": pk.__dict__, "next_node": "carton"}


def transition_to_cartoned(state: dict[str, Any]) -> dict[str, Any]:
    pk = PackagingState(**state.get("packaging_state", {}))
    mock_carton = {
        "cartonMaterial": "FSC-recycled-corrugated",
        "cartonRecycledContentPct": 95,
        "pillowsPerCarton": 6,
        "cartonMassKg": 5.6,
    }
    pk.phase = PackagingPhase.CARTONED
    pk.carton = mock_carton
    pk.completionPct = 60
    return {"packaging_state": pk.__dict__, "next_node": "palletize"}


def transition_to_palletized(state: dict[str, Any]) -> dict[str, Any]:
    pk = PackagingState(**state.get("packaging_state", {}))
    mock_pallet = {
        "palletStandard": "EPAL-1",
        "palletMaterial": "wood",
        "cartonsPerLayer": 8,
        "layersPerPallet": 4,
        "totalCartons": 32,
        "totalPillows": 192,
        "totalMassKg": 195,
        "palletizingRobot": "kuni-umi-Quad-R2-deferred",
    }
    pk.phase = PackagingPhase.PALLETIZED
    pk.pallet = mock_pallet
    pk.completionPct = 80
    return {"packaging_state": pk.__dict__, "next_node": "qr_pin"}


def transition_to_qr_pinned(state: dict[str, Any]) -> dict[str, Any]:
    """G13 take-back QR pinned to IPFS + chain entry."""
    pk = PackagingState(**state.get("packaging_state", {}))
    mock_qr = {
        "pillowDid": f"did:web:etzhayyim.com:makura:pillow:{pk.pillowSerial}",
        "takeBackQrCid": "bafkreitakeback0001...",
        "takeBackChainEntryCid": "bafkreitakebackchain0001...",
        "g13ChainEntryConfirmed": True,
        "g13RecycledTargetPctByR3": 10.0,
    }
    pk.phase = PackagingPhase.QR_PINNED
    pk.qrPin = mock_qr
    pk.completionPct = 95
    return {"packaging_state": pk.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    pk = PackagingState(**state.get("packaging_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-levi-unit-2",
            "role": "vacuum_carton_witness",
            "timestamp": "2026-05-26T16:00:00Z",
            "signature": "iJ1kL2mN3oP4...",
        },
    ]
    pk.phase = PackagingPhase.ATTESTATION_EMITTED
    pk.robotSignatures = mock_sigs
    pk.completionPct = 100
    record = {
        "$type": "com.etzhayyim.makura.packagingRecord",
        "lotId": pk.lotId,
        "pillowSerial": pk.pillowSerial,
        "vacuumCompression": pk.vacuumCompression,
        "carton": pk.carton,
        "pallet": pk.pallet,
        "qrPin": pk.qrPin,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T16:00:10Z",
    }
    return {"packaging_state": pk.__dict__, "packaging_record": record, "next_node": "end"}
