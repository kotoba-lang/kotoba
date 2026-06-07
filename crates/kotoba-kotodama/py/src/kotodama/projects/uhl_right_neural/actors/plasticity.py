"""V12 PlasticityActor — central plasticity age × critical-period gating.

Charter §V12: 中枢可塑性 is year-dependent. The auditory critical period
closes meaningfully around age 7 (Kral, Sharma — ~3.5-7y window for
cross-modal reorganization to consolidate). For unilateral congenital SNHL
the contralateral cortex carries the load until binaural input restoration,
and central plasticity defines the ceiling on what V13 (Bayesian outcome)
can plausibly predict.

This actor does NOT prescribe a training regimen — that is a P1 deliverable
where an LLM-assisted regimen builder is plugged in. P0 emits a phase gate
verdict (`passed` / `marginal` / `closed`) and an outcome-ceiling category
that V13 uses as a prior.

Per ADR-2605181000 §Ethical guardrail 6: V12 acts as a phase gate for the
downstream chain — `closed` does NOT halt the Pregel, but it carries an
explicit lower outcome ceiling into V13.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Age window table (clinician-reviewable in PR) ────────────────────────────

# Optimal binaural plasticity window upper bound (years).
_OPTIMAL_WINDOW_UPPER_YEARS = 3.5
# Window during which plasticity remains substantial but reduced.
_REDUCED_WINDOW_UPPER_YEARS = 7.0


# ── Output schema ────────────────────────────────────────────────────────────


class PhaseGate(str, Enum):
    """Plasticity phase gate verdict."""

    OPTIMAL = "optimal"  # < 3.5y — full plasticity window
    REDUCED = "reduced"  # 3.5-7y — substantial but reduced
    MARGINAL = "marginal"  # 7-12y — limited; case-by-case
    CLOSED = "closed"  # >= 12y — adult/late plasticity only


class OutcomeCeiling(str, Enum):
    """V13 prior: rough ceiling on attainable binaural outcomes."""

    HIGH = "high"  # near-normal binaural integration achievable
    MODERATE = "moderate"
    LIMITED = "limited"
    LATE_ADULT = "late_adult"  # adult-style accommodation only


class PlasticityPlan(BaseModel):
    """V12 output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    age_years: float = Field(..., ge=0.0, le=120.0)
    phase_gate: PhaseGate
    phase_gate_passed: bool = Field(
        ...,
        description="True iff phase_gate ∈ {OPTIMAL, REDUCED}. "
        "False does NOT halt the chain (charter §V12) — it sets a lower "
        "ceiling for V13.",
    )
    outcome_ceiling: OutcomeCeiling
    notes: list[str] = Field(default_factory=list)
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class PlasticityActor:
    """V12 — deterministic age × critical-period gate."""

    name = "V12_plasticity"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        phenotype = state.get("phenotype") or {}
        age_years = phenotype.get("age_years")
        if age_years is None:
            return {
                "plasticity_plan": {
                    "_absent": True,
                    "_reason": "V01 phenotype missing — V12 cannot apply age gate.",
                },
                "requires_human_review": True,
            }

        # V05 prognosis signal: CMV-positive UHL has higher contralateral
        # progression risk → slightly tighter age advisory.
        cmv_positive = bool((state.get("substrate_evidence") or {}).get("cmv_positive"))

        plan = PlasticityActor._gate(float(age_years), cmv_positive=cmv_positive)
        return {
            "plasticity_plan": plan.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _gate(age_years: float, cmv_positive: bool) -> PlasticityPlan:
        notes: list[str] = []

        if age_years < _OPTIMAL_WINDOW_UPPER_YEARS:
            phase = PhaseGate.OPTIMAL
            ceiling = OutcomeCeiling.HIGH
            rationale = (
                f"age {age_years}y < {_OPTIMAL_WINDOW_UPPER_YEARS}y → optimal "
                f"binaural plasticity window; high outcome ceiling."
            )
        elif age_years < _REDUCED_WINDOW_UPPER_YEARS:
            phase = PhaseGate.REDUCED
            ceiling = OutcomeCeiling.MODERATE
            rationale = (
                f"age {age_years}y in [{_OPTIMAL_WINDOW_UPPER_YEARS}, "
                f"{_REDUCED_WINDOW_UPPER_YEARS}) → reduced but substantial "
                f"plasticity; moderate ceiling."
            )
        elif age_years < 12.0:
            phase = PhaseGate.MARGINAL
            ceiling = OutcomeCeiling.LIMITED
            rationale = (
                f"age {age_years}y in [{_REDUCED_WINDOW_UPPER_YEARS}, 12) → "
                f"marginal plasticity; limited ceiling, case-by-case review."
            )
        else:
            phase = PhaseGate.CLOSED
            ceiling = OutcomeCeiling.LATE_ADULT
            rationale = (
                f"age {age_years}y ≥ 12y → critical period closed; "
                f"adult/late accommodation only."
            )

        if cmv_positive:
            notes.append(
                "V05 CMV-positive: heightened contralateral progression risk; "
                "audiologic surveillance of the unaffected ear is indicated."
            )

        return PlasticityPlan(
            age_years=age_years,
            phase_gate=phase,
            phase_gate_passed=phase in (PhaseGate.OPTIMAL, PhaseGate.REDUCED),
            outcome_ceiling=ceiling,
            notes=notes,
            rationale=rationale,
        )
