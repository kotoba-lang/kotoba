"""
Zeebe worker for the graph-sos-intel actor (ADR-2605071700).

Subscribes to 6 BPMN job types:
  com.etzhayyim.apps.graphSosIntel.inventoryCatalog  – R/PT15M: snapshot kotoba Datom log topology
  com.etzhayyim.apps.graphSosIntel.writeSnapshot     – persist snapshot + relation rows
  com.etzhayyim.apps.graphSosIntel.detectFindings    – compare snapshots, emit findings
  com.etzhayyim.apps.graphSosIntel.queryLatestSnapshot – fetch latest snapshot for briefing
  com.etzhayyim.apps.graphSosIntel.generateBriefing  – LLM-driven briefing text
  com.etzhayyim.apps.graphSosIntel.writeFinding      – persist finding row

Run:
  python -m kotodama.graph_sos_intel_worker_main

Env:
  AGENTGATEWAY_MCP_URL    — LangServer AgentGateway URL (default 127.0.0.1:8080)
  KOTOBA_URL           — kotoba Datom log client URL
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("graph_sos_intel_worker")

ACTOR_DID = "did:web:graph-sos-intel.etzhayyim.com"

# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str = "snap") -> str:
    import hashlib
    import time
    ts = str(time.time_ns())
    digest = hashlib.sha256(ts.encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── inventoryCatalog ─────────────────────────────────────────────────────


async def task_inventory_catalog(**_kwargs: Any) -> dict[str, Any]:
    """Query information_schema to build a topology catalog snapshot."""
    observed_at = _now()

    client = get_kotoba_client()
    # R0: Specific Datalog query needed for Datomic schema introspection (tables).
    # This Datalog is a placeholder and assumes a simplified Datomic schema.
    relations_raw = await asyncio.to_thread(
        client.q,
        """
        [:find ?schema ?name ?type ?insertable
         :where
           ;; Placeholder: Replace with Datalog to query Datomic schema for table-like entities.
           ;; For example, querying for all entity idents that represent 'tables'.
           ;; [?e :db/ident ?ident]
           ;; (str ?ident) ?ident-str
           ;; (re-find #"^db.part/user" ?ident-str) ; Example for user-defined schema parts
           ;; ... derive schema, name, type, insertable from Datomic's schema attributes
           [?e :db/ident ?ident]
           [(namespace ?ident) ?ns]
           [(name ?ident) ?n]
           [(str ?ns) ?schema]
           [(str ?n) ?name]
           ["BASE TABLE" ?type]
           ["YES" ?insertable]
           (not (re-find #"^db.sys" ?schema))
           (not (re-find #"^db.part" ?schema))
           (not (re-find #"^db.type" ?schema))
           (not (re-find #"^db.cardinality" ?schema))
           (not (re-find #"^db.unique" ?schema))
           (not (re-find #"^db.fn" ?schema))
           (not (re-find #"^db.install" ?schema))
           (not (re-find #"^fressian" ?schema))
           (not (re-find #"^datomic" ?schema))
           (not (re-find #"^rw_" ?name))
         ]
        """,
    )
    # Convert to list of tuples and sort to match original output shape and ordering
    relations = sorted([tuple(row) for row in relations_raw], key=lambda x: x[1])

    # R0: Specific Datalog query needed for Datomic schema introspection (indexes).
    # This Datalog is a placeholder as Datomic doesn't have a direct 'pg_indexes' equivalent.
    indexes_raw = await asyncio.to_thread(
        client.q,
        """
        [:find ?schema ?table ?index ?def
         :where
           ;; Placeholder: Replace with Datalog to query Datomic schema for index-like entities.
           ;; Datomic indexes are implicit or defined by attributes like :db/fulltext, :db/unique.
           ;; A custom Datalog query would be needed to extract 'index' information.
           [?e :db/ident ?ident]
           [(namespace ?ident) ?ns]
           [(name ?ident) ?n]
           [(str ?ns) ?schema]
           [(str ?n) ?table]
           ["placeholder-index" ?index] ; Placeholder for index name
           ["placeholder-def" ?def]     ; Placeholder for index definition
           (not (re-find #"^db.sys" ?schema))
           (not (re-find #"^db.part" ?schema))
           (not (re-find #"^db.type" ?schema))
           (not (re-find #"^db.cardinality" ?schema))
           (not (re-find #"^db.unique" ?schema))
           (not (re-find #"^db.fn" ?schema))
           (not (re-find #"^db.install" ?schema))
           (not (re-find #"^fressian" ?schema))
           (not (re-find #"^datomic" ?schema))
         ]
        """,
    )
    # Convert to list of tuples and sort to match original output shape and ordering
    indexes = sorted([tuple(row) for row in indexes_raw], key=lambda x: (x[1], x[2]))

    vertex_tables = [r for r in relations if r[1].startswith("vertex_")]
    edge_tables = [r for r in relations if r[1].startswith("edge_")]
    mv_tables = [r for r in relations if r[2] == "MATERIALIZED VIEW"]
    idx_count = len(indexes)

    LOG.info(
        "inventoryCatalog: %d vertex / %d edge / %d mv / %d idx",
        len(vertex_tables), len(edge_tables), len(mv_tables), idx_count,
    )

    return {
        "observedAt": observed_at,
        "relationTotal": len(relations),
        "vertexTableCount": len(vertex_tables),
        "edgeTableCount": len(edge_tables),
        "mvCount": len(mv_tables),
        "idxCount": idx_count,
        "relations": [
            {"schema": r[0], "name": r[1], "kind": r[2], "insertable": r[3]}
            for r in relations
        ],
        "indexes": [
            {"schema": r[0], "table": r[1], "name": r[2], "def": r[3]}
            for r in indexes
        ],
    }


# ─── writeSnapshot ────────────────────────────────────────────────────────


async def task_write_snapshot(
    observedAt: str = "",
    relationTotal: int = 0,
    vertexTableCount: int = 0,
    edgeTableCount: int = 0,
    mvCount: int = 0,
    idxCount: int = 0,
    relations: list | None = None,
    indexes: list | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Persist snapshot + relation/index inventory rows."""
    snapshot_id = _gen_id("snap")
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.graphSosIntel.snapshot/{snapshot_id}"
    created_at = _now()

    def _write() -> None:
        client = get_kotoba_client()
        client.insert_row(
            "vertex_graph_sos_intel_snapshot",
            {
                "vertex_id": vertex_id,
                "snapshot_id": snapshot_id,
                "actor_did": ACTOR_DID,
                "scope": "public",
                "status": "active",
                "relation_total": relationTotal,
                "vertex_table_count": vertexTableCount,
                "edge_table_count": edgeTableCount,
                "mv_count": mvCount,
                "idx_count": idxCount,
                "anomaly_count": 0,
                "stale_relation_count": 0,
                "heavy_ddl_pending_count": 0,
                "summary": f"Topology snapshot {snapshot_id}: {relationTotal} relations",
                "recommendation_json": json.dumps({}),
                "evidence_json": json.dumps({"observedAt": observedAt}),
                "created_at": created_at,
                "updated_at": created_at,
                "owner_did": ACTOR_DID,
                "org_id": "etzhayyim",
                "user_id": "graph-sos-intel",
                "actor_id": "gs0s1nt7",
                "sensitivity_ord": 0,
            },
        )

        if relations:
            for rel in relations[:500]:
                rel_vid = (
                    f"at://{ACTOR_DID}/com.etzhayyim.apps.graphSosIntel.relation"
                    f"/{snapshot_id}:{rel['name']}"
                )
                client.insert_row(
                    "vertex_graph_sos_relation_inventory",
                    {
                        "vertex_id": rel_vid,
                        "schema_name": rel.get("schema", "public"),
                        "relation_name": rel["name"],
                        "relation_kind": rel.get("kind", ""),
                        "table_type": rel.get("kind", ""),
                        "is_insertable_into": rel.get("insertable", "NO"),
                        "observed_at": observedAt,
                        "owner_did": ACTOR_DID,
                        "sensitivity_ord": 0,
                    },
                )

        if indexes:
            for idx in indexes[:500]:
                idx_vid = (
                    f"at://{ACTOR_DID}/com.etzhayyim.apps.graphSosIntel.index"
                    f"/{snapshot_id}:{idx['name']}"
                )
                client.insert_row(
                    "vertex_graph_sos_index_inventory",
                    {
                        "vertex_id": idx_vid,
                        "schema_name": idx.get("schema", "public"),
                        "table_name": idx.get("table", ""),
                        "index_name": idx["name"],
                        "index_def": idx.get("def", ""),
                        "observed_at": observedAt,
                        "owner_did": ACTOR_DID,
                        "sensitivity_ord": 0,
                    },
                )

    await asyncio.to_thread(_write)
    LOG.info("writeSnapshot: persisted %s", snapshot_id)
    return {"snapshotId": snapshot_id, "vertexId": vertex_id}


# ─── detectFindings ───────────────────────────────────────────────────────


async def task_detect_findings(
    snapshotId: str = "",
    vertexTableCount: int = 0,
    edgeTableCount: int = 0,
    mvCount: int = 0,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Compare with previous snapshot and emit findings for anomalies."""
    client = get_kotoba_client()
    # R0: Complex Datalog query with ORDER BY and 'not equal' condition.
    # This Datalog query needs to select the latest snapshot that is not the current one.
    # Assuming snapshot_id is unique and created_at can be used for ordering.
    prev_raw = await asyncio.to_thread(
        client.q,
        """
        [:find ?sid ?vtc ?etc ?mvc
         :where
           [?e :vertex_graph_sos_intel_snapshot/snapshot_id ?sid]
           [?e :vertex_graph_sos_intel_snapshot/vertex_table_count ?vtc]
           [?e :vertex_graph_sos_intel_snapshot/edge_table_count ?etc]
           [?e :vertex_graph_sos_intel_snapshot/mv_count ?mvc]
           [?e :vertex_graph_sos_intel_snapshot/created_at ?created_at]
           (not= ?sid ?current-snapshot-id)
         :order-by desc ?created_at
         :limit 1
         ]
        """,
        args={"?current-snapshot-id": snapshotId}
    )
    prev = prev_raw[0] if prev_raw else None

    findings: list[dict[str, Any]] = []
    created_at = _now()

    def _check_delta(label: str, curr: int, prev_val: int, threshold: int = 5) -> None:
        delta = abs(curr - prev_val)
        if delta >= threshold:
            fid = _gen_id("fnd")
            findings.append({
                "finding_id": fid,
                "finding_kind": "table_count_delta",
                "severity": "warning" if delta < 20 else "critical",
                "affected_relation": label,
                "affected_relation_kind": "vertex_table" if "vertex" in label else label,
                "summary": f"{label} count changed by {delta} (prev={prev_val}, curr={curr})",
                "evidence_json": json.dumps({"prev": prev_val, "curr": curr, "delta": delta}),
                "recommendation": "Investigate DDL migration backlog",
                "recommended_action_kind": "investigate",
            })

    if prev:
        _, prev_v, prev_e, prev_m = prev
        _check_delta("vertex_table", vertexTableCount, prev_v or 0)
        _check_delta("edge_table", edgeTableCount, prev_e or 0)
        _check_delta("materialized_view", mvCount, prev_m or 0)

    if findings:
        def _write_findings() -> None:
            client = get_kotoba_client()
            for f in findings:
                fid = f["finding_id"]
                vid = f"at://{ACTOR_DID}/com.etzhayyim.apps.graphSosIntel.finding/{fid}"
                client.insert_row(
                    "vertex_graph_sos_intel_finding",
                    {
                        "vertex_id": vid,
                        "finding_id": fid,
                        "actor_did": ACTOR_DID,
                        "finding_kind": f["finding_kind"],
                        "severity": f["severity"],
                        "status": "open",
                        "affected_relation": f["affected_relation"],
                        "affected_relation_kind": f["affected_relation_kind"],
                        "summary": f["summary"],
                        "evidence_json": f["evidence_json"],
                        "recommendation": f["recommendation"],
                        "recommended_action_kind": f["recommended_action_kind"],
                        "ddl_request_ref": snapshotId,
                        "created_at": created_at,
                        "updated_at": created_at,
                        "owner_did": ACTOR_DID,
                        "org_id": "etzhayyim",
                        "user_id": "graph-sos-intel",
                        "actor_id": "gs0s1nt7",
                        "sensitivity_ord": 0,
                    },
                )

        await asyncio.to_thread(_write_findings)

    LOG.info("detectFindings: %d finding(s) for snapshot %s", len(findings), snapshotId)
    return {"findingCount": len(findings), "findings": [f["finding_id"] for f in findings]}


# ─── queryLatestSnapshot ──────────────────────────────────────────────────


async def task_query_latest_snapshot(**_kwargs: Any) -> dict[str, Any]:
    """Return the most recent snapshot for the briefing task."""
    client = get_kotoba_client()
    # R0: Complex Datalog query with ORDER BY and LIMIT.
    row_raw = await asyncio.to_thread(
        client.q,
        """
        [:find ?sid ?rt ?vtc ?etc ?mvc ?ic ?ac ?cat
         :where
           [?e :vertex_graph_sos_intel_snapshot/snapshot_id ?sid]
           [?e :vertex_graph_sos_intel_snapshot/relation_total ?rt]
           [?e :vertex_graph_sos_intel_snapshot/vertex_table_count ?vtc]
           [?e :vertex_graph_sos_intel_snapshot/edge_table_count ?etc]
           [?e :vertex_graph_sos_intel_snapshot/mv_count ?mvc]
           [?e :vertex_graph_sos_intel_snapshot/idx_count ?ic]
           [?e :vertex_graph_sos_intel_snapshot/anomaly_count ?ac]
           [?e :vertex_graph_sos_intel_snapshot/created_at ?cat]
         :order-by desc ?cat
         :limit 1
         ]
        """,
    )
    row = row_raw[0] if row_raw else None
    if not row:
        return {"snapshotFound": False}

    sid, rt, vtc, etc, mvc, ic, ac, cat = row
    return {
        "snapshotFound": True,
        "snapshotId": sid,
        "relationTotal": rt,
        "vertexTableCount": vtc,
        "edgeTableCount": etc,
        "mvCount": mvc,
        "idxCount": ic,
        "anomalyCount": ac,
        "snapshotCreatedAt": str(cat),
    }


# ─── generateBriefing ─────────────────────────────────────────────────────


async def task_generate_briefing(
    snapshotFound: bool = False,
    snapshotId: str = "",
    relationTotal: int = 0,
    vertexTableCount: int = 0,
    edgeTableCount: int = 0,
    mvCount: int = 0,
    idxCount: int = 0,
    anomalyCount: int = 0,
    snapshotCreatedAt: str = "",
    **_kwargs: Any,
) -> dict[str, Any]:
    """LLM-driven briefing summarizing the latest topology snapshot."""
    from kotodama import llm

    if not snapshotFound:
        return {
            "briefingText": "No topology snapshot available yet.",
            "severity": "info",
        }

    user_prompt = (
        f"Graph SoS Intel topology briefing — snapshot {snapshotId} @ {snapshotCreatedAt}.\n"
        f"Stats: {relationTotal} relations total "
        f"({vertexTableCount} vertex tables, {edgeTableCount} edge tables, "
        f"{mvCount} MVs, {idxCount} indexes). "
        f"Anomalies detected: {anomalyCount}.\n"
        "Write a concise 3-sentence operational briefing for a system reliability engineer. "
        "Include the counts, highlight any anomaly count > 0, and recommend next action if needed."
    )

    result = await asyncio.to_thread(
        llm.call_tier,
        "fast",
        "You are a graph database observability assistant. Respond in plain English.",
        user_prompt,
        max_tokens=200,
    )

    briefing_text = (result.get("content") or "").strip()
    severity = "warning" if anomalyCount > 0 else "info"

    LOG.info("generateBriefing: snapshot=%s anomalies=%d", snapshotId, anomalyCount)
    return {
        "briefingText": briefing_text,
        "severity": severity,
        "snapshotId": snapshotId,
    }


# ─── writeFinding ─────────────────────────────────────────────────────────


async def task_write_finding(
    briefingText: str = "",
    severity: str = "info",
    snapshotId: str = "",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Persist a briefing-derived finding row."""
    if not briefingText:
        return {"written": False, "reason": "empty briefing"}

    fid = _gen_id("fnd")
    vid = f"at://{ACTOR_DID}/com.etzhayyim.apps.graphSosIntel.finding/{fid}"
    created_at = _now()

    def _write() -> None:
        client = get_kotoba_client()
        client.insert_row(
            "vertex_graph_sos_intel_finding",
            {
                "vertex_id": vid,
                "finding_id": fid,
                "actor_did": ACTOR_DID,
                "finding_kind": "briefing",
                "severity": severity,
                "status": "open",
                "affected_relation": "graph_topology",
                "affected_relation_kind": "snapshot",
                "summary": briefingText[:1000],
                "evidence_json": json.dumps({"snapshotId": snapshotId}),
                "recommendation": "Review latest snapshot findings",
                "recommended_action_kind": "review",
                "ddl_request_ref": snapshotId,
                "created_at": created_at,
                "updated_at": created_at,
                "owner_did": ACTOR_DID,
                "org_id": "etzhayyim",
                "user_id": "graph-sos-intel",
                "actor_id": "gs0s1nt7",
                "sensitivity_ord": 0,
            },
        )

    await asyncio.to_thread(_write)
    LOG.info("writeFinding: %s (severity=%s)", fid, severity)
    return {"written": True, "findingId": fid, "vertexId": vid}


# ─── worker entrypoint ────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("GRAPH_SOS_INTEL_TASK_TIMEOUT_MS", "120000"))

    registrations = {
        "com.etzhayyim.apps.graphSosIntel.inventoryCatalog": task_inventory_catalog,
        "com.etzhayyim.apps.graphSosIntel.writeSnapshot": task_write_snapshot,
        "com.etzhayyim.apps.graphSosIntel.detectFindings": task_detect_findings,
        "com.etzhayyim.apps.graphSosIntel.queryLatestSnapshot": task_query_latest_snapshot,
        "com.etzhayyim.apps.graphSosIntel.generateBriefing": task_generate_briefing,
        "com.etzhayyim.apps.graphSosIntel.writeFinding": task_write_finding,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "graph-sos-intel zeebe worker registered %d task types via %s",
        len(registrations), gateway,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    task = asyncio.create_task(worker.work())
    await stop.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    load_env_file()
    os.environ.setdefault("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
