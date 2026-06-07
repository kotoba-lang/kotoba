"""Pregel topology smoke tests — graph compiles and end-to-end run succeeds."""
from __future__ import annotations

import pytest

from kotodama.projects.uhl_right_neural.pregel import app, build_graph


def test_graph_compiles() -> None:
    g = build_graph()
    assert g is not None


def test_app_singleton_compiles() -> None:
    assert app is not None


def test_all_16_vertices_present() -> None:
    g = build_graph()
    expected = {
        "V01_phenotype",
        "V02_genetic_screen",
        "V03_imaging",
        "V04_electrophys",
        "V05_cmv_torch",
        "V06_substrate_classifier",
        "V07_otof_tx",
        "V08_neurotrophin",
        "V09_reprogramming",
        "V10_device_fitting",
        "V11_abi",
        "V12_plasticity",
        "V13_outcome",
        "V14_trial_design",
        "V15_regulatory",
        "V16_institution_matcher",
    }
    # LangGraph exposes nodes via the compiled graph's nodes attribute
    actual = set(g.nodes.keys()) if hasattr(g, "nodes") else set()
    # Compiled graphs may expose nodes through different attrs across versions;
    # fall back to the builder if needed.
    if not actual:
        from kotodama.projects.uhl_right_neural.pregel import _build  # type: ignore

        builder = _build()
        actual = set(builder.nodes.keys())
    missing = expected - actual
    assert not missing, f"missing vertices: {missing}"


@pytest.mark.parametrize(
    "evidence,expected_substrate_class,terminal_present",
    [
        # nerve aplasia → V11 → V12-V16
        (
            {"cn_fiber_count": 0},
            "nerve_aplasia",
            True,
        ),
        # SGN-present HC-loss → V07 → V10 → V12-V16
        (
            {
                "cn_fiber_count": 4,
                "eabr_present": True,
                "eabr_latency_prolonged": False,
                "dpoae_present": False,
            },
            "sgn_present_hc_loss",
            True,
        ),
    ],
)
def test_end_to_end_run(
    evidence: dict,
    expected_substrate_class: str,
    terminal_present: bool,
) -> None:
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-abc12345",
                "side": "right",
                "age_years": 3.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": evidence,
        }
    )
    assert final["phenotype"]["in_project_scope"] is True
    assert final["substrate_decision"]["substrate_class"] == expected_substrate_class
    if terminal_present:
        assert "institution_match" in final
        assert final["institution_match"]["requires_human_review"] is True


def test_phenotype_out_of_scope_left_side() -> None:
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-leftxxxx",
                "side": "left",
                "age_years": 3.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {"cn_fiber_count": 0},
        }
    )
    assert final["phenotype"]["in_project_scope"] is False
    # Pipeline still runs (we don't hard-block out-of-scope), but flag is False
    assert "institution_match" in final


def test_p0_full_pipeline_emits_v10_v12_v13_outputs() -> None:
    """SGN_PRESENT_HC_LOSS pediatric case exercises V10 + V12 + V13 actors."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-p0fullxx",
                "side": "right",
                "age_years": 2.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {
                "cn_fiber_count": 4,
                "eabr_present": True,
                "eabr_latency_prolonged": False,
                "dpoae_present": False,
            },
            "outcome_input": {
                "localization": {"trials": 20, "successes": 14},
                "sin": {"trials": 20, "successes": 15},
                "pedsql": {"trials": 20, "successes": 16},
            },
        }
    )
    # V10 — eCI fitting plan with pediatric seed
    assert final["device_plan"]["recommendation"] == "electrical_ci"
    assert final["device_plan"]["t_level_initial_cl"] == 100
    # V12 — optimal phase gate at age 2
    assert final["plasticity_plan"]["phase_gate"] == "optimal"
    assert final["plasticity_plan"]["phase_gate_passed"] is True
    # V13 — three Beta-Binomial posteriors with credible intervals in [0,1]
    posterior = final["outcome_posterior"]
    for axis in ("localization", "sin", "pedsql"):
        a = posterior[axis]
        assert 0.0 <= a["credible_interval_low"] <= a["credible_interval_high"] <= 1.0


def test_nerve_aplasia_defers_device_to_abi() -> None:
    """NERVE_APLASIA routes V10 → V11 ABI candidacy → V15 reg → V16."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-aplasia0",
                "side": "right",
                "age_years": 3.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {"cn_fiber_count": 0},
        }
    )
    # Routed via V11 path so V10 not visited (no device_plan in state).
    assert final["substrate_decision"]["substrate_class"] == "nerve_aplasia"
    assert final["plasticity_plan"]["phase_gate"] == "optimal"
    assert "outcome_posterior" in final
    assert "institution_match" in final
    # P1: V11 ABI plan should be real, not a stub marker.
    abi = final["abi_plan"]
    assert "_stub" not in abi
    assert abi["candidacy"] == "optimal"
    assert abi["surgical_center_preference"] == "manchester_university_nhs"
    # P1: V15 regulatory should classify ABI as PMA / Class 4 device.
    reg = final["regulatory_path"]
    assert "_stub" not in reg
    assert reg["treatment_category"] == "auditory_brainstem_implant"
    assert reg["fda_pathway"] == "premarket_approval"


def test_p1_dfnb9_pediatric_bilateral_chord_path() -> None:
    """SGN_PRESENT_HC_LOSS pediatric + DFNB9 confirmed bilateral → V07 CHORD trial path."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-dfnb9bil",
                "side": "bilateral",
                "age_years": 2.5,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "genetic_input": {
                "panel_run_id": "panel-test-001",
                "variants": [
                    {
                        "gene": "OTOF",
                        "hgvs_c": "c.5098G>C",
                        "zygosity": "homozygous",
                        "acmg_class": 5,
                    },
                ],
            },
            "substrate_evidence": {
                "cn_fiber_count": 4,
                "eabr_present": True,
                "eabr_latency_prolonged": False,
                "dpoae_present": False,
            },
        }
    )
    assert (
        final["substrate_decision"]["substrate_class"] == "sgn_present_hc_loss"
    )
    # V02 → V07 OTOF triage.
    otof = final["otof_tx_plan"]
    assert otof["dfnb9_gate_passed"] is True
    assert otof["recommendation"] == "dfnb9_trial_eligible"
    assert otof["access_tier"] == "chord_jp_trial"
    assert otof["unilateral_exception"] is False
    # V15 reg should pick up the OTOF gene-therapy classification.
    reg = final["regulatory_path"]
    assert reg["treatment_category"] == "otof_gene_therapy_otarmeni"
    assert reg["fda_pathway"] == "accelerated_approval"


def test_p1_dfnb9_unilateral_right_side_exception() -> None:
    """SGN_PRESENT_HC_LOSS pediatric + DFNB9 + unilateral right → exception path."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-dfnb9rht",
                "side": "right",
                "age_years": 3.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "genetic_input": {
                "panel_run_id": "panel-test-002",
                "variants": [
                    {
                        "gene": "OTOF",
                        "hgvs_c": "c.5098G>C",
                        "zygosity": "homozygous",
                        "acmg_class": 5,
                    },
                ],
            },
            "substrate_evidence": {
                "cn_fiber_count": 4,
                "eabr_present": True,
                "eabr_latency_prolonged": False,
                "dpoae_present": False,
            },
        }
    )
    otof = final["otof_tx_plan"]
    assert (
        otof["recommendation"] == "dfnb9_trial_unilateral_exception"
    )
    assert otof["unilateral_exception"] is True
    assert otof["requires_sponsor_inquiry"] is True


def test_p1_non_dfnb9_routes_to_device_classification() -> None:
    """No OTOF variant → V07 returns NOT_DFNB9, V15 falls through to device."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-nodfnb9",
                "side": "right",
                "age_years": 2.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {
                "cn_fiber_count": 4,
                "eabr_present": True,
                "eabr_latency_prolonged": False,
                "dpoae_present": False,
            },
        }
    )
    # V02 emitted an empty result (no genetic_input), so V07 sees
    # had_genetic_panel=True (the empty verdicts[] key) + no OTOF flag,
    # which is the NOT_DFNB9 branch (run-but-negative), not NOT_TESTED.
    otof = final["otof_tx_plan"]
    assert otof["recommendation"] == "not_dfnb9"
    # V15 should fall back to the eCI device classification.
    reg = final["regulatory_path"]
    assert reg["treatment_category"] == "electrical_cochlear_implant"
    assert reg["fda_pathway"] == "premarket_approval"


def test_p2_sgn_degenerating_routes_to_neurotrophin() -> None:
    """SGN_DEGENERATING_NERVE_PRESENT routes V08 neurotrophin research track."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-sgndegen",
                "side": "right",
                "age_years": 3.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {
                "cn_fiber_count": 3,
                "eabr_present": True,
                "eabr_latency_prolonged": True,
            },
        }
    )
    assert (
        final["substrate_decision"]["substrate_class"]
        == "sgn_degenerating_nerve_present"
    )
    nt = final["neurotrophin_plan"]
    assert "_stub" not in nt
    assert nt["recommendation"] == "research_track_eligible"
    assert nt["parallel_eci_track"] is True
    assert nt["research_path_id"] == "sgn-regen-uk-research"
    # V15 should classify as AAV-neurotrophin (IND path).
    reg = final["regulatory_path"]
    assert reg["treatment_category"] == "aav_neurotrophin_preservation"
    assert reg["fda_pathway"] == "investigational_new_drug"


def test_p3_sgn_absent_nerve_present_routes_to_reprogramming() -> None:
    """SGN_ABSENT_NERVE_PRESENT routes V09 reprog → optoCI bridge."""
    final = app.invoke(
        {
            "phenotype_input": {
                "patient_ref": "test-hash-sgnabsent",
                "side": "right",
                "age_years": 25.0,
                "onset": "congenital",
                "progressive": False,
                "locale_country": "JP",
            },
            "substrate_evidence": {
                "cn_fiber_count": 2,
                "eabr_present": False,
            },
        }
    )
    assert (
        final["substrate_decision"]["substrate_class"]
        == "sgn_absent_nerve_present"
    )
    rp = final["reprogramming_plan"]
    assert "_stub" not in rp
    assert rp["recommendation"] == "research_track_eligible"
    assert rp["bridge_track"] == "opto_ci_de_trial"
    # V15 should classify as in-situ reprog → IND path.
    reg = final["regulatory_path"]
    assert reg["treatment_category"] == "in_situ_genetic_reprogramming"
    assert reg["fda_pathway"] == "investigational_new_drug"
