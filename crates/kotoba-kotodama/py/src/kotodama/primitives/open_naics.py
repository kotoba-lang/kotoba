"""open-naics primitives for the LangServer + UDF runtime."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OPEN_NAICS_DID = "did:web:open-naics.etzhayyim.com"
NAICS_DID = "did:web:naics.etzhayyim.com"
ACTOR_ID = "sys.worker.open-naics"
VALID_RELATIONS = {"exactMatch", "broader", "narrower", "relatedTo"}

try:
    from langgraph.graph import END, StateGraph  # type: ignore

    _LANGGRAPH_OK = True
except ImportError:  # pragma: no cover
    END = "END"  # type: ignore[assignment]
    StateGraph = object  # type: ignore[assignment]
    _LANGGRAPH_OK = False


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def verification_for_confidence(confidence: Any) -> str:
    c = _confidence(confidence)
    if c >= 0.9:
        return "authoritative"
    if c >= 0.5:
        return "community"
    return "candidate"


def industry_did(naics_code: Any) -> str:
    return f"{NAICS_DID}:industry:{str(naics_code or '').strip()}"


def classification_vertex_id(entity_did: str, naics_code: str, classified_at: str) -> str:
    return f"at://{OPEN_NAICS_DID}/com.etzhayyim.apps.openNaics.classification/{_digest(entity_did, naics_code, classified_at)}"


def _audit(caller_did: str) -> dict[str, Any]:
    did = caller_did or OPEN_NAICS_DID
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 2,
        "owner_did": did,
        "org_id": did,
        "user_id": did,
        "actor_id": ACTOR_ID,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    get_kotoba_client().insert_row(table, row)


async def _classify_langgraph(
    entity_did: str, naics_code: str, confidence: float
) -> dict[str, Any]:
    if not _LANGGRAPH_OK:
        return {
            "verification": verification_for_confidence(confidence),
            "requireReview": confidence < 0.5,
        }

    def derive(state: dict[str, Any]) -> dict[str, Any]:
        conf = _confidence(state.get("confidence"))
        state["verification"] = verification_for_confidence(conf)
        state["requireReview"] = conf < 0.5
        state["industryDid"] = industry_did(state.get("naicsCode"))
        return state

    graph = StateGraph(dict)
    graph.add_node("derive", derive)
    graph.set_entry_point("derive")
    graph.add_edge("derive", END)
    compiled = graph.compile()
    state = {"entityDid": entity_did, "naicsCode": naics_code, "confidence": confidence}
    if hasattr(compiled, "ainvoke"):
        return dict(await compiled.ainvoke(state))
    return dict(compiled.invoke(state))


async def task_open_naics_classify_entity(
    entityDid: str = "",
    naicsCode: str = "",
    entityName: str = "",
    country: str = "",
    evidenceUrl: str = "",
    confidence: float = 0.0,
    classifiedAt: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    code = str(naicsCode or "").strip()
    if not entityDid or not code:
        return {"ok": False, "error": "entityDid and naicsCode required"}
    if not code.isdigit() or len(code) < 2 or len(code) > 6:
        return {"ok": False, "error": "naicsCode must be 2-6 digits"}
    conf = _confidence(confidence)
    decision = await _classify_langgraph(entityDid, code, conf)
    verification = str(decision.get("verification") or verification_for_confidence(conf))
    status = "confirmed" if verification in {"authoritative", "community"} else "candidate"
    classified_at = classifiedAt or _now_iso()
    vertex_id = classification_vertex_id(entityDid, code, classified_at)
    _insert(
        "vertex_open_naics_classification",
        {
            "vertex_id": vertex_id,
            "entity_did": entityDid,
            "naics_code": code,
            "entity_name": entityName or None,
            "country": country or None,
            "evidence_url": evidenceUrl or None,
            "confidence": conf,
            "verification": verification,
            "status": status,
            "classified_at": classified_at,
            **_audit(callerDid or OPEN_NAICS_DID),
        },
        dry_run=dryRun,
    )
    return {
        "ok": True,
        "vertexId": vertex_id,
        "verification": verification,
        "requireReview": bool(decision.get("requireReview")),
        "status": status,
        "industryDid": industry_did(code),
    }


async def task_open_naics_record_concordance(
    naicsCode: str = "",
    otherTaxonomy: str = "",
    otherCode: str = "",
    relation: str = "",
    confidence: float | None = None,
    source: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    code = str(naicsCode or "").strip()
    if not code or not otherTaxonomy or not otherCode or not relation:
        return {"ok": False, "error": "naicsCode, otherTaxonomy, otherCode and relation required"}
    if not code.isdigit() or len(code) < 2 or len(code) > 6:
        return {"ok": False, "error": "naicsCode must be 2-6 digits"}
    if relation not in VALID_RELATIONS:
        return {"ok": False, "error": f"invalid relation: {relation}"}
    vertex_id = f"at://{OPEN_NAICS_DID}/com.etzhayyim.apps.openNaics.concordance/{_digest(code, otherTaxonomy, otherCode, relation)}"
    _insert(
        "vertex_open_naics_concordance",
        {
            "vertex_id": vertex_id,
            "naics_code": code,
            "other_taxonomy": otherTaxonomy,
            "other_code": otherCode,
            "relation": relation,
            "confidence": None if confidence is None else _confidence(confidence),
            "source": source or None,
            "status": "active",
            **_audit(callerDid or OPEN_NAICS_DID),
        },
        dry_run=dryRun,
    )
    return {"ok": True, "vertexId": vertex_id, "status": "active"}
