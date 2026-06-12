"""V03 ImagingActor — internal auditory canal (IAC) MRI fiber count.

Reads CISS/FIESTA-derived counts of cochlear nerve (CN) and facial nerve (FN)
fibers in the affected IAC, plus optional aplasia/hypoplasia radiologist
flags. Emits the `cn_fiber_count` SubstrateEvidence field consumed by V06.

Vision-LLM補助 (charter §15-actor fleet) is deferred to P1; this P0
implementation is a deterministic radiologist-style rule cascade. Inputs
come from radiology read structured into the CnFiberRead shape — the rule
that converts raw DICOM into the count is out of scope for the Pregel and
is handled upstream by a vision-LLM-assisted radiologist tool.

Per ADR-2605181000 §Ethical guardrails: all downstream output carries
`requires_human_review = True`.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


Ear = Literal["right", "left"]


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# CN/FN ratio below which the cochlear nerve is treated as relatively
# hypoplastic regardless of the absolute count. Normal IAC anatomy carries
# CN ≈ FN, so a ratio < 0.5 is a flag even if CN count is nominally ≥3.
_CN_FN_RATIO_HYPOPLASTIC_THRESHOLD = 0.5


# ── Input ────────────────────────────────────────────────────────────────────


class IacAplasiaCall(str, Enum):
    """Radiologist-asserted aplasia/hypoplasia call. Overrides the raw count
    when present (e.g. for a CN that has zero strands but a residual sheath)."""

    NORMAL = "normal"
    HYPOPLASTIC = "hypoplastic"
    APLASTIC = "aplastic"


class CnFiberRead(BaseModel):
    """Radiology read of the affected IAC."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ear: Ear

    cn_fiber_strands: int = Field(
        ...,
        ge=0,
        le=4,
        description="Cochlear nerve fiber strands counted on CISS/FIESTA "
        "(0=aplasia, 1-2=severe hypoplasia, 3-4=normal-ish).",
    )
    fn_fiber_strands: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        description="Facial nerve fiber strands in the same IAC. Used as the "
        "denominator of the CN/FN ratio sanity check.",
    )

    radiologist_call: IacAplasiaCall = Field(
        default=IacAplasiaCall.NORMAL,
        description="Overall radiologist verdict. If APLASTIC the count is "
        "forced to 0 in the V06-bound output regardless of strands.",
    )
    iac_stenosis: bool = Field(
        default=False,
        description="IAC bony stenosis — surgical relevance for V11 ABI, "
        "informational for V06.",
    )


class ImagingInput(BaseModel):
    """V03 input wrapper."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    read: CnFiberRead


# ── Output ───────────────────────────────────────────────────────────────────


class ImagingResult(BaseModel):
    """V03 output. `cn_fiber_count` and `iac_stenosis` go to substrate_evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ear: Ear
    cn_fiber_count: int = Field(..., ge=0, le=4)
    cn_fn_ratio: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    cn_hypoplastic_by_ratio: bool = False
    iac_stenosis: bool = False
    radiologist_call: IacAplasiaCall
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aplasia_consistency(self) -> "ImagingResult":
        if self.radiologist_call is IacAplasiaCall.APLASTIC and self.cn_fiber_count != 0:
            raise ValueError(
                "radiologist_call=aplastic but cn_fiber_count != 0; "
                "ImagingActor.compute() must reconcile these before emitting."
            )
        return self


# ── Actor ────────────────────────────────────────────────────────────────────


class ImagingActor:
    """V03 — deterministic IAC fiber-count fusion."""

    name = "V03_imaging"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("imaging_input")
        if raw is None:
            # No imaging input — V06 will see absent cn_fiber_count and route
            # to INDETERMINATE.
            return {
                "imaging_result": {"_absent": True},
            }
        parsed = ImagingInput.model_validate(raw)
        result = ImagingActor._fuse(parsed.read)

        delta_evidence: dict[str, Any] = dict(state.get("substrate_evidence") or {})
        delta_evidence["cn_fiber_count"] = result.cn_fiber_count

        return {
            "imaging_result": result.model_dump(),
            "substrate_evidence": delta_evidence,
            "requires_human_review": True,
        }

    @staticmethod
    def _fuse(read: CnFiberRead) -> ImagingResult:
        notes: list[str] = []

        cn_fiber_count = read.cn_fiber_strands
        if read.radiologist_call is IacAplasiaCall.APLASTIC and cn_fiber_count != 0:
            notes.append(
                f"radiologist call=aplastic overriding cn_fiber_strands={cn_fiber_count} → 0"
            )
            cn_fiber_count = 0

        cn_fn_ratio: Optional[float] = None
        hypoplastic_by_ratio = False
        if read.fn_fiber_strands is not None and read.fn_fiber_strands > 0:
            cn_fn_ratio = round(cn_fiber_count / read.fn_fiber_strands, 3)
            if cn_fn_ratio < _CN_FN_RATIO_HYPOPLASTIC_THRESHOLD:
                hypoplastic_by_ratio = True
                notes.append(
                    f"CN/FN ratio {cn_fn_ratio} < {_CN_FN_RATIO_HYPOPLASTIC_THRESHOLD} → "
                    f"relative cochlear nerve hypoplasia even if absolute count "
                    f"({cn_fiber_count}) is nominally adequate."
                )

        if read.iac_stenosis:
            notes.append(
                "IAC bony stenosis present — surgical implication for V11 ABI; "
                "informational for V06."
            )

        return ImagingResult(
            ear=read.ear,
            cn_fiber_count=cn_fiber_count,
            cn_fn_ratio=cn_fn_ratio,
            cn_hypoplastic_by_ratio=hypoplastic_by_ratio,
            iac_stenosis=read.iac_stenosis,
            radiologist_call=read.radiologist_call,
            notes=notes,
        )
