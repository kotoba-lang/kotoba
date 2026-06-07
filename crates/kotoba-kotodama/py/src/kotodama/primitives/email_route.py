"""email_route — route pregel-triaged Outlook emails to projector convos.

Task type: ``outlook.email.route``

Architecture (Phase 1 — metadata-only, no body decryption):

  SELECT pending non-sales emails from graphar.vertex_email_message (written
  by the pregel LangGraph server) that are not yet present in
  edge_email_routes_to_project.
  For each email, match against vertex_email_project_route routing rules
  (ordered by priority DESC).  If a rule matches, write:
    * edge_email_routes_to_project  (email → project)
    * INSERT into vertex_projector_message so the projector convo gets a
      notification: "New email from <from_addr> [<from_domain>]"

  Returns {routedTotal, skippedTotal, errors[]} as BPMN process variables.

Table SSoT (Alembic migration 20260512_0001):
  vertex_email_project_route  — routing rules
  edge_email_routes_to_project — routing results (FK: graphar.vertex_email_message.message_id)
Graph schema SSoT (20260512100000_vertex_email_pregel.up.sql):
  graphar.vertex_email_message — pregel LangGraph output (PK: message_id)
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_PREGEL = "did:web:pregel.etzhayyim.com"
COLLECTION_MESSAGE = "com.etzhayyim.convo.message"


def _new_vid() -> str:
    return f"email-route-{uuid.uuid4().hex[:16]}"


async def task_email_route(
    batchSize: int = 100,
    accountDid: str = "",
) -> dict[str, Any]:
    """Route clean, triaged Outlook emails to projector project convos.

    BPMN variables in:
      batchSize  (int, default 100) — max emails to process per run
      accountDid (str, default "")  — filter to a single M365 account

    BPMN variables out:
      routedTotal  (int)  — emails successfully routed to a project
      skippedTotal (int)  — clean emails with no matching routing rule
      errors       (str)  — JSON array of {messageId, error} for failed rows
    """
    batch = max(1, min(int(batchSize or 100), 500))
    account_filter = (accountDid or "").strip()

    # 1. Fetch pending non-sales emails from pregel output, not yet routed
    # R0: Order by and limit are applied in Python.
    datalog_query = """
    [:find ?message_id ?from_address ?received_at
     :where
       [?e :vertex/type "email_message"]
       [?e :email_message/response_status "pending"]
       [?e :email_message/is_sales false]
       (not-join [?e]
         [?route :edge/type "edge_email_routes_to_project"]
         [?route :email_routes_to_project/email_vertex_id ?e])
       [?e :email_message/message_id ?message_id]
       [?e :email_message/from_address ?from_address]
       [?e :email_message/received_at ?received_at
       ]
    """
    query_args = []
    if account_filter:
        datalog_query = f"[:in $ ?account_filter\n{datalog_query}"
        datalog_query += "   [?e :email_message/owner ?account_filter]\n"
        query_args.append(account_filter)

    datalog_query += "]"

    rows = get_kotoba_client().q(datalog_query, args=tuple(query_args))
    emails_raw = [
        {"message_id": r[0], "from_address": r[1], "received_at": r[2]}
        for r in rows
    ]

    # R0: SPLIT_PART, ORDER BY, and LIMIT applied in Python
    emails = []
    for email_raw in emails_raw:
        from_address = email_raw["from_address"]
        from_domain = from_address.split('@', 1)[1] if '@' in from_address else ""
        emails.append({
            "message_id": email_raw["message_id"],
            "from_address": from_address,
            "from_domain": from_domain,
            "received_at": email_raw["received_at"],
        })

    emails.sort(key=lambda x: x["received_at"], reverse=True)
    emails = emails[:batch]

    if not emails:
        return {"routedTotal": 0, "skippedTotal": 0, "errors": "[]"}

    # 2. Load all routing rules ordered by priority
    # R0: Order by is applied in Python.
    rules_raw = get_kotoba_client().select_where(
        "vertex_email_project_route", "active", True,
        columns=["rule_id", "project_slug", "convo_id", "match_type", "match_value", "priority"]
    )
    rules = sorted(
        rules_raw,
        key=lambda x: (x.get("priority", 0), x.get("rule_id", "")),
        reverse=True
    )

    now = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    routed = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for email in emails:
        from_domain = str(email.get("from_domain") or "").lower()
        from_addr = str(email.get("from_address") or "").lower()
        email_vid = email.get("message_id")
        msg_id = email.get("message_id", "")

        matched_rule: dict[str, Any] | None = None
        for rule in rules:
            mt = str(rule.get("match_type") or "").lower()
            mv = str(rule.get("match_value") or "").lower()
            if mt == "domain" and from_domain == mv:
                matched_rule = rule
                break
            if mt == "address" and from_addr == mv:
                matched_rule = rule
                break
            if mt == "domain_suffix" and from_domain.endswith(mv):
                matched_rule = rule
                break

        if matched_rule is None:
            skipped += 1
            continue

        project_slug = matched_rule["project_slug"]
        convo_id = matched_rule.get("convo_id") or f"project:{project_slug}"
        edge_vid = _new_vid()
        msg_rkey = f"pregel-{uuid.uuid4().hex[:12]}"
        msg_uri = f"at://{ACTOR_PREGEL}/{COLLECTION_MESSAGE}/{msg_rkey}"

        try:
            get_kotoba_client().insert_row(
                "edge_email_routes_to_project",
                {
                    "vertex_id": edge_vid,
                    "email_vertex_id": email_vid,
                    "project_slug": project_slug,
                    "convo_id": convo_id,
                    "rule_id": str(matched_rule.get("rule_id") or ""),
                    "matched_at": now,
                    "actor_did": ACTOR_PREGEL,
                    "created_at": now,
                },
            )
            get_kotoba_client().insert_row(
                "vertex_projector_message",
                {
                    "vertex_id": f"proj-msg-{uuid.uuid4().hex[:12]}",
                    "convo_id": convo_id,
                    "text": f"[pregel] New email from {from_addr or from_domain} "
                            f"routed to project:{project_slug}",
                    "created_at": now,
                    "actor_id": ACTOR_PREGEL,
                    "rkey": msg_rkey,
                    "uri": msg_uri,
                    "value_json": json.dumps({
                        "sourceMessageId": str(msg_id),
                        "fromDomain": from_domain,
                        "fromAddress": from_addr,
                        "matchType": matched_rule.get("match_type"),
                        "matchValue": matched_rule.get("match_value"),
                    }, ensure_ascii=False),
                },
            )
            routed += 1
        except Exception as exc:
            errors.append({"messageId": str(msg_id), "error": str(exc)[:120]})

    return {
        "routedTotal": routed,
        "skippedTotal": skipped,
        "errors": json.dumps(errors, ensure_ascii=False),
    }


def register(worker: object, *, timeout_ms: int = 60_000) -> None:
    """Wire ``outlook.email.route`` onto the shared LangServer worker."""
    worker.task(  # type: ignore[attr-defined]
        task_type="outlook.email.route",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_email_route)


__all__ = ["task_email_route", "register"]
