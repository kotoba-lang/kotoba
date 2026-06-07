"""Third batch of gov_* module tests (Middle East + Africa + Southeast Asia + Nordic).

Covers gov_sau, gov_are, gov_tha, gov_mys, gov_phl, gov_egy,
gov_nga, gov_ken, gov_nor, gov_dnk for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_sau as SAU
from kotodama.primitives import gov_are as ARE
from kotodama.primitives import gov_tha as THA
from kotodama.primitives import gov_mys as MYS
from kotodama.primitives import gov_phl as PHL
from kotodama.primitives import gov_egy as EGY
from kotodama.primitives import gov_nga as NGA
from kotodama.primitives import gov_ken as KEN
from kotodama.primitives import gov_nor as NOR
from kotodama.primitives import gov_dnk as DNK


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_sau_domain_slug() -> None:
    result = SAU._url_to_domain_slug("https://www.spa.gov.sa")
    assert "gov-sa" in result


def test_are_domain_slug() -> None:
    result = ARE._url_to_domain_slug("https://www.uae.gov.ae")
    assert "gov-ae" in result


def test_tha_domain_slug() -> None:
    result = THA._url_to_domain_slug("https://www.thaigov.go.th")
    assert "thaigov-go-th" in result


def test_mys_domain_slug() -> None:
    result = MYS._url_to_domain_slug("https://www.pmo.gov.my")
    assert "pmo-gov-my" in result


def test_phl_domain_slug() -> None:
    result = PHL._url_to_domain_slug("https://www.officialgazette.gov.ph")
    assert "gov-ph" in result


def test_egy_domain_slug() -> None:
    result = EGY._url_to_domain_slug("https://www.presidency.eg")
    assert "presidency-eg" in result


def test_nga_domain_slug() -> None:
    result = NGA._url_to_domain_slug("https://www.statehouse.gov.ng")
    assert "gov-ng" in result


def test_ken_domain_slug() -> None:
    result = KEN._url_to_domain_slug("https://www.president.go.ke")
    assert "president-go-ke" in result


def test_nor_domain_slug() -> None:
    result = NOR._url_to_domain_slug("https://www.regjeringen.no")
    assert "regjeringen-no" in result


def test_dnk_domain_slug() -> None:
    result = DNK._url_to_domain_slug("https://www.stm.dk")
    assert "stm-dk" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_sau_vertex_id() -> None:
    vid = SAU._vertex_id("council-of-ministers")
    assert "at://" in vid and "govOrg" in vid


def test_are_vertex_id() -> None:
    vid = ARE._vertex_id("supreme-council")
    assert "supreme-council" in vid


def test_tha_vertex_id() -> None:
    vid = THA._vertex_id("prime-minister")
    assert "prime-minister" in vid


def test_mys_vertex_id() -> None:
    vid = MYS._vertex_id("perdana-menteri")
    assert "perdana-menteri" in vid


def test_phl_vertex_id() -> None:
    vid = PHL._vertex_id("malacanan")
    assert "malacanan" in vid


def test_egy_vertex_id() -> None:
    vid = EGY._vertex_id("presidency")
    assert "presidency" in vid


def test_nga_vertex_id() -> None:
    vid = NGA._vertex_id("aso-rock")
    assert "aso-rock" in vid


def test_ken_vertex_id() -> None:
    vid = KEN._vertex_id("state-house")
    assert "state-house" in vid


def test_nor_vertex_id() -> None:
    vid = NOR._vertex_id("statsministeriet")
    assert "statsministeriet" in vid


def test_dnk_vertex_id() -> None:
    vid = DNK._vertex_id("statsministeriet")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_sau_seed_orgs() -> None:
    orgs = SAU._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_are_seed_orgs() -> None:
    orgs = ARE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tha_seed_orgs() -> None:
    orgs = THA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mys_seed_orgs() -> None:
    orgs = MYS._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_phl_seed_orgs() -> None:
    orgs = PHL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_egy_seed_orgs() -> None:
    orgs = EGY._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_nga_seed_orgs() -> None:
    orgs = NGA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ken_seed_orgs() -> None:
    orgs = KEN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_nor_seed_orgs() -> None:
    orgs = NOR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_dnk_seed_orgs() -> None:
    orgs = DNK._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
