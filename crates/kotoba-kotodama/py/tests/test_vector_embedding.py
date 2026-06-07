from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import vector_embedding as V  # noqa: E402


class _Cursor:
    def __init__(self, rows=None, description=None):
        self.rows = rows or []
        self.description = description or []
        self.sqls = []
        self.params = []
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        self.params.append(params)

    def fetchall(self):
        return self.rows


class _SyncCursorFactory:
    def __init__(self, cursors):
        self.cursors = cursors
        self.index = 0

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                cur = factory.cursors[min(factory.index, len(factory.cursors) - 1)]
                factory.index += 1
                return cur

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_normalize_768_truncates_and_normalizes():
    out = V.normalize_768([1.0] * 1024)

    assert len(out) == 768
    assert abs(sum(v * v for v in out) - 1.0) < 1e-6


def test_plan_actor_candidates(monkeypatch):
    cur = _Cursor(
        rows=[
            (
                "did:erc725:etzhayyim:260425:0xabc",
                "did:web:alice.example",
                "alice.example",
                "Alice",
                "Builder",
                "service",
            )
        ],
        description=[
            ("root_did",),
            ("facade_did",),
            ("handle",),
            ("display_name",),
            ("description",),
            ("performer_type",),
        ],
    )
    monkeypatch.setattr(V, "sync_cursor", _SyncCursorFactory([cur]))

    candidates = V.plan_actor_candidates(limit=5, shard_id=3)

    assert len(candidates) == 1
    assert candidates[0].source_uri == "actor:did:erc725:etzhayyim:260425:0xabc"
    assert candidates[0].repo == "did:web:alice.example"
    assert candidates[0].shard_id == 3
    assert "Alice" in candidates[0].text
    assert "view_actor_unified" in cur.sqls[0]
    assert "did:erc725:etzhayyim:260425:%%" in cur.sqls[0]


def test_backfill_batch_fake_embedding_writes(monkeypatch):
    select_cur = _Cursor(
        rows=[
            (
                "post-row-1",
                "at://did:plc:a/app.bsky.feed.post/r1",
                "cid1",
                "did:plc:a",
                "r1",
                "alice.example",
                "hello world",
                "alt text",
                "en",
                "2026-04-27T00:00:00Z",
                "2026-04-27T00:00:01Z",
            )
        ],
        description=[
            ("vertex_id",),
            ("source_uri",),
            ("source_cid",),
            ("repo",),
            ("rkey",),
            ("handle",),
            ("text",),
            ("embed_alt_text",),
            ("lang",),
            ("created_at",),
            ("indexed_at",),
        ],
    )
    write_cur = _Cursor()
    monkeypatch.setattr(V, "sync_cursor", _SyncCursorFactory([select_cur, write_cur]))
    monkeypatch.setenv("VECTOR_EMBEDDING_FAKE", "1")

    out = asyncio.run(V.task_vector_embedding_backfill_batch(surface="posts", limit=10))

    assert out["planned"] == 1
    assert out["written"] == 1
    assert out["modelId"] == "bge-m3"
    assert "vertex_vector_embedding_source" in write_cur.sqls[0]
    assert "%(shard_id)s::int" in write_cur.sqls[0]
    assert "%(width_px)s::int" in write_cur.sqls[0]
    assert "%(duration_ms)s::bigint" in write_cur.sqls[0]
    assert "vertex_vector_embedding_768" in write_cur.sqls[1]
    assert "%(shard_id)s::int" in write_cur.sqls[1]
    assert "%(emb)s::vector(768)" in write_cur.sqls[1]


def test_hume_fake_emotion_writes(monkeypatch):
    cur = _Cursor()
    candidates = [
        V.EmbeddingCandidate(
            source_uri="at://did:plc:a/app.bsky.feed.post/r1",
            source_kind="bluesky_post",
            source_vertex_id="post-row-1",
            modality="text",
            tenant_id="public",
            shard_id=None,
            text="I am excited and calm",
            text_preview="I am excited and calm",
        )
    ]
    monkeypatch.setattr(V, "sync_cursor", _SyncCursorFactory([cur]))
    monkeypatch.setenv("VECTOR_EMBEDDING_HUME_FAKE", "1")

    out = V.enrich_hume_emotions(candidates)

    assert out["written"] == 1
    assert "vertex_vector_emotion_signal" in cur.sqls[0]
    assert "%(shard_id)s::int" in cur.sqls[0]
    assert "%(top_score)s::double precision" in cur.sqls[0]
    assert cur.params[0]["model_id"] == "hume-emotional-language"
    assert cur.params[0]["top_emotion"] in ("Calmness", "Interest")


def test_emotion_only_plans_from_existing_sources(monkeypatch):
    select_cur = _Cursor(
        rows=[
            (
                "at://did:plc:a/app.bsky.feed.post/r1",
                "bluesky_post",
                "post-row-1",
                "public",
                None,
                "text",
                "a short post",
                "did:plc:a",
                "r1",
                "cid1",
                "en",
                "2026-04-27T00:00:00Z",
            )
        ],
        description=[
            ("source_uri",),
            ("source_kind",),
            ("source_vertex_id",),
            ("tenant_id",),
            ("shard_id",),
            ("modality",),
            ("text_preview",),
            ("repo",),
            ("rkey",),
            ("source_cid",),
            ("lang",),
            ("captured_at",),
        ],
    )
    write_cur = _Cursor()
    monkeypatch.setattr(V, "sync_cursor", _SyncCursorFactory([select_cur, write_cur]))
    monkeypatch.setenv("VECTOR_EMBEDDING_HUME_FAKE", "1")

    out = V.backfill_batch("posts", limit=1, emotion_only=True)

    assert out["surface"] == "emotion"
    assert out["planned"] == 1
    assert out["humeEmotion"]["written"] == 1
    assert "vertex_vector_embedding_source" in select_cur.sqls[0]
    assert "vertex_vector_emotion_signal" in write_cur.sqls[0]
