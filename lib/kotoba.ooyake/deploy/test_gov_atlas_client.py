#!/usr/bin/env python3
"""Tests for the shared gov-atlas read client (ADR-2606021600).

Run: python3 test_gov_atlas_client.py   (or pytest)
Asserts against the committed registry seeds (curated core).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gov_atlas_client import GovAtlas  # noqa: E402

A = GovAtlas()


def test_get_unit():
    u = A.get_unit("gov.jpn.mof")
    assert u and u[":gov.unit/name-local"] == "財務省"
    assert A.get_unit("gov.nonexistent") is None


def test_resolve_path():
    chain = A.resolve_path("gov.jpn.mof.nta.tokyo.kojimachi")
    ids = [u[":gov.unit/id"] for u in chain]
    assert ids == ["gov.jpn", "gov.jpn.mof", "gov.jpn.mof.nta",
                   "gov.jpn.mof.nta.tokyo", "gov.jpn.mof.nta.tokyo.kojimachi"], ids


def test_children():
    kids = {u[":gov.unit/id"] for u in A.children("gov.jpn")}
    # 財務省 + the JP-central ministries are direct children of gov.jpn
    assert "gov.jpn.mof" in kids and "gov.jpn.cao" in kids


def test_facets():
    assert any(u[":gov.unit/id"] == "gov.jpn.mof" for u in A.by_level("ministry"))
    jp = A.by_jurisdiction("jpn")
    assert len(jp) >= 20  # base + JP central
    assert all((u.get(":gov.unit/jurisdiction") or "").startswith("jpn") for u in jp)


def test_search():
    hits = {u[":gov.unit/id"] for u in A.search("財務")}
    assert "gov.jpn.mof" in hits


def test_resolve_procedure():
    r = A.resolve_procedure("jp-juminhyo-utsushi")
    assert r and r["owner"]["name"] == "新宿区"
    assert r["windows"][0]["resolved"] and "戸籍住民課" in r["windows"][0]["name"]
    assert r["forms"][0]["chigiriRef"] == "chigiri:gov:jp-juminhyo:v0"
    assert A.resolve_procedure("nope") is None


def test_find_service():
    res = A.find_service("住民票")
    assert res and res[0]["owner"]["name"] == "新宿区"


def test_full_atlas_loaded():
    # the client must load the FULL atlas, not just the *.seed.edn core
    assert len(A.units) > 6000, len(A.units)
    assert A.get_unit("gov.fra.minefi") and A.get_unit("gov.deu.bundesbank")


def test_by_branch():
    judic = A.by_branch("judicial")
    assert any(u[":gov.unit/id"].endswith(".supreme-court") for u in judic)
    assert len(A.by_branch("legislative")) >= 150


def test_country_profile():
    p = A.country_profile("fra")
    assert p["country"][":gov.unit/id"] == "gov.fra"
    assert p["national_body_count"] >= 5
    assert p["subdivision_count"] >= 1
    assert "executive" in p["bodies_by_branch"]


def test_addresses_for():
    # France's central bank HQ (Banque de France) is geolocated
    assert any(a.get(":gov.address/lat") is not None for a in A.addresses_for("gov.fra.banque"))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")

