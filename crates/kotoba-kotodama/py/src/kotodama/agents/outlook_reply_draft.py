"""Outlook reply-draft HITL helpers.

Manages LLM-generated reply drafts for emails that were triaged as "clean".
Drafts are held for human review (approve / discard / edit) before sending.

Table: ``vertex_email_reply_draft`` (persisted in kotoba Datom log)
  vertex_id       VARCHAR PK   (format: ``draft-{email_vertex_id}``)
  email_vertex_id VARCHAR NOT NULL
  from_address    VARCHAR DEFAULT ''
  subject         VARCHAR DEFAULT ''
  draft_text      VARCHAR NOT NULL
  status          VARCHAR DEFAULT 'pending'   (pending | approved | discarded)
  action          VARCHAR DEFAULT ''
  final_text      VARCHAR DEFAULT ''
  actor_did       VARCHAR NOT NULL
  created_at      VARCHAR NOT NULL

DDL (for reference only; actual persistence handled by kotoba Datom log):

  CREATE TABLE vertex_email_reply_draft (
      vertex_id       VARCHAR PRIMARY KEY,
      email_vertex_id VARCHAR NOT NULL,
      from_address    VARCHAR DEFAULT '',
      subject         VARCHAR DEFAULT '',
      draft_text      VARCHAR NOT NULL,
      status          VARCHAR DEFAULT 'pending',
      action          VARCHAR DEFAULT '',
      final_text      VARCHAR DEFAULT '',
      actor_did       VARCHAR NOT NULL,
      created_at      VARCHAR NOT NULL
  );
"""

from __future__ import annotations

import os
import time
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:pregel.etzhayyim.com"


# ── Internal helpers ───────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fetch_email_details(email_vertex_id: str) -> dict | None:
    """SELECT from_address, subject, body_preview FROM vertex_email_message WHERE vertex_id = %s."""
    kotoba_client = get_kotoba_client()
    row = kotoba_client.select_first_where(
        "vertex_email_message",
        "vertex_id",
        email_vertex_id,
        columns=["from_address", "subject", "body_preview"]
    )

    if row is None:
        return None

    return {
        "from_address": row.get("from_address", ""),
        "subject": row.get("subject", ""),
        "body_preview": row.get("body_preview", ""),
    }


def _generate_draft_text(from_address: str, subject: str, body_preview: str) -> str:
    """Generate a polite reply draft using LLM or template fallback.

    Tries langchain_openai or openai if OPENAI_API_KEY / OPENAI_BASE_URL is set.
    Falls back to a static Japanese template when LLM is unavailable.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")

    if api_key or base_url:
        # Try LangChain first, then raw openai SDK
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
            from langchain_core.messages import HumanMessage  # type: ignore[import-not-found]

            llm_kwargs: dict[str, Any] = {"model": "gpt-4o-mini", "temperature": 0.3}
            if api_key:
                llm_kwargs["api_key"] = api_key
            if base_url:
                llm_kwargs["base_url"] = base_url

            llm = ChatOpenAI(**llm_kwargs)
            prompt = (
                f"以下のメールに対する丁寧な日本語の返信下書きを作成してください。\n\n"
                f"送信元: {from_address}\n"
                f"件名: {subject}\n"
                f"本文抜粋: {body_preview[:500]}\n\n"
                f"返信下書き:"
            )
            result = llm.invoke([HumanMessage(content=prompt)])
            draft = str(result.content).strip()
            if draft:
                return draft
        except Exception:
            pass  # fall through to openai SDK or template

        try:
            import openai  # type: ignore[import-not-found]

            client_kwargs: dict[str, Any] = {}
            if api_key:
                client_kwargs["api_key"] = api_key
            if base_url:
                client_kwargs["base_url"] = base_url

            client = openai.OpenAI(**client_kwargs)
            prompt = (
                f"以下のメールに対する丁寧な日本語の返信下書きを作成してください。\n\n"
                f"送信元: {from_address}\n"
                f"件名: {subject}\n"
                f"本文抜粋: {body_preview[:500]}\n\n"
                f"返信下書き:"
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            draft = (response.choices[0].message.content or "").strip()
            if draft:
                return draft
        except Exception:
            pass  # fall through to template

    # Static template fallback
    return (
        "お世話になっております。\n\n"
        "ご連絡いただきありがとうございます。\n"
        "内容を確認の上、改めてご連絡いたします。\n\n"
        "よろしくお願いいたします。"
    )


# ── Internal helpers (continued) ──────────────────────────────────────


def _should_auto_approve(from_address: str) -> bool:
    """Return True if sender history is trusted enough to skip HITL.

    Criteria: at least 5 clean verdicts, zero spam verdicts in the last 90 days.
    """
    if not from_address:
        return False
    try:
        from kotodama.agents.outlook_feedback import get_sender_prior as _gsp
        prior = _gsp(from_address)
        return prior.get("clean_count", 0) >= 5 and prior.get("spam_count", 0) == 0
    except Exception:
        return False


# ── Public API ─────────────────────────────────────────────────────────


def queue_reply_draft(
    email_vertex_id: str,
    from_address: str = "",
    subject: str = "",
    body_preview: str = "",
) -> str | None:
    """Generate and queue a reply draft.

    If *from_address*, *subject*, or *body_preview* are not provided,
    they are fetched from ``vertex_email_message``.

    Uses ``INSERT ... SELECT ... WHERE NOT EXISTS`` to avoid duplicates
    (RisingWave does not support ON CONFLICT).

    Returns the draft *vertex_id* if a new row was inserted,
    or ``None`` if a draft already existed for this email.
    """
    draft_vertex_id = f"draft-{email_vertex_id}"

    # Fill missing details from vertex_email_message
    if not (from_address and subject and body_preview):
        details = _fetch_email_details(email_vertex_id)
        if details:
            from_address = from_address or details.get("from_address", "")
            subject = subject or details.get("subject", "")
            body_preview = body_preview or details.get("body_preview", "")

    draft_text = _generate_draft_text(from_address, subject, body_preview)
    now = _now_iso()

    kotoba_client = get_kotoba_client()

    # Check if draft already exists
    existing_draft = kotoba_client.select_first_where(
        "vertex_email_reply_draft",
        "vertex_id",
        draft_vertex_id
    )

    if existing_draft:
        inserted = False
    else:
        row_dict = {
            "vertex_id": draft_vertex_id,
            "email_vertex_id": email_vertex_id,
            "from_address": str(from_address)[:480],
            "subject": str(subject)[:480],
            "draft_text": draft_text,
            "status": "pending",
            "action": "",
            "final_text": "",
            "actor_did": ACTOR_DID,
            "created_at": now,
        }
        inserted_row = kotoba_client.insert_row("vertex_email_reply_draft", row_dict)
        inserted = bool(inserted_row)

    if inserted and _should_auto_approve(from_address):
        try:
            apply_draft_verdict(draft_vertex_id, "approve")
        except Exception:
            pass  # best-effort; draft remains pending for manual review

    return draft_vertex_id if inserted else None


def list_pending_drafts(limit: int = 50) -> list[dict]:
    """SELECT pending reply drafts.

    Returns a list of dicts with keys:
      thread_id (= vertex_id), updated_at (= created_at),
      email_vertex_id, from_address, subject, draft_text

    (Data sourced from kotoba Datom log)
    """
    limit = max(1, min(int(limit), 1000))
    kotoba_client = get_kotoba_client()
    # R0: Fetching a broader set and applying ORDER BY and LIMIT in Python
    raw_rows = kotoba_client.select_where(
        "vertex_email_reply_draft",
        "status",
        "pending",
        columns=["vertex_id", "created_at", "email_vertex_id",
                 "from_address", "subject", "draft_text"],
        limit=1000 # Max limit to fetch, then sort/limit in Python
    )

    # Sort in Python by 'created_at' in descending order
    raw_rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    # Apply limit
    raw_rows = raw_rows[:limit]

    result: list[dict] = []
    for r in raw_rows: # r is already a dict
        result.append(
            {
                "thread_id": r["vertex_id"],
                "updated_at": r["created_at"],
                "email_vertex_id": r["email_vertex_id"],
                "from_address": r["from_address"],
                "subject": r["subject"],
                "draft_text": r["draft_text"],
            }
        )
    return result


def get_draft_item(draft_id: str) -> dict | None:
    """SELECT a single reply draft by vertex_id.

    Returns a dict with all column values or ``None`` if not found.
    (Data sourced from kotoba Datom log)
    """
    kotoba_client = get_kotoba_client()
    row = kotoba_client.select_first_where(
        "vertex_email_reply_draft",
        "vertex_id",
        draft_id,
        columns=["vertex_id", "created_at", "email_vertex_id",
                 "from_address", "subject", "draft_text",
                 "status", "action", "final_text"]
    )

    if row is None:
        return None

    return {
        "thread_id": row.get("vertex_id", ""),
        "updated_at": row.get("created_at", ""),
        "email_vertex_id": row.get("email_vertex_id", ""),
        "from_address": row.get("from_address", ""),
        "subject": row.get("subject", ""),
        "draft_text": row.get("draft_text", ""),
        "status": row.get("status", ""),
        "action": row.get("action", ""),
        "final_text": row.get("final_text", ""),
    }


def apply_draft_verdict(draft_id: str, action: str, final_text: str = "") -> bool:
    """Apply a human verdict to a reply draft.

    *action* must be one of ``'approve'``, ``'discard'``, or ``'edit'``.

    - ``approve`` → ``status='approved'``, ``final_text`` = provided text or original draft
    - ``discard`` → ``status='discarded'``, ``final_text`` = provided text or original draft
    - ``edit``    → ``status='approved'``, ``final_text`` = provided text (edited version)

    Returns ``True`` on success, ``False`` if the draft was not found.
    (Data sourced from kotoba Datom log)
    """
    action = str(action).lower()[:120]
    kotoba_client = get_kotoba_client()

    # Fetch existing draft to fall back to draft_text when final_text is empty
    existing_draft = kotoba_client.select_first_where(
        "vertex_email_reply_draft",
        "vertex_id",
        draft_id,
        columns=["draft_text"]
    )
    if existing_draft is None:
        return False

    original_draft_text: str = existing_draft.get("draft_text", "")
    resolved_final_text = str(final_text).strip() if str(final_text).strip() else original_draft_text

    if action == "discard":
        new_status = "discarded"
    else:
        # approve or edit both result in approved status
        new_status = "approved"

    # Update using insert_row (upsert behavior)
    updated_row_dict = {
        "vertex_id": draft_id,
        "status": new_status,
        "action": action,
        "final_text": resolved_final_text,
    }
    kotoba_client.insert_row("vertex_email_reply_draft", updated_row_dict)

    if new_status == "approved":
        try:
            from kotodama.agents.outlook_reply_sender import send_reply_for_draft as _srf
            _srf(draft_id, resolved_final_text)
        except Exception:
            pass  # sending is best-effort; DB status already updated

    return True

__all__ = [
    "queue_reply_draft",
    "list_pending_drafts",
    "get_draft_item",
    "apply_draft_verdict",
]
