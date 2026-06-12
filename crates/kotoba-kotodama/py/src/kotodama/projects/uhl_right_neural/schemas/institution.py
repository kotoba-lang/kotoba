"""UHL-R Medical Institution Registry schema.

Authoritative per ADR-2605181040.

Hard rules (enforced here):
  1. PII zero — no individual patients, no individual clinicians.
  2. evidence_url required on every ProcedureRecord — public sources only.
  3. last_verified_at required — staleness window = 180 days
     (computed by InstitutionMatcherActor, not by these models).
  4. ReferralPathRef → ADR-2605181050 path slugs only.
  5. requires_human_review is enforced at the actor/lexicon output level,
     not here (models only describe institutions, not match decisions).
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────


class CapabilityKind(str, Enum):
    """Capability taxonomy per ADR-2605181040 §Schema/Capability."""

    GENETIC_TEST = "GENETIC_TEST"
    PED_CI = "PED_CI"
    CND_CI = "CND_CI"
    ABI = "ABI"
    GENE_TX_OTOF = "GENE_TX_OTOF"
    OPTO_CI_TRIAL = "OPTO_CI_TRIAL"
    NEURAL_REGEN_RESEARCH = "NEURAL_REGEN_RESEARCH"
    CONSULT_HUB = "CONSULT_HUB"


class Reimbursement(str, Enum):
    """Funding model for a procedure at a given institution."""

    HOKEN = "hoken"          # Japanese health insurance covered
    SELF_PAY = "self_pay"    # Patient self-pay (incl. overseas)
    TRIAL = "trial"          # Clinical trial / research participation
    UNKNOWN = "unknown"


class Country(str, Enum):
    """ISO 3166-1 alpha-2 country codes used in seed data."""

    JP = "JP"
    US = "US"
    GB = "GB"
    DE = "DE"
    ES = "ES"


# ── Models ───────────────────────────────────────────────────────────────────


class ProcedureRecord(BaseModel):
    """Evidence-backed claim about an institution's procedural capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cumulative_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Cumulative cases performed. None = not publicly disclosed.",
    )
    count_as_of: Optional[date] = Field(
        default=None,
        description="Date the cumulative_count was current. None when count is None.",
    )
    evidence_url: HttpUrl = Field(
        ...,
        description="Public source URL — academic journal, official site, "
        "peer-reviewed paper, or regulatory body. No SNS or personal blogs.",
    )
    reimbursement: Reimbursement = Field(...)
    notes_ja: Optional[str] = Field(default=None, max_length=2000)


class Capability(BaseModel):
    """One declared capability with its evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CapabilityKind
    procedure_record: ProcedureRecord
    notes_ja: Optional[str] = Field(default=None, max_length=2000)


class ReferralPathRef(BaseModel):
    """Foreign-key reference to an ADR-2605181050 named referral path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path_id: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9\-]{2,63}$",
        description="Path slug defined in ADR-2605181050 (e.g. abi-uk-nhs-paediatric).",
    )


class Institution(BaseModel):
    """A single medical institution record (1:1 with MST/PDS record)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        ...,
        pattern=r"^[a-z]{2}-[a-z0-9][a-z0-9\-]{1,63}$",
        description="Slug: <country>-<short>. Lowercase. Stable.",
    )
    did: Optional[str] = Field(
        default=None,
        pattern=r"^did:",
        description="Optional DID if institution participates in the substrate.",
    )
    name_ja: str = Field(..., min_length=1, max_length=200)
    name_en: str = Field(..., min_length=1, max_length=200)
    country: Country
    locale: str = Field(..., min_length=1, max_length=200)
    website: HttpUrl
    capabilities: list[Capability] = Field(..., min_length=1)
    referral_paths: list[ReferralPathRef] = Field(default_factory=list)
    last_verified_at: date
    verified_by: str = Field(
        ...,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Verifier email. Public ops contact only — no PII.",
    )

    @field_validator("capabilities")
    @classmethod
    def _capability_kinds_unique(cls, v: list[Capability]) -> list[Capability]:
        seen: set[CapabilityKind] = set()
        for cap in v:
            if cap.kind in seen:
                raise ValueError(
                    f"Duplicate capability kind {cap.kind.value}. "
                    "Merge into a single Capability entry."
                )
            seen.add(cap.kind)
        return v


class InstitutionRegistry(BaseModel):
    """Top-level seed file shape (institutions_jp.yaml / institutions_intl.yaml)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    institutions: list[Institution] = Field(..., min_length=1)

    @field_validator("institutions")
    @classmethod
    def _ids_unique(cls, v: list[Institution]) -> list[Institution]:
        seen: set[str] = set()
        for inst in v:
            if inst.id in seen:
                raise ValueError(f"Duplicate institution id: {inst.id}")
            seen.add(inst.id)
        return v
