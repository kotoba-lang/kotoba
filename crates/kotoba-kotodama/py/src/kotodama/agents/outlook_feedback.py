"""Outlook triage auto-learning feedback loop (Phase 4).

Records human verdicts for gray-zone emails and uses historical per-sender
data to adjust future triage scores.

DDL (run once in autocommit — do NOT execute from this module):

    CREATE TABLE vertex_email_triage_feedback (
        vertex_id       VARCHAR PRIMARY KEY,
        email_vertex_id VARCHAR NOT NULL,
        from_address    VARCHAR DEFAULT '',
        triage_score    INTEGER DEFAULT 0,
        verdict         VARCHAR NOT NULL,
        actor_did       VARCHAR NOT NULL,
        created_at      VARCHAR NOT NULL
    );

kotoba Datom log does NOT support ON CONFLICT — use INSERT ... SELECT ... WHERE NOT EXISTS.
DDL runs in autocommit.  No FK constraints.
"""

from __future__ import annotations

import time
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:pregel.etzhayyim.com"


# ── Internal helpers ───────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _cutoff_iso(days: int) -> str:
    """Return an ISO-8601 UTC timestamp for *days* ago."""
    # Use mktime on a struct_time that represents a UTC epoch offset.
    # time.gmtime(0) == 1970-01-01T00:00:00Z; we subtract days*86400 seconds.
    now_epoch = time.mktime(time.gmtime())  # seconds since epoch (UTC approx)
    cutoff_epoch = now_epoch - days * 86400
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cutoff_epoch))


# ── Public API ─────────────────────────────────────────────────────────


def record_verdict(
    email_vertex_id: str,
    from_address: str,
    triage_score: int,
    verdict: str,
) -> bool:
    """Record a human verdict for a triaged email.

    Uses ``INSERT ... SELECT ... WHERE NOT EXISTS`` to avoid duplicates
    (kotoba Datom log does not support ON CONFLICT).

    Args:
        email_vertex_id: The ``vertex_id`` of the source email message.
        from_address: Sender email address (may be empty string).
        triage_score: Integer triage score at the time of verdict.
        verdict: One of ``'clean'``, ``'spam'``, or ``'gray'``.

    Returns:
        ``True`` if the feedback row was inserted, ``False`` if it already
        existed (idempotent).
    """
    vertex_id = f"feedback-{email_vertex_id}"
    now = _now_iso()
    verdict = str(verdict)[:120]
    from_address = str(from_address or "")[:480]
    triage_score = int(triage_score or 0)

    client = get_kotoba_client()
    existing_record = client.select_first_where("vertex_email_triage_feedback", "vertex_id", vertex_id)
    if existing_record:
        return False
    else:
        row_dict = {
            "vertex_id": vertex_id,
            "email_vertex_id": email_vertex_id,
            "from_address": from_address,
            "triage_score": triage_score,
            "verdict": verdict,
            "actor_did": ACTOR_DID,
            "created_at": now,
        }
        client.insert_row("vertex_email_triage_feedback", row_dict)
        return True


def get_sender_prior(
    from_address: str,
    days: int = 90,
    limit: int = 30,
) -> dict[str, Any]:
    """Return verdict counts for a given sender over the past *days* days.

    Args:
        from_address: Sender email address to look up.
        days: Look-back window in days (default 90).
        limit: Maximum rows to scan (default 30).

    Returns:
        A dict with keys ``clean_count``, ``spam_count``, ``gray_count``,
        and ``total``.
    """
    limit = max(1, min(int(limit), 1000))
    days = max(1, int(days))
    cutoff = _cutoff_iso(days)
    from_address = str(from_address or "")

    counts: dict[str, int] = {"clean": 0, "spam": 0, "gray": 0}

    if not from_address:
        return {"clean_count": 0, "spam_count": 0, "gray_count": 0, "total": 0}

    client = get_kotoba_client()
    # R0: In-Python filter for created_at and aggregation for verdict counts.
    all_feedback_rows = client.select_where(
        "vertex_email_triage_feedback",
        "from_address",
        from_address,
        columns=["verdict", "created_at"],
        limit=2000,
    )

    filtered_rows = [
        row for row in all_feedback_rows
        if row["created_at"] >= cutoff
    ]

    for row in filtered_rows:
        verdict_val = str(row["verdict"] or "").lower()
        if verdict_val in counts:
            counts[verdict_val] += 1

    total = counts["clean"] + counts["spam"] + counts["gray"]
    return {
        "clean_count": counts["clean"],
        "spam_count": counts["spam"],
        "gray_count": counts["gray"],
        "total": total,
    }


def apply_sender_prior(
    score: int,
    from_address: str,
) -> tuple[int, list[str]]:
    """Adjust a triage score based on historical sender verdicts.

    Rules (applied in order, higher threshold replaces lower):
      - clean_count >= 3 and spam_count == 0  → score -= 20
      - clean_count >= 5 and spam_count == 0  → score -= 35  (replaces -20)
      - spam_count  >= 3                       → score += 20
      - spam_count  >= 5                       → score += 35  (replaces +20)

    The final score is clamped to [0, 99].

    Args:
        score: Current triage score.
        from_address: Sender email address.

    Returns:
        ``(adjusted_score, reasons)`` where *reasons* is a list of short
        explanation strings added by this function.  Always returns the
        original (score, []) on any exception.
    """
    try:
        prior = get_sender_prior(from_address)
        clean_n = prior["clean_count"]
        spam_n = prior["spam_count"]
        reasons: list[str] = []
        delta = 0

        if clean_n >= 5 and spam_n == 0:
            delta = -35
            reasons.append(f"prior:clean×{clean_n}")
        elif clean_n >= 3 and spam_n == 0:
            delta = -20
            reasons.append(f"prior:clean×{clean_n}")

        if spam_n >= 5:
            delta = 35
            reasons = [f"prior:spam×{spam_n}"]
        elif spam_n >= 3:
            delta = 20
            reasons = [f"prior:spam×{spam_n}"]

        adjusted = max(0, min(99, score + delta))
        return adjusted, reasons
    except Exception:
        return score, []


__all__ = ["record_verdict", "get_sender_prior", "apply_sender_prior"]
