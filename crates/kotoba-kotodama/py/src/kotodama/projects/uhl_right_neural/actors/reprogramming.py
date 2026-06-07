"""V09 ReprogrammingActor — in situ Ascl1 + Pou4f1 + Myt1l SGN reprogramming.

Charter Phase 3 of ADR-2605181000. Indicated when V06 substrate =
SGN_ABSENT_NERVE_PRESENT — the cochlear nerve fibres are still there
but the spiral ganglion neuron cell bodies are gone. The proposed
intervention is in situ polycistronic reprogramming via AAV: deliver
Ascl1 + Pou4f1 + Myt1l (the Vierbuchen / Wapinski neuronal trio) to
the Sox2+ supporting-cell population so they trans-differentiate into
new SGN.

**Research-stage, no preclinical IND today.** The actor's role is the
same shape as V08 — classify the patient as research-pipeline eligible
without recommending an intervention. The relevant external research
path is ADR-2605181050 §`optoci-de-trial` for the closest parallel
"new auditory neuron substrate" effort (Göttingen EKFZ OT optogenetic
CI), since SGN reprogramming as a clinical intervention is years
behind that work.

Rule cascade only. No LLM. Outputs:
  - recommendation ∈ {RESEARCH_TRACK_ELIGIBLE,
                       PRECLINICAL_ONLY,
                       SUBSTRATE_MISMATCH,
                       AGE_INELIGIBLE_ADULT_FIRST,
                       NOT_TESTED}
  - bridge_track ∈ {optoCI / ABI / eCI_fallback}
  - research_path_id: str | None
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .substrate_classifier import SubstrateClass


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# Charter §V09 + ADR-2605181050 §optoci-de-trial: the closest current
# research context (Göttingen / EKFZ OT optogenetic CI) is adult-first
# because the optical-implant safety profile in pediatrics is unknown.
# V09 itself is even more preclinical than V08; first-in-human is
# expected to follow optoCI by years and be adult-first.
_ADULT_FIRST_AGE_MIN_YEARS = 18.0


# ── Output schema ────────────────────────────────────────────────────────────


class ReprogrammingRecommendation(str, Enum):
    RESEARCH_TRACK_ELIGIBLE = "research_track_eligible"
    PRECLINICAL_ONLY = "preclinical_only"  # in-scope but no open IND
    SUBSTRATE_MISMATCH = "substrate_mismatch"
    AGE_INELIGIBLE_ADULT_FIRST = "age_ineligible_adult_first"
    NOT_TESTED = "not_tested"


class ReprogrammingBridgeTrack(str, Enum):
    """Today's auditory restoration option while the reprogramming
    pipeline matures."""

    OPTO_CI_DE_TRIAL = "opto_ci_de_trial"          # Göttingen path
    ABI_BRIDGE = "abi_bridge"                       # if nerve subsequently aplastic
    ECI_FALLBACK = "eci_fallback"                   # device only, accepts ceiling
    NONE_ASSIGNED = "none_assigned"


class ReprogrammingPlan(BaseModel):
    """V09 output. Returned in state under `reprogramming_plan`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation: ReprogrammingRecommendation
    primary_construct: str = Field(
        default="Ascl1+Pou4f1+Myt1l polycistronic, Sox2+ targeted",
        max_length=200,
        description=(
            "Canonical reprogramming cocktail from the Vierbuchen / "
            "Wapinski neuronal-trio literature. Informational only — "
            "the IND sponsor selects the actual construct."
        ),
    )
    bridge_track: ReprogrammingBridgeTrack
    research_path_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "ADR-2605181050 referral path id (`optoci-de-trial` is the "
            "closest contemporary trial; SGN reprogramming has no open "
            "first-in-human protocol today)."
        ),
    )
    preclinical_status: bool = Field(
        default=True,
        description=(
            "Constant True for v0.x. Flip to False when SGN reprogramming "
            "enters first-in-human."
        ),
    )
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class ReprogrammingActor:
    """V09 — in situ SGN reprogramming research-track triage."""

    name = "V09_reprogramming"

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

        plan = ReprogrammingActor._triage(
            substrate=substrate, age_years=age_f
        )
        return {
            "reprogramming_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _triage(
        *,
        substrate: Optional[SubstrateClass],
        age_years: Optional[float],
    ) -> ReprogrammingPlan:
        # ── Gate 1: substrate must be SGN_ABSENT_NERVE_PRESENT ──
        if substrate is None:
            return ReprogrammingPlan(
                recommendation=ReprogrammingRecommendation.NOT_TESTED,
                bridge_track=ReprogrammingBridgeTrack.NONE_ASSIGNED,
                research_path_id=None,
                rationale=(
                    "V06 substrate_decision missing; cannot classify "
                    "SGN-reprogramming research-track eligibility."
                ),
            )
        if substrate is not SubstrateClass.SGN_ABSENT_NERVE_PRESENT:
            return ReprogrammingPlan(
                recommendation=ReprogrammingRecommendation.SUBSTRATE_MISMATCH,
                bridge_track=ReprogrammingBridgeTrack.NONE_ASSIGNED,
                research_path_id=None,
                rationale=(
                    f"V06 substrate_class={substrate.value} does not match "
                    "the V09 indication (SGN_ABSENT_NERVE_PRESENT). "
                    "Reprogramming is indicated only when SGN cell bodies "
                    "are gone but the nerve fibres remain."
                ),
            )

        # ── Gate 2: adult-first first-in-human design ──
        if age_years is None:
            return ReprogrammingPlan(
                recommendation=ReprogrammingRecommendation.NOT_TESTED,
                bridge_track=ReprogrammingBridgeTrack.NONE_ASSIGNED,
                research_path_id=None,
                rationale=(
                    "V01 age missing — required for the adult-first "
                    "first-in-human classification."
                ),
            )

        adult = age_years >= _ADULT_FIRST_AGE_MIN_YEARS
        return ReprogrammingPlan(
            recommendation=(
                ReprogrammingRecommendation.RESEARCH_TRACK_ELIGIBLE
                if adult
                else ReprogrammingRecommendation.AGE_INELIGIBLE_ADULT_FIRST
            ),
            bridge_track=(
                ReprogrammingBridgeTrack.OPTO_CI_DE_TRIAL
                if adult
                else ReprogrammingBridgeTrack.ECI_FALLBACK
            ),
            research_path_id=(
                "optoci-de-trial"
                if adult
                else "sgn-regen-uk-research"
            ),
            rationale=(
                (
                    "Substrate match (SGN absent, nerve present) + adult "
                    "age window. SGN reprogramming has no open first-in-"
                    "human protocol today; the closest contemporary "
                    "research is Göttingen / EKFZ OT optogenetic CI "
                    "(ADR-2605181050 §optoci-de-trial). Register "
                    "patient with that research pipeline as a "
                    "substrate-matched contact."
                )
                if adult
                else (
                    f"Substrate match but age {age_years}y is below the "
                    "adult-first first-in-human cutoff for any current "
                    "SGN-substrate research. Bridge with eCI fallback "
                    "while the pipeline matures; register research "
                    "interest (SGN regen UK)."
                )
            ),
        )
