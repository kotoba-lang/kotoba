"""Tests for vector_embedding primitives."""

from __future__ import annotations

import asyncio
import math
import os
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import vector_embedding as VE  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_embed_mode(monkeypatch):
    monkeypatch.setenv("VECTOR_EMBEDDING_FAKE", "1")


@pytest.fixture()
def _stub_db():
    with patch("kotodama.primitives.vector_embedding.sync_cursor") as m:
        cur = MagicMock()
        cur.description = None
        cur.fetchall.return_value = []
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── normalize_768 (pure) ────────────────────────────────────────────────

def test_normalize_768_output_has_correct_dim():
    vec = VE.normalize_768([1.0] * 768)
    assert len(vec) == 768


def test_normalize_768_output_is_unit_length():
    vec = VE.normalize_768([1.0] * 768)
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6


def test_normalize_768_pads_short_vector():
    vec = VE.normalize_768([1.0, 2.0, 3.0])
    assert len(vec) == 768


def test_normalize_768_truncates_long_vector():
    vec = VE.normalize_768([1.0] * 900)
    assert len(vec) == 768


def test_normalize_768_raises_on_zero_vector():
    with pytest.raises(ValueError, match="norm is zero"):
        VE.normalize_768([0.0] * 768)


# ─── vector_literal (pure) ───────────────────────────────────────────────

def test_vector_literal_bracket_format():
    lit = VE.vector_literal([1.0] * 768)
    assert lit.startswith("[")
    assert lit.endswith("]")
    values = lit[1:-1].split(",")
    assert len(values) == 768


# ─── _fake_embed (pure) ──────────────────────────────────────────────────

def test_fake_embed_returns_unit_vectors():
    vecs = VE._fake_embed(["hello", "world"])
    assert len(vecs) == 2
    for vec in vecs:
        assert len(vec) == 768
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6


def test_fake_embed_is_deterministic():
    v1 = VE._fake_embed(["test text"])
    v2 = VE._fake_embed(["test text"])
    assert v1 == v2


def test_fake_embed_different_for_different_texts():
    v1 = VE._fake_embed(["text A"])
    v2 = VE._fake_embed(["text B"])
    assert v1 != v2


# ─── embed_texts_768 (fake mode via env) ─────────────────────────────────

def test_embed_texts_768_uses_fake_in_fake_mode():
    vecs = VE.embed_texts_768(["actor profile text"])
    assert len(vecs) == 1
    assert len(vecs[0]) == VE.DIM


# ─── _clean_text (pure) ──────────────────────────────────────────────────

def test_clean_text_collapses_whitespace():
    result = VE._clean_text("  hello   world  ")
    assert result == "hello world"


def test_clean_text_truncates_to_limit():
    result = VE._clean_text("a" * 5000, limit=100)
    assert len(result) <= 100


def test_clean_text_handles_none():
    result = VE._clean_text(None)
    assert result == ""


# ─── _actor_text / _post_text (pure) ─────────────────────────────────────

def test_actor_text_combines_fields():
    row = {
        "display_name": "Shinshi Actor",
        "handle": "shinshi.etzhayyim.com",
        "description": "AI music actor",
        "root_did": "did:erc725:etzhayyim:260425:abc",
    }
    text = VE._actor_text(row)
    assert "Shinshi Actor" in text
    assert "shinshi.etzhayyim.com" in text
    assert "AI music actor" in text


def test_post_text_combines_fields():
    row = {
        "text": "New album released",
        "handle": "shinshi.etzhayyim.com",
        "source_uri": "at://did:web:shinshi.etzhayyim.com/app.bsky.feed.post/rk1",
    }
    text = VE._post_text(row)
    assert "New album released" in text
    assert "shinshi.etzhayyim.com" in text


# ─── _summarize_hume_prediction / _collect_emotion_scores (pure) ─────────

def test_collect_emotion_scores_extracts_from_nested():
    out: dict = {}
    VE._collect_emotion_scores(
        {"emotions": [{"name": "Joy", "score": 0.8}, {"name": "Calm", "score": 0.4}]}, out
    )
    assert "Joy" in out
    assert out["Joy"] == [0.8]


def test_summarize_hume_prediction_finds_top():
    raw = {"emotions": [{"name": "Joy", "score": 0.9}, {"name": "Sad", "score": 0.1}]}
    result = VE._summarize_hume_prediction(raw)
    assert result["topEmotion"] == "Joy"
    assert abs(result["topScore"] - 0.9) < 1e-6


def test_summarize_hume_prediction_empty_returns_none():
    result = VE._summarize_hume_prediction({})
    assert result["topEmotion"] is None
    assert result["topScore"] is None


# ─── enrich_hume_emotions (no DB path) ───────────────────────────────────

def test_enrich_hume_emotions_empty_candidates():
    result = VE.enrich_hume_emotions([])
    assert result["planned"] == 0
    assert result["written"] == 0


def test_enrich_hume_emotions_without_hume_env_skips():
    candidate = VE.EmbeddingCandidate(
        source_uri="actor:did:erc725:etzhayyim:260425:abc",
        source_kind="actor_profile",
        source_vertex_id="did:erc725:etzhayyim:260425:abc",
        modality="text",
        tenant_id="public",
        shard_id=None,
        text="test actor",
        text_preview="test actor",
    )
    # Hume not enabled → returns enabled=False immediately
    result = VE.enrich_hume_emotions([candidate], dry_run=True)
    assert result["planned"] == 1
    assert result["written"] == 0
    assert result["enabled"] is False


def test_enrich_hume_emotions_dry_run_with_fake_hume(monkeypatch):
    monkeypatch.setenv("VECTOR_EMBEDDING_HUME_FAKE", "1")
    candidate = VE.EmbeddingCandidate(
        source_uri="actor:did:erc725:etzhayyim:260425:abc",
        source_kind="actor_profile",
        source_vertex_id="did:erc725:etzhayyim:260425:abc",
        modality="text",
        tenant_id="public",
        shard_id=None,
        text="test actor",
        text_preview="test actor",
    )
    result = VE.enrich_hume_emotions([candidate], dry_run=True)
    assert result["planned"] == 1
    assert result["written"] == 0
    assert result.get("dryRun") is True


# ─── backfill_batch (invalid surface, no DB) ─────────────────────────────

def test_backfill_batch_invalid_surface_returns_error():
    result = VE.backfill_batch("widgets")
    assert "error" in result
    assert result["planned"] == 0


# ─── backfill_batch with empty DB mock ───────────────────────────────────

def test_backfill_batch_actors_dry_run(_stub_db):
    result = VE.backfill_batch("actors", dry_run=True)
    assert result["surface"] == "actors"
    assert result["dryRun"] is True


def test_backfill_batch_posts_dry_run(_stub_db):
    result = VE.backfill_batch("posts", dry_run=True)
    assert result["surface"] == "posts"
    assert result["dryRun"] is True


# ─── task_vector_embedding_backfill_batch ────────────────────────────────

def test_task_invalid_surface_async(_stub_db):
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(
        surface="widgets", dryRun=True,
    ))
    assert "error" in result


def test_task_actors_dry_run_async(_stub_db):
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(
        surface="actors", limit=10, dryRun=True,
    ))
    assert result["surface"] == "actors"
    assert result["dryRun"] is True


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_one_task():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    VE.register(FakeWorker(), timeout_ms=300_000)
    assert registered == ["vectorEmbedding.backfillBatch"]
