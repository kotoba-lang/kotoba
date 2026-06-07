"""Outlook / M365 spam-phishing triage LangGraph agent.

Graph id: ``outlook.triage.v1``
Task type: ``outlook.triage`` (registered via ``zeebe_worker_main.py``)

Architecture (Phase 4 — gmail_triage.py 横展開):

    START → claim → t1 → t2_rep ─┬─ has_gray → t3 ─┐
                                  │                  ├─→ synth → register → mark → END
                                  └─ no_gray ────────┘

Reuses pure helpers and the ``_node_t2_reputation`` / ``_node_register_yabai``
nodes from ``gmail_triage.py`` because they operate on yabai schema
(source-agnostic) and bounded reputation MV.

Outlook-specific nodes:
  - ``_node_claim``: SELECT from vertex_email_message (shared with kyber)
  - ``_node_t1``: rule classifier — **metadata-only** since subject_enc /
    body_preview_enc are signal:v1: encrypted (BEC Tier-2). Drops the
    keyword/URL signals from gmail's _phish_score and uses auth headers
    + reply-to mismatch + sender_kind + first_seen_from_domain instead.
  - ``_node_t3_llm``: LLM #1 prompt with metadata-only fields.
  - ``_node_threat_synth``: LLM #2 IOC summary, snippet replaced with
    sender_kind + first_seen flag.
  - ``_node_mark_triaged``: UPDATE vertex_email_message.

Cross-channel reputation: ``mv_yabai_sender_reputation_24h`` aggregates
evidence by entity_id (= ``email-{sanitized}`` from the address). gmail
and outlook spam from the same sender automatically share the same
yabai entity row → 360° threat picture without extra wiring.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

_log = logging.getLogger(__name__)

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives import langgraph_registry

# Reuse pure helpers + 2 source-agnostic nodes from gmail_triage
from kotodama.agents.gmail_triage import (
    ALLOWLIST_DOMAINS,
    SCORE_GRAY_LOW,
    SCORE_SPAM,
    SCORE_TRASH,
    _allowlisted,
    _domain_of,
    _node_register_yabai,
    _node_t2_reputation,
    _reputation_score_bump,
    _sanitize_addr,
    _yabai_evidence_meta,
)

ACTOR_OUTLOOK = "did:web:outlook.etzhayyim.com"


# ── Graph state ────────────────────────────────────────────────────────


class OutlookTriageState(TypedDict, total=False):
    batchSize: int
    accountDid: str
    claimed: list[dict[str, Any]]
    reputation: dict[str, dict[str, Any]]
    grayIds: list[str]
    yabaiEntities: int
    yabaiEvidence: int
    triagedTotal: int
    spamTotal: int
    trashTotal: int
    grayTotal: int
    cleanTotal: int
    llmCalls: int
    error: str


# ── Helpers (outlook-specific) ─────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _phish_score_metadata(
    spf: str, dkim: str, dmarc: str,
    reply_to: str, from_addr: str,
    sender_kind: str, first_seen_from_domain: str,
) -> tuple[int, list[str]]:
    """Outlook variant: same auth-header weights as gmail's _phish_score
    minus subject keyword + URL extraction (encrypted columns).

    Adds 2 outlook-specific signals:
      - sender_kind == 'external' + first_seen_from_domain set: +10
        (first contact from external domain = elevated phishing risk)
      - sender_kind == 'guest': +5 (cross-tenant sharing)
    """
    score = 0
    reasons: list[str] = []
    if spf and spf not in ("pass", "none"):
        score += 20
        reasons.append(f"spf={spf}")
    if dkim and dkim not in ("pass", "none"):
        score += 20
        reasons.append(f"dkim={dkim}")
    if dmarc and dmarc not in ("pass", "none"):
        score += 25
        reasons.append(f"dmarc={dmarc}")
    if reply_to and from_addr:
        rt_dom = _domain_of(reply_to)
        fr_dom = _domain_of(from_addr)
        if rt_dom and fr_dom and rt_dom != fr_dom:
            score += 15
            reasons.append(f"reply-to-mismatch:{rt_dom}!={fr_dom}")
    sk = (sender_kind or "").lower()
    if sk == "external" and (first_seen_from_domain or "").strip():
        score += 10
        reasons.append("first-contact-external")
    elif sk == "guest":
        score += 5
        reasons.append("sender-kind:guest")
    return min(score, 100), reasons


# ── Graph nodes ────────────────────────────────────────────────────────


async def _node_claim(state: OutlookTriageState) -> OutlookTriageState:
    batch = max(1, min(int(state.get("batchSize") or 50), 200))
    account_filter = (state.get("accountDid") or "").strip()
    sql_where = []
    sql_args: list[Any] = []
    if account_filter:
        sql_where.append("?accountDid = :accountDid")
        sql_args.append(account_filter)
    # R0: using Datalog q() for IS NULL and ORDER BY.
    # Note: Datalog's :in clause expects a single list of arguments for parameters.
    # We must prepend the filters to sql_args
    # Datalog query uses (not (has ?e :vertex/triaged_at)) for IS NULL
    query_edn = """
    [:find
        (pull ?e [:vertex/id :vertex/message_id :vertex/from_address
                  :vertex/from_domain :vertex/from_name :vertex/reply_to
                  :vertex/sender_kind :vertex/first_seen_from_domain
                  :vertex/spf_result :vertex/dkim_result :vertex/dmarc_result
                  :vertex/account_did :vertex/received_at])
     :in $
     :where
        [?e :vertex/type :vertex.type/email_message]
        (not (has ?e :vertex/triaged_at))
        %s
     :order-by desc ?receivedAt
     :limit %s]
    """ % (" ".join([f"[{clause}]" for clause in sql_where]), batch)

    # Datalog arguments need to be a tuple for :in $ [args...]
    datalog_args = [account_filter] if account_filter else []

    results = get_kotoba_client().q(query_edn, args=datalog_args)

    claimed = []
    for res_list in results:
        res_dict = res_list[0] # pull returns the map as the first item in the list
        # Transform datalog keys to snake_case for consistency with previous behavior
        # and to match the keys expected by downstream logic.
        # Also, remove the :vertex/ prefix
        transformed_row = {
            k.replace(':vertex/', '').replace(':', '').replace('-', '_'): v
            for k, v in res_dict.items()
        }
        claimed.append(transformed_row)
    # Normalize address column name to from_addr so shared helpers
    # (_sanitize_addr / _node_t2_reputation) see the same key as gmail.
    for row in claimed:
        if row.get("from_address") and not row.get("from_addr"):
            row["from_addr"] = row["from_address"]
    return {**state, "claimed": claimed, "llmCalls": int(state.get("llmCalls") or 0)}


async def _node_t1(state: OutlookTriageState) -> OutlookTriageState:
    """Rule-based classifier (metadata-only — encrypted body)."""
    out: list[dict[str, Any]] = []
    gray_ids: list[str] = []
    for row in state.get("claimed") or []:
        from_addr = str(row.get("from_addr") or row.get("from_address") or "")
        if _allowlisted(from_addr):
            row["classification"] = "clean"
            row["score"] = 0
            row["reasons"] = [f"allowlist:{_domain_of(from_addr)}"]
        else:
            score, reasons = _phish_score_metadata(
                str(row.get("spf_result") or ""),
                str(row.get("dkim_result") or ""),
                str(row.get("dmarc_result") or ""),
                str(row.get("reply_to") or ""),
                from_addr,
                str(row.get("sender_kind") or ""),
                str(row.get("first_seen_from_domain") or ""),
            )
            try:
                from kotodama.agents.outlook_feedback import apply_sender_prior as _asp
                score, prior_reasons = _asp(score, from_addr)
                reasons = reasons + prior_reasons
            except Exception:
                pass  # prior adjustment is best-effort
            row["score"] = score
            row["reasons"] = reasons
            if score >= SCORE_SPAM:
                row["classification"] = "spam"
            elif score >= SCORE_GRAY_LOW:
                row["classification"] = "gray"
                gray_ids.append(str(row.get("vertex_id") or ""))
            else:
                row["classification"] = "clean"
        out.append(row)
    return {**state, "claimed": out, "grayIds": gray_ids}


def _has_gray(state: OutlookTriageState) -> str:
    return "t3" if (state.get("grayIds") or []) else "synth"


async def _node_t3_llm(state: OutlookTriageState) -> OutlookTriageState:
    """LLM #1 — Murakumo re-score for gray-zone (40 <= score < 70). Capped at 5."""
    gray_ids = set(state.get("grayIds") or [])
    if not gray_ids:
        return state
    rows = [r for r in (state.get("claimed") or []) if str(r.get("vertex_id") or "") in gray_ids][:5]
    llm_calls = int(state.get("llmCalls") or 0)
    system = (
        "You are a phishing/spam triage classifier for Outlook/M365 emails. "
        "Subject and body are encrypted, so you only see metadata. "
        "Return JSON {\"classification\":\"spam|gray|clean\","
        "\"confidence\":0.0-1.0,\"reasons\":[short strings]}. "
        "Be conservative: only mark spam if metadata signals are strong "
        "(triple auth fail, reply-to mismatch, first-contact external)."
    )
    for row in rows:
        prompt = json.dumps({
            "from": row.get("from_addr"),
            "fromDomain": row.get("from_domain"),
            "fromName": row.get("from_name"),
            "replyTo": row.get("reply_to"),
            "spf": row.get("spf_result"),
            "dkim": row.get("dkim_result"),
            "dmarc": row.get("dmarc_result"),
            "senderKind": row.get("sender_kind"),
            "firstSeenFromDomain": row.get("first_seen_from_domain"),
            "ruleScore": row.get("score"),
            "ruleReasons": row.get("reasons"),
        }, ensure_ascii=False)
        try:
            result = llm.call_tier_json(
                tier="fast", system=system, user=prompt,
                max_tokens=200, temperature=0.0,
            )
            llm_calls += 1
            cls = str(result.get("classification") or "gray").lower()
            if cls not in {"spam", "gray", "clean"}:
                cls = "gray"
            conf = float(result.get("confidence") or 0.5)
            row["classification"] = cls
            row["score"] = int(round(min(99, max(0, int(row.get("score") or 0) + (20 if cls == "spam" else (-20 if cls == "clean" else 0))))))
            extra_reasons = result.get("reasons") or []
            if isinstance(extra_reasons, list):
                row["reasons"] = list(row.get("reasons") or []) + [f"t3:{str(x)[:60]}" for x in extra_reasons[:3]]
            row["reasons"].append(f"t3-conf:{conf:.2f}")
        except Exception as exc:
            row["reasons"] = list(row.get("reasons") or []) + [f"t3-err:{type(exc).__name__}"]
    return {**state, "llmCalls": llm_calls}


async def _node_threat_synth(state: OutlookTriageState) -> OutlookTriageState:
    """LLM #2 — IOC summary for confirmed spam rows. Capped at 3."""
    rows = [r for r in (state.get("claimed") or []) if str(r.get("classification") or "") == "spam"][:3]
    if not rows:
        return state
    llm_calls = int(state.get("llmCalls") or 0)
    system = (
        "You are a threat intelligence synthesizer. Given Outlook email "
        "metadata flagged as spam/phishing, produce JSON: "
        "{\"threat_type\": one of [credential_phishing, invoice_fraud, "
        "malware_delivery, business_email_compromise, tech_support_scam, "
        "generic_spam, internal_compromise], "
        "\"iocs\": [up to 5 short strings — domains, sender handles, headers], "
        "\"summary\": \"2-sentence English threat description\", "
        "\"recommended_action\": one of [block_sender, block_domain, "
        "report_to_msrc, ignore, manual_review]}."
    )
    for row in rows:
        prompt = json.dumps({
            "from": row.get("from_addr"),
            "fromDomain": row.get("from_domain"),
            "fromName": row.get("from_name"),
            "replyTo": row.get("reply_to"),
            "senderKind": row.get("sender_kind"),
            "firstSeenFromDomain": row.get("first_seen_from_domain"),
            "ruleScore": row.get("score"),
            "ruleReasons": row.get("reasons"),
        }, ensure_ascii=False)
        try:
            result = llm.call_tier_json(
                tier="fast", system=system, user=prompt,
                max_tokens=300, temperature=0.0,
            )
            llm_calls += 1
            threat_type = str(result.get("threat_type") or "generic_spam")[:50]
            iocs = result.get("iocs") or []
            if not isinstance(iocs, list):
                iocs = []
            iocs = [str(x)[:80] for x in iocs[:5]]
            summary = str(result.get("summary") or "")[:300]
            action = str(result.get("recommended_action") or "manual_review")[:30]
            row["iocDescription"] = json.dumps({
                "threat_type": threat_type,
                "iocs": iocs,
                "summary": summary,
                "recommended_action": action,
            }, ensure_ascii=False)[:480]
        except Exception as exc:
            row["reasons"] = list(row.get("reasons") or []) + [f"synth-err:{type(exc).__name__}"]
    return {**state, "llmCalls": llm_calls}


async def _node_invoke_pregel(state: OutlookTriageState) -> OutlookTriageState:
    """For each clean email, submit to pregel_triage for intent classification.

    subject/body are encrypted (BEC Tier-2); pregel falls back to the
    sender-heuristic path.  Errors are non-fatal — triage has already completed.
    """
    clean_rows = [r for r in (state.get("claimed") or []) if r.get("classification") == "clean"]
    if not clean_rows:
        return state
    try:
        from kotodama.pregel.graph import build_graph as _pregel_build
        _pregel = _pregel_build()
        for row in clean_rows:
            msg_id = str(row.get("message_id") or row.get("vertex_id") or "")
            if not msg_id:
                continue
            try:
                await _pregel.ainvoke({
                    "message_id": msg_id,
                    "from_address": str(row.get("from_address") or ""),
                    "from_name": str(row.get("from_name") or ""),
                    "to_addresses": str(row.get("account_did") or ""),
                    "subject": "",
                    "received_at": str(row.get("received_at") or ""),
                    "body_preview": str(row.get("from_name") or ""),
                })
            except Exception as exc:
                _log.warning("[outlook_triage][invoke_pregel] msg=%s %s", msg_id, exc)
    except Exception as exc:
        _log.warning("[outlook_triage][invoke_pregel] setup failed: %s", exc)
    return state


async def _node_mark_triaged(state: OutlookTriageState) -> OutlookTriageState:
    rows = state.get("claimed") or []
    if not rows:
        return {**state, "triagedTotal": 0, "spamTotal": 0, "trashTotal": 0, "grayTotal": 0, "cleanTotal": 0}
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    counts = {"spam": 0, "trash": 0, "gray": 0, "clean": 0}
    for row in rows:
        vid = row.get("vertex_id")
        if not vid:
            continue
        cls = str(row.get("classification") or "clean")
        counts[cls] = counts.get(cls, 0) + 1
        score = int(row.get("score") or 0)
        reasons_csv = ",".join(str(x) for x in (row.get("reasons") or []))[:480]

        # Use insert_row for UPSERT behavior on vertex_email_message
        get_kotoba_client().insert_row(
            "vertex_email_message",
            {
                "vertex_id": vid,
                "triaged_at": now,
                "triage_classification": cls,
                "triage_score": score,
                "triage_reasons": reasons_csv,
            },
        )
    return {
        **state,
        "triagedTotal": len(rows),
        "spamTotal": counts["spam"],
        "trashTotal": counts["trash"],
        "grayTotal": counts["gray"],
        "cleanTotal": counts["clean"],
    }


# ── Graph compile ──────────────────────────────────────────────────────


def _build_graph() -> Any:
    builder: StateGraph = StateGraph(OutlookTriageState)
    builder.add_node("claim", _node_claim)
    builder.add_node("t1", _node_t1)
    builder.add_node("t2_rep", _node_t2_reputation)   # shared with gmail_triage
    builder.add_node("t3", _node_t3_llm)
    builder.add_node("synth", _node_threat_synth)
    builder.add_node("register", _node_register_yabai)  # shared with gmail_triage
    builder.add_node("mark", _node_mark_triaged)
    builder.add_node("invoke_pregel", _node_invoke_pregel)
    builder.add_edge(START, "claim")
    builder.add_edge("claim", "t1")
    builder.add_edge("t1", "t2_rep")
    builder.add_conditional_edges("t2_rep", _has_gray, {"t3": "t3", "synth": "synth"})
    builder.add_edge("t3", "synth")
    builder.add_edge("synth", "register")
    builder.add_edge("register", "mark")
    builder.add_edge("mark", "invoke_pregel")
    builder.add_edge("invoke_pregel", END)
    return builder.compile()


outlook_triage_graph = _build_graph()
langgraph_registry.register("outlook.triage.v1", outlook_triage_graph)


def register(worker: object, *, timeout_ms: int = 120_000) -> None:
    """Wire ``outlook.triage`` onto the shared LangServer worker.

    The job variables mirror the LangGraph state fields so the BPMN ioMapping
    can drive batch size and per-account filtering without code changes:

      batchSize   (int, optional, default 50)  — max rows to claim per run
      accountDid  (str, optional, default "")  — filter to a single M365 account
    """

    async def _task(batchSize: int = 50, accountDid: str = "") -> dict:
        from langgraph.errors import GraphRecursionError  # type: ignore

        try:
            result = await outlook_triage_graph.ainvoke(
                {"batchSize": batchSize, "accountDid": accountDid}
            )
        except GraphRecursionError as exc:
            return {"error": f"recursion:{exc}", "triagedTotal": 0}
        except Exception as exc:
            return {"error": str(exc), "triagedTotal": 0}
        return {
            "triagedTotal": result.get("triagedTotal", 0),
            "spamTotal": result.get("spamTotal", 0),
            "cleanTotal": result.get("cleanTotal", 0),
            "grayTotal": result.get("grayTotal", 0),
            "llmCalls": result.get("llmCalls", 0),
        }

    worker.task(task_type="outlook.triage", single_value=False, timeout_ms=timeout_ms)(_task)  # type: ignore[attr-defined]


__all__ = ["outlook_triage_graph", "OutlookTriageState", "_phish_score_metadata", "register"]
