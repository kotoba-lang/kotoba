"""
Zeebe worker for ki (木) — vascular plant synthesis layer (ADR-2605072100).

Vascular plant analogy: xylem absorbs processed signals upward, phloem
distributes synthesized knowledge artifacts downward. Growth rings (年輪)
form versioned knowledge checkpoints. ki sits above hakkou in the organism
hierarchy, synthesizing fermented knowledge into durable artifacts.

Subscribes to 4 domain job types:
  ki.absorb     — scan for pending vertex_ki_absorb rows (no args) OR create a new
                  absorb row (with sourceVertexId/content); returns absorbStatus
  ki.synthesize — LLM-based structured synthesis into knowledge artifact
  ki.bloom      — publish synthesized artifact to graph (phloem output)
  ki.ring       — create versioned knowledge checkpoint (growth ring)

Run:
  python -m kotodama.ki_worker_main

Env:
  AGENTGATEWAY_MCP_URL         — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL                — RisingWave postgres URL
  KI_CONFIDENCE_CUTOFF  — min synthesis confidence to auto-bloom (default 0.6)
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
from kotodama.primitives.active_inference_substrate import select_belief_store, KiAbsorbRecord, KiArtifactRecord, KiRingRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("ki_worker")

KI_DID = "did:web:ki.etzhayyim.com"
HAKKOU_DID = "did:web:hakkou.etzhayyim.com"
KOKE_DID = "did:web:koke.etzhayyim.com"

CONFIDENCE_CUTOFF = float(os.environ.get("KI_CONFIDENCE_CUTOFF", "0.6"))


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── ki.absorb ────────────────────────────────────────────────────────────


async def task_absorb(
    sourceVertexId: str = "",
    inputKind: str = "text",
    content: str = "",
    agentDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Absorb a processed signal into ki vascular input (xylem).

    Scan mode (no args): queries vertex_ki_absorb for the oldest unprocessed row,
    returns {absorbId, status="absorbed"} or {absorbId="", status="empty"}.

    Create mode (sourceVertexId or content): inserts a new absorb row and returns it.
    """

    # ── scan mode: called by BPMN timer with no inputs ──
    if not sourceVertexId and not content:
        def _scan() -> dict[str, Any]:
            store = select_belief_store()
            with store._conn() as conn:
                conn.row_factory = sqlite3.Row
                try:
                    row = conn.execute(
                        """
                        SELECT vertex_id FROM vertex_ki_absorb
                        WHERE synthesized_at IS NULL
                        ORDER BY created_at ASC
                        LIMIT 1
                        """
                    ).fetchone()
                except sqlite3.OperationalError:
                    row = None
            if not row:
                return {"absorbId": "", "status": "empty"}
            vid = row["vertex_id"]
            absorb_id = vid.split("/")[-1]
            return {"absorbId": absorb_id, "absorbVertexId": vid, "status": "absorbed"}

        result = await asyncio.to_thread(_scan)
        LOG.info("absorb (scan): %s", result.get("absorbId") or "empty")
        return result

    # ── create mode: called externally with source data ──
    absorb_id = _uid("xyl")
    absorb_vid = f"at://{KI_DID}/com.etzhayyim.apps.ki.absorb/{absorb_id}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        rec = KiAbsorbRecord(
            vertex_id=absorb_vid,
            record_id=_uid("rec"),
            owner_did=KI_DID,
            label="ki_absorb",
            status="absorbed",
            stream_id="",
            agent_did=agentDid or KI_DID,
            value_json=json.dumps({"content": content[:500]}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            source_vertex_id=sourceVertexId,
            input_kind=inputKind,
            content_hash=content_hash,
            absorbed_at=now,
            synthesized_at=None
        )
        store.put_vertex_ki_absorb(rec)
        return {
            "absorbId": absorb_id,
            "absorbVertexId": absorb_vid,
            "contentHash": content_hash,
            "status": "absorbed",
            "absorbedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("absorb (create): %s hash=%s", absorb_id, content_hash)
    return result


# ─── ki.synthesize ────────────────────────────────────────────────────────


async def task_synthesize(
    absorbId: str = "",
    inputKind: str = "text",
    content: str = "",
    **_: Any,
) -> dict[str, Any]:
    """LangGraph 3-node synthesis pipeline (parse → synthesize → refine).

    Graph: ki.synthesize.v1 (kotodama.primitives.ki_synthesis_graph)
    Falls back to single-LLM call if LangGraph is unavailable.
    """

    if not absorbId and not content:
        return {"error": "absorbId or content required"}

    if absorbId and not content:
        def _get_content() -> tuple[Any, ...]:
            store = select_belief_store()
            with store._conn() as conn:
                conn.row_factory = sqlite3.Row
                try:
                    return conn.execute(
                        "SELECT value_json FROM vertex_ki_absorb WHERE vertex_id LIKE ? LIMIT 1",
                        (f"%{absorbId}%",)
                    ).fetchone()
                except sqlite3.OperationalError:
                    return None
        row = await asyncio.to_thread(_get_content)
        if row:
            try:
                val = json.loads(row["value_json"] or "{}")
                content = val.get("content", "")
            except (json.JSONDecodeError, TypeError):
                pass

    from kotodama.primitives import ki_synthesis_graph  # noqa: E402

    graph_result = await asyncio.to_thread(
        ki_synthesis_graph.synthesize,
        absorbId=absorbId,
        inputKind=inputKind,
        content=content,
    )

    if graph_result.get("error") and not graph_result.get("synthesis"):
        return {"error": graph_result["error"]}

    synthesis = graph_result.get("synthesis", "")
    confidence = float(graph_result.get("confidence", 0.5))
    artifact_kind = str(graph_result.get("artifactKind", "insight"))
    key_points = list(graph_result.get("keyPoints", []))
    refined = bool(graph_result.get("refined", False))

    artifact_id = _uid("art")
    artifact_vid = f"at://{KI_DID}/com.etzhayyim.apps.ki.artifact/{artifact_id}"
    artifact_hash = hashlib.sha256(synthesis.encode()).hexdigest()[:32]
    now = _now()

    def _write() -> None:
        store = select_belief_store()
        rec = KiArtifactRecord(
            vertex_id=artifact_vid,
            record_id=_uid("rec"),
            owner_did=KI_DID,
            label="ki_artifact",
            status="synthesized",
            stream_id="",
            agent_did=KI_DID,
            value_json=json.dumps({"keyPoints": key_points, "refined": refined}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            absorb_id=absorbId,
            artifact_kind=artifact_kind,
            synthesis=synthesis,
            confidence=confidence,
            artifact_hash=artifact_hash,
            bloomed_at=None
        )
        store.put_vertex_ki_artifact(rec)
        if absorbId:
            with store._conn() as conn:
                conn.execute(
                    "UPDATE vertex_ki_absorb SET status = 'synthesized', synthesized_at = ?, updated_at = ? WHERE vertex_id LIKE ?",
                    (now, now, f"%{absorbId}%")
                )

    await asyncio.to_thread(_write)
    LOG.info(
        "synthesize: %s kind=%s confidence=%.2f refined=%s",
        artifact_id, artifact_kind, confidence, refined,
    )
    # Phase D2 (ADR-2605082000): embed routing decision so ki v2 topology
    # uses field-based conditional edges, retiring _confidence_gate.
    # Mirrors ki_cycle._confidence_gate: bloom only if confidence ≥ cutoff.
    import os as _os
    _cutoff = float(_os.environ.get("KI_CONFIDENCE_CUTOFF", "0.6"))
    return {
        "artifactId": artifact_id,
        "artifactVertexId": artifact_vid,
        "synthesis": synthesis,
        "artifactKind": artifact_kind,
        "confidence": confidence,
        "refined": refined,
        "absorbId": absorbId,
        "nextRoute": "bloom" if confidence >= _cutoff else "skip_bloom",
    }


# ─── ki.bloom ─────────────────────────────────────────────────────────────


async def task_bloom(
    artifactId: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Publish synthesized knowledge artifact to the graph (phloem output)."""

    if not artifactId:
        return {"error": "artifactId required"}

    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT vertex_id, confidence FROM vertex_ki_artifact WHERE vertex_id LIKE ? AND status = 'synthesized' LIMIT 1",
                    (f"%{artifactId}%",)
                ).fetchone()
            except sqlite3.OperationalError:
                row = None

        if not row:
            return {"error": f"artifact not found or not synthesized: {artifactId}"}

        vid, confidence = row["vertex_id"], float(row["confidence"] or 0)
        if confidence < CONFIDENCE_CUTOFF:
            return {
                "bloomed": False,
                "artifactId": artifactId,
                "reason": f"confidence {confidence:.2f} below cutoff {CONFIDENCE_CUTOFF}",
            }

        with store._conn() as conn:
            conn.execute(
                "UPDATE vertex_ki_artifact SET status = 'bloomed', bloomed_at = ?, updated_at = ? WHERE vertex_id = ?",
                (now, now, vid)
            )
        return {
            "bloomed": True,
            "artifactId": artifactId,
            "publishedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("bloom: %s bloomed=%s", artifactId, result.get("bloomed"))
    return result


# ─── ki.ring ──────────────────────────────────────────────────────────────


async def task_ring(
    period: str = "P1D",
    **_: Any,
) -> dict[str, Any]:
    """Create versioned knowledge checkpoint (growth ring / 年輪 analogy)."""

    ring_id = _uid("ring")
    ring_vid = f"at://{KI_DID}/com.etzhayyim.apps.ki.ring/{ring_id}"
    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                count_row = conn.execute(
                    "SELECT COUNT(*) as count FROM vertex_ki_artifact WHERE status = 'bloomed'"
                ).fetchone()
            except sqlite3.OperationalError:
                count_row = None

        snapshot_count = int(count_row["count"]) if count_row else 0

        rec = KiRingRecord(
            vertex_id=ring_vid,
            record_id=_uid("rec"),
            owner_did=KI_DID,
            label="ki_ring",
            status="active",
            stream_id="",
            agent_did=KI_DID,
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            period=period,
            snapshot_count=snapshot_count,
            ring_at=now
        )
        store.put_vertex_ki_ring(rec)
        return {
            "ringId": ring_id,
            "ringVertexId": ring_vid,
            "period": period,
            "snapshotCount": snapshot_count,
            "ringAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("ring: %s period=%s snapshots=%d", ring_id, period, result["snapshotCount"])
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("KI_TASK_TIMEOUT_MS", "180000"))

    registrations = {
        "ki.absorb": task_absorb,
        "ki.synthesize": task_synthesize,
        "ki.bloom": task_bloom,
        "ki.ring": task_ring,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "ki zeebe worker registered %d task types via %s",
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
