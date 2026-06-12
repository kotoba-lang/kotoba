"""V06 SubstrateClassifierActor — 4-way neural-substrate classifier (DMN).

Architectural hinge per ADR-2605181000. Consumes V02 (genetic), V03 (IAC-MRI),
V04 (electrophys), V05 (CMV/TORCH) via the V01-V05 fan-in, and emits one of
four substrate classes used to branch into V07-V11.

The decision table is documented in `../dmn/substrate_classifier.md` and
mirrored here in code as a deterministic rule cascade. The DMN doc is the
authoritative review surface; this file is the runtime implementation.

P0 MVP note: V02-V05 actors are stubs in pregel.py for this scaffold. The
classifier consumes whatever evidence is present; absent evidence widens
the uncertainty band. Full evidence-fusion is a P1 deliverable.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Evidence inputs (subset implemented in P0) ───────────────────────────────


class SubstrateEvidence(BaseModel):
    """Fan-in evidence consumed by V06. None = signal not available."""

    model_config = ConfigDict(extra="forbid")

    # From V03 (imaging.ImagingActor) — internal auditory canal MRI
    cn_fiber_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        description="Cochlear nerve fiber strands on CISS/FIESTA "
        "(0=aplasia, 1-2=severe hypoplasia, 3-4=normal-ish).",
    )

    # From V04 (electrophys.ElectrophysActor)
    eabr_present: Optional[bool] = Field(
        default=None,
        description="Electrically-evoked ABR present (i.e. SGN responsive).",
    )
    eabr_latency_prolonged: Optional[bool] = Field(default=None)
    dpoae_present: Optional[bool] = Field(
        default=None,
        description="Distortion product OAE — outer hair cell function proxy.",
    )

    # From V02 (genetic_screen.GeneticScreenActor)
    biallelic_otof_pathogenic: Optional[bool] = Field(
        default=None,
        description="ACMG class 4-5 biallelic OTOF (gates ADR-2605181060 access).",
    )

    # From V05 (cmv_torch.CmvTorchActor) — informational, does not branch V06
    cmv_positive: Optional[bool] = Field(default=None)


# ── Output ───────────────────────────────────────────────────────────────────


class SubstrateClass(str, Enum):
    """4-way branch for V07-V11 routing."""

    SGN_PRESENT_HC_LOSS = "sgn_present_hc_loss"
    SGN_DEGENERATING_NERVE_PRESENT = "sgn_degenerating_nerve_present"
    SGN_ABSENT_NERVE_PRESENT = "sgn_absent_nerve_present"
    NERVE_APLASIA = "nerve_aplasia"
    INDETERMINATE = "indeterminate"


_BRANCH_TO_DOWNSTREAM: dict[SubstrateClass, list[str]] = {
    SubstrateClass.SGN_PRESENT_HC_LOSS: ["V07_otof_tx_if_dfnb9", "V10_eci"],
    SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT: ["V08_neurotrophin", "V10_eci"],
    SubstrateClass.SGN_ABSENT_NERVE_PRESENT: ["V09_reprogramming", "V10_opto_ci"],
    SubstrateClass.NERVE_APLASIA: ["V11_abi"],
    SubstrateClass.INDETERMINATE: [],
}


class SubstrateDecision(BaseModel):
    """V06 output. `downstream_vertices` is consumed by Pregel branch routing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate_class: SubstrateClass
    downstream_vertices: list[str]
    confidence: Literal["high", "medium", "low"]
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class SubstrateClassifierActor:
    """V06 — deterministic 4-way classifier (DMN rule cascade).

    Cascade order (first match wins) — see dmn/substrate_classifier.md:
      1. cn_fiber_count == 0                          → NERVE_APLASIA (high)
      2. eabr_present == False AND cn_fiber_count ∈ {1,2}
                                                      → SGN_ABSENT_NERVE_PRESENT (medium)
      3. eabr_present == True AND eabr_latency_prolonged == True AND cn_fiber_count >= 2
                                                      → SGN_DEGENERATING_NERVE_PRESENT (medium)
      4. eabr_present == True AND dpoae_present == False AND cn_fiber_count >= 3
                                                      → SGN_PRESENT_HC_LOSS (high)
      5. otherwise                                    → INDETERMINATE (low)
    """

    name = "V06_substrate_classifier"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("substrate_evidence", {}) or {}
        ev = SubstrateEvidence.model_validate(raw)
        decision = SubstrateClassifierActor._classify(ev)
        return {
            "substrate_decision": decision.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _classify(ev: SubstrateEvidence) -> SubstrateDecision:
        # Rule 1 — nerve aplasia
        if ev.cn_fiber_count == 0:
            return SubstrateDecision(
                substrate_class=SubstrateClass.NERVE_APLASIA,
                downstream_vertices=_BRANCH_TO_DOWNSTREAM[SubstrateClass.NERVE_APLASIA],
                confidence="high",
                rationale="cn_fiber_count=0 → cochlear nerve aplasia; "
                "ABI (V11) only current option.",
            )

        # Rule 2 — SGN absent, nerve present
        if (
            ev.eabr_present is False
            and ev.cn_fiber_count is not None
            and ev.cn_fiber_count in (1, 2)
        ):
            return SubstrateDecision(
                substrate_class=SubstrateClass.SGN_ABSENT_NERVE_PRESENT,
                downstream_vertices=_BRANCH_TO_DOWNSTREAM[
                    SubstrateClass.SGN_ABSENT_NERVE_PRESENT
                ],
                confidence="medium",
                rationale="eABR absent + nerve fiber 1-2 → SGN absent/severely "
                "reduced with nerve substrate; reprog (V09) / optoCI (V10b) tracks.",
            )

        # Rule 3 — SGN degenerating, nerve present
        if (
            ev.eabr_present is True
            and ev.eabr_latency_prolonged is True
            and ev.cn_fiber_count is not None
            and ev.cn_fiber_count >= 2
        ):
            return SubstrateDecision(
                substrate_class=SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT,
                downstream_vertices=_BRANCH_TO_DOWNSTREAM[
                    SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT
                ],
                confidence="medium",
                rationale="eABR present but prolonged + nerve OK → SGN "
                "degenerating; neurotrophin preserve (V08) + eCI (V10).",
            )

        # Rule 4 — SGN present, hair-cell loss only
        if (
            ev.eabr_present is True
            and ev.dpoae_present is False
            and ev.cn_fiber_count is not None
            and ev.cn_fiber_count >= 3
        ):
            return SubstrateDecision(
                substrate_class=SubstrateClass.SGN_PRESENT_HC_LOSS,
                downstream_vertices=_BRANCH_TO_DOWNSTREAM[
                    SubstrateClass.SGN_PRESENT_HC_LOSS
                ],
                confidence="high",
                rationale="eABR present + DPOAE absent + nerve normal → "
                "hair-cell loss with SGN intact; OTOF-tx (V07) if DFNB9 "
                "(V02 gate), else eCI (V10).",
            )

        return SubstrateDecision(
            substrate_class=SubstrateClass.INDETERMINATE,
            downstream_vertices=[],
            confidence="low",
            rationale="Insufficient or contradictory evidence; "
            "re-acquire V02-V05 inputs before re-running V06.",
        )
