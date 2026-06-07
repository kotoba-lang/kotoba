"""V16 InstitutionMatcherActor tests — loading, ranking, gates, staleness."""
from __future__ import annotations

from datetime import date

import pytest

from kotodama.projects.uhl_right_neural.actors.institution_matcher import (
    InstitutionMatcherActor,
)
from kotodama.projects.uhl_right_neural.actors.substrate_classifier import (
    SubstrateClass,
)
from kotodama.projects.uhl_right_neural.schemas import CapabilityKind


@pytest.fixture(scope="module")
def matcher() -> InstitutionMatcherActor:
    return InstitutionMatcherActor()


# ── Registry loading ─────────────────────────────────────────────────────────


def test_registry_loads_both_seed_files(matcher: InstitutionMatcherActor) -> None:
    items = matcher._load()
    assert len(items) >= 12  # 8 jp + 7 intl - some buffer
    ids = {i.id for i in items}
    # spot-check a known domestic and international entry
    assert "jp-shinshu-u-orl" in ids
    assert "uk-manchester-abi" in ids


# ── Substrate routing ───────────────────────────────────────────────────────


def test_nerve_aplasia_routes_to_abi(matcher: InstitutionMatcherActor) -> None:
    result = matcher.match(
        substrate_class=SubstrateClass.NERVE_APLASIA,
        locale_country="JP",
        dfnb9_confirmed=False,
    )
    # Should include Manchester / GSTT / Fukushima-NMS — all ABI providers
    matched_ids = {c.institution_id for c in result.candidates}
    assert any("abi" in mid or "fukushima" in mid for mid in matched_ids)
    # Every candidate must have ABI in matched capabilities
    for c in result.candidates:
        assert CapabilityKind.ABI in c.matched_capabilities


def test_sgn_absent_routes_to_research(matcher: InstitutionMatcherActor) -> None:
    result = matcher.match(
        substrate_class=SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
        locale_country="JP",
        dfnb9_confirmed=False,
    )
    for c in result.candidates:
        assert any(
            k in c.matched_capabilities
            for k in (
                CapabilityKind.NEURAL_REGEN_RESEARCH,
                CapabilityKind.OPTO_CI_TRIAL,
            )
        )


# ── DFNB9 gate ───────────────────────────────────────────────────────────────


def test_gene_tx_otof_filtered_without_dfnb9(
    matcher: InstitutionMatcherActor,
) -> None:
    """GENE_TX_OTOF must NOT appear in matched_capabilities when DFNB9 unconfirmed."""
    result = matcher.match(
        substrate_class=SubstrateClass.SGN_PRESENT_HC_LOSS,
        locale_country="JP",
        dfnb9_confirmed=False,
    )
    for c in result.candidates:
        assert CapabilityKind.GENE_TX_OTOF not in c.matched_capabilities


def test_gene_tx_otof_allowed_with_dfnb9(
    matcher: InstitutionMatcherActor,
) -> None:
    """When DFNB9 confirmed, GENE_TX_OTOF capability may appear."""
    result = matcher.match(
        substrate_class=SubstrateClass.SGN_PRESENT_HC_LOSS,
        locale_country="US",
        dfnb9_confirmed=True,
    )
    has_otof = any(
        CapabilityKind.GENE_TX_OTOF in c.matched_capabilities for c in result.candidates
    )
    assert has_otof, "expected at least one institution to surface GENE_TX_OTOF"


# ── Staleness ────────────────────────────────────────────────────────────────


def test_staleness_flag_set_for_old_records(
    matcher: InstitutionMatcherActor,
) -> None:
    """Records older than 180 days from `today` must carry is_stale=True."""
    future_today = date(2027, 5, 18)  # 365 days after seed verified_at
    result = matcher.match(
        substrate_class=SubstrateClass.NERVE_APLASIA,
        locale_country="GB",
        dfnb9_confirmed=False,
        today=future_today,
    )
    assert result.candidates
    for c in result.candidates:
        assert c.is_stale is True
        assert any("Stale" in n for n in c.notes)


def test_no_staleness_when_recent(matcher: InstitutionMatcherActor) -> None:
    """When today ≈ seed verified_at, nothing is stale."""
    result = matcher.match(
        substrate_class=SubstrateClass.NERVE_APLASIA,
        locale_country="GB",
        dfnb9_confirmed=False,
        today=date(2026, 5, 19),
    )
    for c in result.candidates:
        assert c.is_stale is False


# ── Locale affinity ─────────────────────────────────────────────────────────


def test_locale_match_boosts_domestic(matcher: InstitutionMatcherActor) -> None:
    """For consult-hub type queries, JP locale should rank JP institutions higher."""
    result = matcher.match(
        substrate_class=SubstrateClass.INDETERMINATE,
        locale_country="JP",
        dfnb9_confirmed=False,
        top_n=10,
    )
    assert result.candidates
    # Top candidate must be a JP institution (locale_affinity dominates)
    assert result.candidates[0].country.value == "JP"


# ── Output invariants ───────────────────────────────────────────────────────


def test_output_enforces_human_review_flags(
    matcher: InstitutionMatcherActor,
) -> None:
    result = matcher.match(
        substrate_class=SubstrateClass.NERVE_APLASIA,
        locale_country="JP",
        dfnb9_confirmed=False,
    )
    assert result.requires_human_review is True
    assert result.ethics_committee_required is True
    assert result.data_export_requires_review is True


def test_compute_full_state_path(matcher: InstitutionMatcherActor) -> None:
    """End-to-end compute() call from a representative Pregel state."""
    state = {
        "substrate_decision": {"substrate_class": "nerve_aplasia"},
        "phenotype": {"locale_country": "JP"},
        "substrate_evidence": {"biallelic_otof_pathogenic": False},
    }
    out = matcher.compute(state)
    assert "institution_match" in out
    match = out["institution_match"]
    assert match["requires_human_review"] is True
    assert match["substrate_class"] == "nerve_aplasia"
    assert len(match["candidates"]) >= 1


def test_indeterminate_returns_consult_hub_candidates(
    matcher: InstitutionMatcherActor,
) -> None:
    result = matcher.match(
        substrate_class=SubstrateClass.INDETERMINATE,
        locale_country="JP",
        dfnb9_confirmed=False,
    )
    assert result.candidates  # should find consult-hubs + genetic-test sites
