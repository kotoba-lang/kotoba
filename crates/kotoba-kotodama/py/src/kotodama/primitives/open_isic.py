"""open-isic primitives for the LangServer + UDF runtime.

These task handlers replace the Cloudflare Worker as the authoritative write
path for ISIC classifications. The static taxonomy remains in
`60-apps/etzhayyim-project-open-isic/data/classes`; BPMN/Zeebe owns process
orchestration and these functions own deterministic validation + graph writes.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OPEN_ISIC_DID = "did:web:open-isic.etzhayyim.com"
ACTOR_ID = "sys.worker.open-isic"
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


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "60-apps").exists() and (parent / "20-actors").exists():
            return parent
    return here.parents[6]


def _classes_dir() -> Path:
    configured = os.environ.get("OPEN_ISIC_CLASSES_DIR")
    if configured:
        return Path(configured)
    return _repo_root() / "60-apps/etzhayyim-project-open-isic/data/classes"


def _load_class(code: str) -> dict[str, Any] | None:
    norm = str(code or "").strip()
    if not norm:
        return None
    path = _classes_dir() / f"{norm}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _class_did(code: str) -> str:
    return f"{OPEN_ISIC_DID}:class:{code}"


def _vertex_id(collection: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
    return f"at://{OPEN_ISIC_DID}/{collection}/{digest}"


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


def _audit(caller_did: str) -> dict[str, Any]:
    did = caller_did or OPEN_ISIC_DID
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 1,
        "owner_did": did,
        "org_id": did,
        "user_id": did,
        "actor_id": ACTOR_ID,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    get_kotoba_client().insert_row(table, row)


async def _classify_langgraph(entity_name: str, isic_class: dict[str, Any] | None, confidence: float) -> dict[str, Any]:
    """Small LangGraph guard used by both LangServer and UDF paths.

    It is intentionally deterministic: LangGraph gives us a checkpointable
    state-machine boundary without adding LLM dependency to the hot path.
    """
    if not _LANGGRAPH_OK:
        return {
            "verification": verification_for_confidence(confidence),
            "requireReview": confidence < 0.5,
            "reason": "langgraph unavailable; confidence rule applied",
        }

    def validate(state: dict[str, Any]) -> dict[str, Any]:
        state["classKnown"] = bool(state.get("isicClass"))
        return state

    def decide(state: dict[str, Any]) -> dict[str, Any]:
        conf = _confidence(state.get("confidence"))
        state["verification"] = verification_for_confidence(conf)
        state["requireReview"] = (not state.get("classKnown")) or conf < 0.5
        label = (state.get("isicClass") or {}).get("nameEn") or "unknown ISIC class"
        state["reason"] = f"{state.get('entityName') or 'entity'} -> {label}"
        return state

    graph = StateGraph(dict)
    graph.add_node("validate", validate)
    graph.add_node("decide", decide)
    graph.set_entry_point("validate")
    graph.add_edge("validate", "decide")
    graph.add_edge("decide", END)
    compiled = graph.compile()
    if hasattr(compiled, "ainvoke"):
        return dict(await compiled.ainvoke({
            "entityName": entity_name,
            "isicClass": isic_class,
            "confidence": confidence,
        }))
    return dict(compiled.invoke({
        "entityName": entity_name,
        "isicClass": isic_class,
        "confidence": confidence,
    }))


async def task_open_isic_classify_entity(
    entityDid: str = "",
    isicClassCode: str = "",
    entityName: str = "",
    country: str = "",
    evidenceUrl: str = "",
    confidence: float = 0.0,
    classifiedAt: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if not entityDid or not isicClassCode:
        return {"ok": False, "error": "entityDid and isicClassCode required"}
    isic_class = _load_class(isicClassCode)
    if isic_class is None:
        return {"ok": False, "error": f"unknown ISIC class: {isicClassCode}"}
    conf = _confidence(confidence)
    decision = await _classify_langgraph(entityName, isic_class, conf)
    verification = str(decision.get("verification") or verification_for_confidence(conf))
    status = "confirmed" if verification in {"authoritative", "community"} else "candidate"
    classified_at = classifiedAt or _now_iso()
    vertex_id = _vertex_id("com.etzhayyim.apps.openIsic.classification", entityDid, isicClassCode, classified_at)
    audit = _audit(callerDid or OPEN_ISIC_DID)
    _insert("vertex_open_isic_classification", {
        "vertex_id": vertex_id,
        "entity_did": entityDid,
        "isic_class_code": isicClassCode,
        "entity_name": entityName or None,
        "country": country or None,
        "evidence_url": evidenceUrl or None,
        "confidence": conf,
        "verification": verification,
        "status": status,
        "classified_at": classified_at,
        **audit,
    }, dry_run=dryRun)
    edge_id = _vertex_id("com.etzhayyim.apps.openIsic.classificationClass", vertex_id, isicClassCode)
    _insert("edge_open_isic_classification_class", {
        "edge_id": edge_id,
        "src_vid": vertex_id,
        "dst_vid": f"at://{_class_did(isicClassCode)}/com.etzhayyim.apps.openIsic.class/{isicClassCode}",
        "role": "classifiedAs",
        **audit,
    }, dry_run=dryRun)
    return {
        "ok": True,
        "vertexId": vertex_id,
        "edgeId": edge_id,
        "verification": verification,
        "requireReview": bool(decision.get("requireReview")),
        "status": status,
        "classDid": _class_did(isicClassCode),
    }


async def task_open_isic_record_concordance(
    isicClassCode: str = "",
    otherTaxonomy: str = "",
    otherCode: str = "",
    relation: str = "",
    confidence: float | None = None,
    source: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if not isicClassCode or not otherTaxonomy or not otherCode or not relation:
        return {"ok": False, "error": "isicClassCode, otherTaxonomy, otherCode and relation required"}
    if relation not in VALID_RELATIONS:
        return {"ok": False, "error": f"invalid relation: {relation}"}
    if _load_class(isicClassCode) is None:
        return {"ok": False, "error": f"unknown ISIC class: {isicClassCode}"}
    vertex_id = _vertex_id("com.etzhayyim.apps.openIsic.concordance", isicClassCode, otherTaxonomy, otherCode, relation)
    _insert("vertex_open_isic_concordance", {
        "vertex_id": vertex_id,
        "isic_class_code": isicClassCode,
        "other_taxonomy": otherTaxonomy,
        "other_code": otherCode,
        "relation": relation,
        "confidence": None if confidence is None else _confidence(confidence),
        "source": source or None,
        "status": "active",
        **_audit(callerDid or OPEN_ISIC_DID),
    }, dry_run=dryRun)
    return {"ok": True, "vertexId": vertex_id, "status": "active"}


async def task_open_isic_flag_dual_use_industry(
    entityDid: str = "",
    entityVid: str = "",
    isicClassCode: str = "",
    confidence: float = 1.0,
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    code = isicClassCode or "2520"
    return await task_open_isic_classify_entity(
        entityDid=entityDid or entityVid,
        isicClassCode=code,
        entityName="",
        confidence=confidence,
        classifiedAt=_now_iso(),
        callerDid=callerDid,
        dryRun=dryRun,
    )


async def task_open_isic_classify_arms_manufacturing(**kwargs: Any) -> dict[str, Any]:
    kwargs["isicClassCode"] = "2520"
    return await task_open_isic_flag_dual_use_industry(**kwargs)


from typing import Any
import os
import json
import glob
from kotodama.primitives.open_isic import OPEN_ISIC_DID

_SECTION_MAP = {
    "A": ("01", "02", "03"),
    "B": ("05", "06", "07", "08", "09"),
    "C": tuple(f"{i:02d}" for i in range(10, 34)),
    "D": ("35",),
    "E": ("36", "37", "38", "39"),
    "F": ("41", "42", "43"),
    "G": ("45", "46", "47"),
    "H": ("49", "50", "51", "52", "53"),
    "I": ("55", "56"),
    "J": ("58", "59", "60", "61", "62", "63"),
    "K": ("64", "65", "66"),
    "L": ("68",),
    "M": ("69", "70", "71", "72", "73", "74", "75"),
    "N": ("77", "78", "79", "80", "81", "82"),
    "O": ("84",),
    "P": ("85",),
    "Q": ("86", "87", "88"),
    "R": ("90", "91", "92", "93"),
    "S": ("94", "95", "96"),
    "T": ("97", "98"),
    "U": ("99",)
}

_SECTION_NAMES = {
    "A": "Agriculture, forestry and fishing",
    "B": "Mining and quarrying",
    "C": "Manufacturing",
    "D": "Electricity, gas, steam and air conditioning supply",
    "E": "Water supply; sewerage, waste management and remediation activities",
    "F": "Construction",
    "G": "Wholesale and retail trade; repair of motor vehicles and motorcycles",
    "H": "Transportation and storage",
    "I": "Accommodation and food service activities",
    "J": "Information and communication",
    "K": "Financial and insurance activities",
    "L": "Real estate activities",
    "M": "Professional, scientific and technical activities",
    "N": "Administrative and support service activities",
    "O": "Public administration and defence; compulsory social security",
    "P": "Education",
    "Q": "Human health and social work activities",
    "R": "Arts, entertainment and recreation",
    "S": "Other service activities",
    "T": "Activities of households as employers",
    "U": "Activities of extraterritorial organizations and bodies"
}

def _get_classes_dir() -> str:
    from pathlib import Path
    return str(Path(__file__).resolve().parents[6] / "60-apps" / "etzhayyim-project-open-isic" / "data" / "classes")

def _load_all_classes() -> list[dict]:
    d = _get_classes_dir()
    files = glob.glob(os.path.join(d, "*.json"))
    out = []
    for f in files:
        with open(f, "r") as fp:
            out.append(json.load(fp))
    return out

async def task_open_isic_get_taxonomy(**kwargs: Any) -> dict[str, Any]:
    """Retrieve ISIC taxonomy hierarchy."""
    level = kwargs.get("level", "section")
    parent_code = kwargs.get("parentCode", "")
    
    if level == "section":
        return {
            "ok": True,
            "items": [{"code": k, "name": v} for k, v in _SECTION_NAMES.items()]
        }
        
    classes = _load_all_classes()
    
    if level == "division":
        if not parent_code:
            return {"ok": False, "error": "parentCode (Section) required for division level"}
        prefixes = _SECTION_MAP.get(parent_code.upper(), ())
        # Find unique divisions in these prefixes
        divs = set()
        for c in classes:
            c_div = c.get("code", "")[:2]
            if c_div in prefixes:
                divs.add(c_div)
        return {"ok": True, "items": [{"code": d} for d in sorted(divs)]}
        
    if level == "group":
        if not parent_code or len(parent_code) != 2:
            return {"ok": False, "error": "parentCode (2-digit Division) required for group level"}
        groups = set()
        for c in classes:
            c_grp = c.get("group", "")
            if c_grp.startswith(parent_code):
                groups.add(c_grp)
        return {"ok": True, "items": [{"code": g} for g in sorted(groups)]}
        
    if level == "class":
        if not parent_code or len(parent_code) != 3:
            return {"ok": False, "error": "parentCode (3-digit Group) required for class level"}
        cls_list = []
        for c in classes:
            if c.get("group", "") == parent_code:
                cls_list.append({"code": c.get("code"), "name": c.get("nameEn"), "description": c.get("description")})
        return {"ok": True, "items": sorted(cls_list, key=lambda x: x["code"])}
        
    return {"ok": False, "error": f"Invalid level: {level}"}
