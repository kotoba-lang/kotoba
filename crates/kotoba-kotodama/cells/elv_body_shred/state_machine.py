"""ELV body shred state machine — ADR-2605261215 L4 (hodoki).

Stripped hulk shredder + magnetic + eddy-current + density sort.
G13 ≥95% material recovery; ASR <5% mass to landfill; cross-actor handoff to
kanayama (ferrous + Al + Cu) + silicon Wave 2 (electronics PCB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BodyShredPhase(Enum):
    INIT = "init"
    HULK_LOADED = "hulk_loaded"
    SHREDDED = "shredded"
    SORTED = "sorted"
    KANAYAMA_HANDOFF = "kanayama_handoff"
    SILICON_HANDOFF = "silicon_handoff"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class BodyShredState:
    phase: BodyShredPhase
    vehicleId: str
    completionPct: int
    hulkLoad: dict[str, Any] | None = None
    shredTelemetry: dict[str, Any] | None = None
    sortStreams: dict[str, Any] | None = None
    kanayamaHandoff: dict[str, Any] | None = None
    siliconHandoff: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_hulk_loaded(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    mock_load = {
        "preShredMassKg": 1100,
        "hulkConditionAfterHarvest": "stripped",
        "g8DataWipeVerified": True,
        "g6FgasVerifiedCaptured": True,
        "g7BatteryRemoved": True,
        "asbestosCheck": "clear",
    }
    bs.phase = BodyShredPhase.HULK_LOADED
    bs.hulkLoad = mock_load
    bs.completionPct = 15
    return {"body_shred_state": bs.__dict__, "next_node": "shred"}


def transition_to_shredded(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    mock_shred = {
        "shredderType": "horizontal-hammer-mill",
        "outputParticleMmRange": [30, 150],
        "shredDurationS": 240,
        "ipfsPhotoCid": "bafkreishred001...",
    }
    bs.phase = BodyShredPhase.SHREDDED
    bs.shredTelemetry = mock_shred
    bs.completionPct = 40
    return {"body_shred_state": bs.__dict__, "next_node": "sort"}


def transition_to_sorted(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    mock_sort = {
        "ferrousMassKg": 720,
        "nonFerrousAlMassKg": 145,
        "copperWireMassKg": 32,
        "electronicsPcbMassKg": 8.5,
        "asrMassKg": 52,
        "totalOutMassKg": 957.5,
        "g13RecoveryRatePct": 100.0 * (957.5 - 52) / 957.5,
        "g13AsrPctOfInput": 52 / 1100 * 100,
        "g13AsrMaxPctLimit": 5.0,
        "g13Compliant": (52 / 1100 * 100) < 5.0,
    }
    bs.phase = BodyShredPhase.SORTED
    bs.sortStreams = mock_sort
    bs.completionPct = 65
    return {"body_shred_state": bs.__dict__, "next_node": "kanayama"}


def transition_to_kanayama_handoff(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    sort = bs.sortStreams or {}
    mock_handoff = {
        "destinationActor": "kanayama",
        "destinationDid": "did:web:etzhayyim.com:kanayama",
        "streams": {
            "ferrous": {"massKg": sort.get("ferrousMassKg", 0), "destinationCell": "kanayama Wave 2 (steel R3)"},
            "nonFerrousAl": {"massKg": sort.get("nonFerrousAlMassKg", 0), "destinationCell": "kanayama Wave 1 (Al melt)"},
            "copperWire": {"massKg": sort.get("copperWireMassKg", 0), "destinationCell": "kanayama Wave 3 (Cu secondary smelter)"},
        },
        "shippedAt": "2026-05-26T17:00:00Z",
        "custodyChainCid": "bafkreikanayamahandoff001...",
    }
    bs.phase = BodyShredPhase.KANAYAMA_HANDOFF
    bs.kanayamaHandoff = mock_handoff
    bs.completionPct = 80
    return {"body_shred_state": bs.__dict__, "next_node": "silicon"}


def transition_to_silicon_handoff(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    sort = bs.sortStreams or {}
    mock_handoff = {
        "destinationActor": "silicon-wave2",
        "destinationDid": "did:web:etzhayyim.com:silicon",
        "pcbMassKg": sort.get("electronicsPcbMassKg", 0),
        "feedTarget": "silicon Wave 2 ECU PCB rare-metal recovery (Ag/Au/Pd/Cu)",
        "shippedAt": "2026-05-26T17:05:00Z",
        "wave2GatedNote": "Wave 2 ADR ratification pending; holding bay storage in R0–R1",
    }
    bs.phase = BodyShredPhase.SILICON_HANDOFF
    bs.siliconHandoff = mock_handoff
    bs.completionPct = 92
    return {"body_shred_state": bs.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    bs = BodyShredState(**state.get("body_shred_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:awa-zebulun-unit-2",
            "role": "shredder_witness",
            "timestamp": "2026-05-26T17:10:00Z",
            "signature": "uU1vV2wW3xX4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-zebulun-unit-1",
            "role": "sort_metrology",
            "timestamp": "2026-05-26T17:10:05Z",
            "signature": "yY5zZ6aA7bB8...",
        },
    ]
    bs.phase = BodyShredPhase.ATTESTATION_EMITTED
    bs.robotSignatures = mock_sigs
    bs.completionPct = 100
    record = {
        "$type": "com.etzhayyim.hodoki.shredOutputAttestation",
        "vehicleId": bs.vehicleId,
        "hulkLoad": bs.hulkLoad,
        "shred": bs.shredTelemetry,
        "sortStreams": bs.sortStreams,
        "kanayamaHandoff": bs.kanayamaHandoff,
        "siliconHandoff": bs.siliconHandoff,
        "g13Compliant": (bs.sortStreams or {}).get("g13Compliant", False),
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T17:10:10Z",
    }
    return {"body_shred_state": bs.__dict__, "shred_output_attestation": record, "next_node": "end"}
