"""ELV seat + textile recovery state machine — ADR-2605261215 L3c (hodoki).

G13 cross-actor invariant closure — seat foam routed to makura
(closes makura G13 take-back ≥10% recycled crumb by R3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SeatTextilePhase(Enum):
    INIT = "init"
    SEATS_REMOVED = "seats_removed"
    FOAM_SEPARATED = "foam_separated"
    TEXTILE_SORTED = "textile_sorted"
    MAKURA_HANDOFF = "makura_handoff"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class SeatTextileState:
    phase: SeatTextilePhase
    vehicleId: str
    completionPct: int
    seatsRemoved: dict[str, Any] | None = None
    foamSeparation: dict[str, Any] | None = None
    textileSort: dict[str, Any] | None = None
    makuraHandoff: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_seats_removed(state: dict[str, Any]) -> dict[str, Any]:
    st = SeatTextileState(**state.get("seat_textile_state", {}))
    mock_seats = {
        "seatPositions": ["front-left", "front-right", "rear"],
        "totalSeatMassKg": 68.0,
        "fastenerType": "M10-bolt",
        "tokikeRobotUsed": True,
    }
    st.phase = SeatTextilePhase.SEATS_REMOVED
    st.seatsRemoved = mock_seats
    st.completionPct = 25
    return {"seat_textile_state": st.__dict__, "next_node": "foam"}


def transition_to_foam_separated(state: dict[str, Any]) -> dict[str, Any]:
    st = SeatTextileState(**state.get("seat_textile_state", {}))
    mock_foam = {
        "foamMassKg": 14.5,
        "foamTypeIdentified": "polyurethane-flexible-slab",
        "foamDensityKgPerM3Approx": 45,
        "fragranceContaminationDetected": False,
        "frChemistryDetected": "none",
        "makuraSuitable": True,
    }
    st.phase = SeatTextilePhase.FOAM_SEPARATED
    st.foamSeparation = mock_foam
    st.completionPct = 50
    return {"seat_textile_state": st.__dict__, "next_node": "textile"}


def transition_to_textile_sorted(state: dict[str, Any]) -> dict[str, Any]:
    st = SeatTextileState(**state.get("seat_textile_state", {}))
    mock_textile = {
        "fabricMassKg": 8.5,
        "leatherMassKg": 22.0,
        "syntheticBlendMassKg": 6.0,
        "totalNonFoamKg": 36.5,
        "languagesPresent": ["ja", "en"],
        "g4BilingualSorting": True,
    }
    st.phase = SeatTextilePhase.TEXTILE_SORTED
    st.textileSort = mock_textile
    st.completionPct = 70
    return {"seat_textile_state": st.__dict__, "next_node": "makura_handoff"}


def transition_to_makura_handoff(state: dict[str, Any]) -> dict[str, Any]:
    """G13 cross-actor invariant closure — foam → makura."""
    st = SeatTextileState(**state.get("seat_textile_state", {}))
    foam_mass = st.foamSeparation.get("foamMassKg", 0.0) if st.foamSeparation else 0.0
    mock_handoff = {
        "destinationActor": "makura",
        "destinationDid": "did:web:etzhayyim.com:makura",
        "foamMassHandedOffKg": foam_mass,
        "feedTarget": "pillow_foam_shredding (recycled-blend input)",
        "g13MakuraInvariantClosure": True,
        "shippedAt": "2026-05-26T16:00:00Z",
        "custodyChainCid": "bafkreifoamhandoff001...",
    }
    st.phase = SeatTextilePhase.MAKURA_HANDOFF
    st.makuraHandoff = mock_handoff
    st.completionPct = 92
    return {"seat_textile_state": st.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    st = SeatTextileState(**state.get("seat_textile_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:tokike-dan-unit-1",
            "role": "fastener_release_witness",
            "timestamp": "2026-05-26T16:15:00Z",
            "signature": "qQ1rR2sS3tT4...",
        },
    ]
    st.phase = SeatTextilePhase.ATTESTATION_EMITTED
    st.robotSignatures = mock_sigs
    st.completionPct = 100
    record = {
        "vehicleId": st.vehicleId,
        "seatsRemoved": st.seatsRemoved,
        "foamSeparation": st.foamSeparation,
        "textileSort": st.textileSort,
        "makuraHandoff": st.makuraHandoff,
        "g13Compliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T16:15:10Z",
    }
    return {"seat_textile_state": st.__dict__, "seat_textile_handoff_record": record, "next_node": "end"}
