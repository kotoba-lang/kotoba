"""V01 PhenotypeActor — patient demographics + clinical phenotype intake.

Pure rule-based actor (no LLM). Validates input shape, normalises side, and
emits a phenotype record consumed downstream by V06 SubstrateClassifierActor
(via the V01→V04 fan-in superstep) and V16 InstitutionMatcherActor (for
patient locale).

Per ADR-2605181000 §Ethical guardrails: this actor enforces
`requires_human_review = True` on all downstream outputs.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


Side = Literal["right", "left", "bilateral"]
Onset = Literal["congenital", "postnatal_early", "postnatal_late", "unknown"]


class PhenotypeInput(BaseModel):
    """Raw patient intake for V01."""

    model_config = ConfigDict(extra="forbid")

    patient_ref: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="De-identified patient reference (hash / Shamir share id). "
        "MUST NOT contain PII per ADR-2605181040 §PII zero.",
    )
    side: Side
    age_years: float = Field(..., ge=0.0, le=120.0)
    onset: Onset = "congenital"
    progressive: bool = False
    locale_country: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 patient locale (for V16 matching).",
    )
    locale_region: Optional[str] = Field(default=None, max_length=128)


class PhenotypeRecord(BaseModel):
    """V01 output consumed by V02-V06 fan-in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    patient_ref: str
    side: Side
    age_years: float
    onset: Onset
    progressive: bool
    locale_country: str
    locale_region: Optional[str]
    # Project-level scope gate. Charter (ADR-2605181000) is right-sided
    # congenital. Out-of-scope cases still pass through V01 but flag here.
    in_project_scope: bool


class PhenotypeActor:
    """V01 — deterministic phenotype intake."""

    name = "V01_phenotype"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph node body. Reads `phenotype_input` from state, emits `phenotype`.

        Returns a state delta (per LangGraph convention).
        """
        raw = state.get("phenotype_input")
        if raw is None:
            return {"error": "V01: missing phenotype_input"}

        parsed = PhenotypeInput.model_validate(raw)
        record = PhenotypeRecord(
            patient_ref=parsed.patient_ref,
            side=parsed.side,
            age_years=parsed.age_years,
            onset=parsed.onset,
            progressive=parsed.progressive,
            locale_country=parsed.locale_country,
            locale_region=parsed.locale_region,
            in_project_scope=(
                parsed.side == "right" and parsed.onset == "congenital"
            ),
        )
        return {
            "phenotype": record.model_dump(),
            "requires_human_review": True,
        }
