"""ELV parts harvest state machine — ADR-2605261215 L3a (hodoki).

G12 RIGHT-TO-REPAIR INVARIANT — every harvested part has IPFS-pinned
catalog entry with VIN provenance + part DID + condition grade + bilingual
description; no proprietary lock-in; no anti-disassembly DRM tolerated.

CONSTITUTIONAL FIRST: §2(e) anti-gatekeeping operationalized at vehicle scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PartsHarvestPhase(Enum):
    INIT = "init"
    PARTS_IDENTIFIED = "parts_identified"
    CONDITION_GRADED = "condition_graded"
    PART_DIDS_ISSUED = "part_dids_issued"
    CATALOG_PUBLISHED = "catalog_published"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class PartsHarvestState:
    phase: PartsHarvestPhase
    vehicleId: str
    vin: str
    completionPct: int
    partsList: list[dict[str, Any]] = field(default_factory=list)
    catalogPublication: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def _make_part(idx: int, vin: str, name_ja: str, name_en: str, mass_kg: float, grade: str) -> dict[str, Any]:
    return {
        "partId": f"{vin}-PART-{idx:04d}",
        "partDid": f"did:web:etzhayyim.com:hodoki:part:{vin}:{idx:04d}",
        "vinProvenance": vin,
        "descriptionJa": name_ja,
        "descriptionEn": name_en,
        "massKg": mass_kg,
        "conditionGrade": grade,
    }


def transition_to_parts_identified(state: dict[str, Any]) -> dict[str, Any]:
    ph = PartsHarvestState(**state.get("parts_harvest_state", {}))
    vin = ph.vin or "WAUZZZ8V3MA000001"
    mock_parts = [
        _make_part(1, vin, "エンジン", "engine", 145.0, "B"),
        _make_part(2, vin, "トランスミッション", "transmission", 85.0, "B"),
        _make_part(3, vin, "ヘッドライト 左", "headlight-left", 4.2, "A"),
        _make_part(4, vin, "ヘッドライト 右", "headlight-right", 4.2, "A"),
        _make_part(5, vin, "ドア 前左", "door-front-left", 22.0, "A"),
        _make_part(6, vin, "ドア 前右", "door-front-right", 22.0, "A"),
        _make_part(7, vin, "アルテルネーター", "alternator", 6.5, "A"),
        _make_part(8, vin, "スターターモーター", "starter-motor", 4.8, "B"),
        _make_part(9, vin, "ラジエーター", "radiator", 8.5, "A"),
        _make_part(10, vin, "ECU メイン", "ecu-main-body", 0.6, "A-wiped"),
        _make_part(11, vin, "シート 前左 (G13→makura)", "seat-front-left (G13→makura)", 18.0, "B"),
        _make_part(12, vin, "シート 前右 (G13→makura)", "seat-front-right (G13→makura)", 18.0, "B"),
        _make_part(13, vin, "シート リア (G13→makura)", "seat-rear (G13→makura)", 32.0, "B"),
    ]
    ph.phase = PartsHarvestPhase.PARTS_IDENTIFIED
    ph.partsList = mock_parts
    ph.completionPct = 30
    return {"parts_harvest_state": ph.__dict__, "next_node": "grade"}


def transition_to_condition_graded(state: dict[str, Any]) -> dict[str, Any]:
    """Already graded inline during identification. Mark phase."""
    ph = PartsHarvestState(**state.get("parts_harvest_state", {}))
    ph.phase = PartsHarvestPhase.CONDITION_GRADED
    ph.completionPct = 55
    return {"parts_harvest_state": ph.__dict__, "next_node": "issue_dids"}


def transition_to_part_dids_issued(state: dict[str, Any]) -> dict[str, Any]:
    """Already issued inline during identification. Mark phase."""
    ph = PartsHarvestState(**state.get("parts_harvest_state", {}))
    ph.phase = PartsHarvestPhase.PART_DIDS_ISSUED
    ph.completionPct = 75
    return {"parts_harvest_state": ph.__dict__, "next_node": "publish"}


def transition_to_catalog_published(state: dict[str, Any]) -> dict[str, Any]:
    """G12 — IPFS-pinned public bilingual parts catalog."""
    ph = PartsHarvestState(**state.get("parts_harvest_state", {}))
    mock_pub = {
        "catalogCid": "bafkreipartscatalog-WAUZZZ8V3MA000001...",
        "languagesPresent": ["ja", "en"],
        "g4BilingualMet": True,
        "g12RightToRepairInvariant": True,
        "g12PublicDiscovery": True,
        "g12NoProprietaryLockIn": True,
        "g12NoDrmCircumvention": True,
        "partCount": len(ph.partsList),
        "totalReusableMassKg": sum(p.get("massKg", 0.0) for p in ph.partsList),
    }
    ph.phase = PartsHarvestPhase.CATALOG_PUBLISHED
    ph.catalogPublication = mock_pub
    ph.completionPct = 92
    return {"parts_harvest_state": ph.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    ph = PartsHarvestState(**state.get("parts_harvest_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-simeon-unit-1",
            "role": "parts_extraction",
            "timestamp": "2026-05-26T14:00:00Z",
            "signature": "yY1zZ2aB3cC4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-simeon-unit-1",
            "role": "condition_grading",
            "timestamp": "2026-05-26T14:00:05Z",
            "signature": "dD5eE6fF7gG8...",
        },
    ]
    ph.phase = PartsHarvestPhase.ATTESTATION_EMITTED
    ph.robotSignatures = mock_sigs
    ph.completionPct = 100
    record = {
        "$type": "com.etzhayyim.hodoki.partsHarvestCatalog",
        "vehicleId": ph.vehicleId,
        "vinProvenance": ph.vin,
        "parts": ph.partsList,
        "publication": ph.catalogPublication,
        "g12Compliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T14:00:10Z",
    }
    return {"parts_harvest_state": ph.__dict__, "parts_harvest_catalog": record, "next_node": "end"}
