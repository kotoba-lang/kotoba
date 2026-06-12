"""Outlook triage analytics helpers.

Runs lightweight COUNT/GROUP BY queries against the triage tables.
All queries use LIMIT to stay within kotoba Datom log safe read paths.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


def _cutoff_iso(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def get_triage_stats(days: int = 30) -> dict[str, Any]:
    """COUNT triage_classification from vertex_email_message (last N days) in kotoba Datom log."""
    cutoff = _cutoff_iso(days)
    kotoba_client = get_kotoba_client()
    # R0: Fetching all relevant records and applying grouping/counting in Python
    # since the `triaged_at >= %s` range query and GROUP BY/COUNT are not
    # directly supported by `select_where`. The original SQL had a LIMIT 20
    # on the grouped results, so we fetch more (limit 2000) and then limit.
    all_messages = kotoba_client.select_where(
        "vertex_email_message",
        None,  # No equality filter, will fetch all
        None,
        columns=["triage_classification", "triaged_at"],
        limit=2000,  # A reasonable limit to avoid overwhelming the system
    )

    # Filter by triaged_at in Python
    filtered_messages = [
        msg for msg in all_messages if msg.get("triaged_at") and msg["triaged_at"] >= cutoff
    ]

    # Group and count in Python
    triage_counts: dict[str, int] = {}
    for msg in filtered_messages:
        classification = msg.get("triage_classification")
        if classification is None:
            classification = "unknown"
        triage_counts[classification] = triage_counts.get(classification, 0) + 1

    # Sort and limit to 20 as per original SQL
    sorted_counts = sorted(triage_counts.items(), key=lambda item: item[1], reverse=True)[:20]

    return {str(k): int(v) for k, v in sorted_counts}


def get_gray_queue_stats() -> dict[str, Any]:
    """COUNT status/verdict breakdown from vertex_email_gray_queue in kotoba Datom log."""
    kotoba_client = get_kotoba_client()
    # R0: Fetching all relevant records and applying grouping/counting in Python
    # since GROUP BY/COUNT is not directly supported by `select_where`.
    all_queue_items = kotoba_client.select_where(
        "vertex_email_gray_queue",
        None,  # No equality filter, will fetch all
        None,
        columns=["status", "verdict"],
        limit=2000,  # A reasonable limit
    )

    # Group and count in Python
    queue_counts: dict[tuple[str, str], int] = {}
    for item in all_queue_items:
        status = item.get("status") or ""
        verdict = item.get("verdict") or ""
        key = (status, verdict)
        queue_counts[key] = queue_counts.get(key, 0) + 1

    # Convert to the desired result format, applying the LIMIT 30 after grouping.
    # Sort by count (descending) to effectively apply the LIMIT 30 on the most frequent combinations.
    sorted_queue_counts = sorted(queue_counts.items(), key=lambda item: item[1], reverse=True)[:30]

    result: dict[str, Any] = {"pending": 0, "resolved": {}, "skipped": 0}
    for (status, verdict), cnt in sorted_queue_counts:
        if status == "pending":
            result["pending"] = result.get("pending", 0) + cnt
        elif status == "skipped":
            result["skipped"] = result.get("skipped", 0) + cnt
        elif status == "resolved":
            resolved = result.setdefault("resolved", {})
            resolved[verdict or "unknown"] = resolved.get(verdict or "unknown", 0) + cnt
    return result


def get_draft_stats() -> dict[str, Any]:
    """COUNT status/action breakdown from vertex_email_reply_draft in kotoba Datom log."""
    kotoba_client = get_kotoba_client()
    # R0: Fetching all relevant records and applying grouping/counting in Python
    # since GROUP BY/COUNT is not directly supported by `select_where`.
    all_draft_items = kotoba_client.select_where(
        "vertex_email_reply_draft",
        None,  # No equality filter, will fetch all
        None,
        columns=["status", "action"],
        limit=2000,  # A reasonable limit
    )

    # Group and count in Python
    draft_counts: dict[tuple[str, str], int] = {}
    for item in all_draft_items:
        status = item.get("status") or ""
        action = item.get("action") or ""
        key = (status, action)
        draft_counts[key] = draft_counts.get(key, 0) + 1

    # Convert to the desired result format, applying the LIMIT 30 after grouping.
    sorted_draft_counts = sorted(draft_counts.items(), key=lambda item: item[1], reverse=True)[:30]

    result: dict[str, Any] = {"pending": 0, "approved": {}, "discarded": 0}
    for (status, action), cnt in sorted_draft_counts:
        if status == "pending":
            result["pending"] = result.get("pending", 0) + cnt
        elif status == "discarded":
            result["discarded"] = result.get("discarded", 0) + cnt
        elif status == "approved":
            approved = result.setdefault("approved", {})
            approved[action or "approve"] = approved.get(action or "approve", 0) + cnt
    return result


def get_feedback_stats(days: int = 90) -> dict[str, Any]:
    """COUNT verdict from vertex_email_triage_feedback (last N days) in kotoba Datom log."""
    cutoff = _cutoff_iso(days)
    kotoba_client = get_kotoba_client()
    # R0: Fetching all relevant records and applying grouping/counting in Python
    # since the `created_at >= %s` range query and GROUP BY/COUNT are not
    # directly supported by `select_where`. The original SQL had a LIMIT 10
    # on the grouped results, so we fetch more (limit 2000) and then limit.
    all_feedback_items = kotoba_client.select_where(
        "vertex_email_triage_feedback",
        None,  # No equality filter, will fetch all
        None,
        columns=["verdict", "created_at"],
        limit=2000,  # A reasonable limit
    )

    # Filter by created_at in Python
    filtered_feedback_items = [
        item for item in all_feedback_items if item.get("created_at") and item["created_at"] >= cutoff
    ]

    # Group and count in Python
    feedback_counts: dict[str, int] = {}
    for item in filtered_feedback_items:
        verdict = item.get("verdict")
        if verdict is None:
            verdict = "unknown"
        feedback_counts[verdict] = feedback_counts.get(verdict, 0) + 1

    # Sort and limit to 10 as per original SQL
    sorted_counts = sorted(feedback_counts.items(), key=lambda item: item[1], reverse=True)[:10]

    return {str(k): int(v) for k, v in sorted_counts}


def get_all_stats(days: int = 30) -> dict[str, Any]:
    """Aggregate all stats into a single response dict."""
    result: dict[str, Any] = {"days": days, "generated_at": datetime.now(timezone.utc).isoformat()}
    try:
        result["triage"] = get_triage_stats(days)
    except Exception as e:
        result["triage"] = {"error": str(e)[:120]}
    try:
        result["gray_queue"] = get_gray_queue_stats()
    except Exception as e:
        result["gray_queue"] = {"error": str(e)[:120]}
    try:
        result["drafts"] = get_draft_stats()
    except Exception as e:
        result["drafts"] = {"error": str(e)[:120]}
    try:
        result["feedback"] = get_feedback_stats(days)
    except Exception as e:
        result["feedback"] = {"error": str(e)[:120]}
    return result


__all__ = ["get_all_stats"]
