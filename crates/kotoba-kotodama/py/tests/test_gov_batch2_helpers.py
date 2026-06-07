"""Second batch of gov_* module tests (Europe + Asia + Africa + Americas).

Covers gov_esp, gov_ita, gov_pol, gov_kor, gov_idn, gov_zaf,
gov_mex, gov_tur, gov_nld, gov_swe for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_esp as ESP
from kotodama.primitives import gov_ita as ITA
from kotodama.primitives import gov_pol as POL
from kotodama.primitives import gov_kor as KOR
from kotodama.primitives import gov_idn as IDN
from kotodama.primitives import gov_zaf as ZAF
from kotodama.primitives import gov_mex as MEX
from kotodama.primitives import gov_tur as TUR
from kotodama.primitives import gov_nld as NLD
from kotodama.primitives import gov_swe as SWE


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_esp_domain_slug() -> None:
    result = ESP._url_to_domain_slug("https://www.lamoncloa.gob.es")
    assert "lamoncloa-gob-es" in result


def test_ita_domain_slug() -> None:
    result = ITA._url_to_domain_slug("https://www.governo.it")
    assert "governo-it" in result


def test_pol_domain_slug() -> None:
    result = POL._url_to_domain_slug("https://www.premier.gov.pl")
    assert "gov-pl" in result or "premier" in result


def test_kor_domain_slug() -> None:
    result = KOR._url_to_domain_slug("https://www.president.go.kr")
    assert "president-go-kr" in result


def test_idn_domain_slug() -> None:
    result = IDN._url_to_domain_slug("https://www.setneg.go.id")
    assert "setneg-go-id" in result


def test_zaf_domain_slug() -> None:
    result = ZAF._url_to_domain_slug("https://www.gov.za")
    assert "gov-za" in result


def test_mex_domain_slug() -> None:
    result = MEX._url_to_domain_slug("https://www.gob.mx")
    assert "gob-mx" in result


def test_tur_domain_slug() -> None:
    result = TUR._url_to_domain_slug("https://www.cbddo.gov.tr")
    assert "gov-tr" in result


def test_nld_domain_slug() -> None:
    result = NLD._url_to_domain_slug("https://www.rijksoverheid.nl")
    assert "rijksoverheid-nl" in result


def test_swe_domain_slug() -> None:
    result = SWE._url_to_domain_slug("https://www.regeringen.se")
    assert "regeringen-se" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_esp_vertex_id() -> None:
    vid = ESP._vertex_id("presidencia")
    assert "at://" in vid and "com.etzhayyim.apps.states.govOrg" in vid


def test_ita_vertex_id() -> None:
    vid = ITA._vertex_id("presidenza")
    assert "presidenza" in vid


def test_pol_vertex_id() -> None:
    vid = POL._vertex_id("kancelaria")
    assert "kancelaria" in vid


def test_kor_vertex_id() -> None:
    vid = KOR._vertex_id("cheongwadae")
    assert "cheongwadae" in vid


def test_idn_vertex_id() -> None:
    vid = IDN._vertex_id("sekretariat")
    assert "sekretariat" in vid


def test_zaf_vertex_id() -> None:
    vid = ZAF._vertex_id("presidency")
    assert "presidency" in vid


def test_mex_vertex_id() -> None:
    vid = MEX._vertex_id("presidencia")
    assert "presidencia" in vid


def test_tur_vertex_id() -> None:
    vid = TUR._vertex_id("cumhurbaskanligi")
    assert "cumhurbaskanligi" in vid


def test_nld_vertex_id() -> None:
    vid = NLD._vertex_id("rijksoverheid")
    assert "rijksoverheid" in vid


def test_swe_vertex_id() -> None:
    vid = SWE._vertex_id("statsradsberednigen")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_esp_seed_orgs() -> None:
    orgs = ESP._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ita_seed_orgs() -> None:
    orgs = ITA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_pol_seed_orgs() -> None:
    orgs = POL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_kor_seed_orgs() -> None:
    orgs = KOR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_idn_seed_orgs() -> None:
    orgs = IDN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_zaf_seed_orgs() -> None:
    orgs = ZAF._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mex_seed_orgs() -> None:
    orgs = MEX._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tur_seed_orgs() -> None:
    orgs = TUR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_nld_seed_orgs() -> None:
    orgs = NLD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_swe_seed_orgs() -> None:
    orgs = SWE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
