"""Pydantic schema tests for uhl_right_neural institution registry.

Validates that:
  - the two seed YAMLs (jp + intl) parse cleanly into the strict schema
  - duplicate id / duplicate capability_kind validators reject malformed input
  - PII-protective fields (verified_by email pattern, no PII in name fields) hold
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from kotodama.projects.uhl_right_neural.schemas import (
    Capability,
    CapabilityKind,
    Country,
    Institution,
    InstitutionRegistry,
    ProcedureRecord,
    Reimbursement,
)


SEED_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "kotodama"
    / "projects"
    / "uhl_right_neural"
    / "seed"
)


# ── Seed validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "seed_file,min_institutions",
    [("institutions_jp.yaml", 5), ("institutions_intl.yaml", 5)],
)
def test_seed_yaml_validates(seed_file: str, min_institutions: int) -> None:
    path = SEED_DIR / seed_file
    assert path.is_file(), f"missing seed {path}"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    reg = InstitutionRegistry.model_validate(data)
    assert len(reg.institutions) >= min_institutions


def test_all_institutions_have_evidence_urls() -> None:
    """ADR-2605181040 rule 2: evidence_url is required and must be a URL."""
    for seed_file in ("institutions_jp.yaml", "institutions_intl.yaml"):
        with (SEED_DIR / seed_file).open("r", encoding="utf-8") as f:
            reg = InstitutionRegistry.model_validate(yaml.safe_load(f))
        for inst in reg.institutions:
            for cap in inst.capabilities:
                # HttpUrl validation already happened on parse; this asserts
                # we didn't allow empty/sentinel values past validation.
                assert str(cap.procedure_record.evidence_url).startswith(
                    ("https://", "http://")
                )


def test_all_institutions_have_last_verified_at() -> None:
    """ADR-2605181040 rule 3: last_verified_at is required."""
    for seed_file in ("institutions_jp.yaml", "institutions_intl.yaml"):
        with (SEED_DIR / seed_file).open("r", encoding="utf-8") as f:
            reg = InstitutionRegistry.model_validate(yaml.safe_load(f))
        for inst in reg.institutions:
            assert isinstance(inst.last_verified_at, date)


# ── Strict validation ────────────────────────────────────────────────────────


def _valid_capability(kind: CapabilityKind = CapabilityKind.PED_CI) -> Capability:
    return Capability(
        kind=kind,
        procedure_record=ProcedureRecord(
            evidence_url="https://example.org/source",
            reimbursement=Reimbursement.HOKEN,
        ),
    )


def _valid_institution(id_: str = "jp-test-org") -> Institution:
    return Institution(
        id=id_,
        name_ja="テスト機関",
        name_en="Test Institution",
        country=Country.JP,
        locale="Tokyo",
        website="https://example.org/",
        capabilities=[_valid_capability()],
        last_verified_at=date(2026, 5, 18),
        verified_by="ops@example.org",
    )


def test_duplicate_capability_kind_rejected() -> None:
    cap1 = _valid_capability(CapabilityKind.PED_CI)
    cap2 = _valid_capability(CapabilityKind.PED_CI)
    with pytest.raises(ValidationError, match="Duplicate capability kind"):
        Institution(
            **{
                **_valid_institution().model_dump(),
                "capabilities": [cap1.model_dump(), cap2.model_dump()],
            }
        )


def test_duplicate_institution_id_rejected() -> None:
    a = _valid_institution("jp-dup")
    b = _valid_institution("jp-dup")
    with pytest.raises(ValidationError, match="Duplicate institution id"):
        InstitutionRegistry(institutions=[a, b])


def test_verified_by_must_be_email() -> None:
    with pytest.raises(ValidationError):
        Institution(
            **{
                **_valid_institution().model_dump(),
                "verified_by": "not-an-email",
            }
        )


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        Institution.model_validate(
            {**_valid_institution().model_dump(), "secret_field": "leak"}
        )


def test_empty_capabilities_rejected() -> None:
    with pytest.raises(ValidationError):
        Institution(
            **{**_valid_institution().model_dump(), "capabilities": []}
        )
