"""ADSKAILab / generic HuggingFace dataset ingest primitives.

Pulls text/code datasets from HuggingFace Hub into kotoba Datom log so the
existing training-export pipeline (`v_training_text` UNION ALL +
`trainingExport.bpmn` → B2 → `etzhayyim/etzhayyim-corpus`) automatically
picks them up.

Phase 1 scope (text/code only):
  ADSKAILab/Zero-To-CAD-100k                  parquet, cadquery_file + cadquery_ops_json
  ADSKAILab/Zero-To-CAD-1m                    parquet, same columns
  ADSKAILab/LLM-narrative-planning-taskset    3 zip archives (story/plan text)
  ADSKAILab/dsl_icl_eval-*                    parquet DSL eval

Out of scope (Phase 2 → B2 blob storage): ABC-1M, Make-A-Shape-*,
WaLa-* (3D voxel / point cloud / mesh).

Output records (created by 20260505220000_vertex_hf_dataset):
  vertex_hf_dataset           — catalog row per slug
  vertex_hf_dataset_record    — one row per training sample
                                (text_for_training feeds v_training_text)

Env vars (optional — only required for gated repos / private datasets):
  HF_TOKEN  HuggingFace API token (read scope sufficient)

Catalog rows are seeded by 20260505220200_seed_adsk_bpmn_and_catalog;
new datasets can be added by INSERTing a row into vertex_hf_dataset.
The R/P30D BPMN `adsk_ingest_dataset` calls `adsk.dataset.ingestAll`
which iterates `vertex_hf_dataset WHERE status='active'` and is
stale-by-staleSeconds.
"""

from __future__ import annotations

import io
import hashlib
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable

from kotodama.kotoba_datomic import get_kotoba_client

# ──────────────────────────────────────────────────────────────────────
# Constants / env
# ──────────────────────────────────────────────────────────────────────

_ADSK_ACTOR = "did:web:adsk.etzhayyim.com"
_HF_TOKEN = os.environ.get("HF_TOKEN", "").strip() or None

# Hard cap on a single record body persisted inline (kotoba Datom log varchar safety).
_RECORD_BYTE_HARDCAP = 64_000

# Minimum text length to be useful for training. Shorter rows are
# skipped (matches v_training_text WHERE LENGTH(...) >= 20).
_TEXT_MIN_BYTES = 20


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _truncate(s: str | None, cap: int = _RECORD_BYTE_HARDCAP) -> str | None:
    if s is None:
        return None
    # PostgreSQL text columns reject NUL (0x00) bytes — strip them.
    # Same regression as isbn (Shift-JIS / DjVu decode).
    if "\x00" in s:
        s = s.replace("\x00", "")
    b = s.encode("utf-8", errors="replace")
    if len(b) <= cap:
        return s
    return b[:cap].decode("utf-8", errors="replace")


def _vertex_id(slug: str, record_id: str) -> str:
    safe_slug = re.sub(r"[^a-zA-Z0-9]", "-", slug)
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "-", record_id)[:200]
    return f"at://{_ADSK_ACTOR}/com.etzhayyim.apps.adsk.record/{safe_slug}--{safe_id}"


def _rw_executemany(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    client = get_kotoba_client()
    n = 0
    for row_dict in rows:
        client.insert_row("vertex_hf_dataset_record", row_dict)
        n += 1
    return n


def _update_catalog(slug: str, row_count: int) -> None:
    client = get_kotoba_client()
    client.insert_row("vertex_hf_dataset", {
        "slug": slug,
        "row_count_ingested": row_count,
        "last_synced_at": _now_iso(),
    })


# ──────────────────────────────────────────────────────────────────────
# HF dataset readers (stream-friendly)
# ──────────────────────────────────────────────────────────────────────


def _hf_load_streaming(slug: str, split: str | None) -> Iterable[dict[str, Any]]:
    """Stream rows from a HuggingFace dataset.

    Lazy import of `datasets` so the rest of kotodama can run on
    pods without the heavy pyarrow/datasets stack installed.

    When `split` is omitted, iterate **all** splits sequentially so we
    don't silently leave behind train/validation rows just because
    `load_dataset` returned the test split first.
    """
    from datasets import load_dataset

    kwargs: dict[str, Any] = {"streaming": True}
    if _HF_TOKEN:
        kwargs["token"] = _HF_TOKEN
    if split:
        kwargs["split"] = split

    ds = load_dataset(slug, **kwargs)
    if split:
        yield from ds
        return
    # IterableDatasetDict-like: keys() are split names.
    if hasattr(ds, "keys"):
        for split_name in ds.keys():
            for row in ds[split_name]:
                # Tag the row with its origin split so the extractor
                # can record it. We mutate a shallow copy to avoid
                # poisoning the upstream cache.
                if isinstance(row, dict):
                    row = {**row, "_split": split_name}
                yield row
    else:
        yield from ds


def _hf_snapshot_files(slug: str, allow_patterns: list[str] | None = None) -> str:
    """Download the raw repo (LFS resolved) and return the local dir.

    Used for datasets whose viewer is unavailable (e.g. zip-only
    archives like LLM-narrative-planning-taskset).
    """
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=slug,
        repo_type="dataset",
        token=_HF_TOKEN,
        allow_patterns=allow_patterns,
    )


# ──────────────────────────────────────────────────────────────────────
# Per-dataset text extractors
# ──────────────────────────────────────────────────────────────────────


def _extract_zero_to_cad(row: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Return (record_id, text_for_training, lang).

    Concatenates the executable CadQuery Python source + the operations
    JSON. Both are valuable training signal: code teaches the program
    surface, ops_json teaches the construction sequence semantics.
    """
    record_id = str(row.get("uuid") or "").strip()
    parts: list[str] = []

    cad = row.get("cadquery_file")
    if isinstance(cad, (bytes, bytearray)):
        try:
            parts.append(bytes(cad).decode("utf-8", errors="replace"))
        except Exception:
            pass
    elif isinstance(cad, str) and cad:
        parts.append(cad)

    ops = row.get("cadquery_ops_json")
    if isinstance(ops, str) and ops:
        parts.append("\n# ops:\n" + ops)
    elif ops is not None:
        try:
            parts.append("\n# ops:\n" + json.dumps(ops, ensure_ascii=False))
        except Exception:
            pass

    text = "\n".join(parts) if parts else None
    return record_id, text, "python"


def _extract_dsl_icl_eval(row: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """DSL eval rows. The `dsl_mass-dsl_architecture` field holds the
    structured DSL text most useful for training; fall back to a JSON
    dump of the row if absent."""
    site = row.get("site_id") or ""
    bld = row.get("building_id") or ""
    sty = row.get("storey_id") or ""
    record_id = f"{site}-{bld}-{sty}".strip("-") or str(row.get("ifc_file") or "")[:64]

    dsl = row.get("dsl_mass-dsl_architecture")
    if isinstance(dsl, dict):
        text = dsl.get("dsl") or json.dumps(dsl, ensure_ascii=False)
    elif isinstance(dsl, str):
        text = dsl
    else:
        text = json.dumps({k: v for k, v in row.items() if not isinstance(v, (bytes, bytearray))}, ensure_ascii=False, default=str)

    return record_id, text, "en"


def _extract_generic(row: dict[str, Any], text_columns: list[str] | None) -> tuple[str, str | None, str | None]:
    """Generic fallback. If `text_columns` is given, concatenate those
    in order; otherwise serialize the whole row to JSON."""
    rid = str(row.get("id") or row.get("uuid") or row.get("uid") or "")[:200]
    if not rid:
        # synthesize from a stable hash of the row contents
        rid = str(abs(hash(json.dumps({k: str(v)[:100] for k, v in row.items()}, sort_keys=True))))[:16]

    if text_columns:
        parts = []
        for col in text_columns:
            v = row.get(col)
            if isinstance(v, (bytes, bytearray)):
                try:
                    parts.append(bytes(v).decode("utf-8", errors="replace"))
                except Exception:
                    pass
            elif v is not None:
                parts.append(str(v))
        text = "\n".join(parts) if parts else None
    else:
        text = json.dumps({k: (v if not isinstance(v, (bytes, bytearray)) else "<bytes>") for k, v in row.items()},
                          ensure_ascii=False, default=str)
    return rid, text, None


def _row_to_record_args(
    slug: str,
    row: dict[str, Any],
    split: str | None,
    text_columns: list[str] | None,
    row_index: int = 0,
) -> tuple[Any, ...] | None:
    if "Zero-To-CAD" in slug:
        rid, text, lang = _extract_zero_to_cad(row)
    elif "dsl_icl_eval" in slug:
        rid, text, lang = _extract_dsl_icl_eval(row)
    else:
        rid, text, lang = _extract_generic(row, text_columns)

    if not rid or not text:
        return None
    # Always disambiguate with the row index so datasets where multiple
    # rows share the same primary key (e.g. dsl_icl_eval variants over
    # the same building) don't collapse to a single row on PK collision.
    rid = f"{rid}#{row_index}"
    text = _truncate(text)
    if text is None:
        return None
    text_bytes = len(text.encode("utf-8", errors="replace"))
    if text_bytes < _TEXT_MIN_BYTES:
        return None

    raw_payload = _truncate(json.dumps(
        {k: (v if not isinstance(v, (bytes, bytearray)) else "<bytes>") for k, v in row.items()},
        ensure_ascii=False, default=str,
    ))

    vid = _vertex_id(slug, rid)
    return {
        "vertex_id": vid,
        "owner_did": _ADSK_ACTOR,
        "sensitivity_ord": 0,
        "slug": slug,
        "record_id": rid,
        "split": split,
        "lang": lang,
        "text_for_training": text,
        "text_byte_size": text_bytes,
        "raw_json": raw_payload,
        "source_uri": f"hf:{slug}",
        "created_at": _now_iso(),
        "org_id": _ADSK_ACTOR,
        "user_id": _ADSK_ACTOR,
        "actor_id": "sys.adsk.ingest",
    }


# ──────────────────────────────────────────────────────────────────────
# Special-case: zip-archive datasets (no parquet viewer)
# ──────────────────────────────────────────────────────────────────────


def _ingest_narrative_planning(slug: str, limit: int | None) -> int:
    """LLM-narrative-planning-taskset = 3 zip archives. We unzip each
    and emit one record per text file inside (story / plan / domain)."""
    repo_dir = _hf_snapshot_files(slug, allow_patterns=["*.zip", "README.md"])
    rows: list[tuple[Any, ...]] = []
    n = 0
    cap = limit if (limit is not None and limit > 0) else None

    for fname in sorted(os.listdir(repo_dir)):
        if not fname.endswith(".zip"):
            continue
        archive = fname[:-4]
        zpath = os.path.join(repo_dir, fname)
        with zipfile.ZipFile(zpath) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                if cap is not None and n >= cap:
                    break
                try:
                    body = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    continue
                text = _truncate(body)
                if not text or len(text.encode("utf-8", errors="replace")) < _TEXT_MIN_BYTES:
                    continue
                rid = f"{archive}/{member}"
                vid = _vertex_id(slug, rid)
                rows.append({
                    "vertex_id": vid,
                    "owner_did": _ADSK_ACTOR,
                    "sensitivity_ord": 0,
                    "slug": slug,
                    "record_id": rid,
                    "split": archive,
                    "lang": None,
                    "text_for_training": text,
                    "text_byte_size": len(text.encode("utf-8", errors="replace")),
                    "raw_json": _truncate(json.dumps({"archive": archive, "member": member})),
                    "source_uri": f"hf:{slug}",
                    "created_at": _now_iso(),
                    "org_id": _ADSK_ACTOR,
                    "user_id": _ADSK_ACTOR,
                    "actor_id": "sys.adsk.ingest",
                })
                n += 1
        if cap is not None and n >= cap:
            break

    inserted = _rw_executemany(rows)
    _update_catalog(slug, inserted)
    return inserted


# ──────────────────────────────────────────────────────────────────────
# LangServer task handlers
# ──────────────────────────────────────────────────────────────────────


async def task_adsk_dataset_ingest(
    slug: str,
    split: str | None = None,
    limit: int | None = None,
    textColumns: list[str] | None = None,
    force: bool = False,
) -> dict:
    """Ingest one HF dataset by slug into vertex_hf_dataset_record.

    Routing:
      - LLM-narrative-planning-taskset → zip archive path
      - everything else → streaming load_dataset path
    """
    if not slug:
        return {"ok": False, "error": "slug is required"}

    try:
        if "narrative-planning" in slug.lower():
            n = _ingest_narrative_planning(slug, limit)
            return {"ok": True, "slug": slug, "rows": n, "skipped": 0}

        rows: list[tuple[Any, ...]] = []
        skipped = 0
        cap = limit if (limit is not None and limit > 0) else None
        for i, row in enumerate(_hf_load_streaming(slug, split)):
            if cap is not None and i >= cap:
                break
            row_split = split or (row.pop("_split", None) if isinstance(row, dict) else None)
            args = _row_to_record_args(slug, row, row_split, textColumns, row_index=i)
            if args is None:
                skipped += 1
                continue
            rows.append(args)
            # flush in batches of 500 to keep memory bounded for 1M-row datasets
            if len(rows) >= 500:
                _rw_executemany(rows)
                rows = []
        inserted = _rw_executemany(rows)

        # Recompute total (best-effort): count what we actually inserted
        # this run plus what was already there.
        client = get_kotoba_client()
        total = int(client.aggregate_where("vertex_hf_dataset_record", "count", "*", "slug", slug))
        _update_catalog(slug, total)

        return {"ok": True, "slug": slug, "rows": inserted, "skipped": skipped, "total": total}
    except Exception as e:
        return {"ok": False, "slug": slug, "error": f"{type(e).__name__}: {e}"}


async def task_adsk_dataset_ingest_all(
    staleSeconds: int = 30 * 24 * 3600,
    perDatasetLimit: int = 10000,
) -> dict:
    """Iterate vertex_hf_dataset rows and re-ingest those staler than
    `staleSeconds`. Used by the R/P30D `adsk_ingest_dataset` BPMN.

    Returns a per-dataset summary so audit emit has something to chew
    on. On per-dataset failure we keep going; the failure is captured
    in the summary."""
    threshold_ts = time.gmtime(time.time() - max(0, int(staleSeconds)))
    threshold_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ", threshold_ts)

    client = get_kotoba_client()
    rows = client.select_where("vertex_hf_dataset", "status", "active", columns=["slug", "last_synced_at"]) or []

    results: list[dict[str, Any]] = []
    total_rows = 0
    for r in rows:
        slug, last_synced = (r["slug"], r["last_synced_at"])
        if last_synced and last_synced > threshold_iso:
            results.append({"slug": slug, "skipped": True, "reason": "fresh"})
            continue
        sub = await task_adsk_dataset_ingest(slug=slug, limit=perDatasetLimit)
        results.append(sub)
        if sub.get("ok"):
            total_rows += int(sub.get("rows") or 0)

    return {"ok": True, "datasets": len(results), "rows": total_rows, "results": results}


async def task_adsk_3d_blob_ingest(
    slug: str,
    sampleId: str | None = None,
    format: str | None = None,
    b2Bucket: str | None = None,
    b2Key: str | None = None,
    sha256Hex: str | None = None,
    byteSize: int | None = None,
    polygonCount: int | None = None,
    voxelDim: int | None = None,
    latentDim: int | None = None,
    license: str | None = None,
    hfUrl: str | None = None,
    source: str | None = None,
    ingestedByRunId: str | None = None,
) -> dict:
    """Register an already-staged 3D blob in ``vertex_3d_blob``.

    ADR-2605080700 Phase 2 stores large ABC-1M / Make-A-Shape / WaLa
    artifacts in B2 and persists only catalog metadata in kotoba Datom log.
    The heavy download/upload path is handled by the caller; this task
    validates and records the manifest row.
    """
    if not slug:
        return {"ok": False, "error": "slug is required"}
    if not b2Bucket or not b2Key:
        return {"ok": False, "slug": slug, "error": "b2Bucket and b2Key are required"}

    sample_id = sampleId or b2Key.rsplit("/", 1)[-1]
    fmt = (format or b2Key.rsplit(".", 1)[-1] or "blob").lower()
    sha = (sha256Hex or hashlib.sha256(f"{b2Bucket}/{b2Key}".encode()).hexdigest()).lower()
    if sha.startswith("0x"):
        sha = sha[2:]
    now = _now_iso()
    ts_ms = int(time.time() * 1000)
    vertex_id = f"at://{_ADSK_ACTOR}/com.etzhayyim.apps.adsk.blob3d/{re.sub(r'[^a-zA-Z0-9._-]', '-', slug)}--{sha[:16]}"

    client = get_kotoba_client()
    client.insert_row("vertex_3d_blob", {
        "vertex_id": vertex_id,
        "_seq": None,
        "created_date": _today_date(),
        "sensitivity_ord": 1,
        "owner_did": _ADSK_ACTOR,
        "source": source or "hf",
        "slug": slug,
        "sample_id": sample_id,
        "format": fmt,
        "b2_bucket": b2Bucket,
        "b2_key": b2Key,
        "sha256_hex": sha,
        "byte_size": int(byteSize or 0),
        "polygon_count": polygonCount,
        "voxel_dim": voxelDim,
        "latent_dim": latentDim,
        "license": license,
        "hf_url": hfUrl or f"hf:{slug}",
        "ts_ms": ts_ms,
        "ingested_by_run_id": ingestedByRunId,
        "actor_did": _ADSK_ACTOR,
        "org_did": _ADSK_ACTOR,
        "at_did": None,
        "created_at": now,
        "org_id": None,
        "user_id": None,
        "actor_id": None,
    })

    return {
        "ok": True,
        "slug": slug,
        "sampleId": sample_id,
        "format": fmt,
        "vertexId": vertex_id,
        "b2Bucket": b2Bucket,
        "b2Key": b2Key,
        "sha256Hex": sha,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 21_600_000) -> None:
    """Wire all adsk task types onto the shared LangServer worker."""
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("adsk.dataset.ingest",    task_adsk_dataset_ingest)
    t("adsk.dataset.ingestAll", task_adsk_dataset_ingest_all)
    t("adsk.blob3d.ingest",     task_adsk_3d_blob_ingest)


__all__ = [
    "register",
    "task_adsk_dataset_ingest",
    "task_adsk_dataset_ingest_all",
    "task_adsk_3d_blob_ingest",
]
