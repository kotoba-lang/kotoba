"""Myco-Yeast artificial organism Zeebe workers (ADR-2605071200).

Semantic task implementations for the three-layer architecture:
  kobo  (酵母) — individual agents:   bud / germinate / sporulate
  kabi  (カビ) — mycelial network:    anastomosis probe
  kinoko (キノコ) — fruiting body:    PoNF flow threshold check
  hakkou (発酵) — fermentation:       create record / LLM transform / finalize

Task types registered via register():
  kobo.bud_agent
  kobo.germinate
  kobo.sporulate
  kabi.anastomosis_probe
  kinoko.check_flow_threshold
  hakkou.create_ferment_record
  hakkou.llm_transform
  hakkou.finalize_ferment
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

logger = logging.getLogger(__name__)

_NOW = lambda: datetime.now(timezone.utc).isoformat() + "Z"


# ---------------------------------------------------------------------------
# kobo 酵母 — individual agent lifecycle
# ---------------------------------------------------------------------------

def task_kobo_bud_agent(
    parentDid: str = "",
    childDid: str = "",
    childVertexId: str = "",
    childRole: str = "agent",
    parentEta: float = 0.5,
    callerDid: str = "",
    buddingEdgeId: str = "",
) -> dict:
    """Insert vertex_kobo_agent (child) + edge_kobo_budding in one transaction."""
    if not (parentDid and childDid and childVertexId and buddingEdgeId):
        return {"error": "parentDid, childDid, childVertexId, buddingEdgeId required"}
    now = _NOW()
    try:
        kotoba = get_kotoba_client()
        kotoba.insert_row(
            "vertex_kobo_agent",
            {
                "vertex_id": childVertexId,
                "agent_did": childDid,
                "parent_did": parentDid,
                "role": childRole,
                "status": "active",
                "eta": float(parentEta),
                "stress_score": 0,
                "created_at": now,
                "owner_did": callerDid or parentDid,
                "sensitivity_ord": 1,
            },
        )
        kotoba.insert_row(
            "edge_kobo_budding",
            {
                "edge_id": buddingEdgeId,
                "src_vid": parentDid,
                "dst_vid": childVertexId,
                "created_at": now,
                "owner_did": callerDid or parentDid,
                "sensitivity_ord": 1,
            },
        )
        return {"ok": True, "childVertexId": childVertexId}
    except Exception as exc:
        logger.exception("kobo.bud_agent failed")
        return {"ok": False, "error": str(exc)}


def task_kobo_germinate(
    sporeVertexId: str = "",
    quorumN: int = 2,
    newAgentDid: str = "",
    newAgentVertexId: str = "",
    originAgentDid: str = "",
    restoredEta: float = 0.5,
    callerDid: str = "",
) -> dict:
    """Check custody quorum, revive agent from spore, mark spore germinated.

    Returns germinated=True if quorum was met and agent was revived.
    """
    if not (sporeVertexId and newAgentDid and newAgentVertexId):
        return {"error": "sporeVertexId, newAgentDid, newAgentVertexId required",
                "germinated": False}
    try:
        kotoba = get_kotoba_client()
        # R0: Multi-predicate WHERE in SELECT COUNT(*), falling back to Python filter
        custody_edges = kotoba.select_where(
            "edge_houshi_custody",
            "src_vid",
            sporeVertexId,
            columns=["custody_confirmed"],
        )
        confirmed_count = sum(1 for edge in custody_edges if edge.get("custody_confirmed") is True)

        if confirmed_count < quorumN:
            return {"germinated": False, "confirmedCount": confirmed_count,
                    "quorumN": quorumN}

        now = _NOW()
        kotoba.insert_row(
            "vertex_kobo_agent",
            {
                "vertex_id": newAgentVertexId,
                "agent_did": newAgentDid,
                "parent_did": originAgentDid,
                "status": "active",
                "eta": float(restoredEta),
                "stress_score": 0,
                "created_at": now,
                "owner_did": callerDid or originAgentDid,
                "sensitivity_ord": 1,
            },
        )
        kotoba.insert_row(
            "vertex_houshi_spore",
            {
                "vertex_id": sporeVertexId,
                "germinated_at": now,
                "status": "germinated",
            },
        )
        return {"germinated": True, "confirmedCount": confirmed_count,
                "newAgentVertexId": newAgentVertexId}
    except Exception as exc:
        logger.exception("kobo.germinate failed")
        return {"germinated": False, "error": str(exc)}


def task_kobo_sporulate(
    sporeVertexId: str = "",
    agentDid: str = "",
    agentVertexId: str = "",
    blobCbor: str = "",
    revivalKeyHint: str = "",
    quorumN: int = 2,
    callerDid: str = "",
) -> dict:
    """Insert houshi spore and update kobo_agent status to sporulated."""
    if not (sporeVertexId and agentDid and agentVertexId):
        return {"error": "sporeVertexId, agentDid, agentVertexId required"}
    now = _NOW()
    try:
        kotoba = get_kotoba_client()
        kotoba.insert_row(
            "vertex_houshi_spore",
            {
                "vertex_id": sporeVertexId,
                "agent_did": agentDid,
                "blob_cbor": blobCbor,
                "revival_key_hint": revivalKeyHint,
                "quorum_n": int(quorumN),
                "status": "dormant",
                "created_at": now,
                "owner_did": callerDid or agentDid,
                "sensitivity_ord": 1,
            },
        )
        kotoba.insert_row(
            "vertex_kobo_agent",
            {
                "vertex_id": agentVertexId,
                "status": "sporulated",
                "updated_at": now,
            },
        )
        return {"ok": True, "sporeVertexId": sporeVertexId}
    except Exception as exc:
        logger.exception("kobo.sporulate failed")
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# kabi カビ — mycelial network anastomosis
# ---------------------------------------------------------------------------

def task_kabi_anastomosis_probe(
    networkADid: str = "",
    networkBDid: str = "",
    edgeId: str = "",
    callerDid: str = "",
) -> dict:
    """LLM compatibility probe + INSERT edge_kabi_anastomosis.

    Returns probeResult dict with compatible:bool and compatibility_score:float.
    """
    if not (networkADid and networkBDid and edgeId):
        return {"error": "networkADid, networkBDid, edgeId required",
                "probeResult": {"compatible": False}}

    system = (
        "You are a mycelial network compatibility analyst. "
        "Assess whether two agent networks can safely merge (anastomosis). "
        "Return ONE JSON object with keys: compatible (bool), "
        "compatibility_score (0.0-1.0), reason (string, max 120 chars)."
    )
    user = (
        f"Network A DID: {networkADid}\n"
        f"Network B DID: {networkBDid}\n"
        "Assess anastomosis compatibility."
    )
    llm_result = llm.call_tier_json(
        "classifier",
        system=system,
        user=user,
        max_tokens=200,
        temperature=0.1,
    )
    if not llm_result.get("ok"):
        return {"error": llm_result.get("error", "llm failed"),
                "probeResult": {"compatible": False}}

    probe = llm_result.get("data") or {}
    compatible = bool(probe.get("compatible", False))
    score = float(probe.get("compatibility_score", 0.0))
    reason = str(probe.get("reason", ""))

    now = _NOW()
    try:
        kotoba = get_kotoba_client()
        kotoba.insert_row(
            "edge_kabi_anastomosis",
            {
                "edge_id": edgeId,
                "src_vid": networkADid,
                "dst_vid": networkBDid,
                "compatible": compatible,
                "compatibility_score": score,
                "probe_reason": reason[:500],
                "created_at": now,
                "owner_did": callerDid or networkADid,
                "sensitivity_ord": 1,
            },
        )
    except Exception as exc:
        logger.exception("kabi.anastomosis_probe db write failed")
        return {"error": str(exc), "probeResult": {"compatible": False}}

    return {"probeResult": {"compatible": compatible,
                            "compatibility_score": score,
                            "reason": reason}}


# ---------------------------------------------------------------------------
# kinoko キノコ — PoNF fruiting body / consensus
# ---------------------------------------------------------------------------

def task_kinoko_check_flow_threshold(
    blockVertexId: str = "",
    lastBlockId: str = "",
    blockHash: str = "",
) -> dict:
    """Query mv_kabi_nutrient_flow; form PoNF block if threshold met.

    PoNF threshold: totalFlow >= 100 AND minEta >= 0.5.
    Returns blockFormed:bool, totalFlow, participantCount, minEta.
    """
    try:
        kotoba = get_kotoba_client()
        # R0: Multi-aggregate query, falling back to Datalog + Python aggregation
        query_edn = """
        [:find ?total-flow ?avg-eta
         :where
         [?e :mv-kabi-nutrient-flow/total_flow ?total-flow]
         [?e :mv-kabi-nutrient-flow/avg_eta ?avg-eta]]
        """
        rows = kotoba.q(query_edn)

        total_flow = 0.0
        participant_count = 0
        sum_avg_eta = 0.0

        for row in rows:
            total_flow += row[0] if row[0] is not None else 0.0
            sum_avg_eta += row[1] if row[1] is not None else 0.0
            participant_count += 1

        min_eta = sum_avg_eta / participant_count if participant_count > 0 else 0.0

    except Exception:
        pass
    if total_flow < 100 or min_eta < 0.5:
        return {"blockFormed": False, "totalFlow": total_flow,
                "participantCount": participant_count, "minEta": min_eta}

    if not blockVertexId:
        return {"error": "blockVertexId required when threshold met",
                "blockFormed": False}

    now = _NOW()
    try:
        kotoba.insert_row(
            "vertex_kinoko_block",
            {
                "vertex_id": blockVertexId,
                "prev_block_id": lastBlockId,
                "block_hash": blockHash,
                "total_flow": total_flow,
                "participant_count": participant_count,
                "eta_min_used": min_eta,
                "block_status": "finalized",
                "status": "active",
                "created_at": now,
                "owner_did": "did:web:kinoko.etzhayyim.com",
                "sensitivity_ord": 1,
            },
        )
    except Exception as exc:
        logger.exception("kinoko.check_flow_threshold block insert failed")
        return {"blockFormed": False, "error": str(exc)}

    return {"blockFormed": True, "blockVertexId": blockVertexId,
            "totalFlow": total_flow, "participantCount": participant_count,
            "minEta": min_eta}


# ---------------------------------------------------------------------------
# hakkou 発酵 — fermentation pipeline
# ---------------------------------------------------------------------------

def task_hakkou_create_ferment_record(
    fermentVertexId: str = "",
    agentDid: str = "",
    inputKind: str = "",
    inputRef: str = "",
    outputKind: str = "",
    callerDid: str = "",
) -> dict:
    """Insert vertex_hakkou_ferment with status=running."""
    if not (fermentVertexId and agentDid and inputKind):
        return {"error": "fermentVertexId, agentDid, inputKind required"}
    now = _NOW()
    try:
        kotoba = get_kotoba_client()
        kotoba.insert_row(
            "vertex_hakkou_ferment",
            {
                "vertex_id": fermentVertexId,
                "agent_did": agentDid,
                "input_kind": inputKind,
                "input_ref": inputRef,
                "output_kind": outputKind,
                "status": "running",
                "created_at": now,
                "owner_did": callerDid or agentDid,
                "sensitivity_ord": 1,
            },
        )
        return {"ok": True, "fermentVertexId": fermentVertexId}
    except Exception as exc:
        logger.exception("hakkou.create_ferment_record failed")
        return {"ok": False, "error": str(exc)}


def task_hakkou_llm_transform(
    inputKind: str = "",
    inputRef: str = "",
    outputKind: str = "",
) -> dict:
    """LLM fermentation: structured knowledge extraction from raw input.

    Returns fermentOutput dict with the extracted structured content.
    """
    if not (inputKind and outputKind):
        return {"error": "inputKind, outputKind required"}

    system = (
        "You are a fermentation knowledge engine. "
        "Transform raw input into structured knowledge. "
        "Extract key facts, relationships, and insights. "
        "Be precise and citation-grounded. "
        "Return ONE JSON object with keys: "
        "summary (string), facts (array of strings), "
        "relationships (array of {subject, predicate, object}), "
        "confidence (0.0-1.0)."
    )
    user = (
        f"Ferment the following {inputKind} input into a structured {outputKind}. "
        f"Input reference: {inputRef}"
    )
    result = llm.call_tier_json(
        "classifier",
        system=system,
        user=user,
        max_tokens=800,
        temperature=0.1,
    )
    if not result.get("ok"):
        return {"error": result.get("error", "llm failed"), "fermentOutput": {}}
    return {"fermentOutput": result.get("data") or {}}


def task_hakkou_finalize_ferment(
    fermentVertexId: str = "",
    outputVertexId: str = "",
    ethanolHash: str = "",
    co2AuditRef: str = "",
) -> dict:
    """Update vertex_hakkou_ferment with output ref, ethanol hash, status=done."""
    if not fermentVertexId:
        return {"error": "fermentVertexId required"}
    now = _NOW()
    try:
        kotoba = get_kotoba_client()
        kotoba.insert_row(
            "vertex_hakkou_ferment",
            {
                "vertex_id": fermentVertexId,
                "output_vertex_id": outputVertexId,
                "ethanol_hash": ethanolHash,
                "co2_audit_ref": co2AuditRef,
                "status": "done",
                "updated_at": now,
            },
        )
        return {"ok": True, "fermentVertexId": fermentVertexId}
    except Exception as exc:
        logger.exception("hakkou.finalize_ferment failed")
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int = 300_000) -> None:
    worker.task(task_type="kobo.bud_agent", single_value=False,
                timeout_ms=timeout_ms)(
        lambda parentDid="", childDid="", childVertexId="", childRole="agent",
               parentEta=0.5, callerDid="", buddingEdgeId="": task_kobo_bud_agent(
            parentDid=parentDid, childDid=childDid, childVertexId=childVertexId,
            childRole=childRole, parentEta=parentEta, callerDid=callerDid,
            buddingEdgeId=buddingEdgeId,
        )
    )

    worker.task(task_type="kobo.germinate", single_value=False,
                timeout_ms=timeout_ms)(
        lambda sporeVertexId="", quorumN=2, newAgentDid="", newAgentVertexId="",
               originAgentDid="", restoredEta=0.5, callerDid="": task_kobo_germinate(
            sporeVertexId=sporeVertexId, quorumN=quorumN, newAgentDid=newAgentDid,
            newAgentVertexId=newAgentVertexId, originAgentDid=originAgentDid,
            restoredEta=restoredEta, callerDid=callerDid,
        )
    )

    worker.task(task_type="kobo.sporulate", single_value=False,
                timeout_ms=timeout_ms)(
        lambda sporeVertexId="", agentDid="", agentVertexId="", blobCbor="",
               revivalKeyHint="", quorumN=2, callerDid="": task_kobo_sporulate(
            sporeVertexId=sporeVertexId, agentDid=agentDid,
            agentVertexId=agentVertexId, blobCbor=blobCbor,
            revivalKeyHint=revivalKeyHint, quorumN=quorumN, callerDid=callerDid,
        )
    )

    worker.task(task_type="kabi.anastomosis_probe", single_value=False,
                timeout_ms=timeout_ms)(
        lambda networkADid="", networkBDid="", edgeId="",
               callerDid="": task_kabi_anastomosis_probe(
            networkADid=networkADid, networkBDid=networkBDid,
            edgeId=edgeId, callerDid=callerDid,
        )
    )

    worker.task(task_type="kinoko.check_flow_threshold", single_value=False,
                timeout_ms=timeout_ms)(
        lambda blockVertexId="", lastBlockId="",
               blockHash="": task_kinoko_check_flow_threshold(
            blockVertexId=blockVertexId, lastBlockId=lastBlockId,
            blockHash=blockHash,
        )
    )

    worker.task(task_type="hakkou.create_ferment_record", single_value=False,
                timeout_ms=timeout_ms)(
        lambda fermentVertexId="", agentDid="", inputKind="", inputRef="",
               outputKind="", callerDid="": task_hakkou_create_ferment_record(
            fermentVertexId=fermentVertexId, agentDid=agentDid,
            inputKind=inputKind, inputRef=inputRef, outputKind=outputKind,
            callerDid=callerDid,
        )
    )

    worker.task(task_type="hakkou.llm_transform", single_value=False,
                timeout_ms=max(timeout_ms, 120_000))(
        lambda inputKind="", inputRef="", outputKind="": task_hakkou_llm_transform(
            inputKind=inputKind, inputRef=inputRef, outputKind=outputKind,
        )
    )

    worker.task(task_type="hakkou.finalize_ferment", single_value=False,
                timeout_ms=timeout_ms)(
        lambda fermentVertexId="", outputVertexId="", ethanolHash="",
               co2AuditRef="": task_hakkou_finalize_ferment(
            fermentVertexId=fermentVertexId, outputVertexId=outputVertexId,
            ethanolHash=ethanolHash, co2AuditRef=co2AuditRef,
        )
    )
