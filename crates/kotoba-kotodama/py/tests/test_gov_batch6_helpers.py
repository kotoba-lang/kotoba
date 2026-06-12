"""Sixth batch of gov_* module tests (Africa, Caribbean, Central America + Oceania).

Covers gov_eth, gov_gha, gov_dza, gov_cmr, gov_civ, gov_cod,
gov_dom, gov_gtm, gov_fji, gov_blr for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_eth as ETH
from kotodama.primitives import gov_gha as GHA
from kotodama.primitives import gov_dza as DZA
from kotodama.primitives import gov_cmr as CMR
from kotodama.primitives import gov_civ as CIV
from kotodama.primitives import gov_cod as COD
from kotodama.primitives import gov_dom as DOM
from kotodama.primitives import gov_gtm as GTM
from kotodama.primitives import gov_fji as FJI
from kotodama.primitives import gov_blr as BLR


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_eth_domain_slug() -> None:
    result = ETH._url_to_domain_slug("https://www.pmo.gov.et")
    assert "gov-et" in result


def test_gha_domain_slug() -> None:
    result = GHA._url_to_domain_slug("https://www.presidency.gov.gh")
    assert "gov-gh" in result


def test_dza_domain_slug() -> None:
    result = DZA._url_to_domain_slug("https://www.el-mouradia.dz")
    assert "el-mouradia-dz" in result


def test_cmr_domain_slug() -> None:
    result = CMR._url_to_domain_slug("https://www.prc.cm")
    assert "prc-cm" in result


def test_civ_domain_slug() -> None:
    result = CIV._url_to_domain_slug("https://www.presidence.ci")
    assert "presidence-ci" in result


def test_cod_domain_slug() -> None:
    result = COD._url_to_domain_slug("https://www.presidence.cd")
    assert "presidence-cd" in result


def test_dom_domain_slug() -> None:
    result = DOM._url_to_domain_slug("https://www.presidencia.gob.do")
    assert "gob-do" in result


def test_gtm_domain_slug() -> None:
    result = GTM._url_to_domain_slug("https://www.presidencia.gob.gt")
    assert "gob-gt" in result


def test_fji_domain_slug() -> None:
    result = FJI._url_to_domain_slug("https://www.fiji.gov.fj")
    assert "gov-fj" in result


def test_blr_domain_slug() -> None:
    result = BLR._url_to_domain_slug("https://www.president.gov.by")
    assert "gov-by" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_eth_vertex_id() -> None:
    vid = ETH._vertex_id("prime-minister")
    assert "at://" in vid and "govOrg" in vid


def test_gha_vertex_id() -> None:
    vid = GHA._vertex_id("presidency")
    assert "presidency" in vid


def test_dza_vertex_id() -> None:
    vid = DZA._vertex_id("president")
    assert "at://" in vid


def test_cmr_vertex_id() -> None:
    vid = CMR._vertex_id("president")
    assert "at://" in vid


def test_civ_vertex_id() -> None:
    vid = CIV._vertex_id("presidence")
    assert "presidence" in vid


def test_cod_vertex_id() -> None:
    vid = COD._vertex_id("presidence")
    assert "at://" in vid


def test_dom_vertex_id() -> None:
    vid = DOM._vertex_id("presidencia")
    assert "presidencia" in vid


def test_gtm_vertex_id() -> None:
    vid = GTM._vertex_id("presidencia")
    assert "at://" in vid


def test_fji_vertex_id() -> None:
    vid = FJI._vertex_id("prime-minister")
    assert "at://" in vid


def test_blr_vertex_id() -> None:
    vid = BLR._vertex_id("president")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_eth_seed_orgs() -> None:
    orgs = ETH._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_gha_seed_orgs() -> None:
    orgs = GHA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_dza_seed_orgs() -> None:
    orgs = DZA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cmr_seed_orgs() -> None:
    orgs = CMR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_civ_seed_orgs() -> None:
    orgs = CIV._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cod_seed_orgs() -> None:
    orgs = COD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_dom_seed_orgs() -> None:
    orgs = DOM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_gtm_seed_orgs() -> None:
    orgs = GTM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_fji_seed_orgs() -> None:
    orgs = FJI._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_blr_seed_orgs() -> None:
    orgs = BLR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
