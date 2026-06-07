"""V11 AbiActor — Auditory Brainstem Implant candidacy.

Authoritative per ADR-2605181000 §V11 and ADR-2605181050 §`abi-uk-nhs-paediatric`.
ABI is the only restoration option when V06 substrate_classifier =
NERVE_APLASIA (cochlear nerve absent on IAC imaging). The actor decides
whether the patient meets the Manchester / GSTT pediatric-ABI inclusion
window — purely a triage; the surgical decision lives with the receiving
MDT.

No LLM. Rule cascade over V03 imaging (cn_fiber_count, iac_stenosis),
V01 phenotype (age), V06 substrate_decision, plus optional CNS-comorbidity
flags from the upstream state. Every output carries
requires_human_review = True.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .substrate_classifier import SubstrateClass


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# Manchester / GSTT pediatric ABI age windows (ADR-2605181050).
# Surgery typically performed under age 5 for cortical plasticity reasons;
# referrals accepted up to 12y for considered selection.
_ABI_OPTIMAL_AGE_MAX_YEARS = 5.0
_ABI_REFERRAL_AGE_MAX_YEARS = 12.0

# Cochlear-nerve fiber count threshold below which ABI becomes the only
# option (per V06 NERVE_APLASIA rule).
_ABI_HARD_GATE_CN_FIBER_COUNT = 0


# ── Output schema ────────────────────────────────────────────────────────────


class AbiCandidacy(str, Enum):
    """Triage verdict for an ABI referral."""

    OPTIMAL = "optimal"              # Within optimal age + substrate
    SUBOPTIMAL_AGE = "suboptimal_age"  # Substrate fits but age past optimal window
    INELIGIBLE_AGE = "ineligible_age"  # Past referral age ceiling
    INELIGIBLE_SUBSTRATE = "ineligible_substrate"  # Not NERVE_APLASIA — ABI not indicated
    INELIGIBLE_CNS_COMORBIDITY = "ineligible_cns_comorbidity"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AbiCenterPreference(str, Enum):
    """Receiving centre preferences declared in ADR-2605181050."""

    MANCHESTER_UNIVERSITY_NHS = "manchester_university_nhs"
    GUYS_AND_ST_THOMAS_NHS = "guys_and_st_thomas_nhs"
    DOMESTIC_FUKUSHIMA_OR_NIPPON_MED = "domestic_fukushima_or_nippon_med_for_followup"
    UNRESOLVED = "unresolved"


class AbiPlan(BaseModel):
    """V11 output. Returned in state under `abi_plan`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidacy: AbiCandidacy
    surgical_center_preference: AbiCenterPreference
    ineligibility_reasons: list[str] = Field(default_factory=list)
    # Patient-burden + pathway flags (ADR-2605181050 §Burden disclosure).
    burden_disclosure_required: bool = True
    domestic_followup_required: bool = True
    referral_ethics_review_required: bool = True
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class AbiActor:
    """V11 — pediatric ABI candidacy triage."""

    name = "V11_abi"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        substrate_raw = (state.get("substrate_decision") or {}).get(
            "substrate_class"
        )
        evidence = state.get("substrate_evidence") or {}
        phenotype = state.get("phenotype") or {}
        imaging = state.get("imaging_result") or {}

        try:
            substrate = (
                SubstrateClass(substrate_raw) if substrate_raw else None
            )
        except ValueError:
            substrate = None

        age_years = phenotype.get("age_years")
        age_f = float(age_years) if isinstance(age_years, (int, float)) else None
        cn_fiber_count = evidence.get("cn_fiber_count")
        if cn_fiber_count is None and "cn_fiber_count" in imaging:
            cn_fiber_count = imaging.get("cn_fiber_count")
        cns_comorbidity = bool(phenotype.get("cns_comorbidity"))

        plan = AbiActor._triage(
            substrate=substrate,
            age_years=age_f,
            cn_fiber_count=(
                int(cn_fiber_count)
                if isinstance(cn_fiber_count, (int, float))
                else None
            ),
            cns_comorbidity=cns_comorbidity,
        )
        return {
            "abi_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _triage(
        *,
        substrate: Optional[SubstrateClass],
        age_years: Optional[float],
        cn_fiber_count: Optional[int],
        cns_comorbidity: bool,
    ) -> AbiPlan:
        # ── Gate 1: substrate must be NERVE_APLASIA ──
        if substrate is not None and substrate is not SubstrateClass.NERVE_APLASIA:
            return AbiPlan(
                candidacy=AbiCandidacy.INELIGIBLE_SUBSTRATE,
                surgical_center_preference=AbiCenterPreference.UNRESOLVED,
                ineligibility_reasons=[
                    f"V06 substrate_class={substrate.value} is not "
                    "NERVE_APLASIA. ABI bypasses the cochlear nerve and "
                    "is only indicated when the nerve is absent."
                ],
                rationale=(
                    "Substrate is not nerve aplasia; CI / gene therapy / "
                    "neurotrophin tracks are the appropriate options. "
                    "ABI is not indicated."
                ),
            )

        if substrate is None and cn_fiber_count != _ABI_HARD_GATE_CN_FIBER_COUNT:
            return AbiPlan(
                candidacy=AbiCandidacy.REQUIRES_HUMAN_REVIEW,
                surgical_center_preference=AbiCenterPreference.UNRESOLVED,
                ineligibility_reasons=[
                    "V06 substrate_decision not present and "
                    "cn_fiber_count != 0; cannot confirm nerve aplasia."
                ],
                rationale=(
                    "Run V03 imaging + V06 substrate classifier before "
                    "ABI triage. Insufficient evidence for a deterministic "
                    "candidacy verdict."
                ),
            )

        # ── Gate 2: CNS comorbidity hard exclusion ──
        if cns_comorbidity:
            return AbiPlan(
                candidacy=AbiCandidacy.INELIGIBLE_CNS_COMORBIDITY,
                surgical_center_preference=AbiCenterPreference.UNRESOLVED,
                ineligibility_reasons=[
                    "CNS comorbidity (autism spectrum / multi-disability) "
                    "flagged on phenotype. Receiving centres' standard "
                    "selection rules typically exclude — case-by-case "
                    "MDT review only."
                ],
                rationale=(
                    "CNS comorbidity is a relative contraindication for "
                    "pediatric ABI at Manchester / GSTT per their "
                    "published criteria. Refer to MDT for individualised "
                    "review before further pathway commitment."
                ),
            )

        # ── Gate 3: age window ──
        if age_years is None:
            return AbiPlan(
                candidacy=AbiCandidacy.REQUIRES_HUMAN_REVIEW,
                surgical_center_preference=AbiCenterPreference.UNRESOLVED,
                ineligibility_reasons=["V01 age_years missing."],
                rationale=(
                    "V01 phenotype missing age — cannot evaluate the "
                    "ABI age window."
                ),
            )

        if age_years > _ABI_REFERRAL_AGE_MAX_YEARS:
            return AbiPlan(
                candidacy=AbiCandidacy.INELIGIBLE_AGE,
                surgical_center_preference=AbiCenterPreference.UNRESOLVED,
                ineligibility_reasons=[
                    f"Age {age_years}y exceeds the standard pediatric "
                    f"referral ceiling ({_ABI_REFERRAL_AGE_MAX_YEARS}y) "
                    "at Manchester / GSTT."
                ],
                rationale=(
                    "Adolescent / adult ABI is performed elsewhere on a "
                    "compassionate basis but is not the project's primary "
                    "referral path. Domestic ABI centres (福島県立医大 / "
                    "日本医大) accept adult cases — escalate manually."
                ),
            )

        if age_years > _ABI_OPTIMAL_AGE_MAX_YEARS:
            return AbiPlan(
                candidacy=AbiCandidacy.SUBOPTIMAL_AGE,
                surgical_center_preference=(
                    AbiCenterPreference.MANCHESTER_UNIVERSITY_NHS
                ),
                ineligibility_reasons=[],
                rationale=(
                    f"Age {age_years}y is past the optimal cortical-"
                    "plasticity window (≤5y) but within the referral "
                    f"ceiling (≤{_ABI_REFERRAL_AGE_MAX_YEARS}y). Manchester "
                    "accepts considered referrals up to 12y; expected "
                    "outcome ceiling is lower than infant cases."
                ),
            )

        # Optimal window.
        return AbiPlan(
            candidacy=AbiCandidacy.OPTIMAL,
            surgical_center_preference=AbiCenterPreference.MANCHESTER_UNIVERSITY_NHS,
            ineligibility_reasons=[],
            rationale=(
                f"Age {age_years}y within the optimal pediatric window "
                f"(≤{_ABI_OPTIMAL_AGE_MAX_YEARS}y) and substrate = "
                "nerve aplasia. Refer to Manchester or GSTT per "
                "ADR-2605181050. Domestic follow-up + ethics + burden "
                "disclosure all required."
            ),
        )
