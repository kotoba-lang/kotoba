"""Pure helper tests for kotoba-kotodama_organizer primitive.

Covers:
- _utc_now_iso() — ISO 8601 UTC timestamp
- call_organizer() — pure parser of _http_post_json output
- register() — task registration with a fake worker
- module-level constants
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import kotoba-kotodama_organizer as MO


# ─── _utc_now_iso ─────────────────────────────────────────────────────────────

def test_utc_now_iso_returns_string() -> None:
    assert isinstance(MO._utc_now_iso(), str)


def test_utc_now_iso_ends_with_z() -> None:
    assert MO._utc_now_iso().endswith("Z")


def test_utc_now_iso_contains_t() -> None:
    assert "T" in MO._utc_now_iso()


def test_utc_now_iso_starts_with_202() -> None:
    assert MO._utc_now_iso()[:3] == "202"


def test_utc_now_iso_min_length() -> None:
    assert len(MO._utc_now_iso()) >= 20


# ─── call_organizer (pure, mocked _http_post_json) ────────────────────────────

def test_call_organizer_success_response():
    fake = {
        "httpStatus": 200,
        "body": {
            "ts": "2026-01-01T00:00:00Z",
            "runsTotal24h": 10,
            "summary": {"hot": 1, "normal": 5, "stale": 2, "silent": 1, "archived": 1},
            "fleet": {"saturation": 0.75},
        },
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["ok"] is True
    assert result["runsTotal24h"] == 10
    assert result["fleetSaturation"] == 0.75
    assert result["summary"]["hot"] == 1


def test_call_organizer_http_error_not_ok():
    fake = {
        "httpStatus": 500,
        "body": {"error": "internal server error"},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["ok"] is False
    assert result["httpStatus"] == 500


def test_call_organizer_transport_error_status_zero():
    fake = {
        "httpStatus": 0,
        "body": {"error": "transport: connection refused"},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["ok"] is False
    assert result["httpStatus"] == 0
    assert result["runsTotal24h"] == 0


def test_call_organizer_404_not_ok():
    fake = {
        "httpStatus": 404,
        "body": {"error": "not found"},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["ok"] is False


def test_call_organizer_200_with_error_field_not_ok():
    fake = {
        "httpStatus": 200,
        "body": {"error": "some internal failure", "runsTotal24h": 0},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["ok"] is False


def test_call_organizer_missing_summary_defaults_to_zeros():
    fake = {
        "httpStatus": 200,
        "body": {"ts": "2026-01-01T00:00:00Z", "runsTotal24h": 5},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["summary"]["hot"] == 0
    assert result["summary"]["stale"] == 0


def test_call_organizer_missing_fleet_defaults_zero_saturation():
    fake = {
        "httpStatus": 200,
        "body": {"ts": "2026-01-01T00:00:00Z", "runsTotal24h": 3},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["fleetSaturation"] == 0.0


def test_call_organizer_returns_error_string_when_failed():
    fake = {"httpStatus": 503, "body": {"error": "overloaded"}}
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["error"] != ""


def test_call_organizer_plan_ts_from_body():
    ts = "2026-05-01T12:34:56Z"
    fake = {
        "httpStatus": 200,
        "body": {"ts": ts, "runsTotal24h": 1},
    }
    with patch.object(MO, "_http_post_json", return_value=fake):
        result = MO.call_organizer("https://example.com/organizer")
    assert result["planTs"] == ts


# ─── register ─────────────────────────────────────────────────────────────────

def test_register_registers_organizer_run_task():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    MO.register(FakeWorker(), timeout_ms=30_000)
    assert "kotoba-kotodama.organizer.run" in registered


def test_register_single_value_false():
    recorded = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            recorded.append(single_value)
            def deco(fn): return fn
            return deco

    MO.register(FakeWorker(), timeout_ms=30_000)
    assert recorded == [False]


def test_register_passes_timeout():
    recorded = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            recorded.append(timeout_ms)
            def deco(fn): return fn
            return deco

    MO.register(FakeWorker(), timeout_ms=120_000)
    assert recorded == [120_000]


# ─── module-level constants ───────────────────────────────────────────────────

def test_kotoba-kotodama_did_is_string() -> None:
    assert isinstance(MO.KOTODAMA_DID, str)


def test_kotoba-kotodama_did_starts_with_did() -> None:
    assert MO.KOTODAMA_DID.startswith("did:")


def test_organizer_run_collection_is_string() -> None:
    assert isinstance(MO.ORGANIZER_RUN_COLLECTION, str)


def test_organizer_run_collection_contains_organizer() -> None:
    assert "organizer" in MO.ORGANIZER_RUN_COLLECTION.lower()
