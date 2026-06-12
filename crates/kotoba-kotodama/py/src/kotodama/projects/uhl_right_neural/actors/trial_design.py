"""V14 TrialDesignActor — Clinical trial design and sample size parameters.

Authoritative per ADR-2605181000 §V14. Consumes the chosen treatment plan
and the expected outcomes, mapping them to a clinical trial design
strategy (e.g., adaptive single-arm, Bayesian futility, RCT).

Decision support only. Every output is strictly a recommendation.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Output schema ────────────────────────────────────────────────────────────


class TrialPhase(str, Enum):
    """Clinical trial phase mapping."""

    PHASE_1_2A = "phase_1_2a_safety_and_dose"
    PHASE_2B = "phase_2b_efficacy"
    PHASE_3 = "phase_3_pivotal_rct"
    POST_MARKET_REGISTRY = "post_market_registry"
    COMPASSIONATE_USE = "compassionate_use_expanded_access"
    NOT_APPLICABLE = "trial_not_applicable"


class TrialDesignType(str, Enum):
    """Statistical design pattern."""

    ADAPTIVE_SINGLE_ARM = "adaptive_single_arm"
    BAYESIAN_FUTILITY = "bayesian_futility_stopping"
    DOUBLE_BLIND_RCT = "double_blind_rct"
    OPEN_LABEL_OBSERVATIONAL = "open_label_observational"


class TrialProtocol(BaseModel):
    """V14 actor output payload: The recommended trial protocol schema."""

    model_config = ConfigDict(extra="forbid")

    phase: TrialPhase = Field(
        description="Estimated clinical trial phase."
    )
    design_type: TrialDesignType = Field(
        description="Recommended statistical design pattern."
    )
    estimated_n: int = Field(
        description="Estimated target sample size (N)."
    )
    primary_endpoint: str = Field(
        description="Primary endpoint for the trial (e.g., 'Speech-in-noise score improvement at 12M')."
    )
    unilateral_specific: bool = Field(
        default=False,
        description="Whether the design requires specific adaptations for unilateral hearing loss."
    )
    rationale: str = Field(
        description="Reasoning behind the trial design recommendation."
    )
    requires_human_review: bool = Field(
        default=True,
        description="Always true for medical research protocols."
    )


# ── Actor ────────────────────────────────────────────────────────────────────


class TrialDesignActor:
    """Implements V14: Maps treatment path to trial design."""

    def compute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Pregel node entrypoint."""
        
        # 1. Determine active treatment from state
        treatment_type = "unknown"
        if state.get("otof_tx_plan"):
            treatment_type = "otof"
        elif state.get("abi_plan"):
            treatment_type = "abi"
        elif state.get("neurotrophin_plan"):
            treatment_type = "neurotrophin"
        elif state.get("reprogramming_plan"):
            treatment_type = "reprogramming"
        elif state.get("device_plan"):
            treatment_type = "device"

        # 2. Extract outcome expectations (optional)
        outcome_post = state.get("outcome_posterior", {})
        
        # 3. Rule-based trial mapping
        phase = TrialPhase.NOT_APPLICABLE
        design = TrialDesignType.OPEN_LABEL_OBSERVATIONAL
        n_size = 0
        endpoint = "General safety and feasibility"
        unilateral = True
        rationale = "Default fallback pathway."

        if treatment_type == "otof":
            # OTOF Gene Therapy (Otarmeni/CHORD pathway)
            phase = TrialPhase.PHASE_1_2A
            design = TrialDesignType.ADAPTIVE_SINGLE_ARM
            n_size = 12
            endpoint = "ABR threshold improvement and safety at 6 months"
            rationale = "Gene therapy for UHL is early stage; single-arm adaptive design is standard for Phase 1/2a to establish dose safety."
        
        elif treatment_type == "abi":
            # Auditory Brainstem Implant
            phase = TrialPhase.POST_MARKET_REGISTRY
            design = TrialDesignType.OPEN_LABEL_OBSERVATIONAL
            n_size = 50
            endpoint = "CAP / EABR response and spatial hearing validation"
            rationale = "ABI is established but use in UHL-R congenital cases requires registry tracking."
            
        elif treatment_type == "device":
            # eCI (Cochlear Implant)
            phase = TrialPhase.POST_MARKET_REGISTRY
            design = TrialDesignType.OPEN_LABEL_OBSERVATIONAL
            n_size = 100
            endpoint = "Speech-in-noise (SIN) and sound localization"
            rationale = "Cochlear implants for unilateral hearing loss are increasingly standard; tracking requires post-market observational data."

        elif treatment_type == "neurotrophin" or treatment_type == "reprogramming":
            phase = TrialPhase.PHASE_1_2A
            design = TrialDesignType.BAYESIAN_FUTILITY
            n_size = 15
            endpoint = "Neural survival (imaging) and eABR thresholds"
            rationale = "Experimental biologic interventions require stringent safety and futility boundaries."

        protocol = TrialProtocol(
            phase=phase,
            design_type=design,
            estimated_n=n_size,
            primary_endpoint=endpoint,
            unilateral_specific=unilateral,
            rationale=rationale,
            requires_human_review=True,
        )

        return {"trial_protocol": protocol.model_dump(mode="json")}
