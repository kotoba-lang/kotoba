"""ELV emissions audit state machine — ADR-2605261215 cross-cutting (hodoki).

Continuous telemetry from L1b–L4: F-gas leakage, ASR mass + composition,
PGM yield. Per-vehicle compliance log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EmissionsAuditPhase(Enum):
    INIT = "init"
    FGAS_AGGREGATED = "fgas_aggregated"
    ASR_AGGREGATED = "asr_aggregated"
    PGM_YIELD_VERIFIED = "pgm_yield_verified"
    COMPLIANCE_FINALIZED = "compliance_finalized"


@dataclass
class EmissionsAuditState:
    phase: EmissionsAuditPhase
    vehicleId: str
    completionPct: int
    fgasAggregate: dict[str, Any] | None = None
    asrAggregate: dict[str, Any] | None = None
    pgmAggregate: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


def transition_to_fgas_aggregated(state: dict[str, Any]) -> dict[str, Any]:
    ea = EmissionsAuditState(**state.get("emissions_audit_state", {}))
    mock = {
        "totalRecoveredGrams": 491,
        "preChargeGramsLabel": 510,
        "recoveryRatePct": 96.3,
        "g6Compliant": True,
        "atmosphericVentingEventCount": 0,
    }
    ea.phase = EmissionsAuditPhase.FGAS_AGGREGATED
    ea.fgasAggregate = mock
    ea.completionPct = 30
    return {"emissions_audit_state": ea.__dict__, "next_node": "asr"}


def transition_to_asr_aggregated(state: dict[str, Any]) -> dict[str, Any]:
    ea = EmissionsAuditState(**state.get("emissions_audit_state", {}))
    mock = {
        "asrMassKg": 52,
        "inputVehicleCurbWeightKg": 1505,
        "asrPctOfInput": round(52 / 1505 * 100, 2),
        "g13AsrMaxPctLimit": 5.0,
        "g13Compliant": (52 / 1505 * 100) < 5.0,
        "composition": {
            "pvc": 18,
            "glass-fiber": 12,
            "paint-particles": 7,
            "fabric-dust": 6,
            "other": 9,
        },
        "destinationLandfillDid": "did:web:etzhayyim.com:asr-landfill-001",
    }
    ea.phase = EmissionsAuditPhase.ASR_AGGREGATED
    ea.asrAggregate = mock
    ea.completionPct = 60
    return {"emissions_audit_state": ea.__dict__, "next_node": "pgm"}


def transition_to_pgm_yield_verified(state: dict[str, Any]) -> dict[str, Any]:
    ea = EmissionsAuditState(**state.get("emissions_audit_state", {}))
    mock = {
        "ptYieldPct": 95.7,
        "pdYieldPct": 96.3,
        "rhYieldPct": 96.9,
        "g14MinYieldPct": 95.0,
        "g14Compliant": True,
    }
    ea.phase = EmissionsAuditPhase.PGM_YIELD_VERIFIED
    ea.pgmAggregate = mock
    ea.completionPct = 80
    return {"emissions_audit_state": ea.__dict__, "next_node": "compliance"}


def transition_to_compliance_finalized(state: dict[str, Any]) -> dict[str, Any]:
    ea = EmissionsAuditState(**state.get("emissions_audit_state", {}))
    mock = {
        "g6Compliant": (ea.fgasAggregate or {}).get("g6Compliant", False),
        "g13Compliant": (ea.asrAggregate or {}).get("g13Compliant", False),
        "g14Compliant": (ea.pgmAggregate or {}).get("g14Compliant", False),
        "overallCompliant": True,
        "ipfsAuditCid": "bafkreiaudit001...",
        "recordedAt": "2026-05-26T18:00:00Z",
    }
    ea.phase = EmissionsAuditPhase.COMPLIANCE_FINALIZED
    ea.compliance = mock
    ea.completionPct = 100
    record = {
        "vehicleId": ea.vehicleId,
        "fgas": ea.fgasAggregate,
        "asr": ea.asrAggregate,
        "pgm": ea.pgmAggregate,
        "compliance": ea.compliance,
        "recordedAt": "2026-05-26T18:00:00Z",
    }
    return {"emissions_audit_state": ea.__dict__, "emissions_audit_record": record, "next_node": "end"}
