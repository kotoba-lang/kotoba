"""
Zeebe worker for saikin (細菌) — bacteria horizontal transfer layer (ADR-2605072000).

Horizontal gene transfer (HGT) analogy: cross-actor signal propagation across
otherwise disconnected actor clusters. saikin probes the environment for novel
signals, transfers them horizontally to target actors, and forms cooperative
colonies of related signals.

Subscribes to 5 domain job types:
  saikin.probe_environment  — scan external sources for novel signals
  saikin.transfer_signal    — HGT-style copy of signal to target actor namespace
  saikin.form_colony        — group related signals into a cooperative colony
  saikin.lyse               — decompose and release a processed signal
  saikin.handoff_to_ki      — bridge saikin→ki: seed vertex_ki_absorb from a colony

Run:
  python -m kotodama.saikin_worker_main

Env:
  AGENTGATEWAY_MCP_URL     — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL            — RisingWave postgres URL
  SAIKIN_BATCH_SIZE — max signals per probe cycle (default 10)
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
from kotodama.primitives.active_inference_substrate import select_belief_store, SaikinSignalRecord, SaikinTransferRecord, SaikinColonyRecord, SaikinMemberRecord, KiAbsorbRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("saikin_worker")

SAIKIN_DID = "did:web:saikin.etzhayyim.com"
KOKE_DID = "did:web:koke.etzhayyim.com"
KI_DID = "did:web:ki.etzhayyim.com"

BATCH_SIZE = int(os.environ.get("SAIKIN_BATCH_SIZE", "10"))


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── saikin.probe_environment ─────────────────────────────────────────────


async def task_probe_environment(**_: Any) -> dict[str, Any]:
    """Probe environment for novel signals not yet in koke fixation."""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    f"""
                    SELECT vertex_id, signal_hash, input_kind, raw_ref
                    FROM vertex_saikin_signal
                    WHERE status = 'unprocessed'
                    ORDER BY created_at ASC
                    LIMIT {int(BATCH_SIZE)}
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        signals = [
            {
                "signalId": r["vertex_id"].split("/")[-1],
                "vertexId": r["vertex_id"],
                "signalHash": r["signal_hash"] or "",
                "inputKind": r["input_kind"] or "text",
                "rawRef": r["raw_ref"] or "",
            }
            for r in (rows or [])
        ]
        return {"signalCount": len(signals), "signals": signals}

    result = await asyncio.to_thread(_run)
    # Phase D2 (ADR-2605082000): embed routing decision so the topology can
    # use field-based conditional edges instead of a Python router callable.
    # Mirrors saikin_cycle._has_signals_gate exactly.
    result["nextRoute"] = "transfer" if int(result.get("signalCount") or 0) > 0 else "no_signals"
    LOG.info("probe_environment: found %d unprocessed signals", result["signalCount"])
    return result


# ─── saikin.transfer_signal ───────────────────────────────────────────────


async def task_transfer_signal(
    signalId: str = "",
    targetActorDid: str = "",
    signals: list[dict[str, Any]] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """HGT-style horizontal transfer of a signal to a target actor namespace."""

    if not signalId and not (signals and len(signals) > 0):
        return {"error": "signalId or signals required"}

    if signals:
        sig = signals[0]
        signal_id = sig.get("signalId", "")
        raw_ref = sig.get("rawRef", "")
        input_kind = sig.get("inputKind", "text")
        target_did = targetActorDid or KOKE_DID
    else:
        signal_id = signalId
        raw_ref = ""
        input_kind = "text"
        target_did = targetActorDid or KOKE_DID

    transfer_id = _uid("hgt")
    now = _now()
    signal_hash = hashlib.sha256(raw_ref.encode()).hexdigest()[:32] if raw_ref else ""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        rec = SaikinTransferRecord(
            edge_id=transfer_id,
            src_vid=f"at://{SAIKIN_DID}/com.etzhayyim.apps.saikin.signal/{signal_id}",
            dst_vid=f"at://{target_did}/",
            relation_kind="saikin_transfer",
            value_json=json.dumps({"inputKind": input_kind, "signalHash": signal_hash}),
            created_at=now,
            updated_at=now,
            owner_did=SAIKIN_DID,
            sensitivity_ord=0,
            signal_id=signal_id,
            target_actor_did=target_did,
            transfer_kind="horizontal",
            transferred_at=now
        )
        store.put_edge_saikin_transfer(rec)

        if signal_id:
            with store._conn() as conn:
                conn.execute(
                    "UPDATE vertex_saikin_signal SET status = 'transferred', updated_at = ? WHERE vertex_id LIKE ?",
                    (now, f"%{signal_id}%"),
                )
        return {
            "transferId": transfer_id,
            "signalId": signal_id,
            "targetActorDid": target_did,
            "status": "transferred",
            "transferredAt": now,
        }

    result = await asyncio.to_thread(_run)
    # Phase D2: route on transfer outcome — mirrors _transfer_outcome_gate.
    result["nextRoute"] = "form_colony" if result.get("status") == "transferred" else "lyse"
    LOG.info("transfer_signal: %s → %s", signal_id, target_did)
    return result


# ─── saikin.form_colony ───────────────────────────────────────────────────


async def task_form_colony(
    signalIds: list[str] | None = None,
    colonyLabel: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Group related signals into a cooperative colony (biofilm analogy)."""

    if not signalIds:
        return {"error": "signalIds required"}

    colony_id = _uid("col")
    colony_vid = f"at://{SAIKIN_DID}/com.etzhayyim.apps.saikin.colony/{colony_id}"
    now = _now()
    member_count = len(signalIds)

    def _run() -> dict[str, Any]:
        store = select_belief_store()

        col_rec = SaikinColonyRecord(
            vertex_id=colony_vid,
            record_id=_uid("rec"),
            owner_did=SAIKIN_DID,
            label=colonyLabel or "saikin_colony",
            status="active",
            stream_id="",
            agent_did=SAIKIN_DID,
            value_json=json.dumps({"signalIds": signalIds}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            colony_label=colonyLabel or "",
            member_count=member_count,
            formed_at=now,
            lysed_at=None
        )
        store.put_vertex_saikin_colony(col_rec)

        for sid in signalIds:
            edge_id = _uid("cmb")
            mem_rec = SaikinMemberRecord(
                edge_id=edge_id,
                src_vid=colony_vid,
                dst_vid=f"at://{SAIKIN_DID}/com.etzhayyim.apps.saikin.signal/{sid}",
                relation_kind="saikin_member",
                value_json=json.dumps({}),
                created_at=now,
                updated_at=now,
                owner_did=SAIKIN_DID,
                sensitivity_ord=0,
                colony_id=colony_id,
                signal_id=sid,
                joined_at=now
            )
            store.put_edge_saikin_member(mem_rec)

        return {
            "colonyId": colony_id,
            "colonyVertexId": colony_vid,
            "memberCount": member_count,
            "status": "active",
            "formedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("form_colony: %s with %d members", colony_id, member_count)
    return result


# ─── saikin.lyse ──────────────────────────────────────────────────────────


async def task_lyse(
    signalId: str = "",
    reason: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Decompose and release a processed signal (lysis analogy)."""

    if not signalId:
        return {"error": "signalId required"}

    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT vertex_id FROM vertex_saikin_signal WHERE vertex_id LIKE ? LIMIT 1",
                    (f"%{signalId}%",)
                ).fetchone()
            except sqlite3.OperationalError:
                row = None

        if not row:
            return {"error": f"signal not found: {signalId}"}

        vid = row["vertex_id"]
        with store._conn() as conn:
            conn.execute(
                "UPDATE vertex_saikin_signal SET status = 'lysed', updated_at = ? WHERE vertex_id = ?",
                (now, vid),
            )
        return {
            "lysed": True,
            "signalId": signalId,
            "reason": reason,
            "lysedAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("lyse: %s reason=%s", signalId, reason)
    return result


# ─── saikin.handoff_to_ki ────────────────────────────────────────────────


async def task_handoff_to_ki(
    colonyId: str = "",
    signalId: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Bridge saikin→ki: seed a vertex_ki_absorb row from a formed colony."""

    if not colonyId and not signalId:
        return {"error": "colonyId or signalId required"}

    absorb_id = _uid("xyl")
    absorb_vid = f"at://{KI_DID}/com.etzhayyim.apps.ki.absorb/{absorb_id}"
    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        source_vid = ""
        input_kind = "text"
        content_snippet = ""

        with store._conn() as conn:
            conn.row_factory = sqlite3.Row

            if colonyId:
                try:
                    colony = conn.execute(
                        "SELECT vertex_id, colony_label, value_json FROM vertex_saikin_colony WHERE vertex_id LIKE ? LIMIT 1",
                        (f"%{colonyId}%",)
                    ).fetchone()
                except sqlite3.OperationalError:
                    colony = None

                if colony:
                    source_vid = colony["vertex_id"]
                    content_snippet = colony["colony_label"] or ""
                    try:
                        val = json.loads(colony["value_json"] or "{}")
                        content_snippet = content_snippet or str(val.get("signalIds", ""))
                    except (json.JSONDecodeError, TypeError):
                        pass

            if not source_vid and signalId:
                try:
                    sig = conn.execute(
                        "SELECT vertex_id, input_kind, raw_ref FROM vertex_saikin_signal WHERE vertex_id LIKE ? LIMIT 1",
                        (f"%{signalId}%",)
                    ).fetchone()
                except sqlite3.OperationalError:
                    sig = None

                if sig:
                    source_vid = sig["vertex_id"]
                    input_kind = sig["input_kind"] or "text"
                    content_snippet = sig["raw_ref"] or ""

        if not source_vid:
            return {"error": f"neither colony {colonyId!r} nor signal {signalId!r} found"}

        content_hash = hashlib.sha256(content_snippet.encode()).hexdigest()[:32]

        rec = KiAbsorbRecord(
            vertex_id=absorb_vid,
            record_id=_uid("rec"),
            owner_did=KI_DID,
            label="ki_absorb",
            status="absorbed",
            stream_id="",
            agent_did=SAIKIN_DID,
            value_json=json.dumps({"content": content_snippet[:500], "saikinColonyId": colonyId}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            source_vertex_id=source_vid,
            input_kind=input_kind,
            content_hash=content_hash,
            absorbed_at=now,
            synthesized_at=None
        )
        store.put_vertex_ki_absorb(rec)

        return {
            "kiAbsorbId": absorb_id,
            "kiAbsorbVertexId": absorb_vid,
            "sourceVertexId": source_vid,
            "handedOffAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "handoff_to_ki: colony=%s signal=%s absorb=%s",
        colonyId, signalId, result.get("kiAbsorbId"),
    )
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("SAIKIN_TASK_TIMEOUT_MS", "120000"))

    registrations = {
        "saikin.probe_environment": task_probe_environment,
        "saikin.transfer_signal": task_transfer_signal,
        "saikin.form_colony": task_form_colony,
        "saikin.lyse": task_lyse,
        "saikin.handoff_to_ki": task_handoff_to_ki,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "saikin zeebe worker registered %d task types via %s",
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
