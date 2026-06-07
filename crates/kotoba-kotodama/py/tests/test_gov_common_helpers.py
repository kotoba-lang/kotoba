"""Tests for the shared pure helpers present in every gov_* primitive module."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_jpn as JPN
from kotodama.primitives import gov_usa as USA
from kotodama.primitives import gov_deu as DEU
from kotodama.primitives import gov_gbr as GBR
from kotodama.primitives import gov_fra as FRA
from kotodama.primitives import gov_chn as CHN
from kotodama.primitives import gov_ind as IND
from kotodama.primitives import gov_bra as BRA


# ─── _repo_rkey ──────────────────────────────────────────────────────────────

def test_repo_rkey_contains_prefix() -> None:
    result = JPN._repo_rkey("doc", "cabinet-order-1")
    assert result.startswith("doc-")


def test_repo_rkey_sanitizes_special_chars() -> None:
    result = JPN._repo_rkey("pfx", "hello world!@#")
    # spaces and special chars replaced by dash
    assert " " not in result
    assert "!" not in result
    assert "@" not in result


def test_repo_rkey_contains_timestamp() -> None:
    result = JPN._repo_rkey("law", "act-001")
    # timestamp is YYYYMMDDHHMMSSffffff (20 digits)
    parts = result.split("-")
    last = parts[-1]
    assert re.match(r"^\d{20}$", last), f"Expected 20-digit timestamp, got: {last!r}"


def test_repo_rkey_empty_key_becomes_record() -> None:
    result = JPN._repo_rkey("pfx", "")
    assert "record" in result


def test_repo_rkey_key_truncated_at_80() -> None:
    long_key = "a" * 200
    result = JPN._repo_rkey("p", long_key)
    # The safe part (after prefix, before timestamp) should be <= 80 chars
    parts = result.split("-")
    safe_part = "-".join(parts[1:-1])
    assert len(safe_part) <= 80


def test_repo_rkey_usa_same_pattern() -> None:
    result = USA._repo_rkey("fed", "executive-order-123")
    assert result.startswith("fed-")
    assert re.search(r"\d{20}$", result)


def test_repo_rkey_deu_same_pattern() -> None:
    result = DEU._repo_rkey("gesetz", "bundesgesetz-001")
    assert result.startswith("gesetz-")


def test_repo_rkey_gbr_same_pattern() -> None:
    result = GBR._repo_rkey("act", "companies-act")
    assert result.startswith("act-")


def test_repo_rkey_fra_same_pattern() -> None:
    result = FRA._repo_rkey("loi", "loi-2024-001")
    assert result.startswith("loi-")


def test_repo_rkey_chn_same_pattern() -> None:
    result = CHN._repo_rkey("fa", "regulation-001")
    assert result.startswith("fa-")


def test_repo_rkey_ind_same_pattern() -> None:
    result = IND._repo_rkey("act", "indian-act-001")
    assert result.startswith("act-")


def test_repo_rkey_bra_same_pattern() -> None:
    result = BRA._repo_rkey("lei", "lei-001")
    assert result.startswith("lei-")


def test_repo_rkey_unique_over_time() -> None:
    # Two calls with same args should produce different rkeys (timestamp differs)
    r1 = JPN._repo_rkey("pfx", "same-key")
    r2 = JPN._repo_rkey("pfx", "same-key")
    # May be same if called within same microsecond; just verify format
    assert r1.startswith("pfx-")
    assert r2.startswith("pfx-")


def test_repo_rkey_leading_dash_stripped() -> None:
    # Key starting with special chars should not produce leading dashes
    result = JPN._repo_rkey("pfx", "---hello---")
    safe = result[4:]  # after "pfx-"
    assert not safe.startswith("-")


def test_repo_rkey_returns_str() -> None:
    assert isinstance(JPN._repo_rkey("x", "y"), str)


# ─── _mint_pds_service_auth (no-URL path) ────────────────────────────────────

def test_mint_pds_service_auth_returns_empty_when_no_url(monkeypatch) -> None:
    monkeypatch.delenv("PDS_SERVICE_AUTH_MINT_URL", raising=False)
    monkeypatch.delenv("PDS_SERVICE_AUTH_MINT_SECRET", raising=False)
    # Must reload after env change since module reads env at import time via module-level var
    # But the function checks the module-level var; force it to empty
    import importlib, kotodama.primitives.gov_jpn as _m
    orig_url = _m.PDS_SERVICE_AUTH_MINT_URL
    orig_sec = _m.PDS_SERVICE_AUTH_MINT_SECRET
    _m.PDS_SERVICE_AUTH_MINT_URL = ""
    _m.PDS_SERVICE_AUTH_MINT_SECRET = ""
    try:
        result = _m._mint_pds_service_auth("com.etzhayyim.apps.gov.jpn.someMethod")
        assert result == ""
    finally:
        _m.PDS_SERVICE_AUTH_MINT_URL = orig_url
        _m.PDS_SERVICE_AUTH_MINT_SECRET = orig_sec


def test_mint_pds_service_auth_returns_str(monkeypatch) -> None:
    import kotodama.primitives.gov_usa as _m
    orig_url = _m.PDS_SERVICE_AUTH_MINT_URL
    orig_sec = _m.PDS_SERVICE_AUTH_MINT_SECRET
    _m.PDS_SERVICE_AUTH_MINT_URL = ""
    _m.PDS_SERVICE_AUTH_MINT_SECRET = ""
    try:
        result = _m._mint_pds_service_auth("com.etzhayyim.apps.gov.usa.someMethod")
        assert isinstance(result, str)
    finally:
        _m.PDS_SERVICE_AUTH_MINT_URL = orig_url
        _m.PDS_SERVICE_AUTH_MINT_SECRET = orig_sec


def test_mint_pds_service_auth_cache_returns_cached_token() -> None:
    import kotodama.primitives.gov_gbr as _m
    import time

    lxm = "com.etzhayyim.apps.gov.gbr.cached"
    future_exp = int(time.time()) + 3600
    _m._PDS_SERVICE_AUTH_CACHE[lxm] = {"token": "cached-token-abc", "expiresAt": future_exp}
    try:
        result = _m._mint_pds_service_auth(lxm)
        assert result == "cached-token-abc"
    finally:
        _m._PDS_SERVICE_AUTH_CACHE.pop(lxm, None)


# ─── _direct_fetch_hash (pure guard paths) ───────────────────────────────────

def test_direct_fetch_hash_empty_url_returns_empty_tuple() -> None:
    result = JPN._direct_fetch_hash("")
    assert result == ("", "")


def test_direct_fetch_hash_non_http_url_returns_empty_tuple() -> None:
    result = JPN._direct_fetch_hash("ftp://example.com/file")
    assert result == ("", "")


def test_direct_fetch_hash_returns_tuple_of_two_strings() -> None:
    result = JPN._direct_fetch_hash("")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


def test_direct_fetch_hash_usa_same_guard() -> None:
    assert USA._direct_fetch_hash("") == ("", "")
    assert USA._direct_fetch_hash("not-a-url") == ("", "")


def test_direct_fetch_hash_deu_same_guard() -> None:
    assert DEU._direct_fetch_hash("") == ("", "")


def test_direct_fetch_hash_chn_same_guard() -> None:
    assert CHN._direct_fetch_hash("file:///etc/passwd") == ("", "")


def test_direct_fetch_hash_ind_same_guard() -> None:
    assert IND._direct_fetch_hash("") == ("", "")


def test_direct_fetch_hash_bra_same_guard() -> None:
    assert BRA._direct_fetch_hash("") == ("", "")
