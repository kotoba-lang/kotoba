"""V05 CmvTorchActor — congenital CMV / TORCH screen.

CMV is the leading non-genetic cause of congenital UHL; TORCH (toxoplasma,
rubella, HSV, syphilis) screen is the conventional differential. This actor
is rule-based and emits the `cmv_positive` informational flag for V06.

Per charter §V06 evidence: CMV/TORCH does NOT branch the substrate
classifier — V06 only consumes it for rationale text. The clinical reason
to surface it is downstream prognosis (CMV+ UHL has a high progression
risk to the contralateral ear), which V12/V13 will use.

The reference rule mirrors AAP 2023 / JSPID 2024 congenital CMV guidance:
positive if either (a) DNA PCR-positive on neonatal dried blood spot or
urine within 21 days of birth, OR (b) clinically symptomatic + IgM positive
serology with low IgG avidity.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Window (clinician-reviewable in PR) ──────────────────────────────────────

# Days-of-life upper bound for a DNA PCR sample to be considered congenital
# (vs perinatal acquired). AAP 2023 standard is 21 days.
_CONGENITAL_PCR_WINDOW_DAYS = 21


# ── Inputs ───────────────────────────────────────────────────────────────────


class PcrResult(str, Enum):
    NEGATIVE = "negative"
    POSITIVE = "positive"
    NOT_TESTED = "not_tested"


class SerologyResult(str, Enum):
    NEGATIVE = "negative"
    EQUIVOCAL = "equivocal"
    POSITIVE = "positive"
    NOT_TESTED = "not_tested"


class IgGAvidity(str, Enum):
    LOW = "low"
    INTERMEDIATE = "intermediate"
    HIGH = "high"
    NOT_TESTED = "not_tested"


class TorchAgent(str, Enum):
    """Non-CMV TORCH agents tracked for the differential."""

    TOXOPLASMA = "toxoplasma"
    RUBELLA = "rubella"
    HSV = "hsv"
    SYPHILIS = "syphilis"


class TorchSerology(BaseModel):
    """Per-agent IgM/IgG result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: TorchAgent
    igm: SerologyResult = SerologyResult.NOT_TESTED
    igg: SerologyResult = SerologyResult.NOT_TESTED


class CmvTorchInput(BaseModel):
    """V05 input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_age_days: Optional[int] = Field(
        default=None,
        ge=0,
        le=3650,
        description="Days of life at the time the CMV PCR sample was drawn. "
        "Required for the congenital-vs-perinatal call when PCR is positive.",
    )

    cmv_pcr_dbs: PcrResult = PcrResult.NOT_TESTED  # Neonatal dried blood spot
    cmv_pcr_urine: PcrResult = PcrResult.NOT_TESTED
    cmv_igm: SerologyResult = SerologyResult.NOT_TESTED
    cmv_igg: SerologyResult = SerologyResult.NOT_TESTED
    cmv_igg_avidity: IgGAvidity = IgGAvidity.NOT_TESTED
    clinically_symptomatic: bool = Field(
        default=False,
        description="Petechiae / microcephaly / chorioretinitis / hepatosplenomegaly. "
        "Triggers the symptomatic-cCMV branch.",
    )

    torch_serology: list[TorchSerology] = Field(default_factory=list)


# ── Output ───────────────────────────────────────────────────────────────────


class CmvClassification(str, Enum):
    CONGENITAL_CMV_CONFIRMED = "congenital_cmv_confirmed"
    CONGENITAL_CMV_PROBABLE = "congenital_cmv_probable"
    NEGATIVE_OR_INCONCLUSIVE = "negative_or_inconclusive"
    NOT_TESTED = "not_tested"


class CmvTorchResult(BaseModel):
    """V05 output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cmv_classification: CmvClassification
    cmv_positive: bool
    torch_positive_agents: list[TorchAgent] = Field(default_factory=list)
    rationale: str = Field(..., max_length=500)


# ── Actor ────────────────────────────────────────────────────────────────────


class CmvTorchActor:
    """V05 — deterministic CMV/TORCH rule cascade."""

    name = "V05_cmv_torch"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("cmv_torch_input")
        if raw is None:
            empty = CmvTorchResult(
                cmv_classification=CmvClassification.NOT_TESTED,
                cmv_positive=False,
                torch_positive_agents=[],
                rationale="V05 not invoked (no input).",
            )
            return {"cmv_torch_result": empty.model_dump()}

        parsed = CmvTorchInput.model_validate(raw)
        result = CmvTorchActor._classify(parsed)

        delta_evidence: dict[str, Any] = dict(state.get("substrate_evidence") or {})
        delta_evidence["cmv_positive"] = result.cmv_positive

        return {
            "cmv_torch_result": result.model_dump(),
            "substrate_evidence": delta_evidence,
            "requires_human_review": True,
        }

    @staticmethod
    def _classify(parsed: CmvTorchInput) -> CmvTorchResult:
        # ── CMV ──
        pcr_positive_within_window = (
            (
                parsed.cmv_pcr_dbs is PcrResult.POSITIVE
                or parsed.cmv_pcr_urine is PcrResult.POSITIVE
            )
            and parsed.sample_age_days is not None
            and parsed.sample_age_days <= _CONGENITAL_PCR_WINDOW_DAYS
        )

        symptomatic_serology_probable = (
            parsed.clinically_symptomatic
            and parsed.cmv_igm is SerologyResult.POSITIVE
            and parsed.cmv_igg_avidity is IgGAvidity.LOW
        )

        if pcr_positive_within_window:
            cmv_class = CmvClassification.CONGENITAL_CMV_CONFIRMED
            cmv_rationale = (
                f"CMV DNA PCR positive within "
                f"{_CONGENITAL_PCR_WINDOW_DAYS}-day congenital window → "
                f"congenital cCMV confirmed."
            )
        elif symptomatic_serology_probable:
            cmv_class = CmvClassification.CONGENITAL_CMV_PROBABLE
            cmv_rationale = (
                "Symptomatic + IgM positive + low IgG avidity → probable "
                "congenital CMV; PCR confirmation recommended."
            )
        elif (
            parsed.cmv_pcr_dbs is PcrResult.NOT_TESTED
            and parsed.cmv_pcr_urine is PcrResult.NOT_TESTED
            and parsed.cmv_igm is SerologyResult.NOT_TESTED
        ):
            cmv_class = CmvClassification.NOT_TESTED
            cmv_rationale = "CMV screen not performed."
        else:
            cmv_class = CmvClassification.NEGATIVE_OR_INCONCLUSIVE
            cmv_rationale = "CMV screen negative or inconclusive."

        cmv_positive = cmv_class in (
            CmvClassification.CONGENITAL_CMV_CONFIRMED,
            CmvClassification.CONGENITAL_CMV_PROBABLE,
        )

        # ── TORCH ──
        torch_positive: list[TorchAgent] = []
        for sero in parsed.torch_serology:
            if sero.igm is SerologyResult.POSITIVE:
                torch_positive.append(sero.agent)

        rationale = cmv_rationale
        if torch_positive:
            rationale += (
                " TORCH IgM-positive: "
                + ", ".join(a.value for a in torch_positive)
                + "."
            )

        return CmvTorchResult(
            cmv_classification=cmv_class,
            cmv_positive=cmv_positive,
            torch_positive_agents=torch_positive,
            rationale=rationale[:500],
        )
