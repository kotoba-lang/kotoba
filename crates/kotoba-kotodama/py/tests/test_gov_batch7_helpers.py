"""Seventh batch of gov_* module tests (small states + island nations + Gulf + South Asia).

Covers gov_and, gov_bgd, gov_bhr, gov_cyp, gov_cri, gov_hkg,
gov_irn, gov_irq, gov_isl, gov_lbn for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_and as AND_
from kotodama.primitives import gov_bgd as BGD
from kotodama.primitives import gov_bhr as BHR
from kotodama.primitives import gov_cyp as CYP
from kotodama.primitives import gov_cri as CRI
from kotodama.primitives import gov_hkg as HKG
from kotodama.primitives import gov_irn as IRN
from kotodama.primitives import gov_irq as IRQ
from kotodama.primitives import gov_isl as ISL
from kotodama.primitives import gov_lbn as LBN


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_and_domain_slug() -> None:
    result = AND_._url_to_domain_slug("https://www.govern.ad")
    assert "govern-ad" in result


def test_bgd_domain_slug() -> None:
    result = BGD._url_to_domain_slug("https://www.bangladesh.gov.bd")
    assert "gov-bd" in result


def test_bhr_domain_slug() -> None:
    result = BHR._url_to_domain_slug("https://www.moci.gov.bh")
    assert "gov-bh" in result


def test_cyp_domain_slug() -> None:
    result = CYP._url_to_domain_slug("https://www.presidency.gov.cy")
    assert "gov-cy" in result


def test_cri_domain_slug() -> None:
    result = CRI._url_to_domain_slug("https://www.presidencia.go.cr")
    assert "go-cr" in result


def test_hkg_domain_slug() -> None:
    result = HKG._url_to_domain_slug("https://www.gov.hk")
    assert "gov-hk" in result


def test_irn_domain_slug() -> None:
    result = IRN._url_to_domain_slug("https://www.president.ir")
    assert "president-ir" in result


def test_irq_domain_slug() -> None:
    result = IRQ._url_to_domain_slug("https://www.pmo.iq")
    assert "pmo-iq" in result


def test_isl_domain_slug() -> None:
    result = ISL._url_to_domain_slug("https://www.forsaetisraduneyti.is")
    assert "forsaetisraduneyti-is" in result


def test_lbn_domain_slug() -> None:
    result = LBN._url_to_domain_slug("https://www.presidency.gov.lb")
    assert "gov-lb" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_and_vertex_id() -> None:
    vid = AND_._vertex_id("govern")
    assert "at://" in vid and "govOrg" in vid


def test_bgd_vertex_id() -> None:
    vid = BGD._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_bhr_vertex_id() -> None:
    vid = BHR._vertex_id("king")
    assert "at://" in vid


def test_cyp_vertex_id() -> None:
    vid = CYP._vertex_id("presidency")
    assert "presidency" in vid


def test_cri_vertex_id() -> None:
    vid = CRI._vertex_id("presidencia")
    assert "presidencia" in vid


def test_hkg_vertex_id() -> None:
    vid = HKG._vertex_id("chief-executive")
    assert "chief-executive" in vid


def test_irn_vertex_id() -> None:
    vid = IRN._vertex_id("president")
    assert "at://" in vid


def test_irq_vertex_id() -> None:
    vid = IRQ._vertex_id("prime-minister")
    assert "at://" in vid


def test_isl_vertex_id() -> None:
    vid = ISL._vertex_id("forsaetisraduneyti")
    assert "at://" in vid


def test_lbn_vertex_id() -> None:
    vid = LBN._vertex_id("presidency")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_and_seed_orgs() -> None:
    orgs = AND_._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bgd_seed_orgs() -> None:
    orgs = BGD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bhr_seed_orgs() -> None:
    orgs = BHR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cyp_seed_orgs() -> None:
    orgs = CYP._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cri_seed_orgs() -> None:
    orgs = CRI._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_hkg_seed_orgs() -> None:
    orgs = HKG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_irn_seed_orgs() -> None:
    orgs = IRN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_irq_seed_orgs() -> None:
    orgs = IRQ._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_isl_seed_orgs() -> None:
    orgs = ISL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_lbn_seed_orgs() -> None:
    orgs = LBN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
