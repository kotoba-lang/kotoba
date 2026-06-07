"""Pure helper tests for ipfs_ingest and gov_* primitives.

Covers pure functions with no DB/HTTP/subprocess dependencies:
- ipfs_ingest: _build_multipart / _IPFS_URL_DEFAULT / _IPFS_API_URL_DEFAULT /
               _CHUNK_SIZE / constants
- gov_ago (representative of all 140 gov_* modules):
               _utc_now_iso / _url_to_domain_slug / _url_to_hostname /
               _vertex_id / PRIMARY_DID / DOMAIN_CODE / _MINISTRY_NDJSON /
               _STATE_NDJSON / _OFFICIAL_SOURCE_URLS
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub pyzeebe so ipfs_ingest can be imported without the runtime dep
if "pyzeebe" not in sys.modules:
    _stub = types.ModuleType("pyzeebe")
    _stub.ZeebeWorker = object  # type: ignore[attr-defined]
    sys.modules["pyzeebe"] = _stub

from kotodama.primitives import ipfs_ingest as II
from kotodama.primitives import gov_ago as GA
from kotodama.primitives import gov_alb as GB
from kotodama.primitives import gov_jpn as GJ


# ─── ipfs_ingest — constants ─────────────────────────────────────────────────

def test_ii_url_default_starts_with_https():
    assert II._IPFS_URL_DEFAULT.startswith("https://")


def test_ii_url_default_contains_ipfs():
    assert "ipfs" in II._IPFS_URL_DEFAULT


def test_ii_api_url_default_starts_with_http():
    assert II._IPFS_API_URL_DEFAULT.startswith("http")


def test_ii_chunk_size_is_positive_int():
    assert isinstance(II._CHUNK_SIZE, int)
    assert II._CHUNK_SIZE > 0


def test_ii_chunk_size_is_1mb():
    assert II._CHUNK_SIZE == 1024 * 1024


# ─── ipfs_ingest — _build_multipart ──────────────────────────────────────────

def test_ii_build_multipart_returns_tuple():
    body, boundary = II._build_multipart(b"hello", "test.txt")
    assert isinstance(body, bytes)
    assert isinstance(boundary, str)


def test_ii_build_multipart_contains_filename():
    body, _ = II._build_multipart(b"content", "myfile.bin")
    assert b"myfile.bin" in body


def test_ii_build_multipart_contains_content():
    content = b"test data payload"
    body, _ = II._build_multipart(content, "file.bin")
    assert content in body


def test_ii_build_multipart_boundary_not_empty():
    _, boundary = II._build_multipart(b"x", "f.txt")
    assert len(boundary) > 0


def test_ii_build_multipart_boundary_appears_in_body():
    body, boundary = II._build_multipart(b"x", "f.txt")
    assert boundary.encode() in body


def test_ii_build_multipart_has_content_type():
    body, _ = II._build_multipart(b"x", "f.txt")
    assert b"Content-Type: application/octet-stream" in body


def test_ii_build_multipart_unique_boundaries():
    _, b1 = II._build_multipart(b"x", "f.txt")
    _, b2 = II._build_multipart(b"x", "f.txt")
    assert b1 != b2


def test_ii_build_multipart_empty_content():
    body, boundary = II._build_multipart(b"", "empty.bin")
    assert isinstance(body, bytes)
    assert boundary.encode() in body


# ─── gov_ago — _utc_now_iso ───────────────────────────────────────────────────

def test_ga_utc_now_iso_returns_string():
    assert isinstance(GA._utc_now_iso(), str)


def test_ga_utc_now_iso_ends_with_z():
    assert GA._utc_now_iso().endswith("Z")


def test_ga_utc_now_iso_contains_t():
    assert "T" in GA._utc_now_iso()


# ─── gov_ago — _url_to_domain_slug ───────────────────────────────────────────

def test_ga_url_to_domain_slug_strips_https():
    result = GA._url_to_domain_slug("https://example.gov.ag/page")
    assert "https" not in result
    assert "http" not in result


def test_ga_url_to_domain_slug_replaces_dots():
    result = GA._url_to_domain_slug("https://example.gov.ag")
    assert "." not in result
    assert "-" in result


def test_ga_url_to_domain_slug_strips_www():
    result = GA._url_to_domain_slug("https://www.gov.ag/")
    assert not result.startswith("www")


def test_ga_url_to_domain_slug_returns_string():
    result = GA._url_to_domain_slug("https://gov.ag")
    assert isinstance(result, str)


# ─── gov_ago — _url_to_hostname ──────────────────────────────────────────────

def test_ga_url_to_hostname_extracts_host():
    result = GA._url_to_hostname("https://example.gov.ag/path")
    assert result == "example.gov.ag"


def test_ga_url_to_hostname_lowercases():
    result = GA._url_to_hostname("https://GOV.AG/")
    assert result == result.lower()


def test_ga_url_to_hostname_empty_returns_empty():
    result = GA._url_to_hostname("")
    assert result == ""


def test_ga_url_to_hostname_strips_path():
    result = GA._url_to_hostname("https://host.gov.ag/a/b/c")
    assert "/" not in result


# ─── gov_ago — _vertex_id ────────────────────────────────────────────────────

def test_ga_vertex_id_starts_with_at():
    result = GA._vertex_id("ago:ministry-of-finance")
    assert result.startswith("at://")


def test_ga_vertex_id_contains_path():
    result = GA._vertex_id("ago:ministry-of-finance")
    assert "ago:ministry-of-finance" in result


def test_ga_vertex_id_contains_primary_did():
    result = GA._vertex_id("some-path")
    assert "ago-state.etzhayyim.com" in result


# ─── gov_ago — constants ──────────────────────────────────────────────────────

def test_ga_primary_did_starts_with_did():
    assert GA.PRIMARY_DID.startswith("did:")


def test_ga_primary_did_contains_ago():
    assert "ago" in GA.PRIMARY_DID


def test_ga_domain_code_is_ago():
    assert GA.DOMAIN_CODE == "ago"


def test_ga_ministry_ndjson_is_string():
    assert isinstance(GA._MINISTRY_NDJSON, str)


def test_ga_ministry_ndjson_contains_json():
    assert "{" in GA._MINISTRY_NDJSON


def test_ga_state_ndjson_is_string():
    assert isinstance(GA._STATE_NDJSON, str)


def test_ga_official_source_urls_is_list():
    assert isinstance(GA._OFFICIAL_SOURCE_URLS, list)


# ─── gov_alb (second gov module check) ───────────────────────────────────────

def test_gb_primary_did_starts_with_did():
    assert GB.PRIMARY_DID.startswith("did:")


def test_gb_domain_code_is_alb():
    assert GB.DOMAIN_CODE == "alb"


def test_gb_utc_now_iso_returns_string():
    assert isinstance(GB._utc_now_iso(), str)


def test_gb_url_to_domain_slug_works():
    result = GB._url_to_domain_slug("https://gov.al/path")
    assert isinstance(result, str)


def test_gb_vertex_id_starts_with_at():
    result = GB._vertex_id("alb:ministry")
    assert result.startswith("at://")


# ─── gov_jpn (Japan-specific check) ──────────────────────────────────────────

def test_gj_primary_did_starts_with_did():
    assert GJ.PRIMARY_DID.startswith("did:")


def test_gj_domain_code_is_jpn():
    assert GJ.DOMAIN_CODE == "jpn"


def test_gj_utc_now_iso_returns_string():
    assert isinstance(GJ._utc_now_iso(), str)


def test_gj_url_to_domain_slug_works():
    result = GJ._url_to_domain_slug("https://www.mof.go.jp/")
    assert isinstance(result, str)
    assert len(result) > 0
