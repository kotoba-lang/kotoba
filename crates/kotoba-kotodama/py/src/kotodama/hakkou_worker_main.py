"""
Zeebe worker for hakkou (発酵) — fermentation pipeline layer (ADR-2605071200).

Fermentation analogy: irreversible transformation of raw input into structured
knowledge (ethanol output). Write-only, no undo.

Subscribes to 3 domain job types:
  hakkou.create_ferment_record — insert vertex_hakkou_ferment (pending state)
  hakkou.llm_transform         — LLM-based transformation of raw input
  hakkou.finalize_ferment      — mark record completed, store ethanol hash

Run:
  python -m kotodama.hakkou_worker_main

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

from kotodama.primitives.active_inference_substrate import select_belief_store, HakkouFermentRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("hakkou_worker")

HAKKOU_DID = "did:web:hakkou.etzhayyim.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── hakkou.create_ferment_record ────────────────────────────────────────────


async def task_create_ferment_record(
    fermentVertexId: str = "",
    agentDid: str = "",
    inputKind: str = "text",
    inputRef: str = "",
    outputKind: str = "insight",
    callerDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Insert vertex_hakkou_ferment row in 'pending' state."""

    ferment_id = fermentVertexId.split("/")[-1] if fermentVertexId else _uid("hak")
    ferment_vid = fermentVertexId or f"at://{HAKKOU_DID}/com.etzhayyim.apps.hakkou.ferment/{ferment_id}"
    now = _now()
    input_hash = hashlib.sha256(inputRef.encode()).hexdigest()[:32] if inputRef else ""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        rec = HakkouFermentRecord(
            vertex_id=ferment_vid,
            record_id=_uid("rec"),
            owner_did=HAKKOU_DID,
            label="hakkou_ferment",
            status="pending",
            stream_id="",
            agent_did=agentDid or HAKKOU_DID,
            value_json=json.dumps({"callerDid": callerDid, "inputRef": inputRef[:500]}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            input_kind=inputKind,
            input_ref=inputRef[:1000],
            output_kind=outputKind,
            input_hash=input_hash,
        )
        store.put_vertex_hakkou_ferment(rec)
        return {
            "fermentVertexId": ferment_vid,
            "fermentId": ferment_id,
            "status": "pending",
            "createdAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("create_ferment_record: %s kind=%s", ferment_id, inputKind)
    return result


# ─── hakkou.llm_transform ─────────────────────────────────────────────────────


async def task_llm_transform(
    inputKind: str = "text",
    inputRef: str = "",
    outputKind: str = "insight",
    **_: Any,
) -> dict[str, Any]:
    """LLM-based irreversible transformation of raw input into structured output."""

    from kotodama import llm

    system_prompt = (
        "You are hakkou — the fermentation layer of an artificial organism. "
        "Transform the raw input irreversibly into a structured knowledge artifact. "
        f"Output kind requested: {outputKind}. "
        "Respond in JSON with keys: title (string), summary (string), "
        "confidence (0.0-1.0), tags (array of strings), "
        "fermentedContent (string — the transformed output)."
    )

    llm_result = await asyncio.to_thread(
        llm.call_tier,
        "mid",
        system_prompt,
        f"Input kind: {inputKind}\n\n{inputRef[:2000]}",
        max_tokens=500,
    )

    raw = (llm_result.get("content") or "").strip()
    try:
        parsed = json.loads(raw)
        fermented = str(parsed.get("fermentedContent", raw[:300]))
        confidence = float(parsed.get("confidence", 0.5))
        tags = parsed.get("tags", [])
    except (json.JSONDecodeError, ValueError, TypeError):
        fermented = raw[:300]
        confidence = 0.5
        tags = []

    ethanol_hash = hashlib.sha256(fermented.encode()).hexdigest()[:32]
    return {
        "fermentOutput": {
            "content": fermented,
            "confidence": confidence,
            "tags": tags,
            "outputKind": outputKind,
        },
        "ethanolHash": ethanol_hash,
    }


# ─── hakkou.finalize_ferment ──────────────────────────────────────────────────


async def task_finalize_ferment(
    fermentVertexId: str = "",
    outputVertexId: str = "",
    ethanolHash: str = "",
    co2AuditRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Mark ferment record as completed with ethanol hash + output vertex ref."""

    if not fermentVertexId:
        return {"error": "fermentVertexId required"}

    now = _now()

    def _run() -> dict[str, Any]:
        import sqlite3
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM vertex_hakkou_ferment WHERE vertex_id = ?", (fermentVertexId,)).fetchone()
            if not row:
                raise ValueError("Ferment record not found")

            rec = HakkouFermentRecord(
                vertex_id=row["vertex_id"],
                record_id=row["record_id"],
                owner_did=row["owner_did"],
                label=row["label"],
                status="fermented",
                stream_id=row["stream_id"],
                agent_did=row["agent_did"],
                value_json=row["value_json"],
                created_at=row["created_at"],
                updated_at=now,
                sensitivity_ord=row["sensitivity_ord"],
                input_kind=row["input_kind"],
                input_ref=row["input_ref"],
                output_vertex_id=outputVertexId or "",
                output_kind=row["output_kind"],
                ethanol_hash=ethanolHash or "",
                co2_audit_ref=co2AuditRef or "",
            )
        store.put_vertex_hakkou_ferment(rec)

        return {
            "fermented": True,
            "fermentVertexId": fermentVertexId,
            "ethanolHash": ethanolHash,
            "fermentedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("finalize_ferment: %s ethanol=%s", fermentVertexId.split("/")[-1], ethanolHash[:8] if ethanolHash else "")
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("HAKKOU_TASK_TIMEOUT_MS", "180000"))

    registrations = {
        "hakkou.create_ferment_record": task_create_ferment_record,
        "hakkou.llm_transform": task_llm_transform,
        "hakkou.finalize_ferment": task_finalize_ferment,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "hakkou zeebe worker registered %d task types via %s",
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
