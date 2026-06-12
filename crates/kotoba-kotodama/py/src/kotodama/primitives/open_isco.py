"""open-isco primitives for the LangServer + UDF runtime."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OPEN_ISCO_DID = "did:web:open-isco.etzhayyim.com"
ISCO_DID = "did:web:isco.etzhayyim.com"
ACTOR_ID = "sys.worker.open-isco"
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


def code_level(isco_code: Any) -> str:
    length = len(str(isco_code or "").strip())
    if length == 1:
        return "major"
    if length == 2:
        return "submajor"
    if length == 3:
        return "minor"
    return "unit"


def verification_for_confidence(confidence: Any) -> str:
    c = _confidence(confidence)
    if c >= 0.9:
        return "authoritative"
    if c >= 0.5:
        return "community"
    return "candidate"


def occupation_did(isco_code: Any) -> str:
    return f"{ISCO_DID}:occupation:{str(isco_code or '').strip()}"


def classification_vertex_id(worker_did: str, isco_code: str, classified_at: str) -> str:
    return f"at://{OPEN_ISCO_DID}/com.etzhayyim.apps.openIsco.classification/{_digest(worker_did, isco_code, classified_at)}"


def _audit(caller_did: str, employer_did: str = "") -> dict[str, Any]:
    did = caller_did or OPEN_ISCO_DID
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 2,
        "owner_did": did,
        "org_id": employer_did or did,
        "user_id": did,
        "actor_id": ACTOR_ID,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    get_kotoba_client().insert_row(table, row)


async def _classify_langgraph(worker_did: str, isco_code: str, confidence: float) -> dict[str, Any]:
    if not _LANGGRAPH_OK:
        return {
            "codeLevel": code_level(isco_code),
            "verification": verification_for_confidence(confidence),
            "requireReview": confidence < 0.5,
        }

    def derive(state: dict[str, Any]) -> dict[str, Any]:
        conf = _confidence(state.get("confidence"))
        state["codeLevel"] = code_level(state.get("iscoCode"))
        state["verification"] = verification_for_confidence(conf)
        state["requireReview"] = conf < 0.5
        state["occupationDid"] = occupation_did(state.get("iscoCode"))
        return state

    graph = StateGraph(dict)
    graph.add_node("derive", derive)
    graph.set_entry_point("derive")
    graph.add_edge("derive", END)
    compiled = graph.compile()
    state = {"workerDid": worker_did, "iscoCode": isco_code, "confidence": confidence}
    if hasattr(compiled, "ainvoke"):
        return dict(await compiled.ainvoke(state))
    return dict(compiled.invoke(state))


async def task_open_isco_classify_worker(
    workerDid: str = "",
    iscoCode: str = "",
    employerDid: str = "",
    certificateUrl: str = "",
    yearsExperience: float | None = None,
    confidence: float = 0.0,
    classifiedAt: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    code = str(iscoCode or "").strip()
    if not workerDid or not code:
        return {"ok": False, "error": "workerDid and iscoCode required"}
    if not code.isdigit() or len(code) not in {1, 2, 3, 4}:
        return {"ok": False, "error": "iscoCode must be 1-4 digits"}
    conf = _confidence(confidence)
    decision = await _classify_langgraph(workerDid, code, conf)
    verification = str(decision.get("verification") or verification_for_confidence(conf))
    level = str(decision.get("codeLevel") or code_level(code))
    status = "confirmed" if verification in {"authoritative", "community"} else "candidate"
    classified_at = classifiedAt or _now_iso()
    vertex_id = classification_vertex_id(workerDid, code, classified_at)
    _insert("vertex_open_isco_classification", {
        "vertex_id": vertex_id,
        "worker_did": workerDid,
        "isco_code": code,
        "code_level": level,
        "employer_did": employerDid or None,
        "certificate_url": certificateUrl or None,
        "years_experience": yearsExperience,
        "confidence": conf,
        "verification": verification,
        "status": status,
        "classified_at": classified_at,
        **_audit(callerDid or OPEN_ISCO_DID, employerDid),
    }, dry_run=dryRun)
    edge_id = f"at://{OPEN_ISCO_DID}/com.etzhayyim.apps.openIsco.classificationOccupation/{_digest(vertex_id, code)}"
    _insert("edge_open_isco_classification_occ", {
        "edge_id": edge_id,
        "src_vid": vertex_id,
        "dst_vid": occupation_did(code),
        "role": "occupied_as",
        **_audit(callerDid or OPEN_ISCO_DID, employerDid),
    }, dry_run=dryRun)
    return {
        "ok": True,
        "vertexId": vertex_id,
        "edgeId": edge_id,
        "codeLevel": level,
        "verification": verification,
        "requireReview": bool(decision.get("requireReview")),
        "status": status,
        "occupationDid": occupation_did(code),
    }


async def task_open_isco_record_concordance(
    iscoCode: str = "",
    otherTaxonomy: str = "",
    otherCode: str = "",
    relation: str = "",
    confidence: float | None = None,
    source: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    code = str(iscoCode or "").strip()
    if not code or not otherTaxonomy or not otherCode or not relation:
        return {"ok": False, "error": "iscoCode, otherTaxonomy, otherCode and relation required"}
    if not code.isdigit() or len(code) not in {1, 2, 3, 4}:
        return {"ok": False, "error": "iscoCode must be 1-4 digits"}
    if relation not in VALID_RELATIONS:
        return {"ok": False, "error": f"invalid relation: {relation}"}
    vertex_id = f"at://{OPEN_ISCO_DID}/com.etzhayyim.apps.openIsco.concordance/{_digest(code, otherTaxonomy, otherCode, relation)}"
    _insert("vertex_open_isco_concordance", {
        "vertex_id": vertex_id,
        "isco_code": code,
        "other_taxonomy": otherTaxonomy,
        "other_code": otherCode,
        "relation": relation,
        "confidence": None if confidence is None else _confidence(confidence),
        "source": source or None,
        "status": "active",
        **_audit(callerDid or OPEN_ISCO_DID),
    }, dry_run=dryRun)
    return {"ok": True, "vertexId": vertex_id, "status": "active"}

