"""Eighth batch of gov_* module tests (Caribbean + South America + Jordan + Kazakhstan).

Covers gov_atg, gov_bol, gov_brb, gov_brn, gov_cub, gov_ecu,
gov_jam, gov_jor, gov_kaz, gov_bwa for _url_to_domain_slug,
_vertex_id, and _load_seed_orgs patterns.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_atg as ATG
from kotodama.primitives import gov_bol as BOL
from kotodama.primitives import gov_brb as BRB
from kotodama.primitives import gov_brn as BRN
from kotodama.primitives import gov_cub as CUB
from kotodama.primitives import gov_ecu as ECU
from kotodama.primitives import gov_jam as JAM
from kotodama.primitives import gov_jor as JOR
from kotodama.primitives import gov_kaz as KAZ
from kotodama.primitives import gov_bwa as BWA


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_atg_domain_slug() -> None:
    result = ATG._url_to_domain_slug("https://www.ab.gov.ag")
    assert "gov-ag" in result


def test_bol_domain_slug() -> None:
    result = BOL._url_to_domain_slug("https://www.presidencia.gob.bo")
    assert "gob-bo" in result


def test_brb_domain_slug() -> None:
    result = BRB._url_to_domain_slug("https://www.pm.gov.bb")
    assert "gov-bb" in result


def test_brn_domain_slug() -> None:
    result = BRN._url_to_domain_slug("https://www.pmo.gov.bn")
    assert "gov-bn" in result


def test_cub_domain_slug() -> None:
    result = CUB._url_to_domain_slug("https://www.presidencia.gob.cu")
    assert "gob-cu" in result


def test_ecu_domain_slug() -> None:
    result = ECU._url_to_domain_slug("https://www.presidencia.gob.ec")
    assert "gob-ec" in result


def test_jam_domain_slug() -> None:
    result = JAM._url_to_domain_slug("https://www.pm.gov.jm")
    assert "gov-jm" in result


def test_jor_domain_slug() -> None:
    result = JOR._url_to_domain_slug("https://www.pm.gov.jo")
    assert "gov-jo" in result


def test_kaz_domain_slug() -> None:
    result = KAZ._url_to_domain_slug("https://www.akorda.kz")
    assert "akorda-kz" in result


def test_bwa_domain_slug() -> None:
    result = BWA._url_to_domain_slug("https://www.gov.bw")
    assert "gov-bw" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_atg_vertex_id() -> None:
    vid = ATG._vertex_id("prime-minister")
    assert "at://" in vid and "govOrg" in vid


def test_bol_vertex_id() -> None:
    vid = BOL._vertex_id("presidencia")
    assert "presidencia" in vid


def test_brb_vertex_id() -> None:
    vid = BRB._vertex_id("prime-minister")
    assert "at://" in vid


def test_brn_vertex_id() -> None:
    vid = BRN._vertex_id("sultan")
    assert "at://" in vid


def test_cub_vertex_id() -> None:
    vid = CUB._vertex_id("presidencia")
    assert "presidencia" in vid


def test_ecu_vertex_id() -> None:
    vid = ECU._vertex_id("presidencia")
    assert "presidencia" in vid


def test_jam_vertex_id() -> None:
    vid = JAM._vertex_id("prime-minister")
    assert "at://" in vid


def test_jor_vertex_id() -> None:
    vid = JOR._vertex_id("royal-court")
    assert "royal-court" in vid


def test_kaz_vertex_id() -> None:
    vid = KAZ._vertex_id("president")
    assert "at://" in vid


def test_bwa_vertex_id() -> None:
    vid = BWA._vertex_id("president")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_atg_seed_orgs() -> None:
    orgs = ATG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bol_seed_orgs() -> None:
    orgs = BOL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_brb_seed_orgs() -> None:
    orgs = BRB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_brn_seed_orgs() -> None:
    orgs = BRN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_cub_seed_orgs() -> None:
    orgs = CUB._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ecu_seed_orgs() -> None:
    orgs = ECU._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_jam_seed_orgs() -> None:
    orgs = JAM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_jor_seed_orgs() -> None:
    orgs = JOR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_kaz_seed_orgs() -> None:
    orgs = KAZ._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_bwa_seed_orgs() -> None:
    orgs = BWA._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
