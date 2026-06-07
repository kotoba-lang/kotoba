"""Ninth batch of gov_* module tests (Baltic + Pacific + Southeast Asia + North Africa).

Covers gov_ltu, gov_lva, gov_lux, gov_lka, gov_khm, gov_lao,
gov_nzl, gov_omn, gov_mar, gov_mlt for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_ltu as LTU
from kotodama.primitives import gov_lva as LVA
from kotodama.primitives import gov_lux as LUX
from kotodama.primitives import gov_lka as LKA
from kotodama.primitives import gov_khm as KHM
from kotodama.primitives import gov_lao as LAO
from kotodama.primitives import gov_nzl as NZL
from kotodama.primitives import gov_omn as OMN
from kotodama.primitives import gov_mar as MAR
from kotodama.primitives import gov_mlt as MLT


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_ltu_domain_slug() -> None:
    result = LTU._url_to_domain_slug("https://www.lrv.lt")
    assert "lrv-lt" in result


def test_lva_domain_slug() -> None:
    result = LVA._url_to_domain_slug("https://www.mk.gov.lv")
    assert "gov-lv" in result


def test_lux_domain_slug() -> None:
    result = LUX._url_to_domain_slug("https://www.gouvernement.lu")
    assert "gouvernement-lu" in result


def test_lka_domain_slug() -> None:
    result = LKA._url_to_domain_slug("https://www.pmoffice.gov.lk")
    assert "gov-lk" in result


def test_khm_domain_slug() -> None:
    result = KHM._url_to_domain_slug("https://www.pressocm.gov.kh")
    assert "gov-kh" in result


def test_lao_domain_slug() -> None:
    result = LAO._url_to_domain_slug("https://www.na.gov.la")
    assert "gov-la" in result


def test_nzl_domain_slug() -> None:
    result = NZL._url_to_domain_slug("https://www.dpmc.govt.nz")
    assert "govt-nz" in result


def test_omn_domain_slug() -> None:
    result = OMN._url_to_domain_slug("https://www.oman.om")
    assert "oman-om" in result


def test_mar_domain_slug() -> None:
    result = MAR._url_to_domain_slug("https://www.maroc.ma")
    assert "maroc-ma" in result


def test_mlt_domain_slug() -> None:
    result = MLT._url_to_domain_slug("https://www.gov.mt")
    assert "gov-mt" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_ltu_vertex_id() -> None:
    vid = LTU._vertex_id("vyriausybe")
    assert "at://" in vid and "govOrg" in vid


def test_lva_vertex_id() -> None:
    vid = LVA._vertex_id("ministru-kabinets")
    assert "at://" in vid


def test_lux_vertex_id() -> None:
    vid = LUX._vertex_id("premier-ministre")
    assert "at://" in vid


def test_lka_vertex_id() -> None:
    vid = LKA._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_khm_vertex_id() -> None:
    vid = KHM._vertex_id("prime-minister")
    assert "at://" in vid


def test_lao_vertex_id() -> None:
    vid = LAO._vertex_id("government")
    assert "at://" in vid


def test_nzl_vertex_id() -> None:
    vid = NZL._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_omn_vertex_id() -> None:
    vid = OMN._vertex_id("sultan")
    assert "at://" in vid


def test_mar_vertex_id() -> None:
    vid = MAR._vertex_id("premier-ministre")
    assert "at://" in vid


def test_mlt_vertex_id() -> None:
    vid = MLT._vertex_id("prime-minister")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_ltu_seed_orgs() -> None:
    orgs = LTU._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lva_seed_orgs() -> None:
    orgs = LVA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lux_seed_orgs() -> None:
    orgs = LUX._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lka_seed_orgs() -> None:
    orgs = LKA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_khm_seed_orgs() -> None:
    orgs = KHM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lao_seed_orgs() -> None:
    orgs = LAO._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_nzl_seed_orgs() -> None:
    orgs = NZL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_omn_seed_orgs() -> None:
    orgs = OMN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mar_seed_orgs() -> None:
    orgs = MAR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mlt_seed_orgs() -> None:
    orgs = MLT._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
