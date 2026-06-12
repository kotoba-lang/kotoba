"""IPFS CIDv1 (raw / sha2-256 / base32-lower) helper.

Matches the etzhayyim convention (ADR-0029): CIDv1, multicodec=raw (0x55),
multihash=sha2-256 (0x12), multibase=base32 lower (`b` prefix).

Used by the screenshot persistence path so the same file deduplicates
across observations (single `vertex_blob_ipfs` row, many `vertex_screenshot`
rows pointing at it).
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
from base64 import b32encode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _b32_lower_no_pad(data: bytes) -> str:
    """RFC 4648 base32 lower, no padding (multibase prefix `b`)."""
    return b32encode(data).decode("ascii").rstrip("=").lower()


def compute_cidv1_raw_sha256(data: bytes) -> tuple[str, str]:
    """Return (cid, sha256_hex). CID = `b` + base32(0x01 0x55 0x12 0x20 <sha256>)."""
    digest = hashlib.sha256(data).digest()
    cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + digest
    return "b" + _b32_lower_no_pad(cid_bytes), digest.hex()


@dataclass
class BlobMeta:
    cid: str
    sha256_hex: str
    size_bytes: int
    mime_type: str
    is_placeholder: bool = False
    storage_backend: str = ""
    storage_uri: str = ""
    captured_at: str = ""


def blob_from_path(path: str) -> BlobMeta:
    """Read file and compute the CID. Mime sniffed from extension."""
    with open(path, "rb") as f:
        data = f.read()
    cid, sha = compute_cidv1_raw_sha256(data)
    mime, _ = mimetypes.guess_type(path)
    return BlobMeta(
        cid=cid,
        sha256_hex=sha,
        size_bytes=len(data),
        mime_type=mime or "application/octet-stream",
        is_placeholder=False,
        storage_backend="local-file",
        storage_uri=f"file://{os.path.abspath(path)}",
    )


def blob_from_bytes(data: bytes, *, mime_type: str = "application/octet-stream") -> BlobMeta:
    cid, sha = compute_cidv1_raw_sha256(data)
    return BlobMeta(
        cid=cid,
        sha256_hex=sha,
        size_bytes=len(data),
        mime_type=mime_type,
        is_placeholder=False,
    )


def placeholder_blob_for(description: str, *, mime_type: str = "image/png") -> BlobMeta:
    """Deterministic CID derived from a description string.

    Use when the actual binary isn't available (e.g. a screenshot pasted
    into a chat). The CID is stable for the same description, so a later
    `register_blob_bytes()` can detect collisions and upgrade the row.
    """
    payload = f"placeholder:{description}".encode("utf-8")
    cid, sha = compute_cidv1_raw_sha256(payload)
    return BlobMeta(
        cid=cid,
        sha256_hex=sha,
        size_bytes=len(payload),
        mime_type=mime_type,
        is_placeholder=True,
        storage_backend="placeholder",
        storage_uri="",
    )


# ── persistence ────────────────────────────────────────────────────────


def upsert_blob(meta: BlobMeta, *, owner_did: str | None = None) -> str:
    """Idempotent INSERT into vertex_blob_ipfs. Returns the vertex_id."""
    from kotodama import db_sync

    vid = f"ipfs:{meta.cid}"
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    today = datetime.utcnow().date()
    db_sync.execute("DELETE FROM vertex_blob_ipfs WHERE vertex_id = %s", (vid,))
    db_sync.execute(
        """
        INSERT INTO vertex_blob_ipfs (
          vertex_id, created_date, sensitivity_ord, owner_did,
          cid, cid_version, multicodec, multihash_code, multibase,
          size_bytes, mime_type, sha256_hex,
          storage_backend, storage_uri,
          first_seen_at, last_seen_at, is_placeholder, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            vid, today, 100, owner_did,
            meta.cid, 1, "raw", "sha2-256", "base32-lower",
            meta.size_bytes, meta.mime_type, meta.sha256_hex,
            meta.storage_backend, meta.storage_uri,
            now, now, meta.is_placeholder, now,
        ),
    )
    return vid
