"""Tests for the kizashi modality-capability ledger + G10 gate core (ADR-2605312700).

Locks the constitutional G10 anti-pseudoscience gate (grade-X modalities may
NEVER emit), the non-diagnostic invariant, the G9 ALARA ionizing=referral flag,
grade/regulatory-class validation, ledger filtering + sort, and integration
against the real modality seed. Pure stdlib, deterministic, no network.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification + ledger attestation); the pure gate
core lives in ``.modality_gate`` precisely so it is testable without the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_modality_gate.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .modality_gate import (
    EMITTING_GRADES,
    EVIDENCE_GRADE_ORDER,
    EXCLUDED_GRADE,
    REGULATORY_CLASSES,
    Modality,
    ModalityQuery,
    load_registry,
    may_emit,
    resolve_modalities,
    to_modality_ledger_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kizashi/registry/modalities.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(mid, *, grade="A-validated-clinical", reg_class="non-regulated-wellness",
           ionizing=False, phase="R2", can=None, cannot=None,
           status="unverified-seed", display=None):
    return {
        "modalityId": mid,
        "displayName": display or mid,
        "evidenceGrade": grade,
        "regulatoryClass": reg_class,
        "ionizing": ionizing,
        "phaseGate": phase,
        "canDetect": can if can is not None else ["surface geometry"],
        "cannotDetect": cannot if cannot is not None else ["disease diagnosis"],
        "councilAttestationCid": "",
        "verificationStatus": status,
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": "",
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.kizashi.modalityCapability", "modalities": list(entries)}


# ── G10 anti-pseudoscience gate: grade-X may NEVER emit ─────────────────


def test_may_emit_true_for_each_emitting_grade():
    for g in EMITTING_GRADES:
        assert may_emit(g) is True


def test_may_emit_false_for_excluded_grade():
    assert may_emit(EXCLUDED_GRADE) is False


def test_may_emit_unknown_grade_raises():
    with pytest.raises(ValueError):
        may_emit("Z-made-up-grade")


def test_grade_x_modality_has_may_emit_false_even_in_full_ledger():
    reg = _registry(
        _entry("real", grade="A-validated-clinical"),
        _entry("EXCLUDED-aura", grade=EXCLUDED_GRADE),
    )
    res = resolve_modalities(ModalityQuery(emitting_only=False), reg)  # full ledger
    by_id = {m.modality_id: m for m in res.modalities}
    assert by_id["EXCLUDED-aura"].may_emit is False
    assert by_id["real"].may_emit is True


def test_emitting_only_filter_drops_all_grade_x():
    reg = _registry(
        _entry("a", grade="A-validated-clinical"),
        _entry("b", grade="B-emerging-peer-reviewed"),
        _entry("c", grade="C-screening-only"),
        _entry("x", grade=EXCLUDED_GRADE),
    )
    res = resolve_modalities(ModalityQuery(emitting_only=True), reg)
    assert all(m.may_emit for m in res.modalities)
    assert "x" not in {m.modality_id for m in res.modalities}


@pytest.mark.parametrize("grade", sorted(EVIDENCE_GRADE_ORDER))
def test_may_emit_equals_grade_membership_for_every_grade(grade):
    res = resolve_modalities(ModalityQuery(), _registry(_entry("m", grade=grade)))
    m = res.modalities[0]
    assert m.may_emit is (grade in EMITTING_GRADES)


# ── non-diagnostic invariant ────────────────────────────────────────────


def test_modality_is_never_diagnostic():
    res = resolve_modalities(ModalityQuery(), _registry(_entry("a")))
    assert res.is_diagnostic is False
    assert all(m.is_diagnostic is False for m in res.modalities)


def test_can_and_cannot_detect_preserved_verbatim():
    reg = _registry(_entry("a", can=["joint angles"], cannot=["disc pathology", "pain"]))
    m = resolve_modalities(ModalityQuery(), reg).modalities[0]
    assert m.can_detect == ("joint angles",)
    assert m.cannot_detect == ("disc pathology", "pain")


# ── G9 ALARA: ionizing = referral-only ──────────────────────────────────


def test_ionizing_flagged_referral_only():
    reg = _registry(_entry("ct", ionizing=True), _entry("optical", ionizing=False))
    by_id = {m.modality_id: m for m in resolve_modalities(ModalityQuery(), reg).modalities}
    assert by_id["ct"].ionizing_referral_only is True
    assert by_id["optical"].ionizing_referral_only is False


def test_include_ionizing_false_drops_ionizing():
    reg = _registry(_entry("ct", ionizing=True), _entry("optical", ionizing=False))
    res = resolve_modalities(ModalityQuery(include_ionizing=False), reg)
    assert {m.modality_id for m in res.modalities} == {"optical"}


def test_ionizing_must_be_bool():
    bad = _entry("ct")
    bad["ionizing"] = "yes"
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), _registry(bad))


# ── grade / regulatory-class validation (no guessing) ───────────────────


def test_unknown_evidence_grade_in_registry_raises():
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), _registry(_entry("a", grade="totally-made-up")))


def test_unknown_regulatory_class_in_registry_raises():
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), _registry(_entry("a", reg_class="snake-oil-class")))


def test_unknown_regulatory_class_filter_raises():
    with pytest.raises(ValueError):
        resolve_modalities(
            ModalityQuery(regulatory_class="bogus"), _registry(_entry("a")))


def test_all_known_regulatory_classes_pass():
    reg = _registry(*[_entry(c, reg_class=c) for c in REGULATORY_CLASSES])
    res = resolve_modalities(ModalityQuery(), reg)
    assert {m.regulatory_class for m in res.modalities} == REGULATORY_CLASSES


# ── filtering + sort ────────────────────────────────────────────────────


def test_sort_by_grade_then_displayname():
    reg = _registry(
        _entry("x", grade=EXCLUDED_GRADE, display="AAA"),
        _entry("c", grade="C-screening-only", display="ZZZ"),
        _entry("a", grade="A-validated-clinical", display="MMM"),
    )
    res = resolve_modalities(ModalityQuery(), reg)
    assert [m.modality_id for m in res.modalities] == ["a", "c", "x"]


def test_grade_ties_broken_by_displayname_case_insensitive():
    reg = _registry(
        _entry("b", grade="A-validated-clinical", display="bravo"),
        _entry("a", grade="A-validated-clinical", display="Alpha"),
    )
    res = resolve_modalities(ModalityQuery(), reg)
    assert [m.display_name for m in res.modalities] == ["Alpha", "bravo"]


def test_capability_substring_filter_over_can_detect():
    reg = _registry(
        _entry("gait", can=["gait cadence", "stride length"]),
        _entry("thermal", can=["surface temperature"]),
    )
    res = resolve_modalities(ModalityQuery(capability="gait"), reg)
    assert [m.modality_id for m in res.modalities] == ["gait"]


def test_phase_gate_filter():
    reg = _registry(_entry("r2", phase="R2"), _entry("r3", phase="R3"))
    res = resolve_modalities(ModalityQuery(phase_gate="R3"), reg)
    assert [m.modality_id for m in res.modalities] == ["r3"]


def test_allow_unverified_false_drops_seed():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_modalities(ModalityQuery(allow_unverified=False), reg)
    assert [m.modality_id for m in res.modalities] == ["ok"]


# ── validation of malformed input ───────────────────────────────────────


def test_registry_without_modalities_list_raises():
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), {"modalities": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"modalityId": "a", "regulatoryClass": "non-regulated-wellness",
           "ionizing": False}  # no displayName / evidenceGrade
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), _registry(bad))


def test_can_detect_must_be_list():
    bad = _entry("a")
    bad["canDetect"] = "not-a-list"
    with pytest.raises(ValueError):
        resolve_modalities(ModalityQuery(), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_modality_is_frozen_may_emit_immutable():
    res = resolve_modalities(ModalityQuery(), _registry(_entry("x", grade=EXCLUDED_GRADE)))
    m = res.modalities[0]
    assert isinstance(m, Modality)
    assert m.may_emit is False
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        m.may_emit = True  # type: ignore[misc]


# ── ledger record builder ───────────────────────────────────────────────


def test_ledger_record_asserts_invariants_and_counts():
    reg = _registry(
        _entry("a", grade="A-validated-clinical"),
        _entry("x", grade=EXCLUDED_GRADE),
    )
    res = resolve_modalities(ModalityQuery(), reg)
    rec = to_modality_ledger_record(
        res, attested_by_did="did:web:council.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isDiagnostic"] is False
    assert rec["modalityCount"] == 2
    assert rec["emittingCount"] == 1
    assert rec["excludedCount"] == 1
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["sessionRef"] == "at://session/1"
    # the grade-X view carries mayEmit False
    x_view = next(v for v in rec["modalities"] if v["modalityId"] == "x")
    assert x_view["mayEmit"] is False


# ── integration: drive the real modality seed (14 modalities) ───────────


def test_registry_loads_with_expected_shape():
    data = load_registry(_REGISTRY)
    assert len(data["modalities"]) == 14
    res = resolve_modalities(ModalityQuery(), data)
    assert len(res.modalities) == 14  # whole ledger projects without raising


def test_real_seed_excluded_modalities_can_never_emit():
    data = load_registry(_REGISTRY)
    res = resolve_modalities(ModalityQuery(), data)
    excluded = [m for m in res.modalities if m.evidence_grade == EXCLUDED_GRADE]
    assert len(excluded) == 3  # bio-resonance / aura / quantum-zenshin-hadou
    assert all(m.may_emit is False for m in excluded)
    ids = {m.modality_id for m in excluded}
    assert {"EXCLUDED-bio-resonance", "EXCLUDED-aura-imaging",
            "EXCLUDED-quantum-zenshin-hadou"} <= ids


def test_real_seed_emitting_only_yields_eleven_non_excluded():
    data = load_registry(_REGISTRY)
    res = resolve_modalities(ModalityQuery(emitting_only=True), data)
    assert len(res.modalities) == 11
    assert all(m.may_emit for m in res.modalities)
    assert all(m.evidence_grade != EXCLUDED_GRADE for m in res.modalities)


def test_real_seed_single_ionizing_is_referral_only():
    data = load_registry(_REGISTRY)
    res = resolve_modalities(ModalityQuery(), data)
    ionizing = [m for m in res.modalities if m.ionizing]
    assert [m.modality_id for m in ionizing] == ["imaging-referral-mri-ct"]
    assert ionizing[0].ionizing_referral_only is True


def test_real_seed_ledger_record_excluded_count_is_three():
    data = load_registry(_REGISTRY)
    res = resolve_modalities(ModalityQuery(), data)
    rec = to_modality_ledger_record(
        res, attested_by_did="did:web:council.example",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    assert rec["modalityCount"] == 14
    assert rec["emittingCount"] == 11
    assert rec["excludedCount"] == 3
    assert rec["isDiagnostic"] is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
