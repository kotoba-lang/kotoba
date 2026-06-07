"""Batch tests for gov_* modules sharing the same pure helper patterns.

Tests gov_fra, gov_usa, gov_gbr, gov_can, gov_aus, gov_chn, gov_ind,
gov_bra, gov_deu (already covered in test_gov_extra_helpers), etc.
Each module exposes: _url_to_domain_slug, _vertex_id, _load_seed_orgs.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_fra as FRA
from kotodama.primitives import gov_usa as USA
from kotodama.primitives import gov_gbr as GBR
from kotodama.primitives import gov_can as CAN
from kotodama.primitives import gov_aus as AUS
from kotodama.primitives import gov_chn as CHN
from kotodama.primitives import gov_ind as IND
from kotodama.primitives import gov_bra as BRA


# ─── _url_to_domain_slug (shared pattern) ────────────────────────────────────

def test_fra_domain_slug_basic() -> None:
    assert FRA._url_to_domain_slug("https://gouvernement.fr") == "gouvernement-fr"


def test_fra_domain_slug_strips_www() -> None:
    result = FRA._url_to_domain_slug("https://www.elysee.fr")
    assert "www" not in result
    assert "elysee-fr" in result


def test_usa_domain_slug_basic() -> None:
    assert USA._url_to_domain_slug("https://whitehouse.gov") == "whitehouse-gov"


def test_usa_domain_slug_strips_www() -> None:
    result = USA._url_to_domain_slug("https://www.whitehouse.gov")
    assert "www" not in result
    assert "whitehouse-gov" in result


def test_gbr_domain_slug_basic() -> None:
    result = GBR._url_to_domain_slug("https://gov.uk")
    assert "gov-uk" in result


def test_can_domain_slug_basic() -> None:
    result = CAN._url_to_domain_slug("https://canada.ca")
    assert "canada-ca" in result


def test_aus_domain_slug_basic() -> None:
    result = AUS._url_to_domain_slug("https://australia.gov.au")
    assert "australia-gov-au" in result


def test_chn_domain_slug_basic() -> None:
    result = CHN._url_to_domain_slug("https://www.gov.cn")
    assert "gov-cn" in result


def test_ind_domain_slug_basic() -> None:
    result = IND._url_to_domain_slug("https://india.gov.in")
    assert "india-gov-in" in result


def test_bra_domain_slug_basic() -> None:
    result = BRA._url_to_domain_slug("https://www.gov.br")
    assert "gov-br" in result


# ─── _vertex_id (shared pattern) ─────────────────────────────────────────────

def test_fra_vertex_id_format() -> None:
    vid = FRA._vertex_id("premier-ministre")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.states.govOrg" in vid
    assert "premier-ministre" in vid


def test_usa_vertex_id_format() -> None:
    vid = USA._vertex_id("executive/president")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_gbr_vertex_id_deterministic() -> None:
    a = GBR._vertex_id("cabinet-office")
    b = GBR._vertex_id("cabinet-office")
    assert a == b


def test_can_vertex_id_contains_path() -> None:
    vid = CAN._vertex_id("treasury-board")
    assert "treasury-board" in vid


def test_aus_vertex_id_format() -> None:
    vid = AUS._vertex_id("pm-cabinet")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_chn_vertex_id_format() -> None:
    vid = CHN._vertex_id("state-council")
    assert "state-council" in vid


def test_ind_vertex_id_format() -> None:
    vid = IND._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_bra_vertex_id_format() -> None:
    vid = BRA._vertex_id("presidencia")
    assert "presidencia" in vid


# ─── _load_seed_orgs (shared pattern) ────────────────────────────────────────

def test_fra_load_seed_orgs_nonempty() -> None:
    orgs = FRA._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_fra_load_seed_orgs_have_path_and_name() -> None:
    orgs = FRA._load_seed_orgs()
    for org in orgs[:3]:
        assert "path" in org
        assert "name" in org


def test_usa_load_seed_orgs_nonempty() -> None:
    orgs = USA._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_gbr_load_seed_orgs_nonempty() -> None:
    orgs = GBR._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_can_load_seed_orgs_nonempty() -> None:
    orgs = CAN._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_aus_load_seed_orgs_nonempty() -> None:
    orgs = AUS._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_chn_load_seed_orgs_nonempty() -> None:
    orgs = CHN._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_ind_load_seed_orgs_nonempty() -> None:
    orgs = IND._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_bra_load_seed_orgs_nonempty() -> None:
    orgs = BRA._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0
