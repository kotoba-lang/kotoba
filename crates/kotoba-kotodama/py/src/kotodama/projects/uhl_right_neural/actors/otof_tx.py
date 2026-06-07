"""V07 OtofTxActor — Otarmeni (lunsotogene parvec-cwha) access path triage.

Authoritative per ADR-2605181000 §V07 and ADR-2605181060. DFNB9 hard
gate (biallelic OTOF ACMG class 4-5 from V02) plus CHORD JP trial
inclusion windows decide which of the three access tiers — CHORD JP
trial / PMDA routine / personal import — is plausible. Unilateral
right-side cases (this project's main cohort) are typically NOT DFNB9
and are explicitly flagged as exceptions requiring sponsor + ethics
escalation per ADR-2605181060 §片側性症例の例外処理.

No LLM. All routing is rule-driven against the V02 genetic screen +
V01 phenotype state. Every output carries requires_human_review=True
plus the ADR-2605181060 unilateral-exception flag when applicable.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# CHORD trial age window (NCT05788536). The trial recruited infants
# through adolescents; we treat ≥ 18y as out-of-trial-window today.
_CHORD_AGE_MIN_YEARS = 0.0
_CHORD_AGE_MAX_YEARS = 17.999

# Project scope reminder: charter is right-sided. ADR-2605181060
# expects this gate to fire `unilateral_exception=true` because
# DFNB9 typically presents bilaterally.
_PROJECT_LATERALITY = "right"


# ── Output schema ────────────────────────────────────────────────────────────


class OtofAccessTier(str, Enum):
    """Three-tier access path declared in ADR-2605181060."""

    CHORD_JP_TRIAL = "chord_jp_trial"        # Tier 1 — trial enrollment
    PMDA_ROUTINE = "pmda_routine"            # Tier 2 — post-approval (future)
    PERSONAL_IMPORT = "personal_import"      # Tier 3 — deprecated
    NOT_APPLICABLE = "not_applicable"        # gate failed


class OtofRecommendation(str, Enum):
    DFNB9_TRIAL_ELIGIBLE = "dfnb9_trial_eligible"
    DFNB9_TRIAL_UNILATERAL_EXCEPTION = "dfnb9_trial_unilateral_exception"
    DFNB9_PEDIATRIC_AGE_WINDOW_CLOSED = "dfnb9_pediatric_age_window_closed"
    NOT_DFNB9 = "not_dfnb9"
    NOT_TESTED = "not_tested"


class OtofPlan(BaseModel):
    """V07 output. Returned in state under `otof_tx_plan`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation: OtofRecommendation
    access_tier: OtofAccessTier
    # Hard gate booleans (echoed for downstream V14 trial design).
    dfnb9_gate_passed: bool
    in_chord_age_window: bool
    unilateral_exception: bool
    # Patient-facing escalation switches mandated by ADR-2605181060.
    requires_sponsor_inquiry: bool = Field(
        ...,
        description=(
            "True when the CHORD JP site must be contacted for a "
            "per-case eligibility decision (typical for unilateral "
            "exceptions or borderline age)."
        ),
    )
    requires_ethics_committee: bool = Field(
        ...,
        description=(
            "True for any non-NOT_APPLICABLE recommendation — DFNB9 "
            "gene therapy enrollment requires home-institution ethics "
            "approval regardless of tier (ADR-2605181060)."
        ),
    )
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class OtofTxActor:
    """V07 — Otarmeni access path triage."""

    name = "V07_otof_tx"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        genetic = state.get("genetic_result") or {}
        phenotype = state.get("phenotype") or {}

        biallelic_otof = bool(genetic.get("biallelic_otof_pathogenic"))
        panel_run_id_present = bool(genetic.get("panel_run_id"))
        age_years = phenotype.get("age_years")
        side = phenotype.get("side")

        plan = OtofTxActor._triage(
            biallelic_otof_pathogenic=biallelic_otof,
            had_genetic_panel=panel_run_id_present
            or "verdicts" in (genetic or {}),
            age_years=(
                float(age_years) if isinstance(age_years, (int, float)) else None
            ),
            side=side if isinstance(side, str) else None,
        )
        return {
            "otof_tx_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _triage(
        *,
        biallelic_otof_pathogenic: bool,
        had_genetic_panel: bool,
        age_years: Optional[float],
        side: Optional[str],
    ) -> OtofPlan:
        # ── Gate 1: V02 must have run ──
        if not had_genetic_panel and not biallelic_otof_pathogenic:
            return OtofPlan(
                recommendation=OtofRecommendation.NOT_TESTED,
                access_tier=OtofAccessTier.NOT_APPLICABLE,
                dfnb9_gate_passed=False,
                in_chord_age_window=False,
                unilateral_exception=False,
                requires_sponsor_inquiry=False,
                requires_ethics_committee=False,
                rationale=(
                    "V02 hereditary deafness panel not yet run; DFNB9 status "
                    "unknown. Run V02 before V07 routing decision."
                ),
            )

        # ── Gate 2: biallelic OTOF pathogenic (ACMG 4-5) hard requirement ──
        if not biallelic_otof_pathogenic:
            return OtofPlan(
                recommendation=OtofRecommendation.NOT_DFNB9,
                access_tier=OtofAccessTier.NOT_APPLICABLE,
                dfnb9_gate_passed=False,
                in_chord_age_window=False,
                unilateral_exception=False,
                requires_sponsor_inquiry=False,
                requires_ethics_committee=False,
                rationale=(
                    "V02 did not confirm biallelic OTOF ACMG class 4-5; "
                    "Otarmeni access path is not applicable. Patient is "
                    "routed to substrate-class-appropriate alternatives "
                    "(V08 / V09 / V10 / V11) instead."
                ),
            )

        # Gate passed.
        in_age_window = (
            age_years is not None
            and _CHORD_AGE_MIN_YEARS <= age_years <= _CHORD_AGE_MAX_YEARS
        )
        unilateral = (
            isinstance(side, str) and side.lower() == _PROJECT_LATERALITY
        )

        # ── Gate 3: CHORD age window ──
        if not in_age_window:
            return OtofPlan(
                recommendation=OtofRecommendation.DFNB9_PEDIATRIC_AGE_WINDOW_CLOSED,
                access_tier=OtofAccessTier.PMDA_ROUTINE,
                dfnb9_gate_passed=True,
                in_chord_age_window=False,
                unilateral_exception=unilateral,
                requires_sponsor_inquiry=True,
                requires_ethics_committee=True,
                rationale=(
                    "DFNB9 confirmed but patient is outside the CHORD trial "
                    "pediatric age window. Tier 2 (PMDA routine) becomes "
                    "the realistic path once PMDA approves Otarmeni "
                    "(estimated 2027-2028 per ADR-2605181060)."
                ),
            )

        # ── Unilateral exception per ADR-2605181060 §片側性症例 ──
        if unilateral:
            return OtofPlan(
                recommendation=OtofRecommendation.DFNB9_TRIAL_UNILATERAL_EXCEPTION,
                access_tier=OtofAccessTier.CHORD_JP_TRIAL,
                dfnb9_gate_passed=True,
                in_chord_age_window=True,
                unilateral_exception=True,
                requires_sponsor_inquiry=True,
                requires_ethics_committee=True,
                rationale=(
                    "DFNB9 confirmed unilaterally — extremely rare case "
                    "per ADR-2605181060. CHORD trial inclusion criteria "
                    "typically require bilateral DFNB9; per-case decision "
                    "requires home-ethics + sponsor + Regeneron 3-way "
                    "review BEFORE enrollment can be considered."
                ),
            )

        # ── Standard Tier 1 path (bilateral DFNB9, pediatric) ──
        return OtofPlan(
            recommendation=OtofRecommendation.DFNB9_TRIAL_ELIGIBLE,
            access_tier=OtofAccessTier.CHORD_JP_TRIAL,
            dfnb9_gate_passed=True,
            in_chord_age_window=True,
            unilateral_exception=False,
            requires_sponsor_inquiry=True,
            requires_ethics_committee=True,
            rationale=(
                "DFNB9 confirmed + CHORD pediatric age window. Refer to "
                "CHORD JP site (NCT05788536) per ADR-2605181060 §Tier 1. "
                "Sponsor inquiry + home-ethics approval required."
            ),
        )
