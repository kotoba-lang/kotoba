"""
HuggingFace Hub dataset catalog — Zeebe task handler registrations.

Task types handled:
  hf.dataset.listFilters      — list enabled vertex_hfhub_filter vertex_ids
  hf.dataset.scanAll          — iterate filter list, call scan per filter
  hf.dataset.scan             — scan HF Hub for 1 filter → upsert datasets + matches
  hf.dataset.fetchSplitsBatch — batch-fetch splits for pending datasets
  hf.dataset.fetchSplits      — fetch splits for 1 repo_id
  hf.dataset.applyFilter      — re-evaluate a filter against existing catalog rows
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.ingest.hf_dataset import (
    task_hf_dataset_apply_filter,
    task_hf_dataset_fetch_splits,
    task_hf_dataset_scan,
)

LOG = logging.getLogger(__name__)


# ── hf.dataset.listFilters ────────────────────────────────────────────────────

def task_hf_dataset_list_filters(**_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    rows = client.select_where("vertex_hfhub_filter", "enabled", True, columns=["vertex_id"], limit=200)
    ids = [r["vertex_id"] for r in rows]
    return {"ok": True, "filter_ids": ids, "filter_count": len(ids)}


# ── hf.dataset.scanAll ────────────────────────────────────────────────────────

def task_hf_dataset_scan_all(
    filter_ids: list[str] | None = None,
    limit_per_filter: int = 500,
    **_: Any,
) -> dict[str, Any]:
    """Iterate filter_ids list, call task_hf_dataset_scan per filter."""
    ids = filter_ids or []
    total_scanned = 0
    total_matched = 0
    for fid in ids:
        try:
            result = task_hf_dataset_scan(filter_id=fid, limit=limit_per_filter)
            total_scanned += result.get("scanned", 0)
            total_matched += result.get("matched", 0)
        except Exception as exc:
            LOG.warning("scan failed filter=%s: %s", fid, exc)
    return {"ok": True, "total_scanned": total_scanned, "total_matched": total_matched}


# ── hf.dataset.fetchSplitsBatch ───────────────────────────────────────────────

def task_hf_dataset_fetch_splits_batch(
    batch_size: int = 50,
    **_: Any,
) -> dict[str, Any]:
    """Fetch split metadata for up to batch_size pending datasets."""
    # R0: Multi-predicate OR and ORDER BY handled in Python.
    client = get_kotoba_client()

    # Fetch rows where status is 'pending'
    pending_rows = client.select_where(
        "vertex_hfhub_dataset",
        "status",
        "pending",
        columns=["repo_id", "created_at", "last_scanned_at"]
    )

    # Fetch rows where last_scanned_at is NULL
    null_scanned_rows = client.select_where(
        "vertex_hfhub_dataset",
        "last_scanned_at",
        None,
        columns=["repo_id", "created_at", "last_scanned_at"]
    )

    # Combine and remove duplicates, prioritizing entries if they appear in both lists
    combined_rows_map = {row["repo_id"]: row for row in pending_rows}
    for row in null_scanned_rows:
        if row["repo_id"] not in combined_rows_map:
            combined_rows_map[row["repo_id"]] = row

    rows_to_process = list(combined_rows_map.values())

    # Sort by created_at
    rows_to_process.sort(key=lambda r: r["created_at"])

    # Apply limit
    rows = rows_to_process[:int(batch_size)]

    splits_total = 0
    files_total = 0
    for row in rows:
        repo_id = row["repo_id"]
        try:
            result = task_hf_dataset_fetch_splits(repo_id=repo_id)
            splits_total += result.get("splits", 0)
            files_total += result.get("files", 0)
        except Exception as exc:
            LOG.warning("fetchSplits failed repo=%s: %s", repo_id, exc)
    return {"ok": True, "repos": len(rows), "splits_total": splits_total, "files_total": files_total}


# ── Direct pass-through wrappers ──────────────────────────────────────────────

def task_hf_dataset_scan_one(
    filter_id: str | None = None,
    limit: int = 500,
    **_: Any,
) -> dict[str, Any]:
    return task_hf_dataset_scan(filter_id=filter_id, limit=limit)


def task_hf_dataset_fetch_splits_one(
    repo_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    return task_hf_dataset_fetch_splits(repo_id=repo_id)


def task_hf_dataset_apply_filter_one(
    filter_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    return task_hf_dataset_apply_filter(filter_id=filter_id)


# ── Zeebe task type → handler map (consumed by zeebe_worker_main.py) ──────────

TASK_HANDLERS: dict[str, Any] = {
    "hf.dataset.listFilters": task_hf_dataset_list_filters,
    "hf.dataset.scanAll": task_hf_dataset_scan_all,
    "hf.dataset.scan": task_hf_dataset_scan_one,
    "hf.dataset.fetchSplitsBatch": task_hf_dataset_fetch_splits_batch,
    "hf.dataset.fetchSplits": task_hf_dataset_fetch_splits_one,
    "hf.dataset.applyFilter": task_hf_dataset_apply_filter_one,
}
