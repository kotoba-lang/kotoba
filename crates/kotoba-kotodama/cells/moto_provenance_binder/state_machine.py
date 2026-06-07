"""Provenance binder state machine — ADR-2605261330 terminal (futawa).

KotobaDatomic anchoring (input material lots → output VIN + parts catalog
+ tests + hodoki pre-registration). G2 mass-balance ≥98% closure.
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
        "frameAttestationCid": "bafkreiframe001...",
        "engineAttestationCid": "bafkreiengine001...",
        "drivetrainRecordCid": "bafkreidrive001...",
        "electricalAttestationCid": "bafkreiharness001...",
        "suspensionBrakeRecordCid": "bafkreisb001...",
        "paintAttestationCid": "bafkreipaint001...",
        "vehicleLotAttestationCid": "bafkreilot001...",
        "partsCatalogCid": "bafkreipartscatalog001...",
        "testRecordCid": "bafkreitest001...",
        "hodokiPreRegCustodyCid": "bafkreihodokiprereg001...",
    }
    pb.phase = ProvenanceBinderPhase.RECORDS_GATHERED
    pb.recordsGathered = mock
    pb.completionPct = 30
    return {"provenance_binder_state": pb.__dict__, "next_node": "mass_balance"}


def transition_to_mass_balance_computed(state: dict[str, Any]) -> dict[str, Any]:
    pb = ProvenanceBinderState(**state.get("provenance_binder_state", {}))
    mock = {
        "inputMaterialMassKg": 178.5,
        "outputs": {
            "vehicleCurbWeightKg": 168.0,
            "scrapMassKg": 7.5,
            "vocEmissionsKg": 0.15,
            "paintOverspraysKg": 0.45,
            "otherKg": 1.2,
        },
        "totalOutputKg": 168.0 + 7.5 + 0.15 + 0.45 + 1.2,
        "closurePct": 100.0 * (168.0 + 7.5 + 0.15 + 0.45 + 1.2) / 178.5,
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
        "kotoba-datomicBindCid": "bafkreikotoba-datomicbind-futawa-001...",
        "anchorTxHash": "0xFUTAWA-PROVENANCE-BIND-001",
        "anchoredAt": "2026-05-27T18:00:00Z",
        "auditLogLink": f"ipfs://bafkreikotoba-datomicbind-futawa-001/{pb.vin}",
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
        "vin": pb.vin,
        "vehicleDid": f"did:web:etzhayyim.com:futawa:vehicle:{pb.vin}",
        "records": pb.recordsGathered,
        "massBalance": pb.massBalance,
        "kotoba-datomicAnchor": pb.kotoba-datomicAnchor,
        "g2Compliant": (pb.massBalance or {}).get("g2Compliant", False),
        "recordedAt": "2026-05-27T18:00:10Z",
    }
    return {"provenance_binder_state": pb.__dict__, "provenance_binder_record": record, "next_node": "end"}
