"""APQC primitives for the LangServer + LangGraph runtime.

Standalone APQC WASM is retired (archived 2026-05-14).
Pregel implementation: kotodama.langgraph_graphs.apqc_pregel (build_graph())
DB registration: alembic/versions/20260514_0001_apqc_pregel_langgraph_assistant_seed.py

This module provides:
- Legacy task handlers (materializeSubprocesses, emitEvent, coverageSnapshot)
  still used by Zeebe/pyzeebe task routes during Phase 4 migration.
- `apqc_did()` DID builder, kept as shared utility.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives import langgraph_registry

# Pregel graph (py_factory, registered in DB via alembic 20260514_0001)
from kotodama.langgraph_graphs.apqc_pregel import (
    APQC_L1 as _PREGEL_L1,
    task_apqc_pregel_materialize,
    task_apqc_pregel_coverage,
    build_graph as _build_pregel_graph,
)


PROJECTOR_DID = "did:web:kyber-projector.etzhayyim.com"
ACTOR_ID = "sys.worker.apqc"

# Re-export catalog from pregel module (single source of truth)
APQC_L1 = [(l["code"], l["slug"], l["name"], l["subProcesses"]) for l in _PREGEL_L1]
L1_BY_CODE = {code: {"code": code, "slug": slug, "name": name, "subProcesses": count}
              for code, slug, name, count in APQC_L1}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


def apqc_did(code: str, subprocess_code: str = "") -> str:
    code_text = str(code or "")
    l1_code = code_text if code_text in L1_BY_CODE else f"{code_text.split('.')[0]}.0"
    l1 = L1_BY_CODE.get(l1_code)
    if l1 is None:
        return PROJECTOR_DID
    sub_code = subprocess_code or (code_text if code_text != str(l1.get("code")) else "")
    suffix = f":subprocess:{sub_code.replace('.', '-')}" if sub_code else ""
    return f"{PROJECTOR_DID}:apqc:{l1['slug']}{suffix}"


def _audit(caller_did: str) -> dict[str, Any]:
    did = caller_did or PROJECTOR_DID
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


# Register Pregel graph under the legacy v1 key so existing langgraph_loader
# deployments that look up "apqc.materializeSubprocesses.v1" still resolve.
_pregel_graph = _build_pregel_graph()
if _pregel_graph is not None:
    langgraph_registry.register("apqc.materializeSubprocesses.v1", _pregel_graph)
    langgraph_registry.register("apqc.pregel.v1", _pregel_graph)


async def task_apqc_materialize_subprocesses(
    apqcCode: str = "",
    subprocessCode: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if apqcCode not in L1_BY_CODE:
        return {"ok": False, "error": f"unknown apqcCode: {apqcCode}"}
    # Delegate to Pregel implementation; adapt single-code + subprocessCode args.
    result = await task_apqc_pregel_materialize(
        apqcCodes=apqcCode,
        dryRun=dryRun,
        callerDid=callerDid,
    )
    if not result.get("ok"):
        return result
    # Flatten to the legacy response shape expected by existing callers.
    l1_results = result.get("l1Results", [])
    subprocesses: list[dict[str, Any]] = []
    for r in l1_results:
        for code in r.get("subprocesses", []):
            if not subprocessCode or code == subprocessCode:
                subprocesses.append({
                    "apqcCode": apqcCode,
                    "subprocessCode": code,
                    "did": apqc_did(apqcCode, code),
                    "status": "materialized",
                })
    return {
        "ok": True,
        "apqcCode": apqcCode,
        "materialized": len(subprocesses),
        "subprocesses": subprocesses,
        "dryRun": dryRun,
        "callerDid": callerDid or PROJECTOR_DID,
    }


async def task_apqc_emit_event(
    apqcCode: str = "",
    taskId: str = "",
    eventType: str = "",
    caseId: str = "",
    objects: Any = None,
    attributes: Any = None,
    actorDid: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if not apqcCode or not eventType:
        return {"ok": False, "error": "apqcCode and eventType required"}
    l1 = L1_BY_CODE.get(apqcCode.split(".")[0] + ".0") or L1_BY_CODE.get(apqcCode)
    event_id = f"ocel-{_digest(apqcCode, taskId, eventType, caseId, _now_iso())}"
    vertex_id = f"at://{PROJECTOR_DID}/com.etzhayyim.apps.apqc.apqcEvent/{event_id}"
    _insert("vertex_apqc_event", {
        "vertex_id": vertex_id,
        "rkey": event_id,
        "repo": actorDid or apqc_did(apqcCode),
        "ocel_event_id": event_id,
        "apqc_code": apqcCode,
        "apqc_l1_name": (l1 or {}).get("name", ""),
        "task_id": taskId or None,
        "event_type": eventType,
        "case_id": caseId or None,
        "objects_json": json.dumps(objects or [], ensure_ascii=False),
        "attributes_json": json.dumps(attributes or {}, ensure_ascii=False),
        "timestamp": _now_iso(),
        **_audit(callerDid or actorDid or PROJECTOR_DID),
    }, dry_run=dryRun)
    return {
        "ok": True,
        "vertexId": vertex_id,
        "ocelEventId": event_id,
        "apqcCode": apqcCode,
        "eventType": eventType,
        "actorDid": actorDid or apqc_did(apqcCode),
    }


async def task_apqc_coverage_snapshot(**_: Any) -> dict[str, Any]:
    result = await task_apqc_pregel_coverage()
    return {
        **result,
        "registeredL1": len(APQC_L1),
        "totalL1": len(APQC_L1),
        "registeredSubProcesses": 183,
        "totalSubProcesses": 183,
        "runtime": "langserver-langgraph-pregel",
        "standaloneWasm": "retired",
    }

