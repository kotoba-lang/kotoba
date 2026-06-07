"""Additional tests for ingest/core.py time + run-id helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.core import (
    now_iso,
    today,
    stable_run_id,
    run_vertex_id,
    cursor_vertex_id,
    artifact_vertex_id,
)


# ─── now_iso ─────────────────────────────────────────────────────────────────

def test_now_iso_ends_with_z() -> None:
    assert now_iso().endswith("Z")


def test_now_iso_contains_t_separator() -> None:
    assert "T" in now_iso()


def test_now_iso_length() -> None:
    assert len(now_iso()) == 20  # YYYY-MM-DDTHH:MM:SSZ


def test_now_iso_no_microseconds() -> None:
    assert "." not in now_iso()


def test_now_iso_returns_string() -> None:
    assert isinstance(now_iso(), str)


def test_now_iso_matches_pattern() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", now_iso())


# ─── today ───────────────────────────────────────────────────────────────────

def test_today_returns_string() -> None:
    assert isinstance(today(), str)


def test_today_matches_date_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", today())


def test_today_no_time_component() -> None:
    assert "T" not in today()


# ─── stable_run_id ───────────────────────────────────────────────────────────

def test_stable_run_id_returns_string() -> None:
    result = stable_run_id("houbun", "gov-jpn", "delta")
    assert isinstance(result, str)


def test_stable_run_id_contains_family_slug() -> None:
    result = stable_run_id("houbun", "gov-jpn", "delta")
    assert "houbun" in result


def test_stable_run_id_contains_source_slug() -> None:
    result = stable_run_id("houbun", "gov-jpn", "delta")
    assert "gov" in result


def test_stable_run_id_contains_mode_slug() -> None:
    result = stable_run_id("houbun", "gov-jpn", "delta")
    assert "delta" in result


def test_stable_run_id_different_families_differ() -> None:
    r1 = stable_run_id("houbun", "gov-jpn", "delta")
    r2 = stable_run_id("maps", "gov-jpn", "delta")
    assert r1 != r2


def test_stable_run_id_different_sources_differ() -> None:
    r1 = stable_run_id("houbun", "gov-jpn", "delta")
    r2 = stable_run_id("houbun", "sec-adv", "delta")
    assert r1 != r2


def test_stable_run_id_has_hex_suffix() -> None:
    result = stable_run_id("test", "src", "full")
    parts = result.split("-")
    # last part is hex digest
    assert all(c in "0123456789abcdef" for c in parts[-1])


def test_stable_run_id_includes_input_json() -> None:
    r1 = stable_run_id("houbun", "gov-jpn", "delta", input_json="")
    r2 = stable_run_id("houbun", "gov-jpn", "delta", input_json='{"key":"val"}')
    assert r1 != r2


# ─── run_vertex_id ───────────────────────────────────────────────────────────

def test_run_vertex_id_format() -> None:
    vid = run_vertex_id("my-run-id")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.ingest.run" in vid


def test_run_vertex_id_contains_slug() -> None:
    vid = run_vertex_id("houbun-gov-jpn-delta-abc123")
    assert "houbun" in vid


# ─── cursor_vertex_id ────────────────────────────────────────────────────────

def test_cursor_vertex_id_format() -> None:
    vid = cursor_vertex_id("houbun", "gov-jpn", "default")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.ingest.cursor" in vid


def test_cursor_vertex_id_includes_family() -> None:
    vid = cursor_vertex_id("houbun", "gov-jpn", "shard0")
    assert "houbun" in vid


def test_cursor_vertex_id_two_families_differ() -> None:
    v1 = cursor_vertex_id("houbun", "gov-jpn", "default")
    v2 = cursor_vertex_id("maps", "gov-jpn", "default")
    assert v1 != v2


# ─── artifact_vertex_id ──────────────────────────────────────────────────────

def test_artifact_vertex_id_format() -> None:
    vid = artifact_vertex_id("run-abc", "json", "s3://bucket/key")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.ingest.artifact" in vid


def test_artifact_vertex_id_deterministic() -> None:
    v1 = artifact_vertex_id("run-abc", "json", "s3://bucket/key")
    v2 = artifact_vertex_id("run-abc", "json", "s3://bucket/key")
    assert v1 == v2


def test_artifact_vertex_id_varies_with_uri() -> None:
    v1 = artifact_vertex_id("run-abc", "json", "s3://bucket/key1")
    v2 = artifact_vertex_id("run-abc", "json", "s3://bucket/key2")
    assert v1 != v2
