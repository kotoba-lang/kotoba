"""Mold-Allergy handlers for BPMN + Zeebe."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from decimal import Decimal
from typing import Any
from uuid import uuid4

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:mold-allergy.etzhayyim.com"

IUIS_FUNGAL_ALLERGENS: list[dict[str, Any]] = [
    {"species": "Alternaria alternata", "allergen": "Alt a 1", "uniprot": "P79085", "mw_kda": 16.4, "function": "major allergen, unique fold"},
    {"species": "Alternaria alternata", "allergen": "Alt a 6", "uniprot": "Q9HDT3", "mw_kda": 11.0, "function": "enolase"},
    {"species": "Cladosporium herbarum", "allergen": "Cla h 8", "uniprot": "P40918", "mw_kda": 28.0, "function": "mannitol dehydrogenase"},
    {"species": "Cladosporium herbarum", "allergen": "Cla h 9", "uniprot": "P42039", "mw_kda": 39.0, "function": "vacuolar serine protease"},
    {"species": "Aspergillus fumigatus", "allergen": "Asp f 1", "uniprot": "P04389", "mw_kda": 18.0, "function": "mitogillin, ribotoxin"},
    {"species": "Aspergillus fumigatus", "allergen": "Asp f 2", "uniprot": "P79017", "mw_kda": 37.0, "function": "fibrinogen binding"},
    {"species": "Aspergillus fumigatus", "allergen": "Asp f 3", "uniprot": "O43099", "mw_kda": 19.0, "function": "peroxisomal protein"},
    {"species": "Penicillium chrysogenum", "allergen": "Pen ch 13", "uniprot": "Q9UVF8", "mw_kda": 34.0, "function": "alkaline serine protease"},
    {"species": "Penicillium chrysogenum", "allergen": "Pen ch 18", "uniprot": "Q9P8U2", "mw_kda": 32.0, "function": "vacuolar serine protease"},
    {"species": "Malassezia sympodialis", "allergen": "Mala s 1", "uniprot": "Q9UW20", "mw_kda": 35.3, "function": "beta-glucosidase homolog"},
    {"species": "Malassezia sympodialis", "allergen": "Mala s 11", "uniprot": "Q8NIY1", "mw_kda": 22.7, "function": "Mn superoxide dismutase"},
    {"species": "Trichophyton rubrum", "allergen": "Tri r 2", "uniprot": "", "mw_kda": 30.0, "function": "subtilisin-like serine protease"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any, fallback: int = 50) -> int:
    try:
        parsed = int(value if value is not None else fallback)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, min(parsed, 100))


def _offset(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value



def seed_allergen_catalog(**_: Any) -> dict[str, Any]:
    written = 0
    created = now_iso()
    for item in IUIS_FUNGAL_ALLERGENS:
        vertex_id = f"mold-allergy:allergen:{item['allergen'].lower().replace(' ', '-')}"
        row_dict = {
            "vertex_id": vertex_id,
            "owner_did": OWNER_DID,
            "species": item["species"],
            "allergen": item["allergen"],
            "uniprot": item["uniprot"],
            "mw_kda": item["mw_kda"],
            "biochemical_function": item["function"],
            "source": "WHO-IUIS allergen nomenclature",
            "created_at": created,
            "actor_id": "m0ldalg1",
        }
        get_kotoba_client().insert_row("vertex_mold_allergen", row_dict)
        written += 1
    return {"written": written, "total": len(IUIS_FUNGAL_ALLERGENS)}


def record_air_sampling(**kwargs: Any) -> dict[str, Any]:
    site = str(kwargs.get("site") or "")
    if not site:
        return {"error": "site required"}
    session_id = _id("air")
    row_dict = {
        "vertex_id": f"mold-allergy:air:{session_id}",
        "owner_did": OWNER_DID,
        "session_id": session_id,
        "site": site,
        "sampled_at": str(kwargs.get("sampledAt") or now_iso()),
        "method": str(kwargs.get("method") or "Burkard"),
        "alternaria_count_per_m3": _num(kwargs.get("alternariaCountPerM3")),
        "cladosporium_count_per_m3": _num(kwargs.get("cladosporiumCountPerM3")),
        "aspergillus_count_per_m3": _num(kwargs.get("aspergillusCountPerM3")),
        "penicillium_count_per_m3": _num(kwargs.get("penicilliumCountPerM3")),
        "temperature_c": _num(kwargs.get("temperatureC")),
        "relative_humidity": _num(kwargs.get("relativeHumidity")),
        "created_at": now_iso(),
        "actor_id": "m0ldalg1",
    }
    get_kotoba_client().insert_row("vertex_mold_air_sampling", row_dict)
    return {"sessionId": session_id}


def propose_slit_candidate(**kwargs: Any) -> dict[str, Any]:
    species = str(kwargs.get("species") or "")
    if not species:
        return {"error": "species required"}
    candidate_id = _id("slit")
    excipients = kwargs.get("excipients")
    if not isinstance(excipients, list):
        excipients = ["mannitol", "gelatin", "sodium hydroxide"]
    row_dict = {
        "vertex_id": f"mold-allergy:slit:{candidate_id}",
        "owner_did": OWNER_DID,
        "candidate_id": candidate_id,
        "species": species,
        "allergen_source": str(kwargs.get("allergenSource") or "recombinant"),
        "major_allergen": str(kwargs.get("majorAllergen") or ""),
        "dosage_form": str(kwargs.get("dosageForm") or "freeze-dried orodispersible tablet"),
        "buildup_weeks": int(_num(kwargs.get("buildupWeeks"), 1)),
        "maintenance_dose_jau": _num(kwargs.get("maintenanceDoseJau"), 2000),
        "excipients_json": json.dumps(excipients, ensure_ascii=False),
        "target_indication": str(kwargs.get("targetIndication") or "allergic rhinitis"),
        "design_lineage": "Shidakure/Acitea",
        "phase": str(kwargs.get("phase") or "preclinical"),
        "created_at": now_iso(),
        "actor_id": "m0ldalg1",
    }
    get_kotoba_client().insert_row("vertex_mold_slit_candidate", row_dict)
    return {"candidateId": candidate_id}


def list_allergens(species: Any = None, limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    lim = _clamp(limit, 50)
    off = _offset(offset)
    all_rows = []
    if species:
        # R0: Multi-predicate with ordering, limiting, and offsetting in Python
        # Select all matching species, then filter/sort in-memory
        unfiltered_rows = get_kotoba_client().select_where(
            "vertex_mold_allergen", "species", str(species)
        )
        all_rows = sorted(unfiltered_rows, key=lambda x: (x["species"], x["allergen"]))
    else:
        # R0: Ordering, limiting, and offsetting in Python
        unfiltered_rows = get_kotoba_client().select_where("vertex_mold_allergen", "vertex_id", "*") # Fetch all
        all_rows = sorted(unfiltered_rows, key=lambda x: (x["species"], x["allergen"]))

    # Apply limit and offset in Python
    rows = all_rows[off : off + lim]
    return {"allergens": rows, "total": len(all_rows), "offset": off, "limit": lim}


def list_slit_candidates(species: Any = None, phase: Any = None, limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    lim = _clamp(limit, 50)
    off = _offset(offset)
    # R0: Multi-predicate filter, ordering, limiting, and offsetting in Python
    # Fetch all candidates and then apply filters, sort, limit, and offset in-memory.
    all_candidates = get_kotoba_client().select_where("vertex_mold_slit_candidate", "vertex_id", "*")

    filtered_candidates = []
    for candidate in all_candidates:
        match = True
        if species and candidate.get("species") != str(species):
            match = False
        if phase and candidate.get("phase") != str(phase):
            match = False
        if match:
            filtered_candidates.append(candidate)

    # Sort by created_at DESC
    filtered_candidates.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Apply limit and offset in Python
    rows = filtered_candidates[off : off + lim]
    return {"candidates": rows, "total": len(filtered_candidates), "offset": off, "limit": lim}
