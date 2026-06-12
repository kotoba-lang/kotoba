"""Pure helper tests for gov_* primitives.

All gov_* modules share the same helper pattern:
  _utc_now_iso()
  _url_to_domain_slug(url)
  _load_seed_orgs()
  _vertex_id(path)
  _repo_rkey(prefix, key)
  PRIMARY_DID, DOMAIN_CODE constants

Tests parametrize over a representative sample of gov modules to avoid
duplicating boilerplate for each of the 120+ country modules.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# All gov_* country modules
_GOV_MODULE_NAMES = [
    "gov_afg", "gov_ago", "gov_alb", "gov_and", "gov_are", "gov_arg", "gov_atg",
    "gov_aus", "gov_aut", "gov_bel", "gov_bgd", "gov_bgr", "gov_bhr", "gov_bih",
    "gov_blr", "gov_bol", "gov_bra", "gov_brb", "gov_brn", "gov_bwa", "gov_can",
    "gov_che", "gov_chl", "gov_chn", "gov_civ", "gov_cmr", "gov_cod", "gov_col",
    "gov_cri", "gov_cub", "gov_cyp", "gov_cze", "gov_deu", "gov_dma", "gov_dnk",
    "gov_dom", "gov_dza", "gov_ecu", "gov_egy", "gov_esp", "gov_est", "gov_eth",
    "gov_fin", "gov_fji", "gov_fra", "gov_gbr", "gov_geo", "gov_gha", "gov_grc",
    "gov_grd", "gov_gtm", "gov_guy", "gov_hkg", "gov_hnd", "gov_hrv", "gov_hti",
    "gov_hun", "gov_idn", "gov_ind", "gov_irl", "gov_irn", "gov_irq", "gov_isl",
    "gov_ita", "gov_jam", "gov_jor", "gov_jpn", "gov_kaz", "gov_ken", "gov_kgz",
    "gov_khm", "gov_kor", "gov_kwt", "gov_lao", "gov_lbn", "gov_lby", "gov_lka",
    "gov_ltu", "gov_lux", "gov_lva", "gov_mar", "gov_mdg", "gov_mex", "gov_mhl",
    "gov_mkd", "gov_mlt", "gov_mmr", "gov_mne", "gov_mng", "gov_moz", "gov_mys",
    "gov_nga", "gov_nic", "gov_nld", "gov_nor", "gov_npl", "gov_nzl", "gov_omn",
    "gov_pak", "gov_pan", "gov_per", "gov_phl", "gov_png", "gov_pol", "gov_prk",
    "gov_prt", "gov_pry", "gov_pse", "gov_qat", "gov_rou", "gov_rus", "gov_rwa",
    "gov_sau", "gov_sdn", "gov_sen", "gov_sgp", "gov_slv", "gov_srb", "gov_ssd",
    "gov_sur", "gov_svk", "gov_svn", "gov_swe", "gov_tha", "gov_tjk", "gov_tkm",
    "gov_tls", "gov_tur", "gov_tza", "gov_uga", "gov_ukr", "gov_ury", "gov_usa",
    "gov_uzb", "gov_ven", "gov_vnm", "gov_yem", "gov_zaf", "gov_zmb", "gov_zwe",
]


def _load(name: str) -> Any:
    return importlib.import_module(f"kotodama.primitives.{name}")


# ─── _utc_now_iso ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_utc_now_iso_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._utc_now_iso(), str)


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_utc_now_iso_ends_with_z(mod_name: str):
    mod = _load(mod_name)
    assert mod._utc_now_iso().endswith("Z")


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_utc_now_iso_contains_t(mod_name: str):
    mod = _load(mod_name)
    assert "T" in mod._utc_now_iso()


# ─── _url_to_domain_slug ──────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_url_to_domain_slug_strips_https(mod_name: str):
    mod = _load(mod_name)
    result = mod._url_to_domain_slug("https://www.gov.example.jp/")
    assert "https" not in result


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_url_to_domain_slug_replaces_dots(mod_name: str):
    mod = _load(mod_name)
    result = mod._url_to_domain_slug("https://www.mof.go.jp/")
    assert "." not in result


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_url_to_domain_slug_strips_www(mod_name: str):
    mod = _load(mod_name)
    result = mod._url_to_domain_slug("https://www.example.com/")
    assert not result.startswith("www")


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_url_to_domain_slug_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._url_to_domain_slug("https://example.com/"), str)


def test_gov_jpn_url_to_domain_slug_expected():
    mod = _load("gov_jpn")
    result = mod._url_to_domain_slug("https://www.mof.go.jp/")
    assert result == "mof-go-jp"


def test_gov_usa_url_to_domain_slug_expected():
    mod = _load("gov_usa")
    result = mod._url_to_domain_slug("https://www.whitehouse.gov/")
    assert result == "whitehouse-gov"


# ─── _load_seed_orgs ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_load_seed_orgs_returns_list(mod_name: str):
    mod = _load(mod_name)
    result = mod._load_seed_orgs()
    assert isinstance(result, list)


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_load_seed_orgs_not_empty(mod_name: str):
    mod = _load(mod_name)
    result = mod._load_seed_orgs()
    assert len(result) > 0


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_load_seed_orgs_have_path(mod_name: str):
    mod = _load(mod_name)
    for org in mod._load_seed_orgs():
        assert "path" in org


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_load_seed_orgs_have_name(mod_name: str):
    mod = _load(mod_name)
    for org in mod._load_seed_orgs():
        assert "name" in org


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_load_seed_orgs_are_dicts(mod_name: str):
    mod = _load(mod_name)
    for org in mod._load_seed_orgs():
        assert isinstance(org, dict)


# ─── _vertex_id ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_vertex_id_starts_with_at(mod_name: str):
    mod = _load(mod_name)
    result = mod._vertex_id("some:path")
    assert result.startswith("at://")


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_vertex_id_contains_path(mod_name: str):
    mod = _load(mod_name)
    result = mod._vertex_id("test:org:path")
    assert "test:org:path" in result


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_vertex_id_contains_primary_did(mod_name: str):
    mod = _load(mod_name)
    result = mod._vertex_id("some:path")
    assert mod.PRIMARY_DID in result


# ─── _repo_rkey ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_repo_rkey_starts_with_prefix(mod_name: str):
    mod = _load(mod_name)
    result = mod._repo_rkey("gov-ingest", "mof")
    assert result.startswith("gov-ingest-")


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_repo_rkey_contains_key(mod_name: str):
    mod = _load(mod_name)
    result = mod._repo_rkey("pfx", "my-ministry")
    assert "my-ministry" in result


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_repo_rkey_sanitizes_special_chars(mod_name: str):
    mod = _load(mod_name)
    result = mod._repo_rkey("pfx", "org with spaces!")
    assert " " not in result
    assert "!" not in result


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES[:5])
def test_gov_repo_rkey_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._repo_rkey("pfx", "key"), str)


# ─── constants ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_primary_did_is_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod.PRIMARY_DID, str)


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_primary_did_starts_with_did(mod_name: str):
    mod = _load(mod_name)
    assert mod.PRIMARY_DID.startswith("did:")


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_domain_code_is_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod.DOMAIN_CODE, str)


@pytest.mark.parametrize("mod_name", _GOV_MODULE_NAMES)
def test_gov_domain_code_is_short(mod_name: str):
    mod = _load(mod_name)
    # ISO 3166-1 alpha-3 codes or similar short identifiers
    assert 2 <= len(mod.DOMAIN_CODE) <= 5
