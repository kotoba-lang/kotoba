"""Tenth batch of gov_* module tests (Iberia + CIS + Sub-Saharan + Southeast Asia + Balkans).

Covers gov_prt, gov_rou, gov_rus, gov_sgp, gov_sen, gov_srb,
gov_svk, gov_svn, gov_pan, gov_rwa for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_prt as PRT
from kotodama.primitives import gov_rou as ROU
from kotodama.primitives import gov_rus as RUS
from kotodama.primitives import gov_sgp as SGP
from kotodama.primitives import gov_sen as SEN
from kotodama.primitives import gov_srb as SRB
from kotodama.primitives import gov_svk as SVK
from kotodama.primitives import gov_svn as SVN
from kotodama.primitives import gov_pan as PAN
from kotodama.primitives import gov_rwa as RWA


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_prt_domain_slug() -> None:
    result = PRT._url_to_domain_slug("https://www.portugal.gov.pt")
    assert "gov-pt" in result


def test_rou_domain_slug() -> None:
    result = ROU._url_to_domain_slug("https://www.gov.ro")
    assert "gov-ro" in result


def test_rus_domain_slug() -> None:
    result = RUS._url_to_domain_slug("https://www.government.ru")
    assert "government-ru" in result


def test_sgp_domain_slug() -> None:
    result = SGP._url_to_domain_slug("https://www.pmo.gov.sg")
    assert "gov-sg" in result


def test_sen_domain_slug() -> None:
    result = SEN._url_to_domain_slug("https://www.presidence.sn")
    assert "presidence-sn" in result


def test_srb_domain_slug() -> None:
    result = SRB._url_to_domain_slug("https://www.srbija.gov.rs")
    assert "gov-rs" in result


def test_svk_domain_slug() -> None:
    result = SVK._url_to_domain_slug("https://www.vlada.gov.sk")
    assert "gov-sk" in result


def test_svn_domain_slug() -> None:
    result = SVN._url_to_domain_slug("https://www.gov.si")
    assert "gov-si" in result


def test_pan_domain_slug() -> None:
    result = PAN._url_to_domain_slug("https://www.presidencia.gob.pa")
    assert "gob-pa" in result


def test_rwa_domain_slug() -> None:
    result = RWA._url_to_domain_slug("https://www.presidency.gov.rw")
    assert "gov-rw" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_prt_vertex_id() -> None:
    vid = PRT._vertex_id("presidencia")
    assert "at://" in vid and "govOrg" in vid


def test_rou_vertex_id() -> None:
    vid = ROU._vertex_id("presedintie")
    assert "at://" in vid


def test_rus_vertex_id() -> None:
    vid = RUS._vertex_id("president")
    assert "at://" in vid


def test_sgp_vertex_id() -> None:
    vid = SGP._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_sen_vertex_id() -> None:
    vid = SEN._vertex_id("presidence")
    assert "presidence" in vid


def test_srb_vertex_id() -> None:
    vid = SRB._vertex_id("vlada")
    assert "vlada" in vid


def test_svk_vertex_id() -> None:
    vid = SVK._vertex_id("vlada")
    assert "at://" in vid


def test_svn_vertex_id() -> None:
    vid = SVN._vertex_id("vlada")
    assert "at://" in vid


def test_pan_vertex_id() -> None:
    vid = PAN._vertex_id("presidencia")
    assert "presidencia" in vid


def test_rwa_vertex_id() -> None:
    vid = RWA._vertex_id("presidency")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_prt_seed_orgs() -> None:
    orgs = PRT._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_rou_seed_orgs() -> None:
    orgs = ROU._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_rus_seed_orgs() -> None:
    orgs = RUS._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_sgp_seed_orgs() -> None:
    orgs = SGP._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_sen_seed_orgs() -> None:
    orgs = SEN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_srb_seed_orgs() -> None:
    orgs = SRB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_svk_seed_orgs() -> None:
    orgs = SVK._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_svn_seed_orgs() -> None:
    orgs = SVN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_pan_seed_orgs() -> None:
    orgs = PAN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_rwa_seed_orgs() -> None:
    orgs = RWA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
