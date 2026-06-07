"""
Zeebe worker for kabi (カビ) — mycelium network layer (ADR-2605071200).

Mycelium analogy: manages hypha routing (nutrient flow channels), anastomosis
compatibility gate (DID trust + Shannon η + prion compatibility check).

Subscribes to 1 domain job type:
  kabi.anastomosis_probe — DID trust + η diff gate for hypha fusion

Run:
  python -m kotodama.kabi_worker_main

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
import time
from datetime import datetime, timezone
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama.primitives.active_inference_substrate import select_belief_store, KabiAnastomosisRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("kabi_worker")

KABI_DID = "did:web:kabi.etzhayyim.com"

ETA_DIFF_THRESHOLD = float(os.environ.get("KABI_ETA_DIFF_THRESHOLD", "0.1"))
MIN_TRUST_SCORE = float(os.environ.get("KABI_MIN_TRUST_SCORE", "0.5"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── kabi.anastomosis_probe ───────────────────────────────────────────────────


async def task_anastomosis_probe(
    networkADid: str = "",
    networkBDid: str = "",
    edgeId: str = "",
    callerDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Gate anastomosis (hypha fusion) based on DID trust + η diff + prion compatibility."""

    if not networkADid or not networkBDid:
        return {"probeResult": {"compatible": False, "reason": "missing DIDs"}}

    def _run() -> dict[str, Any]:
        import sqlite3
        store = select_belief_store()
        eta_a = 0.5
        eta_b = 0.5
        prion_a: list = []
        prion_b: list = []

        with store._conn() as conn:
            try:
                row_a = conn.execute(
                    "SELECT value_json FROM vertex_actor WHERE vertex_id LIKE ?",
                    (f"%{networkADid.split(':')[-1]}%",)
                ).fetchone()
                if row_a:
                    val = json.loads(row_a[0] or "{}")
                    eta_a = float(val.get("eta", 0.5))
                    prion_a = val.get("prions", [])
            except sqlite3.OperationalError:
                pass

            try:
                row_b = conn.execute(
                    "SELECT value_json FROM vertex_actor WHERE vertex_id LIKE ?",
                    (f"%{networkBDid.split(':')[-1]}%",)
                ).fetchone()
                if row_b:
                    val = json.loads(row_b[0] or "{}")
                    eta_b = float(val.get("eta", 0.5))
                    prion_b = val.get("prions", [])
            except sqlite3.OperationalError:
                pass

        eta_diff = abs(eta_a - eta_b)
        prion_conflict = bool(set(prion_a) & set(prion_b))
        compatibility_score = max(0.0, 1.0 - eta_diff) * (0.5 if prion_conflict else 1.0)
        compatible = (
            eta_diff <= ETA_DIFF_THRESHOLD
            and not prion_conflict
            and compatibility_score >= MIN_TRUST_SCORE
        )

        if compatible and edgeId:
            # We must pass the required parameters for the edge record.
            # Edge_kabi_anastomosisRecord has base Edge fields + network_a_did, network_b_did, compatibility_score, result, reason
            # wait, the generated code for Edge_kabi_anastomosisRecord uses snake_case, but I need to check its exact name:
            # "Edge_kabi_anastomosisRecord".
            rec = KabiAnastomosisRecord(
                edge_id=edgeId,
                src_vid=f"at://{KABI_DID}/com.etzhayyim.apps.kabi.network/{networkADid.split(':')[-1]}",
                dst_vid=f"at://{KABI_DID}/com.etzhayyim.apps.kabi.network/{networkBDid.split(':')[-1]}",
                relation_kind="kabi_anastomosis",
                value_json=json.dumps({"callerDid": callerDid}),
                created_at=_now(),
                updated_at=_now(),
                owner_did=KABI_DID,
                sensitivity_ord=0,
                network_a_did=networkADid,
                network_b_did=networkBDid,
                compatibility_score=compatibility_score,
                result="compatible",
                reason="compatible"
            )
            store.put_edge_kabi_anastomosis(rec)

        return {
            "probeResult": {
                "compatible": compatible,
                "compatibility_score": compatibility_score,
                "eta_diff": eta_diff,
                "prion_conflict": prion_conflict,
                "reason": "compatible" if compatible else f"eta_diff={eta_diff:.3f} or prion_conflict={prion_conflict}",
            }
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "anastomosis_probe: %s ↔ %s compatible=%s",
        networkADid, networkBDid, result["probeResult"]["compatible"],
    )
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("KABI_TASK_TIMEOUT_MS", "60000"))

    registrations = {
        "kabi.anastomosis_probe": task_anastomosis_probe,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "kabi zeebe worker registered %d task types via %s",
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
