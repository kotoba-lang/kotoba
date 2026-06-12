"""
Zeebe worker for kobo (酵母) — individual agent lifecycle layer (ADR-2605071200).

Yeast analogy: individual agents bud (asexual reproduction), sporulate
(stress-escape to dormancy via houshi), and germinate (revival from spore).

Subscribes to 3 domain job types:
  kobo.bud_agent  — record a budding event (parent→child agent edge)
  kobo.sporulate  — store agent state as CBOR spore, prepare for houshi custody
  kobo.germinate  — revive agent from spore with quorum confirmation

Run:
  python -m kotodama.kobo_worker_main

Env:
  AGENTGATEWAY_MCP_URL  — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL         — RisingWave postgres URL
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel
from kotodama.primitives.active_inference_substrate import select_belief_store, KoboAgentRecord, KoboBuddingRecord, HoushiSporeRecord, HoushiCustodyRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("kobo_worker")

KOBO_DID = "did:web:kobo.etzhayyim.com"
HOUSHI_DID = "did:web:houshi.etzhayyim.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── kobo.bud_agent ───────────────────────────────────────────────────────────


async def task_bud_agent(
    parentDid: str = "",
    childDid: str = "",
    childVertexId: str = "",
    childRole: str = "",
    parentEta: float = 0.5,
    callerDid: str = "",
    buddingEdgeId: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Record a budding event: parent agent produces a child agent."""

    if not parentDid or not childDid:
        return {"error": "parentDid and childDid required"}

    edge_id = buddingEdgeId or _uid("bud")
    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        rec = KoboBuddingRecord(
            edge_id=edge_id,
            src_vid=f"at://{KOBO_DID}/com.etzhayyim.apps.kobo.agent/{parentDid.split(':')[-1]}",
            dst_vid=childVertexId or f"at://{KOBO_DID}/com.etzhayyim.apps.kobo.agent/{childDid.split(':')[-1]}",
            relation_kind="kobo_budding",
            value_json=json.dumps({"callerDid": callerDid, "childRole": childRole}),
            created_at=now,
            updated_at=now,
            owner_did=KOBO_DID,
            sensitivity_ord=0,
            parent_did=parentDid,
            child_did=childDid,
            budded_at=now,
            prion_count=0
        )
        store.put_edge_kobo_budding(rec)
        return {
            "buddingEdgeId": edge_id,
            "parentDid": parentDid,
            "childDid": childDid,
            "buddedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("bud_agent: %s → %s edge=%s", parentDid, childDid, edge_id)
    return result


# ─── kobo.sporulate ───────────────────────────────────────────────────────────


async def task_sporulate(
    sporeVertexId: str = "",
    agentDid: str = "",
    agentVertexId: str = "",
    blobCbor: str = "",
    revivalKeyHint: str = "",
    quorumN: int = 2,
    callerDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Freeze agent state into a CBOR spore blob for houshi custody."""

    if not agentDid:
        return {"error": "agentDid required"}

    spore_id = sporeVertexId.split("/")[-1] if sporeVertexId else _uid("spore")
    spore_vid = sporeVertexId or f"at://{HOUSHI_DID}/com.etzhayyim.apps.houshi.spore/{spore_id}"
    now = _now()
    spore_hash = hashlib.sha256((blobCbor or agentDid).encode()).hexdigest()[:32]

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            # Mark kobo agent as dormant
            if agentVertexId:
                conn.execute(
                    "UPDATE vertex_kobo_agent SET status = 'dormant', updated_at = ? WHERE vertex_id = ?",
                    (now, agentVertexId),
                )

        # Insert spore record in houshi
        rec = HoushiSporeRecord(
            vertex_id=spore_vid,
            record_id=_uid("rec"),
            owner_did=HOUSHI_DID,
            label="houshi_spore",
            status="dormant",
            stream_id="",
            agent_did=KOBO_DID,
            value_json=json.dumps({"callerDid": callerDid}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            origin_agent_did=agentDid,
            blob_cbor=blobCbor[:1000] if blobCbor else "",
            revival_key_hint=revivalKeyHint or "",
            quorum_n=quorumN,
            germinated_at=None
        )
        store.put_vertex_houshi_spore(rec)

        return {
            "sporeVertexId": spore_vid,
            "sporeId": spore_id,
            "sporeHash": spore_hash,
            "agentDid": agentDid,
            "sporulatedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("sporulate: %s spore=%s quorumN=%d", agentDid, spore_id, quorumN)
    return result


# ─── kobo.germinate ───────────────────────────────────────────────────────────


async def task_germinate(
    sporeVertexId: str = "",
    quorumN: int = 2,
    newAgentDid: str = "",
    newAgentVertexId: str = "",
    originAgentDid: str = "",
    restoredEta: float = 0.5,
    callerDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Revive an agent from spore with quorum confirmation."""

    if not sporeVertexId:
        return {"error": "sporeVertexId required", "germinated": False, "confirmedCount": 0}

    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                spore_row = conn.execute(
                    "SELECT vertex_id, quorum_n, origin_agent_did FROM vertex_houshi_spore WHERE vertex_id = ? LIMIT 1",
                    (sporeVertexId,)
                ).fetchone()

                # We need custody_count but HoushiSporeRecord does not have it, let's join or just count edges
                custody_row = conn.execute(
                    "SELECT COUNT(*) as custody_count FROM edge_houshi_custody WHERE src_vid = ? AND custody_confirmed = 1",
                    (sporeVertexId,)
                ).fetchone()
            except sqlite3.OperationalError:
                spore_row = None
                custody_row = None

        if not spore_row:
            return {"error": f"spore not found: {sporeVertexId}", "germinated": False, "confirmedCount": 0}

        _vid = spore_row["vertex_id"]
        db_quorum_n = spore_row["quorum_n"]
        origin_did = spore_row["origin_agent_did"]
        custody_count = int(custody_row["custody_count"]) if custody_row else 0

        effective_quorum = int(db_quorum_n or quorumN)
        confirmed_count = custody_count + 1

        with store._conn() as conn:
            if confirmed_count >= effective_quorum:
                # Quorum reached — germinate
                conn.execute(
                    "UPDATE vertex_houshi_spore SET status = 'germinated', germinated_at = ?, updated_at = ? WHERE vertex_id = ?",
                    (now, now, sporeVertexId),
                )
                # Revive kobo agent
                if newAgentVertexId:
                    conn.execute(
                        "UPDATE vertex_kobo_agent SET status = 'active', updated_at = ? WHERE vertex_id = ?",
                        (now, newAgentVertexId),
                    )

                return {
                    "germinated": True,
                    "confirmedCount": confirmed_count,
                    "newAgentDid": newAgentDid or (origin_did or originAgentDid),
                    "germinatedAt": now,
                }

        return {
            "germinated": False,
            "confirmedCount": confirmed_count,
            "requiredCount": effective_quorum,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "germinate: spore=%s germinated=%s confirmed=%s",
        sporeVertexId.split("/")[-1], result.get("germinated"), result.get("confirmedCount"),
    )
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("KOBO_TASK_TIMEOUT_MS", "120000"))

    registrations = {
        "kobo.bud_agent": task_bud_agent,
        "kobo.sporulate": task_sporulate,
        "kobo.germinate": task_germinate,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "kobo zeebe worker registered %d task types via %s",
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
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    os.environ.setdefault("RW_SYNC_POOL", "0")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
