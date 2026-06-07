"""Fourth batch of gov_* module tests (Eastern Europe + Central Asia + Latin America + Caribbean).

Covers gov_ukr, gov_pak, gov_bgr, gov_hrv, gov_hun, gov_cze,
gov_arg, gov_col, gov_per, gov_chl for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_ukr as UKR
from kotodama.primitives import gov_pak as PAK
from kotodama.primitives import gov_bgr as BGR
from kotodama.primitives import gov_hrv as HRV
from kotodama.primitives import gov_hun as HUN
from kotodama.primitives import gov_cze as CZE
from kotodama.primitives import gov_arg as ARG
from kotodama.primitives import gov_col as COL
from kotodama.primitives import gov_per as PER
from kotodama.primitives import gov_chl as CHL


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_ukr_domain_slug() -> None:
    result = UKR._url_to_domain_slug("https://www.president.gov.ua")
    assert "gov-ua" in result


def test_pak_domain_slug() -> None:
    result = PAK._url_to_domain_slug("https://www.cabinet.gov.pk")
    assert "gov-pk" in result


def test_bgr_domain_slug() -> None:
    result = BGR._url_to_domain_slug("https://www.gov.bg")
    assert "gov-bg" in result


def test_hrv_domain_slug() -> None:
    result = HRV._url_to_domain_slug("https://www.vlada.gov.hr")
    assert "gov-hr" in result


def test_hun_domain_slug() -> None:
    result = HUN._url_to_domain_slug("https://www.kormany.hu")
    assert "kormany-hu" in result


def test_cze_domain_slug() -> None:
    result = CZE._url_to_domain_slug("https://www.vlada.cz")
    assert "vlada-cz" in result


def test_arg_domain_slug() -> None:
    result = ARG._url_to_domain_slug("https://www.argentina.gob.ar")
    assert "gob-ar" in result


def test_col_domain_slug() -> None:
    result = COL._url_to_domain_slug("https://www.presidencia.gov.co")
    assert "gov-co" in result


def test_per_domain_slug() -> None:
    result = PER._url_to_domain_slug("https://www.gob.pe")
    assert "gob-pe" in result


def test_chl_domain_slug() -> None:
    result = CHL._url_to_domain_slug("https://www.gob.cl")
    assert "gob-cl" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_ukr_vertex_id() -> None:
    vid = UKR._vertex_id("president")
    assert "at://" in vid and "govOrg" in vid


def test_pak_vertex_id() -> None:
    vid = PAK._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_bgr_vertex_id() -> None:
    vid = BGR._vertex_id("council-of-ministers")
    assert "council-of-ministers" in vid


def test_hrv_vertex_id() -> None:
    vid = HRV._vertex_id("vlada")
    assert "vlada" in vid


def test_hun_vertex_id() -> None:
    vid = HUN._vertex_id("miniszterelnok")
    assert "miniszterelnok" in vid


def test_cze_vertex_id() -> None:
    vid = CZE._vertex_id("vlada")
    assert "vlada" in vid


def test_arg_vertex_id() -> None:
    vid = ARG._vertex_id("presidencia")
    assert "presidencia" in vid


def test_col_vertex_id() -> None:
    vid = COL._vertex_id("presidencia")
    assert "presidencia" in vid


def test_per_vertex_id() -> None:
    vid = PER._vertex_id("presidencia")
    assert "at://" in vid


def test_chl_vertex_id() -> None:
    vid = CHL._vertex_id("presidencia")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_ukr_seed_orgs() -> None:
    orgs = UKR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_pak_seed_orgs() -> None:
    orgs = PAK._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bgr_seed_orgs() -> None:
    orgs = BGR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_hrv_seed_orgs() -> None:
    orgs = HRV._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_hun_seed_orgs() -> None:
    orgs = HUN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cze_seed_orgs() -> None:
    orgs = CZE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_arg_seed_orgs() -> None:
    orgs = ARG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_col_seed_orgs() -> None:
    orgs = COL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_per_seed_orgs() -> None:
    orgs = PER._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_chl_seed_orgs() -> None:
    orgs = CHL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
