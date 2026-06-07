"""Tests for additional pure helpers in gov_ago (and similar gov modules)."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_ago as AGO
from kotodama.primitives import gov_deu as DEU
from kotodama.primitives import gov_jpn as JPN


# ─── gov_ago: _url_to_hostname ───────────────────────────────────────────────

def test_url_to_hostname_basic() -> None:
    assert AGO._url_to_hostname("https://gov.ao/page") == "gov.ao"


def test_url_to_hostname_http() -> None:
    assert AGO._url_to_hostname("http://example.gov.ao") == "example.gov.ao"


def test_url_to_hostname_lowercases() -> None:
    result = AGO._url_to_hostname("https://Ministry.GOV.AO")
    assert result == "ministry.gov.ao"


def test_url_to_hostname_no_scheme() -> None:
    result = AGO._url_to_hostname("gov.ao/path")
    assert "gov.ao" in result


def test_url_to_hostname_empty_returns_empty() -> None:
    assert AGO._url_to_hostname("") == ""


# ─── gov_ago: _wet_domain_candidates ─────────────────────────────────────────

def test_wet_domain_candidates_basic() -> None:
    result = AGO._wet_domain_candidates("https://www.gov.ao", "gov-ao")
    assert isinstance(result, list)
    assert len(result) > 0


def test_wet_domain_candidates_deduplicates() -> None:
    result = AGO._wet_domain_candidates("https://gov.ao", "gov-ao")
    # No duplicates
    assert len(result) == len(set(result))


def test_wet_domain_candidates_strips_www() -> None:
    result = AGO._wet_domain_candidates("https://www.gov.ao/home", "slug")
    # should have both "www.gov.ao" and "gov.ao" (stripped)
    combined = " ".join(result)
    assert "gov.ao" in combined


def test_wet_domain_candidates_slug_first() -> None:
    result = AGO._wet_domain_candidates("https://example.gov.ao", "my-slug")
    assert result[0] == "my-slug"


# ─── gov_ago: _url_to_domain_slug ────────────────────────────────────────────

def test_ago_domain_slug_basic() -> None:
    result = AGO._url_to_domain_slug("https://gov.ao")
    assert result == "gov-ao"


def test_ago_domain_slug_strips_www() -> None:
    result = AGO._url_to_domain_slug("https://www.example.gov.ao")
    assert "www" not in result
    assert "example-gov-ao" in result


def test_ago_domain_slug_empty_returns_empty() -> None:
    assert AGO._url_to_domain_slug("") == ""


# ─── gov_ago: _vertex_id ─────────────────────────────────────────────────────

def test_ago_vertex_id_format() -> None:
    vid = AGO._vertex_id("mod")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_ago_vertex_id_contains_path() -> None:
    vid = AGO._vertex_id("presidency")
    assert "presidency" in vid


def test_ago_vertex_id_deterministic() -> None:
    a = AGO._vertex_id("mod")
    b = AGO._vertex_id("mod")
    assert a == b


# ─── gov_ago: _load_seed_orgs ────────────────────────────────────────────────

def test_ago_load_seed_orgs_returns_list() -> None:
    orgs = AGO._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_ago_load_seed_orgs_have_required_fields() -> None:
    orgs = AGO._load_seed_orgs()
    for org in orgs[:3]:
        assert "path" in org
        assert "name" in org


# ─── gov_deu: unique helpers ─────────────────────────────────────────────────

def test_deu_load_seed_orgs_returns_list() -> None:
    orgs = DEU._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_deu_vertex_id_format() -> None:
    vid = DEU._vertex_id("bmi")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_deu_url_to_domain_slug() -> None:
    result = DEU._url_to_domain_slug("https://www.bundesregierung.de")
    assert "bundesregierung-de" in result


# ─── gov_jpn: unique helpers ─────────────────────────────────────────────────

def test_jpn_load_seed_orgs_returns_list() -> None:
    orgs = JPN._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_jpn_vertex_id_format() -> None:
    vid = JPN._vertex_id("mof")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_jpn_url_to_domain_slug_japanese_domain() -> None:
    result = JPN._url_to_domain_slug("https://www.mof.go.jp")
    assert "mof-go-jp" in result
