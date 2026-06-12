"""Fifth batch of gov_* module tests (Austria, Belgium, Switzerland, Finland, Greece, Ireland + more).

Covers gov_aut, gov_bel, gov_che, gov_fin, gov_grc, gov_irl,
gov_est, gov_geo, gov_alb, gov_bih for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_aut as AUT
from kotodama.primitives import gov_bel as BEL
from kotodama.primitives import gov_che as CHE
from kotodama.primitives import gov_fin as FIN
from kotodama.primitives import gov_grc as GRC
from kotodama.primitives import gov_irl as IRL
from kotodama.primitives import gov_est as EST
from kotodama.primitives import gov_geo as GEO
from kotodama.primitives import gov_alb as ALB
from kotodama.primitives import gov_bih as BIH


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_aut_domain_slug() -> None:
    result = AUT._url_to_domain_slug("https://www.bundeskanzleramt.gv.at")
    assert "gv-at" in result


def test_bel_domain_slug() -> None:
    result = BEL._url_to_domain_slug("https://www.premier.be")
    assert "premier-be" in result


def test_che_domain_slug() -> None:
    result = CHE._url_to_domain_slug("https://www.admin.ch")
    assert "admin-ch" in result


def test_fin_domain_slug() -> None:
    result = FIN._url_to_domain_slug("https://www.valtioneuvosto.fi")
    assert "valtioneuvosto-fi" in result


def test_grc_domain_slug() -> None:
    result = GRC._url_to_domain_slug("https://www.primeminister.gr")
    assert "primeminister-gr" in result


def test_irl_domain_slug() -> None:
    result = IRL._url_to_domain_slug("https://www.gov.ie")
    assert "gov-ie" in result


def test_est_domain_slug() -> None:
    result = EST._url_to_domain_slug("https://www.riigikantselei.ee")
    assert "riigikantselei-ee" in result


def test_geo_domain_slug() -> None:
    result = GEO._url_to_domain_slug("https://www.gov.ge")
    assert "gov-ge" in result


def test_alb_domain_slug() -> None:
    result = ALB._url_to_domain_slug("https://www.kryeministria.al")
    assert "kryeministria-al" in result


def test_bih_domain_slug() -> None:
    result = BIH._url_to_domain_slug("https://www.vijeceministara.gov.ba")
    assert "gov-ba" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_aut_vertex_id() -> None:
    vid = AUT._vertex_id("bundeskanzler")
    assert "at://" in vid and "govOrg" in vid


def test_bel_vertex_id() -> None:
    vid = BEL._vertex_id("premier")
    assert "premier" in vid


def test_che_vertex_id() -> None:
    vid = CHE._vertex_id("bundesrat")
    assert "bundesrat" in vid


def test_fin_vertex_id() -> None:
    vid = FIN._vertex_id("valtioneuvosto")
    assert "valtioneuvosto" in vid


def test_grc_vertex_id() -> None:
    vid = GRC._vertex_id("primeminister")
    assert "primeminister" in vid


def test_irl_vertex_id() -> None:
    vid = IRL._vertex_id("taoiseach")
    assert "taoiseach" in vid


def test_est_vertex_id() -> None:
    vid = EST._vertex_id("riigikantselei")
    assert "riigikantselei" in vid


def test_geo_vertex_id() -> None:
    vid = GEO._vertex_id("government")
    assert "at://" in vid


def test_alb_vertex_id() -> None:
    vid = ALB._vertex_id("kryeministria")
    assert "at://" in vid


def test_bih_vertex_id() -> None:
    vid = BIH._vertex_id("vijece-ministara")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_aut_seed_orgs() -> None:
    orgs = AUT._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bel_seed_orgs() -> None:
    orgs = BEL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_che_seed_orgs() -> None:
    orgs = CHE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_fin_seed_orgs() -> None:
    orgs = FIN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_grc_seed_orgs() -> None:
    orgs = GRC._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_irl_seed_orgs() -> None:
    orgs = IRL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_est_seed_orgs() -> None:
    orgs = EST._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_geo_seed_orgs() -> None:
    orgs = GEO._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_alb_seed_orgs() -> None:
    orgs = ALB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bih_seed_orgs() -> None:
    orgs = BIH._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
