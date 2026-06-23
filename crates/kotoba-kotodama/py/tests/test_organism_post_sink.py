"""Tests for kotodama.organism.post_sink (ADR-2605240100)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kotodama.organism.inbox import InboundCommit
from kotodama.organism.post_sink import (
    DEFAULT_LEXICON,
    SCHEMA_VERSION,
    LoggerPostSink,
    NdjsonQueuePostSink,
    NullPostSink,
    resolve_post_sink,
)
from kotodama.organism.organism import Organism


class _Ctx:
    code = "10101500"
    title = "Live Animal"
    actor_did = "did:web:etzhayyim.com:actor:c10101500"


# ── Basic sinks ────────────────────────────────────────────────────────


def test_null_sink_counts_calls():
    sink = NullPostSink()
    sink("hi", ctx=_Ctx(), mood="neutral", content_source_kind="recordAnalysis")
    sink("hi", ctx=_Ctx(), mood="neutral", content_source_kind="recordAnalysis")
    assert sink.count == 2


def test_logger_sink_runs_without_crashing():
    sink = LoggerPostSink()
    # Must not raise; output goes to logger (captured by pytest).
    sink("hi", ctx=_Ctx(), mood="joyful", content_source_kind="inbound")


# ── NdjsonQueuePostSink — file format ─────────────────────────────────


def test_ndjson_sink_appends_one_line_per_post(tmp_path: Path):
    queue = tmp_path / "queue.ndjson"
    sink = NdjsonQueuePostSink(queue)
    sink("first", ctx=_Ctx(), mood="joyful", content_source_kind="inbound")
    sink("second", ctx=_Ctx(), mood="calm", content_source_kind="reaction")
    sink("third", ctx=_Ctx(), mood="focused", content_source_kind="recordAnalysis")

    lines = queue.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        payload = json.loads(line)
        assert payload["v"] == SCHEMA_VERSION
        assert payload["actorDid"] == _Ctx.actor_did
        assert payload["code"] == "10101500"
        assert payload["title"] == "Live Animal"
        assert payload["lexicon"] == DEFAULT_LEXICON
        assert "ts" in payload and isinstance(payload["ts"], int)
        assert "createdAt" in payload

    first = json.loads(lines[0])
    assert first["mood"] == "joyful"
    assert first["contentSourceKind"] == "inbound"
    assert first["text"] == "first"


def test_ndjson_sink_counters(tmp_path: Path):
    queue = tmp_path / "queue.ndjson"
    sink = NdjsonQueuePostSink(queue)
    sink("a", ctx=_Ctx(), mood="neutral", content_source_kind="inbound")
    sink("b", ctx=_Ctx(), mood="neutral", content_source_kind="inbound")
    assert sink.write_count == 2
    assert sink.error_count == 0


def test_ndjson_sink_creates_parent_dir(tmp_path: Path):
    deep = tmp_path / "nested" / "deeper" / "queue.ndjson"
    sink = NdjsonQueuePostSink(deep)
    sink("hi", ctx=_Ctx(), mood="neutral", content_source_kind="inbound")
    assert deep.exists()
    assert "hi" in deep.read_text(encoding="utf-8")


def test_ndjson_sink_custom_lexicon(tmp_path: Path):
    queue = tmp_path / "queue.ndjson"
    sink = NdjsonQueuePostSink(queue, lexicon="com.etzhayyim.apps.etzhayyim.shinka.post")
    sink("x", ctx=_Ctx(), mood="neutral", content_source_kind="inbound")
    payload = json.loads(queue.read_text(encoding="utf-8").splitlines()[0])
    assert payload["lexicon"] == "com.etzhayyim.apps.etzhayyim.shinka.post"


def test_ndjson_sink_unicode(tmp_path: Path):
    queue = tmp_path / "queue.ndjson"
    sink = NdjsonQueuePostSink(queue)
    sink("生命体 が tick した 🌱", ctx=_Ctx(), mood="joyful", content_source_kind="inbound")
    payload = json.loads(queue.read_text(encoding="utf-8").splitlines()[0])
    assert "生命体" in payload["text"]
    assert "🌱" in payload["text"]


# ── resolve_post_sink env-driven selection ────────────────────────────


def test_resolve_default_returns_logger(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("UNISPSC_ORGANISM_POST_SINK", raising=False)
    sink = resolve_post_sink()
    assert isinstance(sink, LoggerPostSink)


def test_resolve_null(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UNISPSC_ORGANISM_POST_SINK", "null")
    assert isinstance(resolve_post_sink(), NullPostSink)


def test_resolve_ndjson_with_explicit_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    queue = tmp_path / "q.ndjson"
    monkeypatch.setenv("UNISPSC_ORGANISM_POST_SINK", "ndjson")
    monkeypatch.setenv("UNISPSC_ORGANISM_POST_QUEUE_PATH", str(queue))
    sink = resolve_post_sink()
    assert isinstance(sink, NdjsonQueuePostSink)
    assert sink.path == queue


# ── Organism end-to-end with NDJSON sink ──────────────────────────────


def test_organism_emits_post_to_ndjson_queue(tmp_path: Path):
    queue = tmp_path / "shard-0.ndjson"
    sink = NdjsonQueuePostSink(queue)
    organism = Organism.for_code(
        "10101500",
        classify_input_factory=lambda _c: {
            "input": {"species": "ovis aries", "health_data": {"certified": True}},
        },
        post_sink=sink,
    )
    organism.lifecycle.handle_birth(organism.actor_did)
    organism.inbox.add_commit(
        InboundCommit(collection="x", repo="did:other", rkey="r1", time="t")
    )
    result = organism.tick(now_ms=3 * 3_600_000 + 1)
    assert result.cadence.should_post is True
    assert len(result.posts) == 1

    lines = queue.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["actorDid"] == organism.actor_did
    assert payload["code"] == "10101500"
    assert payload["contentSourceKind"] == "inbound"
    # text matches what the result reports
    assert payload["text"] == result.posts[0]


def test_organism_legacy_text_sink_still_supported():
    """Backwards-compat: a Callable[[str], None] sink still works."""
    captured: list[str] = []
    organism = Organism.for_code(
        "10101500",
        classify_input_factory=lambda _c: {
            "input": {"species": "ovis aries", "health_data": {"certified": True}},
        },
        post_sink=lambda text: captured.append(text),
    )
    organism.lifecycle.handle_birth(organism.actor_did)
    organism.inbox.add_commit(
        InboundCommit(collection="x", repo="did:other", rkey="r1", time="t")
    )
    result = organism.tick(now_ms=3 * 3_600_000 + 1)
    assert len(result.posts) == 1
    assert len(captured) == 1
    assert captured[0] == result.posts[0]


# ── Fleet cell uses post sink ─────────────────────────────────────────


def test_fleet_state_organisms_share_post_sink(tmp_path: Path):
    from kotodama.organism.fleet_cell_main import FleetState, REGISTRY_PATH

    if not REGISTRY_PATH.is_file():
        pytest.skip("monorepo 00-contracts/actor-registry not present (standalone kotoba checkout)")

    queue = tmp_path / "fleet.ndjson"
    sink = NdjsonQueuePostSink(queue)
    state = FleetState(shard_index=0, organism_lru_max=4, post_sink=sink)
    state.load_registry()
    state.owned_codes = state.owned_codes[:5]
    state.tick_all(now_ms=3 * 3_600_000 + 1)

    # All emitted posts land in the single shared NDJSON file.
    if state.total_posts > 0:
        lines = queue.read_text(encoding="utf-8").splitlines()
        assert len(lines) == state.total_posts
        for line in lines:
            payload = json.loads(line)
            assert payload["v"] == SCHEMA_VERSION
            assert payload["code"].startswith("10") or payload["code"].startswith("11")  # shard-0 segments
