"""Eleventh batch of gov_* module tests (remaining countries).

Covers gov_dma, gov_grd, gov_guy, gov_hnd, gov_kgz, gov_kwt,
gov_lby, gov_mkd, gov_mne, gov_mng for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_dma as DMA
from kotodama.primitives import gov_grd as GRD
from kotodama.primitives import gov_guy as GUY
from kotodama.primitives import gov_hnd as HND
from kotodama.primitives import gov_kgz as KGZ
from kotodama.primitives import gov_kwt as KWT
from kotodama.primitives import gov_lby as LBY
from kotodama.primitives import gov_mkd as MKD
from kotodama.primitives import gov_mne as MNE
from kotodama.primitives import gov_mng as MNG


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_dma_domain_slug() -> None:
    result = DMA._url_to_domain_slug("https://www.dominica.gov.dm")
    assert "gov-dm" in result


def test_grd_domain_slug() -> None:
    result = GRD._url_to_domain_slug("https://www.gov.gd")
    assert "gov-gd" in result


def test_guy_domain_slug() -> None:
    result = GUY._url_to_domain_slug("https://www.op.gov.gy")
    assert "gov-gy" in result


def test_hnd_domain_slug() -> None:
    result = HND._url_to_domain_slug("https://www.presidencia.gob.hn")
    assert "gob-hn" in result


def test_kgz_domain_slug() -> None:
    result = KGZ._url_to_domain_slug("https://www.president.kg")
    assert "president-kg" in result


def test_kwt_domain_slug() -> None:
    result = KWT._url_to_domain_slug("https://www.pm.gov.kw")
    assert "gov-kw" in result


def test_lby_domain_slug() -> None:
    result = LBY._url_to_domain_slug("https://www.pc.gov.ly")
    assert "gov-ly" in result


def test_mkd_domain_slug() -> None:
    result = MKD._url_to_domain_slug("https://www.vlada.mk")
    assert "vlada-mk" in result


def test_mne_domain_slug() -> None:
    result = MNE._url_to_domain_slug("https://www.gov.me")
    assert "gov-me" in result


def test_mng_domain_slug() -> None:
    result = MNG._url_to_domain_slug("https://www.zasag.mn")
    assert "zasag-mn" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_dma_vertex_id() -> None:
    vid = DMA._vertex_id("prime-minister")
    assert "at://" in vid and "govOrg" in vid


def test_grd_vertex_id() -> None:
    vid = GRD._vertex_id("prime-minister")
    assert "at://" in vid


def test_guy_vertex_id() -> None:
    vid = GUY._vertex_id("president")
    assert "at://" in vid


def test_hnd_vertex_id() -> None:
    vid = HND._vertex_id("presidencia")
    assert "presidencia" in vid


def test_kgz_vertex_id() -> None:
    vid = KGZ._vertex_id("president")
    assert "at://" in vid


def test_kwt_vertex_id() -> None:
    vid = KWT._vertex_id("emir")
    assert "at://" in vid


def test_lby_vertex_id() -> None:
    vid = LBY._vertex_id("government")
    assert "at://" in vid


def test_mkd_vertex_id() -> None:
    vid = MKD._vertex_id("vlada")
    assert "vlada" in vid


def test_mne_vertex_id() -> None:
    vid = MNE._vertex_id("vlada")
    assert "at://" in vid


def test_mng_vertex_id() -> None:
    vid = MNG._vertex_id("government")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_dma_seed_orgs() -> None:
    orgs = DMA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_grd_seed_orgs() -> None:
    orgs = GRD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_guy_seed_orgs() -> None:
    orgs = GUY._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_hnd_seed_orgs() -> None:
    orgs = HND._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_kgz_seed_orgs() -> None:
    orgs = KGZ._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_kwt_seed_orgs() -> None:
    orgs = KWT._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lby_seed_orgs() -> None:
    orgs = LBY._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mkd_seed_orgs() -> None:
    orgs = MKD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mne_seed_orgs() -> None:
    orgs = MNE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mng_seed_orgs() -> None:
    orgs = MNG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
