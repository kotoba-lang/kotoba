"""crm_lei_review_loop — LangGraph loop for CRM ↔ GLEIF LEI review.

Graph:
  load_review_queue -> maybe_interrupt -> mark_waiting -> END

The MCP server owns writes that verify/reject LEI matches. This graph is the
checkpointed orchestration layer: it loads queue rows, interrupts when human
evidence is needed, and marks queue rows as waiting for review.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client


class CrmLeiReviewState(TypedDict, total=False):
    crmSystem: str
    entityType: str
    country: str
    limit: int
    queueItems: list[dict[str, Any]]
    queueCount: int
    needsHumanReview: bool
    interruptPayload: dict[str, Any]
    markedCount: int
    ok: bool
    error: str | None





def load_review_queue(state: CrmLeiReviewState) -> dict[str, Any]:
    limit = int(state.get("limit") or 20)
    limit = max(1, min(limit, 100))
    client = get_kotoba_client()
    # R0: Complex filtering and ordering requires raw Datalog query.
    find_clause = '[:find ?vertex-id ?review-id ?crm-system ?crm-entity-type ?crm-source-id ?crm-legal-name ?crm-country ?review-status ?review-reason ?candidate-count ?candidates-json ?priority ?evidence-note'
    where_clauses = [
        ':where',
        '[?e :vertex.crm-lei-review-queue/review-status ?review-status]',
        '[(contains? #{"open" "needs_human_review"} ?review-status)]',
        '[?e :vertex.crm-lei-review-queue/vertex-id ?vertex-id]',
        '[?e :vertex.crm-lei-review-queue/review-id ?review-id]',
        '[?e :vertex.crm-lei-review-queue/crm-system ?crm-system]',
        '[?e :vertex.crm-lei-review-queue/crm-entity-type ?crm-entity-type]',
        '[?e :vertex.crm-lei-review-queue/crm-source-id ?crm-source-id]',
        '[?e :vertex.crm-lei-review-queue/crm-legal-name ?crm-legal-name]',
        '[?e :vertex.crm-lei-review-queue/crm-country ?crm-country]',
        '[?e :vertex.crm-lei-review-queue/review-reason ?review-reason]',
        '[?e :vertex.crm-lei-review-queue/candidate-count ?candidate-count]',
        '[?e :vertex.crm-lei-review-queue/candidates-json ?candidates-json]',
        '[?e :vertex.crm-lei-review-queue/priority ?priority]',
        '[?e :vertex.crm-lei-review-queue/evidence-note ?evidence-note]'
    ]

    if state.get("crmSystem"):
        where_clauses.append(f'[?e :vertex.crm-lei-review-queue/crm-system "{state["crmSystem"]}"]')
    if state.get("entityType"):
        where_clauses.append(f'[?e :vertex.crm-lei-review-queue/crm-entity-type "{state["entityType"]}"]')
    if state.get("country"):
        where_clauses.append(f'[?e :vertex.crm-lei-review-queue/crm-country "{str(state["country"]).upper()}"]')

    order_by_clause = ':order-by [?priority :desc] [?e :db/txInstant :desc]' # Assuming updated_at maps to db/txInstant
    limit_clause = f':limit {limit}]'

    query_edn = ' '.join([find_clause] + where_clauses + [order_by_clause] + [limit_clause])

    raw_rows = client.q(query_edn)

    cols = [
        "vertex_id", "review_id", "crm_system", "crm_entity_type",
        "crm_source_id", "crm_legal_name", "crm_country", "review_status",
        "review_reason", "candidate_count", "candidates_json", "priority",
        "evidence_note"
    ]
    rows = [dict(zip(cols, row, strict=False)) for row in raw_rows]

    return {
        "queueItems": rows,
        "queueCount": len(rows),
        "needsHumanReview": bool(rows),
        "ok": True,
        "error": None,
    }


def maybe_interrupt(state: CrmLeiReviewState) -> dict[str, Any]:
    items = state.get("queueItems") or []
    if not items:
        return {"needsHumanReview": False, "interruptPayload": {}}
    payload = {
        "kind": "crm_lei_review",
        "message": "Review unresolved CRM legal entities and verify/reject LEI candidates through openLei.crm.bridge.review.",
        "items": items,
    }
    try:
        from langgraph.types import interrupt

        decision = interrupt(payload)
        return {"interruptPayload": payload, "reviewDecision": decision, "needsHumanReview": True}
    except Exception:
        return {"interruptPayload": payload, "needsHumanReview": True}


def mark_waiting(state: CrmLeiReviewState) -> dict[str, Any]:
    client = get_kotoba_client()
    items = state.get("queueItems") or []
    count = 0
    for item in items:
        vertex_id = item.get("vertex_id")
        if not vertex_id:
            continue

        # Fetch the current item to check its status
        current_item = client.select_first_where(
            "vertex_crm_lei_review_item", "vertex_id", vertex_id
        )

        if current_item and current_item.get("review_status") == "open":
            updated_item = current_item.copy()
            updated_item.update(
                review_status="needs_human_review",
                updated_at=datetime.now(timezone.utc).isoformat(),
                evidence_note="crm_lei_review_loop interrupted for human LEI evidence review",
            )
            # Use insert_row for upsert functionality
            client.insert_row("vertex_crm_lei_review_item", updated_item)
            count += 1
    return {"markedCount": count}





def _route_after_load(state: CrmLeiReviewState) -> str:
    return "interrupt" if state.get("queueCount", 0) else "done"


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(CrmLeiReviewState)
    builder.add_node("load_review_queue", load_review_queue)
    builder.add_node("maybe_interrupt", maybe_interrupt)
    builder.add_node("mark_waiting", mark_waiting)
    builder.set_entry_point("load_review_queue")
    builder.add_conditional_edges(
        "load_review_queue",
        _route_after_load,
        {"interrupt": "maybe_interrupt", "done": END},
    )
    builder.add_edge("maybe_interrupt", "mark_waiting")
    builder.add_edge("mark_waiting", END)
    return builder.compile()
