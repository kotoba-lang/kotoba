"""Tests for pure helper functions in telecom_tmf.py and telecom_5g_security.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_tmf as TMF
from kotodama.primitives import telecom_5g_security as T5G


# ─── telecom_tmf: _vid ───────────────────────────────────────────────────────

def test_tmf_vid_format() -> None:
    vid = TMF._vid("productOffering", "offer-001")
    assert "at://" in vid
    assert "com.etzhayyim.apps.telecom.productOffering" in vid
    assert "offer-001" in vid


def test_tmf_vid_deterministic() -> None:
    a = TMF._vid("order", "ord-1")
    b = TMF._vid("order", "ord-1")
    assert a == b


def test_tmf_vid_varies_by_kind() -> None:
    a = TMF._vid("productOffering", "x")
    b = TMF._vid("productOrder", "x")
    assert a != b


# ─── telecom_tmf: _hash_pii ──────────────────────────────────────────────────

def test_tmf_hash_pii_returns_sha256_prefix() -> None:
    result = TMF._hash_pii("customer@example.com")
    assert result is not None
    assert result.startswith("sha256:")


def test_tmf_hash_pii_none_returns_none() -> None:
    assert TMF._hash_pii(None) is None
    assert TMF._hash_pii("") is None


def test_tmf_hash_pii_deterministic() -> None:
    a = TMF._hash_pii("test@example.com")
    b = TMF._hash_pii("test@example.com")
    assert a == b


def test_tmf_hash_pii_varies_with_value() -> None:
    a = TMF._hash_pii("alice@example.com")
    b = TMF._hash_pii("bob@example.com")
    assert a != b


# ─── telecom_tmf: _join ──────────────────────────────────────────────────────

def test_tmf_join_list_to_csv() -> None:
    result = TMF._join(["a", "b", "c"])
    assert result == "a,b,c"


def test_tmf_join_none_returns_none() -> None:
    assert TMF._join(None) is None


def test_tmf_join_empty_list_returns_none() -> None:
    result = TMF._join([])
    assert result is None


def test_tmf_join_string_passthrough() -> None:
    result = TMF._join("single")
    assert result == "single"


def test_tmf_join_empty_string_returns_none() -> None:
    result = TMF._join("")
    assert result is None


def test_tmf_join_filters_empty_items() -> None:
    result = TMF._join(["a", "", "b"])
    assert result == "a,b"


# ─── telecom_tmf: _require ───────────────────────────────────────────────────

def test_tmf_require_passes_with_all_fields() -> None:
    TMF._require({"a": "val", "b": "other"}, ["a", "b"])


def test_tmf_require_raises_on_missing_field() -> None:
    try:
        TMF._require({"a": "val"}, ["a", "b"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "b" in str(e)


def test_tmf_require_raises_on_none_field() -> None:
    try:
        TMF._require({"a": None}, ["a"])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_tmf_require_raises_on_empty_string() -> None:
    try:
        TMF._require({"a": ""}, ["a"])
        assert False, "expected ValueError"
    except ValueError:
        pass


# ─── telecom_tmf: _new_id ────────────────────────────────────────────────────

def test_tmf_new_id_with_parts_deterministic() -> None:
    a = TMF._new_id("offer", "part1", "part2")
    b = TMF._new_id("offer", "part1", "part2")
    assert a == b


def test_tmf_new_id_starts_with_prefix() -> None:
    result = TMF._new_id("order", "p1")
    assert result.startswith("order_")


def test_tmf_new_id_varies_by_parts() -> None:
    a = TMF._new_id("sub", "x")
    b = TMF._new_id("sub", "y")
    assert a != b


# ─── telecom_5g_security: _hash_id ───────────────────────────────────────────

def test_t5g_hash_id_sha256_prefix() -> None:
    result = T5G._hash_id("imsi:001010000000001")
    assert result is not None
    assert result.startswith("sha256:")


def test_t5g_hash_id_none_returns_none() -> None:
    assert T5G._hash_id(None) is None


def test_t5g_hash_id_empty_returns_none() -> None:
    assert T5G._hash_id("") is None


def test_t5g_hash_id_deterministic() -> None:
    a = T5G._hash_id("supi:123")
    b = T5G._hash_id("supi:123")
    assert a == b


# ─── telecom_5g_security: _join ──────────────────────────────────────────────

def test_t5g_join_list() -> None:
    result = T5G._join(["x", "y", "z"])
    assert result == "x,y,z"


def test_t5g_join_none_returns_none() -> None:
    assert T5G._join(None) is None


def test_t5g_join_set_is_handled() -> None:
    result = T5G._join({"a", "b"})
    assert result is not None
    assert "a" in result and "b" in result


def test_t5g_join_empty_returns_none() -> None:
    assert T5G._join([]) is None
    assert T5G._join("") is None


# ─── telecom_5g_security: _require ───────────────────────────────────────────

def test_t5g_require_passes_with_all() -> None:
    T5G._require({"a": "v", "b": "w"}, ["a", "b"])


def test_t5g_require_raises_on_missing() -> None:
    try:
        T5G._require({"a": "v"}, ["a", "c"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "c" in str(e)
