"""Pure-path tests for the four historical-enrichment ingest handlers.

Handlers under test (all in coverage_gap.py):
  - _ingest_business_person_lei  (domain: business_person_lei)
  - _ingest_org_hierarchy        (domain: org_hierarchy)
  - _ingest_follows_history      (domain: follows_history)
  - _ingest_natural_person       (domain: natural_person)

Strategy:
  - sync_cursor is replaced with a noop context manager (no DB required).
  - _fetch_url is replaced with a stub that returns minimal valid JSON.
  - _WD_CURSOR is reset before each natural_person test so cursor seeding
    does not bleed across tests.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import coverage_gap as CG  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────────────

def _noop_cursor_cm(rows: list | None = None) -> MagicMock:
    """Returns a MagicMock that acts as `with sync_cursor() as cur:`."""
    cur = MagicMock()
    cur.fetchall.return_value = rows if rows is not None else []
    cur.fetchone.return_value = None
    cur.rowcount = 0
    cm_instance = MagicMock()
    cm_instance.__enter__ = MagicMock(return_value=cur)
    cm_instance.__exit__ = MagicMock(return_value=False)
    factory = MagicMock(return_value=cm_instance)
    return factory


def _gleif_name_miss() -> bytes:
    """GLEIF search response: no results."""
    return json.dumps({"data": []}).encode()


def _gleif_name_hit(lei: str = "AAAAAAAAAAAAAAAAAAAA", name: str = "Test Corp") -> bytes:
    return json.dumps({
        "data": [{
            "id": lei,
            "attributes": {
                "lei": lei,
                "entity": {
                    "legalName": {"name": name},
                },
            },
        }]
    }).encode()


def _wbgetentities_no_humans() -> bytes:
    """wbgetentities response: 50 entities, none are Q5 (human)."""
    entities = {
        f"Q{1000000 + i}": {
            "id": f"Q{1000000 + i}",
            "labels": {"en": {"value": f"Item{i}"}},
            "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q6"}}}}]},
        }
        for i in range(50)
    }
    return json.dumps({"entities": entities}).encode()


def _wbgetentities_one_human(qnum: int = 1000001, name: str = "Alice") -> bytes:
    entities = {
        f"Q{qnum}": {
            "id": f"Q{qnum}",
            "labels": {"en": {"value": name}},
            "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]},
        },
        **{
            f"Q{qnum + i}": {
                "id": f"Q{qnum + i}",
                "labels": {},
                "claims": {},
            }
            for i in range(1, 50)
        },
    }
    return json.dumps({"entities": entities}).encode()


# ── business_person_lei ────────────────────────────────────────────────────────

class TestIngestBusinessPersonLei:
    def setup_method(self) -> None:
        self._orig_sc = CG.sync_cursor
        self._orig_fetch = CG._fetch_url

    def teardown_method(self) -> None:
        CG.sync_cursor = self._orig_sc  # type: ignore[attr-defined]
        CG._fetch_url = self._orig_fetch  # type: ignore[attr-defined]

    def test_returns_dict(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert isinstance(result, dict)

    def test_ok_true_when_no_rows(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("ok") is True

    def test_zero_written_when_no_rows(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("rowsWritten") == 0

    def test_has_error_key(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert "error" in result

    def test_gleif_miss_skips_row(self) -> None:
        rows = [("vid:001", "Nonexistent Corp XYZ")]
        CG.sync_cursor = _noop_cursor_cm(rows)  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _gleif_name_miss()  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("ok") is True
        assert result.get("rowsWritten") == 0
        assert result.get("skipped", 0) >= 1

    def test_gleif_hit_exact_match_updates(self) -> None:
        lei = "BBBBBBBBBBBBBBBBBBBBB"[:20]
        name = "Exact Match Corp"
        rows = [("vid:001", name)]
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = rows
        cur_mock.fetchone.return_value = None
        cur_mock.rowcount = 1
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cur_mock)
        cm.__exit__ = MagicMock(return_value=False)
        CG.sync_cursor = MagicMock(return_value=cm)  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _gleif_name_hit(lei, name)  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("ok") is True
        assert result.get("rowsWritten") == 1

    def test_gleif_hit_name_mismatch_skips(self) -> None:
        lei = "CCCCCCCCCCCCCCCCCCCCC"[:20]
        rows = [("vid:001", "Original Corp")]
        CG.sync_cursor = _noop_cursor_cm(rows)  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _gleif_name_hit(lei, "Different Corp")  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("rowsWritten") == 0

    def test_local_cache_hit_skips_api(self) -> None:
        """Fast path: match via vertex_open_lei_entity, no GLEIF API call."""
        lei = "DDDDDDDDDDDDDDDDDDDDD"[:20]
        name = "Local Cache Corp"
        bp_rows = [("vid:001", name)]
        # First cursor call returns bp_rows; second returns the local LEI match.
        call_count = [0]

        def make_cm(bp_rows: list, lei_rows: list) -> MagicMock:
            cur = MagicMock()
            responses = [bp_rows, lei_rows]

            def fetchall_side_effect() -> list:
                idx = call_count[0]
                call_count[0] += 1
                return responses[idx] if idx < len(responses) else []

            cur.fetchall.side_effect = fetchall_side_effect
            cur.fetchone.return_value = None
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cur)
            cm.__exit__ = MagicMock(return_value=False)
            return MagicMock(return_value=cm)

        CG.sync_cursor = make_cm(bp_rows, [(name.lower(), lei)])  # type: ignore[attr-defined]
        api_called = []
        CG._fetch_url = lambda url, timeout=30: (api_called.append(url), _gleif_name_miss())[1]  # type: ignore[attr-defined]
        result = CG._ingest_business_person_lei(50)
        assert result.get("ok") is True
        assert result.get("rowsWritten") == 1
        assert len(api_called) == 0, "GLEIF API should not be called when local cache hits"


# ── org_hierarchy ──────────────────────────────────────────────────────────────

class TestIngestOrgHierarchy:
    def setup_method(self) -> None:
        self._orig_sc = CG.sync_cursor

    def teardown_method(self) -> None:
        CG.sync_cursor = self._orig_sc  # type: ignore[attr-defined]

    def test_returns_dict(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_org_hierarchy(50)
        assert isinstance(result, dict)

    def test_ok_true_no_lei_rows(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_org_hierarchy(50)
        assert result.get("ok") is True

    def test_zero_written_no_lei_rows(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_org_hierarchy(50)
        assert result.get("rowsWritten") == 0

    def test_error_message_explains_missing_lei(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_org_hierarchy(50)
        assert "lei" in result.get("error", "").lower()


# ── follows_history ────────────────────────────────────────────────────────────

class TestIngestFollowsHistory:
    def setup_method(self) -> None:
        self._orig_sc = CG.sync_cursor

    def teardown_method(self) -> None:
        CG.sync_cursor = self._orig_sc  # type: ignore[attr-defined]

    def test_returns_dict(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_follows_history(50)
        assert isinstance(result, dict)

    def test_ok_true_no_actors(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_follows_history(50)
        assert result.get("ok") is True

    def test_zero_written_no_actors(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        result = CG._ingest_follows_history(50)
        assert result.get("rowsWritten") == 0


# ── natural_person ─────────────────────────────────────────────────────────────

class TestIngestNaturalPerson:
    def setup_method(self) -> None:
        self._orig_sc = CG.sync_cursor
        self._orig_fetch = CG._fetch_url
        CG._WD_CURSOR.clear()  # reset in-memory cursor between tests

    def teardown_method(self) -> None:
        CG.sync_cursor = self._orig_sc  # type: ignore[attr-defined]
        CG._fetch_url = self._orig_fetch  # type: ignore[attr-defined]
        CG._WD_CURSOR.clear()

    def test_returns_dict(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]
        result = CG._ingest_natural_person(8_000_000_000)
        assert isinstance(result, dict)

    def test_ok_true_no_humans_in_batch(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]
        result = CG._ingest_natural_person(8_000_000_000)
        assert result.get("ok") is True

    def test_zero_written_no_humans(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]
        result = CG._ingest_natural_person(8_000_000_000)
        assert result.get("rowsWritten") == 0

    def test_cursor_advances_after_run(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]
        CG._ingest_natural_person(8_000_000_000)
        assert CG._WD_CURSOR.get("qnum", 0) > 999999

    def test_human_found_writes_row(self) -> None:
        call_count = 0

        def fake_fetch(url: str, timeout: int = 30) -> bytes:
            nonlocal call_count
            call_count += 1
            return _wbgetentities_one_human(1000001, "Alice")

        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = []
        cur_mock.fetchone.return_value = None  # no existing row → writes
        cur_mock.rowcount = 0
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cur_mock)
        cm.__exit__ = MagicMock(return_value=False)
        CG.sync_cursor = MagicMock(return_value=cm)  # type: ignore[attr-defined]
        CG._fetch_url = fake_fetch  # type: ignore[attr-defined]

        result = CG._ingest_natural_person(8_000_000_000)
        assert result.get("ok") is True
        assert result.get("rowsWritten", 0) >= 1

    def test_cursor_seeds_from_db_max_qid(self) -> None:
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = []
        cur_mock.fetchone.return_value = ("Q2000000",)  # simulate existing max Q-ID
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cur_mock)
        cm.__exit__ = MagicMock(return_value=False)
        CG.sync_cursor = MagicMock(return_value=cm)  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]

        CG._ingest_natural_person(8_000_000_000)
        assert CG._WD_CURSOR.get("qnum", 0) >= 2000000

    def test_has_cursor_at_key(self) -> None:
        CG.sync_cursor = _noop_cursor_cm()  # type: ignore[attr-defined]
        CG._fetch_url = lambda url, timeout=30: _wbgetentities_no_humans()  # type: ignore[attr-defined]
        result = CG._ingest_natural_person(8_000_000_000)
        assert "cursorAt" in result
