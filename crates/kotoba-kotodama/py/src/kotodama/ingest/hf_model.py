"""
hf_model — HuggingFace Hub model catalog ingest.

Zeebe task types:
  hf.model.scan             — apply a vertex_hfhub_filter (entity_type=model|both)
                              → populate vertex_hfhub_model + edges + edge_hfhub_filter_match
  hf.model.fetchDetail      — fetch full model card for a single repo_id
  hf.model.resolveLineage   — resolve edge_hfhub_model_base + edge_hfhub_model_dataset links

HF Hub API used:
  GET /api/models?limit=N&filter=...&full=true   — list with metadata
  GET /api/models/{repo_id}                       — single model detail

Env (reuses K8s Secret training-hf-creds):
  HF_TOKEN   read-only HuggingFace API token

kotoba Datom log conventions:
  - No ON CONFLICT — PK implicit upsert
  - LIMIT inlined as {int(n)} — avoids psycopg3 prepared-statement rejection
  - No CURRENT_DATE in prepared statements
  - flush=False on all inserts
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger(__name__)

_OWNER_DID = "did:web:ingest.etzhayyim.com"
_HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
_HF_API = "https://huggingface.co/api"
_TIMEOUT = 30
_SCAN_LIMIT = int(os.environ.get("HF_MODEL_SCAN_LIMIT", "500"))


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _hf_request(url: str) -> Any:
    headers: dict[str, str] = {"Accept": "application/json"}
    if _HF_TOKEN:
        headers["Authorization"] = f"Bearer {_HF_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        LOG.warning("hf_request failed url=%s: %s", url, exc)
        return None





# ── HF Hub API — model list ───────────────────────────────────────────────────

def _list_hf_models(fspec: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Call HF Hub /api/models with filter criteria."""
    base = f"{_HF_API}/models?full=true&limit={int(limit)}"
    for tag in fspec.get("tags", []):
        base += f"&filter={urllib.parse.quote(tag)}"
    for task in fspec.get("tasks", []):
        base += f"&filter={urllib.parse.quote(task)}"
    for lang in fspec.get("languages", []):
        base += f"&filter=language:{urllib.parse.quote(lang)}"
    if fspec.get("license"):
        base += f"&filter=license:{urllib.parse.quote(fspec['license'])}"
    result = _hf_request(base)
    return result if isinstance(result, list) else []


def _fetch_model_detail(repo_id: str) -> dict[str, Any] | None:
    """GET /api/models/{repo_id} — full model card."""
    return _hf_request(f"{_HF_API}/models/{urllib.parse.quote(repo_id, safe='/')}")


# ── field extraction ──────────────────────────────────────────────────────────

def _extract_model_row(info: dict[str, Any]) -> dict[str, Any]:
    """Normalise a HF Hub model info dict into vertex_hfhub_model columns."""
    repo_id = info.get("id") or info.get("modelId", "")
    card = info.get("cardData") or {}
    cfg = info.get("config") or {}
    sf = info.get("safetensors") or {}
    ti = info.get("transformersInfo") or {}

    tags: list[str] = info.get("tags") or []

    # Derive task categories from tags (e.g. "task_categories:text-classification")
    task_categories: list[str] = []
    languages: list[str] = []
    license_tag = ""
    for t in tags:
        if t.startswith("task_categories:"):
            task_categories.append(t.removeprefix("task_categories:"))
        elif t.startswith("language:"):
            languages.append(t.removeprefix("language:"))
        elif t.startswith("license:"):
            license_tag = t.removeprefix("license:")

    # pipeline_tag is more reliable than task_categories for primary task
    pipeline_tag = info.get("pipeline_tag") or (task_categories[0] if task_categories else "")

    # Parameter count from safetensors.total
    num_parameters: int | None = sf.get("total")
    if num_parameters is not None:
        num_parameters = int(num_parameters)

    # Primary dtype from safetensors.parameters (key with max value)
    params_by_dtype: dict[str, int] = sf.get("parameters") or {}
    primary_dtype = ""
    if params_by_dtype:
        primary_dtype = max(params_by_dtype, key=lambda k: params_by_dtype[k])

    # Architectures
    archs: list[str] = cfg.get("architectures") or []
    architecture = archs[0] if archs else ""

    # base_model from cardData (can be string or list)
    base_model_raw = card.get("base_model")
    base_model = ""
    base_models: list[str] = []
    if isinstance(base_model_raw, str):
        base_model = base_model_raw
        base_models = [base_model_raw] if base_model_raw else []
    elif isinstance(base_model_raw, list):
        base_models = [str(b) for b in base_model_raw if b]
        base_model = base_models[0] if base_models else ""

    # Training datasets from cardData.datasets
    training_datasets: list[str] = []
    ds_raw = card.get("datasets")
    if isinstance(ds_raw, list):
        training_datasets = [str(d) for d in ds_raw if d]
    elif isinstance(ds_raw, str) and ds_raw:
        training_datasets = [ds_raw]

    return {
        "vertex_id": f"hf:model:{repo_id}",
        "repo_id": repo_id,
        "author": info.get("author", ""),
        "sha": info.get("sha", ""),
        "pipeline_tag": pipeline_tag,
        "library_name": info.get("library_name", ""),
        "model_type": cfg.get("model_type", ""),
        "architecture": architecture,
        "auto_model_class": ti.get("auto_model", ""),
        "inference_state": str(info.get("inference", "") or ""),
        "num_parameters": num_parameters,
        "primary_dtype": primary_dtype,
        "used_storage_bytes": info.get("usedStorage"),
        "license": card.get("license") or license_tag,
        "base_model": base_model,
        "trending_score": info.get("trendingScore"),
        "downloads_month": int(info.get("downloads") or 0),
        "likes": int(info.get("likes") or 0),
        "gated": bool(info.get("gated", False)),
        "disabled": bool(info.get("disabled", False)),
        "private": bool(info.get("private", False)),
        "card_data": json.dumps(card, ensure_ascii=False)[:8000],
        "spaces_count": len(info.get("spaces") or []),
        "created_at_hf": info.get("createdAt", ""),
        "last_modified_hf": info.get("lastModified", ""),
        # derived
        "tags": tags,
        "task_categories": task_categories,
        "languages": languages,
        "base_models": base_models,
        "training_datasets": training_datasets,
    }


def _model_passes_filter(m: dict[str, Any], fspec: dict[str, Any]) -> bool:
    if fspec.get("exclude_private") and m["private"]:
        return False
    if fspec.get("require_gated") and not m["gated"]:
        return False
    min_dl = fspec.get("min_downloads")
    if min_dl and m["downloads_month"] < min_dl:
        return False
    return True


# ── DB writes ─────────────────────────────────────────────────────────────────

def _upsert_model(m: dict[str, Any]) -> None:
    client = get_kotoba_client()
    ts = _now_iso()
    date = _today()

    row_dict = {
        "vertex_id": m["vertex_id"],
        "created_date": date,
        "repo_id": m["repo_id"],
        "author": m["author"],
        "sha": m["sha"],
        "pipeline_tag": m["pipeline_tag"],
        "library_name": m["library_name"],
        "model_type": m["model_type"],
        "architecture": m["architecture"],
        "auto_model_class": m["auto_model_class"],
        "inference_state": m["inference_state"],
        "num_parameters": m["num_parameters"],
        "primary_dtype": m["primary_dtype"],
        "used_storage_bytes": m["used_storage_bytes"],
        "license": m["license"],
        "base_model": m["base_model"],
        "trending_score": m["trending_score"],
        "downloads_month": m["downloads_month"],
        "likes": m["likes"],
        "gated": m["gated"],
        "disabled": m["disabled"],
        "private": m["private"],
        "card_data": m["card_data"],
        "spaces_count": m["spaces_count"],
        "status": "active",
        "last_scanned_at": ts,
        "created_at_hf": m["created_at_hf"],
        "last_modified_hf": m["last_modified_hf"],
        "actor_did": _OWNER_DID,
        "created_at": ts,
    }
    client.insert_row("vertex_hfhub_model", row_dict)


def _upsert_model_edges(m: dict[str, Any]) -> None:
    client = get_kotoba_client()
    vid = m["vertex_id"]
    for tag in m["tags"]:
        client.insert_row("edge_hfhub_model_tag", {"edge_id": f"{vid}-{tag}", "model_id": vid, "tag": tag})
    for task in m["task_categories"]:
        client.insert_row("edge_hfhub_model_task", {"edge_id": f"{vid}-{task}", "model_id": vid, "task_category": task})
    # Also insert pipeline_tag as a task edge (more reliable)
    if m["pipeline_tag"] and m["pipeline_tag"] not in m["task_categories"]:
        client.insert_row("edge_hfhub_model_task", {"edge_id": f"{vid}-{m['pipeline_tag']}", "model_id": vid, "task_category": m["pipeline_tag"]})
    for lang in m["languages"]:
        client.insert_row("edge_hfhub_model_language", {"edge_id": f"{vid}-{lang}", "model_id": vid, "lang_code": lang})
    for depth, bm in enumerate(m["base_models"], start=1):
        client.insert_row("edge_hfhub_model_base", {"edge_id": f"{vid}-{bm}-{depth}", "model_id": vid, "base_model_id": bm, "depth": depth})
    for ds in m["training_datasets"]:
        client.insert_row("edge_hfhub_model_dataset", {"edge_id": f"{vid}-{ds}", "model_id": vid, "dataset_repo_id": ds})


def _upsert_filter_match(filter_id: str, model_id: str) -> None:
    client = get_kotoba_client()
    ts = _now_iso()
    row_dict = {
        "edge_id": f"{filter_id}-{model_id}",
        "filter_id": filter_id,
        "dataset_id": model_id,
        "matched_at": ts,
    }
    client.insert_row("edge_hfhub_filter_match", row_dict)


# ── Zeebe task implementations ────────────────────────────────────────────────

def task_hf_model_scan(
    filter_id: str | None = None,
    limit: int | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Scan HuggingFace Hub for models matching a stored filter spec.
    Uses the same vertex_hfhub_filter table as dataset scan (entity_type='model'|'both').

    Variables:
      filter_id  vertex_hfhub_filter.vertex_id (required)
      limit      max models per invocation (default HF_MODEL_SCAN_LIMIT)
    """
    if not filter_id:
        return {"ok": False, "error": "filter_id required"}

    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_hfhub_filter",
        "vertex_id",
        filter_id,
        columns=[
            "vertex_id", "slug", "filter_tags", "filter_tasks", "filter_languages",
            "filter_license", "min_downloads", "max_rows", "require_gated", "exclude_private", "enabled"
        ]
    )
    # R0: select_first_where only supports a single WHERE clause, so 'enabled' check is done in Python.
    if not row or not row.get("enabled"):
        return {"ok": False, "error": f"filter not found or disabled: {filter_id}"}

    (vid, slug, filter_tags, filter_tasks, filter_languages,
     filter_license, min_downloads, max_rows, require_gated, exclude_private) = (
        row["vertex_id"], row["slug"], row["filter_tags"], row["filter_tasks"], row["filter_languages"],
        row["filter_license"], row["min_downloads"], row["max_rows"], row["require_gated"], row["exclude_private"]
    )

    fspec = {
        "tags": json.loads(filter_tags) if filter_tags else [],
        "tasks": json.loads(filter_tasks) if filter_tasks else [],
        "languages": json.loads(filter_languages) if filter_languages else [],
        "license": filter_license,
        "min_downloads": min_downloads,
        "require_gated": require_gated,
        "exclude_private": exclude_private,
    }

    scan_limit = int(limit or _SCAN_LIMIT)
    models = _list_hf_models(fspec, scan_limit)

    inserted = 0
    matched = 0
    for info in models:
        m = _extract_model_row(info)
        if not _model_passes_filter(m, fspec):
            continue
        try:
            _upsert_model(m)
            _upsert_model_edges(m)
            _upsert_filter_match(filter_id, m["vertex_id"])
            inserted += 1
            matched += 1
        except Exception as exc:
            LOG.warning("model upsert failed repo=%s: %s", m["repo_id"], exc)

    client.insert_row(
        "vertex_hfhub_filter",
        {
            "vertex_id": filter_id,
            "last_run_at": _now_iso(),
            "match_count": matched,
        },
    )

    LOG.info("hf.model.scan filter=%s scanned=%d matched=%d", filter_id, len(models), matched)
    return {"ok": True, "filter_id": filter_id, "scanned": len(models), "inserted": inserted, "matched": matched}


def task_hf_model_fetch_detail(
    repo_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Fetch full model card detail for a single repo_id and upsert all fields.
    Enriches a previously-scanned model (from list API which has fewer fields).

    Variables:
      repo_id  HuggingFace model repo id (e.g. "google/gemma-4-31B-it")
    """
    if not repo_id:
        return {"ok": False, "error": "repo_id required"}

    info = _fetch_model_detail(repo_id)
    if not info:
        return {"ok": False, "error": f"model not found or API error: {repo_id}"}

    m = _extract_model_row(info)
    try:
        _upsert_model(m)
        _upsert_model_edges(m)
    except Exception as exc:
        LOG.warning("model fetchDetail failed repo=%s: %s", repo_id, exc)
        return {"ok": False, "repo_id": repo_id, "error": str(exc)}

    return {
        "ok": True,
        "repo_id": repo_id,
        "pipeline_tag": m["pipeline_tag"],
        "num_parameters": m["num_parameters"],
        "base_model": m["base_model"],
        "training_datasets": m["training_datasets"],
    }


def task_hf_model_resolve_lineage(
    batch_size: int = 50,
    **_: Any,
) -> dict[str, Any]:
    """
    For edge_hfhub_model_dataset rows where dataset_vertex_id is NULL,
    attempt to resolve to an existing vertex_hfhub_dataset vertex_id.
    Also fetches detail for pending models that lack num_parameters.

    Idempotent — safe to re-run.
    """
    client = get_kotoba_client()

    # Resolve dataset cross-references
    # R0: Multi-predicate WHERE (dataset_vertex_id IS NULL) and LIMIT handled in Python.
    all_dataset_edges = client.select_where("edge_hfhub_model_dataset", "dataset_vertex_id", None, limit=batch_size)
    unresolved = [
        (edge["model_id"], edge["dataset_repo_id"])
        for edge in all_dataset_edges
        if edge["dataset_vertex_id"] is None
    ]

    ds_resolved = 0
    for (model_id, ds_repo_id) in unresolved:
        ds_vid = f"hf:dataset:{ds_repo_id}"
        exists = client.select_first_where(
            "vertex_hfhub_dataset",
            "vertex_id",
            ds_vid,
            columns=["vertex_id"]
        )
        if exists:
            client.insert_row(
                "edge_hfhub_model_dataset",
                {
                    "edge_id": f"{model_id}-{ds_repo_id}",  # Assuming edge_id exists, needs to be unique
                    "model_id": model_id,
                    "dataset_repo_id": ds_repo_id,
                    "dataset_vertex_id": ds_vid,
                },
            )
            ds_resolved += 1

    # Enrich models that are missing num_parameters (were scanned from list API)
    # R0: Multi-predicate WHERE (num_parameters IS NULL, status='active') and ORDER BY handled in Python.
    all_hfhub_models = client.select_where("vertex_hfhub_model", "num_parameters", None, limit=batch_size * 2) # Fetch more to allow for filtering
    pending = [
        model["repo_id"]
        for model in all_hfhub_models
        if model["num_parameters"] is None and model["status"] == "active"
    ]
    # Apply order by downloads_month DESC in Python
    pending.sort(key=lambda repo_id: client.select_first_where("vertex_hfhub_model", "repo_id", repo_id, columns=["downloads_month"])["downloads_month"], reverse=True)
    pending = pending[:batch_size]

    enriched = 0
    for repo_id in pending:
        result = task_hf_model_fetch_detail(repo_id=repo_id)
        if result.get("ok"):
            enriched += 1

    LOG.info("hf.model.resolveLineage ds_resolved=%d enriched=%d", ds_resolved, enriched)
    return {"ok": True, "ds_resolved": ds_resolved, "enriched": enriched}
