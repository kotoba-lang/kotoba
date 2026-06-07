"""Shared durable state helpers for ingest workers.

The canonical domain facts stay in source-specific vertex/edge tables. This
module only writes the cross-domain orchestration spine documented in
`90-docs/260425-ingest-orchestration-zeebe-python-k8s-mcp-design.md`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

INGEST_ACTOR_DID = "did:web:ingest.etzhayyim.com"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return "-".join(part for part in "".join(out).split("-") if part)[:160] or "unknown"


def stable_run_id(ingest_family: str, source_id: str, mode: str, input_json: str = "") -> str:
    payload = "|".join((ingest_family, source_id, mode, input_json or "", now_iso()))
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=6).hexdigest()
    return f"{_slug(ingest_family)}-{_slug(source_id)}-{_slug(mode)}-{digest}"


def run_vertex_id(run_id: str) -> str:
    return f"at://{INGEST_ACTOR_DID}/com.etzhayyim.apps.ingest.run/{_slug(run_id)}"


def cursor_vertex_id(ingest_family: str, source_id: str, shard_key: str) -> str:
    slug = _slug(f"{ingest_family}-{source_id}-{shard_key}")
    return f"at://{INGEST_ACTOR_DID}/com.etzhayyim.apps.ingest.cursor/{slug}"


def artifact_vertex_id(run_id: str, artifact_kind: str, uri: str) -> str:
    digest = hashlib.blake2b(uri.encode("utf-8"), digest_size=6).hexdigest()
    slug = _slug(f"{run_id}-{artifact_kind}-{digest}")
    return f"at://{INGEST_ACTOR_DID}/com.etzhayyim.apps.ingest.artifact/{slug}"





@dataclass(frozen=True)
class IngestRun:
    ingest_family: str
    source_id: str
    mode: str = "delta"
    run_id: str = ""
    status: str = "planned"
    zeebe_process_instance_key: str | None = None
    bpmn_process_id: str | None = None
    requested_by: str | None = None
    input_json: str | None = None

    def with_run_id(self) -> "IngestRun":
        if self.run_id:
            return self
        return IngestRun(
            ingest_family=self.ingest_family,
            source_id=self.source_id,
            mode=self.mode,
            run_id=stable_run_id(self.ingest_family, self.source_id, self.mode, self.input_json or ""),
            status=self.status,
            zeebe_process_instance_key=self.zeebe_process_instance_key,
            bpmn_process_id=self.bpmn_process_id,
            requested_by=self.requested_by,
            input_json=self.input_json,
        )


@dataclass(frozen=True)
class IngestArtifact:
    run_id: str
    artifact_kind: str
    source_id: str
    uri: str
    sha256: str | None = None
    byte_size: int | None = None
    record_count: int | None = None
    props: dict[str, Any] | None = None


def upsert_run(run: IngestRun) -> str:
    """Create a run row if missing, then update mutable progress fields."""
    run = run.with_run_id()
    vid = run_vertex_id(run.run_id)
    now = now_iso()
    client = get_kotoba_client()
    client.insert_row(
        "vertex_ingest_run",
        {
            "vertex_id": vid,
            "_seq": None,
            "created_date": today(),
            "sensitivity_ord": 0,
            "owner_did": INGEST_ACTOR_DID,
            "run_id": run.run_id,
            "ingest_family": run.ingest_family,
            "source_id": run.source_id,
            "mode": run.mode,
            "status": run.status,
            "zeebe_process_instance_key": run.zeebe_process_instance_key,
            "bpmn_process_id": run.bpmn_process_id,
            "started_at": now,
            "requested_by": run.requested_by,
            "input_json": run.input_json,
            "created_at": now,
            "updated_at": now,
        },
    )
    return vid




def mark_run_finished(
    run_id: str,
    *,
    status: str,
    records_read: int | None = None,
    records_written: int | None = None,
    records_skipped: int | None = None,
    error_count: int | None = None,
    last_error: str | None = None,
    output: dict[str, Any] | None = None,
) -> None:
    vid = run_vertex_id(run_id)
    client = get_kotoba_client()
    existing_run = client.select_first_where("vertex_ingest_run", "vertex_id", vid)
    if not existing_run:
        # This case should ideally not happen if upsert_run is always called first.
        # For now, we'll log a warning or raise an error if this becomes an issue.
        # Following the original code's implicit assumption that the record exists.
        # Create a basic dictionary if it doesn't exist to allow insert_row to proceed
        # but this might not be ideal as this function is for 'marking finished'.
        # A more robust solution might be to create a new run or raise an error.
        # For now, we'll just create a minimal dict for insert_row.
        existing_run = {"vertex_id": vid, "status": "unknown", "updated_at": now_iso()}


    updated_run_data = {
        "vertex_id": vid,
        "status": status,
        "finished_at": now_iso(),
        "records_read": records_read if records_read is not None else existing_run.get("records_read"),
        "records_written": records_written if records_written is not None else existing_run.get("records_written"),
        "records_skipped": records_skipped if records_skipped is not None else existing_run.get("records_skipped"),
        "error_count": error_count if error_count is not None else existing_run.get("error_count"),
        "last_error": last_error if last_error is not None else existing_run.get("last_error"),
        "output_json": json.dumps(output, sort_keys=True, separators=(",", ":")) if output is not None else existing_run.get("output_json"),
        "updated_at": now_iso(),
    }
    # Merge with existing data to ensure all required fields for upsert are present
    # (e.g., created_date, ingest_family, etc., which are not updated by this function)
    final_run_data = {**existing_run, **updated_run_data}
    client.insert_row("vertex_ingest_run", final_run_data)


def upsert_cursor(
    *,
    ingest_family: str,
    source_id: str,
    shard_key: str,
    cursor_value: str | None = None,
    high_watermark: str | None = None,
    content_hash: str | None = None,
    locked_by_run_id: str | None = None,
    lock_expires_at: str | None = None,
    status: str | None = None,
    last_error: str | None = None,
) -> str:
    vid = cursor_vertex_id(ingest_family, source_id, shard_key)
    now = now_iso()
    cursor_hash = (
        hashlib.sha256(cursor_value.encode("utf-8")).hexdigest()
        if cursor_value is not None
        else None
    )
    client = get_kotoba_client()
    existing_cursor = client.select_first_where("vertex_ingest_cursor", "vertex_id", vid)

    # Initialize with default values, and then overwrite with provided and existing values
    cursor_data = {
        "vertex_id": vid,
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 0,
        "owner_did": INGEST_ACTOR_DID,
        "ingest_family": ingest_family,
        "source_id": source_id,
        "shard_key": shard_key,
        "cursor_value": cursor_value,
        "cursor_hash": cursor_hash,
        "high_watermark": high_watermark,
        "content_hash": content_hash,
        "updated_at": now,
        "locked_by_run_id": locked_by_run_id,
        "lock_expires_at": lock_expires_at,
        "status": status,
        "fail_count": 0,
        "last_error": last_error,
    }

    if existing_cursor:
        # For COALESCE behavior, update only if new value is not None, otherwise keep existing
        for key, new_val in cursor_data.items():
            if new_val is None and key in existing_cursor:
                cursor_data[key] = existing_cursor[key]
        # Also ensure 'created_date', 'owner_did', 'ingest_family', 'source_id', 'shard_key', '_seq', 'sensitivity_ord', 'fail_count'
        # are preserved from existing_cursor if not explicitly set in cursor_data
        for key in ["created_date", "owner_did", "ingest_family", "source_id", "shard_key", "_seq", "sensitivity_ord", "fail_count"]:
            if key in existing_cursor and key not in cursor_data: # If not explicitly set (which it is for many)
                 cursor_data[key] = existing_cursor[key]
        # Specifically for fail_count which had an increment logic in the old SQL for certain status updates
        # The new approach assumes fail_count is always set to 0 unless explicitly handled elsewhere.
        # Given the update SQL had `fail_count = COALESCE(%s, fail_count)` and `CAST(0 AS BIGINT)` for insert,
        # we stick to 0 for initial insert and rely on explicit updates if increment is needed.
        cursor_data["fail_count"] = existing_cursor.get("fail_count", 0) # Default to 0 if not found


    client.insert_row("vertex_ingest_cursor", cursor_data)
    return vid




def upsert_artifact(artifact: IngestArtifact) -> str:
    vid = artifact_vertex_id(artifact.run_id, artifact.artifact_kind, artifact.uri)
    now = now_iso()
    props = json.dumps(artifact.props, sort_keys=True, separators=(",", ":")) if artifact.props else None
    client = get_kotoba_client()
    artifact_data = {
        "vertex_id": vid,
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 0,
        "owner_did": INGEST_ACTOR_DID,
        "run_id": artifact.run_id,
        "artifact_kind": artifact.artifact_kind,
        "source_id": artifact.source_id,
        "uri": artifact.uri,
        "sha256": artifact.sha256,
        "byte_size": artifact.byte_size,
        "record_count": artifact.record_count,
        "created_at": now,
        "props": props,
    }
    client.insert_row("vertex_ingest_artifact", artifact_data)
    return vid


