"""Thirteenth (final) batch of gov_* module tests - last remaining countries.

Covers gov_mdg, gov_mhl, gov_png, gov_prk, gov_pse, gov_sdn,
gov_slv, gov_ssd, gov_sur, gov_tjk, gov_tkm, gov_tls, gov_yem.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_mdg as MDG
from kotodama.primitives import gov_mhl as MHL
from kotodama.primitives import gov_png as PNG
from kotodama.primitives import gov_prk as PRK
from kotodama.primitives import gov_pse as PSE
from kotodama.primitives import gov_sdn as SDN
from kotodama.primitives import gov_slv as SLV
from kotodama.primitives import gov_ssd as SSD
from kotodama.primitives import gov_sur as SUR
from kotodama.primitives import gov_tjk as TJK
from kotodama.primitives import gov_tkm as TKM
from kotodama.primitives import gov_tls as TLS
from kotodama.primitives import gov_yem as YEM


# ─── _url_to_domain_slug ─────────────────────────────────────────────────────

def test_mdg_domain_slug() -> None:
    result = MDG._url_to_domain_slug("https://www.presidence.gov.mg")
    assert "gov-mg" in result


def test_mhl_domain_slug() -> None:
    result = MHL._url_to_domain_slug("https://www.rmi.gov.mh")
    assert "gov-mh" in result


def test_png_domain_slug() -> None:
    result = PNG._url_to_domain_slug("https://www.pm.gov.pg")
    assert "gov-pg" in result


def test_prk_domain_slug() -> None:
    result = PRK._url_to_domain_slug("https://www.naenara.com.kp")
    assert "naenara-com-kp" in result


def test_pse_domain_slug() -> None:
    result = PSE._url_to_domain_slug("https://www.presidency.ps")
    assert "presidency-ps" in result


def test_sdn_domain_slug() -> None:
    result = SDN._url_to_domain_slug("https://www.presidencysudan.com")
    assert "presidencysudan-com" in result


def test_slv_domain_slug() -> None:
    result = SLV._url_to_domain_slug("https://www.presidencia.gob.sv")
    assert "gob-sv" in result


def test_ssd_domain_slug() -> None:
    result = SSD._url_to_domain_slug("https://www.sspresidency.gov.ss")
    assert "gov-ss" in result


def test_sur_domain_slug() -> None:
    result = SUR._url_to_domain_slug("https://www.gov.sr")
    assert "gov-sr" in result


def test_tjk_domain_slug() -> None:
    result = TJK._url_to_domain_slug("https://www.president.tj")
    assert "president-tj" in result


def test_tkm_domain_slug() -> None:
    result = TKM._url_to_domain_slug("https://www.turkmenistan.gov.tm")
    assert "gov-tm" in result


def test_tls_domain_slug() -> None:
    result = TLS._url_to_domain_slug("https://www.presidente.tl")
    assert "presidente-tl" in result


def test_yem_domain_slug() -> None:
    result = YEM._url_to_domain_slug("https://www.presidentyemen.com")
    assert "presidentyemen-com" in result


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_mdg_vertex_id() -> None:
    vid = MDG._vertex_id("presidence")
    assert "at://" in vid and "govOrg" in vid


def test_mhl_vertex_id() -> None:
    vid = MHL._vertex_id("president")
    assert "at://" in vid


def test_png_vertex_id() -> None:
    vid = PNG._vertex_id("prime-minister")
    assert "at://" in vid


def test_prk_vertex_id() -> None:
    vid = PRK._vertex_id("parliament")
    assert "at://" in vid


def test_pse_vertex_id() -> None:
    vid = PSE._vertex_id("presidency")
    assert "presidency" in vid


def test_sdn_vertex_id() -> None:
    vid = SDN._vertex_id("government")
    assert "at://" in vid


def test_slv_vertex_id() -> None:
    vid = SLV._vertex_id("presidencia")
    assert "presidencia" in vid


def test_ssd_vertex_id() -> None:
    vid = SSD._vertex_id("presidency")
    assert "at://" in vid


def test_sur_vertex_id() -> None:
    vid = SUR._vertex_id("president")
    assert "at://" in vid


def test_tjk_vertex_id() -> None:
    vid = TJK._vertex_id("president")
    assert "at://" in vid


def test_tkm_vertex_id() -> None:
    vid = TKM._vertex_id("president")
    assert "at://" in vid


def test_tls_vertex_id() -> None:
    vid = TLS._vertex_id("presidente")
    assert "presidente" in vid


def test_yem_vertex_id() -> None:
    vid = YEM._vertex_id("president")
    assert "at://" in vid


# ─── _load_seed_orgs ─────────────────────────────────────────────────────────

def test_mdg_seed_orgs() -> None:
    orgs = MDG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_mhl_seed_orgs() -> None:
    orgs = MHL._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_png_seed_orgs() -> None:
    orgs = PNG._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_prk_seed_orgs() -> None:
    orgs = PRK._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_pse_seed_orgs() -> None:
    orgs = PSE._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_sdn_seed_orgs() -> None:
    orgs = SDN._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_slv_seed_orgs() -> None:
    orgs = SLV._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_ssd_seed_orgs() -> None:
    orgs = SSD._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_sur_seed_orgs() -> None:
    orgs = SUR._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tjk_seed_orgs() -> None:
    orgs = TJK._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tkm_seed_orgs() -> None:
    orgs = TKM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_tls_seed_orgs() -> None:
    orgs = TLS._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0


def test_yem_seed_orgs() -> None:
    orgs = YEM._load_seed_orgs()
    assert isinstance(orgs, list) and len(orgs) > 0
