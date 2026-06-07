"""
hf_dataset — HuggingFace Hub dataset catalog ingest.

Zeebe task types:
  hf.dataset.scan          — apply a vertex_hfhub_filter → populate vertex_hfhub_dataset
                             + edge_hfhub_filter_match (called by datasetScan.bpmn)
  hf.dataset.fetchSplits   — fetch split/parquet metadata for a single repo_id
                             → vertex_hfhub_split + vertex_hfhub_file + edge_hfhub_split_file
  hf.dataset.applyFilter   — re-evaluate edge_hfhub_filter_match for a filter against
                             already-catalogued datasets (no Hub API call)

Env (from K8s Secret training-hf-creds — same secret as training_export.py):
  HF_TOKEN      HuggingFace API token (read-only is sufficient)

Kotoba Datom log conventions applied:
  - No ON CONFLICT — PK implicit upsert (same-PK re-INSERT overwrites)
  - LIMIT inlined as {int(n)} — avoids psycopg3 prepared-statement rejection
  - No CURRENT_DATE in hot-path queries — pass date string from Python
  - flush=False on all inserts (avoid kotoba_datomic transaction guard)
  - dml_rate_limit not needed here (catalog rows <500K total, not bulk)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger(__name__)

_OWNER_DID = "did:web:ingest.etzhayyim.com"
_HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
_HF_API = "https://huggingface.co/api"
_DS_SERVER = "https://datasets-server.huggingface.co"
_TIMEOUT = 30
_SCAN_LIMIT = int(os.environ.get("HF_SCAN_LIMIT", "500"))


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _hf_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_HF_API}/{path.lstrip('/')}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None)
        url = f"{url}?{qs}"
    headers: dict[str, str] = {"Accept": "application/json"}
    if _HF_TOKEN:
        headers["Authorization"] = f"Bearer {_HF_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        LOG.warning("hf_get failed url=%s: %s", url, exc)
        return None


def _ds_server_get(endpoint: str, repo_id: str) -> Any:
    url = f"{_DS_SERVER}/{endpoint}?dataset={urllib.parse.quote(repo_id, safe='')}"
    headers: dict[str, str] = {}
    if _HF_TOKEN:
        headers["Authorization"] = f"Bearer {_HF_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        LOG.debug("ds_server_get failed repo=%s endpoint=%s: %s", repo_id, endpoint, exc)
        return None


def _upsert_dataset(ds: dict[str, Any]) -> None:
    ts = _now_iso()
    date = _today()
    get_kotoba_client().insert_row(
        "vertex_hfhub_dataset",
        {
            "vertex_id": ds["vertex_id"],
            "created_date": date,
            "repo_id": ds["repo_id"],
            "author": ds["author"],
            "sha": ds["sha"],
            "license": ds["license"],
            "size_category": ds["size_category"],
            "downloads_month": ds["downloads_month"],
            "likes": ds["likes"],
            "gated": ds["gated"],
            "disabled": ds["disabled"],
            "private": ds["private"],
            "description": ds["description"],
            "card_data": ds["card_data"],
            "status": "active",
            "last_scanned_at": ts,
            "actor_did": _OWNER_DID,
            "created_at": ts,
        },
    )


def _upsert_edges(ds: dict[str, Any]) -> None:
    vid = ds["vertex_id"]
    for tag in ds["tags"]:
        get_kotoba_client().insert_row(
            "edge_hfhub_dataset_tag",
            {"dataset_id": vid, "tag": tag},
        )
    for task in ds["task_categories"]:
        get_kotoba_client().insert_row(
            "edge_hfhub_dataset_task",
            {"dataset_id": vid, "task_category": task},
        )
    for lang in ds["languages"]:
        get_kotoba_client().insert_row(
            "edge_hfhub_dataset_language",
            {"dataset_id": vid, "lang_code": lang},
        )


def _upsert_filter_match(filter_id: str, dataset_id: str) -> None:
    get_kotoba_client().insert_row(
        "edge_hfhub_filter_match",
        {"filter_id": filter_id, "dataset_id": dataset_id, "matched_at": _now_iso()},
    )


def _parse_filter_spec(row: dict[str, Any]) -> dict[str, Any]:
    """Unpack vertex_hfhub_filter row into a dict."""
    return {
        "vertex_id": row["vertex_id"],
        "slug": row["slug"],
        "tags": json.loads(row["filter_tags"]) if row["filter_tags"] else [],
        "tasks": json.loads(row["filter_tasks"]) if row["filter_tasks"] else [],
        "languages": json.loads(row["filter_languages"]) if row["filter_languages"] else [],
        "license": row["filter_license"],
        "min_downloads": row["min_downloads"],
        "max_rows": row["max_rows"],
        "require_gated": row["require_gated"],
        "exclude_private": row["exclude_private"],
    }


# ── Zeebe task handlers ───────────────────────────────────────────────────────

def task_hf_dataset_scan(
    filter_id: str | None = None,
    limit: int | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Scan HuggingFace Hub for datasets matching a stored filter spec.

    Variables:
      filter_id  vertex_hfhub_filter.vertex_id (required)
      limit      max datasets to process per invocation (default HF_SCAN_LIMIT)
    """
    if not filter_id:
        return {"ok": False, "error": "filter_id required"}

    fspec_row = get_kotoba_client().select_first_where(
        "vertex_hfhub_filter",
        "vertex_id",
        filter_id,
        columns=[
            "vertex_id", "slug", "filter_tags", "filter_tasks", "filter_languages",
            "filter_license", "min_downloads", "max_rows", "require_gated", "exclude_private",
            "enabled",
        ]
    )
    if not fspec_row or not fspec_row.get("enabled"):
        return {"ok": False, "error": f"filter not found or disabled: {filter_id}"}

    fspec = _parse_filter_spec(fspec_row)
    scan_limit = int(limit or _SCAN_LIMIT)
    datasets = _list_hf_datasets(fspec, scan_limit)

    inserted = 0
    matched = 0
    for info in datasets:
        ds = _extract_dataset_row(info)
        if not _dataset_passes_filter(ds, fspec):
            continue
        try:
            _upsert_dataset(ds)
            _upsert_edges(ds)
            _upsert_filter_match(filter_id, ds["vertex_id"])
            inserted += 1
            matched += 1
        except Exception as exc:
            LOG.warning("upsert failed repo=%s: %s", ds["repo_id"], exc)

    # R0: Kotoba client does not have a direct UPDATE. Fetch, modify, then upsert.
    filter_row = get_kotoba_client().select_first_where(
        "vertex_hfhub_filter", "vertex_id", filter_id
    )
    if filter_row:
        filter_row["last_run_at"] = _now_iso()
        filter_row["match_count"] = matched
        get_kotoba_client().insert_row("vertex_hfhub_filter", filter_row)

    LOG.info("hf.dataset.scan filter=%s scanned=%d matched=%d", filter_id, len(datasets), matched)
    return {"ok": True, "filter_id": filter_id, "scanned": len(datasets), "inserted": inserted, "matched": matched}


def task_hf_dataset_fetch_splits(
    repo_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Fetch split stats and parquet file list for a single dataset.

    Writes to vertex_hfhub_split, vertex_hfhub_file, edge_hfhub_split_file.

    Variables:
      repo_id  HuggingFace dataset repo id (e.g. "squad")
    """
    if not repo_id:
        return {"ok": False, "error": "repo_id required"}

    splits_resp = _ds_server_get("splits", repo_id)
    parquet_resp = _ds_server_get("parquet", repo_id)

    splits_written = 0
    files_written = 0

    if splits_resp and "splits" in splits_resp:
        sizes: dict[str, dict[str, Any]] = {}
        if parquet_resp and "parquet_files" in parquet_resp:
            for pf in parquet_resp["parquet_files"]:
                key = f"{pf.get('config','default')}:{pf.get('split','')}"
                grp = sizes.setdefault(key, {"num_bytes": 0, "num_files": 0, "files": []})
                grp["num_bytes"] += pf.get("size", 0) or 0
                grp["num_files"] += 1
                grp["files"].append(pf)

        for sp in splits_resp["splits"]:
            config = sp.get("config", "default")
            split = sp.get("split", "")
            split_vid = f"hf:split:{repo_id}:{config}:{split}"
            info_key = f"{config}:{split}"
            grp = sizes.get(info_key, {})

            ts = _now_iso()
            get_kotoba_client().insert_row(
                "vertex_hfhub_split",
                {
                    "vertex_id": split_vid,
                    "created_date": _today(),
                    "repo_id": repo_id,
                    "config_name": config,
                    "split_name": split,
                    "num_rows": sp.get("num_rows"),
                    "num_bytes": grp.get("num_bytes"),
                    "num_files": grp.get("num_files", 0),
                    "features_json": json.dumps(sp.get("features", {}), ensure_ascii=False)[:4000],
                    "actor_did": _OWNER_DID,
                    "created_at": ts,
                },
            )
            splits_written += 1

            for pf in grp.get("files", []):
                fpath = pf.get("filename", pf.get("url", ""))
                blob_url = (
                    f"https://huggingface.co/datasets/{repo_id}/resolve/main/{fpath}"
                    if not fpath.startswith("http")
                    else fpath
                )
                file_vid = f"hf:file:{repo_id}:{config}:{split}:{fpath}"
                get_kotoba_client().insert_row(
                    "vertex_hfhub_file",
                    {
                        "vertex_id": file_vid,
                        "created_date": _today(),
                        "repo_id": repo_id,
                        "split_vertex_id": split_vid,
                        "file_path": fpath,
                        "file_format": "parquet",
                        "file_size": pf.get("size"),
                        "blob_url": blob_url,
                        "actor_did": _OWNER_DID,
                        "created_at": ts,
                    },
                )
                get_kotoba_client().insert_row(
                    "edge_hfhub_split_file",
                    {"split_id": split_vid, "file_id": file_vid},
                )
                files_written += 1

    # Mark dataset active
    # R0: Kotoba client does not have a direct UPDATE. Fetch, modify, then upsert.
    dataset_row = get_kotoba_client().select_first_where(
        "vertex_hfhub_dataset", "repo_id", repo_id
    )
    if dataset_row:
        dataset_row["status"] = "active"
        dataset_row["last_scanned_at"] = _now_iso()
        get_kotoba_client().insert_row("vertex_hfhub_dataset", dataset_row)

    LOG.info("hf.dataset.fetchSplits repo=%s splits=%d files=%d", repo_id, splits_written, files_written)
    return {"ok": True, "repo_id": repo_id, "splits": splits_written, "files": files_written}


def task_hf_dataset_apply_filter(
    filter_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Re-evaluate a filter against already-catalogued vertex_hfhub_dataset rows.
    Does NOT call the HF Hub API. Useful after editing filter criteria.

    Variables:
      filter_id  vertex_hfhub_filter.vertex_id (required)
    """
    if not filter_id:
        return {"ok": False, "error": "filter_id required"}

    fspec_row = get_kotoba_client().select_first_where(
        "vertex_hfhub_filter", "vertex_id", filter_id
    )
    if not fspec_row:
        return {"ok": False, "error": f"filter not found: {filter_id}"}

    fspec = _parse_filter_spec(fspec_row)

    # Pull tags/tasks/languages per dataset via edges
    dataset_rows = get_kotoba_client().select_where(
        "vertex_hfhub_dataset",
        "status",
        "active",
        columns=["vertex_id", "repo_id", "downloads_month", "private", "gated"],
        limit=50000
    )

    matched = 0
    for ds_row in dataset_rows:
        ds_meta = {
            "vertex_id": ds_row["vertex_id"],
            "repo_id": ds_row["repo_id"],
            "downloads_month": ds_row["downloads_month"] or 0,
            "private": bool(ds_row["private"]),
            "gated": bool(ds_row["gated"]),
        }
        if not _dataset_passes_filter(ds_meta, fspec):
            continue
        _upsert_filter_match(filter_id, ds_meta["vertex_id"])
        matched += 1

    # R0: Kotoba client does not have a direct UPDATE. Fetch, modify, then upsert.
    filter_row = get_kotoba_client().select_first_where(
        "vertex_hfhub_filter", "vertex_id", filter_id
    )
    if filter_row:
        filter_row["last_run_at"] = _now_iso()
        filter_row["match_count"] = matched
        get_kotoba_client().insert_row("vertex_hfhub_filter", filter_row)

    LOG.info("hf.dataset.applyFilter filter=%s matched=%d", filter_id, matched)
    return {"ok": True, "filter_id": filter_id, "evaluated": len(dataset_rows), "matched": matched}


# ── urllib.parse import guard ─────────────────────────────────────────────────
import urllib.parse  # noqa: E402 — stdlib, used in _list_hf_datasets
