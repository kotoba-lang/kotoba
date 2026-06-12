"""
lawfirm.sales.* + lawfirm.mail.replyWebhook — LangServer handlers.

Task types:
  lawfirm.mail.replyWebhook        Match incoming mail reply → outreach event + stage advance
  lawfirm.sales.pipelineTransition Update lead stage with audit row
  lawfirm.sales.recordOutreach     Record outbound touchpoint manually

ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.sales")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _vid(kind: str) -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"







# ── Stage advance map ────────────────────────────────────────────────────────

_STAGE_ON_REPLY = {
    "lead":              "contacted",   # never possible (reply requires outbound first)
    "contacted":         "engaged",
    "engaged":           "engaged",     # idempotent
    "meeting_requested": "meeting_set",
    "meeting_set":       "meeting_set",
    "pilot":             "pilot",
    "paid":              "paid",
}


# ── Task: lawfirm.mail.replyWebhook ──────────────────────────────────────────

async def task_lawfirm_mail_reply_webhook(
    message_id: str = "",
    in_reply_to: str = "",
    from_email: str = "",
    from_name: str = "",
    to_emails: list[str] | None = None,
    subject: str = "",
    body_preview: str = "",
    received_at: str = "",
    graph_event_id: str = "",
    raw_headers: str = "",
) -> dict:
    """Match incoming reply to a tracked lead, persist event, advance stage."""
    if not from_email:
        return {"ok": False, "error": "from_email required"}

    # Idempotency check
    if graph_event_id:
        dup = get_kotoba_client().select_first_where(
            "vertex_lawfirm_outreach_event", "asset_uri", f"graph://{graph_event_id}"
        )
        if dup:
            return {"ok": True, "matched_lead_id": "", "stage_advanced": False, "duplicate": True}

    # Match strategy: domain → target_email substring → subject keyword
    domain = from_email.split("@")[-1].lower() if "@" in from_email else ""

    # R0: Datalog doesn't directly support SQL LIKE/LOWER in patterns,
    # so fetching relevant fields and filtering in Python.
    datalog_query = """
[:find ?lead_id ?stage ?target_email ?target_name
 :where
 [?e :vertex/type :vertex_lawfirm_lead]
 [?e :vertex_lawfirm_lead/lead_id ?lead_id]
 [?e :vertex_lawfirm_lead/stage ?stage]
 [?e :vertex_lawfirm_lead/target_email ?target_email]
 [?e :vertex_lawfirm_lead/target_name ?target_name]]
"""
    raw_results = get_kotoba_client().q(datalog_query)

    rows = []
    domain_lower = domain.lower()
    domain_first_part_lower = domain.split('.')[0].lower() if domain.split('.') else "" # Handle empty domain split

    for r in raw_results:
        lead_id, stage, target_email, target_name = r
        if (domain_lower and domain_lower in target_email.lower()) or \
           (domain_first_part_lower and domain_first_part_lower in target_name.lower()):
            rows.append({"lead_id": lead_id, "stage": stage})
        if len(rows) >= 5: # Apply LIMIT 5 here
            break
    matched_lead_id = ""
    matched_stage = ""
    if rows:
        matched_lead_id = rows[0]["lead_id"]
        matched_stage = rows[0]["stage"]

    # Persist inbound outreach event
    event_uri = _vid("outreachEvent")
    get_kotoba_client().insert_row(
        "vertex_lawfirm_outreach_event",
        {
            "vertex_id": event_uri,
            "lead_id": matched_lead_id,
            "event_kind": "reply_received",
            "channel": "email",
            "direction": "in",
            "subject": subject[:500],
            "body_preview": body_preview[:1500],
            "asset_uri": f"graph://{graph_event_id}" if graph_event_id else "",
            "occurred_at": received_at or _now_iso(),
            "actor_did": from_email,
            "created_at": _now_iso(),
            "owner_did": _FIRM_DID,
        },
    )

    stage_advanced = False
    new_stage = matched_stage
    if matched_lead_id and matched_stage in _STAGE_ON_REPLY:
        nxt = _STAGE_ON_REPLY[matched_stage]
        if nxt != matched_stage:
            get_kotoba_client().insert_row(
                "vertex_lawfirm_lead",
                {
                    "lead_id": matched_lead_id, # Identity column
                    "stage": nxt,
                    "last_reply_at": _now_iso(),
                    "last_touch_at": _now_iso(),
                },
            )
            get_kotoba_client().insert_row(
                "vertex_lawfirm_pipeline_stage",
                {
                    "vertex_id": _vid("pipelineStage"),
                    "lead_id": matched_lead_id,
                    "from_stage": matched_stage,
                    "to_stage": nxt,
                    "transitioned_at": _now_iso(),
                    "reason": "mail_reply_received",
                    "decided_by_did": from_email,
                    "created_at": _now_iso(),
                    "owner_did": _FIRM_DID,
                },
            )
            stage_advanced = True
            new_stage = nxt

    LOG.info(
        "mail reply matched lead=%s domain=%s advanced=%s new_stage=%s",
        matched_lead_id, domain, stage_advanced, new_stage,
    )
    return {
        "ok":                  True,
        "matched_lead_id":     matched_lead_id,
        "outreach_event_uri":  event_uri,
        "stage_advanced":      stage_advanced,
        "new_stage":           new_stage,
    }


# ── Task: lawfirm.sales.pipelineTransition ───────────────────────────────────

_VALID_STAGES = {
    "lead", "contacted", "engaged", "meeting_requested", "meeting_set",
    "demo", "pilot", "paid", "lost", "declined_conflict",
}


async def task_lawfirm_pipeline_transition(
    lead_id: str = "",
    to_stage: str = "",
    reason: str = "",
    decided_by_did: str = "",
) -> dict:
    if not lead_id or to_stage not in _VALID_STAGES:
        return {"ok": False, "error": f"invalid lead_id or stage: {to_stage!r}"}

    cur = get_kotoba_client().select_first_where("vertex_lawfirm_lead", "lead_id", lead_id, columns=["stage"])
    if not cur:
        return {"ok": False, "error": f"lead not found: {lead_id}"}
    from_stage = cur["stage"]

    get_kotoba_client().insert_row(
        "vertex_lawfirm_lead",
        {
            "lead_id": lead_id, # Identity column
            "stage": to_stage,
            "last_touch_at": _now_iso(),
        },
    )
    get_kotoba_client().insert_row(
        "vertex_lawfirm_pipeline_stage",
        {
            "vertex_id": _vid("pipelineStage"),
            "lead_id": lead_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "transitioned_at": _now_iso(),
            "reason": reason[:500],
            "decided_by_did": decided_by_did or _FIRM_DID,
            "created_at": _now_iso(),
            "owner_did": _FIRM_DID,
        },
    )
    LOG.info("pipeline transition lead=%s %s → %s by %s", lead_id, from_stage, to_stage, decided_by_did)
    return {"ok": True, "lead_id": lead_id, "from_stage": from_stage, "to_stage": to_stage}


# ── Task: lawfirm.sales.recordOutreach ───────────────────────────────────────

async def task_lawfirm_record_outreach(
    lead_id: str = "",
    event_kind: str = "mail_sent",
    channel: str = "email",
    direction: str = "out",
    subject: str = "",
    body_preview: str = "",
    asset_uri: str = "",
    actor_did: str = "",
) -> dict:
    if not lead_id:
        return {"ok": False, "error": "lead_id required"}
    event_uri = _vid("outreachEvent")
    get_kotoba_client().insert_row(
        "vertex_lawfirm_outreach_event",
        {
            "vertex_id": event_uri,
            "lead_id": lead_id,
            "event_kind": event_kind,
            "channel": channel,
            "direction": direction,
            "subject": subject[:500],
            "body_preview": body_preview[:1500],
            "asset_uri": asset_uri,
            "occurred_at": _now_iso(),
            "actor_did": actor_did,
            "created_at": _now_iso(),
            "owner_did": _FIRM_DID,
        },
    )
    if direction == "out":
        get_kotoba_client().insert_row(
            "vertex_lawfirm_lead",
            {
                "lead_id": lead_id, # Identity column
                "last_touch_at": _now_iso(),
            },
        )
    return {"ok": True, "event_uri": event_uri}


# ── Worker registration ──────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.mail.replyWebhook",
              timeout_ms=timeout_ms, max_jobs_to_activate=8)
    async def _wh(message_id: str = "", in_reply_to: str = "",
                  from_email: str = "", from_name: str = "",
                  to_emails: list[str] | None = None, subject: str = "",
                  body_preview: str = "", received_at: str = "",
                  graph_event_id: str = "", raw_headers: str = "") -> dict:
        return await task_lawfirm_mail_reply_webhook(
            message_id=message_id, in_reply_to=in_reply_to,
            from_email=from_email, from_name=from_name,
            to_emails=to_emails or [], subject=subject,
            body_preview=body_preview, received_at=received_at,
            graph_event_id=graph_event_id, raw_headers=raw_headers,
        )

    @app.task(task_type="lawfirm.sales.pipelineTransition",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _trans(lead_id: str = "", to_stage: str = "",
                     reason: str = "", decided_by_did: str = "") -> dict:
        return await task_lawfirm_pipeline_transition(
            lead_id=lead_id, to_stage=to_stage,
            reason=reason, decided_by_did=decided_by_did,
        )

    @app.task(task_type="lawfirm.sales.recordOutreach",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _rec(lead_id: str = "", event_kind: str = "mail_sent",
                   channel: str = "email", direction: str = "out",
                   subject: str = "", body_preview: str = "",
                   asset_uri: str = "", actor_did: str = "") -> dict:
        return await task_lawfirm_record_outreach(
            lead_id=lead_id, event_kind=event_kind, channel=channel,
            direction=direction, subject=subject, body_preview=body_preview,
            asset_uri=asset_uri, actor_did=actor_did,
        )

    LOG.info("Registered tasks: lawfirm.mail.replyWebhook, lawfirm.sales.{pipelineTransition,recordOutreach}")
