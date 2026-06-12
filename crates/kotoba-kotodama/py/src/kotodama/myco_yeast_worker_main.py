"""
Zeebe worker for the myco-yeast artificial organism (ADR-2605071200).

Subscribes to 8 domain job types:
  kabi.anastomosis_probe       — anastomosis compatibility gate
  kobo.bud_agent               — budding (asexual reproduction)
  kobo.sporulate               — sporulation → houshi custody
  kobo.germinate               — germination (spore revival)
  kinoko.check_flow_threshold  — PoNF consensus block production
  hakkou.create_ferment_record — start fermentation job
  hakkou.llm_transform         — LLM-driven irreversible transformation
  hakkou.finalize_ferment      — seal ferment with ethanol_hash

Run:
  python -m kotodama.myco_yeast_worker_main

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
from kotodama.primitives.active_inference_substrate import select_belief_store, KabiAnastomosisRecord, KabiHyphaRecord, KoboAgentRecord, KoboPrionRecord, KoboBuddingRecord, HoushiSporeRecord, KinokoBlockRecord, HakkouFermentRecord
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("myco_yeast_worker")

KABI_DID = "did:web:kabi.etzhayyim.com"
KOBO_DID = "did:web:kobo.etzhayyim.com"
KINOKO_DID = "did:web:kinoko.etzhayyim.com"
HOUSHI_DID = "did:web:houshi.etzhayyim.com"
HAKKOU_DID = "did:web:hakkou.etzhayyim.com"

PONF_FLOW_THRESHOLD = float(os.environ.get("PONF_FLOW_THRESHOLD", "100.0"))
PONF_ETA_MIN = float(os.environ.get("PONF_ETA_MIN", "0.5"))
ANASTOMOSIS_TRUST_MIN = float(os.environ.get("ANASTOMOSIS_TRUST_MIN", "0.6"))
ANASTOMOSIS_ETA_DIFF_MAX = float(os.environ.get("ANASTOMOSIS_ETA_DIFF_MAX", "0.3"))
PRION_MALIGNANT_THRESHOLD = float(os.environ.get("PRION_MALIGNANT_THRESHOLD", "0.7"))


# ─── helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    digest = hashlib.sha256(f"{prefix}{time.time_ns()}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


# ─── kabi.anastomosis_probe ───────────────────────────────────────────────


async def task_kabi_anastomosis_probe(
    network_a_did: str = "",
    network_b_did: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Gate protocol: decide whether two kabi networks may merge (anastomose)."""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                # fetch network η for A and B
                row_a = conn.execute(
                    "SELECT total_flow, hypha_count FROM vertex_kabi_network WHERE agent_did = ? LIMIT 1",
                    (network_a_did,)
                ).fetchone()
                row_b = conn.execute(
                    "SELECT total_flow, hypha_count FROM vertex_kabi_network WHERE agent_did = ? LIMIT 1",
                    (network_b_did,)
                ).fetchone()

                # compute average eta per network from edge_kabi_hypha
                eta_a_row = conn.execute(
                    "SELECT AVG(eta) as avg_eta FROM edge_kabi_hypha WHERE src_agent_did = ? AND pruned_at IS NULL",
                    (network_a_did,)
                ).fetchone()
                eta_b_row = conn.execute(
                    "SELECT AVG(eta) as avg_eta FROM edge_kabi_hypha WHERE src_agent_did = ? AND pruned_at IS NULL",
                    (network_b_did,)
                ).fetchone()

                # check malignant prions from either side
                malignant_a = conn.execute(
                    "SELECT COUNT(*) as count FROM vertex_kobo_prion WHERE agent_did = ? AND malignant_score > ?",
                    (network_a_did, PRION_MALIGNANT_THRESHOLD)
                ).fetchone()
                malignant_b = conn.execute(
                    "SELECT COUNT(*) as count FROM vertex_kobo_prion WHERE agent_did = ? AND malignant_score > ?",
                    (network_b_did, PRION_MALIGNANT_THRESHOLD)
                ).fetchone()
            except sqlite3.OperationalError:
                row_a, row_b = None, None
                eta_a_row, eta_b_row = None, None
                malignant_a, malignant_b = None, None

        eta_a = float(eta_a_row["avg_eta"] or 0) if eta_a_row else 0.0
        eta_b = float(eta_b_row["avg_eta"] or 0) if eta_b_row else 0.0

        count_a = int(malignant_a["count"]) if malignant_a else 0
        count_b = int(malignant_b["count"]) if malignant_b else 0
        prion_ok = (count_a == 0 and count_b == 0)

        eta_diff = abs(eta_a - eta_b)
        # simple trust proxy: both networks must have ≥1 hypha
        trust_ok = (row_a is not None) and (row_b is not None)
        eta_ok = eta_diff <= ANASTOMOSIS_ETA_DIFF_MAX

        accept = trust_ok and eta_ok and prion_ok
        compatibility_score = round(
            (1.0 if trust_ok else 0.0) * 0.4
            + max(0.0, 1.0 - eta_diff) * 0.4
            + (1.0 if prion_ok else 0.0) * 0.2,
            4,
        )
        result = "ACCEPT" if accept else "REJECT"
        reason = (
            "compatibility checks passed" if accept
            else (
                "malignant prion detected" if not prion_ok
                else f"eta_diff={eta_diff:.3f} > threshold={ANASTOMOSIS_ETA_DIFF_MAX}" if not eta_ok
                else "network not found"
            )
        )

        # persist anastomosis decision
        edge_id = _uid("ana")
        ana_rec = KabiAnastomosisRecord(
            edge_id=edge_id,
            src_vid=network_a_did,
            dst_vid=network_b_did,
            relation_kind="anastomosis",
            value_json=json.dumps({"eta_a": eta_a, "eta_b": eta_b}),
            created_at=_now(),
            updated_at=_now(),
            owner_did=KABI_DID,
            sensitivity_ord=0,
            network_a_did=network_a_did,
            network_b_did=network_b_did,
            compatibility_score=compatibility_score,
            result=result,
            reason=reason
        )
        store.put_edge_kabi_anastomosis(ana_rec)

        if accept:
            # add bidirectional hypha seeds
            for src, dst in [(network_a_did, network_b_did), (network_b_did, network_a_did)]:
                hid = _uid("hyp")
                hypha_rec = KabiHyphaRecord(
                    edge_id=hid,
                    src_vid=src,
                    dst_vid=dst,
                    relation_kind="hypha",
                    value_json=json.dumps({}),
                    created_at=_now(),
                    updated_at=_now(),
                    owner_did=KABI_DID,
                    sensitivity_ord=0,
                    src_agent_did=src,
                    dst_agent_did=dst,
                    eta=round((eta_a + eta_b) / 2, 4),
                    flow=0.0,
                    pruned_at=None
                )
                store.put_edge_kabi_hypha(hypha_rec)

        return {
            "result": result, "reason": reason,
            "compatibilityScore": compatibility_score, "edgeId": edge_id,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("anastomosis_probe %s ↔ %s → %s", network_a_did, network_b_did, result["result"])
    return result


# ─── kobo.bud_agent ───────────────────────────────────────────────────────


async def task_kobo_bud_agent(
    parent_did: str = "",
    child_did: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Budding: create a child kobo agent with inherited heritable prions."""

    if not parent_did:
        return {"error": "parent_did required"}

    generated_child = not child_did
    if not child_did:
        child_did = f"did:web:kobo.etzhayyim.com:agent:{_uid('bud')}"

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                parent = conn.execute(
                    "SELECT vertex_id, eta, role, stress_score FROM vertex_kobo_agent WHERE agent_did = ? LIMIT 1",
                    (parent_did,)
                ).fetchone()

                # copy heritable prions
                prions = conn.execute(
                    "SELECT pattern_hash, heritable, malignant_score, content FROM vertex_kobo_prion "
                    "WHERE agent_did = ? AND heritable = 1",
                    (parent_did,)
                ).fetchall()
            except sqlite3.OperationalError:
                parent = None
                prions = []

        if not parent:
            return {"error": f"parent agent not found: {parent_did}"}

        now = _now()
        child_vid = f"at://{KOBO_DID}/com.etzhayyim.apps.kobo.agent/{child_did.split(':')[-1]}"

        agent_rec = KoboAgentRecord(
            vertex_id=child_vid,
            record_id=_uid("rec"),
            owner_did=KOBO_DID,
            label="kobo_agent",
            status="active",
            stream_id="",
            agent_did=child_did,
            value_json=json.dumps({"origin": "budding"}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            parent_did=parent_did,
            role=parent["role"] or "general",
            eta=float(parent["eta"] or 0.5),
            stress_score=0.0
        )
        store.put_vertex_kobo_agent(agent_rec)

        # transfer heritable prions
        for p in prions:
            pvid = f"at://{KOBO_DID}/com.etzhayyim.apps.kobo.prion/{_uid('prn')}"
            prion_rec = KoboPrionRecord(
                vertex_id=pvid,
                record_id=_uid("rec"),
                owner_did=KOBO_DID,
                label="kobo_prion",
                status="active",
                stream_id="",
                agent_did=child_did,
                value_json=json.dumps({}),
                created_at=now,
                updated_at=now,
                sensitivity_ord=0,
                pattern_hash=p["pattern_hash"],
                heritable=True,
                malignant_score=float(p["malignant_score"] or 0.0),
                content=p["content"] or ""
            )
            store.put_vertex_kobo_prion(prion_rec)

        # record budding edge
        eid = _uid("bud")
        bud_rec = KoboBuddingRecord(
            edge_id=eid,
            src_vid=parent["vertex_id"],
            dst_vid=child_vid,
            relation_kind="budding",
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            owner_did=KOBO_DID,
            sensitivity_ord=0,
            parent_did=parent_did,
            child_did=child_did,
            budded_at=now,
            prion_count=len(prions)
        )
        store.put_edge_kobo_budding(bud_rec)

        return {
            "childDid": child_did, "childVertexId": child_vid,
            "prionCount": len(prions), "edgeId": eid, "generated": generated_child,
        }

    result = await asyncio.to_thread(_run)
    LOG.info("bud_agent: %s → %s (%d prions)", parent_did, result.get("childDid"), result.get("prionCount", 0))
    return result


# ─── kobo.sporulate ───────────────────────────────────────────────────────


async def task_kobo_sporulate(
    agent_did: str = "",
    quorum_n: int = 3,
    **_: Any,
) -> dict[str, Any]:
    """Sporulate a kobo agent under stress: encode state → houshi spore."""

    if not agent_did:
        return {"error": "agent_did required"}

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                agent = conn.execute(
                    "SELECT vertex_id, stress_score, value_json FROM vertex_kobo_agent "
                    "WHERE agent_did = ? AND status = 'active' LIMIT 1",
                    (agent_did,)
                ).fetchone()

                prions = conn.execute(
                    "SELECT pattern_hash, heritable, content FROM vertex_kobo_prion WHERE agent_did = ?",
                    (agent_did,)
                ).fetchall()
            except sqlite3.OperationalError:
                agent = None
                prions = []

        if not agent:
            return {"error": f"active agent not found: {agent_did}"}

        # CBOR-like blob: JSON-encoded essential state
        blob_data = {
            "agent_did": agent_did,
            "prions": [{"ph": p["pattern_hash"], "heritable": p["heritable"], "content": p["content"]} for p in prions],
            "encoded_at": _now(),
        }
        blob_json = json.dumps(blob_data)
        revival_key_hint = hashlib.sha256(blob_json.encode()).hexdigest()[:16]

        spore_id = _uid("spr")
        spore_vid = f"at://{HOUSHI_DID}/com.etzhayyim.apps.houshi.spore/{spore_id}"
        now = _now()

        spore_rec = HoushiSporeRecord(
            vertex_id=spore_vid,
            record_id=_uid("rec"),
            owner_did=HOUSHI_DID,
            label="houshi_spore",
            status="dormant",
            stream_id="",
            agent_did=agent_did,
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            origin_agent_did=agent_did,
            blob_cbor=blob_json,
            revival_key_hint=revival_key_hint,
            quorum_n=quorum_n,
            germinated_at=None
        )
        store.put_vertex_houshi_spore(spore_rec)

        with store._conn() as conn:
            # mark agent dormant
            conn.execute(
                "UPDATE vertex_kobo_agent SET status = 'dormant', updated_at = ? WHERE agent_did = ?",
                (now, agent_did),
            )
        return {"sporeId": spore_id, "sporeVertexId": spore_vid, "revivalKeyHint": revival_key_hint}

    result = await asyncio.to_thread(_run)
    LOG.info("sporulate: %s → spore %s", agent_did, result.get("sporeId"))
    return result


# ─── kobo.germinate ───────────────────────────────────────────────────────


async def task_kobo_germinate(
    spore_id: str = "",
    confirming_custodian_did: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Germinate a dormant spore: check custody quorum, revive agent."""

    if not spore_id:
        return {"error": "spore_id required"}

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                spore = conn.execute(
                    "SELECT vertex_id, origin_agent_did, blob_cbor, quorum_n, germinated_at "
                    "FROM vertex_houshi_spore WHERE (vertex_id LIKE ? OR record_id = ?) LIMIT 1",
                    (f"%{spore_id}%", spore_id)
                ).fetchone()

                if not spore:
                    return {"error": f"spore not found: {spore_id}"}
                if spore["germinated_at"]:
                    return {"error": "already germinated", "germinatedAt": spore["germinated_at"]}

                custody_count_row = conn.execute(
                    "SELECT COUNT(*) as count FROM edge_houshi_custody WHERE src_vid = ? AND custody_confirmed = 1",
                    (spore["vertex_id"],)
                ).fetchone()
            except sqlite3.OperationalError:
                return {"error": f"spore not found: {spore_id}"}

        confirmed = int(custody_count_row["count"] if custody_count_row else 0)
        quorum_needed = int(spore["quorum_n"] or 3)
        quorum_met = confirmed >= (quorum_needed // 2 + 1)

        if not quorum_met:
            return {
                "quorumMet": False,
                "confirmed": confirmed,
                "required": quorum_needed // 2 + 1,
            }

        agent_did = spore["origin_agent_did"]
        now = _now()

        with store._conn() as conn:
            conn.execute(
                "UPDATE vertex_houshi_spore SET germinated_at = ?, updated_at = ? WHERE vertex_id = ?",
                (now, now, spore["vertex_id"]),
            )
            conn.execute(
                "UPDATE vertex_kobo_agent SET status = 'active', updated_at = ? WHERE agent_did = ?",
                (now, agent_did),
            )
        return {"quorumMet": True, "agentDid": agent_did, "germinatedAt": now}

    result = await asyncio.to_thread(_run)
    LOG.info("germinate: spore=%s quorumMet=%s", spore_id, result.get("quorumMet"))
    return result


# ─── kinoko.check_flow_threshold ─────────────────────────────────────────


async def task_kinoko_check_flow_threshold(**_: Any) -> dict[str, Any]:
    """PoNF: if total_flow ≥ threshold AND avg_eta ≥ min, form a consensus block."""

    def _run() -> dict[str, Any]:
        store = select_belief_store()
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    """
                    SELECT SUM(flow) as sum_flow, AVG(eta) as avg_eta, COUNT(DISTINCT src_agent_did) as participants
                    FROM edge_kabi_hypha
                    WHERE pruned_at IS NULL
                    """
                ).fetchone()
            except sqlite3.OperationalError:
                row = None

        if not row or row["sum_flow"] is None:
            return {"thresholdMet": False, "totalFlow": 0.0, "avgEta": 0.0}

        total_flow = float(row["sum_flow"] or 0)
        avg_eta = float(row["avg_eta"] or 0)
        participants = int(row["participants"] or 0)

        if total_flow < PONF_FLOW_THRESHOLD or avg_eta < PONF_ETA_MIN:
            return {
                "thresholdMet": False,
                "totalFlow": round(total_flow, 4),
                "avgEta": round(avg_eta, 4),
                "required": {"flow": PONF_FLOW_THRESHOLD, "eta": PONF_ETA_MIN},
            }

        # form block
        with store._conn() as conn:
            conn.row_factory = sqlite3.Row
            try:
                prev = conn.execute(
                    "SELECT vertex_id, block_hash FROM vertex_kinoko_block "
                    "WHERE block_status = 'final' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
            except sqlite3.OperationalError:
                prev = None

        prev_block_id = (prev["vertex_id"] if prev else "") or ""
        prev_hash = (prev["block_hash"] if prev else "") or ""

        block_id = _uid("blk")
        block_hash = hashlib.sha256(
            f"{prev_hash}{total_flow}{avg_eta}{_now()}".encode()
        ).hexdigest()[:32]
        block_vid = f"at://{KINOKO_DID}/com.etzhayyim.apps.kinoko.block/{block_id}"
        now = _now()

        rec = KinokoBlockRecord(
            vertex_id=block_vid,
            record_id=_uid("rec"),
            owner_did=KINOKO_DID,
            label="kinoko_block",
            status="active",
            stream_id="",
            agent_did=KINOKO_DID,
            value_json=json.dumps({"participants": participants}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            prev_block_id=prev_block_id,
            block_hash=block_hash,
            total_flow=total_flow,
            participant_count=participants,
            eta_min_used=avg_eta,
            block_status="final"
        )
        store.put_vertex_kinoko_block(rec)

        with store._conn() as conn:
            # reset flow counters on hypha edges
            conn.execute(
                "UPDATE edge_kabi_hypha SET flow = 0.0, updated_at = ? WHERE pruned_at IS NULL",
                (now,),
            )
        return {
            "thresholdMet": True,
            "blockId": block_id, "blockHash": block_hash,
            "totalFlow": round(total_flow, 4),
            "avgEta": round(avg_eta, 4),
            "participantCount": participants,
        }

    result = await asyncio.to_thread(_run)
    LOG.info(
        "check_flow_threshold: met=%s flow=%.2f eta=%.3f block=%s",
        result["thresholdMet"], result.get("totalFlow", 0),
        result.get("avgEta", 0), result.get("blockId", "-"),
    )
    return result


# ─── hakkou.create_ferment_record ────────────────────────────────────────


async def task_hakkou_create_ferment_record(
    input_kind: str = "text",
    input_ref: str = "",
    agent_did: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Start a fermentation job: write-only record, irreversible."""

    if not input_ref:
        return {"error": "input_ref required"}

    ferment_id = _uid("fmnt")
    vid = f"at://{HAKKOU_DID}/com.etzhayyim.apps.hakkou.ferment/{ferment_id}"
    now = _now()

    def _write() -> None:
        store = select_belief_store()
        rec = HakkouFermentRecord(
            vertex_id=vid,
            record_id=_uid("rec"),
            owner_did=HAKKOU_DID,
            label="hakkou_ferment",
            status="pending",
            stream_id="",
            agent_did=agent_did or HAKKOU_DID,
            value_json=json.dumps({}),
            created_at=now,
            updated_at=now,
            sensitivity_ord=0,
            input_kind=input_kind,
            input_ref=input_ref,
            output_vertex_id=None,
            output_kind=None,
            ethanol_hash=None,
            co2_audit_ref=None
        )
        store.put_vertex_hakkou_ferment(rec)

    await asyncio.to_thread(_write)
    LOG.info("create_ferment_record: %s kind=%s", ferment_id, input_kind)
    return {"fermentId": ferment_id, "vertexId": vid, "status": "pending"}


# ─── hakkou.llm_transform ────────────────────────────────────────────────


async def task_hakkou_llm_transform(
    ferment_id: str = "",
    input_kind: str = "text",
    input_ref: str = "",
    agent_did: str = "",
    **_: Any,
) -> dict[str, Any]:
    """LLM-driven irreversible transformation: raw signal → structured knowledge."""

    from kotodama import llm

    if not input_ref:
        return {"error": "input_ref required"}

    content = input_ref[:2000]  # truncate if direct content passed

    result = await asyncio.to_thread(
        llm.call_tier,
        "mid",
        (
            "You are a data fermentation engine. Extract structured facts from the input. "
            "Respond in JSON with keys: summary (str), entities (list[str]), "
            "category (str), confidence (0-1)."
        ),
        f"Input kind: {input_kind}\n\n{content}",
        max_tokens=300,
    )

    raw_output = (result.get("content") or "").strip()
    ethanol_hash = hashlib.sha256(raw_output.encode()).hexdigest()[:32]

    LOG.info("llm_transform: ferment=%s ethanol_hash=%s", ferment_id, ethanol_hash)
    return {
        "fermentId": ferment_id,
        "llmOutput": raw_output,
        "ethanolHash": ethanol_hash,
    }


# ─── hakkou.finalize_ferment ─────────────────────────────────────────────


async def task_hakkou_finalize_ferment(
    ferment_id: str = "",
    llmOutput: str = "",
    ethanolHash: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Seal the ferment record: write ethanol_hash + co2_audit_ref."""

    if not ferment_id:
        return {"error": "ferment_id required"}

    co2_ref = _uid("co2")
    now = _now()

    def _seal() -> int:
        store = select_belief_store()
        with store._conn() as conn:
            cursor = conn.execute(
                """
                UPDATE vertex_hakkou_ferment
                SET status = 'complete',
                    output_kind = 'structured_knowledge',
                    ethanol_hash = ?,
                    co2_audit_ref = ?,
                    updated_at = ?
                WHERE vertex_id LIKE ?
                """,
                (ethanolHash or "", co2_ref, now, f"%{ferment_id}%"),
            )
            return cursor.rowcount or 0

    updated = await asyncio.to_thread(_seal)
    LOG.info("finalize_ferment: %s updated=%d co2=%s", ferment_id, updated, co2_ref)
    return {"fermentId": ferment_id, "co2AuditRef": co2_ref, "updated": updated}


# ─── worker entrypoint ────────────────────────────────────────────────────


async def run_worker() -> None:
    gateway = os.environ.get("AGENTGATEWAY_MCP_URL", "127.0.0.1:8080")
    channel = create_langserver_channel(grpc_address=gateway)
    worker = LangServerWorker(channel)
    timeout_ms = int(os.environ.get("MYCO_YEAST_TASK_TIMEOUT_MS", "120000"))

    registrations = {
        "kabi.anastomosis_probe": task_kabi_anastomosis_probe,
        "kobo.bud_agent": task_kobo_bud_agent,
        "kobo.sporulate": task_kobo_sporulate,
        "kobo.germinate": task_kobo_germinate,
        "kinoko.check_flow_threshold": task_kinoko_check_flow_threshold,
        "hakkou.create_ferment_record": task_hakkou_create_ferment_record,
        "hakkou.llm_transform": task_hakkou_llm_transform,
        "hakkou.finalize_ferment": task_hakkou_finalize_ferment,
    }
    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(fn)

    LOG.info(
        "myco-yeast zeebe worker registered %d task types via %s",
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
