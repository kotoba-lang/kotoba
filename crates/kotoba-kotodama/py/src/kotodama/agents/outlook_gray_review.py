from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


ACTOR_DID = "did:web:pregel.etzhayyim.com"


# ── Internal helpers ───────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Public API ─────────────────────────────────────────────────────────


def enqueue_gray_emails(rows: list[dict]) -> int:
    """INSERT gray emails into ``vertex_email_gray_queue``.

    Each *row* must contain:
      - ``vertex_id``   — email vertex ID (becomes the email_vertex_id column)
      - ``from_address`` or ``from_addr`` — sender address (optional)
      - ``score``       — integer triage score
      - ``reasons``     — list[str] of triage reason strings

    Uses ``select_first_where`` and ``insert_row`` to avoid duplicates
    (Kotoba Datom log handles upserts on identity for existing items).

    Returns the number of rows actually inserted.
    """
    if not rows:
        return 0

    now = _now_iso()
    inserted = 0
    client = get_kotoba_client()

    for row in rows:
        email_vertex_id = str(row.get("vertex_id") or "")
        if not email_vertex_id:
            continue
        gray_vertex_id = f"gray-{email_vertex_id}"
        from_address = str(
            row.get("from_address") or row.get("from_addr") or ""
        )[:480]
        score = int(row.get("score") or 0)
        reasons_list = row.get("reasons") or []
        if isinstance(reasons_list, (list, tuple)):
            reasons_csv = ",".join(str(r) for r in reasons_list)[:480]
        else:
            reasons_csv = str(reasons_list)[:480]

        # Check if already exists (R0: Emulating "WHERE NOT EXISTS")
        existing_item = client.select_first_where("vertex_email_gray_queue", "vertex_id", gray_vertex_id)
        if existing_item is None:
            row_to_insert = {
                "vertex_id": gray_vertex_id,
                "email_vertex_id": email_vertex_id,
                "from_address": from_address,
                "triage_score": score,
                "triage_reasons": reasons_csv,
                "status": "pending",
                "verdict": "",
                "actor_did": ACTOR_DID,
                "created_at": now,
            }
            client.insert_row("vertex_email_gray_queue", row_to_insert)
            inserted += 1

    return inserted


def list_pending_gray(limit: int = 50) -> list[dict]:
    """SELECT pending gray-zone emails from the queue.

    Returns a list of dicts with keys:
      thread_id, updated_at, email_vertex_id, from_address,
      triage_score, triage_reasons
    """
    limit = max(1, min(int(limit), 1000))
    client = get_kotoba_client()

    raw_rows = client.select_where(
        "vertex_email_gray_queue",
        "status",
        "pending",
        columns=[
            "vertex_id",
            "created_at",
            "email_vertex_id",
            "from_address",
            "triage_score",
            "triage_reasons",
        ],
        limit=limit,  # R0: LIMIT applied via select_where
    ) or []

    # R0: ORDER BY created_at DESC applied in Python
    raw_rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    result: list[dict] = []
    for r in raw_rows:
        result.append(
            {
                "thread_id": r["vertex_id"],
                "updated_at": r["created_at"],
                "email_vertex_id": r["email_vertex_id"],
                "from_address": r["from_address"],
                "triage_score": r["triage_score"],
                "triage_reasons": r["triage_reasons"],
            }
        )
    return result


def get_gray_item(thread_id: str) -> dict | None:
    """SELECT a single gray-queue item by vertex_id.

    Returns a dict with keys:
      thread_id, updated_at, email_vertex_id, from_address,
      triage_score, triage_reasons, status
    or ``None`` if not found.
    """
    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_email_gray_queue",
        "vertex_id",
        thread_id,
        columns=[
            "vertex_id",
            "created_at",
            "email_vertex_id",
            "from_address",
            "triage_score",
            "triage_reasons",
            "status",
        ],
    )

    if row is None:
        return None

    # row is already a dict, so we can use it directly
    return {
        "thread_id": row["vertex_id"],
        "updated_at": row["created_at"],
        "email_vertex_id": row["email_vertex_id"],
        "from_address": row["from_address"],
        "triage_score": row["triage_score"],
        "triage_reasons": row["triage_reasons"],
        "status": row["status"],
    }


def apply_verdict(thread_id: str, verdict: str) -> bool:
    """Apply a human verdict to a gray-queue item.

    Sets ``status='resolved'`` and ``verdict=verdict`` on the queue row,
    and also propagates the decision to ``vertex_email_message`` by
    setting ``triaged_at`` and ``triage_classification``.

    Returns ``True`` on success, ``False`` if the queue item was not found.
    """
    now = _now_iso()
    verdict = str(verdict)[:120]
    client = get_kotoba_client()

    # Fetch email_vertex_id, triage_score, and from_address
    fetched_row = client.select_first_where(
        "vertex_email_gray_queue",
        "vertex_id",
        thread_id,
        columns=["email_vertex_id", "triage_score", "from_address"],
    )
    if fetched_row is None:
        return False
    email_vertex_id: str = fetched_row["email_vertex_id"]
    triage_score: int = int(fetched_row["triage_score"] or 0)
    from_address: str = str(fetched_row["from_address"] or "")

    # Update the gray queue row
    gray_queue_update_dict = {
        "vertex_id": thread_id,
        "status": "resolved",
        "verdict": verdict,
    }
    client.insert_row("vertex_email_gray_queue", gray_queue_update_dict)

    # Propagate to vertex_email_message
    email_message_update_dict = {
        "vertex_id": email_vertex_id,
        "triaged_at": now,
        "triage_classification": verdict,
    }
    client.insert_row("vertex_email_message", email_message_update_dict)

    # Record feedback for auto-learning (best-effort)
    try:
        from kotodama.agents.outlook_feedback import record_verdict as _rv
        _rv(email_vertex_id, from_address, triage_score, verdict)
    except Exception:
        pass  # feedback recording is best-effort

    # If classified as clean, queue a reply draft (best-effort)
    if verdict == "clean":
        try:
            from kotodama.agents.outlook_reply_draft import queue_reply_draft as _qrd
            _qrd(email_vertex_id)
        except Exception:
            pass  # draft generation is best-effort

    return True


__all__ = [
    "enqueue_gray_emails",
    "list_pending_gray",
    "get_gray_item",
    "apply_verdict",
]
