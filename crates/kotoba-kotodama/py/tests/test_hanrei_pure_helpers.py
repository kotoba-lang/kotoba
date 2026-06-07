"""Tests for pure helper functions in primitives/hanrei.py:
_job_vid, _case_vid, _jurisdiction_vid, _court_vid, _new_job_id."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import hanrei as HR

_OWNER_DID = "did:web:hanrei.etzhayyim.com"


# ─── _job_vid ─────────────────────────────────────────────────────────────────

def test_job_vid_starts_with_at() -> None:
    assert HR._job_vid("job123").startswith("at://")


def test_job_vid_contains_owner_did() -> None:
    assert _OWNER_DID in HR._job_vid("job123")


def test_job_vid_contains_job_id() -> None:
    assert "job123" in HR._job_vid("job123")


def test_job_vid_deterministic() -> None:
    assert HR._job_vid("abc") == HR._job_vid("abc")


def test_job_vid_varies_with_id() -> None:
    assert HR._job_vid("a") != HR._job_vid("b")


def test_job_vid_returns_string() -> None:
    assert isinstance(HR._job_vid("x"), str)


# ─── _case_vid ────────────────────────────────────────────────────────────────

def test_case_vid_starts_with_at() -> None:
    assert HR._case_vid("case001").startswith("at://")


def test_case_vid_contains_owner_did() -> None:
    assert _OWNER_DID in HR._case_vid("case001")


def test_case_vid_contains_rkey() -> None:
    assert "case001" in HR._case_vid("case001")


def test_case_vid_deterministic() -> None:
    assert HR._case_vid("rkey") == HR._case_vid("rkey")


def test_case_vid_varies_with_rkey() -> None:
    assert HR._case_vid("r1") != HR._case_vid("r2")


# ─── _jurisdiction_vid ────────────────────────────────────────────────────────

def test_jurisdiction_vid_starts_with_at() -> None:
    assert HR._jurisdiction_vid("JPN").startswith("at://")


def test_jurisdiction_vid_contains_owner_did() -> None:
    assert _OWNER_DID in HR._jurisdiction_vid("JPN")


def test_jurisdiction_vid_deterministic() -> None:
    assert HR._jurisdiction_vid("JPN") == HR._jurisdiction_vid("JPN")


def test_jurisdiction_vid_varies_with_iso3() -> None:
    assert HR._jurisdiction_vid("JPN") != HR._jurisdiction_vid("USA")


def test_jurisdiction_vid_hash_length_in_rkey() -> None:
    # rkey part is last segment: 16 hex chars
    vid = HR._jurisdiction_vid("JPN")
    rkey = vid.split("/")[-1]
    assert len(rkey) == 16
    assert all(c in "0123456789abcdef" for c in rkey)


def test_jurisdiction_vid_returns_string() -> None:
    assert isinstance(HR._jurisdiction_vid("GBR"), str)


# ─── _court_vid ───────────────────────────────────────────────────────────────

def test_court_vid_starts_with_at() -> None:
    assert HR._court_vid("supreme").startswith("at://")


def test_court_vid_contains_owner_did() -> None:
    assert _OWNER_DID in HR._court_vid("supreme")


def test_court_vid_deterministic() -> None:
    assert HR._court_vid("supreme") == HR._court_vid("supreme")


def test_court_vid_varies_with_court_id() -> None:
    assert HR._court_vid("supreme") != HR._court_vid("district")


def test_court_vid_rkey_is_hex() -> None:
    vid = HR._court_vid("high")
    rkey = vid.split("/")[-1]
    assert len(rkey) == 16
    assert all(c in "0123456789abcdef" for c in rkey)


def test_court_vid_returns_string() -> None:
    assert isinstance(HR._court_vid("ip_high"), str)


# ─── _new_job_id ──────────────────────────────────────────────────────────────

def test_new_job_id_returns_string() -> None:
    assert isinstance(HR._new_job_id(), str)


def test_new_job_id_length_16() -> None:
    assert len(HR._new_job_id()) == 16


def test_new_job_id_hex_chars() -> None:
    jid = HR._new_job_id()
    assert all(c in "0123456789abcdef" for c in jid)


def test_new_job_id_unique() -> None:
    ids = {HR._new_job_id() for _ in range(10)}
    assert len(ids) == 10
