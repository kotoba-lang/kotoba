"""Tests for ooyake WorldModelCell — cross-actor world-model reconcile
(ADR-2606021600 §3, depends ADR-2606011000 + ADR-2606011800).

Run: python3 -m pytest cells/world_model/test_world_model_cell.py
 or: python3 cells/world_model/test_world_model_cell.py  (self-run)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cell import (  # noqa: E402
    WorldModelCell,
    derive_organism_id,
    load_edges,
    load_gov_units,
    load_organisms,
    parse_edn,
    reconcile_world_model,
    regulators_of,
    render_world_model_edn,
    stewarded_entities_of,
)

# small in-memory fixtures so the structural assertions don't drift with the
# (growing) committed registry — the live-data smoke is test_live_seed_*.
_GOV = {
    "gov.jpn": {":gov.unit/id": "gov.jpn", ":gov.unit/level": ":country", ":gov.unit/name-en": "Japan"},
    "gov.jpn.meti": {":gov.unit/id": "gov.jpn.meti", ":gov.unit/level": ":ministry",
                     ":gov.unit/name-en": "METI", ":gov.unit/organism": "org.state.jp.meti"},
    "gov.jpn.mof": {":gov.unit/id": "gov.jpn.mof", ":gov.unit/level": ":ministry", ":gov.unit/name-en": "MOF"},
    "gov.xx.bad": {":gov.unit/id": "gov.xx.bad", ":gov.unit/level": ":agency",
                   ":gov.unit/name-en": "Bad", ":gov.unit/organism": "org.state.xx.missing"},
    # civic service surface — excluded by construction (G1 power-only, no target-list)
    "gov.jpn.city.13104": {":gov.unit/id": "gov.jpn.city.13104", ":gov.unit/level": ":ward",
                           ":gov.unit/name-en": "Shinjuku City"},
    "madoguchi.x": {":gov.unit/id": "madoguchi.x", ":gov.unit/level": ":madoguchi"},
}
_ORGS = {
    "org.state.jp.meti": {":organism/id": "org.state.jp.meti", ":organism/subkind": ":agency", ":organism/label": "METI"},
    "org.corp.tw.tsmc": {":organism/id": "org.corp.tw.tsmc", ":organism/subkind": ":corp", ":organism/label": "TSMC"},
    "org.state.us.orphan": {":organism/id": "org.state.us.orphan", ":organism/subkind": ":state", ":organism/label": "Orphan"},
}


def test_derive_organism_id():
    assert derive_organism_id("gov.jpn.meti") == "org.gov.jpn.meti"
    assert derive_organism_id("gov.usa") == "org.gov.usa"
    assert derive_organism_id("weird") == "org.gov.weird"


def test_confirmed_dangling_proposed_and_exclusion():
    r = reconcile_world_model(_GOV, _ORGS)
    # METI has an explicit link whose target exists → confirmed
    assert r["confirmed_links"] == [{"unit": "gov.jpn.meti", "organism": "org.state.jp.meti"}]
    # gov.xx.bad has an explicit link whose target is MISSING → dangling (G5 flag)
    assert r["dangling_links"] == [{"unit": "gov.xx.bad", "organism": "org.state.xx.missing"}]
    # gov.jpn (country) + gov.jpn.mof (ministry) → proposed (power-bearing, no link)
    proposed_units = sorted(p["unit"] for p in r["proposed_links"])
    assert proposed_units == ["gov.jpn", "gov.jpn.mof"]
    # ward + madoguchi are civic surface → excluded, never a karma node
    assert r["excluded_non_power_units"] == 2
    # power-bearing total = confirmed(1)+dangling(1)+proposed(2)
    assert r["power_bearing_units"] == 4


def test_proposed_organisms_are_latent_and_representative():
    r = reconcile_world_model(_GOV, _ORGS)
    for o in r["proposed_organisms"]:
        assert o[":organism/standing"] == ":latent"
        assert o[":organism/claimed?"] is False
        assert o[":organism/sourcing"] == ":representative"
        assert o[":organism/kind"] == ":institutional"
    # ministry → :agency, country → :state
    by_unit = {p["unit"]: o for p, o in zip(r["proposed_links"], r["proposed_organisms"])}
    assert by_unit["gov.jpn.mof"][":organism/subkind"] == ":agency"
    assert by_unit["gov.jpn"][":organism/subkind"] == ":state"


def test_orphan_and_non_gov_classification():
    r = reconcile_world_model(_GOV, _ORGS)
    # org.state.us.orphan is governmental but referenced by no gov-unit → orphan
    assert [o["organism"] for o in r["orphan_gov_organisms"]] == ["org.state.us.orphan"]
    # TSMC is a corp → correctly out of atlas scope, not an orphan
    assert r["non_gov_organisms_out_of_atlas"] == 1


def test_coverage_pct():
    r = reconcile_world_model(_GOV, _ORGS)
    # reconciled = confirmed(1) + derived(0) = 1 of 4 power-bearing
    assert r["coverage"]["reconciled"] == 1
    assert r["coverage"]["reconciled_pct"] == 25.0


def test_edn_render_is_wellformed():
    r = reconcile_world_model(_GOV, _ORGS)
    edn = render_world_model_edn(r)
    assert ":reconciled" in edn and ":proposed-links" in edn and ":dangling-links" in edn
    assert "world-model-v1" in edn
    assert 'org.state.jp.meti' in edn
    # balanced braces
    assert edn.count("{") == edn.count("}")


def test_cell_live_mode_gated():
    try:
        WorldModelCell().solve({"mode": "live"})
    except RuntimeError as e:
        assert "not activated" in str(e) and ("G4" in str(e) or "G7" in str(e))
    else:
        raise AssertionError("live mode must raise (gated)")


def test_cell_unknown_mode_rejected():
    try:
        WorldModelCell().solve({"mode": "bogus"})
    except ValueError as e:
        assert "unknown world_model mode" in str(e)
    else:
        raise AssertionError("unknown mode must raise ValueError")


_EDGES = [
    {":en/id": "e1", ":en/kind": ":tends", ":en/from": "org.state.jp.meti", ":en/to": "org.corp.jp.7203"},
    {":en/id": "e2", ":en/kind": ":custodies", ":en/from": "org.state.jp.meti", ":en/to": "org.corp.jp.6758"},
    # :depends-on is the entity's reverse dependency, NOT governance → must be ignored
    {":en/id": "e3", ":en/kind": ":depends-on", ":en/from": "org.state.jp.meti", ":en/to": "org.corp.tw.tsmc"},
    # an edge from a NON-reconciled organism → no stewardship path
    {":en/id": "e4", ":en/kind": ":tends", ":en/from": "org.state.us.orphan", ":en/to": "org.corp.tw.tsmc"},
]


def test_government_stewardship_join():
    orgs = dict(_ORGS)
    orgs["org.corp.jp.7203"] = {":organism/id": "org.corp.jp.7203", ":organism/subkind": ":corp", ":organism/label": "Toyota"}
    orgs["org.corp.jp.6758"] = {":organism/id": "org.corp.jp.6758", ":organism/subkind": ":corp", ":organism/label": "Sony"}
    r = reconcile_world_model(_GOV, orgs, _EDGES)
    paths = r["government_stewardship"]
    # only the two governance edges from the reconciled METI unit resolve
    assert {(p["gov_unit"], p["entity"], p["kind"]) for p in paths} == {
        ("gov.jpn.meti", "org.corp.jp.7203", ":tends"),
        ("gov.jpn.meti", "org.corp.jp.6758", ":custodies"),
    }
    # :depends-on excluded; orphan-origin excluded
    assert all(p["gov_unit"] == "gov.jpn.meti" for p in paths)
    assert paths[0]["entity_label"] in {"Toyota", "Sony"}


def test_stewardship_empty_without_edges():
    r = reconcile_world_model(_GOV, _ORGS)  # edges defaulted to None
    assert r["government_stewardship"] == []


def test_live_seed_stewardship_present():
    r = reconcile_world_model(load_gov_units(), load_organisms(), load_edges())
    stew = r["government_stewardship"]
    assert len(stew) >= 10, len(stew)
    # every stewardship path must originate at a reconciled gov-unit
    reconciled_units = {c["unit"] for c in r["confirmed_links"]} | {d["unit"] for d in r["derived_links"]}
    assert all(s["gov_unit"] in reconciled_units for s in stew)


def test_edn_artifact_roundtrips_through_parser():
    """the persisted artifact must be valid, re-readable EDN (the kotoba-ingest
    contract) — not merely a balanced string. Render → parse → assert structure."""
    r = reconcile_world_model(load_gov_units(), load_organisms(), load_edges())
    doc = parse_edn(render_world_model_edn(r))
    assert isinstance(doc, dict)
    assert doc[":graph"][":name"] == "world-model-v1"
    # reconciled block re-reads as a list of records carrying the wired METI link
    recon = doc[":reconciled"]
    assert isinstance(recon, list) and len(recon) == len(r["confirmed_links"]) + len(r["derived_links"])
    assert any(rec.get(":gov.unit/id") == "gov.jpn.meti"
               and rec.get(":gov.unit/organism") == "org.state.jp.meti" for rec in recon)
    # stewardship block round-trips with the same cardinality
    assert len(doc[":government-stewardship"]) == len(r["government_stewardship"])
    # proposed blocks survive as lists too
    assert isinstance(doc[":proposed-links"], list)
    assert isinstance(doc[":dangling-links"], list)


def test_query_helpers_both_directions():
    orgs = dict(_ORGS)
    orgs["org.corp.jp.7203"] = {":organism/id": "org.corp.jp.7203", ":organism/subkind": ":corp", ":organism/label": "Toyota"}
    orgs["org.corp.jp.6758"] = {":organism/id": "org.corp.jp.6758", ":organism/subkind": ":corp", ":organism/label": "Sony"}
    r = reconcile_world_model(_GOV, orgs, _EDGES)
    # forward: what does METI steward?
    fwd = {s["entity"] for s in stewarded_entities_of(r, "gov.jpn.meti")}
    assert fwd == {"org.corp.jp.7203", "org.corp.jp.6758"}
    # reverse: who regulates Toyota? (only METI in this fixture)
    rev = regulators_of(r, "org.corp.jp.7203")
    assert [x["gov_unit"] for x in rev] == ["gov.jpn.meti"]
    # an un-stewarded entity → no regulators
    assert regulators_of(r, "org.corp.tw.tsmc") == []


def test_live_seed_apple_regulators():
    r = reconcile_world_model(load_gov_units(), load_organisms(), load_edges())
    apple = {x["gov_unit"] for x in regulators_of(r, "org.corp.us.apple")}
    assert {"gov.eu", "gov.usa.sec"} <= apple, apple


def test_live_seed_meti_is_confirmed():
    """Smoke over the REAL committed registry + tsumugi seed: METI must reconcile
    (the one :gov.unit/organism link we wired) and the run must stay honest."""
    gov = load_gov_units()
    orgs = load_organisms()
    r = reconcile_world_model(gov, orgs)
    assert any(c["unit"] == "gov.jpn.meti" and c["organism"] == "org.state.jp.meti"
               for c in r["confirmed_links"]), "METI link must be confirmed"
    assert r["dangling_links"] == [], "no dangling links expected in committed data"
    assert r["power_bearing_units"] > 100, "atlas should carry many power-bearing units"
    # the world model is mostly UNRECONCILED today — that is the honest finding
    assert r["coverage"]["reconciled"] >= 1


def test_cell_writes_artifact(tmp_path=None):
    import tempfile
    d = tempfile.mkdtemp()
    out = WorldModelCell().solve({"mode": "bundled", "out_dir": d})
    assert out["status"] == "ok"
    p = os.path.join(d, "world-model.kotoba.edn")
    assert os.path.exists(p)
    assert "world-model-v1" in open(p, encoding="utf-8").read()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
