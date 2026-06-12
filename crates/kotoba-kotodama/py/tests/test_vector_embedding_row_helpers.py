"""Tests for _source_row and _embedding_row pure helpers in vector_embedding.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives.vector_embedding import (
    EmbeddingCandidate,
    _source_row,
    _embedding_row,
)


def _make_candidate(**kwargs) -> EmbeddingCandidate:
    defaults = {
        "source_uri": "at://did:web:test.etzhayyim.com/collection/rkey001",
        "source_kind": "actor_profile",
        "source_vertex_id": "at://did:web:test.etzhayyim.com/collection/rkey001",
        "modality": "text",
        "tenant_id": "test-tenant",
        "shard_id": 0,
        "text": "Sample actor bio for embedding test",
        "text_preview": "Sample actor bio",
    }
    defaults.update(kwargs)
    return EmbeddingCandidate(**defaults)


# ─── _source_row ─────────────────────────────────────────────────────────────

def test_source_row_has_vertex_id() -> None:
    c = _make_candidate()
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert "vertex_id" in row
    assert "embedding-source:" in row["vertex_id"]


def test_source_row_source_uri_propagated() -> None:
    c = _make_candidate(source_uri="at://test/col/rkey")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["source_uri"] == "at://test/col/rkey"


def test_source_row_source_kind_propagated() -> None:
    c = _make_candidate(source_kind="actor_profile")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["source_kind"] == "actor_profile"


def test_source_row_actor_profile_uses_view_actor_universal() -> None:
    c = _make_candidate(source_kind="actor_profile")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["source_table"] == "view_actor_universal"


def test_source_row_post_kind_uses_bluesky_post() -> None:
    c = _make_candidate(source_kind="post")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["source_table"] == "vertex_bluesky_post"


def test_source_row_content_hash_is_sha256() -> None:
    import hashlib
    c = _make_candidate(text="hello world")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    expected = hashlib.sha256("hello world".encode("utf-8")).hexdigest()
    assert row["content_hash"] == expected


def test_source_row_content_hash_varies_with_text() -> None:
    c1 = _make_candidate(text="text one")
    c2 = _make_candidate(text="text two")
    now = "2026-04-29T00:00:00Z"
    assert _source_row(c1, now=now)["content_hash"] != _source_row(c2, now=now)["content_hash"]


def test_source_row_visibility_is_public() -> None:
    c = _make_candidate()
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["visibility"] == "public"


def test_source_row_media_type_is_text_plain() -> None:
    c = _make_candidate()
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["media_type"] == "text/plain"


def test_source_row_now_propagated_to_indexed_at() -> None:
    now = "2026-04-29T12:00:00Z"
    c = _make_candidate()
    row = _source_row(c, now=now)
    assert row["indexed_at"] == now


def test_source_row_tenant_id_propagated() -> None:
    c = _make_candidate(tenant_id="tenant-abc")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["tenant_id"] == "tenant-abc"


def test_source_row_shard_id_propagated() -> None:
    c = _make_candidate(shard_id=3)
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["shard_id"] == 3


def test_source_row_lang_none_when_not_set() -> None:
    c = _make_candidate()
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["lang"] is None


def test_source_row_lang_propagated() -> None:
    c = _make_candidate(lang="ja")
    row = _source_row(c, now="2026-04-29T00:00:00Z")
    assert row["lang"] == "ja"


# ─── _embedding_row ──────────────────────────────────────────────────────────

def test_embedding_row_has_embedding_id() -> None:
    c = _make_candidate()
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert "embedding_id" in row
    assert row["embedding_id"].startswith("emb768:")


def test_embedding_row_source_uri_propagated() -> None:
    c = _make_candidate(source_uri="at://test/col/rkey")
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert row["source_uri"] == "at://test/col/rkey"


def test_embedding_row_emb_is_string() -> None:
    c = _make_candidate()
    vector = [0.5] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert isinstance(row["emb"], str)
    assert "[" in row["emb"] and "]" in row["emb"]


def test_embedding_row_embedded_at_is_now() -> None:
    now = "2026-04-29T10:00:00Z"
    c = _make_candidate()
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now=now)
    assert row["embedded_at"] == now


def test_embedding_row_modality_propagated() -> None:
    c = _make_candidate(modality="text")
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert row["modality"] == "text"


def test_embedding_row_tenant_id_propagated() -> None:
    c = _make_candidate(tenant_id="t-xyz")
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert row["tenant_id"] == "t-xyz"


def test_embedding_row_created_at_uses_candidate_when_set() -> None:
    c = _make_candidate(created_at="2026-01-01T00:00:00Z")
    vector = [0.1] * 768
    row = _embedding_row(c, vector, now="2026-04-29T00:00:00Z")
    assert row["created_at"] == "2026-01-01T00:00:00Z"


def test_embedding_row_created_at_falls_back_to_now() -> None:
    c = _make_candidate()  # created_at=None
    vector = [0.1] * 768
    now = "2026-04-29T00:00:00Z"
    row = _embedding_row(c, vector, now=now)
    assert row["created_at"] == now
