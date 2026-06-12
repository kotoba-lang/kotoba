"""V10 ConventionalDeviceActor — electrical CI fitting recommendation.

Charter §15-actor fleet groups V10a (eCI) and V11 (ABI) under one actor file;
this P0 implementation covers V10a only. V11 ABI candidacy is the P1
deliverable per the phase plan, and remains a stub in pregel.py until then.
V10b optoCI is P3.

The actor consumes (a) the V06 substrate_decision (which routes here) and
(b) the patient phenotype/age from V01. It emits a recommended electrode
mapping strategy, an initial T-/C-level seed, and a fitting cadence — all
clinical-rule based. No LLM in P0.

Note: this is decision support. The actual programming session is performed
by an audiologist; the V10 output is one input among many.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .substrate_classifier import SubstrateClass


# ── Constants (clinician-reviewable in PR) ───────────────────────────────────

# Pediatric initial T-level seed (current units, CL). Conservative default
# for first activation; refined session-by-session by the audiologist.
_PEDIATRIC_T_LEVEL_INITIAL_CL = 100
# Pediatric initial C-level seed.
_PEDIATRIC_C_LEVEL_INITIAL_CL = 180
# Adult initial T-level seed.
_ADULT_T_LEVEL_INITIAL_CL = 120
# Adult initial C-level seed.
_ADULT_C_LEVEL_INITIAL_CL = 210
# Age cutoff (years) between pediatric and adult seeds.
_PEDIATRIC_AGE_CUTOFF_YEARS = 18.0


# ── Output schema ────────────────────────────────────────────────────────────


class CodingStrategy(str, Enum):
    """CI speech coding strategy seeds (manufacturer-agnostic naming)."""

    CIS = "CIS"  # Continuous Interleaved Sampling — universal baseline
    ACE = "ACE"  # Advanced Combination Encoder — Cochlear default
    HIRES = "HIRES"  # HiResolution — Advanced Bionics default
    FSP = "FSP"  # Fine Structure Processing — MED-EL default


class FittingCadence(str, Enum):
    """Initial mapping follow-up cadence."""

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class DeviceRecommendation(str, Enum):
    """Top-level device recommendation."""

    ECI = "electrical_ci"            # standard eCI (V10a P0)
    ECI_WITH_NEUROTROPHIN_TRACK = "eci_with_neurotrophin_track"  # SGN_DEGENERATING → V08 parallel
    DEFER_PENDING_V11 = "defer_pending_v11_abi_eval"  # NERVE_APLASIA — ABI is the device
    DEFER_PENDING_V09 = "defer_pending_v09_reprogramming"  # SGN_ABSENT_NERVE_PRESENT — optoCI/reprog
    DEFER_HUMAN_REVIEW = "defer_human_review"  # INDETERMINATE


class DevicePlan(BaseModel):
    """V10 output. `recommendation` may also indicate a defer-to-other-vertex."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation: DeviceRecommendation
    coding_strategy_seed: Optional[CodingStrategy] = None
    t_level_initial_cl: Optional[int] = Field(default=None, ge=0, le=400)
    c_level_initial_cl: Optional[int] = Field(default=None, ge=0, le=400)
    fitting_cadence: Optional[FittingCadence] = None
    sessions_first_3_months: Optional[int] = Field(default=None, ge=0, le=20)
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class ConventionalDeviceActor:
    """V10 — deterministic eCI fitting recommendation (P0 scope: V10a only)."""

    name = "V10_device_fitting"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        substrate_raw = state.get("substrate_decision") or {}
        phenotype_raw = state.get("phenotype") or {}

        substrate_class_raw = substrate_raw.get("substrate_class")
        age_years = phenotype_raw.get("age_years")

        plan = ConventionalDeviceActor._plan(substrate_class_raw, age_years)
        return {
            "device_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _plan(
        substrate_class_raw: Optional[str],
        age_years: Optional[float],
    ) -> DevicePlan:
        if not substrate_class_raw:
            return DevicePlan(
                recommendation=DeviceRecommendation.DEFER_HUMAN_REVIEW,
                rationale="V06 substrate_decision absent; cannot recommend device.",
            )

        try:
            klass = SubstrateClass(substrate_class_raw)
        except ValueError:
            return DevicePlan(
                recommendation=DeviceRecommendation.DEFER_HUMAN_REVIEW,
                rationale=f"Unknown substrate_class={substrate_class_raw}; defer.",
            )

        # Branch routing per V06 substrate class.
        if klass is SubstrateClass.NERVE_APLASIA:
            return DevicePlan(
                recommendation=DeviceRecommendation.DEFER_PENDING_V11,
                rationale="Nerve aplasia → eCI ineffective; route to V11 ABI candidacy.",
            )
        if klass is SubstrateClass.SGN_ABSENT_NERVE_PRESENT:
            return DevicePlan(
                recommendation=DeviceRecommendation.DEFER_PENDING_V09,
                rationale="SGN absent + nerve present → eCI sub-optimal; "
                "V09 reprog / V10b optoCI track preferred (P3 deliverable).",
            )
        if klass is SubstrateClass.INDETERMINATE:
            return DevicePlan(
                recommendation=DeviceRecommendation.DEFER_HUMAN_REVIEW,
                rationale="V06 INDETERMINATE; re-acquire evidence before V10 fitting.",
            )

        # Two remaining classes get a real eCI fitting plan.
        is_pediatric = (
            age_years is not None and age_years < _PEDIATRIC_AGE_CUTOFF_YEARS
        )
        t_seed = (
            _PEDIATRIC_T_LEVEL_INITIAL_CL
            if is_pediatric
            else _ADULT_T_LEVEL_INITIAL_CL
        )
        c_seed = (
            _PEDIATRIC_C_LEVEL_INITIAL_CL
            if is_pediatric
            else _ADULT_C_LEVEL_INITIAL_CL
        )
        cadence = FittingCadence.WEEKLY if is_pediatric else FittingCadence.BIWEEKLY
        sessions = 8 if is_pediatric else 5

        if klass is SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT:
            recommendation = DeviceRecommendation.ECI_WITH_NEUROTROPHIN_TRACK
            rationale = (
                "SGN degenerating + nerve present → eCI with V08 neurotrophin "
                "preservation track in parallel (P2 deliverable for V08; "
                "eCI fitting proceeds now). CIS for conservative baseline."
            )
            strategy = CodingStrategy.CIS
        else:  # SGN_PRESENT_HC_LOSS
            recommendation = DeviceRecommendation.ECI
            rationale = (
                "SGN present + hair-cell loss → standard eCI candidate. "
                "Manufacturer-default strategy seed (ACE/HIRES/FSP); CIS used "
                "as the cross-manufacturer fallback in this output."
            )
            strategy = CodingStrategy.CIS

        return DevicePlan(
            recommendation=recommendation,
            coding_strategy_seed=strategy,
            t_level_initial_cl=t_seed,
            c_level_initial_cl=c_seed,
            fitting_cadence=cadence,
            sessions_first_3_months=sessions,
            rationale=rationale,
        )
