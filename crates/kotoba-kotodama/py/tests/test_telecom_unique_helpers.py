"""Tests for unique pure helpers in telecom sub-modules (esim, ims, npn, ntn, wlan)."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_esim as ESIM
from kotodama.primitives import telecom_ims as IMS
from kotodama.primitives import telecom_npn as NPN
from kotodama.primitives import telecom_ntn as NTN
from kotodama.primitives import telecom_wlan as WLAN
from kotodama.primitives import telecom_oss as OSS
from kotodama.primitives import telecom_resource as RES


# ─── telecom_esim: _hash ─────────────────────────────────────────────────────

def test_esim_hash_sha256_prefix() -> None:
    result = ESIM._hash("EID-12345678901234567890123456789012")
    assert result is not None
    assert result.startswith("sha256:")


def test_esim_hash_none_returns_none() -> None:
    assert ESIM._hash(None) is None
    assert ESIM._hash("") is None


def test_esim_hash_already_prefixed_passthrough() -> None:
    prefixed = "sha256:" + "a" * 64
    result = ESIM._hash(prefixed)
    assert result == prefixed


def test_esim_hash_deterministic() -> None:
    a = ESIM._hash("eid-001")
    b = ESIM._hash("eid-001")
    assert a == b


def test_esim_hash_varies_with_value() -> None:
    a = ESIM._hash("eid-001")
    b = ESIM._hash("eid-002")
    assert a != b


# ─── telecom_esim: _vid ──────────────────────────────────────────────────────

def test_esim_vid_format() -> None:
    vid = ESIM._vid("euicc", "key-001")
    assert "at://" in vid
    assert "com.etzhayyim.apps.telecom.euicc" in vid
    assert "key-001" in vid


# ─── telecom_ims: _hash_join ─────────────────────────────────────────────────

def test_ims_hash_join_list_of_values() -> None:
    result = IMS._hash_join(["tel:+1234567890", "tel:+9876543210"])
    assert result is not None
    parts = result.split(",")
    assert len(parts) == 2
    assert all(p.startswith("sha256:") for p in parts)


def test_ims_hash_join_none_returns_none() -> None:
    assert IMS._hash_join(None) is None


def test_ims_hash_join_empty_list_returns_none() -> None:
    assert IMS._hash_join([]) is None


def test_ims_hash_join_single_value() -> None:
    result = IMS._hash_join("tel:+1234")
    assert result is not None
    assert result.startswith("sha256:")


def test_ims_hash_join_deterministic() -> None:
    a = IMS._hash_join(["a", "b"])
    b = IMS._hash_join(["a", "b"])
    assert a == b


# ─── telecom_npn: _join_vids ─────────────────────────────────────────────────

def test_npn_join_vids_list() -> None:
    result = NPN._join_vids(["cell-001", "cell-002"], "npnCell")
    assert result is not None
    parts = result.split(",")
    assert len(parts) == 2
    assert all("npnCell" in p for p in parts)


def test_npn_join_vids_none_returns_none() -> None:
    assert NPN._join_vids(None, "kind") is None


def test_npn_join_vids_non_list_returns_none() -> None:
    assert NPN._join_vids("string", "kind") is None


def test_npn_join_vids_empty_list_returns_none() -> None:
    assert NPN._join_vids([], "kind") is None


def test_npn_join_vids_filters_empty() -> None:
    result = NPN._join_vids(["valid", "", "also-valid"], "kind")
    assert result is not None
    parts = result.split(",")
    assert len(parts) == 2


# ─── telecom_ntn: _join_vids (same pattern) ──────────────────────────────────

def test_ntn_join_vids_basic() -> None:
    result = NTN._join_vids(["sat-001"], "ntnSatellite")
    assert result is not None
    assert "ntnSatellite" in result


def test_ntn_join_vids_none_returns_none() -> None:
    assert NTN._join_vids(None, "kind") is None


# ─── telecom_wlan: _parse_date ───────────────────────────────────────────────

def test_wlan_parse_date_iso_string() -> None:
    from datetime import date
    result = WLAN._parse_date("2026-05-01", "field")
    assert result == date(2026, 5, 1)


def test_wlan_parse_date_date_object() -> None:
    from datetime import date
    d = date(2026, 1, 15)
    result = WLAN._parse_date(d, "field")
    assert result == d


def test_wlan_parse_date_none_raises() -> None:
    try:
        WLAN._parse_date(None, "startAt")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ─── telecom_oss: _vid ───────────────────────────────────────────────────────

def test_oss_vid_format() -> None:
    vid = OSS._vid("alarmRecord", "rec-001")
    assert "at://" in vid
    assert "telecom.alarmRecord" in vid
    assert "rec-001" in vid


# ─── telecom_resource: _vid ──────────────────────────────────────────────────

def test_resource_vid_format() -> None:
    vid = RES._vid("networkElement", "ne-001")
    assert "at://" in vid
    assert "telecom.networkElement" in vid
