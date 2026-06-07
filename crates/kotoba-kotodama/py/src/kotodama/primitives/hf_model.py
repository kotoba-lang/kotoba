"""
HuggingFace Hub model catalog — Zeebe task handler registrations.

Task types:
  hf.model.listFilters      — list enabled vertex_hfhub_filter rows for models
  hf.model.scanAll          — iterate filter list, call scan per filter
  hf.model.scan             — scan HF Hub for 1 model filter
  hf.model.fetchDetailBatch — fetch full card for pending/unenriched models
  hf.model.fetchDetail      — fetch full card for 1 repo_id
  hf.model.resolveLineage   — resolve edge_hfhub_model_base + edge_hfhub_model_dataset
"""

from __future__ import annotations

import logging
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


LOG = logging.getLogger(__name__)


def _fetchall(table: str, column: str, value: Any, columns: list[str] | None = None, limit: int | None = None) -> list[dict]:
    return get_kotoba_client().select_where(table, column, value, columns, limit)


def task_hf_model_list_filters(**_: Any) -> dict[str, Any]:
    # R0: Filtering for entity_type='model' or 'both' done in Python due to multi-predicate WHERE.
    # The limit is applied after fetching, so a higher limit is used here to ensure 200 results if available.
    rows = _fetchall(
        table="vertex_hfhub_filter",
        column="enabled",
        value=True,
        columns=["vertex_id", "entity_type"],
        limit=2000,  # Fetch more to allow for in-Python filtering
    )
    filtered_rows = [
        row["vertex_id"]
        for row in rows
        if row["entity_type"] in ("model", "both")
    ][:200]  # Apply the original limit after filtering
    ids = filtered_rows
    return {"ok": True, "filter_ids": ids, "filter_count": len(ids)}


def task_hf_model_scan_all(
    filter_ids: list[str] | None = None,
    limit_per_filter: int = 500,
    **_: Any,
) -> dict[str, Any]:
    ids = filter_ids or []
    total_scanned = 0
    total_matched = 0
    for fid in ids:
        try:
            result = task_hf_model_scan(filter_id=fid, limit=limit_per_filter)
            total_scanned += result.get("scanned", 0)
            total_matched += result.get("matched", 0)
        except Exception as exc:
            LOG.warning("model scan failed filter=%s: %s", fid, exc)
    return {"ok": True, "total_scanned": total_scanned, "total_matched": total_matched}


def task_hf_model_fetch_detail_batch(
    batch_size: int = 30,
    **_: Any,
) -> dict[str, Any]:
    """Fetch full model card for models missing parameter info (list API gaps)."""
    # R0: Filtering for num_parameters IS NULL, ORDER BY downloads_month, and LIMIT are done in Python
    # due to multi-predicate WHERE and ORDER BY clauses not supported by simple shims.
    # Fetch a broader set and filter/sort in Python.
    rows = _fetchall(
        table="vertex_hfhub_model",
        column="status",
        value="active",
        columns=["repo_id", "num_parameters", "downloads_month"],
        limit=2000,  # Fetch more to allow for in-Python filtering and sorting
    )

    filtered_and_sorted_rows = sorted(
        [row for row in rows if row["num_parameters"] is None],
        key=lambda x: x.get("downloads_month", 0),  # Handle potential missing downloads_month
        reverse=True,
    )[:batch_size]  # Apply the batch_size limit after filtering and sorting

    enriched = 0
    for row in filtered_and_sorted_rows:
        repo_id = row["repo_id"]
        try:
            result = task_hf_model_fetch_detail(repo_id=repo_id)
            if result.get("ok"):
                enriched += 1
        except Exception as exc:
            LOG.warning("model fetchDetail failed repo=%s: %s", repo_id, exc)
    return {"ok": True, "processed": len(filtered_and_sorted_rows), "enriched": enriched}


def task_hf_model_scan_one(filter_id: str | None = None, limit: int = 500, **_: Any) -> dict[str, Any]:
    return task_hf_model_scan(filter_id=filter_id, limit=limit)


def task_hf_model_fetch_detail_one(repo_id: str | None = None, **_: Any) -> dict[str, Any]:
    return task_hf_model_fetch_detail(repo_id=repo_id)


def task_hf_model_resolve_lineage_one(**kwargs: Any) -> dict[str, Any]:
    return task_hf_model_resolve_lineage(**kwargs)


TASK_HANDLERS: dict[str, Any] = {
    "hf.model.listFilters": task_hf_model_list_filters,
    "hf.model.scanAll": task_hf_model_scan_all,
    "hf.model.scan": task_hf_model_scan_one,
    "hf.model.fetchDetailBatch": task_hf_model_fetch_detail_batch,
    "hf.model.fetchDetail": task_hf_model_fetch_detail_one,
    "hf.model.resolveLineage": task_hf_model_resolve_lineage_one,
}
