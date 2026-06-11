"""Coverage-frontier tests for maps registry/property collection."""

from __future__ import annotations

from kotodama.ingest import maps_collection as M


def test_seed_all_known_variations_includes_property_registry_frontier() -> None:
    out = M.seed_all_known_variations(dryRun=True)

    assert out["byKind"]["propertyRegistry"] == len(M.PROPERTY_REGISTRY_COVERAGE_TARGETS)
    assert out["candidateCount"] >= len(M.PROPERTY_REGISTRY_COVERAGE_TARGETS)

    labels = {target["label"] for target in M.PROPERTY_REGISTRY_COVERAGE_TARGETS}
    assert {
        "LandRegistry",
        "LegalEntity",
        "OwnsProperty",
        "PropertyOwner",
        "PropertyRegistry",
    } <= labels


def test_property_registry_frontier_routes_as_registry_jobs() -> None:
    for target in M.PROPERTY_REGISTRY_COVERAGE_TARGETS:
        assert target["sourceDid"].startswith("did:web:maps.etzhayyim.com:registry:wikidata")
        assert M._label_to_dataset_type(target["label"]) == "registry"
