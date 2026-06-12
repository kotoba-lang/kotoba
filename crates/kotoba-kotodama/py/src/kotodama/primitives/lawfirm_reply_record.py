"""
lawfirm.cadence.recordReply — LangServer handler for inbound mail replies.

Backs com.etzhayyim.apps.lawfirm.mailReplyWebhook lexicon (existing).

Match strategy (in priority order):
  1. graph_event_id idempotency check (skip if already recorded)
  2. in_reply_to header → look up prior outreach_event by message_id mapping
     (currently not stored — falls through to step 3)
  3. from_email match against vertex_lawfirm_lead.target_email (most reliable)
  4. Subject-line "Re: <prior subject>" prefix match against
     vertex_lawfirm_outreach_event.subject (fallback)

On match:
  - INSERT vertex_lawfirm_outreach_event(event_kind='reply_received',
    direction='inbound', actor_did=from_email-derived)
  - If lead.stage IN ('contacted', 'lead'): UPDATE stage='meeting_requested'
    + last_reply_at + last_touch_at
  - Suppresses subsequent dispatchFollowUps via the NOT EXISTS reply_received
    gate already in lawfirm_cadence_dispatch.py

Rough sentiment cue (positive/neutral/negative) derived from body_preview
keyword match — feeds vertex_lawfirm_outreach_event.sentiment column for
later LLM-based scoring upgrade. Day-0: keyword-only.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.cadence.reply")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"

_POSITIVE_CUES = (
    "yes", "interested", "happy to", "let's", "sure", "sounds good",
    "schedule", "available", "calendar", "let me know when",
    "good idea", "go ahead", "send me", "would like",
)
_NEGATIVE_CUES = (
    "not interested", "no thanks", "pass", "remove", "unsubscribe",
    "stop sending", "do not contact", "decline", "not a fit",
)


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")





def _classify_sentiment(body_preview: str) -> tuple[float, str]:
    """Return (sentiment_score in [-1, +1], label)."""
    text = (body_preview or "").lower()
    pos_hits = sum(1 for cue in _POSITIVE_CUES if cue in text)
    neg_hits = sum(1 for cue in _NEGATIVE_CUES if cue in text)
    if pos_hits == 0 and neg_hits == 0:
        return 0.0, "neutral"
    if neg_hits > pos_hits:
        return max(-1.0, -0.5 - 0.1 * (neg_hits - pos_hits)), "negative"
    if pos_hits > neg_hits:
        return min(1.0, 0.5 + 0.1 * (pos_hits - neg_hits)), "positive"
    return 0.0, "neutral"


def _strip_subject_prefix(subject: str) -> str:
    """Strip leading 'Re:' / 'RE:' / 'Fwd:' prefixes for thread match."""
    s = subject or ""
    while True:
        m = re.match(r"^\s*(re|fwd|fw)\s*:\s*", s, re.IGNORECASE)
        if not m:
            return s.strip()
        s = s[m.end():]


# ── Task: lawfirm.cadence.recordReply ────────────────────────────────────────

async def task_lawfirm_record_reply(
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
    if not from_email:
        return {"ok": False, "error": "from_email required"}

    # Idempotency: skip if graph_event_id already recorded
    if graph_event_id:
        pass
    # R0: Multi-predicate query for idempotency check
    query_edn_idempotency = """
    [:find ?vid
     :in $ ?gid
     :where
     [?e "asset_uri" ?gid]
     [?e "event_kind" "reply_received"]
     [?e "vertex_id" ?vid]]
    """
    existing_raw = get_kotoba_client().q(query_edn_idempotency, args=(f"graph:{graph_event_id}",))
    existing = [{"vertex_id": item[0]} for item in existing_raw]
    if existing:
            return {
                "ok": True, "matched_lead_id": "",
                "outreach_event_uri": existing[0]["vertex_id"],
                "stage_advanced": False, "new_stage": "",
                "duplicate": True,
            }

    # Match by from_email (most reliable)
    # R0: Query for lead by email, case-insensitive, ordered by created_at, limited to 1
    query_edn_lead_by_email = """
    [:find (pull ?e [:lead_id :target_name :stage])
     :in $ ?email
     :where
     [?e "target_email" ?target_email]
     [(clojure.string/lower ?target_email) ?lower_target_email]
     [(clojure.string/lower ?email) ?lower_email]
     [(= ?lower_target_email ?lower_email)]
     [?e "created_at" ?created_at]]
    :order-by [[?created_at :desc]]
    :limit 1]
    """
    lead_rows_raw = get_kotoba_client().q(query_edn_lead_by_email, args=(from_email,))
    lead_rows = [item[0] for item in lead_rows_raw]

    # Fallback: subject thread match against prior outreach_event
    if not lead_rows and subject:
        stripped = _strip_subject_prefix(subject)
        if stripped:
            # R0: Query for lead by subject match (LIKE), joining outreach_event and lead tables.
            query_edn_subject_match = """
            [:find (pull ?l [:lead_id :target_name :stage])
             :in $ ?pat
             :where
             [?oe "direction" "outbound"]
             [?oe "subject" ?subject]
             [(str ?subject) ?subject_str]
             [(.contains ?subject_str ?pat)] ; Equivalent of LIKE %pat%
             [?oe "occurred_at" ?occurred_at]
             [?oe "lead_id" ?lead_id]
             [?l "lead_id" ?lead_id]]
            :order-by [[?occurred_at :desc]]
            :limit 1]
            """
            lead_rows_raw = get_kotoba_client().q(query_edn_subject_match, args=(stripped[:200],))
            lead_rows = [item[0] for item in lead_rows_raw]

    if not lead_rows:
        # Unmatched: log + return ok (no failure — Graph webhook should not retry)
        LOG.info(
            "reply: no lead match from=%s subject=%s",
            from_email, (subject or "")[:80],
        )
        return {
            "ok": True, "matched_lead_id": "",
            "outreach_event_uri": "",
            "stage_advanced": False, "new_stage": "",
            "matched": False,
        }

    row = lead_rows[0]
    lead_id = row["lead_id"]
    cur_stage = row.get("stage") or "lead"

    sentiment_score, sentiment_label = _classify_sentiment(body_preview)
    occurred_at = received_at or _now_iso()

    ev_uri = (
        f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.outreachEvent/"
        f"{lead_id}-reply-{_dt.datetime.now(tz=_dt.UTC).strftime('%Y%m%d%H%M%S')}"
    )
    asset_uri = f"graph:{graph_event_id}" if graph_event_id else (message_id or "")
    actor = f"mailto:{from_email}"

    outreach_event_data = {
        "vertex_id": ev_uri,
        "lead_id": lead_id,
        "event_kind": "reply_received",
        "channel": "email",
        "direction": "inbound",
        "subject": (subject or "")[:300],
        "body_preview": (body_preview or "")[:500],
        "asset_uri": asset_uri,
        "occurred_at": occurred_at,
        "actor_did": actor,
        "sentiment": float(sentiment_score),
        "created_at": _now_iso(),
        "sensitivity_ord": 200,
        "owner_did": _FIRM_DID,
    }
    get_kotoba_client().insert_row("vertex_lawfirm_outreach_event", outreach_event_data)

    # Stage advance: lead/contacted → meeting_requested on first reply
    stage_advanced = False
    new_stage = cur_stage
    if cur_stage in ("lead", "contacted"):
        new_stage = "meeting_requested" if sentiment_label != "negative" else "lost"
        lead_update_data = {
            "lead_id": lead_id,
            "stage": new_stage,
            "last_reply_at": occurred_at,
            "last_touch_at": _now_iso(),
        }
        get_kotoba_client().insert_row("vertex_lawfirm_lead", lead_update_data)
        stage_advanced = True
    else:
        lead_update_data = {
            "lead_id": lead_id,
            "last_reply_at": occurred_at,
            "last_touch_at": _now_iso(),
        }
        get_kotoba_client().insert_row("vertex_lawfirm_lead", lead_update_data)

    LOG.info(
        "reply recorded lead=%s sentiment=%s (%.2f) stage=%s→%s",
        lead_id, sentiment_label, sentiment_score, cur_stage, new_stage,
    )
    return {
        "ok": True,
        "matched_lead_id": lead_id,
        "outreach_event_uri": ev_uri,
        "stage_advanced": stage_advanced,
        "new_stage": new_stage,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "matched": True,
    }


# ── LangServer registration ─────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 30_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.cadence.recordReply",
              timeout_ms=timeout_ms, max_jobs_to_activate=8)
    async def _record(message_id: str = "", in_reply_to: str = "",
                      from_email: str = "", from_name: str = "",
                      to_emails: list[str] | None = None,
                      subject: str = "", body_preview: str = "",
                      received_at: str = "", graph_event_id: str = "",
                      raw_headers: str = "") -> dict:
        return await task_lawfirm_record_reply(
            message_id=message_id, in_reply_to=in_reply_to,
            from_email=from_email, from_name=from_name,
            to_emails=to_emails, subject=subject,
            body_preview=body_preview, received_at=received_at,
            graph_event_id=graph_event_id, raw_headers=raw_headers,
        )

    LOG.info("Registered tasks: lawfirm.cadence.recordReply")
