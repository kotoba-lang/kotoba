"""SSoT drift-lock for the ooyake↔tsumugi world-model reconcile
(ADR-2606021600 §3; the ake/fuchi/noroshi test_consistency pattern).

Binds the registry links, the tsumugi seed, the coverage gate, the manifest, the
kotoba ingest graph name, and the test runner to ONE source of truth — so a future
edit that wires a `:gov.unit/organism` link but forgets the organism (or drifts the
gate floor, or renames the graph, or drops a cell from the manifest) fails loudly
here instead of silently shipping.

Run: python3 -m pytest cells/world_model/test_consistency.py
 or: python3 cells/world_model/test_consistency.py  (self-run)
"""

from __future__ import annotations

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ACTOR = os.path.normpath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_ACTOR, "scripts"))
sys.path.insert(0, os.path.join(_ACTOR, "deploy"))

from cell import load_organisms, parse_edn, render_world_model_edn, reconcile_world_model, load_gov_units, load_edges  # noqa: E402


def _registry_organism_links() -> dict[str, str]:
    """every committed :gov.unit/organism link, unit-id → organism-id."""
    links: dict[str, str] = {}
    for f in sorted(glob.glob(os.path.join(_ACTOR, "registry", "gov-units*.edn"))):
        for u in parse_edn(open(f, encoding="utf-8").read()).get(":units", []):
            org = u.get(":gov.unit/organism")
            if org:
                links[u[":gov.unit/id"]] = org
    return links


def test_every_registry_link_resolves_to_an_organism():
    """structural zero-dangling lock: each wired link's target exists in tsumugi."""
    links = _registry_organism_links()
    orgs = load_organisms()
    missing = {u: o for u, o in links.items() if o not in orgs}
    assert missing == {}, f"dangling :gov.unit/organism links: {missing}"
    assert len(links) >= 9, len(links)


def test_links_are_unique_targets():
    """no two gov-units claim the SAME organism (1:1 reconcile)."""
    links = _registry_organism_links()
    targets = list(links.values())
    assert len(targets) == len(set(targets)), "duplicate organism target across units"


def test_gate_expected_set_matches_registry():
    """the coverage gate may only expect links that are actually wired, and its
    floor must equal the curated expected-set size (no stale floor)."""
    import world_model_coverage as gate

    links = _registry_organism_links()
    assert gate.EXPECTED_CONFIRMED <= set(links), gate.EXPECTED_CONFIRMED - set(links)
    assert gate.CONFIRMED_FLOOR == len(gate.EXPECTED_CONFIRMED), (
        gate.CONFIRMED_FLOOR, len(gate.EXPECTED_CONFIRMED))


def test_manifest_declares_world_model_cell():
    m = json.loads(open(os.path.join(_ACTOR, "manifest.jsonld"), encoding="utf-8").read())
    names = {c["name"] for c in m.get("cells", [])}
    assert "world_model" in names, names


def test_ingest_graph_name_matches_artifact():
    """the kotoba ingest graph and the EDN artifact graph header are the same name."""
    import ingest_world_model as ing

    assert ing.WORLD_GRAPH == "world-model-v1"
    edn = render_world_model_edn(reconcile_world_model(load_gov_units(), load_organisms(), load_edges()))
    assert ":name \"world-model-v1\"" in edn


def test_runner_wires_world_model_gates():
    rt = open(os.path.join(_ACTOR, "deploy", "run_tests.sh"), encoding="utf-8").read()
    for needle in ("world_model cell", "world_model coverage", "world_model ingest"):
        assert needle in rt, f"run_tests.sh missing: {needle}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
