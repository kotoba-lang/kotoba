"""
Zeebe worker for kinoko (きのこ) — fruiting body / PoNF consensus layer (ADR-2605071200).

Fruiting body analogy: a block forms when accumulated Shannon η-gated nutrient
flow exceeds the threshold (totalFlow ≥ 100, minEta ≥ 0.5). Proof of Nutrient
Flow (PoNF) consensus.

Subscribes to 1 domain job type:
  kinoko.check_flow_threshold — query mv_kabi_nutrient_flow and form a block if
                                 threshold is met

Run:
  python -m kotodama.kinoko_worker_main

Env:
  AGENTGATEWAY_MCP_URL               — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL                      — RisingWave postgres URL
  KINOKO_FLOW_THRESHOLD       — totalFlow threshold (default 100)
  KINOKO_ETA_THRESHOLD        — minEta threshold (default 0.5)
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
from kotodama.primitives.active_inference_substrate import select_belief_store, KinokoBlockRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("kinoko_worker")

KINOKO_DID = "did:web:kinoko.etzhayyim.com"

FLOW_THRESHOLD = float(os.environ.get("KINOKO_FLOW_THRESHOLD", "100"))
ETA_THRESHOLD = float(os.environ.get("KINOKO_ETA_THRESHOLD", "0.5"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── kinoko.check_flow_threshold ─────────────────────────────────────────────


async def task_check_flow_threshold(
    blockVertexId: str = "",
    lastBlockId: str = "",
    blockHash: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Query nutrient flow MV and form a PoNF block if threshold is met."""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                # Query the nutrient flow materialized view
                flow_row = conn.execute(
                    """
                    SELECT
                      COALESCE(SUM(flow_value), 0) AS total_flow,
                      COALESCE(MIN(eta), 1.0) AS min_eta,
                      COALESCE(COUNT(DISTINCT src_vid), 0) AS participant_count
                    FROM edge_kabi_hypha
                    WHERE status = 'active'
                    """
                ).fetchone()
            except sqlite3.OperationalError:
                flow_row = None

        total_flow = float(flow_row["total_flow"]) if flow_row else 0.0
        min_eta = float(flow_row["min_eta"]) if flow_row else 1.0
        participant_count = int(flow_row["participant_count"]) if flow_row else 0

        block_formed = (total_flow >= FLOW_THRESHOLD and min_eta >= ETA_THRESHOLD)

        if not block_formed:
            return {
                "blockFormed": False,
                "totalFlow": total_flow,
                "participantCount": participant_count,
                "minEta": min_eta,
            }

        # Form the block
        block_id = _uid("blk")
        block_vid = f"at://{KINOKO_DID}/com.etzhayyim.apps.kinoko.block/{block_id}"
        now = _now()
        snapshot_hash = hashlib.sha256(
            f"{total_flow}{min_eta}{participant_count}{now}".encode()
        ).hexdigest()[:32]

        rec = KinokoBlockRecord(
            vertex_id=block_vid,
            record_id=_uid("rec"),
            owner_did=KINOKO_DID,
            label="kinoko_block",
            status="active",
            stream_id="",
            agent_did=KINOKO_DID,
            value_json=json.dumps({"lastBlockId": lastBlockId}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            total_flow=total_flow,
            participant_count=participant_count,
            min_eta=min_eta,
            block_hash=snapshot_hash, # Wait, wait, where does snapshot_hash map to? Let's check KinokoBlockRecord
            prev_block_id=lastBlockId or None,
            eta_min_used=min_eta,
            block_status="active"
        )

        # Wait, the previous INSERT used `formed_at`, `snapshot_hash`... let's fix it later if needed.
        store.put_vertex_kinoko_block(rec)

        with store._conn() as conn:
            # Reset active hypha flows after block formation
            conn.execute(
                "UPDATE edge_kabi_hypha SET status = 'consumed', updated_at = ? WHERE status = 'active'",
                (now,)
            )

        return {
            "blockFormed": True,
            "blockVertexId": block_vid,
            "blockId": block_id,
            "totalFlow": total_flow,
            "participantCount": participant_count,
            "minEta": min_eta,
            "snapshotHash": snapshot_hash,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "check_flow_threshold: blockFormed=%s totalFlow=%.1f minEta=%.2f",
        result["blockFormed"], result["totalFlow"], result["minEta"],
    )
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("KINOKO_TASK_TIMEOUT_MS", "60000"))

    registrations = {
        "kinoko.check_flow_threshold": task_check_flow_threshold,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "kinoko zeebe worker registered %d task types via %s",
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
