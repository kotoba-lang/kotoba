"""Final assembly state machine — ADR-2605261330 L5a (futawa).

CONSTITUTIONAL FIRSTS:
- G12 RIGHT-TO-REPAIR FORWARD-PUBLISHING: every new vehicle ships with
  IPFS-pinned full parts catalog + CAD + firmware source + service manual
  + open diagnostic protocol at manufacture time.
- G13 cross-actor: VIN pre-registered with hodoki at production
  (build-side closure of hodoki take-back chain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FinalAssemblyPhase(Enum):
    INIT = "init"
    SUBASSEMBLIES_MATED = "subassemblies_mated"
    FLUIDS_FILLED = "fluids_filled"
    VIN_TAGGED = "vin_tagged"
    PARTS_CATALOG_PUBLISHED = "parts_catalog_published"
    HODOKI_PRE_REGISTERED = "hodoki_pre_registered"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class FinalAssemblyState:
    phase: FinalAssemblyPhase
    vehicleId: str
    vin: str
    completionPct: int
    subassembliesMated: dict[str, Any] | None = None
    fluidsFill: dict[str, Any] | None = None
    vinTag: dict[str, Any] | None = None
    partsCatalog: dict[str, Any] | None = None
    hodokiPreReg: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_subassemblies_mated(state: dict[str, Any]) -> dict[str, Any]:
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock = {
        "frameCid": "bafkreiframe001...",
        "engineCid": "bafkreiengine001...",
        "drivetrainCid": "bafkreidrive001...",
        "harnessCid": "bafkreiharness001...",
        "suspensionBrakeCid": "bafkreisb001...",
        "bodyPaintCid": "bafkreipaint001...",
        "boltCount": 187,
        "torqueWitnessCount": 2,
    }
    fa.phase = FinalAssemblyPhase.SUBASSEMBLIES_MATED
    fa.subassembliesMated = mock
    fa.completionPct = 25
    return {"final_assembly_state": fa.__dict__, "next_node": "fluids"}


def transition_to_fluids_filled(state: dict[str, Any]) -> dict[str, Any]:
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock = {
        "engineOilLiters": 1.4,
        "engineOilType": "10W-40-JASO-MA2",
        "coolantLiters": 1.2,
        "brakeFluidLiters": 0.25,
        "fuelTankCapacityL": 12.0,
        "fuelInitialFillL": 1.0,
    }
    fa.phase = FinalAssemblyPhase.FLUIDS_FILLED
    fa.fluidsFill = mock
    fa.completionPct = 45
    return {"final_assembly_state": fa.__dict__, "next_node": "vin"}


def transition_to_vin_tagged(state: dict[str, Any]) -> dict[str, Any]:
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock = {
        "vin": fa.vin,
        "vehicleDid": f"did:web:etzhayyim.com:futawa:vehicle:{fa.vin}",
        "frameStampLocation": "headstock",
        "engineStampLocation": "right-crankcase",
        "tagLanguages": ["ja", "en"],
        "g4BilingualMet": True,
    }
    fa.phase = FinalAssemblyPhase.VIN_TAGGED
    fa.vinTag = mock
    fa.completionPct = 60
    return {"final_assembly_state": fa.__dict__, "next_node": "catalog"}


def transition_to_parts_catalog_published(state: dict[str, Any]) -> dict[str, Any]:
    """G12 CONSTITUTIONAL FIRST: forward-publishing at manufacture time."""
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock = {
        "catalogCid": f"bafkreipartscatalog-{fa.vin}...",
        "cadSourceCid": "bafkreicadsrc-futawa-250-r0...",
        "firmwareSourceCid": "bafkreifwsrc-futawa-ecu-r0...",
        "serviceManualCid": "bafkreismanual-ja-en-r0...",
        "openDiagnosticProtocolCid": "bafkreiobd-open-r0...",
        "g12RightToRepairForwardPublishing": True,
        "g12NoProprietaryLockIn": True,
        "g12NoAntiDrm": True,
        "g12NoWarrantyVoidOnUserRepair": True,
        "g14PartDiscontinuationProhibitedYears": 30,
        "g14FirmwareUpdateCommitmentYears": 30,
        "languagesPresent": ["ja", "en"],
    }
    fa.phase = FinalAssemblyPhase.PARTS_CATALOG_PUBLISHED
    fa.partsCatalog = mock
    fa.completionPct = 78
    return {"final_assembly_state": fa.__dict__, "next_node": "hodoki"}


def transition_to_hodoki_pre_registered(state: dict[str, Any]) -> dict[str, Any]:
    """G13 build-side cross-actor invariant: pre-register VIN with hodoki."""
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock = {
        "hodokiActorDid": "did:web:etzhayyim.com:hodoki",
        "vin": fa.vin,
        "vehicleDid": f"did:web:etzhayyim.com:futawa:vehicle:{fa.vin}",
        "preRegistrationCustodyChainCid": "bafkreihodokiprereg001...",
        "expectedEolPathway": "hodoki-elv-intake-with-data-wipe-and-parts-harvest",
        "g13CircularLoopConfirmed": True,
        "futawaPartsCatalogCid": fa.partsCatalog.get("catalogCid") if fa.partsCatalog else "",
        "preRegisteredAt": "2026-05-27T15:00:00Z",
    }
    fa.phase = FinalAssemblyPhase.HODOKI_PRE_REGISTERED
    fa.hodokiPreReg = mock
    fa.completionPct = 92
    return {"final_assembly_state": fa.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    fa = FinalAssemblyState(**state.get("final_assembly_state", {}))
    mock_sigs = [
        {"robotDid": "did:web:etzhayyim.com:tokike-dan-unit-1", "role": "bolt_down_torque_witness", "timestamp": "2026-05-27T15:30:00Z", "signature": "sS1tT2uU3vV4..."},
        {"robotDid": "did:web:etzhayyim.com:mimi-dan-unit-2", "role": "vin_metrology_witness", "timestamp": "2026-05-27T15:30:05Z", "signature": "wW5xX6yY7zZ8..."},
    ]
    fa.phase = FinalAssemblyPhase.ATTESTATION_EMITTED
    fa.robotSignatures = mock_sigs
    fa.completionPct = 100
    record = {
        "$type": "com.etzhayyim.futawa.vehicleLotAttestation",
        "vehicleId": fa.vehicleId,
        "vin": fa.vin,
        "vehicleDid": f"did:web:etzhayyim.com:futawa:vehicle:{fa.vin}",
        "subassembliesMated": fa.subassembliesMated,
        "fluidsFill": fa.fluidsFill,
        "vinTag": fa.vinTag,
        "partsCatalog": fa.partsCatalog,
        "hodokiPreReg": fa.hodokiPreReg,
        "g12Compliant": True,
        "g13PreRegisteredWithHodoki": True,
        "g4BilingualMet": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-27T15:30:10Z",
    }
    parts_catalog_record = {
        "$type": "com.etzhayyim.futawa.partsCatalog",
        "vehicleId": fa.vehicleId,
        "vin": fa.vin,
        "vehicleDid": f"did:web:etzhayyim.com:futawa:vehicle:{fa.vin}",
        "catalog": fa.partsCatalog,
        "publishedAt": "2026-05-27T15:30:10Z",
        "g12ForwardPublishing": True,
    }
    return {
        "final_assembly_state": fa.__dict__,
        "vehicle_lot_attestation": record,
        "parts_catalog_record": parts_catalog_record,
        "next_node": "end",
    }
