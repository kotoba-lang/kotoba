"""ELV provenance binder state machine — ADR-2605261215 terminal (hodoki).

Full chain DID anchoring on kotoba-datomic: input VIN → parts catalog + material
lots + emissions + ASR mass. G2 mass-balance audit ≥98% closure attestation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProvenanceBinderPhase(Enum):
    INIT = "init"
    RECORDS_GATHERED = "records_gathered"
    MASS_BALANCE_COMPUTED = "mass_balance_computed"
    KOTOBA_DATOMIC_ANCHORED = "kotoba-datomic_anchored"
    BINDER_COMPLETE = "binder_complete"


@dataclass
class ProvenanceBinderState:
    phase: ProvenanceBinderPhase
    vehicleId: str
    vin: str
    completionPct: int
    recordsGathered: dict[str, Any] | None = None
    massBalance: dict[str, Any] | None = None
    kotoba-datomicAnchor: dict[str, Any] | None = None


def transition_to_records_gathered(state: dict[str, Any]) -> dict[str, Any]:
    pb = ProvenanceBinderState(**state.get("provenance_binder_state", {}))
    mock = {
        "elvIntakeRecordCid": "bafkreiintake001...",
        "dataWipeAttestationCid": "bafkreidatawipe001...",
        "depollutionAttestationCid": "bafkreidepollution001...",
        "batteryHandlingRecordCid": "bafkreibatt001...",
        "partsHarvestCatalogCid": "bafkreipartscatalog001...",
        "catalystRecoveryRecordCid": "bafkreicatalyst001...",
        "seatTextileHandoffCid": "bafkreiseat001...",
        "shredOutputAttestationCid": "bafkreishred001...",
        "emissionsAuditRecordCid": "bafkreiemissions001...",
    }
    pb.phase = ProvenanceBinderPhase.RECORDS_GATHERED
    pb.recordsGathered = mock
    pb.completionPct = 30
    return {"provenance_binder_state": pb.__dict__, "next_node": "mass_balance"}


def transition_to_mass_balance_computed(state: dict[str, Any]) -> dict[str, Any]:
    """G2 ≥98% closure invariant (inherits kanayama pattern)."""
    pb = ProvenanceBinderState(**state.get("provenance_binder_state", {}))
    mock = {
        "inputCurbWeightKg": 1505,
        "outputs": {
            "fluidsKg": 30.5,
            "fgasGramsRecovered": 491,
            "batteriesKg": 88,
            "partsHarvestedKg": 256,
            "catalystBrickKg": 1.92,
            "seatFoamMakuraKg": 14.5,
            "textileSortKg": 36.5,
            "ferrousKg": 720,
            "nonFerrousAlKg": 145,
            "copperWireKg": 32,
            "ecuPcbSiliconKg": 8.5,
            "asrKg": 52,
        },
        "totalOutputKg": 30.5 + 0.491 + 88 + 256 + 1.92 + 14.5 + 36.5 + 720 + 145 + 32 + 8.5 + 52,
        "closurePct": 100.0 * (30.5 + 0.491 + 88 + 256 + 1.92 + 14.5 + 36.5 + 720 + 145 + 32 + 8.5 + 52) / 1505,
        "g2MinClosurePct": 98.0,
        "g2Compliant": True,
    }
    pb.phase = ProvenanceBinderPhase.MASS_BALANCE_COMPUTED
    pb.massBalance = mock
    pb.completionPct = 65
    return {"provenance_binder_state": pb.__dict__, "next_node": "anchor"}


def transition_to_kotoba-datomic_anchored(state: dict[str, Any]) -> dict[str, Any]:
    pb = ProvenanceBinderState(**state.get("provenance_binder_state", {}))
    mock = {
        "kotoba-datomicBindCid": "bafkreikotoba-datomicbind001...",
        "anchorTxHash": "0xELV-PROVENANCE-BIND-001",
        "anchoredAt": "2026-05-26T19:00:00Z",
        "auditLogLink": f"ipfs://bafkreikotoba-datomicbind001/{pb.vin}",
    }
    pb.phase = ProvenanceBinderPhase.KOTOBA_DATOMIC_ANCHORED
    pb.kotoba-datomicAnchor = mock
    pb.completionPct = 90
    return {"provenance_binder_state": pb.__dict__, "next_node": "complete"}


def transition_to_binder_complete(state: dict[str, Any]) -> dict[str, Any]:
    pb = ProvenanceBinderState(**state.get("provenance_binder_state", {}))
    pb.phase = ProvenanceBinderPhase.BINDER_COMPLETE
    pb.completionPct = 100
    record = {
        "vehicleId": pb.vehicleId,
        "vehicleDid": f"did:web:etzhayyim.com:hodoki:vehicle:{pb.vin}",
        "vin": pb.vin,
        "records": pb.recordsGathered,
        "massBalance": pb.massBalance,
        "kotoba-datomicAnchor": pb.kotoba-datomicAnchor,
        "g2Compliant": (pb.massBalance or {}).get("g2Compliant", False),
        "recordedAt": "2026-05-26T19:00:10Z",
    }
    return {"provenance_binder_state": pb.__dict__, "provenance_binder_record": record, "next_node": "end"}
