"""Kenkyusha research-frontier XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client


APP_DID = "did:web:kenkyusha.etzhayyim.com"
APP_ID = "kk8r3n5v"
KIND_TABLES = {
    "discipline": "vertex_kenkyusha_discipline",
    "frontier": "vertex_kenkyusha_frontier",
    "hypothesis": "vertex_kenkyusha_hypothesis",
    "evidence": "vertex_kenkyusha_evidence",
    "didRegistration": "vertex_kenkyusha_did_registration",
}

ISCED = [
    ("0011", "00", "001", "Basic programmes and qualifications", "基礎課程"),
    ("0111", "01", "011", "Education science", "教育学"),
    ("0213", "02", "021", "Fine arts", "美術"),
    ("0311", "03", "031", "Economics", "経済学"),
    ("0421", "04", "042", "Law", "法学"),
    ("0511", "05", "051", "Biology", "生物学"),
    ("0533", "05", "053", "Physics", "物理学"),
    ("0613", "06", "061", "Software and applications development", "ソフトウェア・アプリケーション開発"),
    ("0714", "07", "071", "Electronics and automation", "電子工学・自動化"),
    ("0912", "09", "091", "Medicine", "医学"),
]


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(prefix: str = "k") -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:6]}"


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        n = float(v)
        return n if n == n and n not in (float("inf"), float("-inf")) else fallback
    except (TypeError, ValueError):
        return fallback


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v





def _djb2(prefix: str, parts: list[str]) -> str:
    canonical = "|".join(parts)
    h = 5381
    for ch in canonical:
        h = ((h * 33) + ord(ch)) & 0xFFFFFFFF
    return f"{prefix}{h:08x}{len(canonical):04x}"


def _collection(name: str) -> str:
    return f"com.etzhayyim.apps.kenkyusha.{name}"


def _record_key(name: str, record: dict[str, Any]) -> str:
    if name == "discipline":
        key = record.get("isced4") or record.get("id")
    elif name == "frontier":
        key = record.get("frontierId") or record.get("id")
    elif name == "hypothesis":
        key = record.get("hypothesisId") or record.get("id")
    elif name == "evidence":
        key = record.get("evidenceId") or record.get("id")
    elif name == "didRegistration":
        key = record.get("path") or record.get("did") or record.get("id")
    else:
        key = record.get("id")
    return _str(key or _gid(name))[:128]


def _vertex_uri(name: str, rkey: str) -> str:
    return f"at://{APP_DID}/{_collection(name)}/{rkey}"


def _common_columns() -> list[str]:
    return [
        "vertex_id",
        "record_key",
        "did",
        "label",
        "status",
        "value_json",
        "indexed_at",
        "created_at",
        "updated_at",
        "org_id",
        "user_id",
        "actor_id",
        "actor_did",
        "org_did",
        "owner_did",
        "sensitivity_ord",
    ]


def _typed_values(name: str, record: dict[str, Any], rkey: str) -> dict[str, Any]:
    if name == "discipline":
        return {
            "isced4": _str(record.get("isced4")),
            "isced_broad": _str(record.get("iscedBroad")),
            "isced_narrow": _str(record.get("iscedNarrow")),
            "name_en": _str(record.get("nameEn")),
            "name_ja": _str(record.get("nameJa")),
            "paradigm": _str(record.get("paradigm")),
            "maturity": _str(record.get("maturity")),
            "interdisciplinarity": _str(record.get("interdisciplinarity")),
            "cohort_hash": _str(record.get("cohortHash")),
            "publication_count": int(_num(record.get("publicationCount"), 0)),
            "citation_count": int(_num(record.get("citationCount"), 0)),
            "frontier_count": int(_num(record.get("frontierCount"), 0)),
        }
    if name == "frontier":
        return {
            "frontier_id": _str(record.get("frontierId") or record.get("id") or rkey),
            "title": _str(record.get("title")),
            "description": _str(record.get("description")),
            "detection_method": _str(record.get("detectionMethod")),
            "primary_discipline": _str(record.get("primaryDiscipline")),
            "urgency": _str(record.get("urgency")),
            "evidence_level": _str(record.get("evidenceLevel")),
            "consensus_level": _str(record.get("consensusLevel")),
            "cohort_hash": _str(record.get("cohortHash")),
            "hypothesis_count": int(_num(record.get("hypothesisCount"), 0)),
            "evidence_count": int(_num(record.get("evidenceCount"), 0)),
            "detected_at": _str(record.get("detectedAt")),
            "last_analyzed_at": _str(record.get("lastAnalyzedAt")),
        }
    if name == "hypothesis":
        return {
            "hypothesis_id": _str(record.get("hypothesisId") or record.get("id") or rkey),
            "frontier_id": _str(record.get("frontierId")),
            "statement": _str(record.get("statement")),
            "rationale": _str(record.get("rationale")),
            "confidence_score": _num(record.get("confidenceScore"), 0.0),
            "llm_model": _str(record.get("llmModel")),
            "evaluated_at": _str(record.get("evaluatedAt")),
        }
    if name == "evidence":
        return {
            "evidence_id": _str(record.get("evidenceId") or record.get("id") or rkey),
            "frontier_id": _str(record.get("frontierId")),
            "hypothesis_id": _str(record.get("hypothesisId")),
            "source_type": _str(record.get("sourceType")),
            "source_did": _str(record.get("sourceDid")),
            "source_uri": _str(record.get("sourceUri")),
            "relevance_score": _num(record.get("relevanceScore"), 0.0),
            "evidence_type": _str(record.get("evidenceType")),
            "extracted_claim": _str(record.get("extractedClaim")),
        }
    if name == "didRegistration":
        return {
            "path": _str(record.get("path")),
            "display_name": _str(record.get("displayName")),
        }
    raise ValueError(f"unsupported kenkyusha record kind: {name}")


def _label(record: dict[str, Any]) -> str:
    return _str(record.get("nameEn") or record.get("title") or record.get("statement") or record.get("extractedClaim") or record.get("displayName"))


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid.uuid5(uuid.NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _write_edge(table: str, src: str, dst: str, relation: str, value: dict[str, Any], now: str) -> None:
    value_json = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    row_dict = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": value_json,
        "created_at": now,
        "updated_at": now,
        "owner_did": APP_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row(table, row_dict)


def _write_edges(name: str, record: dict[str, Any], vertex_id: str, now: str) -> None:
    if name == "frontier":
        discipline = _str(record.get("primaryDiscipline"))
        if discipline:
            _write_edge(
                "edge_kenkyusha_frontier_discipline",
                vertex_id,
                _vertex_uri("discipline", discipline),
                "primary_discipline",
                {"frontierId": record.get("frontierId") or record.get("id"), "isced4": discipline},
                now,
            )
    elif name == "hypothesis":
        frontier_id = _str(record.get("frontierId"))
        if frontier_id:
            _write_edge(
                "edge_kenkyusha_hypothesis_frontier",
                vertex_id,
                _vertex_uri("frontier", frontier_id),
                "hypothesis_for_frontier",
                {"hypothesisId": record.get("hypothesisId") or record.get("id"), "frontierId": frontier_id},
                now,
            )
    elif name == "evidence":
        hypothesis_id = _str(record.get("hypothesisId"))
        if hypothesis_id:
            _write_edge(
                "edge_kenkyusha_evidence_hypothesis",
                vertex_id,
                _vertex_uri("hypothesis", hypothesis_id),
                "evidence_for_hypothesis",
                {"evidenceId": record.get("evidenceId") or record.get("id"), "hypothesisId": hypothesis_id, "frontierId": record.get("frontierId")},
                now,
            )


def _write(name: str, record: dict[str, Any]) -> dict[str, str]:
    table = KIND_TABLES.get(name)
    if table is None:
        raise ValueError(f"unsupported kenkyusha record kind: {name}")
    now = _now()
    rkey = _record_key(name, record)
    collection = _collection(name)
    vertex_id = _vertex_uri(name, rkey)
    value_json = json.dumps({"$type": collection, **record}, ensure_ascii=False, separators=(",", ":"), default=str)
    typed = _typed_values(name, record, rkey)
    values = {
        "vertex_id": vertex_id,
        "record_key": rkey,
        "did": _str(record.get("did")),
        "label": _label(record),
        "status": _str(record.get("status")),
        "value_json": value_json,
        "indexed_at": now,
        "created_at": _str(record.get("createdAt")) or now,
        "updated_at": _str(record.get("updatedAt") or record.get("evaluatedAt")) or now,
        "org_id": _str(record.get("orgId")) or "anon",
        "user_id": _str(record.get("userId")) or "anon",
        "actor_id": _str(record.get("actorId")) or APP_ID,
        "actor_did": APP_DID,
        "org_did": _str(record.get("orgId")) or "anon",
        "owner_did": APP_DID,
        "sensitivity_ord": 2,
        **typed,
    }
    get_kotoba_client().insert_row(table, values)
    _write_edges(name, record, vertex_id, now)
    return {"uri": vertex_id, "rkey": rkey}


def _list(name: str, match: dict[str, Any] | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    table = KIND_TABLES.get(name)
    if table is None:
        raise ValueError(f"unsupported kenkyusha record kind: {name}")

    client = get_kotoba_client()
    # R0: Multi-predicate / ORDER BY / OFFSET are handled in Python.
    # The Datalog query fetches all entities associated with the given table name.
    # This assumes entities are associated with a `:vertex/table` attribute for lookup.
    datalog_query = f'[:find (pull ?e [*]) :where [?e :vertex/table "{table}"]]'
    all_rows = client.q(datalog_query)

    processed_rows = []
    for row in all_rows:
        raw = row
        value_json_str = raw.get("value_json")
        if isinstance(value_json_str, str) and value_json_str:
            try:
                data = json.loads(value_json_str)
                if isinstance(data, dict):
                    raw = {**data, **raw}
            except json.JSONDecodeError:
                pass
        processed_rows.append(raw)

    if match:
        processed_rows = [r for r in processed_rows if all(str(r.get(k) or "") == str(v) for k, v in match.items())]

    processed_rows.sort(key=lambda x: x.get("indexed_at", ""), reverse=True)

    rows = processed_rows[offset : offset + limit]

    return rows


def task_kenkyusha_seed_disciplines(**_: Any) -> dict[str, Any]:
    if _list("discipline", limit=1):
        return {"ok": True, "detail": "already seeded"}
    for isced4, broad, narrow, name_en, name_ja in ISCED:
        cohort = _djb2("d", [broad, narrow, isced4, "mixed", "nascent", "mono"])
        _write("discipline", {
            "id": _gid("disc"),
            "did": f"did:web:kenkyusha.etzhayyim.com:discipline:{isced4}",
            "isced4": isced4,
            "iscedBroad": broad,
            "iscedNarrow": narrow,
            "nameEn": name_en,
            "nameJa": name_ja,
            "paradigm": "mixed",
            "maturity": "nascent",
            "interdisciplinarity": "mono",
            "cohortHash": cohort,
            "publicationCount": 0,
            "citationCount": 0,
            "frontierCount": 0,
            "orgId": "anon",
            "userId": "anon",
            "actorId": APP_ID,
            "createdAt": _now(),
        })
    return {"ok": True, "detail": f"seeded {len(ISCED)} ISCED-F disciplines"}


def task_kenkyusha_detect_frontiers(method: str = "citationGap", limit: Any = 10, **_: Any) -> dict[str, Any]:
    count = max(1, min(int(_num(limit, 10)), 50))
    detected = 0
    for idx in range(count if method in ("manual", "seed") else 1):
        cohort = _djb2("r", [method, str(idx), "medium", "none", "none"])
        frontier_id = _gid("frontier")
        _write("frontier", {
            "id": frontier_id,
            "did": f"did:web:kenkyusha.etzhayyim.com:frontier:{cohort}",
            "title": f"{method}: research frontier {idx + 1}",
            "description": "Potential unresolved research area detected by fallback BPMN worker",
            "detectionMethod": method,
            "primaryDiscipline": "0000",
            "secondaryDisciplines": "[]",
            "urgency": "medium",
            "evidenceLevel": "none",
            "consensusLevel": "none",
            "cohortHash": cohort,
            "hypothesisCount": 0,
            "evidenceCount": 0,
            "status": "detected",
            "detectedAt": _now(),
            "lastAnalyzedAt": _now(),
            "orgId": "anon",
            "userId": "anon",
            "actorId": APP_ID,
            "createdAt": _now(),
        })
        detected += 1
    return {"ok": True, "detected": detected, "method": method}


def task_kenkyusha_generate_hypothesis(frontierId: str = "", title: str = "", description: str = "", **_: Any) -> dict[str, Any]:
    if not frontierId:
        return {"ok": False, "error": "frontierId required"}
    prompt = f'Given the research frontier "{title or frontierId}" - {description}, generate one testable scientific hypothesis.'
    try:
        resp = llm.call_tier("fast", system="You produce concise testable scientific hypotheses.", user=prompt, max_tokens=250, temperature=0.3)
        statement = _str(resp.get("content")) or f"Hypothesis for: {title or frontierId}"
        model = _str(resp.get("model")) or "fast"
    except Exception:
        statement = f"Hypothesis for: {title or frontierId}"
        model = "fallback"
    hyp_id = _gid("hyp")
    _write("hypothesis", {"id": hyp_id, "frontierId": frontierId, "statement": statement, "rationale": f"Auto-generated from frontier analysis: {description}", "supportingEvidence": "[]", "contradictingEvidence": "[]", "confidenceScore": 0.3, "llmModel": model, "status": "proposed", "orgId": "anon", "userId": "anon", "actorId": APP_ID, "createdAt": _now()})
    return {"ok": True, "hypothesisId": hyp_id, "statement": statement}


def task_kenkyusha_collect_evidence(hypothesisId: str = "", frontierId: str = "", limit: Any = 20, **_: Any) -> dict[str, Any]:
    if not hypothesisId or not frontierId:
        return {"ok": False, "error": "hypothesisId and frontierId required"}
    evidence_id = _gid("ev")
    _write("evidence", {"id": evidence_id, "frontierId": frontierId, "hypothesisId": hypothesisId, "sourceType": "manual", "sourceDid": "", "sourceUri": "", "relevanceScore": 0.5, "evidenceType": "neutral", "extractedClaim": "Evidence collection placeholder until typed research tables land", "orgId": "anon", "userId": "anon", "actorId": APP_ID, "createdAt": _now()})
    return {"ok": True, "collected": 1}


def task_kenkyusha_evaluate_hypothesis(hypothesisId: str = "", **_: Any) -> dict[str, Any]:
    if not hypothesisId:
        return {"ok": False, "error": "hypothesisId required"}
    evidence = _list("evidence", {"hypothesisId": hypothesisId}, limit=100)
    supports = len([e for e in evidence if e.get("evidenceType") == "supports"])
    contradicts = len([e for e in evidence if e.get("evidenceType") == "contradicts"])
    total = len(evidence)
    status = "supported" if total >= 5 and supports > contradicts * 2 else "refuted" if total >= 5 and contradicts > supports * 2 else "inconclusive"
    confidence = 0.3 if total < 5 else 0.6
    _write("hypothesis", {"id": _gid("hyp_eval"), "hypothesisId": hypothesisId, "status": status, "confidenceScore": confidence, "supportingEvidence": json.dumps({"supports": supports, "contradicts": contradicts, "total": total}), "evaluatedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID, "createdAt": _now()})
    return {"ok": True, "hypothesisId": hypothesisId, "status": status, "confidenceScore": confidence, "supports": supports, "contradicts": contradicts, "totalEvidence": total}


def task_kenkyusha_register_dids(batchSize: Any = 10, **_: Any) -> dict[str, Any]:
    rows = _list("discipline", limit=max(1, int(_num(batchSize, 10))))
    for row in rows:
        _write("didRegistration", {"id": _gid("did"), "did": row.get("did"), "path": f"discipline:{row.get('isced4')}", "displayName": f"{row.get('nameEn')} / {row.get('nameJa')}", "createdAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"ok": True, "registered": len(rows)}


def task_kenkyusha_list_frontiers(discipline: str = "", urgency: str = "", status: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _list("frontier", {"primaryDiscipline": discipline, "urgency": urgency, "status": status}, int(_num(limit, 50)), int(_num(offset, 0)))
    return {"ok": True, "frontiers": rows, "total": len(rows), "offset": int(_num(offset, 0)), "limit": int(_num(limit, 50))}


def task_kenkyusha_get_frontier(id: str = "", did: str = "", **_: Any) -> dict[str, Any]:
    if not id and not did:
        return {"ok": False, "error": "id or did required"}
    rows = _list("frontier", {"id": id, "did": did}, limit=1)
    if not rows:
        return {"ok": False, "error": "frontier not found"}
    hypotheses = _list("hypothesis", {"frontierId": _str(rows[0].get("id"))}, limit=50)
    return {"ok": True, "frontier": rows[0], "hypotheses": hypotheses}


def task_kenkyusha_list_disciplines(broad: str = "", limit: Any = 100, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _list("discipline", {"iscedBroad": broad}, int(_num(limit, 100)), int(_num(offset, 0)))
    if not rows and not broad:
        rows = [{"isced4": a, "iscedBroad": b, "iscedNarrow": c, "nameEn": d, "nameJa": e, "paradigm": "mixed", "maturity": "nascent", "frontierCount": 0, "did": f"did:web:kenkyusha.etzhayyim.com:discipline:{a}"} for a, b, c, d, e in ISCED]
    return {"ok": True, "disciplines": rows, "total": len(rows), "offset": int(_num(offset, 0)), "limit": int(_num(limit, 100))}


def task_kenkyusha_search_evidence(frontierId: str = "", sourceType: str = "", evidenceType: str = "", limit: Any = 50, **_: Any) -> dict[str, Any]:
    rows = _list("evidence", {"frontierId": frontierId, "sourceType": sourceType, "evidenceType": evidenceType}, int(_num(limit, 50)))
    return {"ok": True, "evidence": rows}


def task_kenkyusha_stats(**_: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "disciplines": len(_list("discipline", limit=500)),
        "frontiers": [{"status": "all", "count": len(_list("frontier", limit=500))}],
        "hypotheses": [{"status": "all", "count": len(_list("hypothesis", limit=500))}],
        "evidence": [{"sourceType": "all", "count": len(_list("evidence", limit=500))}],
    }


def task_kenkyusha_coverage_map(broad: str = "", **_: Any) -> dict[str, Any]:
    disciplines = task_kenkyusha_list_disciplines(broad=broad)["disciplines"]
    frontiers = _list("frontier", limit=500)
    coverage = []
    for d in disciplines:
        isced = _str(d.get("isced4"))
        related = [f for f in frontiers if f.get("primaryDiscipline") == isced]
        coverage.append({"isced4": isced, "nameEn": d.get("nameEn"), "maturity": d.get("maturity"), "frontierCount": len(related), "detected": len([f for f in related if f.get("status") == "detected"]), "investigating": len([f for f in related if f.get("status") == "investigating"]), "resolved": len([f for f in related if f.get("status") == "resolved"])})
    covered = len([r for r in coverage if r["frontierCount"] > 0])
    return {"ok": True, "coverage": coverage, "total": len(coverage), "covered": covered, "eta": round(covered / len(coverage), 3) if coverage else 0}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.kenkyusha.collectEvidence": task_kenkyusha_collect_evidence,
        "xrpc.com.etzhayyim.apps.kenkyusha.coverageMap": task_kenkyusha_coverage_map,
        "xrpc.com.etzhayyim.apps.kenkyusha.detectFrontiers": task_kenkyusha_detect_frontiers,
        "xrpc.com.etzhayyim.apps.kenkyusha.evaluateHypothesis": task_kenkyusha_evaluate_hypothesis,
        "xrpc.com.etzhayyim.apps.kenkyusha.generateHypothesis": task_kenkyusha_generate_hypothesis,
        "xrpc.com.etzhayyim.apps.kenkyusha.getFrontier": task_kenkyusha_get_frontier,
        "xrpc.com.etzhayyim.apps.kenkyusha.listDisciplines": task_kenkyusha_list_disciplines,
        "xrpc.com.etzhayyim.apps.kenkyusha.listFrontiers": task_kenkyusha_list_frontiers,
        "xrpc.com.etzhayyim.apps.kenkyusha.registerDids": task_kenkyusha_register_dids,
        "xrpc.com.etzhayyim.apps.kenkyusha.searchEvidence": task_kenkyusha_search_evidence,
        "xrpc.com.etzhayyim.apps.kenkyusha.seedDisciplines": task_kenkyusha_seed_disciplines,
        "xrpc.com.etzhayyim.apps.kenkyusha.stats": task_kenkyusha_stats,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
