"""Pure-path tests for gov_afg primitive module.

Covers pure helpers shared across all gov_* modules:
- _url_to_domain_slug: URL → slug
- _vertex_id: path → AT vertex URI
- _load_seed_orgs: in-memory NDJSON parse
- task_gov_afg_resolve_org_path: early return on empty path
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_afg as AFG


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_afg_domain_slug_basic() -> None:
    result = AFG._url_to_domain_slug("https://president.gov.af")
    assert "president" in result


def test_afg_domain_slug_strips_https() -> None:
    result = AFG._url_to_domain_slug("https://mof.gov.af")
    assert "https" not in result


def test_afg_domain_slug_strips_www() -> None:
    result = AFG._url_to_domain_slug("https://www.moi.gov.af")
    assert "www" not in result


def test_afg_domain_slug_returns_string() -> None:
    assert isinstance(AFG._url_to_domain_slug("https://moe.gov.af"), str)


def test_afg_domain_slug_non_empty() -> None:
    result = AFG._url_to_domain_slug("https://mail.gov.af")
    assert len(result) > 0


def test_afg_domain_slug_uses_hyphens() -> None:
    result = AFG._url_to_domain_slug("https://mail.gov.af")
    assert "-" in result or "." not in result


def test_afg_domain_slug_no_scheme() -> None:
    result = AFG._url_to_domain_slug("mail.gov.af")
    assert isinstance(result, str)


def test_afg_domain_slug_empty_returns_string() -> None:
    result = AFG._url_to_domain_slug("")
    assert isinstance(result, str)


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_afg_vertex_id_includes_path() -> None:
    result = AFG._vertex_id("mod")
    assert "mod" in result


def test_afg_vertex_id_starts_with_at() -> None:
    result = AFG._vertex_id("mod")
    assert result.startswith("at://")


def test_afg_vertex_id_includes_did() -> None:
    result = AFG._vertex_id("mod")
    assert "afg" in result or "did:web" in result


def test_afg_vertex_id_returns_string() -> None:
    assert isinstance(AFG._vertex_id("mod"), str)


def test_afg_vertex_id_different_paths_differ() -> None:
    assert AFG._vertex_id("mod") != AFG._vertex_id("mof")


def test_afg_vertex_id_empty_path() -> None:
    result = AFG._vertex_id("")
    assert isinstance(result, str)


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_afg_seed_orgs_returns_list() -> None:
    orgs = AFG._load_seed_orgs()
    assert isinstance(orgs, list)


def test_afg_seed_orgs_non_empty() -> None:
    orgs = AFG._load_seed_orgs()
    assert len(orgs) > 0


def test_afg_seed_orgs_each_has_path() -> None:
    for org in AFG._load_seed_orgs():
        assert "path" in org


def test_afg_seed_orgs_each_has_name() -> None:
    for org in AFG._load_seed_orgs():
        assert "name" in org


def test_afg_seed_orgs_each_has_website() -> None:
    for org in AFG._load_seed_orgs():
        assert "website" in org


def test_afg_seed_orgs_paths_are_strings() -> None:
    for org in AFG._load_seed_orgs():
        assert isinstance(org["path"], str)


def test_afg_seed_orgs_each_has_name_en() -> None:
    for org in AFG._load_seed_orgs():
        assert "nameEn" in org


def test_afg_seed_orgs_each_has_org_tier() -> None:
    for org in AFG._load_seed_orgs():
        assert "orgTier" in org


def test_afg_seed_orgs_has_ministry() -> None:
    paths = [org["path"] for org in AFG._load_seed_orgs()]
    assert any("mod" in p or "mof" in p or "arg" in p for p in paths)


# ─── task_gov_afg_resolve_org_path — early return on empty path ───────────────

def test_afg_resolve_org_path_empty_returns_dict() -> None:
    result = asyncio.run(AFG.task_gov_afg_resolve_org_path(path=""))
    assert isinstance(result, dict)


def test_afg_resolve_org_path_empty_has_error() -> None:
    result = asyncio.run(AFG.task_gov_afg_resolve_org_path(path=""))
    assert "error" in result


def test_afg_resolve_org_path_empty_error_mentions_path() -> None:
    result = asyncio.run(AFG.task_gov_afg_resolve_org_path(path=""))
    assert "path" in result["error"]


def test_afg_resolve_org_path_no_arg_returns_error() -> None:
    result = asyncio.run(AFG.task_gov_afg_resolve_org_path())
    assert "error" in result


def test_afg_resolve_org_path_whitespace_only_returns_error() -> None:
    result = asyncio.run(AFG.task_gov_afg_resolve_org_path(path="   "))
    assert "error" in result


# ─── constants ───────────────────────────────────────────────────────────────

def test_afg_primary_did_is_string() -> None:
    assert isinstance(AFG.PRIMARY_DID, str)


def test_afg_primary_did_starts_with_did() -> None:
    assert AFG.PRIMARY_DID.startswith("did:")


def test_afg_domain_code_is_afg() -> None:
    assert AFG.DOMAIN_CODE == "afg"
