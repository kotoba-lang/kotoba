"""V16 InstitutionMatcherActor — terminal vertex, substrate × locale → ranked institutions.

Per ADR-2605181040: loads the institution registry seed YAML, ranks candidates
by capability match × geographic affinity × reimbursement preference × staleness,
and emits a result with `requires_human_review: true` enforced.

Per ADR-2605181050: overseas referral path candidates carry burden disclosure
metadata. Per ADR-2605181060: GENE_TX_OTOF capability is gated by DFNB9
confirmation (V02 output) — without that gate, OTOF capability is filtered out.

This actor does NOT make clinical decisions. It produces a ranked candidate
list for human review.
"""
from __future__ import annotations

from datetime import date, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..schemas.institution import (
    Capability,
    CapabilityKind,
    Country,
    Institution,
    InstitutionRegistry,
)
from .substrate_classifier import SubstrateClass


_STALENESS_DAYS = 180  # per ADR-2605181040 §公開ポリシー #3


# ── Mapping: substrate class → required capability kinds ─────────────────────


_SUBSTRATE_TO_CAPABILITIES: dict[SubstrateClass, list[CapabilityKind]] = {
    SubstrateClass.SGN_PRESENT_HC_LOSS: [
        CapabilityKind.GENE_TX_OTOF,    # V07 if DFNB9 gated
        CapabilityKind.PED_CI,          # V10 fallback
        CapabilityKind.CND_CI,
    ],
    SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT: [
        CapabilityKind.NEURAL_REGEN_RESEARCH,  # V08 neurotrophin (research stage)
        CapabilityKind.PED_CI,
        CapabilityKind.CND_CI,
    ],
    SubstrateClass.SGN_ABSENT_NERVE_PRESENT: [
        CapabilityKind.NEURAL_REGEN_RESEARCH,  # V09 reprog (research stage)
        CapabilityKind.OPTO_CI_TRIAL,          # V10b optoCI (trial stage)
    ],
    SubstrateClass.NERVE_APLASIA: [
        CapabilityKind.ABI,  # V11 — only current option
    ],
    SubstrateClass.INDETERMINATE: [
        CapabilityKind.CONSULT_HUB,
        CapabilityKind.GENETIC_TEST,
    ],
}


# ── Output models ────────────────────────────────────────────────────────────


class InstitutionMatch(BaseModel):
    """One ranked institution candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    institution_id: str
    name_ja: str
    name_en: str
    country: Country
    matched_capabilities: list[CapabilityKind]
    score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: dict[str, float]
    referral_path_ids: list[str]
    is_stale: bool = Field(
        ...,
        description=f"True when last_verified_at > {_STALENESS_DAYS}d ago.",
    )
    notes: list[str] = Field(default_factory=list)


class InstitutionMatchResult(BaseModel):
    """V16 output. requires_human_review is immutable per ADR-2605181040/1050/1060."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate_class: SubstrateClass
    candidates: list[InstitutionMatch]
    requires_human_review: bool = True
    burden_summary_url: str = "ADR-2605181050"
    ethics_committee_required: bool = True
    data_export_requires_review: bool = True


# ── Actor ────────────────────────────────────────────────────────────────────


class InstitutionMatcherActor:
    """V16 — load seed, filter by substrate, rank by composite score."""

    name = "V16_institution_matcher"

    def __init__(self, seed_dir: Optional[Path] = None) -> None:
        self._seed_dir = seed_dir or self._default_seed_dir()
        self._registry: Optional[list[Institution]] = None

    @staticmethod
    def _default_seed_dir() -> Path:
        # Resolve to the project's seed/ directory at import time.
        # In production this is shipped with the package.
        pkg = files("kotodama.projects.uhl_right_neural").joinpath("seed")
        return Path(str(pkg))

    def _load(self) -> list[Institution]:
        if self._registry is not None:
            return self._registry
        items: list[Institution] = []
        for fname in ("institutions_jp.yaml", "institutions_intl.yaml"):
            path = self._seed_dir / fname
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            reg = InstitutionRegistry.model_validate(data)
            items.extend(reg.institutions)
        self._registry = items
        return items

    # ── LangGraph node body ──────────────────────────────────────────────────

    def compute(self, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("substrate_decision") or {}
        klass_raw = decision.get("substrate_class")
        if not klass_raw:
            return {"error": "V16: missing substrate_decision"}
        klass = SubstrateClass(klass_raw)

        phenotype = state.get("phenotype") or {}
        locale_country = phenotype.get("locale_country", "JP")

        # Genetic gate (per ADR-2605181060): GENE_TX_OTOF requires DFNB9.
        dfnb9_confirmed = bool(
            (state.get("substrate_evidence") or {}).get(
                "biallelic_otof_pathogenic", False
            )
        )

        result = self.match(
            substrate_class=klass,
            locale_country=locale_country,
            dfnb9_confirmed=dfnb9_confirmed,
        )
        return {"institution_match": result.model_dump()}

    # ── Pure ranking logic (callable for tests) ──────────────────────────────

    def match(
        self,
        substrate_class: SubstrateClass,
        locale_country: str,
        dfnb9_confirmed: bool,
        top_n: int = 5,
        today: Optional[date] = None,
    ) -> InstitutionMatchResult:
        today = today or date.today()
        wanted: set[CapabilityKind] = set(
            _SUBSTRATE_TO_CAPABILITIES.get(substrate_class, [])
        )
        if not wanted:
            return InstitutionMatchResult(
                substrate_class=substrate_class,
                candidates=[],
            )

        candidates: list[InstitutionMatch] = []
        for inst in self._load():
            matched: list[CapabilityKind] = []
            notes: list[str] = []
            for cap in inst.capabilities:
                if cap.kind not in wanted:
                    continue
                if (
                    cap.kind is CapabilityKind.GENE_TX_OTOF
                    and not dfnb9_confirmed
                ):
                    notes.append(
                        "GENE_TX_OTOF filtered: DFNB9 biallelic ACMG 4-5 "
                        "not confirmed (ADR-2605181060)."
                    )
                    continue
                matched.append(cap.kind)
            if not matched:
                continue

            is_stale = (today - inst.last_verified_at) > timedelta(days=_STALENESS_DAYS)
            if is_stale:
                notes.append(
                    f"Stale: last_verified_at older than {_STALENESS_DAYS} days."
                )

            cap_score = len(matched) / max(1, len(wanted))
            locale_score = 1.0 if inst.country.value == locale_country else 0.4
            staleness_score = 0.5 if is_stale else 1.0
            evidence_score = self._evidence_score(inst.capabilities, matched)

            score = round(
                0.45 * cap_score
                + 0.25 * locale_score
                + 0.15 * staleness_score
                + 0.15 * evidence_score,
                4,
            )

            candidates.append(
                InstitutionMatch(
                    institution_id=inst.id,
                    name_ja=inst.name_ja,
                    name_en=inst.name_en,
                    country=inst.country,
                    matched_capabilities=matched,
                    score=score,
                    score_breakdown={
                        "capability_match": round(cap_score, 4),
                        "locale_affinity": round(locale_score, 4),
                        "staleness": round(staleness_score, 4),
                        "evidence_quality": round(evidence_score, 4),
                    },
                    referral_path_ids=[r.path_id for r in inst.referral_paths],
                    is_stale=is_stale,
                    notes=notes,
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return InstitutionMatchResult(
            substrate_class=substrate_class,
            candidates=candidates[:top_n],
        )

    @staticmethod
    def _evidence_score(
        all_caps: list[Capability], matched: list[CapabilityKind]
    ) -> float:
        """Higher when matched capabilities have cumulative_count disclosed."""
        relevant = [c for c in all_caps if c.kind in matched]
        if not relevant:
            return 0.5
        with_count = sum(
            1 for c in relevant if c.procedure_record.cumulative_count is not None
        )
        return with_count / len(relevant)
