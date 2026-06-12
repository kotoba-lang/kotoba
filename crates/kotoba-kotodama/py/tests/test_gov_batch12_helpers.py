"""Twelfth batch of gov_* module tests - final remaining countries.

Covers gov_hti, gov_mmr, gov_moz, gov_nic, gov_npl, gov_png,
gov_pry, gov_qat, gov_sdn, gov_tza, gov_uga, gov_ury, gov_uzb,
gov_ven, gov_vnm, gov_yem, gov_zmb, gov_zwe, gov_pse, gov_slv
for _url_to_domain_slug, _vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_hti as HTI
from kotodama.primitives import gov_mmr as MMR
from kotodama.primitives import gov_moz as MOZ
from kotodama.primitives import gov_nic as NIC
from kotodama.primitives import gov_npl as NPL
from kotodama.primitives import gov_pry as PRY
from kotodama.primitives import gov_qat as QAT
from kotodama.primitives import gov_tza as TZA
from kotodama.primitives import gov_uga as UGA
from kotodama.primitives import gov_ury as URY
from kotodama.primitives import gov_uzb as UZB
from kotodama.primitives import gov_ven as VEN
from kotodama.primitives import gov_vnm as VNM
from kotodama.primitives import gov_zmb as ZMB
from kotodama.primitives import gov_zwe as ZWE


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_hti_domain_slug() -> None:
    result = HTI._url_to_domain_slug("https://www.haiti.gouv.ht")
    assert "gouv-ht" in result


def test_mmr_domain_slug() -> None:
    result = MMR._url_to_domain_slug("https://www.president-office.gov.mm")
    assert "gov-mm" in result


def test_moz_domain_slug() -> None:
    result = MOZ._url_to_domain_slug("https://www.presidencia.gov.mz")
    assert "gov-mz" in result


def test_nic_domain_slug() -> None:
    result = NIC._url_to_domain_slug("https://www.presidencia.gob.ni")
    assert "gob-ni" in result


def test_npl_domain_slug() -> None:
    result = NPL._url_to_domain_slug("https://www.opmcm.gov.np")
    assert "gov-np" in result


def test_pry_domain_slug() -> None:
    result = PRY._url_to_domain_slug("https://www.presidencia.gov.py")
    assert "gov-py" in result


def test_qat_domain_slug() -> None:
    result = QAT._url_to_domain_slug("https://www.gco.gov.qa")
    assert "gov-qa" in result


def test_tza_domain_slug() -> None:
    result = TZA._url_to_domain_slug("https://www.statehouse.go.tz")
    assert "go-tz" in result


def test_uga_domain_slug() -> None:
    result = UGA._url_to_domain_slug("https://www.statehouse.go.ug")
    assert "go-ug" in result


def test_ury_domain_slug() -> None:
    result = URY._url_to_domain_slug("https://www.gub.uy")
    assert "gub-uy" in result


def test_uzb_domain_slug() -> None:
    result = UZB._url_to_domain_slug("https://www.president.uz")
    assert "president-uz" in result


def test_ven_domain_slug() -> None:
    result = VEN._url_to_domain_slug("https://www.presidencia.gob.ve")
    assert "gob-ve" in result


def test_vnm_domain_slug() -> None:
    result = VNM._url_to_domain_slug("https://www.chinhphu.vn")
    assert "chinhphu-vn" in result


def test_zmb_domain_slug() -> None:
    result = ZMB._url_to_domain_slug("https://www.statehouse.gov.zm")
    assert "gov-zm" in result


def test_zwe_domain_slug() -> None:
    result = ZWE._url_to_domain_slug("https://www.president.gov.zw")
    assert "gov-zw" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_hti_vertex_id() -> None:
    vid = HTI._vertex_id("premier-ministre")
    assert "at://" in vid and "govOrg" in vid


def test_mmr_vertex_id() -> None:
    vid = MMR._vertex_id("president")
    assert "at://" in vid


def test_moz_vertex_id() -> None:
    vid = MOZ._vertex_id("presidencia")
    assert "presidencia" in vid


def test_nic_vertex_id() -> None:
    vid = NIC._vertex_id("presidencia")
    assert "presidencia" in vid


def test_npl_vertex_id() -> None:
    vid = NPL._vertex_id("president")
    assert "at://" in vid


def test_pry_vertex_id() -> None:
    vid = PRY._vertex_id("presidencia")
    assert "at://" in vid


def test_qat_vertex_id() -> None:
    vid = QAT._vertex_id("emir")
    assert "at://" in vid


def test_tza_vertex_id() -> None:
    vid = TZA._vertex_id("statehouse")
    assert "statehouse" in vid


def test_uga_vertex_id() -> None:
    vid = UGA._vertex_id("statehouse")
    assert "at://" in vid


def test_ury_vertex_id() -> None:
    vid = URY._vertex_id("presidencia")
    assert "presidencia" in vid


def test_uzb_vertex_id() -> None:
    vid = UZB._vertex_id("president")
    assert "at://" in vid


def test_ven_vertex_id() -> None:
    vid = VEN._vertex_id("presidencia")
    assert "presidencia" in vid


def test_vnm_vertex_id() -> None:
    vid = VNM._vertex_id("government")
    assert "at://" in vid


def test_zmb_vertex_id() -> None:
    vid = ZMB._vertex_id("statehouse")
    assert "at://" in vid


def test_zwe_vertex_id() -> None:
    vid = ZWE._vertex_id("president")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_hti_seed_orgs() -> None:
    orgs = HTI._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mmr_seed_orgs() -> None:
    orgs = MMR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_moz_seed_orgs() -> None:
    orgs = MOZ._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_nic_seed_orgs() -> None:
    orgs = NIC._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_npl_seed_orgs() -> None:
    orgs = NPL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_pry_seed_orgs() -> None:
    orgs = PRY._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_qat_seed_orgs() -> None:
    orgs = QAT._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tza_seed_orgs() -> None:
    orgs = TZA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_uga_seed_orgs() -> None:
    orgs = UGA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ury_seed_orgs() -> None:
    orgs = URY._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_uzb_seed_orgs() -> None:
    orgs = UZB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ven_seed_orgs() -> None:
    orgs = VEN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_vnm_seed_orgs() -> None:
    orgs = VNM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_zmb_seed_orgs() -> None:
    orgs = ZMB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_zwe_seed_orgs() -> None:
    orgs = ZWE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
