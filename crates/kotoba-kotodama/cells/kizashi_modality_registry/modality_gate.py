"""Pure modality-capability ledger + G10 anti-pseudoscience GATE for ``kizashi`` (兆).

Per ADR-2605312700 (兆 kizashi — non-invasive multimodal body-scan / sign-sensing
substrate) and the modality-capability seed at
``20-actors/kizashi/registry/modalities.seed.json``. kizashi SENSES; it never
diagnoses (mitate diagnoses → iyashi treats). The modality ledger is the **G10
anti-pseudoscience gate**: a modality may emit a ``modalityObservation`` ONLY if
it is ledgered here with a defensible evidence grade. Grade-X entries
(bio-resonance / aura / 波動 / quantum scanners) are EXCLUDED and may NEVER emit.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Verified-modality-only / anti-pseudoscience (G10)** — ``may_emit`` is True
    ONLY for an emitting evidence grade (A / B / C). A grade-X
    (``X-excluded-pseudoscience``) modality has ``may_emit`` ``False`` and there
    is NO code path that can set it ``True``. An unknown / missing evidence grade
    raises (no ungraded modality is ever ledgered as emitting).
  * **Non-diagnostic** — kizashi senses, it does not diagnose.
    ``is_diagnostic`` / ``isDiagnostic`` is ALWAYS ``False``. ``canDetect`` /
    ``cannotDetect`` honesty fields are preserved verbatim so the boundary of
    what a modality can and cannot sense is always carried alongside it.
  * **ALARA — ionizing = referral, never routine (G9)** — an ionizing modality
    is flagged ``ionizing_referral_only`` ``True``; it is a referral pathway,
    not a routine sensing pod.
  * **Regulated-class honesty (G4)** — ``regulatoryClass`` must be one of the
    known classes; an unknown class raises (no unclassified device routed).
  * No inference, no network; pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure gate core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``KizashiModalityRegistryCell`` graph)
stays non-deployable until Council ratification (Lv6+ ≥3) + ledger attestation.
Landing + testing this core does NOT activate the cell.

Output shape mirrors a ledger view over Lexicon
``com.etzhayyim.kizashi.modalityCapability`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── evidence grades (the registry's OWN quality signal) ─────────────────
# Lower sort-key sorts FIRST. The single excluded grade is the G10 boundary.
EVIDENCE_GRADE_ORDER = {
    "A-validated-clinical": 0,
    "B-emerging-peer-reviewed": 1,
    "C-screening-only": 2,
    "X-excluded-pseudoscience": 3,
}

# Grades permitted to emit a modalityObservation. The excluded grade is, by
# construction, NOT in this set — this frozenset IS the G10 gate.
EMITTING_GRADES = frozenset(
    {"A-validated-clinical", "B-emerging-peer-reviewed", "C-screening-only"}
)
EXCLUDED_GRADE = "X-excluded-pseudoscience"

# Known regulatory classes (ADR-2605312700). An entry whose ``regulatoryClass``
# is outside this set raises in ``_to_modality`` (no unclassified device routed).
REGULATORY_CLASSES = frozenset(
    {
        "non-regulated-wellness",
        "samd-software",
        "regulated-medical-device",
        "ionizing-licensed-facility-only",
    }
)

# verificationStatus values routable when the caller declines unverified-seed
# entries; whether to surface ``unverified-seed`` is caller policy.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})


@dataclass(frozen=True)
class ModalityQuery:
    """Ledger query. No PII — this is a capability ledger, not a member record."""

    capability: str | None = None  # OPTIONAL substring over canDetect; None = any
    regulatory_class: str | None = None  # OPTIONAL exact class filter; None = any
    phase_gate: str | None = None  # OPTIONAL exact phase-gate filter; None = any
    emitting_only: bool = False  # True → drop grade-X (G10) entirely
    include_ionizing: bool = True  # False → drop ionizing modalities (G9)
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class Modality:
    """One ledgered sensing modality. ``may_emit`` is the G10 gate result."""

    modality_id: str
    display_name: str
    evidence_grade: str
    regulatory_class: str
    ionizing: bool
    phase_gate: str
    can_detect: tuple[str, ...]
    cannot_detect: tuple[str, ...]
    verification_status: str
    council_attestation_cid: str
    notes: str
    provenance: str
    last_verified: str
    may_emit: bool  # G10 gate: True ONLY for an emitting grade (never grade-X)
    is_diagnostic: bool  # ALWAYS False
    ionizing_referral_only: bool  # G9 ALARA: True iff ionizing


@dataclass(frozen=True)
class ModalityResult:
    capability: str | None
    regulatory_class: str | None
    phase_gate: str | None
    is_diagnostic: bool  # ALWAYS False
    modalities: tuple[Modality, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _grade_rank(grade: str) -> int:
    if grade not in EVIDENCE_GRADE_ORDER:
        raise ValueError(
            f"unknown evidenceGrade {grade!r}; "
            f"allowed: {sorted(EVIDENCE_GRADE_ORDER, key=EVIDENCE_GRADE_ORDER.get)}"
        )
    return EVIDENCE_GRADE_ORDER[grade]


def may_emit(evidence_grade: str) -> bool:
    """The G10 gate: a grade may emit ONLY if it is an emitting grade.

    Validates the grade (unknown → ValueError); a grade-X grade returns False.
    There is no input for which a grade-X modality returns True.
    """
    _grade_rank(evidence_grade)  # validate (raises on unknown)
    return evidence_grade in EMITTING_GRADES


def _str_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list, got {type(value).__name__}")
    return tuple(str(v) for v in value)


def _to_modality(entry: dict) -> Modality:
    """Project one raw registry dict → a frozen :class:`Modality` (G10-pinned).

    Unknown evidenceGrade or regulatoryClass raises — no ungraded / unclassified
    modality is ever ledgered.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    modality_id = _require_str(entry.get("modalityId"), "modalityId")
    display_name = _require_str(entry.get("displayName"), "displayName")
    evidence_grade = _require_str(entry.get("evidenceGrade"), "evidenceGrade")
    _grade_rank(evidence_grade)  # validate early (raises on unknown)
    regulatory_class = _require_str(entry.get("regulatoryClass"), "regulatoryClass")
    if regulatory_class not in REGULATORY_CLASSES:
        raise ValueError(
            f"unknown regulatoryClass {regulatory_class!r}; "
            f"allowed: {sorted(REGULATORY_CLASSES)}"
        )
    ionizing = entry.get("ionizing")
    if not isinstance(ionizing, bool):
        raise ValueError("ionizing must be a bool")
    return Modality(
        modality_id=modality_id,
        display_name=display_name,
        evidence_grade=evidence_grade,
        regulatory_class=regulatory_class,
        ionizing=ionizing,
        phase_gate=str(entry.get("phaseGate", "")),
        can_detect=_str_tuple(entry.get("canDetect", []), "canDetect"),
        cannot_detect=_str_tuple(entry.get("cannotDetect", []), "cannotDetect"),
        verification_status=str(entry.get("verificationStatus", "")),
        council_attestation_cid=str(entry.get("councilAttestationCid", "")),
        notes=str(entry.get("notes", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        may_emit=evidence_grade in EMITTING_GRADES,  # G10 — grade-X → False
        is_diagnostic=False,  # kizashi senses, never diagnoses
        ionizing_referral_only=ionizing,  # G9 ALARA
    )


def resolve_modalities(query: ModalityQuery, registry: dict) -> ModalityResult:
    """Pure ledger query over the modality registry.

    Returns modalities sorted by evidence grade (A→B→C→X) then displayName.
    With ``emitting_only=False`` (default) the FULL ledger is returned for
    transparency — but every grade-X modality still carries ``may_emit=False``
    (G10). ``is_diagnostic`` is hard-wired ``False``.
    """
    capability = query.capability
    if capability is not None:
        capability = _require_str(capability, "capability").lower()
    regulatory_class = query.regulatory_class
    if regulatory_class is not None:
        regulatory_class = _require_str(regulatory_class, "regulatory_class")
        if regulatory_class not in REGULATORY_CLASSES:
            raise ValueError(
                f"unknown regulatory_class {regulatory_class!r}; "
                f"allowed: {sorted(REGULATORY_CLASSES)}"
            )
    phase_gate = query.phase_gate
    if phase_gate is not None:
        phase_gate = _require_str(phase_gate, "phase_gate")

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed modalities.seed.json)")
    raw = registry.get("modalities")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'modalities' list")

    matches: list[Modality] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each modality entry must be a dict")
        m = _to_modality(entry)  # validates grade + class (raises on unknown)
        if query.emitting_only and not m.may_emit:
            continue
        if not query.include_ionizing and m.ionizing:
            continue
        if regulatory_class is not None and m.regulatory_class != regulatory_class:
            continue
        if phase_gate is not None and m.phase_gate != phase_gate:
            continue
        if not query.allow_unverified:
            if m.verification_status not in _VERIFIED_STATUSES:
                continue
        if capability is not None:
            hay = " ".join(m.can_detect).lower()
            if capability not in hay:
                continue
        matches.append(m)

    matches.sort(key=lambda m: (_grade_rank(m.evidence_grade), m.display_name.casefold()))
    return ModalityResult(
        capability=capability,
        regulatory_class=regulatory_class,
        phase_gate=phase_gate,
        is_diagnostic=False,
        modalities=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _modality_view(m: Modality) -> dict:
    return {
        "modalityId": m.modality_id,
        "displayName": m.display_name,
        "evidenceGrade": m.evidence_grade,
        "regulatoryClass": m.regulatory_class,
        "ionizing": m.ionizing,
        "ionizingReferralOnly": m.ionizing_referral_only,
        "phaseGate": m.phase_gate,
        "canDetect": list(m.can_detect),
        "cannotDetect": list(m.cannot_detect),
        "mayEmit": m.may_emit,
        "verificationStatus": m.verification_status,
        "provenance": m.provenance,
        "lastVerified": m.last_verified,
    }


def to_modality_ledger_record(
    result: ModalityResult,
    *,
    attested_by_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.kizashi.modalityCapability`` ledger record.

    ``isDiagnostic`` is asserted ``False`` and EVERY grade-X modality in the view
    is asserted ``mayEmit=False`` before return — G10 structural invariants this
    function cannot violate.
    """
    views = [_modality_view(m) for m in result.modalities]
    rec: dict = {
        "attestedByDid": attested_by_did,
        "isDiagnostic": False,
        "modalityCount": len(views),
        "emittingCount": sum(1 for m in result.modalities if m.may_emit),
        "excludedCount": sum(1 for m in result.modalities if not m.may_emit),
        "modalities": views,
        "createdAt": _iso_dt(created_at),
    }
    if result.capability is not None:
        rec["capabilityLabel"] = result.capability
    if result.regulatory_class is not None:
        rec["regulatoryClassFilter"] = result.regulatory_class
    if result.phase_gate is not None:
        rec["phaseGateFilter"] = result.phase_gate
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isDiagnostic"] is False, "invariant: isDiagnostic must be False"
    for m, view in zip(result.modalities, views):
        if m.evidence_grade == EXCLUDED_GRADE:
            assert view["mayEmit"] is False, "G10: grade-X modality may never emit"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the modality-capability seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("modalities"), list):
        raise ValueError(f"{path} is not a valid modality-capability registry")
    return data


__all__ = [
    "EVIDENCE_GRADE_ORDER",
    "EMITTING_GRADES",
    "EXCLUDED_GRADE",
    "REGULATORY_CLASSES",
    "ModalityQuery",
    "Modality",
    "ModalityResult",
    "may_emit",
    "resolve_modalities",
    "to_modality_ledger_record",
    "load_registry",
]
