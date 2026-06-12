"""
Zeebe worker for koke (苔) — bryophyta primary fixation layer (ADR-2605071900).

Layer 0 of the myco-yeast artificial organism. Reversibly captures raw external
signals (CO₂ analogy) into structured vertex_koke_fixation rows (glucose) before
optionally handing them off to the hakkou fermentation pipeline and the saikin
horizontal-transfer pipeline.

Subscribes to 5 domain job types:
  koke.scan_raw_signals    — find raw signals that need fixation
  koke.fix_signal          — primary fixation (reversible capture)
  koke.classify_fixation   — LLM classification of fixed content
  koke.handoff_to_hakkou   — hand off a fixed+classified signal to hakkou
  koke.handoff_to_saikin   — bridge koke→saikin: copy fixation into vertex_saikin_signal

Run:
  python -m kotodama.koke_worker_main

Env:
  AGENTGATEWAY_MCP_URL  — LangServer AgentGateway URL (default 127.0.0.1:8080)
  RW_URL         — RisingWave postgres URL
  KOKE_CONFIDENCE_THRESHOLD — min confidence for auto-handoff (default 0.7)
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
from kotodama.primitives.active_inference_substrate import select_belief_store, KokeFixationRecord, HakkouFermentRecord, KokeFlowRecord, SaikinSignalRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("koke_worker")

KOKE_DID = "did:web:koke.etzhayyim.com"
HAKKOU_DID = "did:web:hakkou.etzhayyim.com"
SAIKIN_DID = "did:web:saikin.etzhayyim.com"

CONFIDENCE_THRESHOLD = float(os.environ.get("KOKE_CONFIDENCE_THRESHOLD", "0.7"))
SCAN_BATCH_SIZE = int(os.environ.get("KOKE_SCAN_BATCH_SIZE", "10"))


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── koke.scan_raw_signals ────────────────────────────────────────────────


async def task_scan_raw_signals(**_: Any) -> dict[str, Any]:
    """Scan vertex_koke_fixation for signals that need (re-)fixation."""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    f"""
                    SELECT vertex_id, input_kind, raw_ref, signal_hash
                    FROM vertex_koke_fixation
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT {int(SCAN_BATCH_SIZE)}
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        signals = [
            {
                "vertexId": r["vertex_id"],
                "inputKind": r["input_kind"] or "text",
                "rawRef": r["raw_ref"] or "",
                "signalHash": r["signal_hash"] or "",
            }
            for r in (rows or [])
        ]
        return {"signalCount": len(signals), "signals": signals}

    result = await asyncio.to_thread(_run)
    # Phase D2 (ADR-2605082000): embed routing decision so koke.canonical.v2
    # uses field-based conditional edges, retiring koke_cycle._has_signals_gate.
    result["nextRoute"] = "fix" if int(result.get("signalCount") or 0) > 0 else "no_signals"
    LOG.info("scan_raw_signals: found %d pending signals", result["signalCount"])
    return result


# ─── koke.fix_signal ─────────────────────────────────────────────────────


async def task_fix_signal(
    signals: list[dict[str, Any]] | None = None,
    inputKind: str = "text",
    rawRef: str = "",
    agentDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Primary fixation: CO₂ → glucose. Reversible capture."""

    # If called directly (not from scan), create a new fixation
    if not signals and not rawRef:
        return {"error": "signals or rawRef required"}

    if signals:
        # Process first signal from scan
        sig = signals[0]
        fixation_vid = sig.get("vertexId", "")
        input_kind = sig.get("inputKind", "text")
        raw_ref = sig.get("rawRef", "")
    else:
        fixation_vid = ""
        input_kind = inputKind
        raw_ref = rawRef

    signal_hash = hashlib.sha256(raw_ref.encode()).hexdigest()[:32]
    now = _now()

    def _run() -> dict[str, Any]:
        nonlocal fixation_vid
        store = select_belief_store()
        if fixation_vid:
            # Update existing pending fixation to 'fixed'
            with store._conn() as conn:
                conn.execute(
                    "UPDATE vertex_koke_fixation SET status = 'fixed', fixed_at = ?, signal_hash = ?, updated_at = ? WHERE vertex_id = ?",
                    (now, signal_hash, now, fixation_vid),
                )
            fid = fixation_vid.split("/")[-1]
            return {
                "fixationId": fid,
                "vertexId": fixation_vid,
                "signalHash": signal_hash,
                "status": "fixed",
                "inputKind": input_kind,
                "rawRef": raw_ref,
            }
        else:
            # Create new fixation
            fid = _uid("kox")
            vid = f"at://{KOKE_DID}/com.etzhayyim.apps.koke.fixation/{fid}"

            rec = KokeFixationRecord(
                vertex_id=vid,
                record_id=_uid("rec"),
                owner_did=KOKE_DID,
                label="koke_fixation",
                status="fixed",
                stream_id="",
                agent_did=agentDid or KOKE_DID,
                value_json=json.dumps({}),
                created_at=now,
                updated_at=now,
                sensitivity_ord=0,
                input_kind=input_kind,
                raw_ref=raw_ref,
                signal_hash=signal_hash,
                classification=None,
                confidence=0.0,
                fixed_at=now,
                released_at=None
            )
            store.put_vertex_koke_fixation(rec)

            return {
                "fixationId": fid,
                "vertexId": vid,
                "signalHash": signal_hash,
                "status": "fixed",
                "inputKind": input_kind,
                "rawRef": raw_ref,
            }

    result = await asyncio.to_thread(_run)
    LOG.info("fix_signal: %s hash=%s", result.get("fixationId"), signal_hash)
    return result


# ─── koke.classify_fixation ───────────────────────────────────────────────


async def task_classify_fixation(
    fixationId: str = "",
    inputKind: str = "text",
    rawRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    """LLM classification of a fixed signal. Updates classification + confidence."""

    from kotodama import llm

    if not fixationId and not rawRef:
        return {"error": "fixationId or rawRef required", "classification": "unknown", "confidence": 0.0}

    content = rawRef[:1500]

    llm_result = await asyncio.to_thread(
        llm.call_tier,
        "low",
        (
            "You are a signal classifier for the koke fixation layer. "
            "Classify the input into one of: knowledge, event, entity, relation, signal, noise. "
            "Respond in JSON with keys: classification (string), confidence (0.0-1.0), summary (string)."
        ),
        f"Input kind: {inputKind}\n\n{content}",
        max_tokens=150,
    )

    raw = (llm_result.get("content") or "").strip()
    try:
        parsed = json.loads(raw)
        classification = str(parsed.get("classification", "signal"))
        confidence = float(parsed.get("confidence", 0.5))
    except (json.JSONDecodeError, ValueError, TypeError):
        classification = "signal"
        confidence = 0.5

    if fixationId:
        now = _now()

        def _update() -> None:
            store = select_belief_store()
            with store._conn() as conn:
                conn.execute(
                    "UPDATE vertex_koke_fixation SET classification = ?, confidence = ?, updated_at = ? WHERE vertex_id LIKE ?",
                    (classification, confidence, now, f"%{fixationId}%"),
                )

        await asyncio.to_thread(_update)

    LOG.info(
        "classify_fixation: %s → %s (%.2f)", fixationId, classification, confidence
    )
    # Phase D2: route on confidence — mirrors koke_cycle._confidence_gate.
    return {
        "fixationId": fixationId,
        "classification": classification,
        "confidence": confidence,
        "nextRoute": "hakkou" if confidence >= 0.7 else "saikin",
    }


# ─── koke.handoff_to_hakkou ───────────────────────────────────────────────


async def task_handoff_to_hakkou(
    fixationId: str = "",
    classification: str = "signal",
    inputKind: str = "text",
    rawRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Hand off a fixed+classified signal to the hakkou fermentation pipeline."""

    if not fixationId:
        return {"error": "fixationId required"}

    # create hakkou ferment record
    ferment_id = _uid("fmnt")
    ferment_vid = f"at://{HAKKOU_DID}/com.etzhayyim.apps.hakkou.ferment/{ferment_id}"
    edge_id = _uid("kflo")
    now = _now()

    # resolve fixation vertex_id
    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                fixation = conn.execute(
                    "SELECT vertex_id FROM vertex_koke_fixation WHERE vertex_id LIKE ? AND status = 'fixed' LIMIT 1",
                    (f"%{fixationId}%",)
                ).fetchone()
            except sqlite3.OperationalError:
                fixation = None

        if not fixation:
            return {"error": f"fixation not found or not in fixed state: {fixationId}"}

        fixation_vid = fixation["vertex_id"]

        # create hakkou ferment
        ferment_rec = HakkouFermentRecord(
            vertex_id=ferment_vid,
            record_id=_uid("rec"),
            owner_did=HAKKOU_DID,
            label="hakkou_ferment",
            status="pending",
            stream_id="",
            agent_did=KOKE_DID,
            value_json=json.dumps({"source": "koke", "classification": classification}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            input_kind=inputKind,
            input_ref=rawRef or fixationId,
            output_vertex_id=None,
            output_kind=None,
            ethanol_hash=None,
            co2_audit_ref=None
        )
        store.put_vertex_hakkou_ferment(ferment_rec)

        # create koke flow edge
        flow_rec = KokeFlowRecord(
            edge_id=edge_id,
            src_vid=fixation_vid,
            dst_vid=ferment_vid,
            relation_kind="koke_flow",
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            owner_did=KOKE_DID,
            sensitivity_ord=0,
            fixation_id=fixationId,
            ferment_id=ferment_id,
            handoff_kind=classification,
            handed_off_at=now
        )
        store.put_edge_koke_flow(flow_rec)

        with store._conn() as conn:
            # mark fixation as handed off
            conn.execute(
                "UPDATE vertex_koke_fixation SET status = 'handedOff', updated_at = ? WHERE vertex_id = ?",
                (now, fixation_vid),
            )
        return {
            "fermentId": ferment_id,
            "fermentVertexId": ferment_vid,
            "edgeId": edge_id,
            "fixationId": fixationId,
            "handedOffAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "handoff_to_hakkou: fixation=%s ferment=%s",
        fixationId, result.get("fermentId"),
    )
    return result


# ─── koke.handoff_to_saikin ──────────────────────────────────────────────


async def task_handoff_to_saikin(
    fixationId: str = "",
    classification: str = "signal",
    inputKind: str = "text",
    rawRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Bridge koke→saikin: copy a fixation into vertex_saikin_signal for HGT processing."""

    if not fixationId:
        return {"error": "fixationId required"}

    signal_id = _uid("s41k")
    signal_vid = f"at://{SAIKIN_DID}/com.etzhayyim.apps.saikin.signal/{signal_id}"
    edge_id = _uid("kflo")
    now = _now()

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                fixation = conn.execute(
                    """
                    SELECT vertex_id, input_kind, raw_ref, signal_hash
                    FROM vertex_koke_fixation
                    WHERE vertex_id LIKE ?
                    LIMIT 1
                    """,
                    (f"%{fixationId}%",)
                ).fetchone()
            except sqlite3.OperationalError:
                fixation = None

        if not fixation:
            return {"error": f"fixation not found: {fixationId}"}

        fixation_vid = fixation["vertex_id"]
        fix_input_kind = fixation["input_kind"]
        fix_raw_ref = fixation["raw_ref"]
        fix_signal_hash = fixation["signal_hash"]

        signal_rec = SaikinSignalRecord(
            vertex_id=signal_vid,
            record_id=_uid("rec"),
            owner_did=SAIKIN_DID,
            label="saikin_signal",
            status="unprocessed",
            stream_id="",
            agent_did=KOKE_DID,
            value_json=json.dumps({"source": "koke", "classification": classification}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            input_kind=fix_input_kind or inputKind,
            raw_ref=fix_raw_ref or rawRef,
            signal_hash=fix_signal_hash or "",
            probe_source="koke"
        )
        store.put_vertex_saikin_signal(signal_rec)

        flow_rec = KokeFlowRecord(
            edge_id=edge_id,
            src_vid=fixation_vid,
            dst_vid=signal_vid,
            relation_kind="koke_flow",
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            owner_did=KOKE_DID,
            sensitivity_ord=0,
            fixation_id=fixationId,
            ferment_id=signal_id,
            handoff_kind="saikin",
            handed_off_at=now
        )
        store.put_edge_koke_flow(flow_rec)

        return {
            "saikinSignalId": signal_id,
            "saikinSignalVertexId": signal_vid,
            "edgeId": edge_id,
            "fixationId": fixationId,
            "handedOffAt": now,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "handoff_to_saikin: fixation=%s signal=%s",
        fixationId, result.get("saikinSignalId"),
    )
    return result


# ─── worker entrypoint ────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("KOKE_TASK_TIMEOUT_MS", "120000"))

    registrations = {
        "koke.scan_raw_signals": task_scan_raw_signals,
        "koke.fix_signal": task_fix_signal,
        "koke.classify_fixation": task_classify_fixation,
        "koke.handoff_to_hakkou": task_handoff_to_hakkou,
        "koke.handoff_to_saikin": task_handoff_to_saikin,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "koke zeebe worker registered %d task types via %s",
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
