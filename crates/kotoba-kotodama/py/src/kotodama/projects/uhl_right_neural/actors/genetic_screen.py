"""V02 GeneticScreenActor — hereditary deafness panel + ACMG classification.

Deterministic actor (no LLM). Reads patient variant calls, classifies each
against the panel, and emits structured results consumed by V06 substrate
classifier (specifically the `biallelic_otof_pathogenic` evidence flag used
in DFNB9 gating per ADR-2605181060).

Panel mirrors the Shinshu (Usami lab) hereditary deafness panel established
under the 2012 hoken-covered genetic test (rule per institutions_jp.yaml
jp-shinshu-u-orl entry).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Panel ────────────────────────────────────────────────────────────────────


class PanelGene(str, Enum):
    """Genes covered by the V02 hereditary deafness panel."""

    OTOF = "OTOF"
    GJB2 = "GJB2"
    GJB6 = "GJB6"
    SLC26A4 = "SLC26A4"
    MYO7A = "MYO7A"
    MYO15A = "MYO15A"
    TMC1 = "TMC1"
    CDH23 = "CDH23"
    POU3F4 = "POU3F4"


class AcmgClass(int, Enum):
    """ACMG-AMP 5-class pathogenicity scale."""

    BENIGN = 1
    LIKELY_BENIGN = 2
    UNCERTAIN = 3
    LIKELY_PATHOGENIC = 4
    PATHOGENIC = 5


Zygosity = Literal["heterozygous", "homozygous", "compound_heterozygous", "hemizygous"]


# ── Inputs ───────────────────────────────────────────────────────────────────


class VariantCall(BaseModel):
    """One reported variant for a single gene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gene: PanelGene
    hgvs_c: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="HGVS coding-sequence nomenclature (e.g. c.5098G>C).",
    )
    hgvs_p: Optional[str] = Field(default=None, max_length=200)
    zygosity: Zygosity
    acmg_class: AcmgClass


class GeneticScreenInput(BaseModel):
    """V02 input — list of variant calls plus the panel run identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    panel_run_id: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Hashed / de-identified panel run id (no PII).",
    )
    variants: list[VariantCall] = Field(default_factory=list)


# ── Outputs ──────────────────────────────────────────────────────────────────


class GeneVerdict(BaseModel):
    """Per-gene verdict after biallelic + ACMG aggregation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gene: PanelGene
    biallelic_pathogenic: bool = Field(
        ...,
        description="True when ≥2 variants reach ACMG class 4-5 OR a single "
        "homozygous/hemizygous variant reaches class 4-5.",
    )
    highest_class: AcmgClass
    variant_count: int


class GeneticScreenResult(BaseModel):
    """V02 output. Emits a SubstrateEvidence-compatible delta for V06 fan-in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    panel_run_id: str
    verdicts: list[GeneVerdict]
    # Convenience flag consumed by V06 SubstrateEvidence + V16 DFNB9 gate.
    biallelic_otof_pathogenic: bool

    @field_validator("verdicts")
    @classmethod
    def _no_duplicate_genes(cls, v: list[GeneVerdict]) -> list[GeneVerdict]:
        seen: set[PanelGene] = set()
        for verdict in v:
            if verdict.gene in seen:
                raise ValueError(f"Duplicate verdict for gene {verdict.gene}")
            seen.add(verdict.gene)
        return v


# ── Actor ────────────────────────────────────────────────────────────────────


class GeneticScreenActor:
    """V02 — deterministic ACMG-based panel aggregator."""

    name = "V02_genetic_screen"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("genetic_input")
        if raw is None:
            # No genetic input is acceptable — V02 emits an empty result and
            # downstream V06 simply lacks the OTOF gate signal.
            return {
                "genetic_result": GeneticScreenResult(
                    panel_run_id="",
                    verdicts=[],
                    biallelic_otof_pathogenic=False,
                ).model_dump()
            }
        parsed = GeneticScreenInput.model_validate(raw)
        result = GeneticScreenActor._aggregate(parsed)
        return {
            "genetic_result": result.model_dump(),
            # Also push the gate flag into substrate_evidence for V06 fan-in.
            "substrate_evidence": {
                **(state.get("substrate_evidence") or {}),
                "biallelic_otof_pathogenic": result.biallelic_otof_pathogenic,
            },
            "requires_human_review": True,
        }

    @staticmethod
    def _aggregate(parsed: GeneticScreenInput) -> GeneticScreenResult:
        by_gene: dict[PanelGene, list[VariantCall]] = {}
        for v in parsed.variants:
            by_gene.setdefault(v.gene, []).append(v)

        verdicts: list[GeneVerdict] = []
        for gene, calls in by_gene.items():
            highest = max(c.acmg_class for c in calls)
            biallelic = GeneticScreenActor._is_biallelic_pathogenic(calls)
            verdicts.append(
                GeneVerdict(
                    gene=gene,
                    biallelic_pathogenic=biallelic,
                    highest_class=highest,
                    variant_count=len(calls),
                )
            )

        otof_flag = any(
            v.gene is PanelGene.OTOF and v.biallelic_pathogenic for v in verdicts
        )
        return GeneticScreenResult(
            panel_run_id=parsed.panel_run_id,
            verdicts=verdicts,
            biallelic_otof_pathogenic=otof_flag,
        )

    @staticmethod
    def _is_biallelic_pathogenic(calls: list[VariantCall]) -> bool:
        """Biallelic pathogenic = (homozygous|hemizygous class ≥4)
        OR (≥2 distinct heterozygous/compound_het calls each class ≥4)."""
        pathogenic = [c for c in calls if c.acmg_class.value >= 4]
        if not pathogenic:
            return False
        for c in pathogenic:
            if c.zygosity in ("homozygous", "hemizygous"):
                return True
        # Count compound het / het calls
        diploid_evidence = [
            c for c in pathogenic if c.zygosity in ("heterozygous", "compound_heterozygous")
        ]
        return len(diploid_evidence) >= 2
