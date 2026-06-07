"""Tests for time/rkey pure helpers in primitives/maps_sentinel.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_sentinel as MS


# ─── _now_iso ────────────────────────────────────────────────────────────────

def test_now_iso_ends_with_z() -> None:
    assert MS._now_iso().endswith("Z")


def test_now_iso_has_t_separator() -> None:
    assert "T" in MS._now_iso()


def test_now_iso_no_microseconds() -> None:
    assert "." not in MS._now_iso()


def test_now_iso_matches_pattern() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", MS._now_iso())


# ─── _now_ms ─────────────────────────────────────────────────────────────────

def test_now_ms_is_int() -> None:
    assert isinstance(MS._now_ms(), int)


def test_now_ms_is_positive() -> None:
    assert MS._now_ms() > 0


def test_now_ms_is_recent() -> None:
    import time
    ms = MS._now_ms()
    now_ms = int(time.time() * 1000)
    assert abs(ms - now_ms) < 5000


# ─── _new_rkey ───────────────────────────────────────────────────────────────

def test_new_rkey_starts_with_prefix() -> None:
    rkey = MS._new_rkey("sentinel")
    assert rkey.startswith("sentinel-")


def test_new_rkey_has_timestamp_and_uuid() -> None:
    rkey = MS._new_rkey("test")
    parts = rkey.split("-")
    assert len(parts) >= 3


def test_new_rkey_two_calls_differ() -> None:
    r1 = MS._new_rkey("x")
    r2 = MS._new_rkey("x")
    assert r1 != r2


def test_new_rkey_returns_string() -> None:
    assert isinstance(MS._new_rkey("pfx"), str)


# ─── _build_datetime_range ───────────────────────────────────────────────────

def test_build_datetime_range_has_slash() -> None:
    result = MS._build_datetime_range(7)
    assert "/" in result


def test_build_datetime_range_parts_are_iso() -> None:
    result = MS._build_datetime_range(7)
    start, end = result.split("/")
    assert start.endswith("Z")
    assert end.endswith("Z")


def test_build_datetime_range_clamps_min_at_1() -> None:
    result = MS._build_datetime_range(0)
    start, end = result.split("/")
    from datetime import datetime, timezone
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    diff = e - s
    assert diff.days >= 1


def test_build_datetime_range_clamps_max_at_365() -> None:
    result = MS._build_datetime_range(1000)
    start, end = result.split("/")
    from datetime import datetime, timezone
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    diff = e - s
    assert diff.days <= 366  # allow 365+1 for any tz edge case


def test_build_datetime_range_respects_days() -> None:
    result = MS._build_datetime_range(30)
    start, end = result.split("/")
    from datetime import datetime, timezone
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    diff = e - s
    assert 29 <= diff.days <= 30
