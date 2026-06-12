"""V08 NeurotrophinActor — AAV-BDNF / NT-3 SGN preservation triage.

Charter Phase 2 of ADR-2605181000. Indicated when V06 substrate =
SGN_DEGENERATING_NERVE_PRESENT — the spiral ganglion neurons are
present-but-dying and a single intracochlear AAV dose of a
neurotrophin (BDNF or NT-3) may slow / halt the degeneration before
the eCI fitting (V10) loses its substrate.

**Preclinical, no human treatment available today.** The actor's job
is honest triage: classify the patient as research-eligible vs not,
register interest in the appropriate research path (ADR-2605181050
§`sgn-regen-uk-research` is the closest current registry), and surface
that we are NOT recommending an intervention — we are flagging a case
for future eligibility once an IND opens.

Rule cascade only. No LLM. Outputs:
  - recommendation ∈ {RESEARCH_TRACK_ELIGIBLE,
                       PRECLINICAL_ONLY,
                       SUBSTRATE_MISMATCH,
                       AGE_INELIGIBLE_PEDIATRIC_FIRST,
                       NOT_TESTED}
  - parallel_eci_track: bool — V10 eCI fitting can / should run in parallel
  - dosing_nomogram_reference: str — pointer to charter Table §15-actor
  - research_path_id: str | None — ADR-2605181050 reference if applicable

Per project ethical guardrail, every output carries
requires_human_review = True + indicates the preclinical status.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .substrate_classifier import SubstrateClass


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# Pediatric-first IND-enabling design (charter §V08): first-in-human
# is expected to start in pediatric subjects ≥ 1y to align with the
# CHORD trial precedent. Adults are not excluded but are not the
# primary cohort.
_PEDIATRIC_INDEX_AGE_MIN_YEARS = 1.0
_PEDIATRIC_INDEX_AGE_MAX_YEARS = 17.999


# ── Output schema ────────────────────────────────────────────────────────────


class NeurotrophinRecommendation(str, Enum):
    RESEARCH_TRACK_ELIGIBLE = "research_track_eligible"
    PRECLINICAL_ONLY = "preclinical_only"  # in-scope but no open IND yet
    SUBSTRATE_MISMATCH = "substrate_mismatch"
    AGE_INELIGIBLE_PEDIATRIC_FIRST = "age_ineligible_pediatric_first"
    NOT_TESTED = "not_tested"


class NeurotrophinConstruct(str, Enum):
    AAV_BDNF = "aav_bdnf"
    AAV_NT3 = "aav_nt3"
    UNDETERMINED = "undetermined"


class NeurotrophinPlan(BaseModel):
    """V08 output. Returned in state under `neurotrophin_plan`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation: NeurotrophinRecommendation
    primary_construct: NeurotrophinConstruct
    parallel_eci_track: bool = Field(
        ...,
        description=(
            "True when V10 eCI fitting can safely proceed in parallel — "
            "the preclinical neurotrophin preserve track does not block "
            "device implantation, it tries to keep the SGN substrate "
            "alive that the device depends on."
        ),
    )
    dosing_nomogram_reference: str = Field(
        ...,
        max_length=200,
        description=(
            "Pointer to the charter Table §V08 dosing nomogram — "
            "informational only; the actual dose is set by the IND "
            "sponsor when an IND opens."
        ),
    )
    research_path_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "ADR-2605181050 referral path id (e.g. `sgn-regen-uk-research`) "
            "the patient can register with as a research-pipeline contact."
        ),
    )
    preclinical_status: bool = Field(
        default=True,
        description=(
            "Constant True for v0.x. Flip to False when the first IND "
            "opens and the actor recommendation becomes a treatment "
            "decision rather than a research-track classification."
        ),
    )
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class NeurotrophinActor:
    """V08 — AAV-BDNF / NT-3 research-track triage."""

    name = "V08_neurotrophin"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        substrate_raw = (state.get("substrate_decision") or {}).get(
            "substrate_class"
        )
        try:
            substrate = (
                SubstrateClass(substrate_raw) if substrate_raw else None
            )
        except ValueError:
            substrate = None

        phenotype = state.get("phenotype") or {}
        age_years = phenotype.get("age_years")
        age_f = float(age_years) if isinstance(age_years, (int, float)) else None

        plan = NeurotrophinActor._triage(substrate=substrate, age_years=age_f)
        return {
            "neurotrophin_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _triage(
        *,
        substrate: Optional[SubstrateClass],
        age_years: Optional[float],
    ) -> NeurotrophinPlan:
        # ── Gate 1: substrate must be SGN_DEGENERATING_NERVE_PRESENT ──
        if substrate is None:
            return NeurotrophinPlan(
                recommendation=NeurotrophinRecommendation.NOT_TESTED,
                primary_construct=NeurotrophinConstruct.UNDETERMINED,
                parallel_eci_track=False,
                dosing_nomogram_reference="charter §V08 (pending V06)",
                research_path_id=None,
                rationale=(
                    "V06 substrate_decision missing; cannot classify "
                    "neurotrophin research-track eligibility."
                ),
            )

        if substrate is not SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT:
            return NeurotrophinPlan(
                recommendation=NeurotrophinRecommendation.SUBSTRATE_MISMATCH,
                primary_construct=NeurotrophinConstruct.UNDETERMINED,
                parallel_eci_track=False,
                dosing_nomogram_reference="N/A — substrate mismatch",
                research_path_id=None,
                rationale=(
                    f"V06 substrate_class={substrate.value} does not match "
                    "the V08 indication (SGN_DEGENERATING_NERVE_PRESENT). "
                    "Neurotrophin preserve is indicated only when SGN are "
                    "present-but-dying — different substrate classes route "
                    "to different vertices."
                ),
            )

        # ── Gate 2: pediatric-first IND-enabling design ──
        if age_years is None:
            return NeurotrophinPlan(
                recommendation=NeurotrophinRecommendation.NOT_TESTED,
                primary_construct=NeurotrophinConstruct.UNDETERMINED,
                parallel_eci_track=True,
                dosing_nomogram_reference="charter §V08 (pending V01 age)",
                research_path_id=None,
                rationale=(
                    "V01 age missing — required for the pediatric-first "
                    "research-track classification."
                ),
            )

        # Adults are not excluded from the long-term plan, but the
        # first IND-enabling design is pediatric. We don't gate adults
        # out, we just flag them.
        in_pediatric_window = (
            _PEDIATRIC_INDEX_AGE_MIN_YEARS
            <= age_years
            <= _PEDIATRIC_INDEX_AGE_MAX_YEARS
        )

        # Default construct: BDNF is the more established candidate
        # for SGN preservation. NT-3 is the alternative; the IND
        # sponsor picks. Surface as UNDETERMINED so the actor doesn't
        # appear to recommend a molecule that isn't approved.
        return NeurotrophinPlan(
            recommendation=(
                NeurotrophinRecommendation.RESEARCH_TRACK_ELIGIBLE
                if in_pediatric_window
                else NeurotrophinRecommendation.PRECLINICAL_ONLY
            ),
            primary_construct=NeurotrophinConstruct.UNDETERMINED,
            parallel_eci_track=True,
            dosing_nomogram_reference="charter §V08 (BDNF / NT-3 AAV dosing nomogram, IND-enabling)",
            research_path_id="sgn-regen-uk-research",
            rationale=(
                (
                    "Substrate match (SGN degenerating + nerve present) + "
                    "pediatric age window — register patient with the SGN "
                    "regen / neurotrophin research pipeline. No open IND "
                    "today; eCI fitting (V10) proceeds in parallel to "
                    "preserve auditory function while the substrate-rescue "
                    "track matures."
                )
                if in_pediatric_window
                else (
                    f"Substrate match but age {age_years}y is outside the "
                    "pediatric-first IND-enabling window. Patient is "
                    "preclinically of-interest; register research contact "
                    "but no current trial is recruiting in this age band."
                )
            ),
        )
